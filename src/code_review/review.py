import json
import os
import re
import sys

from github_client import GitHubClient
from diff_parser import parse_diff
from gemini_service import GeminiService
from repository_service import get_diff_between_refs


def get_review_context(env=None):
    if env is None:
        env = os.environ

    gemini_api_key = env.get("GEMINI_API_KEY") or env.get("INPUT_GEMINI_API_KEY")
    github_token = (
        env.get("GITHUB_TOKEN")
        or env.get("INPUT_GITHUB_TOKEN")
        or env.get("GH_TOKEN")
    )

    payload = {}
    event_path = env.get("GITHUB_EVENT_PATH")
    if event_path and os.path.isfile(event_path):
        try:
            with open(event_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            print(f"Warning: Could not read GITHUB_EVENT_PATH ({event_path}): {e}")

    repo_full_name = (
        env.get("REPO_FULL_NAME")
        or env.get("GITHUB_REPOSITORY")
        or payload.get("repository", {}).get("full_name")
    )

    event_name = (
        env.get("EVENT_NAME")
        or env.get("GITHUB_EVENT_NAME")
        or ""
    )

    pr_number = env.get("PR_NUMBER", "")
    if not pr_number:
        pr_data = payload.get("pull_request")
        if isinstance(pr_data, dict) and "number" in pr_data:
            pr_number = str(pr_data["number"])
        elif "number" in payload and event_name in ("pull_request", "pull_request_target", "issue_comment"):
            pr_number = str(payload["number"])
        elif "issue" in payload and isinstance(payload.get("issue"), dict) and "number" in payload["issue"]:
            pr_number = str(payload["issue"]["number"])

    if not pr_number:
        github_ref = env.get("GITHUB_REF", "")
        match = re.search(r"refs/pull/(\d+)", github_ref)
        if match:
            pr_number = match.group(1)
        else:
            ref_name = env.get("GITHUB_REF_NAME", "")
            match = re.search(r"^(\d+)/(merge|head)", ref_name)
            if match:
                pr_number = match.group(1)

    pr_action = payload.get("action", "")

    is_deleted = bool(payload.get("deleted", False))

    commit_sha = (
        env.get("COMMIT_SHA")
        or env.get("GITHUB_SHA")
        or payload.get("after")
        or payload.get("head_commit", {}).get("id")
        or ""
    )
    if is_deleted or commit_sha == "0000000000000000000000000000000000000000":
        commit_sha = ""

    base_ref = env.get("BASE_REF", "")
    if not base_ref:
        if isinstance(payload.get("pull_request"), dict):
            base_ref = payload["pull_request"].get("base", {}).get("sha", "")
        elif "before" in payload:
            base_ref = payload.get("before", "")
        if not base_ref:
            base_ref = env.get("GITHUB_BASE_REF", "")

    head_ref = env.get("HEAD_REF", "")
    if not head_ref:
        if isinstance(payload.get("pull_request"), dict):
            head_ref = payload["pull_request"].get("head", {}).get("sha", "")
        elif "after" in payload:
            head_ref = payload.get("after", "")
        if not head_ref:
            head_ref = env.get("GITHUB_HEAD_REF") or commit_sha

    return {
        "gemini_api_key": gemini_api_key,
        "github_token": github_token,
        "repo_full_name": repo_full_name,
        "event_name": event_name,
        "pr_number": pr_number,
        "pr_action": pr_action,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "commit_sha": commit_sha,
    }


def main():
    ctx = get_review_context()
    gemini_api_key = ctx["gemini_api_key"]
    github_token = ctx["github_token"]
    repo_full_name = ctx["repo_full_name"]
    event_name = ctx["event_name"]
    pr_number = ctx["pr_number"]
    pr_action = ctx.get("pr_action", "")
    base_ref = ctx["base_ref"]
    head_ref = ctx["head_ref"]
    commit_sha = ctx["commit_sha"]

    if not all([gemini_api_key, github_token, repo_full_name]):
        print("Error: Missing required environment variables.")
        print("Required: GEMINI_API_KEY, GITHUB_TOKEN, REPO_FULL_NAME")
        sys.exit(1)

    # Determine event type
    is_pr_event = event_name in ("pull_request", "pull_request_target")
    is_push_event = event_name == "push"

    if not is_pr_event and not is_push_event:
        # Check if manual PR or commit review was requested (e.g. CLI or workflow_dispatch)
        if pr_number:
            is_pr_event = True
        elif commit_sha:
            is_push_event = True
        else:
            print(
                f"Unsupported event type: '{event_name}'. "
                "AI Code Review only runs on 'pull_request' and 'push' events."
            )
            return

    github = GitHubClient(github_token, repo_full_name)
    gemini = GeminiService(gemini_api_key)

    if is_pr_event:
        # Only review on relevant PR actions (opened, synchronize, reopened)
        if pr_action and pr_action not in ("opened", "synchronize", "reopened"):
            print(
                f"Skipping pull_request event with action '{pr_action}'. "
                "Supported actions: opened, synchronize, reopened."
            )
            return

        if not pr_number:
            print("Error: Pull request event detected, but could not determine PR number.")
            return

        try:
            pr_num = int(pr_number)
        except ValueError:
            print(f"Error: Invalid pull request number: {pr_number}")
            return

        run_pr_review(github, gemini, pr_num)
    else:
        if not commit_sha:
            print("No valid commit SHA found for push review - skipping review.")
            return
        run_push_review(github, gemini, base_ref, head_ref, commit_sha)


def run_pr_review(github, gemini, pr_number):
    print(f"Reviewing PR #{pr_number} in {github.repo}")

    # Check for existing bot comments to avoid duplicates
    existing_comments = github.get_review_comments(pr_number)
    bot_comments = [c for c in existing_comments if c.get("user", {}).get("type") == "Bot"]
    if bot_comments:
        print("Bot has already commented on this PR. Checking if this is a new push...")

    # Get changed files from the PR
    changed_files = github.get_pr_files(pr_number)
    if not changed_files:
        print("No changed files found in this PR.")
        return

    # Parse diffs and review
    diff_entries = parse_diff(changed_files)
    if not diff_entries:
        print("No reviewable changes found in the diff.")
        return

    diff_text = build_diff_text(diff_entries)
    if not diff_text.strip():
        print("No meaningful diff content to review.")
        return

    print(f"Sending {len(diff_entries)} file(s) for review...")
    review_result = gemini.review_code(diff_text)
    if not review_result:
        print("Gemini did not return a valid review.")
        return

    summary = review_result.get("summary", "No summary provided.")
    comments = review_result.get("comments", [])

    valid_lines = build_valid_lines_map(diff_entries)
    valid_comments = []
    for comment in comments:
        path = comment.get("path", "")
        line = comment.get("line", 0)
        body = comment.get("body", "")
        if not body:
            continue
        snapped_line, position = snap_to_valid_line(path, line, valid_lines)
        if snapped_line is not None and position is not None:
            comment["line"] = snapped_line
            comment["position"] = position
            valid_comments.append(comment)
        else:
            print(f"Skipping comment for {path}:{line} - not in diff range.")

    if valid_comments:
        print(f"Posting {len(valid_comments)} inline comment(s)...")
        github.post_review(pr_number, valid_comments)
    else:
        print("No inline comments to post.")

    files_reviewed = [entry["path"] for entry in diff_entries]
    summary_body = format_summary(summary, files_reviewed, len(valid_comments))
    github.post_summary_comment(pr_number, summary_body)
    print("Review complete.")


def run_push_review(github, gemini, base_ref, head_ref, commit_sha):
    if not commit_sha:
        print("No valid commit SHA provided for push review - skipping review.")
        return

    print(f"Reviewing push commit {commit_sha[:8]} in {github.repo}")

    # Get commit details via GitHub API
    commit_data = github.get_commit(commit_sha)
    if not commit_data:
        print(f"Could not retrieve commit {commit_sha[:8]} details.")
        return

    # Check for merge commits (multiple parents)
    parents = commit_data.get("parents", [])
    if len(parents) > 1:
        print(f"Commit {commit_sha[:8]} is a merge commit with {len(parents)} parents - skipping review.")
        return

    changed_files = commit_data.get("files", [])
    if not changed_files:
        print("No changed files found in this commit.")
        return

    diff_entries = parse_diff(changed_files)
    if not diff_entries:
        print("No reviewable changes found in the diff.")
        return

    diff_text = build_diff_text(diff_entries)
    if not diff_text.strip():
        print("No meaningful diff content to review.")
        return

    print(f"Sending {len(diff_entries)} file(s) for review...")
    review_result = gemini.review_code(diff_text)
    if not review_result:
        print("Gemini did not return a valid review.")
        return

    summary = review_result.get("summary", "No summary provided.")
    comments = review_result.get("comments", [])

    valid_lines = build_valid_lines_map(diff_entries)
    valid_comments = []
    for comment in comments:
        path = comment.get("path", "")
        line = comment.get("line", 0)
        body = comment.get("body", "")
        if not body:
            continue
        snapped_line, position = snap_to_valid_line(path, line, valid_lines)
        if snapped_line is not None and position is not None:
            comment["line"] = snapped_line
            comment["position"] = position
            valid_comments.append(comment)
        else:
            print(f"Skipping comment for {path}:{line} - not in diff range.")

    if valid_comments:
        print(f"Posting {len(valid_comments)} inline comment(s) on commit...")
        github.post_commit_comments(commit_sha, valid_comments)
    else:
        print("No inline comments to post.")

    files_reviewed = [entry["path"] for entry in diff_entries]
    summary_body = format_summary(summary, files_reviewed, len(valid_comments))
    github.post_commit_comment(commit_sha, summary_body)
    print("Review complete.")


def build_diff_text(diff_entries):
    parts = []
    for entry in diff_entries:
        parts.append(f"## File: {entry['path']}")
        parts.append("```diff")
        for chunk in entry["chunks"]:
            for line in chunk["annotated_lines"]:
                parts.append(line)
        parts.append("```")
        parts.append("")
    return "\n".join(parts)


def build_valid_lines_map(diff_entries):
    """Only added lines (+) are valid targets for inline comments."""
    valid = {}
    for entry in diff_entries:
        lines_map = {}  # line_number -> diff position
        for chunk in entry["chunks"]:
            for line_num in chunk["added_lines"]:
                if line_num in chunk["changed_lines"]:
                    lines_map[line_num] = chunk["changed_lines"][line_num]
        if lines_map:
            valid[entry["path"]] = lines_map
    return valid


def snap_to_valid_line(path, line, valid_lines):
    """Find the nearest valid line within a range of +/- 3 lines."""
    if path not in valid_lines:
        return None, None
    lines_map = valid_lines[path]
    if line in lines_map:
        return line, lines_map[line]
    # Search nearby lines (prefer closest)
    for offset in [1, -1, 2, -2, 3, -3]:
        candidate = line + offset
        if candidate in lines_map:
            return candidate, lines_map[candidate]
    return None, None


def format_summary(summary, files_reviewed, inline_count):
    lines = [
        "## 🤖 AI Code Review Summary",
        "",
        f"**Files reviewed:** {len(files_reviewed)}",
        f"**Inline comments posted:** {inline_count}",
        "",
        "### Files Changed:",
        "",
    ]
    for f in files_reviewed:
        lines.append(f"- `{f}`")
    lines.append("")
    lines.append("### What Changed:")
    lines.append("")
    lines.append(summary)
    lines.append("")
    lines.append("---")
    lines.append("*This review was generated automatically by AI Code Review (Gemini).*")
    return "\n".join(lines)


if __name__ == "__main__":
    # Add the code_review directory to path for imports
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
