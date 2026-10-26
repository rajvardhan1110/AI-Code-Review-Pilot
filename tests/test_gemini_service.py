import unittest
import os
import sys

# Ensure src/code_review is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "code_review")))

from gemini_service import GeminiService


class TestGeminiService(unittest.TestCase):

    def setUp(self):
        self.service = GeminiService("test_api_key")

    def test_prompt_loaded_from_file(self):
        # Prompt should be loaded from review_prompt.md
        self.assertTrue(len(self.service.prompt_template) > 0)
        self.assertIn("Code Review Prompt", self.service.prompt_template)
        self.assertIn("Inline comments", self.service.prompt_template)

    def test_extract_json_from_markdown_block(self):
        text = (
            "Here is the review:\n"
            "```json\n"
            "{\n"
            '  "summary": "Looks good overall.",\n'
            '  "comments": [\n'
            '    {"path": "main.py", "line": 10, "body": "[Added] Added function"}\n'
            "  ]\n"
            "}\n"
            "```\n"
        )
        parsed = self.service._extract_json(text)
        self.assertEqual(parsed["summary"], "Looks good overall.")
        self.assertEqual(len(parsed["comments"]), 1)
        self.assertEqual(parsed["comments"][0]["path"], "main.py")
        self.assertEqual(parsed["comments"][0]["line"], 10)

    def test_extract_json_from_generic_code_block(self):
        text = (
            "```\n"
            "{\n"
            '  "summary": "Simple update.",\n'
            '  "comments": []\n'
            "}\n"
            "```\n"
        )
        parsed = self.service._extract_json(text)
        self.assertEqual(parsed["summary"], "Simple update.")
        self.assertEqual(parsed["comments"], [])

    def test_extract_json_raw(self):
        text = '{"summary": "No issues found.", "comments": []}'
        parsed = self.service._extract_json(text)
        self.assertEqual(parsed["summary"], "No issues found.")
        self.assertEqual(parsed["comments"], [])

    def test_extract_json_invalid_fallback(self):
        text = "This is not valid JSON at all."
        parsed = self.service._extract_json(text)
        self.assertEqual(parsed["summary"], "This is not valid JSON at all.")
        self.assertEqual(parsed["comments"], [])

    def test_parse_response_with_candidates(self):
        response_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"summary": "Clean code", "comments": []}'
                            }
                        ]
                    }
                }
            ]
        }
        result = self.service._parse_response(response_data)
        self.assertEqual(result["summary"], "Clean code")


if __name__ == "__main__":
    unittest.main()
