"""Scratch retains notes while excluding common local credentials and outputs."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class ScratchIgnoreTests(unittest.TestCase):
    def test_local_files_excluded_and_notes_retained(self):
        source = Path(__file__).resolve().parents[2] / ".gitignore"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scratch").mkdir()
            shutil.copy2(source, root / "scratch/.gitignore")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def ignored(path):
                return subprocess.run(["git", "check-ignore", "--no-index", "-q", path],
                                      cwd=root).returncode == 0
            for path in (".env", ".env.local", "token.key", "out/data.csv", "results/data.csv",
                         ".venv/bin/python", "node_modules/example/package.json"):
                with self.subTest(path=path):
                    self.assertTrue(ignored("scratch/" + path))
            for path in ("notes/consultations/meeting.md", "notes/results-analysis.md",
                         "research.csv", ".env.example"):
                with self.subTest(path=path):
                    self.assertFalse(ignored("scratch/" + path))


if __name__ == "__main__":
    unittest.main()
