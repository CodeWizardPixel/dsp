from filters.chebyshev.chebyshev_lowpass_filter import DEFAULT_ORDER, DEFAULT_RIPPLE_DB
from util import (
    BlockFrequencyFilter,
    apply_frequency_filter,
    chebyshev_gain_by_ratio,
    ripple_db_to_epsilon,
)


DEFAULT_CUTOFF_HZ = 4000


def high_pass_frequency_ratio(frequency_hz, cutoff_hz):
    if frequency_hz == 0:
        return float("inf")

    return cutoff_hz / frequency_hz


def chebyshev_high_pass_gain(
    frequency_hz,
    cutoff_hz,
    order,
    epsilon,
):
    if frequency_hz == 0:
        return 0

    frequency_ratio = high_pass_frequency_ratio(frequency_hz, cutoff_hz)
    return chebyshev_gain_by_ratio(frequency_ratio, order, epsilon)


def chebyshev_high_pass_filter(
    samples,
    sample_rate,
    cutoff_hz=DEFAULT_CUTOFF_HZ,
    order=DEFAULT_ORDER,
    ripple_db=DEFAULT_RIPPLE_DB,
):
    epsilon = ripple_db_to_epsilon(ripple_db)

    return apply_frequency_filter(
        samples,
        sample_rate,
        lambda frequency_hz: chebyshev_high_pass_gain(
            frequency_hz,
            cutoff_hz,
            order,
            epsilon,
        ),
    )


class StreamingChebyshevHighPassFilter(BlockFrequencyFilter):
    def __init__(
        self,
        sample_rate,
        cutoff_hz=DEFAULT_CUTOFF_HZ,
        order=DEFAULT_ORDER,
        ripple_db=DEFAULT_RIPPLE_DB,
        gain_db=0,
    ):
        epsilon = ripple_db_to_epsilon(ripple_db)

        super().__init__(
            sample_rate,
            lambda frequency_hz: chebyshev_high_pass_gain(
                frequency_hz,
                cutoff_hz,
                order,
                epsilon,
            ),
            gain_db,
        )
