# AI Maintenance Notes

Этот файл предназначен для будущей нейросети или разработчика, который будет поддерживать проект.

Проект - учебный программный аудиопроигрыватель с 8-полосным эквалайзером, двумя типами кольцевого буфера и двумя семействами фильтров.

## Главное ограничение

Фильтры Чебышева I рода должны строиться по формуле АЧХ:

```text
H(w) = 1 / sqrt(1 + epsilon^2 * Tn^2(w / w0))
```

Нельзя использовать готовое проектирование фильтра из `scipy.signal`, например:

```python
cheby1
cheby2
butter
sosfilt
lfilter
```

Разрешено использовать преобразования Фурье из SciPy, например:

```python
scipy.fft.rfft
scipy.fft.irfft
scipy.fft.rfftfreq
scipy.fft.fftshift
```

То есть SciPy можно использовать как вычислительный инструмент, но не как готовый генератор фильтра.

## Структура проекта

```text
play_wav.py
util.py

buffers/
  dual_thread_ring_buffer.py
  single_thread_ring_buffer.py

filters/
  sinc/
    lowpass_sinc_filter.py
    band_pass_filter.py
    highpass_sinc_filter.py

  chebyshev/
    chebyshev_lowpass_filter.py
    chebyshev_bandpass_filter.py
    chebyshev_highpass_filter.py
    chebyshev_filter_bank.py

ui/
  main_window.py
```

## `play_wav.py`

Главный модуль воспроизведения.

Содержит:

- чтение WAV;
- перевод stereo в mono;
- конвертацию PCM bytes <-> samples;
- выбор типа буфера;
- выбор типа фильтра;
- запуск воспроизведения через PyAudio;
- класс `EqualizerPlayer`.

Важные константы:

```python
BUFFER_MODE_DUAL_THREAD = "dual_thread"
BUFFER_MODE_SINGLE_THREAD = "single_thread"
FILTER_TYPE_SINC = "sinc"
FILTER_TYPE_CHEBYSHEV = "chebyshev"
```

Функция `build_filter_bank(...)` выбирает семейство фильтров.

Для Sinc FIR возвращается список из 8 потоковых фильтров.

Для Чебышева возвращается один объект:

```python
ChebyshevFilterBank
```

Поэтому `process_samples_with_filter_bank(...)` поддерживает оба случая:

```python
if hasattr(filters, "process_samples"):
    return filters.process_samples(samples)
```

## Буферы

### `buffers/dual_thread_ring_buffer.py`

Двухпоточный кольцевой буфер.

Используется в режиме:

```python
BUFFER_MODE_DUAL_THREAD
```

Схема:

```text
producer thread -> RingBufferDualThread -> PyAudio callback
```

Внутри используется `Condition`, потому что один поток пишет, другой читает.

### `buffers/single_thread_ring_buffer.py`

Однопоточный кольцевой буфер.

Используется в режиме:

```python
BUFFER_MODE_SINGLE_THREAD
```

Схема:

```text
read wav -> filter -> write buffer -> read buffer -> stream.write
```

Блокировок нет, потому что всё происходит в одном потоке.

## Sinc FIR фильтры

Лежат в:

```text
filters/sinc/
```

Файлы:

- `lowpass_sinc_filter.py`
- `band_pass_filter.py`
- `highpass_sinc_filter.py`

Эти фильтры строят FIR-ядра напрямую и используют `StreamingFirFilter` из `util.py`.

Окно Хэмминга используется для сглаживания обрезанного ядра.

## Чебышев I рода

Лежит в:

```text
filters/chebyshev/
```

Главная формула АЧХ находится в `util.py`:

```python
def chebyshev_gain_by_ratio(frequency_ratio, order, epsilon):
    chebyshev_value = chebyshev_polynomial(order, frequency_ratio)
    return 1 / math.sqrt(1 + epsilon * epsilon * chebyshev_value * chebyshev_value)
```

Многочлен Чебышева:

```python
def chebyshev_polynomial(order, x):
```

Перевод ripple в epsilon:

```python
def ripple_db_to_epsilon(ripple_db):
```

### Отдельные формулы

НЧ:

```python
chebyshev_low_pass_gain(...)
```

ПФ:

```python
chebyshev_band_pass_gain(...)
```

ВЧ:

```python
chebyshev_high_pass_gain(...)
```

### `chebyshev_filter_bank.py`

Это 8-полосный банк Чебышева для реального воспроизведения.

Он не должен использовать `scipy.signal.cheby1`.

Текущая идея:

1. По формуле Чебышева считается суммарная АЧХ 8 полос.
2. Через `irfft` получается импульсная характеристика.
3. Берётся центральный кусок длиной `DEFAULT_TAP_COUNT`.
4. К нему применяется окно Хэмминга.
5. Получается FIR-ядро.
6. Звук фильтруется потоковой свёрткой с историей сэмплов.

Это сделано, чтобы не обрабатывать каждый аудиоблок как отдельный FFT-кусок. Блочная FFT-обработка без overlap/save или overlap/add давала щелчки на границах блоков.

## UI

Главный файл:

```text
ui/main_window.py
```

Интерфейс позволяет:

- выбрать WAV-файл;
- выбрать тип буфера;
- выбрать тип фильтра;
- изменить размер аудиоблока;
- изменить число блоков кольцевого буфера;
- изменить предзаполнение;
- изменить усиление каждой из 8 полос от `0 dB` до `-100 dB`;
- старт/стоп воспроизведения.

Кнопка `Стоп` должна сбрасывать воспроизведение, но не закрывать приложение.

## Полосы эквалайзера

```text
1: 0-100 Hz
2: 100-300 Hz
3: 300-700 Hz
4: 700-1500 Hz
5: 1500-3100 Hz
6: 3100-6300 Hz
7: 6300-12700 Hz
8: 12700-22050 Hz
```

Полоса 1 - НЧ.

Полосы 2-7 - полосовые.

Полоса 8 - ВЧ.

## Усиление полос

UI передаёт значения в dB:

```text
0 ... -100
```

Перевод в линейный коэффициент:

```python
def db_to_gain(db):
    return 10 ** (db / 20)
```

При движении слайдера вызывается:

```python
set_band_gain(band_number, gain_db)
```

Для Sinc FIR меняется gain конкретного фильтра.

Для Чебышева пересобирается суммарное FIR-ядро.

## Что делать при щелчках

Проверять в таком порядке:

1. Клиппинг после суммирования полос.
2. Слишком маленький `block_size`.
3. Слишком маленький `ring_buffer_blocks`.
4. Слишком маленький `prefill_blocks` для двухпоточного режима.
5. Непрерывность состояния фильтра между блоками.
6. Слишком короткое FIR-ядро.

Для Чебышева вероятный источник щелчков - слишком короткий `DEFAULT_TAP_COUNT` или слишком резкие переходы АЧХ.

## Проверка после изменений

Минимальная проверка:

```powershell
python -m py_compile util.py play_wav.py ui\main_window.py filters\sinc\*.py filters\chebyshev\*.py buffers\*.py
```

Запуск UI:

```powershell
python ui\main_window.py
```

## Стиль проекта

Это учебный проект. Код должен быть простым и понятным.

Не добавлять сложные абстракции без необходимости.

Не прятать важную DSP-математику за готовыми библиотечными функциями, если по ТЗ требуется реализация формулы.

Сторонние библиотеки допустимы для:

- PyAudio;
- PyQt5;
- FFT из SciPy.

Сторонние библиотеки не должны использоваться для готового синтеза Чебышевских фильтров.
