import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import recorder


class RecorderDeviceSelectionTests(unittest.TestCase):
    def test_list_input_devices_filters_output_only_devices(self):
        devices = [
            {"name": "Built-in Output", "max_input_channels": 0},
            {"name": "USB Mic", "max_input_channels": 1},
            {"name": "BlackHole 2ch", "max_input_channels": 2},
        ]

        with mock.patch.object(recorder.sd, "query_devices", return_value=devices):
            self.assertEqual(recorder.list_input_devices(), [(1, "USB Mic"), (2, "BlackHole 2ch")])

    def test_virtual_device_finds_blackhole_case_insensitively(self):
        with mock.patch.object(recorder, "list_input_devices", return_value=[(4, "BLACKHOLE 2ch")]):
            self.assertEqual(recorder.get_virtual_device(), (4, "BLACKHOLE 2ch"))

    def test_external_mic_prefers_known_usb_keyword(self):
        with mock.patch.object(recorder, "list_input_devices", return_value=[(0, "Built-in Microphone"), (3, "Rode NT-USB")]):
            self.assertEqual(recorder.get_external_mic(), (3, "Rode NT-USB"))

    def test_external_mic_falls_back_to_system_default(self):
        with mock.patch.object(recorder, "list_input_devices", return_value=[(0, "Built-in Microphone")]), mock.patch.object(
            recorder.sd, "query_devices", return_value={"name": "System Default"}
        ) as query:
            self.assertEqual(recorder.get_external_mic(), (None, "System Default"))

        query.assert_called_once_with(kind="input")

    def test_setup_virtual_exits_when_blackhole_missing(self):
        with mock.patch.object(recorder, "get_virtual_device", return_value=(None, None)):
            with self.assertRaises(SystemExit) as raised:
                recorder.setup_virtual_recording()

        self.assertEqual(raised.exception.code, 1)

    def test_setup_inperson_confirms_detected_external_mic(self):
        with mock.patch.object(recorder, "get_external_mic", return_value=(8, "Yeti Stereo Microphone")), mock.patch(
            "builtins.input", return_value=""
        ):
            self.assertEqual(recorder.setup_inperson_recording(), (8, "Yeti Stereo Microphone"))

    def test_setup_inperson_prompt_choice_when_external_rejected(self):
        with mock.patch.object(recorder, "get_external_mic", return_value=(8, "Yeti Stereo Microphone")), mock.patch.object(
            recorder, "list_input_devices", return_value=[(1, "Built-in"), (8, "Yeti Stereo Microphone")]
        ), mock.patch("builtins.input", side_effect=["n", "1"]):
            self.assertEqual(recorder.setup_inperson_recording(), (8, "Yeti Stereo Microphone"))

    def test_setup_inperson_raises_when_no_input_devices(self):
        with mock.patch.object(recorder, "get_external_mic", return_value=(None, "Default")), mock.patch.object(
            recorder, "list_input_devices", return_value=[]
        ):
            with self.assertRaisesRegex(RuntimeError, "No input audio devices"):
                recorder.setup_inperson_recording()


class RecorderRecordTests(unittest.TestCase):
    def test_record_captures_frames_and_writes_wav_with_mocks(self):
        class FakeStream:
            def __init__(self, **kwargs):
                self.callback = kwargs["callback"]
                self.kwargs = kwargs

            def __enter__(self):
                self.callback(np.ones((2, 1), dtype="float32"), 2, None, None)
                self.callback(np.zeros((3, 1), dtype="float32"), 3, None, None)
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        writes = []

        def fake_write(path, audio, sample_rate):
            writes.append((path, audio.copy(), sample_rate))
            Path(path).write_bytes(b"wav")

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(recorder.sd, "InputStream", FakeStream), mock.patch.object(
            recorder.sf, "write", side_effect=fake_write
        ), mock.patch("tempfile.NamedTemporaryFile") as named_temp, mock.patch("builtins.input", return_value=""):
            out_path = Path(tmp) / "recorded.wav"
            named_temp.return_value.name = str(out_path)
            named_temp.return_value.close = mock.Mock()

            result = recorder.record(device_index=5, label="test")

        self.assertEqual(result, str(out_path))
        self.assertEqual(writes[0][2], recorder.SAMPLE_RATE)
        self.assertEqual(writes[0][1].shape, (5, 1))

    def test_record_raises_when_no_audio_captured(self):
        class FakeStream:
            def __init__(self, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with mock.patch.object(recorder.sd, "InputStream", FakeStream), mock.patch("builtins.input", return_value=""):
            with self.assertRaisesRegex(RuntimeError, "No audio was captured"):
                recorder.record()


if __name__ == "__main__":
    unittest.main()
