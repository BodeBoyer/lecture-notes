# lecture-notes

Local-first lecture and meeting notes for macOS. Records audio (in-person mic or virtual meeting via BlackHole), transcribes with on-device MLX Whisper, then generates structured Markdown notes with Claude.

Pre-recorded video also supported — point it at a local file or a URL (YouTube, Panopto, Zoom share link, anything `yt-dlp` handles).

## Pipeline

1. **Source** — live audio capture, local audio/video file, or URL
2. **Transcription** — MLX Whisper `large-v3` running on your Mac (free, no API)
3. **Notes** — Claude API turns the transcript into structured study notes

Output: `notes/<COURSE>/<date>_<filename>.md` containing the polished notes followed by the raw timestamped transcript.

## Setup

Requires macOS, Python 3.9+, and an Anthropic API key.

```bash
git clone https://github.com/BodeBoyer/lecture-notes.git
cd lecture-notes
./setup.sh
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env
brew install ffmpeg          # required for video files (mp4, mov, etc.)
brew install blackhole-2ch   # only if you want to record virtual meetings
```

The first run downloads the Whisper `large-v3` model (~3GB) from Hugging Face — one-time.

## Usage

### Live recording

```bash
.venv/bin/python notes.py record-start "COMP 210" --mic
# ...attend lecture...
.venv/bin/python notes.py record-stop
```

For virtual meetings (Zoom/Teams/browser audio), use `--virtual` instead of `--mic` after configuring BlackHole as your audio output.

### Pre-recorded lecture (file or URL)

```bash
# Local file
.venv/bin/python notes.py process ~/Downloads/lecture.mp4 "COMP 210"

# YouTube
.venv/bin/python notes.py process "https://youtube.com/watch?v=XXXX" "COMP 210"

# Panopto / SSO-protected source — uses your browser's saved cookies
.venv/bin/python notes.py process "https://uncch.hosted.panopto.com/..." "COMP 210" --browser-cookies chrome
```

### Other commands

```bash
.venv/bin/python notes.py list-notes              # all saved notes, newest first
.venv/bin/python notes.py summarize               # casual summary of most recent recording
.venv/bin/python notes.py summarize 0             # summarize by index from list-notes
```

## Claude Code / Desktop integration

This repo ships slash commands and an MCP server for invoking the pipeline from Claude.

### Slash commands (Claude Code)

```bash
./claude/install.sh
```

Installs `/lecture` and `/lecture-stop` into `~/.claude/commands/` with absolute paths fixed to your clone. Re-run after pulling updates.

### MCP server (Claude Desktop)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lecture-notes": {
      "command": "/absolute/path/to/lecture-notes/.venv-mcp/bin/python",
      "args": ["/absolute/path/to/lecture-notes/mcp_server.py"]
    }
  }
}
```

Then restart Claude Desktop. Tools exposed: `start_recording`, `stop_recording`, `process_video`, `list_devices`, `list_recordings`, `summarize_recording`.

## How accurate is the transcription?

Whisper `large-v3` averages ~92–96% word-level accuracy on clear single-speaker lecture audio. Common failure modes: technical jargon, proper nouns, acronyms, math read aloud. Heavy accents or overlapping speakers will hurt accuracy further. The transcript is good enough that Claude can write solid notes, but expect occasional misheard technical terms in both.
