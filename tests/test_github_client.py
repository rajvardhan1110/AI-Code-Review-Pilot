import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Ensure src/code_review is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "code_review")))

from github_client import GitHubClient


class TestGitHubClient(unittest.TestCase):

    def test_client_initialization(self):
        client = GitHubClient("ghp_fake_token", "owner/sample-repo")
        self.assertEqual(client.token, "ghp_fake_token")
        self.assertEqual(client.repo, "owner/sample-repo")
        self.assertEqual(client.base_url, "https://api.github.com/repos/owner/sample-repo")
        self.assertEqual(client.headers["Authorization"], "Bearer ghp_fake_token")
        self.assertEqual(client.headers["Accept"], "application/vnd.github.v3+json")

    @patch("requests.get")
    def test_get_commit_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "sha": "abc1234",
            "parents": [{"sha": "p1"}],
            "files": [{"filename": "main.py", "patch": "@@ -1 +1 @@"}]
        }
        mock_get.return_value = mock_resp

        client = GitHubClient("token", "owner/repo")
        commit_data = client.get_commit("abc1234")
        self.assertIsNotNone(commit_data)
        self.assertEqual(commit_data["sha"], "abc1234")
        self.assertEqual(len(commit_data["parents"]), 1)

    @patch("requests.get")
    def test_get_commit_failure(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Not found"
        mock_get.return_value = mock_resp

        client = GitHubClient("token", "owner/repo")
        commit_data = client.get_commit("nonexistent")
        self.assertIsNone(commit_data)

    @patch("requests.get")
    def test_get_commit_files(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "sha": "abc1234",
            "files": [{"filename": "app.py", "patch": "+print(1)"}]
        }
        mock_get.return_value = mock_resp

        client = GitHubClient("token", "owner/repo")
        files = client.get_commit_files("abc1234")
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["filename"], "app.py")


if __name__ == "__main__":
    unittest.main()
