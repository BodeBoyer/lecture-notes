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


def _run(*args) -> str:
    result = subprocess.run(
        [PYTHON, NOTES, *args],
        capture_output=True,
        text=True,
        cwd=HERE,
    )
    output = (result.stdout + result.stderr).strip()
    return output if output else "(no output)"


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
        device: Device index from list_devices(). Pass -1 to auto-detect.
    """
    args = ["record-start", course, f"--{mode}"]
    if device >= 0:
        args += ["--device", str(device)]
    return _run(*args)


@mcp.tool()
def stop_recording() -> str:
    """Stop the current background recording, transcribe it, and generate structured notes."""
    return _run("record-stop")


@mcp.tool()
def summarize_recording(index: int = 0) -> str:
    """
    Generate a conversational summary of a saved recording.

    Args:
        index: Index from list_recordings(). Defaults to 0 (most recent).
    """
    return _run("summarize", str(index))


if __name__ == "__main__":
    mcp.run()
