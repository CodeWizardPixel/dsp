import wave
import winsound


file_path = "audio.wav"

# Read WAV file metadata.
with wave.open(file_path, "rb") as wav_file:
    channels = wav_file.getnchannels()
    sample_width = wav_file.getsampwidth()
    frame_rate = wav_file.getframerate()
    frames = wav_file.getnframes()

    print("Каналов:", channels)
    print("Байт на сэмпл:", sample_width)
    print("Частота дискретизации:", frame_rate)
    print("Количество фреймов:", frames)

# Play WAV file.
winsound.PlaySound(file_path, winsound.SND_FILENAME)
