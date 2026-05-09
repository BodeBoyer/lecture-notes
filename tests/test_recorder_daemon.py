import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import recorder_daemon


class RecorderDaemonTests(unittest.TestCase):
    def test_usage_exits_when_required_args_missing(self):
        with mock.patch("sys.argv", ["recorder_daemon.py"]), self.assertRaises(SystemExit) as raised:
            recorder_daemon.main()

        self.assertEqual(raised.exception.code, 1)

    def test_daemon_records_until_stop_file_and_writes_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "out.wav"
            stop_file = Path(tmp) / "stop"

            class FakeStream:
                def __init__(self, **kwargs):
                    self.callback = kwargs["callback"]
                    self.kwargs = kwargs

                def __enter__(self):
                    self.callback(np.ones((2, 1), dtype="float32"), 2, None, None)
                    stop_file.touch()
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            writes = []

            def fake_write(path, audio, sample_rate):
                writes.append((path, audio.copy(), sample_rate))
                Path(path).write_bytes(b"wav")

            with mock.patch("sys.argv", ["recorder_daemon.py", str(audio_path), "6", str(stop_file)]), mock.patch.object(
                recorder_daemon.sd, "InputStream", FakeStream
            ), mock.patch.object(recorder_daemon.sf, "write", side_effect=fake_write), mock.patch.object(
                recorder_daemon.time, "sleep", return_value=None
            ):
                recorder_daemon.main()

        self.assertEqual(writes[0][0], str(audio_path))
        self.assertEqual(writes[0][1].shape, (2, 1))
        self.assertEqual(writes[0][2], recorder_daemon.SAMPLE_RATE)

    def test_daemon_removes_audio_path_and_raises_when_no_frames_captured(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "out.wav"
            audio_path.write_bytes(b"empty placeholder")
            stop_file = Path(tmp) / "stop"

            class FakeStream:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs

                def __enter__(self):
                    stop_file.touch()
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            with mock.patch("sys.argv", ["recorder_daemon.py", str(audio_path), "None", str(stop_file)]), mock.patch.object(
                recorder_daemon.sd, "InputStream", FakeStream
            ), mock.patch.object(recorder_daemon.sf, "write") as write, mock.patch.object(
                recorder_daemon.time, "sleep", return_value=None
            ):
                with self.assertRaisesRegex(RuntimeError, "No audio was captured"):
                    recorder_daemon.main()

            write.assert_not_called()
            self.assertFalse(audio_path.exists())


if __name__ == "__main__":
    unittest.main()
