# AI Code Review Pilot (GitHub Actions + Gemini)

A lightweight, zero-setup AI code review system packaged as a reusable GitHub Action.
It inspects unified diffs, sends code changes to Google Gemini, and publishes inline review comments and summary feedback directly on GitHub Pull Requests or commits.

## Overview

This repository provides automated, AI-powered code reviews for any programming language.
Users can plug this action directly into any repository with a single workflow step.
It supports both Pull Request events and Push events.
It uses a prebuilt container image hosted on GitHub Container Registry (GHCR), eliminating Docker build time on every run.

## Key Features

- **Dual event support**: Reviews pull request diffs on PR events and commit diffs on push events.
- **Smart event handling**: Automatically handles `opened`, `synchronize`, and `reopened` PR events while ignoring unrelated PR actions (such as `closed` or `labeled`) and unrelated workflow events.
- **Merge commit and empty diff handling**: Safely skips merge commits with multiple parents, empty commits, and branch deletions without error.
- **Prebuilt container performance**: Pulls a prebuilt image from GHCR in seconds instead of rebuilding the Docker image on every workflow run.
- **Graceful fallback**: Automatically falls back to building from the local Dockerfile if the remote image is unavailable.
- **Zero setup for callers**: Runs in any repository with a single workflow step.
- **No checkout required**: Fetches pull request diffs and commit patches directly through the GitHub REST API.
- **Automatic context detection**: Automatically detects repository name, event type, PR number, and commit references from GitHub Actions runtime variables.
- **Diff-focused analysis**: Reviews only changed lines (`+`), minimizing token usage and latency.
- **Accurate line snapping**: Accurately maps Gemini feedback to diff line positions within a +/- 3 line window.
- **Batch and fallback commenting**: Posts PR review comments in batch, falling back to individual comments if needed.
- **Duplicate comment prevention**: Automatically updates existing summary comments instead of cluttering threads with duplicate messages.

## Workflow Examples

You can configure AI Code Review for pull requests, pushes, or both.

### 1. Pull Request Workflow (Recommended for PR Reviews)

Create `.github/workflows/ai-code-review-pr.yml`:

```yaml
name: AI Code Review (Pull Request)

on:
  pull_request:
    types: [opened, synchronize, reopened]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: AI Code Review
        uses: rajvardhan1110/AI-Code-Review-Pilot@v1
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 2. Push Workflow (Review Commits Pushed to Branches)

Create `.github/workflows/ai-code-review-push.yml`:

```yaml
name: AI Code Review (Push)

on:
  push:
    branches: ["main"]

permissions:
  contents: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: AI Code Review
        uses: rajvardhan1110/AI-Code-Review-Pilot@v1
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 3. Combined Workflow (Pull Requests and Pushes)

Create `.github/workflows/ai-code-review.yml`:

