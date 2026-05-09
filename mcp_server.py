#!/usr/bin/env python3
"""
MCP server exposing lecture-notes tools to the Claude desktop app.
Runs as a subprocess managed by Claude; communicates via stdio.
"""
import os
import subprocess
from mcp.server.fastmcp import FastMCP

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(HERE, ".venv", "bin", "python")
NOTES = os.path.join(HERE, "notes.py")

mcp = FastMCP("lecture-notes")


def _run(*args, timeout=20) -> str:
    """Run a notes.py subcommand with stdin closed so it never blocks on input."""
    result = subprocess.run(
        [PYTHON, NOTES, *args],
        capture_output=True,
        text=True,
        cwd=HERE,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
    )
    output = (result.stdout + result.stderr).strip()
    return output if output else "(no output)"


def _auto_pick_device() -> int:
    """Pick the first non-BlackHole input device without prompting."""
    devices_output = _run("list-devices")
    for line in devices_output.splitlines():
        if "blackhole" not in line.lower() and ":" in line:
            try:
                return int(line.split(":")[0].strip())
            except ValueError:
                pass
    return 0


@mcp.tool()
def list_devices() -> str:
    """List available audio input devices with their index numbers."""
    return _run("list-devices")


@mcp.tool()
def list_recordings() -> str:
    """List all saved recordings and notes files, newest first."""
    return _run("list-notes")


@mcp.tool()
def start_recording(course: str, mode: str, device: int = -1) -> str:
    """
    Start a background recording.

    Args:
        course: Course or meeting name (e.g. "COMP 210" or "Internship standup")
        mode: "mic" for in-person with external mic, "virtual" for Zoom/Teams via BlackHole
        device: Device index from list_devices(). Omit to auto-select.
    """
    if mode == "mic" and device < 0:
        device = _auto_pick_device()

    args = ["record-start", course, f"--{mode}"]
    if device >= 0:
        args += ["--device", str(device)]
    return _run(*args)


@mcp.tool()
def stop_recording() -> str:
    """Stop the current background recording, transcribe it, and generate structured notes."""
    # Transcription + Claude can take several minutes for long recordings
    return _run("record-stop", timeout=600)


@mcp.tool()
def summarize_recording(index: int = 0) -> str:
    """
    Generate a conversational summary of a saved recording.

    Args:
        index: Index from list_recordings(). Defaults to 0 (most recent).
    """
    return _run("summarize", str(index), timeout=60)


if __name__ == "__main__":
    mcp.run()
