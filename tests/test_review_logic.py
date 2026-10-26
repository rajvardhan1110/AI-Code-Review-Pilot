import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Ensure src/code_review is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "code_review")))

from review import (
    snap_to_valid_line,
    build_valid_lines_map,
    build_diff_text,
    format_summary,
    get_review_context,
    run_push_review,
    run_pr_review,
    main,
)


class TestReviewLogic(unittest.TestCase):

    def test_snap_to_valid_line(self):
        valid_lines = {
            "src/app.py": {
                10: 2,
                20: 5,
            }
        }

        # Exact match
        line, pos = snap_to_valid_line("src/app.py", 10, valid_lines)
        self.assertEqual(line, 10)
        self.assertEqual(pos, 2)

        # Within +/- 1 offset
        line, pos = snap_to_valid_line("src/app.py", 11, valid_lines)
        self.assertEqual(line, 10)
        self.assertEqual(pos, 2)

        # Within +/- 2 offset
        line, pos = snap_to_valid_line("src/app.py", 18, valid_lines)
        self.assertEqual(line, 20)
        self.assertEqual(pos, 5)

        # Within +/- 3 offset
        line, pos = snap_to_valid_line("src/app.py", 23, valid_lines)
        self.assertEqual(line, 20)
        self.assertEqual(pos, 5)

        # Out of range (> 3 lines away)
        line, pos = snap_to_valid_line("src/app.py", 50, valid_lines)
        self.assertIsNone(line)
        self.assertIsNone(pos)

        # Unknown file path
        line, pos = snap_to_valid_line("non_existent.py", 10, valid_lines)
        self.assertIsNone(line)
        self.assertIsNone(pos)

    def test_build_valid_lines_map(self):
        diff_entries = [
            {
                "path": "test.py",
                "chunks": [
                    {
                        "added_lines": [5, 6],
                        "changed_lines": {4: 1, 5: 2, 6: 3, 7: 4},
                    }
                ],
            }
        ]
        # Only lines in added_lines that also exist in changed_lines should be included
        valid_map = build_valid_lines_map(diff_entries)
        self.assertIn("test.py", valid_map)
        self.assertEqual(valid_map["test.py"], {5: 2, 6: 3})

    def test_build_diff_text(self):
        diff_entries = [
            {
                "path": "math.py",
                "chunks": [
                    {
                        "annotated_lines": ["L1: def add(a, b):", "L2: +    return a + b"]
                    }
                ],
            }
        ]
        text = build_diff_text(diff_entries)
        self.assertIn("## File: math.py", text)
        self.assertIn("```diff", text)
        self.assertIn("L1: def add(a, b):", text)
        self.assertIn("L2: +    return a + b", text)

    def test_format_summary(self):
        summary = "Refactored math helpers."
        files = ["math.py", "utils.py"]
        result = format_summary(summary, files, 3)

        self.assertIn("AI Code Review Summary", result)
        self.assertIn("**Files reviewed:** 2", result)
        self.assertIn("**Inline comments posted:** 3", result)
        self.assertIn("- `math.py`", result)
        self.assertIn("- `utils.py`", result)
        self.assertIn(summary, result)

    def test_get_review_context_from_explicit_env(self):
        env = {
            "GEMINI_API_KEY": "test_gemini_key",
            "GITHUB_TOKEN": "test_gh_token",
            "REPO_FULL_NAME": "owner/repo",
            "EVENT_NAME": "pull_request",
            "PR_NUMBER": "42",
            "BASE_REF": "base123",
            "HEAD_REF": "head456",
            "COMMIT_SHA": "sha789",
        }
        ctx = get_review_context(env)
        self.assertEqual(ctx["gemini_api_key"], "test_gemini_key")
        self.assertEqual(ctx["github_token"], "test_gh_token")
        self.assertEqual(ctx["repo_full_name"], "owner/repo")
        self.assertEqual(ctx["event_name"], "pull_request")
        self.assertEqual(ctx["pr_number"], "42")
        self.assertEqual(ctx["base_ref"], "base123")
        self.assertEqual(ctx["head_ref"], "head456")
        self.assertEqual(ctx["commit_sha"], "sha789")

    def test_get_review_context_from_github_actions_pr(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as f:
            json.dump({
                "number": 101,
                "pull_request": {
                    "number": 101,
                    "base": {"sha": "basesha"},
                    "head": {"sha": "headsha"},
                },
                "repository": {
                    "full_name": "auto-owner/auto-repo",
                },
            }, f)
            event_path = f.name

        try:
            env = {
                "GEMINI_API_KEY": "test_gemini_key",
                "GITHUB_TOKEN": "test_gh_token",
                "GITHUB_REPOSITORY": "auto-owner/auto-repo",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_EVENT_PATH": event_path,
                "GITHUB_SHA": "runner_sha",
            }
            ctx = get_review_context(env)
            self.assertEqual(ctx["gemini_api_key"], "test_gemini_key")
            self.assertEqual(ctx["github_token"], "test_gh_token")
            self.assertEqual(ctx["repo_full_name"], "auto-owner/auto-repo")
            self.assertEqual(ctx["event_name"], "pull_request")
            self.assertEqual(ctx["pr_number"], "101")
            self.assertEqual(ctx["base_ref"], "basesha")
            self.assertEqual(ctx["head_ref"], "headsha")
            self.assertEqual(ctx["commit_sha"], "runner_sha")
        finally:
            if os.path.exists(event_path):
                os.remove(event_path)

    def test_get_review_context_from_github_ref(self):
        env = {
            "GEMINI_API_KEY": "key",
            "GITHUB_TOKEN": "token",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_REF": "refs/pull/77/merge",
            "GITHUB_SHA": "sha123",
        }
        ctx = get_review_context(env)
        self.assertEqual(ctx["pr_number"], "77")
        self.assertEqual(ctx["repo_full_name"], "owner/repo")

    def test_get_review_context_from_github_actions_push(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as f:
            json.dump({
                "before": "commit_before",
                "after": "commit_after",
                "head_commit": {"id": "commit_after"},
                "repository": {"full_name": "owner/repo"},
            }, f)
            event_path = f.name

        try:
            env = {
                "GEMINI_API_KEY": "key",
                "GITHUB_TOKEN": "token",
                "GITHUB_REPOSITORY": "owner/repo",
                "GITHUB_EVENT_NAME": "push",
                "GITHUB_EVENT_PATH": event_path,
                "GITHUB_SHA": "commit_after",
            }
            ctx = get_review_context(env)
            self.assertEqual(ctx["event_name"], "push")
            self.assertEqual(ctx["pr_number"], "")
            self.assertEqual(ctx["base_ref"], "commit_before")
            self.assertEqual(ctx["head_ref"], "commit_after")
            self.assertEqual(ctx["commit_sha"], "commit_after")
        finally:
            if os.path.exists(event_path):
                os.remove(event_path)

    def test_get_review_context_inputs_fallback(self):
        env = {
            "INPUT_GEMINI_API_KEY": "key_from_input",
            "INPUT_GITHUB_TOKEN": "token_from_input",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_REF": "refs/pull/15/merge",
        }
        ctx = get_review_context(env)
        self.assertEqual(ctx["gemini_api_key"], "key_from_input")
        self.assertEqual(ctx["github_token"], "token_from_input")
        self.assertEqual(ctx["pr_number"], "15")

    def test_get_review_context_branch_deletion(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as f:
            json.dump({
                "deleted": True,
                "after": "0000000000000000000000000000000000000000",
                "repository": {"full_name": "owner/repo"},
            }, f)
            event_path = f.name

        try:
            env = {
                "GEMINI_API_KEY": "key",
                "GITHUB_TOKEN": "token",
                "GITHUB_REPOSITORY": "owner/repo",
                "GITHUB_EVENT_NAME": "push",
                "GITHUB_EVENT_PATH": event_path,
                "GITHUB_SHA": "0000000000000000000000000000000000000000",
            }
            ctx = get_review_context(env)
            self.assertEqual(ctx["commit_sha"], "")
        finally:
            if os.path.exists(event_path):
                os.remove(event_path)

    def test_get_review_context_pr_action(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as f:
            json.dump({
                "action": "synchronize",
                "number": 55,
                "pull_request": {"number": 55},
                "repository": {"full_name": "owner/repo"},
            }, f)
            event_path = f.name

        try:
            env = {
                "GEMINI_API_KEY": "key",
                "GITHUB_TOKEN": "token",
                "GITHUB_REPOSITORY": "owner/repo",
                "GITHUB_EVENT_NAME": "pull_request",
                "GITHUB_EVENT_PATH": event_path,
            }
            ctx = get_review_context(env)
            self.assertEqual(ctx["pr_action"], "synchronize")
            self.assertEqual(ctx["pr_number"], "55")
        finally:
            if os.path.exists(event_path):
                os.remove(event_path)

    def test_get_review_context_missing_fields_graceful(self):
        ctx = get_review_context({})
        self.assertEqual(ctx["event_name"], "")
        self.assertEqual(ctx["pr_number"], "")
        self.assertEqual(ctx["commit_sha"], "")
        self.assertIsNone(ctx["gemini_api_key"])
        self.assertIsNone(ctx["github_token"])

    @patch("review.run_pr_review")
    @patch("review.run_push_review")
    @patch("review.get_review_context")
    def test_main_unrelated_event_skipped(self, mock_ctx, mock_push, mock_pr):
        mock_ctx.return_value = {
            "gemini_api_key": "key",
            "github_token": "token",
            "repo_full_name": "owner/repo",
            "event_name": "schedule",
            "pr_number": "",
            "commit_sha": "",
            "base_ref": "",
            "head_ref": "",
            "pr_action": "",
        }
        main()
        mock_pr.assert_not_called()
        mock_push.assert_not_called()

    @patch("review.run_pr_review")
    @patch("review.run_push_review")
    @patch("review.get_review_context")
    def test_main_pr_unsupported_action_skipped(self, mock_ctx, mock_push, mock_pr):
        mock_ctx.return_value = {
            "gemini_api_key": "key",
            "github_token": "token",
            "repo_full_name": "owner/repo",
            "event_name": "pull_request",
            "pr_action": "closed",
            "pr_number": "12",
            "commit_sha": "sha12",
            "base_ref": "b",
            "head_ref": "h",
        }
        main()
        mock_pr.assert_not_called()
        mock_push.assert_not_called()

    @patch("review.run_pr_review")
    @patch("review.run_push_review")
    @patch("review.get_review_context")
    def test_main_pr_missing_pr_number(self, mock_ctx, mock_push, mock_pr):
        mock_ctx.return_value = {
            "gemini_api_key": "key",
            "github_token": "token",
            "repo_full_name": "owner/repo",
            "event_name": "pull_request",
            "pr_action": "opened",
            "pr_number": "",
            "commit_sha": "sha12",
            "base_ref": "b",
            "head_ref": "h",
        }
        main()
        mock_pr.assert_not_called()
        mock_push.assert_not_called()

    @patch("review.GeminiService")
    def test_run_push_review_merge_commit_skipped(self, mock_gemini_cls):
        mock_github = MagicMock()
        mock_github.repo = "owner/repo"
        mock_github.get_commit.return_value = {
            "sha": "merge_commit_sha",
            "parents": [{"sha": "p1"}, {"sha": "p2"}],
            "files": [{"filename": "f.py", "patch": "+change"}],
        }
        mock_gemini = mock_gemini_cls.return_value

        run_push_review(mock_github, mock_gemini, "base", "head", "merge_commit_sha")
        mock_gemini.review_code.assert_not_called()
        mock_github.post_commit_comments.assert_not_called()

    @patch("review.GeminiService")
    def test_run_push_review_empty_commit(self, mock_gemini_cls):
        mock_github = MagicMock()
        mock_github.repo = "owner/repo"
        mock_github.get_commit.return_value = {
            "sha": "empty_commit_sha",
            "parents": [{"sha": "p1"}],
            "files": [],
        }
        mock_gemini = mock_gemini_cls.return_value

        run_push_review(mock_github, mock_gemini, "base", "head", "empty_commit_sha")
        mock_gemini.review_code.assert_not_called()

    @patch("review.GeminiService")
    def test_run_push_review_empty_diff(self, mock_gemini_cls):
        mock_github = MagicMock()
        mock_github.repo = "owner/repo"
        mock_github.get_commit.return_value = {
            "sha": "c_sha",
            "parents": [{"sha": "p1"}],
            "files": [{"filename": "package-lock.json", "patch": "+lock"}],
        }
        mock_gemini = mock_gemini_cls.return_value

        run_push_review(mock_github, mock_gemini, "base", "head", "c_sha")
        # diff_parser skips package-lock.json, so diff_entries is empty
        mock_gemini.review_code.assert_not_called()


if __name__ == "__main__":
    unittest.main()
