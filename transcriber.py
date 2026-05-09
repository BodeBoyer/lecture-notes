import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".aiff", ".aif"}

# Small = fast + good quality for clear speech like lectures.
# Swap to "mlx-community/whisper-medium-mlx" if accuracy is lacking.
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Transcript:
    text: str
    segments: List[TranscriptSegment]
    language: Optional[str] = None

    def export_text(self) -> str:
        """Return a faithful, readable transcript export from Whisper segments."""
        if not self.segments:
            return self.text

        lines = []
        for segment in self.segments:
            text = segment.text.strip()
            if not text:
                continue
            start = _format_timestamp(segment.start)
            end = _format_timestamp(segment.end)
            lines.append(f"[{start} - {end}] {text}")

        return "\n".join(lines) if lines else self.text


def _format_timestamp(seconds: float) -> str:
    milliseconds = round(max(seconds, 0.0) * 1000.0)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def _transcript_from_result(result: Dict[str, Any]) -> Transcript:
    text = (result.get("text") or "").strip()
    segments = []

    for raw_segment in result.get("segments") or []:
        segment_text = (raw_segment.get("text") or "").strip()
        if not segment_text:
            continue
        try:
            start = float(raw_segment["start"])
            end = float(raw_segment["end"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Malformed transcript segment: {raw_segment!r}") from exc
        if end < start:
            raise ValueError(f"Transcript segment ends before it starts: {raw_segment!r}")
        segments.append(TranscriptSegment(start=start, end=end, text=segment_text))

    if segments:
        segment_text = " ".join(segment.text for segment in segments).strip()
        if not text:
            text = segment_text
        elif segment_text and "".join(segment_text.split()) != "".join(text.split()):
            text = segment_text

    if not text:
        raise RuntimeError(
            "Transcription completed, but Whisper returned no transcript text"
        )

    return Transcript(text=text, segments=segments, language=result.get("language"))


def _ffmpeg_available():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _extract_audio_ffmpeg(video_path):
    """Extract audio from video to a temp wav using ffmpeg."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-ar", "16000", "-ac", "1", tmp.name],
        check=True,
        capture_output=True,
    )
    return tmp.name


def _load_audio_array(file_path):
    """
    Convert audio to 16kHz mono float32 numpy array using macOS afconvert.
    This avoids the ffmpeg dependency for audio-only files.
    """
    import numpy as np
    import soundfile as sf

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    try:
        subprocess.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", file_path, tmp.name],
            check=True,
            capture_output=True,
        )
        data, _ = sf.read(tmp.name, dtype="float32")
        return data
    finally:
        os.unlink(tmp.name)


def transcribe(file_path, *, include_metadata=False):
    """Transcribe an audio or video file."""
    import mlx_whisper

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = path.suffix.lower()
    tmp_audio = None

    if ext in VIDEO_EXTENSIONS:
        if not _ffmpeg_available():
            raise RuntimeError(
                "ffmpeg is required for video files. Install with: brew install ffmpeg"
            )
        print("Extracting audio from video...")
        tmp_audio = _extract_audio_ffmpeg(file_path)
        # video-extracted wav is already 16kHz mono, pass path directly
        audio_input = tmp_audio
        use_path = True
    elif ext in AUDIO_EXTENSIONS:
        # Load via afconvert → numpy to avoid ffmpeg dependency
        audio_input = None
        use_path = False
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    try:
        print(f"Transcribing with Whisper ({WHISPER_MODEL.split('/')[-1]})...")
        kwargs = dict(
            path_or_hf_repo=WHISPER_MODEL,
            initial_prompt="This is a recording of a lecture or meeting. The speaker uses complete sentences and may use technical or academic terminology.",
        )
        if use_path:
            result = mlx_whisper.transcribe(audio_input, **kwargs)
        else:
            audio_array = _load_audio_array(file_path)
            result = mlx_whisper.transcribe(audio_array, **kwargs)
        transcript = _transcript_from_result(result)
        return transcript if include_metadata else transcript.text
    finally:
        if tmp_audio:
            os.unlink(tmp_audio)
