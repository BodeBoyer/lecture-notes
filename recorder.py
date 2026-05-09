import os
import sys
import tempfile
import threading
from typing import Optional

import numpy as np
import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 16000
BLACKHOLE_NAME = "blackhole"
EXTERNAL_MIC_KEYWORDS = ["usb", "external", "blue", "samson", "yeti", "snowball", "rode", "shure"]


def list_input_devices():
    devices = sd.query_devices()
    return [
        (i, d["name"])
        for i, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]


def _find_device_by_keyword(keywords):
    for idx, name in list_input_devices():
        if any(kw in name.lower() for kw in keywords):
            return idx, name
    return None, None


def get_virtual_device():
    """Return the BlackHole device index, or None if not installed."""
    idx, name = _find_device_by_keyword([BLACKHOLE_NAME])
    return idx, name


def get_external_mic():
    """Return an external/USB mic device index, or fall back to system default."""
    idx, name = _find_device_by_keyword(EXTERNAL_MIC_KEYWORDS)
    if idx is not None:
        return idx, name
    # Fall back to system default input
    default = sd.query_devices(kind="input")
    return None, default["name"]


def _prompt_device_choice(devices):
    """Let the user pick from a numbered list. Returns device index."""
    print("\nAvailable input devices:")
    for i, (dev_idx, name) in enumerate(devices):
        print(f"  [{i}] {name}")
    while True:
        try:
            choice = int(input("Select device number: ").strip())
            if 0 <= choice < len(devices):
                return devices[choice][0]
        except (ValueError, KeyboardInterrupt):
            pass
        print("Invalid choice, try again.")


def record(device_index: Optional[int] = None, label: str = "audio") -> str:
    """
    Record from device_index until the user presses Enter.
    Returns path to a temp WAV file (caller is responsible for cleanup).
    """
    frames = []
    stop_event = threading.Event()

    def callback(indata, frame_count, time_info, status):
        if not stop_event.is_set():
            frames.append(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=device_index,
        callback=callback,
    )

    try:
        with stream:
            print(f"\nRecording {label}...")
            print("Press Enter to stop.\n")
            input()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()

    if not frames:
        raise RuntimeError("No audio was captured.")

    audio = np.concatenate(frames, axis=0)
    duration = len(audio) / SAMPLE_RATE
    print(f"Captured {duration:.1f}s of audio.")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    sf.write(tmp.name, audio, SAMPLE_RATE)
    return tmp.name


def setup_virtual_recording():
    """
    Guide the user through BlackHole setup if not installed.
    Returns (device_index, device_name) ready to record from.
    """
    idx, name = get_virtual_device()
    if idx is not None:
        print(f"Virtual audio device found: {name}")
        return idx, name

    print(
        "\nBlackHole is not installed. It's a free virtual audio driver that lets\n"
        "you record system audio (Zoom, Teams, browser, etc.).\n\n"
        "To install:\n"
        "  brew install blackhole-2ch\n\n"
        "After installing, go to:\n"
        "  System Settings → Sound → Output → select 'BlackHole 2ch'\n"
        "(You'll hear silence from your speakers while routing — use headphones.)\n\n"
        "Then re-run this command.\n"
    )
    sys.exit(1)


def setup_inperson_recording():
    """
    Auto-detect external mic or let user choose from available devices.
    Returns (device_index, device_name) ready to record from.
    """
    idx, name = get_external_mic()

    # If we found a known external mic keyword, confirm and use it
    if idx is not None:
        print(f"External mic detected: {name}")
        confirm = input("Use this device? [Y/n]: ").strip().lower()
        if confirm in ("", "y", "yes"):
            return idx, name

    # Otherwise show all devices and let user pick
    devices = list_input_devices()
    if not devices:
        raise RuntimeError("No input audio devices were found.")
    idx = _prompt_device_choice(devices)
    name = next(n for i, n in devices if i == idx)
    return idx, name
