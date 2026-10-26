import unittest
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


if __name__ == "__main__":
    unittest.main()
