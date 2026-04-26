from util import (
    StreamingFirFilter,
    apply_window,
    build_hamming_window,
    convolve,
    make_odd,
    normalize_kernel,
    sinc_value,
)


DEFAULT_CUTOFF_HZ = 4000
DEFAULT_TAP_COUNT = 31


def build_sinc_kernel(sample_rate, cutoff_hz, tap_count=101):
    tap_count = make_odd(tap_count)
    cutoff_ratio = cutoff_hz / sample_rate
    center = tap_count // 2

    return [
        sinc_value(tap_index - center, cutoff_ratio)
        for tap_index in range(tap_count)
    ]


def build_low_pass_kernel(sample_rate, cutoff_hz, tap_count):
    kernel = build_sinc_kernel(sample_rate, cutoff_hz, tap_count)
    window = build_hamming_window(len(kernel))
    windowed_kernel = apply_window(kernel, window)

    return normalize_kernel(windowed_kernel)


def sinc_filter(samples, sample_rate, cutoff_hz, taps=101, gain_db=0):
    kernel = build_low_pass_kernel(sample_rate, cutoff_hz, taps)
    return convolve(samples, kernel, gain_db)


class StreamingLowPassFilter(StreamingFirFilter):
    def __init__(self, sample_rate, cutoff_hz, tap_count=101, gain_db=0):
        kernel = build_low_pass_kernel(sample_rate, cutoff_hz, tap_count)
        super().__init__(kernel, gain_db)
