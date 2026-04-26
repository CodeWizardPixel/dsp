from util import (
    BlockFrequencyFilter,
    apply_frequency_filter,
    chebyshev_gain,
    ripple_db_to_epsilon,
)


DEFAULT_CUTOFF_HZ = 4000
DEFAULT_ORDER = 4
DEFAULT_RIPPLE_DB = 1


def chebyshev_low_pass_gain(
    frequency_hz,
    cutoff_hz,
    order,
    epsilon,
):
    return chebyshev_gain(frequency_hz, cutoff_hz, order, epsilon)


def chebyshev_low_pass_filter(
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
        lambda frequency_hz: chebyshev_low_pass_gain(
            frequency_hz,
            cutoff_hz,
            order,
            epsilon,
        ),
    )


class StreamingChebyshevLowPassFilter(BlockFrequencyFilter):
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
            lambda frequency_hz: chebyshev_low_pass_gain(
                frequency_hz,
                cutoff_hz,
                order,
                epsilon,
            ),
            gain_db,
        )
