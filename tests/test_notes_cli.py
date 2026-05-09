import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import notes
from transcriber import Transcript, TranscriptSegment


class NotesCliTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.state_file = self.root / "state.json"
        self.stop_file = self.root / "stop"
        self.notes_dir = self.root / "notes"

        self.patches = [
            mock.patch.object(notes, "STATE_FILE", self.state_file),
            mock.patch.object(notes, "STOP_FILE", self.stop_file),
            mock.patch.object(notes, "NOTES_DIR", self.notes_dir),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.tmpdir.cleanup()
        sys.modules.pop("transcriber", None)
        sys.modules.pop("summarizer", None)
        sys.modules.pop("recorder", None)

    def test_process_runs_full_pipeline_with_mocked_transcriber_and_anthropic(self):
        fake_transcriber = types.SimpleNamespace()
        fake_transcriber.transcribe = mock.Mock(
            return_value=Transcript(
                text="mock transcript",
                segments=[TranscriptSegment(start=0, end=1, text="mock transcript")],
                language="en",
            )
        )
        fake_summarizer = types.SimpleNamespace()
        fake_summarizer.generate_notes = mock.Mock(return_value="# COMP 210 - Mock Notes\n\n- point")
        sys.modules["transcriber"] = fake_transcriber
        sys.modules["summarizer"] = fake_summarizer

        source = self.root / "lecture.wav"
        source.write_bytes(b"audio")

        notes.cmd_process([str(source), "COMP 210"])

        fake_transcriber.transcribe.assert_called_once_with(str(source), include_metadata=True)
        fake_summarizer.generate_notes.assert_called_once_with("mock transcript", "COMP 210")
        outputs = list((self.notes_dir / "COMP-210").glob("*_lecture.md"))
        self.assertEqual(len(outputs), 1)
        written = outputs[0].read_text()
        self.assertIn("# COMP 210 - Mock Notes", written)
        self.assertIn("## Raw Transcript", written)
        self.assertIn("[00:00:00.000 - 00:00:01.000] mock transcript", written)

    def test_record_start_creates_state_and_launches_daemon(self):
        fake_proc = types.SimpleNamespace(pid=4242)
        with mock.patch.object(notes, "_resolve_device", return_value=(7, "USB Mic", "inperson")) as resolve, mock.patch(
            "notes.subprocess.Popen", return_value=fake_proc
        ) as popen, mock.patch.object(notes, "HERE", self.root):
            notes.cmd_record_start(["COMP 210", "--mic"])

        resolve.assert_called_once_with(["COMP 210", "--mic"])
        self.assertTrue(self.state_file.exists())
        self.assertFalse(self.stop_file.exists())
        state = json.loads(self.state_file.read_text())
        self.assertEqual(state["course"], "COMP 210")
        self.assertEqual(state["mode"], "inperson")
        self.assertEqual(state["device_name"], "USB Mic")
        self.assertEqual(state["pid"], 4242)
        self.assertTrue(Path(state["audio_path"]).exists())
        popen.assert_called_once()
        command = popen.call_args.args[0]
        self.assertEqual(command[1], str(self.root / "recorder_daemon.py"))
        self.assertEqual(command[3], "7")
        self.assertEqual(command[4], str(self.stop_file))

    def test_record_start_refuses_when_state_exists(self):
        self.state_file.write_text("{}")

        with self.assertRaises(SystemExit) as raised:
            notes.cmd_record_start(["COMP 210"])

        self.assertEqual(raised.exception.code, 1)

    def test_record_stop_stops_daemon_runs_pipeline_and_removes_audio(self):
        audio_path = self.root / "recording.wav"
        audio_path.write_bytes(b"audio")
        self.state_file.write_text(
            json.dumps({"course": "COMP 210", "audio_path": str(audio_path), "pid": 99, "started": "2026-05-09"})
        )
        fake_psutil = types.SimpleNamespace(pid_exists=mock.Mock(return_value=False))
        sys.modules["psutil"] = fake_psutil

        with mock.patch("time.sleep", return_value=None), mock.patch.object(notes, "run_pipeline") as pipeline:
            notes.cmd_record_stop([])

        pipeline.assert_called_once_with(str(audio_path), "COMP 210", source_label="recording_2026-05-09")
        self.assertFalse(self.state_file.exists())
        self.assertFalse(self.stop_file.exists())
        self.assertFalse(audio_path.exists())

    def test_record_stop_missing_audio_exits_and_cleans_state(self):
        audio_path = self.root / "missing.wav"
        self.state_file.write_text(
            json.dumps({"course": "COMP 210", "audio_path": str(audio_path), "pid": 99, "started": "2026-05-09"})
        )
        sys.modules["psutil"] = types.SimpleNamespace(pid_exists=mock.Mock(return_value=False))

        with mock.patch("time.sleep", return_value=None), self.assertRaises(SystemExit) as raised:
            notes.cmd_record_stop([])

        self.assertEqual(raised.exception.code, 1)
        self.assertFalse(self.state_file.exists())
        self.assertFalse(self.stop_file.exists())

    def test_record_interactive_records_then_runs_pipeline_and_removes_audio(self):
        tmp_audio = self.root / "interactive.wav"
        tmp_audio.write_bytes(b"audio")
        fake_recorder = types.SimpleNamespace(record=mock.Mock(return_value=str(tmp_audio)))
        sys.modules["recorder"] = fake_recorder

        with mock.patch.object(notes, "_resolve_device", return_value=(3, "Yeti", "inperson")), mock.patch.object(
            notes, "run_pipeline"
        ) as pipeline:
            notes.cmd_record(["COMP 210"])

        fake_recorder.record.assert_called_once_with(device_index=3, label="inperson")
        pipeline.assert_called_once()
        self.assertEqual(pipeline.call_args.args[0], str(tmp_audio))
        self.assertEqual(pipeline.call_args.args[1], "COMP 210")
        self.assertFalse(tmp_audio.exists())

    def test_resolve_device_selects_virtual_or_inperson(self):
        fake_recorder = types.SimpleNamespace(
            setup_virtual_recording=mock.Mock(return_value=(1, "BlackHole 2ch")),
            setup_inperson_recording=mock.Mock(return_value=(2, "USB Mic")),
        )
        sys.modules["recorder"] = fake_recorder

        self.assertEqual(notes._resolve_device(["COMP 210", "--virtual"]), (1, "BlackHole 2ch", "virtual"))
        self.assertEqual(notes._resolve_device(["COMP 210", "--mic"]), (2, "USB Mic", "inperson"))


if __name__ == "__main__":
    unittest.main()
