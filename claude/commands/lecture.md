Start a live recording (in-person or virtual meeting), OR process a pre-recorded lecture video, then generate a transcript and structured notes.

## Step 1 — get recording type

Use AskUserQuestion to ask:
- "What type of lecture?" with options:
  - In-person / external mic (live recording)
  - Virtual meeting via BlackHole (live: Zoom, Teams, browser)
  - Pre-recorded video — local file or URL (YouTube, Panopto, Zoom share link)

## Step 2 — get course/meeting name

Ask the user: "What is the course or meeting name?" (free text)

## Step 3 — branch on type

### A) Pre-recorded video

1. Ask the user: "What's the source? Paste a URL (YouTube, Panopto, Zoom) or a local file path."
2. If the URL looks SSO-protected (e.g. contains `panopto`, `sakai`, `instructure`, `unc.edu`), use AskUserQuestion to ask: "This source likely needs browser cookies. Which browser are you logged in with?" — options: chrome, firefox, safari, edge.
3. Run the process command. URL example:
```
{{LECTURE_NOTES_PATH}}/.venv/bin/python {{LECTURE_NOTES_PATH}}/notes.py process "<url_or_path>" "<course>" [--browser-cookies <browser>]
```
4. Long lectures can take 10–30 minutes (download + Whisper transcription + Claude notes). Tell the user this up front and stream the output.
5. When done, the output ends with the saved notes file path — print the notes inline so the user can read them in the chat.

### B) Live: in-person

1. List available microphones:
```
{{LECTURE_NOTES_PATH}}/.venv/bin/python {{LECTURE_NOTES_PATH}}/notes.py list-devices
```
The output will be lines like `0: MacBook Pro Microphone`. Use AskUserQuestion to present the device names as options and ask "Which microphone should be used?". Note the index number.
2. Start the recording:
```
{{LECTURE_NOTES_PATH}}/.venv/bin/python {{LECTURE_NOTES_PATH}}/notes.py record-start "<course>" --mic --device <idx>
```
3. Tell the user: recording is running in the background; type `/lecture-stop` when done.

### C) Live: virtual meeting

1. Start the recording:
```
{{LECTURE_NOTES_PATH}}/.venv/bin/python {{LECTURE_NOTES_PATH}}/notes.py record-start "<course>" --virtual
```
2. Tell the user: recording is running in the background; type `/lecture-stop` when done.
