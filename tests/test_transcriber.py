import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import transcriber


class TranscriptResultTests(unittest.TestCase):
    def test_format_timestamp_clamps_negative_and_rounds(self):
        self.assertEqual(transcriber._format_timestamp(-2.5), "00:00:00.000")
        self.assertEqual(transcriber._format_timestamp(65.4326), "00:01:05.433")
        self.assertEqual(transcriber._format_timestamp(3661.005), "01:01:01.005")

    def test_transcript_from_segments_prefers_normalized_segment_text(self):
        result = {
            "text": "different text",
            "language": "en",
            "segments": [
                {"start": 0, "end": 1.5, "text": " Hello "},
                {"start": "1.5", "end": "3", "text": "world"},
            ],
        }

        transcript = transcriber._transcript_from_result(result)

        self.assertEqual(transcript.text, "Hello world")
        self.assertEqual(transcript.language, "en")
        self.assertEqual(transcript.export_text(), "[00:00:00.000 - 00:00:01.500] Hello\n[00:00:01.500 - 00:00:03.000] world")

    def test_transcript_uses_plain_text_when_no_segments(self):
        transcript = transcriber._transcript_from_result({"text": " standalone text "})

        self.assertEqual(transcript.text, "standalone text")
        self.assertEqual(transcript.segments, [])
        self.assertEqual(transcript.export_text(), "standalone text")

    def test_empty_transcript_raises(self):
        with self.assertRaisesRegex(RuntimeError, "no transcript text"):
            transcriber._transcript_from_result({"text": "", "segments": []})

    def test_empty_segment_text_is_ignored(self):
        transcript = transcriber._transcript_from_result(
            {"segments": [{"start": 0, "end": 1, "text": "  "}, {"start": 1, "end": 2, "text": "kept"}]}
        )

        self.assertEqual(transcript.text, "kept")
        self.assertEqual(len(transcript.segments), 1)

    def test_malformed_segments_raise_value_error(self):
        cases = [
            {"segments": [{"end": 1, "text": "missing start"}]},
            {"segments": [{"start": "bad", "end": 1, "text": "bad start"}]},
            {"segments": [{"start": 2, "end": 1, "text": "backwards"}]},
        ]

        for result in cases:
            with self.subTest(result=result):
                with self.assertRaises(ValueError):
                    transcriber._transcript_from_result(result)


class TranscribePipelineTests(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop("mlx_whisper", None)

    def test_audio_transcribe_uses_fake_mlx_and_loader(self):
        fake_mlx = types.SimpleNamespace()
        fake_mlx.transcribe = mock.Mock(
            return_value={
                "text": "",
                "segments": [{"start": 0, "end": 2, "text": "Mock lecture transcript"}],
                "language": "en",
            }
        )
        sys.modules["mlx_whisper"] = fake_mlx

        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "lecture.wav"
            audio_path.write_bytes(b"not real audio")

            with mock.patch.object(transcriber, "_load_audio_array", return_value=[0.0, 0.1]) as load_audio:
                transcript = transcriber.transcribe(audio_path, include_metadata=True)

        load_audio.assert_called_once_with(audio_path)
        fake_mlx.transcribe.assert_called_once()
        self.assertEqual(transcript.text, "Mock lecture transcript")
        self.assertEqual(transcript.language, "en")

    def test_video_transcribe_extracts_audio_and_cleans_temp(self):
        fake_mlx = types.SimpleNamespace()
        fake_mlx.transcribe = mock.Mock(return_value={"text": "video words", "segments": []})
        sys.modules["mlx_whisper"] = fake_mlx

        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "lecture.mp4"
            extracted_path = Path(tmp) / "extracted.wav"
            video_path.write_bytes(b"video")
            extracted_path.write_bytes(b"audio")

            with mock.patch.object(transcriber, "_ffmpeg_available", return_value=True), mock.patch.object(
                transcriber, "_extract_audio_ffmpeg", return_value=str(extracted_path)
            ):
                text = transcriber.transcribe(str(video_path))

            self.assertEqual(text, "video words")
            self.assertFalse(extracted_path.exists())
            fake_mlx.transcribe.assert_called_once_with(str(extracted_path), path_or_hf_repo=transcriber.WHISPER_MODEL, initial_prompt=mock.ANY)


if __name__ == "__main__":
    unittest.main()
