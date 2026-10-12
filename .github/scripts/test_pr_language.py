"""Stdlib checks for the language policy and safe CLI event handling."""

from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pr_language import main, validate_english


class PRLanguageTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.event_path = Path(directory.name) / "private-event.json"

    def invoke(self, path):
        environment = os.environ.copy()
        environment.pop("GITHUB_EVENT_PATH", None)
        if path is not None:
            environment["GITHUB_EVENT_PATH"] = str(path)
        output = StringIO()
        with patch.dict(os.environ, environment, clear=True), redirect_stdout(output):
            status = main()
        text = output.getvalue()
        for private in ("private-token", str(self.event_path), "Traceback"):
            self.assertNotIn(private, text)
        return status, text

    def test_title_and_body_require_nonempty_text(self):
        for value in (None, "", " \n\t ", 123, [], {}):
            with self.subTest(value=value):
                self.assertTrue(validate_english(value, "Valid body"))
                self.assertTrue(validate_english("Valid title", value))

    def test_each_field_requires_an_ascii_latin_letter(self):
        for value in ("123", "🛠️", "É", "-- ✅ --"):
            with self.subTest(value=value):
                self.assertTrue(validate_english(value, "Body"))
                self.assertTrue(validate_english("Title", value))

    def test_non_latin_letters_are_rejected_without_echoing_text(self):
        for value in ("中文", "カナ", "한글", "Привет", "مرحبا", "Ελληνικά", "हिन्दी"):
            with self.subTest(script=value):
                text = "English " + value
                errors = validate_english("Title", text)
                self.assertEqual(errors, ["PR body must use Latin letters for English text."])
                self.assertNotIn(text, " ".join(errors))

    def test_english_markdown_names_paths_quotes_urls_and_emojis_are_allowed(self):
        body = "## Changes\nFix José's parser — review by Zoë. 🛠️\n> Ready\n`src/file.py`\nhttps://example.org/x\n```python\nprint('ok')\n```"
        self.assertEqual(validate_english("Fix parser’s output ✅", body), [])

    def test_event_contexts(self):
        for event, expected in (
            ({"pull_request": {"title": "Fix parser", "body": "Add validation."}}, 0),
            ({"pull_request": {"title": "中文 private-token", "body": "Valid body"}}, 1),
            ({"pull_request": {"title": "Fix parser"}}, 1),
            ({"pull_request": None}, 1),
            ({"ref": "refs/heads/main"}, 0), ({"inputs": {}}, 0), ([], 1),
        ):
            with self.subTest(event=event):
                self.event_path.write_text(json.dumps(event), encoding="utf-8")
                self.assertEqual(self.invoke(self.event_path)[0], expected)

    def test_unavailable_or_corrupt_event_fails_safely(self):
        for mode in ("missing_environment", "missing_file", "bad_json", "bad_utf8"):
            with self.subTest(mode=mode):
                self.event_path.unlink(missing_ok=True)
                if mode == "bad_json":
                    self.event_path.write_text("private-token invalid JSON", encoding="utf-8")
                elif mode == "bad_utf8":
                    self.event_path.write_bytes(b"\xffprivate-token")
                status, output = self.invoke(None if mode == "missing_environment" else self.event_path)
                self.assertEqual(status, 1)
                self.assertIn("failed", output)

    def test_cli_entrypoint_returns_the_check_status_without_site_packages(self):
        for body, expected in (("Valid English body", 0), ("English 中文", 1)):
            with self.subTest(body=body):
                self.event_path.write_text(json.dumps({"pull_request": {"title": "Title", "body": body}}), encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, "-S", str(Path(__file__).with_name("pr_language.py"))],
                    env=os.environ | {"GITHUB_EVENT_PATH": str(self.event_path)},
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, expected)
                self.assertNotIn(str(self.event_path), result.stdout + result.stderr)
