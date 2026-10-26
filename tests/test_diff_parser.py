import unittest
import os
import sys

# Ensure src/code_review is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "code_review")))

from diff_parser import parse_diff, parse_patch, should_skip_file, _splitext


class TestDiffParser(unittest.TestCase):

    def test_should_skip_file_extensions(self):
        # Skipped file types
        self.assertTrue(should_skip_file("package-lock.json"))
        self.assertTrue(should_skip_file("yarn.lock"))
        self.assertTrue(should_skip_file("pnpm-lock.yaml"))
        self.assertTrue(should_skip_file("logo.png"))
        self.assertTrue(should_skip_file("icon.svg"))
        self.assertTrue(should_skip_file("bundle.min.js"))
        self.assertTrue(should_skip_file("styles.min.css"))
        self.assertTrue(should_skip_file("app.js.map"))

        # Allowed file types
        self.assertFalse(should_skip_file("main.py"))
        self.assertFalse(should_skip_file("App.tsx"))
        self.assertFalse(should_skip_file("workflow.yml"))
        self.assertFalse(should_skip_file("server.go"))

    def test_splitext(self):
        self.assertEqual(_splitext("test.py"), ("test", ".py"))
        self.assertEqual(_splitext("archive.tar.gz"), ("archive.tar", ".gz"))
        self.assertEqual(_splitext("Makefile"), ("Makefile", ""))

    def test_parse_patch(self):
        sample_patch = (
            "@@ -10,4 +10,5 @@ def compute(x):\n"
            "     total = 0\n"
            "-    old_factor = 1\n"
            "+    new_factor = 2\n"
            "+    total += x * new_factor\n"
            "     return total\n"
        )
        chunks = parse_patch(sample_patch)
        self.assertEqual(len(chunks), 1)

        chunk = chunks[0]
        # Added lines should be 11 and 12
        self.assertEqual(chunk["added_lines"], [11, 12])

        # changed_lines maps new line number to 1-based diff position
        # Position 1: hunk header (not stored in changed_lines)
        # Position 2: '     total = 0' -> line 10
        # Position 3: '-    old_factor = 1' (deleted line, not in changed_lines)
        # Position 4: '+    new_factor = 2' -> line 11
        # Position 5: '+    total += x * new_factor' -> line 12
        # Position 6: '     return total' -> line 13
        self.assertIn(11, chunk["changed_lines"])
        self.assertIn(12, chunk["changed_lines"])
        self.assertEqual(chunk["changed_lines"][11], 4)
        self.assertEqual(chunk["changed_lines"][12], 5)

        # Annotated lines check
        self.assertTrue(any("L11: +    new_factor = 2" in line for line in chunk["annotated_lines"]))
        self.assertTrue(any("     : -    old_factor = 1" in line for line in chunk["annotated_lines"]))

    def test_parse_diff(self):
        changed_files = [
            {
                "filename": "src/utils.py",
                "status": "modified",
                "patch": "@@ -1,3 +1,4 @@\n a = 1\n+b = 2\n c = 3\n",
            },
            {
                "filename": "package-lock.json",
                "status": "modified",
                "patch": "@@ -1,1 +1,1 @@\n-1\n+2\n",
            },
            {
                "filename": "deleted_file.py",
                "status": "removed",
                "patch": "@@ -1,2 +0,0 @@\n-a\n-b\n",
            },
            {
                "filename": "empty_patch.py",
                "status": "modified",
                "patch": "",
            },
        ]
        entries = parse_diff(changed_files)
        # Only src/utils.py should be parsed; lock files, removed files, and empty patches are skipped
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["path"], "src/utils.py")
        self.assertEqual(entries[0]["status"], "modified")


if __name__ == "__main__":
    unittest.main()
