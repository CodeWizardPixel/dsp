from util import (
    StreamingFirFilter,
    apply_window,
    build_hamming_window,
    convolve,
    make_odd,
    sinc_value,
)


DEFAULT_CUTOFF_HZ = 4000
DEFAULT_TAP_COUNT = 31


def build_high_pass_kernel(sample_rate, cutoff_hz, tap_count=101):
    tap_count = make_odd(tap_count)
    cutoff_ratio = cutoff_hz / sample_rate
    center = tap_count // 2
    kernel = []

    for tap_index in range(tap_count):
        sample_offset = tap_index - center
        low_pass_value = sinc_value(sample_offset, cutoff_ratio)

        if tap_index == center:
            kernel.append(1 - low_pass_value)
        else:
            kernel.append(-low_pass_value)

    window = build_hamming_window(len(kernel))
    return apply_window(kernel, window)


def high_pass_filter(samples, sample_rate, cutoff_hz, taps=DEFAULT_TAP_COUNT, gain_db=0):
    kernel = build_high_pass_kernel(sample_rate, cutoff_hz, taps)
    return convolve(samples, kernel, gain_db)


class StreamingHighPassFilter(StreamingFirFilter):
    def __init__(
        self,
        sample_rate,
        cutoff_hz=DEFAULT_CUTOFF_HZ,
        tap_count=DEFAULT_TAP_COUNT,
        gain_db=0,
    ):
        kernel = build_high_pass_kernel(sample_rate, cutoff_hz, tap_count)
        super().__init__(kernel, gain_db)
