import requests


class GitHubClient:
    def __init__(self, token, repo_full_name):
        self.token = token
        self.repo = repo_full_name
        self.base_url = f"https://api.github.com/repos/{repo_full_name}"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def get_pr_files(self, pr_number):
        url = f"{self.base_url}/pulls/{pr_number}/files"
        files = []
        page = 1
        while True:
            response = requests.get(
                url, headers=self.headers, params={"per_page": 100, "page": page}
            )
            if response.status_code != 200:
                print(f"Error fetching PR files: {response.status_code} {response.text}")
                return []
            data = response.json()
            if not data:
                break
            files.extend(data)
            page += 1
        return files

    def get_review_comments(self, pr_number):
        url = f"{self.base_url}/pulls/{pr_number}/comments"
        response = requests.get(url, headers=self.headers, params={"per_page": 100})
        if response.status_code != 200:
            print(f"Error fetching comments: {response.status_code}")
            return []
        return response.json()

    def post_review(self, pr_number, comments):
        url = f"{self.base_url}/pulls/{pr_number}/reviews"
        review_comments = []
        for comment in comments:
            review_comments.append({
                "path": comment["path"],
                "position": comment["position"],
                "body": comment["body"],
            })

        body = {
            "event": "COMMENT",
            "comments": review_comments,
        }

        response = requests.post(url, headers=self.headers, json=body)
        if response.status_code not in (200, 201):
            print(f"Error posting review: {response.status_code} {response.text}")
            self._post_comments_individually(pr_number, comments)
        else:
            print("Review posted successfully.")

    def _post_comments_individually(self, pr_number, comments):
        url = f"{self.base_url}/pulls/{pr_number}/comments"
        posted = 0
        for comment in comments:
            body = {
                "path": comment["path"],
                "position": comment["position"],
                "body": comment["body"],
            }
            response = requests.post(url, headers=self.headers, json=body)
            if response.status_code in (200, 201):
                posted += 1
            else:
                print(f"Failed to post comment on {comment['path']}:pos{comment['position']}: {response.status_code} {response.text}")
        print(f"Posted {posted}/{len(comments)} comments individually.")

    def post_summary_comment(self, pr_number, body):
        url = f"{self.base_url}/issues/{pr_number}/comments"

        # Check for existing summary comments to avoid duplicates
        existing = self._get_issue_comments(pr_number)
        for comment in existing:
            if (
                comment.get("user", {}).get("type") == "Bot"
                and "AI Code Review Summary" in comment.get("body", "")
            ):
                # Update existing comment instead of creating a new one
                update_url = f"https://api.github.com/repos/{self.repo}/issues/comments/{comment['id']}"
                response = requests.patch(update_url, headers=self.headers, json={"body": body})
                if response.status_code == 200:
                    print("Updated existing summary comment.")
                    return
                break

        response = requests.post(url, headers=self.headers, json={"body": body})
        if response.status_code in (200, 201):
            print("Summary comment posted.")
        else:
            print(f"Error posting summary: {response.status_code} {response.text}")

    def _get_issue_comments(self, pr_number):
        url = f"{self.base_url}/issues/{pr_number}/comments"
        response = requests.get(url, headers=self.headers, params={"per_page": 100})
        if response.status_code != 200:
            return []
        return response.json()

    def get_commit(self, commit_sha):
        url = f"{self.base_url}/commits/{commit_sha}"
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            print(f"Error fetching commit: {response.status_code} {response.text}")
            return None
        return response.json()

    def get_commit_files(self, commit_sha):
        commit_data = self.get_commit(commit_sha)
        if not commit_data:
            return []
        return commit_data.get("files", [])

    def post_commit_comment(self, commit_sha, body):
        url = f"{self.base_url}/commits/{commit_sha}/comments"

        # Check for existing summary to avoid duplicates
        existing = self._get_commit_comments(commit_sha)
        for comment in existing:
            if (
                comment.get("user", {}).get("type") == "Bot"
                and "AI Code Review Summary" in comment.get("body", "")
            ):
                update_url = f"https://api.github.com/repos/{self.repo}/comments/{comment['id']}"
                response = requests.patch(update_url, headers=self.headers, json={"body": body})
                if response.status_code == 200:
                    print("Updated existing commit summary comment.")
                    return
                break

        response = requests.post(url, headers=self.headers, json={"body": body})
        if response.status_code in (200, 201):
            print("Commit summary comment posted.")
        else:
            print(f"Error posting commit comment: {response.status_code} {response.text}")

    def post_commit_comments(self, commit_sha, comments):
        url = f"{self.base_url}/commits/{commit_sha}/comments"
        posted = 0
        for comment in comments:
            body = {
                "body": comment["body"],
                "path": comment["path"],
                "position": comment.get("position", comment.get("line", 1)),
            }
            response = requests.post(url, headers=self.headers, json=body)
            if response.status_code in (200, 201):
                posted += 1
            else:
                print(f"Failed to post commit comment on {comment['path']}:{comment.get('line')}: {response.status_code} {response.text}")
        print(f"Posted {posted}/{len(comments)} inline comments on commit.")

    def _get_commit_comments(self, commit_sha):
        url = f"{self.base_url}/commits/{commit_sha}/comments"
        response = requests.get(url, headers=self.headers, params={"per_page": 100})
        if response.status_code != 200:
            return []
        return response.json()
