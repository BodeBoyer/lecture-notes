import os
import unittest
from unittest import mock

import notebooklm_pusher


class NotebookLMPusherConfigTests(unittest.TestCase):
    def test_lookup_notebook_id_canonicalizes_mapping_keys_and_course(self):
        with mock.patch.dict(
            os.environ,
            {"LECTURE_NOTES_NBLM_NOTEBOOKS": " comp 210 =abc123,COMP/301=def456"},
        ):
            self.assertEqual(notebooklm_pusher.lookup_notebook_id("COMP 210"), "abc123")
            self.assertEqual(notebooklm_pusher.lookup_notebook_id(" comp/301 "), "def456")

    def test_push_skips_when_course_has_no_mapping(self):
        with mock.patch.dict(os.environ, {"LECTURE_NOTES_NBLM_NOTEBOOKS": ""}):
            result = notebooklm_pusher.push_to_notebook(mock.Mock(exists=lambda: True), "COMP 210")

        self.assertIn("skipped", result)


if __name__ == "__main__":
    unittest.main()
