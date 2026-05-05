# AI Maintenance Notes

Этот файл предназначен для будущей нейросети или разработчика, который будет поддерживать проект.

Проект - учебный программный аудиопроигрыватель с 8-полосным эквалайзером, тремя типами буфера и двумя семействами фильтров.

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
  shifting_buffer.py

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
- включение аудиоэффектов;
- запуск воспроизведения через PyAudio;
- класс `EqualizerPlayer`.

Важные константы:

```python
BUFFER_MODE_DUAL_THREAD = "dual_thread"
BUFFER_MODE_SINGLE_THREAD = "single_thread"
BUFFER_MODE_SHIFTING = "shifting"
DUAL_THREAD_INPUT_FRAMES_PER_CYCLE = 2
SINGLE_THREAD_INPUT_FRAMES_PER_CYCLE = 8
RING_BUFFER_OUTPUT_FRAMES_PER_CYCLE = 1
FILTER_TYPE_SINC = "sinc"
FILTER_TYPE_CHEBYSHEV = "chebyshev"
```

`BYTES_PER_SAMPLE = 2`, выход всегда mono int16 (`OUTPUT_CHANNELS = 1`).

`DUAL_THREAD_INPUT_FRAMES_PER_CYCLE` и `SINGLE_THREAD_INPUT_FRAMES_PER_CYCLE` разделены специально: можно менять размер пачки записи для двухпоточного и однопоточного кольцевого буфера независимо.

`RING_BUFFER_OUTPUT_FRAMES_PER_CYCLE = 1` означает, что кольцевые буферы отдают на воспроизведение по одному выходному сэмплу за раз. Смещающий буфер работает отдельно и отдает на `stream.write(...)` сразу вторую половину буфера.

Общая цепочка обработки сэмплов перед записью в любой буфер:

