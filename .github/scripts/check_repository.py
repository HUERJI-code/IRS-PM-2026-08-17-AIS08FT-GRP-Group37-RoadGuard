"""Validate the scaffold and require real test integration as code is added."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit


REQUIRED_FILES = (
    'README.md',
    'AGENTS.md',
    'SystemCode/README.md',
    'ProjectReport/README.md',
    'Video/README.md',
    'Miscellaneous/README.md',
    'Miscellaneous/TEAM_WORK_ALLOCATION.md',
    'SystemCode/config/project.example.json',
)
TEXT_SUFFIXES = {'.md', '.json', '.py', '.js', '.jsx', '.ts', '.tsx', '.yml', '.yaml', '.txt'}
PYTHON_ROOTS = ('SystemCode/backend/', 'SystemCode/model/', 'SystemCode/experiments/', 'SystemCode/tests/')
FRONTEND_ROOT = 'SystemCode/frontend/'
CONFLICT_MARKER = re.compile(r'^(?:<{7}|={7}|>{7}|\|{7})(?:\s|$)', re.MULTILINE)
INLINE_LINK = re.compile(r'\]\((<[^>]+>|[^\s)]+)(?:\s+["\'][^)]*)?\)')


def markdown_prose(text: str) -> str:
    """Exclude fenced examples; paths in examples are not documentation links."""
    lines = []
    fence = None
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            delimiter = match.group(1)
            if fence is None:
                fence = delimiter
            elif delimiter[0] == fence[0] and len(delimiter) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return '\n'.join(lines)


def validate(root: Path, paths: list[str]) -> tuple[list[str], dict[str, bool]]:
    tracked = set(paths)
    errors: list[str] = []
    parsed_json = {}
    for required in REQUIRED_FILES:
        if required not in tracked or not (root / required).is_file():
            errors.append(f'Missing required file: {required}')

    for name in sorted(tracked):
        relative = PurePosixPath(name)
        path = root / name
        if not path.is_file():
            continue
        if (relative.name == '.env' or
                (relative.name.startswith('.env.') and relative.name != '.env.example') or
                relative.suffix in {'.pem', '.key', '.db', '.sqlite', '.sqlite3', '.pt', '.pth', '.onnx'} or
                any(part in {'node_modules', '.venv', '__pycache__'} for part in relative.parts)):
            errors.append(f'Remove local credentials/runtime/generated file from Git: {name}')
        if relative.suffix not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeError:
            errors.append(f'Not valid UTF-8: {name}')
            continue
        if CONFLICT_MARKER.search(text):
            errors.append(f'Unresolved merge marker: {name}')
        if relative.suffix == '.json':
            try:
                parsed_json[name] = json.loads(text)
            except ValueError as exc:
                errors.append(f'Invalid JSON: {name}: {exc}')
        if relative.suffix == '.py':
            try:
                ast.parse(text, filename=name)
            except SyntaxError as exc:
                errors.append(f'Invalid Python syntax: {name}:{exc.lineno}: {exc.msg}')
        if relative.suffix == '.md':
            for match in INLINE_LINK.finditer(markdown_prose(text)):
                target = match.group(1).strip('<>')
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                link = unquote(parsed.path)
                destination = (root / link.lstrip('/') if link.startswith('/') else path.parent / link).resolve()
                if not destination.is_relative_to(root.resolve()):
                    errors.append(f'Local Markdown link leaves repository: {name} -> {target}')
                elif not destination.exists():
                    errors.append(f'Broken local Markdown link: {name} -> {target}')

    config = parsed_json.get('SystemCode/config/project.example.json')
    if 'SystemCode/config/project.example.json' in parsed_json:
        try:
            scenario, planning = config['scenario'], config['planning']
            if scenario['country'] != 'Singapore' or scenario['study_area'] != 'Jurong':
                errors.append('Default study area must remain Singapore / Jurong.')
            if planning['default_crew_count'] != 4 or planning['crew_ids'] != [f'crew-{i:02d}' for i in range(1, 5)]:
                errors.append('Default configuration must contain the four agreed crew IDs.')
            if planning['task_counts_for_evaluation'] != [10, 15, 20]:
                errors.append('Primary evaluation must retain task counts 10/15/20.')
        except (KeyError, TypeError):
            errors.append('Example scenario configuration is missing the agreed structure.')

    has_python = any(name.startswith(PYTHON_ROOTS) and name.endswith('.py') for name in tracked)
    has_frontend = any(name.startswith(FRONTEND_ROOT) and
                       (name.endswith(('.js', '.jsx', '.ts', '.tsx')) or
                        name == FRONTEND_ROOT + 'package.json') for name in tracked)
    if has_python:
        if 'SystemCode/backend/requirements-ci.txt' not in tracked:
            errors.append('Python code requires SystemCode/backend/requirements-ci.txt (including pytest).')
        if not any(name.startswith('SystemCode/tests/') and name.endswith('.py') and
                   (PurePosixPath(name).name.startswith('test_') or name.endswith('_test.py')) for name in tracked):
            errors.append('Python code requires real pytest tests under SystemCode/tests/.')
    if has_frontend:
        package = parsed_json.get(FRONTEND_ROOT + 'package.json', {})
        scripts = package.get('scripts', {}) if isinstance(package, dict) else {}
        if not isinstance(scripts, dict):
            scripts = {}
        for script in ('lint', 'test:ci', 'build'):
            command = scripts.get(script)
            if not isinstance(command, str) or not command.strip():
                errors.append(f'Frontend package.json requires a working {script!r} script.')
        if FRONTEND_ROOT + 'package-lock.json' not in tracked:
            errors.append('Frontend requires a committed package-lock.json for npm ci.')
        if not any(name.startswith(FRONTEND_ROOT) and
                   re.search(r'\.(?:test|spec)\.[jt]sx?$', name) for name in tracked):
            errors.append('Frontend code requires real *.test.* or *.spec.* tests.')
    return errors, {'python': has_python, 'frontend': has_frontend}


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
        cwd=root, capture_output=True, check=True,
    )
    paths = [name for name in result.stdout.decode('utf-8').split('\0') if name]
    errors, modules = validate(root, paths)
    lines = [f'{name}={str(enabled).lower()}' for name, enabled in modules.items()]
    if output := os.environ.get('GITHUB_OUTPUT'):
        with open(output, 'a', encoding='utf-8') as handle:
            handle.write('\n'.join(lines) + '\n')
    for line in lines:
        print(line)
    if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(summary, 'a', encoding='utf-8') as handle:
            handle.write('Application test selection: ' + ', '.join(lines) + '\n\n')
            handle.write('A false value means application code is absent; it is not a passed application test.\n')
    for error in errors:
        print(f'ERROR: {error}', file=sys.stderr)
    if errors:
        return 1
    print(f'Repository checks passed ({len(set(paths))} files).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
