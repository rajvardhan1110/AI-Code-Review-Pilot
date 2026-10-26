# AI Code Review (GitHub Actions + Gemini)

A lightweight, zero-setup AI code review system packaged as a reusable GitHub Action.
It inspects unified diffs, sends code changes to Google Gemini, and publishes inline review comments and summary feedback directly on GitHub Pull Requests or commits.

## Overview

This repository provides automated, AI-powered code reviews for any programming language.
Users can plug this action directly into any repository with a single workflow step.
It runs as a container action, requiring no source code checkout, no Python installation, and no manual dependency management in caller workflows.

## Key Features

- **Zero setup**: Runs in any repository with a single workflow step.
- **No checkout required**: Fetches pull request diffs and commit patches directly through the GitHub REST API.
- **Self-contained environment**: Packages Python and all runtime dependencies in a lightweight container.
- **Automatic context detection**: Automatically detects repository name, event type, PR number, and commit references from GitHub Actions runtime variables.
- **Diff-focused analysis**: Reviews only changed lines (`+`), minimizing token usage and latency.
- **Accurate line snapping**: Accurately maps Gemini feedback to diff line positions within a +/- 3 line window.
- **Batch and fallback commenting**: Posts PR review comments in batch, falling back to individual comments if needed.
- **Duplicate comment prevention**: Automatically updates existing summary comments instead of cluttering threads with duplicate messages.
- **Dual event support**: Supports both `pull_request` and `push` events.
- **Customizable prompts**: Bundles a production-ready prompt and supports custom `review_prompt.md` files when checked out in caller workspaces.

## Usage in Any Repository

To use this action in any GitHub repository, create a workflow file (for example, `.github/workflows/ai-code-review.yml`).
Add the following workflow configuration:

```yaml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]
  push:
    branches: ["**"]

permissions:
  contents: write
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - name: AI Code Review
        uses: MY_GITHUB_USERNAME/Review-Only@v1
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

> [!NOTE]
> Replace `MY_GITHUB_USERNAME` with your GitHub username or organization name where this action repository is published.

### Required Setup

1. **Get a Gemini API Key**: Obtain an API key from [Google AI Studio](https://aistudio.google.com/apikey).
2. **Add Secret**: In your target repository, navigate to **Settings** > **Secrets and variables** > **Actions**.
   Create a new repository secret named `GEMINI_API_KEY` and paste your key.
3. **Workflow Permissions**: GitHub Actions requires `pull-requests: write` to publish pull request reviews and comments, and `contents: write` to post commit comments on push events.
   The `GITHUB_TOKEN` secret is automatically provided by the GitHub Actions runner.

### How It Works Behind the Scenes

1. When a pull request or commit push occurs, GitHub Actions triggers the workflow.
2. The action automatically reads standard GitHub environment variables (`GITHUB_REPOSITORY`, `GITHUB_EVENT_NAME`, `GITHUB_EVENT_PATH`, `GITHUB_SHA`).
3. For pull requests, the action extracts the pull request number from the event webhook payload.
4. The action fetches the pull request diff directly from the GitHub REST API without requiring a local git checkout.
5. `diff_parser.py` parses the patch, filters non-code files, and annotates changed lines with line numbers.
6. `gemini_service.py` sends the annotated diff to Google Gemini.
7. `review.py` validates returned line numbers against added lines and snaps comments to valid diff positions.
8. `github_client.py` publishes inline comments and a structured markdown summary back to the pull request.

## Action Inputs and Environment Variables

The action is designed to run with only two environment variables provided in `env`:

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key used for code review. |
| `GITHUB_TOKEN` | Yes | GitHub authentication token (use `${{ secrets.GITHUB_TOKEN }}`). |

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
│       └── ai-code-review.yml     # Self-testing workflow definition
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
├── action.yml                     # GitHub Action definition
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