```text
WAV bytes -> mono samples -> filter bank -> effects -> selected buffer -> PyAudio
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

После фильтрации вызывается `process_audio_samples(...)`. Там последовательно применяются включенные эффекты:

```text
filter bank -> reverb, если включен -> clipping, если включен
```

## Эффекты

Эффекты находятся в `play_wav.py` и применяются после эквалайзера, но до записи в буфер.

### Реверберация

Класс:

```python
ReverbEffect
```

Это простая delay-line реверберация с обратной связью. Основные константы:

```python
DEFAULT_REVERB_DELAY_MS = 120
DEFAULT_REVERB_DECAY = 0.35
DEFAULT_REVERB_WET = 0.35
```

`ReverbEffect` хранит внутренний delay-buffer, поэтому эффект должен создаваться заново при старте воспроизведения и построении фильтров:

```python
self.reverb = ReverbEffect(sample_rate)
```

При изменении чекбокса в UI во время воспроизведения меняется только флаг `reverb_enabled`; состояние delay-buffer не сбрасывается.

### Клиппинг

Функция:

```python
clip_samples(...)
```

Это hard clipping:

```text
sample < -threshold -> -threshold
sample > threshold -> threshold
```

Порог:

```python
DEFAULT_CLIPPING_THRESHOLD = 12000
```

После клиппинга финальная защита от выхода за диапазон int16 все равно остается в `clamp_int16(...)`, который вызывается при конвертации samples -> PCM bytes.

## Буферы

В UI размер буфера можно выбрать от `2` до `512` байт.

Для кольцевых буферов размер должен быть четным.

Для смещающего буфера размер должен быть кратен `4`, потому что буфер делится на две половины и каждая половина должна содержать целое число 16-битных mono-сэмплов.

### `buffers/dual_thread_ring_buffer.py`

Двухпоточный кольцевой буфер.

Используется в режиме:

```python
BUFFER_MODE_DUAL_THREAD
```

Схема:

```text
producer thread -> filter -> effects -> pending bytes -> RingBufferDualThread -> PyAudio callback
```

Внутри используется `Condition`, потому что один поток пишет, другой читает.

Producer заранее читает WAV блоками, фильтрует данные и складывает готовые PCM-байты во внутренний `pending`-буфер. Когда в кольце освобождается достаточно места, producer быстро переносит готовые байты из `pending` в `RingBufferDualThread`.

Запись в кольцо идет пачками, размер пачки задает:

```python
DUAL_THREAD_INPUT_FRAMES_PER_CYCLE
```

Но пачка ограничивается половиной кольцевого буфера, чтобы producer не ждал полного опустошения буфера.

Чтение из кольца в callback происходит по одному сэмплу:

```python
read_sample() -> 2 bytes
```

Размер PyAudio callback для кольцевого режима:

```python
RING_BUFFER_OUTPUT_FRAMES_PER_CYCLE = 1
```

### `buffers/single_thread_ring_buffer.py`

Однопоточный кольцевой буфер.

Используется в режиме:

```python
BUFFER_MODE_SINGLE_THREAD
```

Схема:

```text
filter -> effects -> fill ring buffer -> read one sample -> wait for enough free space -> write next sample batch
```

Блокировок нет, потому что всё происходит в одном потоке.

Сначала буфер заполняется до упора. Затем каретка чтения сдвигается по одному сэмплу:

```python
read_sample() -> stream.write(sample_data)
```

После каждого сдвига проверяется свободное место. Новая запись происходит только когда освободилось место под пачку:

```python
SINGLE_THREAD_INPUT_FRAMES_PER_CYCLE * BYTES_PER_SAMPLE
```

То есть при `SINGLE_THREAD_INPUT_FRAMES_PER_CYCLE = 8` запись ждет, пока чтение освободит `16` байт, и только потом читает из WAV и записывает 8 новых mono-сэмплов.

### `buffers/shifting_buffer.py`

Смещающий буфер.

Используется в режиме:

```python
BUFFER_MODE_SHIFTING
```

Схема:

```text
WAV chunk sized like first half -> filter -> effects -> first half -> shift -> second half -> stream.write(second half)
```

Буфер разделен на две части:

```text
[ первая часть: запись ] -> shift -> [ вторая часть: чтение ]
```

В первую часть записываются отфильтрованные данные. Когда первая часть заполнена, данные смещаются во вторую часть. Воспроизведение читает из второй части целиком:

```python
output_bytes_per_chunk = self.ring_buffer.part_capacity
stream.write(data)
```

Из WAV в этом режиме читается количество фреймов, соответствующее размеру первой половины буфера. Для mono 16-bit WAV это ровно `part_capacity` байт, для stereo 16-bit WAV `readframes(...)` читает больше байт из файла, но после `stereo_to_mono(...)` на выход попадает mono int16.

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
- включить реверберацию;
- включить клиппинг;
- изменить размер буфера в байтах;
- изменить усиление каждой из 8 полос от `0 dB` до `-100 dB`;
- старт/стоп воспроизведения.

Эффекты находятся в группе `Эффекты`:

```text
[ ] Реверберация
[ ] Клиппинг
```

Чекбоксы можно менять во время воспроизведения. UI передает изменения в текущий `PlayerWorker`, а тот вызывает:

```python
set_reverb_enabled(...)
set_clipping_enabled(...)
```

Кнопка `Стоп` должна сбрасывать воспроизведение, но не закрывать приложение.

При старте воспроизведения UI корректирует размер буфера:

- для смещающего режима - до кратности `4`;
- для двухпоточного кольцевого режима - не меньше `DUAL_THREAD_INPUT_FRAMES_PER_CYCLE * BYTES_PER_SAMPLE`;
- для однопоточного кольцевого режима - не меньше `SINGLE_THREAD_INPUT_FRAMES_PER_CYCLE * BYTES_PER_SAMPLE`;
- для кольцевых режимов - до четного значения.

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
2. Слишком маленький `ring_buffer_size_bytes`.
3. Непрерывность состояния фильтра между блоками.
4. Слишком короткое FIR-ядро.

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
