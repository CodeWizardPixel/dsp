import time
import wave
from array import array
from threading import Thread

import pyaudio

from band_pass_filter import StreamingBandPassFilter
from highpass_sinc_filter import StreamingHighPassFilter
from lowpass_sinc_filter import DEFAULT_TAP_COUNT, StreamingLowPassFilter
from dual_thread_ring_buffer import RingBufferDualThread
from single_thread_ring_buffer import SingleThreadRingBuffer


DEFAULT_BLOCK_SIZE = 128
DEFAULT_RING_BUFFER_BLOCKS = 8
DEFAULT_PREFILL_BLOCKS = 2
BUFFER_MODE_DUAL_THREAD = "dual_thread"
BUFFER_MODE_SINGLE_THREAD = "single_thread"
OUTPUT_CHANNELS = 1
BYTES_PER_SAMPLE = 2
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


class EqualizerPlayer:
    def __init__(
        self,
        file_path,
        buffer_mode=BUFFER_MODE_DUAL_THREAD,
        taps=DEFAULT_TAP_COUNT,
        block_size=DEFAULT_BLOCK_SIZE,
        ring_buffer_blocks=DEFAULT_RING_BUFFER_BLOCKS,
        prefill_blocks=DEFAULT_PREFILL_BLOCKS,
        band_gains_db=None,
    ):
        self.file_path = file_path
        self.buffer_mode = buffer_mode
        self.taps = taps
        self.block_size = block_size
        self.ring_buffer_blocks = ring_buffer_blocks
        self.prefill_blocks = prefill_blocks
        self.band_gains_db = DEFAULT_BAND_GAINS_DB.copy()
        self.filters = []
        self.ring_buffer = None
        self.stopped = False

        if band_gains_db is not None:
            self.band_gains_db.update(band_gains_db)

    def set_band_gain(self, band_number, gain_db):
        self.band_gains_db[band_number] = gain_db

        if self.filters:
            self.filters[band_number - 1].set_gain_db(gain_db)

    def stop(self):
        self.stopped = True

        if self.ring_buffer is not None:
            self.ring_buffer.close()

    def play(self):
        if self.buffer_mode == BUFFER_MODE_SINGLE_THREAD:
            self.play_single_thread()
        else:
            self.play_dual_thread()

    def build_filters(self, sample_rate):
        self.filters = build_filter_bank(sample_rate, self.taps, self.band_gains_db)

    def write_filtered_audio_to_buffer_dual_thread(self, wav_file):
        channels = wav_file.getnchannels()

        frames = wav_file.readframes(self.block_size)
        while frames and not self.stopped:
            samples = bytes_to_samples(frames, channels)
            filtered_samples = process_samples_with_filter_bank(samples, self.filters)
            self.ring_buffer.write(samples_to_bytes(filtered_samples))
            frames = wav_file.readframes(self.block_size)

        self.ring_buffer.close()

    def play_dual_thread(self):
        wav_file = wave.open(self.file_path, "rb")
        sample_rate = wav_file.getframerate()
        self.build_filters(sample_rate)

        bytes_per_block = self.block_size * OUTPUT_CHANNELS * BYTES_PER_SAMPLE
        self.ring_buffer = RingBufferDualThread(
            bytes_per_block * self.ring_buffer_blocks
        )
        prefill_size = bytes_per_block * self.prefill_blocks

        producer = Thread(
            target=self.write_filtered_audio_to_buffer_dual_thread,
            args=(wav_file,),
        )
        producer.start()

        while (
            self.ring_buffer.available() < prefill_size
            and producer.is_alive()
            and not self.stopped
        ):
            time.sleep(0.001)

        def play_from_ring_buffer(in_data, frame_count, time_info, status_flags):
            bytes_needed = frame_count * OUTPUT_CHANNELS * BYTES_PER_SAMPLE
            data, finished = self.ring_buffer.read(bytes_needed)

            if finished or self.stopped:
                return data, pyaudio.paComplete

            return data, pyaudio.paContinue

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=OUTPUT_CHANNELS,
            rate=sample_rate,
            output=True,
            frames_per_buffer=self.block_size,
            stream_callback=play_from_ring_buffer,
            start=False,
        )

        stream.start_stream()

        while stream.is_active() and not self.stopped:
            time.sleep(0.05)

        self.stop()
        stream.stop_stream()
        stream.close()
        audio.terminate()
        producer.join()
        wav_file.close()

    def play_single_thread(self):
        wav_file = wave.open(self.file_path, "rb")
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        self.build_filters(sample_rate)

        bytes_per_block = self.block_size * OUTPUT_CHANNELS * BYTES_PER_SAMPLE
        self.ring_buffer = SingleThreadRingBuffer(
            bytes_per_block * self.ring_buffer_blocks
        )

        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=OUTPUT_CHANNELS,
            rate=sample_rate,
            output=True,
            frames_per_buffer=self.block_size,
        )

        frames = wav_file.readframes(self.block_size)
        while frames and not self.stopped:
            samples = bytes_to_samples(frames, channels)
            filtered_samples = process_samples_with_filter_bank(samples, self.filters)
            self.ring_buffer.write(samples_to_bytes(filtered_samples))

            data, finished = self.ring_buffer.read(bytes_per_block)
            stream.write(data)

            if finished:
                break

            frames = wav_file.readframes(self.block_size)

        self.ring_buffer.close()

        while self.ring_buffer.available() > 0 and not self.stopped:
            data, finished = self.ring_buffer.read(bytes_per_block)
            stream.write(data)

            if finished:
                break

        stream.stop_stream()
        stream.close()
        audio.terminate()
        wav_file.close()


def play_wav_with_filter_dual_thread(
    file_path,
    taps=DEFAULT_TAP_COUNT,
    block_size=DEFAULT_BLOCK_SIZE,
    band_gains_db=None,
    ring_buffer_blocks=DEFAULT_RING_BUFFER_BLOCKS,
    prefill_blocks=DEFAULT_PREFILL_BLOCKS,
):
    player = EqualizerPlayer(
        file_path,
        BUFFER_MODE_DUAL_THREAD,
        taps,
        block_size,
        ring_buffer_blocks,
        prefill_blocks,
        band_gains_db,
    )
    player.play()


def play_wav_with_filter_single_thread(
    file_path,
    taps=DEFAULT_TAP_COUNT,
    block_size=DEFAULT_BLOCK_SIZE,
    band_gains_db=None,
    ring_buffer_blocks=DEFAULT_RING_BUFFER_BLOCKS,
):
    player = EqualizerPlayer(
        file_path,
        BUFFER_MODE_SINGLE_THREAD,
        taps,
        block_size,
        ring_buffer_blocks,
        0,
        band_gains_db,
    )
    player.play()


if __name__ == "__main__":
    # play_wav_with_filter_single_thread("audio1.wav")
    play_wav_with_filter_dual_thread("audio.wav")
