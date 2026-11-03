"""Regression checks for a paper component inside a Git checkout (run with TeX Live)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PAPER = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('texlua'), 'requires TeX Live')
class LayoutTests(unittest.TestCase):
    def test_parent_git_hygiene_and_annotation_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paper = root / 'paper'
            for name in ('scripts', 'content', 'include', 'bib', 'guide'):
                shutil.copytree(PAPER / name, paper / name)
            shutil.copy2(PAPER / 'draft.tex', paper / 'draft.tex')
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            for path, text in [('paper/final.pdf', 'generated'), ('paper-final.pdf', 'generated'),
                               ('.claude/settings.local.json', '{}')]:
                p = root / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text)
            subprocess.run(['git', '-C', str(root), 'add', 'paper/final.pdf', 'paper-final.pdf',
                            '.claude/settings.local.json', 'paper/guide/guide.bbl'], check=True)
            env = {k: v for k, v in os.environ.items() if not k.startswith('GITHUB_')}
            result = subprocess.run(['texlua', 'scripts/lint.lua', 'repo-hygiene', '--json'],
                                    cwd=paper, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data['rules'][0]['status'], 'fix')
            self.assertEqual({f['file'] for f in data['findings']},
                             {'final.pdf', '../paper-final.pdf', '../.claude/settings.local.json'})
            annotated = subprocess.run(['texlua', 'scripts/lint.lua', 'repo-hygiene'], cwd=paper,
                                       env={**env, 'GITHUB_ACTIONS': 'true'}, capture_output=True, text=True)
            self.assertIn('file=paper/final.pdf', annotated.stdout)
            self.assertIn('file=paper-final.pdf', annotated.stdout)
            self.assertNotIn('file=paper/../', annotated.stdout)

    def test_evidence_replays_current_git_scripts_from_paper(self):
        probe = subprocess.run(['git', 'cat-file', '-e', 'HEAD:paper/scripts'],
                               cwd=PAPER, capture_output=True)
        if probe.returncode:
            self.skipTest('requires a committed monorepo checkout')
        result = subprocess.run(['python3', 'scripts/lint/tests/evidence.py',
                                 '--only', '^gap-filled-baseline$', '--scripts-ref', 'HEAD'],
                                cwd=PAPER, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('1/1 passed', result.stdout)

    def test_personas_stay_at_monorepo_root(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('review_layout', PAPER / 'scripts/review/review.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue((module.PERSONAS / 'skim.md').is_file())
        self.assertEqual(module.PERSONAS, PAPER.parent / '.claude/skills/reviewer-passes/personas')


if __name__ == '__main__':
    unittest.main()
