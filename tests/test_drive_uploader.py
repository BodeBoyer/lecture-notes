import unittest

import drive_uploader


class DriveUploaderConfigTests(unittest.TestCase):
    def test_safe_course_folder_matches_notes_course_folder_format(self):
        self.assertEqual(drive_uploader._safe_course_folder(" comp 210 "), "COMP-210")
        self.assertEqual(drive_uploader._safe_course_folder("comp/301"), "COMP-301")


if __name__ == "__main__":
    unittest.main()
