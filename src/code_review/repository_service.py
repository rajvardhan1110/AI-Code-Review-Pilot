import subprocess
import os


def get_diff_between_refs(base_ref, head_ref):
    try:
        result = subprocess.run(
            ["git", "diff", base_ref, head_ref, "--unified=3"],
            capture_output=True,
            text=True,
            cwd=os.environ.get("GITHUB_WORKSPACE", "."),
        )
        if result.returncode != 0:
            print(f"Git diff error: {result.stderr}")
            return ""
        return result.stdout
    except Exception as e:
        print(f"Error running git diff: {e}")
        return ""


def get_changed_files(base_ref, head_ref):
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", base_ref, head_ref],
            capture_output=True,
            text=True,
            cwd=os.environ.get("GITHUB_WORKSPACE", "."),
        )
        if result.returncode != 0:
            print(f"Git error: {result.stderr}")
            return []
        return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except Exception as e:
        print(f"Error getting changed files: {e}")
        return []
