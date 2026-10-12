"""Regression checks for failures the repository gate must catch."""

import json
from pathlib import Path
import tempfile
import unittest

from check_repository import REQUIRED_FILES, validate


class RepositoryChecksTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in REQUIRED_FILES:
            self.write(name, '# Placeholder\n')
        self.write('SystemCode/config/project.example.json', json.dumps({
            'scenario': {'country': 'Singapore', 'study_area': 'Jurong'},
            'planning': {'default_crew_count': 4,
                         'crew_ids': ['crew-01', 'crew-02', 'crew-03', 'crew-04'],
                         'task_counts_for_evaluation': [10, 15, 20]},
        }))

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def inspect(self):
        paths = [path.relative_to(self.root).as_posix() for path in self.root.rglob('*') if path.is_file()]
        return validate(self.root, paths)

    def test_scaffold_does_not_claim_application_tests(self):
        errors, modules = self.inspect()
        self.assertEqual(errors, [])
        self.assertEqual(modules, {'python': False, 'frontend': False})

    def test_changed_scope_and_invalid_json_fail(self):
        path = self.root / 'SystemCode/config/project.example.json'
        config = json.loads(path.read_text())
        config['planning']['default_crew_count'] = 2
        self.write('SystemCode/config/project.example.json', json.dumps(config))
        self.assertTrue(any('four agreed' in error for error in self.inspect()[0]))
        self.write('SystemCode/config/project.example.json', '{broken')
        self.assertTrue(any('Invalid JSON' in error for error in self.inspect()[0]))
        self.write('SystemCode/config/project.example.json', 'null')
        self.assertTrue(any('missing the agreed structure' in error for error in self.inspect()[0]))

    def test_broken_links_fail_but_fenced_examples_and_urls_do_not(self):
        self.write('README.md', '[rules](AGENTS.md)\n[web](https://example.com)\n```md\n[example](missing.md)\n```\n')
        self.assertEqual(self.inspect()[0], [])
        self.write('README.md', '[missing](missing.md)\n')
        self.assertTrue(any('Broken local' in error for error in self.inspect()[0]))

    def test_conflict_markers_and_environment_files_fail(self):
        self.write('README.md', '<' * 7 + ' HEAD\nconflicting text\n')
        self.write('.env', 'DEMO_VALUE=not-a-secret\n')
        errors, _ = self.inspect()
        self.assertTrue(any('merge marker' in error for error in errors))
        self.assertTrue(any('Remove local' in error for error in errors))

    def test_new_python_code_cannot_silently_skip_tests(self):
        self.write('SystemCode/backend/app/main.py', 'value = 1\n')
        errors, modules = self.inspect()
        self.assertTrue(modules['python'])
        self.assertTrue(any('requirements-ci.txt' in error for error in errors))
        self.assertTrue(any('real pytest tests' in error for error in errors))

    def test_new_frontend_code_requires_test_and_build_integration(self):
        self.write('SystemCode/frontend/src/App.tsx', 'export const value = 1;\n')
        errors, modules = self.inspect()
        self.assertTrue(modules['frontend'])
        for expected in ['lint', 'test:ci', 'build', 'package-lock.json', 'real *.test.*']:
            self.assertTrue(any(expected in error for error in errors), expected)

    def test_invalid_python_is_detected_without_execution(self):
        self.write('.github/scripts/broken.py', 'def missing_colon()\n    pass\n')
        self.assertTrue(any('Invalid Python syntax' in error for error in self.inspect()[0]))

    def test_declared_modules_are_selected_for_execution(self):
        self.write('SystemCode/backend/app/main.py', 'value = 1\n')
        self.write('SystemCode/backend/requirements-ci.txt', 'pytest==8.3.5\n')
        self.write('SystemCode/tests/test_example.py', 'def test_example():\n    assert 1 == 1\n')
        self.write('SystemCode/frontend/package.json', json.dumps({
            'scripts': {'lint': 'eslint .', 'test:ci': 'vitest run', 'build': 'vite build'},
        }))
        self.write('SystemCode/frontend/package-lock.json', '{}')
        self.write('SystemCode/frontend/src/App.test.tsx', '// Gate-selection fixture, not an application test.\n')
        errors, modules = self.inspect()
        self.assertEqual(errors, [])
        self.assertEqual(modules, {'python': True, 'frontend': True})


if __name__ == '__main__':
    unittest.main()
