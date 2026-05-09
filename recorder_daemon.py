"""
Background recording daemon. Launched by notes.py record-start, stopped by notes.py record-stop.

Usage: python recorder_daemon.py <audio_path> <device_index|None> <stop_file>
"""
import os
import sys
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 16000


def main():
    if len(sys.argv) < 4:
        print("Usage: recorder_daemon.py <audio_path> <device_index|None> <stop_file>")
        sys.exit(1)

    audio_path = sys.argv[1]
    raw_device = sys.argv[2]
    stop_file = sys.argv[3]
    device_index = int(raw_device) if raw_device != "None" else None

    frames = []

    def callback(indata, frame_count, time_info, status):
        frames.append(indata.copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=device_index,
        callback=callback,
    ):
        while not os.path.exists(stop_file):
            time.sleep(0.5)

    if frames:
        audio = np.concatenate(frames, axis=0)
        sf.write(audio_path, audio, SAMPLE_RATE)
    else:
        try:
            os.unlink(audio_path)
        except FileNotFoundError:
            pass
        raise RuntimeError("No audio was captured.")


if __name__ == "__main__":
    main()
