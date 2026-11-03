"""The hygiene command checks code/, not unrelated monorepo components."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "hygiene.py"


class HygieneScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "code/scripts").mkdir(parents=True)
        (self.root / "paper").mkdir()
        shutil.copy2(SOURCE, self.root / "code/scripts/hygiene.py")
        self.git("init", "-q")
        self.git("config", "user.name", "Test Maintainer")
        self.git("config", "user.email", "maintainer@example.invalid")

        # This paper-owned finding and agent identity must not affect code hygiene.
        (self.root / "paper/draft.tex").write_text(
            r"\documentclass{article} % https://overleaf.com/" + "project/private\n",
            encoding="utf-8",
        )
        self.git("add", "paper/draft.tex")
        paper_env = os.environ | {
            "GIT_AUTHOR_NAME": "Codex Agent",
            "GIT_AUTHOR_EMAIL": "codex@openai.com",
            "GIT_COMMITTER_NAME": "Codex Agent",
            "GIT_COMMITTER_EMAIL": "codex@openai.com",
        }
        subprocess.run(["git", "commit", "-m", "Add private paper draft"], cwd=self.root,
                       env=paper_env, check=True, capture_output=True, text=True)

        (self.root / "code/README.md").write_text("Code component\n", encoding="utf-8")
        (self.root / "code/justfile").write_text("test:\n    @true\n", encoding="utf-8")
        self.git("add", "code")
        self.git("commit", "-m", "Add code component")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              capture_output=True, text=True)

    def run_hygiene(self):
        return subprocess.run([sys.executable, "code/scripts/hygiene.py"], cwd=self.root,
                              capture_output=True, text=True)

    def add_original_source_history(self):
        content = b"Old source tree: https://overleaf.com/" + b"project/private\n"
        blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=self.root,
                              input=content, check=True, capture_output=True, text=False).stdout.decode().strip()
        tree = subprocess.run(["git", "mktree"], cwd=self.root,
                              input=f"100644 blob {blob}\tREADME.md\n", check=True,
                              capture_output=True, text=True).stdout.strip()
        env = os.environ.copy()
        env.update({"GIT_AUTHOR_NAME": "Test Maintainer", "GIT_AUTHOR_EMAIL": "maintainer@example.invalid",
                    "GIT_COMMITTER_NAME": "Test Maintainer", "GIT_COMMITTER_EMAIL": "maintainer@example.invalid"})
        head = subprocess.run(["git", "commit-tree", tree, "-m", "Old source snapshot"], cwd=self.root,
                              env=env, check=True, capture_output=True, text=True).stdout.strip()
        (self.root / "code/scripts/source-history.txt").write_text(head + "\n", encoding="utf-8")
        self.git("add", "code/scripts/source-history.txt")
        self.git("commit", "-m", "Record source history root")

    def test_ignores_paper_tree_and_history(self):
        result = self.run_hygiene()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("private-link", result.stdout)
        self.assertNotIn("agent-author", result.stdout)
        self.assertNotIn("paper-source", result.stdout)

    def test_detects_findings_inside_code(self):
        (self.root / "code/README.md").write_text(
            "Private draft: https://overleaf.com/" + "project/example\n", encoding="utf-8"
        )
        result = self.run_hygiene()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("private-link", result.stdout)

    def test_scans_pre_import_history_at_its_original_repository_root(self):
        self.add_original_source_history()
        result = self.run_hygiene()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("warning[private-link]", result.stdout)
        self.assertIn("README.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