```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]
  push:
    branches: ["main"]

permissions:
  contents: write
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: AI Code Review
        uses: rajvardhan1110/AI-Code-Review-Pilot@v1
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Security and Token Permissions

### Why Permissions Differ by Event Type

GitHub Actions restricts permissions based on the API operations performed:

1. **Pull Request Events**:
   - Requires `pull-requests: write` to post inline review comments and summary feedback on the pull request.
   - Requires `contents: read` to fetch pull request metadata and changed files.

2. **Push Events**:
   - Commit comments are associated directly with Git commit objects in the repository contents.
   - GitHub REST API requires `contents: write` to post comments on individual commits (`POST /repos/{owner}/{repo}/commits/{sha}/comments`).

3. **Combined Workflows**:
   - When handling both events in one job, declare `contents: write` and `pull-requests: write`.

### Forked Pull Requests and Secret Isolation

- Workflows triggered by `on: pull_request` from forked repositories run in an isolated security sandbox.
- GitHub Actions does not pass repository secrets (including `GEMINI_API_KEY`) to workflows from forked repositories, and `GITHUB_TOKEN` is strictly read-only.
- If a fork triggers the workflow without `GEMINI_API_KEY`, the action fails safely without executing any untrusted scripts.
- **Do not use `pull_request_target` to bypass this protection.**
- `pull_request_target` runs in the context of the base repository and grants write tokens and secrets.
- Using `pull_request_target` with checkouts of untrusted code can allow malicious pull requests to extract secrets or compromise your repository.

## How Changes Are Identified

1. **Pull Request Events**:
   - The action extracts the PR number from the `GITHUB_EVENT_PATH` payload (or `GITHUB_REF`).
   - It fetches the list of modified files and diff patches using GitHub's Pull Request REST API (`/pulls/{pr_number}/files`).
   - Only reviewed additions (`+`) are analyzed.
   - If the PR number cannot be determined or if the PR action is unsupported (such as `closed`), the action exits cleanly.

2. **Push Events**:
   - The action identifies the target commit using `GITHUB_SHA` (or payload `after`).
   - It retrieves commit details using GitHub's Commit REST API (`/commits/{commit_sha}`).
   - It inspects commit parents.
   - If the commit is a merge commit (more than one parent), it skips automated review to avoid reviewing pre-merged branch histories or diff artifacts.
   - It skips branch deletion events where `commit_sha` is all zeros.
   - It reviews only the files modified in that specific commit.

3. **Unrelated Events**:
   - If the action is triggered by unrelated events (such as `schedule`, `release`, or `issues`), it logs a clear message and terminates without performing reviews.

## Architecture and Container Caching

The action uses a composite action architecture configured in `action.yml`:
1. It targets the prebuilt image `ghcr.io/rajvardhan1110/ai-code-review-pilot:v1`.
2. It attempts to pull the prebuilt image via `docker pull`.
3. If the image is available, the pull completes in ~2-3 seconds, avoiding the 70-90 second Docker build overhead.
4. If the prebuilt image is temporarily unavailable, it automatically falls back to building from `Dockerfile`.
5. It executes the container using `docker run` with the target repository's environment variables and event payload mounted.

## Publishing Releases to GHCR

This repository includes an automated publishing workflow in `.github/workflows/publish-image.yml`.
The workflow triggers whenever a version tag (such as `v1.0.0`) is pushed to the repository.

### Release Workflow Highlights
- Authenticates securely to `ghcr.io` using the built-in `GITHUB_TOKEN` with minimal `packages: write` permissions.
- Normalizes repository naming to lowercase for Docker registry compatibility.
- Tags images with exact semantic version (e.g. `1.0.0`, `v1.0.0`), major version (`v1`), and `latest`.
- Uses Docker BuildKit with GitHub Actions cache backend (`type=gha`) for fast subsequent image builds.
- Does not publish on routine PR or commit reviews, preventing unnecessary image churn.

### Step-by-Step Release Instructions

To publish a new version of the action and its prebuilt container image:

1. Commit and push your changes to `main`:
   ```bash
   git add .
   git commit -m "Support push and pull request events"
   git push origin main
   ```

2. Create and push a version tag:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. Update the floating major tag `v1`:
   ```bash
   git tag -fa v1 -m "Update v1 release"
   git push origin v1 --force
   ```

4. **Important - Make GHCR Package Public**:
   GitHub Container Registry defaults newly pushed packages to **Private**.
   When published for the first time:
   - Navigate to your GitHub profile: `https://github.com/rajvardhan1110?tab=packages`.
   - Select the `ai-code-review-pilot` package.
   - Click **Package settings** in the sidebar.
   - Scroll down to the **Danger Zone** section and click **Change visibility**.
   - Select **Public** and confirm.
   - This allows any external repository to pull the image anonymously without authentication.

## Action Inputs and Environment Variables

| Variable | Type | Required | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Environment | Yes | Google Gemini API key used for code reviews. |
| `GITHUB_TOKEN` | Environment | Yes | GitHub authentication token (use `${{ secrets.GITHUB_TOKEN }}`). |
| `image` | Action Input | No | Custom Docker image override (defaults to `ghcr.io/rajvardhan1110/ai-code-review-pilot:v1`). |

All other context is automatically extracted from the GitHub Actions runtime:
- `REPO_FULL_NAME`: Discovered from `GITHUB_REPOSITORY` (`owner/repo`).
- `EVENT_NAME`: Discovered from `GITHUB_EVENT_NAME` (`pull_request` or `push`).
- `PR_NUMBER`: Extracted from `GITHUB_EVENT_PATH` webhook payload or `GITHUB_REF`.
- `COMMIT_SHA`: Discovered from `GITHUB_SHA` or event payload.
- `BASE_REF` / `HEAD_REF`: Extracted from pull request or push webhook payloads.

## Repository Structure

```text
Review-Only/
├── .github/
│   └── workflows/
│       ├── ai-code-review.yml     # Self-testing workflow definition
│       └── publish-image.yml      # Automated GHCR image publishing workflow
├── src/
│   └── code_review/               # Core Python review engine
│       ├── __init__.py
│       ├── diff_parser.py         # Parses unified diffs and annotates line numbers
│       ├── gemini_service.py      # Calls Gemini API and parses JSON feedback
│       ├── github_client.py       # Interacts with GitHub REST API
│       ├── repository_service.py  # Local git command utilities
│       └── review.py              # Main orchestrator script
├── tests/                         # Unit test suite
│   ├── __init__.py
│   ├── test_diff_parser.py
│   ├── test_gemini_service.py
│   ├── test_github_client.py
│   ├── test_repository_service.py
│   └── test_review_logic.py
├── action.yml                     # Composite GitHub Action definition
├── Dockerfile                     # Container definition for GitHub Actions
├── .dockerignore                  # Docker build exclusions
├── .gitignore
├── requirements.txt               # Python runtime dependencies (`requests`)
├── review_prompt.md               # Default prompt template for Google Gemini
└── README.md                      # Documentation
```

## Running Tests

Run the full unit test suite using standard Python `unittest`:

```bash
python3 -m unittest discover tests -v
```

## Local Verification

To run the review script locally outside of CI:

```bash
export GEMINI_API_KEY="your-gemini-key"
export GITHUB_TOKEN="your-github-token"
export REPO_FULL_NAME="owner/repo"
export PR_NUMBER="1"
export EVENT_NAME="pull_request"

python3 src/code_review/review.py
```
