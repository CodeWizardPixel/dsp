import math
from collections import deque

from scipy.fft import irfft, rfft, rfftfreq


def make_odd(value):
    if value % 2 == 0:
        return value + 1
    return value


def sinc_value(sample_offset, cutoff_ratio):
    if sample_offset == 0:
        return 2 * cutoff_ratio

    return math.sin(2 * math.pi * cutoff_ratio * sample_offset) / (
        math.pi * sample_offset
    )


def build_hamming_window(size):
    return [
        0.54 - 0.46 * math.cos(2 * math.pi * index / (size - 1))
        for index in range(size)
    ]


def apply_window(kernel, window):
    return [
        kernel_value * window_value
        for kernel_value, window_value in zip(kernel, window)
    ]


def normalize_kernel(kernel):
    kernel_sum = sum(kernel)
    if kernel_sum == 0:
        return kernel

    return [kernel_value / kernel_sum for kernel_value in kernel]


def db_to_gain(db):
    return 10 ** (db / 20)


def chebyshev_polynomial(order, x):
    if order == 0:
        return 1

    if order == 1:
        return x

    previous = 1
    current = x

    for _index in range(2, order + 1):
        next_value = 2 * x * current - previous
        previous = current
        current = next_value

    return current


def ripple_db_to_epsilon(ripple_db):
    return math.sqrt(10 ** (ripple_db / 10) - 1)


def chebyshev_gain_by_ratio(frequency_ratio, order, epsilon):
    chebyshev_value = chebyshev_polynomial(order, frequency_ratio)

    return 1 / math.sqrt(1 + epsilon * epsilon * chebyshev_value * chebyshev_value)


def chebyshev_gain(frequency_hz, cutoff_hz, order, epsilon):
    return chebyshev_gain_by_ratio(frequency_hz / cutoff_hz, order, epsilon)


def apply_frequency_filter(samples, sample_rate, gain_function, gain_db=0):
    gain = db_to_gain(gain_db)
    sample_count = len(samples)
    spectrum = rfft(samples)
    frequencies = rfftfreq(sample_count, 1 / sample_rate)

    for index, frequency_hz in enumerate(frequencies):
        spectrum[index] *= gain_function(frequency_hz) * gain

    return irfft(spectrum, sample_count).tolist()


def convolve(samples, kernel, gain_db=0):
    center = len(kernel) // 2
    gain = db_to_gain(gain_db)
    output = []

    for sample_index in range(len(samples)):
        filtered_sample = 0

        for kernel_index, kernel_value in enumerate(kernel):
            input_index = sample_index - kernel_index + center
            if 0 <= input_index < len(samples):
                filtered_sample += samples[input_index] * kernel_value

        output.append(filtered_sample * gain)

    return output


class StreamingFirFilter:
    def __init__(self, kernel, gain_db=0):
        self.kernel = kernel
        self.history = deque([0] * len(kernel), maxlen=len(kernel))
        self.set_gain_db(gain_db)

    def set_gain_db(self, gain_db):
        self.gain_db = gain_db
        self.gain = db_to_gain(gain_db)

    def process_sample(self, sample):
        self.history.appendleft(sample)
        filtered_sample = 0

        for sample_value, kernel_value in zip(self.history, self.kernel):
            filtered_sample += sample_value * kernel_value

        return filtered_sample * self.gain

    def process_samples(self, samples):
        return [self.process_sample(sample) for sample in samples]


class BlockFrequencyFilter:
    def __init__(self, sample_rate, gain_function, gain_db=0):
        self.sample_rate = sample_rate
        self.gain_function = gain_function
        self.set_gain_db(gain_db)

    def set_gain_db(self, gain_db):
        self.gain_db = gain_db
        self.gain = db_to_gain(gain_db)

    def process_samples(self, samples):
        return apply_frequency_filter(
            samples,
            self.sample_rate,
            self.gain_function,
            self.gain_db,
        )
