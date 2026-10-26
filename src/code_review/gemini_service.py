import json
import os
import requests


class GeminiService:
    def __init__(self, api_key):
        self.api_key = api_key
        self.model = "gemini-3.1-flash-lite"
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        self.prompt_template = self._load_prompt()

    def _load_prompt(self):
        # Allow custom review_prompt.md from workspace if available
        workspace = os.environ.get("GITHUB_WORKSPACE")
        if workspace:
            custom_path = os.path.join(workspace, "review_prompt.md")
            if os.path.isfile(custom_path):
                try:
                    with open(custom_path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception:
                    pass

        prompt_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "..",
            "review_prompt.md",
        )
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return self._default_prompt()

    def _default_prompt(self):
        return (
            "You are a senior code reviewer. Review the following code diff and provide feedback.\n"
            "Focus on: bugs, security issues, performance problems, and code quality.\n"
            "Respond in JSON format with 'summary' and 'comments' fields."
        )

    def review_code(self, diff_text):
        prompt = self.prompt_template + "\n\n## Code Diff to Review:\n\n" + diff_text

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0},
        }

        try:
            response = requests.post(
                self.url,
                params={"key": self.api_key},
                json=payload,
                timeout=60,
            )
        except requests.exceptions.Timeout:
            print("Error: Gemini API request timed out.")
            return None
        except requests.exceptions.RequestException as e:
            print(f"Error: Gemini API request failed: {e}")
            return None

        if response.status_code != 200:
            print(f"Gemini API error: {response.status_code} {response.text}")
            return None

        return self._parse_response(response.json())

    def _parse_response(self, response_data):
        try:
            candidates = response_data.get("candidates", [])
            if not candidates:
                print("No candidates in Gemini response.")
                return None

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                print("No parts in Gemini response.")
                return None

            text = parts[0].get("text", "")
            return self._extract_json(text)
        except (KeyError, IndexError) as e:
            print(f"Error parsing Gemini response: {e}")
            return None

    def _extract_json(self, text):
        # Try to find JSON in the response (might be wrapped in markdown code blocks)
        json_match = None

        # Try extracting from code block
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            json_match = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            json_match = text[start:end].strip()
        else:
            # Try parsing the whole text as JSON
            json_match = text.strip()

        try:
            result = json.loads(json_match)
            if "summary" not in result:
                result["summary"] = "Review completed."
            if "comments" not in result:
                result["comments"] = []
            return result
        except json.JSONDecodeError:
            print("Failed to parse JSON from Gemini response. Raw text:")
            print(text[:500])
            # Return a basic result with summary from raw text
            return {
                "summary": text[:500] if text else "Review completed but response was not parseable.",
                "comments": [],
            }
