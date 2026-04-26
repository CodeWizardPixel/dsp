import wave
from array import array

import pyaudio

from band_pass_filter import StreamingBandPassFilter
from highpass_sinc_filter import StreamingHighPassFilter
from lowpass_sinc_filter import DEFAULT_TAP_COUNT, StreamingLowPassFilter


DEFAULT_BLOCK_SIZE = 1024
DEFAULT_BAND_GAINS_DB = {
    1: 0,
    2: 0,
    3: 0,
    4: 0,
    5: 0,
    6: 0,
    7: 0,
    8: 0,
}


def clamp_int16(value):
    return max(-32768, min(32767, int(value)))


def stereo_to_mono(samples):
    mono_samples = []

    for index in range(0, len(samples) - 1, 2):
        left = samples[index]
        right = samples[index + 1]
        mono_samples.append((left + right) / 2)

    return mono_samples


def bytes_to_samples(frames, channels):
    samples = array("h")
    samples.frombytes(frames)

    if channels == 2:
        return stereo_to_mono(samples)

    return samples


def samples_to_bytes(samples):
    pcm = array("h")

    for sample in samples:
        pcm.append(clamp_int16(sample))

    return pcm.tobytes()


def build_filter_bank(sample_rate, taps, band_gains_db=None):
    gains = DEFAULT_BAND_GAINS_DB.copy()
    if band_gains_db is not None:
        gains.update(band_gains_db)

    return [
        StreamingLowPassFilter(sample_rate, 100, taps, gains[1]),
        StreamingBandPassFilter(sample_rate, 100, 300, taps, gains[2]),
        StreamingBandPassFilter(sample_rate, 300, 700, taps, gains[3]),
        StreamingBandPassFilter(sample_rate, 700, 1500, taps, gains[4]),
        StreamingBandPassFilter(sample_rate, 1500, 3100, taps, gains[5]),
        StreamingBandPassFilter(sample_rate, 3100, 6300, taps, gains[6]),
        StreamingBandPassFilter(sample_rate, 6300, 12700, taps, gains[7]),
        StreamingHighPassFilter(sample_rate, 12700, taps, gains[8]),
    ]


def mix_filter_outputs(filter_outputs):
    mixed_samples = []

    for samples_at_time in zip(*filter_outputs):
        mixed_samples.append(sum(samples_at_time))

    return mixed_samples


def process_samples_with_filter_bank(samples, filters):
    filter_outputs = []

    for audio_filter in filters:
        filter_outputs.append(audio_filter.process_samples(samples))

    return mix_filter_outputs(filter_outputs)


def play_wav_with_filter(
    file_path,
    taps=DEFAULT_TAP_COUNT,
    block_size=DEFAULT_BLOCK_SIZE,
    band_gains_db=None,
):
    wav_file = wave.open(file_path, "rb")
    channels = wav_file.getnchannels()
    sample_rate = wav_file.getframerate()
    filters = build_filter_bank(sample_rate, taps, band_gains_db)

    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=sample_rate,
        output=True,
        frames_per_buffer=block_size,
    )

    frames = wav_file.readframes(block_size)
    while frames:
        samples = bytes_to_samples(frames, channels)
        filtered_samples = process_samples_with_filter_bank(samples, filters)
        stream.write(samples_to_bytes(filtered_samples))
        frames = wav_file.readframes(block_size)

    stream.stop_stream()
    stream.close()
    audio.terminate()
    wav_file.close()


if __name__ == "__main__":
    play_wav_with_filter("audio1.wav")
