import io
import math
import wave
from array import array

import winsound


def sinc_kernel(sample_rate, cutoff_hz, taps=101):
    if taps % 2 == 0:
        taps += 1

    fc = cutoff_hz / sample_rate
    center = taps // 2
    kernel = []

    for i in range(taps):
        n = i - center

        if n == 0:
            value = 2 * fc
        else:
            value = math.sin(2 * math.pi * fc * n) / (math.pi * n)

        kernel.append(value)

    return kernel


def hamming_window(size):
    return [
        0.54 - 0.46 * math.cos(2 * math.pi * i / (size - 1))
        for i in range(size)
    ]


def apply_window(kernel, window):
    return [kernel[i] * window[i] for i in range(len(kernel))]


def normalize_kernel(kernel):
    kernel_sum = sum(kernel)
    return [x / kernel_sum for x in kernel]


def convolve(samples, kernel):
    center = len(kernel) // 2
    output = []

    for i in range(len(samples)):
        acc = 0
        for j in range(len(kernel)):
            index = i - j + center
            if 0 <= index < len(samples):
                acc += samples[index] * kernel[j]
        output.append(acc)

    return output


def sinc_filter(samples, sample_rate, cutoff_hz, taps=101):
    kernel = sinc_kernel(sample_rate, cutoff_hz, taps)
    window = hamming_window(len(kernel))
    kernel = apply_window(kernel, window)
    #kernel = normalize_kernel(kernel)

    return convolve(samples, kernel)


def clamp_int16(value):
    return max(-32768, min(32767, int(value)))


def stereo_to_mono(samples):
    mono = []

    for i in range(0, len(samples) - 1, 2):
        mono.append((samples[i] + samples[i + 1]) / 2)

    return mono


class SampleBuffer:
    def __init__(self, sample_rate, cutoff_hz, taps=101):
        self.sample_rate = sample_rate
        self.samples = []

        self.kernel = sinc_kernel(sample_rate, cutoff_hz, taps)
        self.kernel = apply_window(self.kernel, hamming_window(len(self.kernel)))
        #self.kernel = normalize_kernel(self.kernel)

    def add_samples(self, samples):
        self.samples.extend(samples)

    def filter(self):
        return convolve(self.samples, self.kernel)

    def play(self):
        filtered = self.filter()
        pcm = bytearray()

        if len(filtered) == 0:
            return

        max_value = max(abs(sample) for sample in filtered)
        if max_value <= 1:
            filtered = [sample * 32767 for sample in filtered]

        for sample in filtered:
            sample = clamp_int16(sample)
            pcm += sample.to_bytes(2, byteorder="little", signed=True)

        wav_data = io.BytesIO()
        with wave.open(wav_data, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm)

        winsound.PlaySound(wav_data.getvalue(), winsound.SND_MEMORY)



file_path = "audio.wav"

with wave.open(file_path, "rb") as wav_file:
    channels = wav_file.getnchannels()
    sample_width = wav_file.getsampwidth()
    frame_rate = wav_file.getframerate()
    frames = wav_file.readframes(frame_rate*5)

samples = array("h")
samples.frombytes(frames)

# if channels == 2:
#     samples = stereo_to_mono(samples)

buffer = SampleBuffer(sample_rate=frame_rate, cutoff_hz=4000, taps=31)
buffer.add_samples(samples)
buffer.play()
