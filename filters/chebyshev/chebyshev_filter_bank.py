import numpy as np
from scipy.signal import cheby1, sosfilt

from filters.chebyshev.chebyshev_lowpass_filter import DEFAULT_ORDER, DEFAULT_RIPPLE_DB
from util import db_to_gain


CHEBYSHEV_BANDS = [
    ("lowpass", 100),
    ("bandpass", (100, 300)),
    ("bandpass", (300, 700)),
    ("bandpass", (700, 1500)),
    ("bandpass", (1500, 3100)),
    ("bandpass", (3100, 6300)),
    ("bandpass", (6300, 12700)),
    ("highpass", 12700),
]


class ChebyshevFilterBank:
    def __init__(
        self,
        sample_rate,
        band_gains_db,
        order=DEFAULT_ORDER,
        ripple_db=DEFAULT_RIPPLE_DB,
    ):
        self.sample_rate = sample_rate
        self.order = order
        self.ripple_db = ripple_db
        self.band_gains_db = band_gains_db.copy()
        self.band_gains = {}
        self.filters = []

        for band_number, gain_db in self.band_gains_db.items():
            self.band_gains[band_number] = db_to_gain(gain_db)

        self.build_filters()

    def build_filters(self):
        for filter_type, cutoff in CHEBYSHEV_BANDS:
            sos = cheby1(
                self.order,
                self.ripple_db,
                cutoff,
                btype=filter_type,
                fs=self.sample_rate,
                output="sos",
            )
            state = np.zeros((sos.shape[0], 2))
            self.filters.append([sos, state])

    def set_band_gain(self, band_number, gain_db):
        self.band_gains_db[band_number] = gain_db
        self.band_gains[band_number] = db_to_gain(gain_db)

    def process_samples(self, samples):
        input_samples = np.asarray(samples, dtype=float)
        output_samples = np.zeros_like(input_samples)

        for band_index, filter_state in enumerate(self.filters, start=1):
            sos, state = filter_state
            filtered_samples, new_state = sosfilt(sos, input_samples, zi=state)
            filter_state[1] = new_state
            output_samples += filtered_samples * self.band_gains[band_index]

        return output_samples.tolist()
