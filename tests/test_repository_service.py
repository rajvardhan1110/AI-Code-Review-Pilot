import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Ensure src/code_review is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "code_review")))

from repository_service import get_diff_between_refs, get_changed_files


class TestRepositoryService(unittest.TestCase):

    @patch("subprocess.run")
    def test_get_diff_between_refs_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "diff --git a/test.py b/test.py\n..."
        mock_run.return_value = mock_result

        diff = get_diff_between_refs("main", "feature")
        self.assertEqual(diff, "diff --git a/test.py b/test.py\n...")
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_get_diff_between_refs_failure(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "fatal: bad revision"
        mock_run.return_value = mock_result

        diff = get_diff_between_refs("bad_base", "bad_head")
        self.assertEqual(diff, "")

    @patch("subprocess.run")
    def test_get_changed_files_success(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "src/app.py\nsrc/utils.py\n"
        mock_run.return_value = mock_result

        files = get_changed_files("main", "feature")
        self.assertEqual(files, ["src/app.py", "src/utils.py"])

    @patch("subprocess.run")
    def test_get_changed_files_failure(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "git error"
        mock_run.return_value = mock_result

        files = get_changed_files("bad_base", "bad_head")
        self.assertEqual(files, [])


if __name__ == "__main__":
    unittest.main()
