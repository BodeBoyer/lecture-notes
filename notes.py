#!/usr/bin/env python3
"""
Lecture & meeting notes CLI.

Commands:
    record-start <course> [--virtual | --mic]
        Start recording in the background (returns immediately).
        --virtual  : capture system audio (Zoom, Teams, browser) via BlackHole
        --mic      : capture from external/USB microphone (default)

    record-stop
        Stop the background recording, transcribe, and generate notes.

    record <course> [--virtual | --mic]
        Record interactively (press Enter to stop). For use in a normal terminal.

    process <file> <course>
        Generate notes from an existing audio or video file.

Examples:
    python notes.py record-start "COMP 210"
    python notes.py record-start "COMP 210" --virtual
    python notes.py record-stop

    python notes.py process lecture.m4a "COMP 210"
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
NOTES_DIR = HERE / "notes"
STATE_FILE = Path.home() / ".lecture-notes-state.json"
STOP_FILE = Path.home() / ".lecture-notes-stop"


def load_env():
    env_file = HERE / ".env"
    if not env_file.exists():
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def _export_transcript_text(transcript: Any) -> str:
    if hasattr(transcript, "export_text"):
        return transcript.export_text()
    return str(transcript).strip()


def save_notes(course: str, notes: str, transcript: Any, source_filename: str) -> Path:
    safe_course = course.replace(" ", "-").replace("/", "-").upper()
    course_dir = NOTES_DIR / safe_course
    course_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(source_filename).stem.replace(" ", "-")
    today = date.today().isoformat()
    out_path = course_dir / f"{today}_{stem}.md"

    transcript_text = _export_transcript_text(transcript)
    if not transcript_text:
        raise RuntimeError("Refusing to save notes without transcript text")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(notes)
        f.write("\n\n---\n\n")
        f.write("## Raw Transcript\n\n")
        f.write(transcript_text)
        f.write("\n")

    return out_path


def run_pipeline(audio_file: str, course: str, source_label: str):
    from transcriber import transcribe
    from summarizer import generate_notes

    print(f"Course / meeting: {course}\n")

    transcript = transcribe(audio_file, include_metadata=True)
    transcript_text = transcript.text

    print(f"Transcript length: {len(transcript_text.split())} words\n")

    notes = generate_notes(transcript_text, course)

    out_path = save_notes(course, notes, transcript, source_label)

    print(f"\nNotes saved to: {out_path}")
    print("\n" + "=" * 60)
    print(notes)


def _parse_device_flag(args):
    """Extract --device <idx> value from args, return (int or None, remaining_args)."""
    result = None
    cleaned = []
    i = 0
    while i < len(args):
        if args[i] == "--device" and i + 1 < len(args):
            try:
                result = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        else:
            cleaned.append(args[i])
            i += 1
    return result, cleaned


def _resolve_device(args):
    """Return (device_idx, device_name, mode_label) based on flags."""
    from recorder import setup_virtual_recording, setup_inperson_recording

    device_override, args = _parse_device_flag(args)
    flags = {a for a in args if a.startswith("--")}
    virtual = "--virtual" in flags

    if virtual:
        device_idx, device_name = setup_virtual_recording()
        return device_idx, device_name, "virtual"

    if device_override is not None:
        from recorder import list_input_devices

        devices = dict(list_input_devices())
        device_name = devices.get(device_override, f"Device {device_override}")
        return device_override, device_name, "inperson"

    device_idx, device_name = setup_inperson_recording()
    return device_idx, device_name, "inperson"


def cmd_list_devices(_args):
    """list-devices — print numbered input devices for the skill to present."""
    from recorder import list_input_devices
    for idx, name in list_input_devices():
        print(f"{idx}: {name}")


def cmd_record_start(args):
    """record-start <course> [--virtual | --mic]"""
    positional = [a for a in args if not a.startswith("--")]

    if not positional:
        print("Usage: python notes.py record-start <course> [--virtual | --mic]")
        sys.exit(1)

    course = positional[0]

    if STATE_FILE.exists():
        print("A recording is already in progress. Run: python notes.py record-stop")
        sys.exit(1)

    device_idx, device_name, mode = _resolve_device(args)

    # Temp file for the recording — kept until record-stop cleans it up
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=HERE)
    tmp.close()
    audio_path = tmp.name

    # Clean up any leftover stop file
    STOP_FILE.unlink(missing_ok=True)

    # Launch daemon detached so it outlives this process
    daemon = str(HERE / "recorder_daemon.py")
    python = str(HERE / ".venv" / "bin" / "python")
    proc = subprocess.Popen(
        [python, daemon, audio_path, str(device_idx), str(STOP_FILE)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    state = {
        "course": course,
        "mode": mode,
        "device_name": device_name,
        "audio_path": audio_path,
        "pid": proc.pid,
        "started": date.today().isoformat(),
    }
    STATE_FILE.write_text(json.dumps(state))

    print(f"Recording started.")
    print(f"  Course : {course}")
    print(f"  Device : {device_name} ({mode})")
    print(f"  PID    : {proc.pid}")
    print(f"\nWhen done, run: python notes.py record-stop")


def cmd_record_stop(_args):
    """record-stop — stop background recording, transcribe, generate notes."""
    if not STATE_FILE.exists():
        print("No recording in progress.")
        sys.exit(1)

    state = json.loads(STATE_FILE.read_text())
    course = state["course"]
    audio_path = state["audio_path"]

    print("Stopping recording...")
    STOP_FILE.touch()

    # Wait for daemon to finish writing the audio file
    import time
    for _ in range(30):
        time.sleep(1)
        try:
            import psutil
            if not psutil.pid_exists(state["pid"]):
                break
        except ImportError:
            # psutil not available — just wait a fixed amount
            time.sleep(3)
            break

    STATE_FILE.unlink(missing_ok=True)
    STOP_FILE.unlink(missing_ok=True)

    if not Path(audio_path).exists():
        print("Error: audio file was not written. Recording may have failed.")
        sys.exit(1)

    try:
        run_pipeline(audio_path, course, source_label=f"recording_{state['started']}")
    finally:
        os.unlink(audio_path)


def cmd_record(args):
    """record <course> [--virtual | --mic] — interactive, press Enter to stop."""
    from recorder import record

    positional = [a for a in args if not a.startswith("--")]
    if not positional:
        print("Usage: python notes.py record <course> [--virtual | --mic]")
        sys.exit(1)

    course = positional[0]
    device_idx, device_name, mode = _resolve_device(args)

    print(f"Device: {device_name}")
    tmp_path = record(device_index=device_idx, label=mode)
    try:
        run_pipeline(tmp_path, course, source_label=f"recording_{date.today().isoformat()}")
    finally:
        os.unlink(tmp_path)


def cmd_process(args):
    """process <file> <course>"""
    if len(args) < 2:
        print("Usage: python notes.py process <file> <course>")
        sys.exit(1)
    audio_file, course = args[0], args[1]
    print(f"Processing: {audio_file}")
    run_pipeline(audio_file, course, source_label=audio_file)


def cmd_list_notes(_args):
    """list-notes — print all saved notes files, newest first."""
    files = sorted(NOTES_DIR.glob("*/*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        print("No notes found.")
        return
    for i, f in enumerate(files):
        course = f.parent.name
        print(f"{i}: {course} — {f.stem} ({f})")


def cmd_summarize(args):
    """summarize [<notes_file>] — casual conversational summary of a recording."""
    from summarizer import generate_casual_summary
    import re

    if args and not args[0].startswith("--"):
        # Explicit file path or index from list-notes
        target = args[0]
        if target.isdigit():
            files = sorted(NOTES_DIR.glob("*/*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            idx = int(target)
            if idx >= len(files):
                print(f"No notes file at index {idx}. Run list-notes to see options.")
                sys.exit(1)
            notes_file = files[idx]
        else:
            notes_file = Path(target)
    else:
        # Default: most recent notes file
        files = sorted(NOTES_DIR.glob("*/*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            print("No notes found. Record something first.")
            sys.exit(1)
        notes_file = files[0]

    if not notes_file.exists():
        print(f"File not found: {notes_file}")
        sys.exit(1)

    content = notes_file.read_text(encoding="utf-8")
    if "## Raw Transcript" not in content:
        print("No transcript found in this notes file.")
        sys.exit(1)

    raw = content.split("## Raw Transcript")[1].strip()
    transcript = re.sub(r'\[\d+:\d+:\d+\.\d+ - \d+:\d+:\d+\.\d+\] ', '', raw).strip()
    context = f"Recording: {notes_file.parent.name} / {notes_file.stem}"

    print(f"Summarizing: {notes_file}\n")
    summary = generate_casual_summary(transcript, context)
    print(summary)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    load_env()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set. Add it to lecture-notes/.env")
        sys.exit(1)

    command = sys.argv[1]
    rest = sys.argv[2:]

    if command == "list-devices":
        cmd_list_devices(rest)
    elif command == "list-notes":
        cmd_list_notes(rest)
    elif command == "summarize":
        cmd_summarize(rest)
    elif command == "record-start":
        cmd_record_start(rest)
    elif command == "record-stop":
        cmd_record_stop(rest)
    elif command == "record":
        cmd_record(rest)
    elif command == "process":
        cmd_process(rest)
    else:
        if len(sys.argv) >= 3 and Path(sys.argv[1]).exists():
            cmd_process(sys.argv[1:3])
        else:
            print(__doc__)
            sys.exit(1)


if __name__ == "__main__":
    main()
