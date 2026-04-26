from util import (
    StreamingFirFilter,
    apply_window,
    build_hamming_window,
    convolve,
    make_odd,
    sinc_value,
)


DEFAULT_LOW_CUTOFF_HZ = 300
DEFAULT_HIGH_CUTOFF_HZ = 4000
DEFAULT_TAP_COUNT = 31


def build_band_pass_kernel(sample_rate, low_cutoff_hz, high_cutoff_hz, tap_count=101):
    tap_count = make_odd(tap_count)
    low_cutoff_ratio = low_cutoff_hz / sample_rate
    high_cutoff_ratio = high_cutoff_hz / sample_rate
    center = tap_count // 2
    kernel = []

    for tap_index in range(tap_count):
        sample_offset = tap_index - center
        high_pass_part = sinc_value(sample_offset, high_cutoff_ratio)
        low_pass_part = sinc_value(sample_offset, low_cutoff_ratio)
        kernel.append(high_pass_part - low_pass_part)

    window = build_hamming_window(len(kernel))
    return apply_window(kernel, window)


def band_pass_filter(
    samples,
    sample_rate,
    low_cutoff_hz,
    high_cutoff_hz,
    taps=DEFAULT_TAP_COUNT,
    gain_db=0,
):
    kernel = build_band_pass_kernel(
        sample_rate,
        low_cutoff_hz,
        high_cutoff_hz,
        taps,
    )
    return convolve(samples, kernel, gain_db)


class StreamingBandPassFilter(StreamingFirFilter):
    def __init__(
        self,
        sample_rate,
        low_cutoff_hz=DEFAULT_LOW_CUTOFF_HZ,
        high_cutoff_hz=DEFAULT_HIGH_CUTOFF_HZ,
        tap_count=DEFAULT_TAP_COUNT,
        gain_db=0,
    ):
        kernel = build_band_pass_kernel(
            sample_rate,
            low_cutoff_hz,
            high_cutoff_hz,
            tap_count,
        )
        super().__init__(kernel, gain_db)
