import json
import os
import sys
import tempfile
import unittest

# Ensure src/code_review is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "code_review")))

from review import (
    snap_to_valid_line,
    build_valid_lines_map,
    build_diff_text,
    format_summary,
    get_review_context,
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


if __name__ == "__main__":
    unittest.main()
