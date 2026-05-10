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

## NotebookLM bridge (Google Drive)

Notes can auto-upload to Google Drive after each run, so a per-course folder can be added once as a NotebookLM source. NotebookLM has no public API for personal accounts, so this is the supported path; new files dropped into the folder show up after a manual source refresh in the NotebookLM UI.

### One-time Google Cloud setup

1. Open [console.cloud.google.com](https://console.cloud.google.com), create (or pick) a project.
2. Enable the **Google Drive API** under *APIs & Services → Library*.
3. *APIs & Services → OAuth consent screen* → user type **External**, fill the minimum required fields, add your Google account as a test user, save.
4. *APIs & Services → Credentials → Create credentials → OAuth client ID* → application type **Desktop app** → download the JSON.
5. Save the JSON as `credentials/oauth_client.json` inside this repo (the `credentials/` directory is gitignored).

### Enable per run

```bash
echo 'LECTURE_NOTES_DRIVE_PUSH=1' >> .env
```

Optional overrides:

```
LECTURE_NOTES_DRIVE_ROOT_FOLDER_NAME=lecture-notes   # default
LECTURE_NOTES_DRIVE_ROOT_FOLDER_ID=                  # optional app-accessible Drive folder id
```

The first upload opens a browser consent flow; after that the refresh token in `credentials/token.json` keeps things non-interactive.

### Smoke test

```bash
.venv/bin/python drive_uploader.py notes/COMP-210/2026-05-10_recording.md "COMP 210"
```

Then in NotebookLM, create a notebook for the course and add the `lecture-notes/COMP-210` folder as a Google Drive source. Re-add or refresh the source after new uploads.

## NotebookLM direct push (experimental, Phase 2)

In addition to the Drive upload above, notes can also be pushed *directly* into a NotebookLM notebook as a Markdown source via the unofficial [`notebooklm-py`](https://github.com/teng-lin/notebooklm-py) wrapper. This avoids the manual "refresh source" click in NotebookLM after each new lecture.

**Caveats:** the wrapper drives NotebookLM's internal browser endpoints — there is no public API for personal Google accounts. Google can change those endpoints at any time, so treat this as best-effort. The Drive path stays as the reliable fallback.

### One-time setup

```bash
.venv/bin/pip install -r requirements-nblm.txt
.venv/bin/playwright install chromium
.venv/bin/python notebooklm_login.py  # opens browser; sign in with your NotebookLM Google account
```

> The bundled `notebooklm-py` CLI has used Python 3.10-only syntax in some releases. This repo supports Python 3.9+, so `notebooklm_login.py` drives the same Playwright login flow without importing that CLI module.

In the NotebookLM web UI, create a notebook for each course you want to push to. Copy the notebook id out of the URL — it's the long string after `/notebook/`:

```
https://notebooklm.google.com/notebook/<NOTEBOOK_ID>
```

### Configure per-run push

Add to `.env`:

```
LECTURE_NOTES_NBLM_PUSH=1
LECTURE_NOTES_NBLM_NOTEBOOKS=COMP-210=<id>,COMP-301=<id>
```

Course keys are canonicalized to uppercase + hyphens (so `"COMP 210"` matches `COMP-210=...`). Courses without a mapping are silently skipped, so it's safe to enable globally and add notebooks one course at a time.

### Smoke test

```bash
.venv/bin/python notebooklm_pusher.py notes/COMP-210/2026-05-10_recording.md "COMP 210"
```

The pipeline runs Drive push first, then NotebookLM push — both opt-in, both warn-and-continue on failure.

## How accurate is the transcription?

Whisper `large-v3` averages ~92–96% word-level accuracy on clear single-speaker lecture audio. Common failure modes: technical jargon, proper nouns, acronyms, math read aloud. Heavy accents or overlapping speakers will hurt accuracy further. The transcript is good enough that Claude can write solid notes, but expect occasional misheard technical terms in both.
