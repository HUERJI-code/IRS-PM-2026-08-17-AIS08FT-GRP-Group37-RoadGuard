"""Conservative PR character policy; it cannot prove text is natural English."""

import json
import os
from pathlib import Path
import unicodedata


def validate_english(title: str | None, body: str | None) -> list[str]:
    """Return safe policy messages without repeating untrusted PR content."""
    errors = []
    for field, value in (("title", title), ("body", body)):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"PR {field} must be nonempty text.")
            continue
        if not any("A" <= char <= "Z" or "a" <= char <= "z" for char in value):
            errors.append(f"PR {field} must contain an ASCII Latin letter.")
        if any(char.isalpha() and "LATIN" not in unicodedata.name(char, "") for char in value):
            errors.append(f"PR {field} must use Latin letters for English text.")
    return errors


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("PR language check failed: event input is unavailable.")
        return 1
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        print("PR language check failed: event input could not be read.")
        return 1
    if not isinstance(event, dict):
        print("PR language check failed: event input must be an object.")
        return 1
    if "pull_request" not in event:
        print("PR language check skipped: this event has no pull request.")
        return 0
    pull_request = event["pull_request"]
    if not isinstance(pull_request, dict):
        print("PR language check failed: pull request data is invalid.")
        return 1
    errors = validate_english(pull_request.get("title"), pull_request.get("body"))
    for error in errors:
        print(error)
    if errors:
        return 1
    print("PR language check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
