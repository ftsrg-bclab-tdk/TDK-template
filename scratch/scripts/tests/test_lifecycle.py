"""Lifecycle checks use the monorepo paper phase and component path history."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lifecycle


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Test Maintainer")
        self.git("config", "user.email", "maintainer@example.invalid")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args, env=None):
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              capture_output=True, text=True, env=env)

    def commit_file(self, path, contents, age_days):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents, encoding="utf-8")
        self.git("add", path)
        when = datetime.now(timezone.utc) - timedelta(days=age_days, seconds=2)
        stamp = when.strftime("%Y-%m-%dT%H:%M:%S%z")
        env = os.environ.copy()
        env.update({"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp})
        self.git("commit", "-m", f"Update {path}", env=env)

    def test_phase_reads_root_paper_draft(self):
        path = self.root / "paper/draft.tex"
        path.parent.mkdir(parents=True)
        path.write_text(r"\newcommand{\lintphase}{polish}" + "\n", encoding="utf-8")
        with patch.object(lifecycle, "ROOT", self.root):
            self.assertEqual(lifecycle.phase(), "polish")

    def test_age_zero_is_recent_and_path_history_is_component_specific(self):
        self.commit_file("paper/draft.tex", "paper", 0)
        self.commit_file("code/README.md", "code", 7)
        self.commit_file("scratch/notes/anchors/spine.md", "notes", 0)
        with patch.object(lifecycle, "ROOT", self.root):
            self.assertEqual(lifecycle.path_age("paper"), 0)
            self.assertEqual(lifecycle.path_age("code"), 7)
            self.assertIsNone(lifecycle.path_age("proof"))

    def test_shallow_history_is_unknown(self):
        self.commit_file("code/README.md", "code", 1)
        head = self.git("rev-parse", "HEAD").stdout.strip()
        (self.root / ".git/shallow").write_text(head + "\n", encoding="utf-8")
        with patch.object(lifecycle, "ROOT", self.root):
            self.assertIsNone(lifecycle.path_age("code"))

    def test_unknown_history_does_not_fail_a_due_recentness_row(self):
        (self.root / "scratch").mkdir()
        checks = [("Code updated in the last 14 days", "draft",
                   lambda: lifecycle.recent_path("code"))]
        with patch.object(lifecycle, "ROOT", self.root), \
                patch.object(lifecycle, "phase", return_value="draft"), \
                patch.object(lifecycle, "ROWS", checks), redirect_stdout(StringIO()) as out:
            result = lifecycle.main()
        self.assertEqual(result, 0)
        self.assertIn("| Code updated in the last 14 days | draft | unknown |", out.getvalue())


if __name__ == "__main__":
    unittest.main()
