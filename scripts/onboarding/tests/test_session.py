import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.onboarding import session


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((Path(__file__).parents[1] / "account-services.json").read_text())
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"

    def test_interruption_preserves_accepted_answer(self):
        answers = iter(["student-name"])
        def ask(prompt):
            try:
                return next(answers)
            except StopIteration:
                raise EOFError
        result = session.collect(self.path, self.catalog, ask, lambda event: None)
        self.assertTrue(result["interrupted"])
        state = session.load(self.path, self.catalog)
        self.assertEqual(state["github"]["identifier"]["value"], "student-name")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_dry_run_never_prompts_or_writes(self):
        result = session.collect(self.path, self.catalog, lambda _: self.fail(), lambda _: self.fail(), dry_run=True)
        self.assertTrue(result["prompts"])
        self.assertFalse(self.path.exists())

    def test_failed_replace_keeps_previous_file(self):
        session.save(self.path, self.catalog, {})
        previous = self.path.read_bytes()
        with patch.object(session.os, "replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                session.save(self.path, self.catalog, {})
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_save_failure_never_emits_saved(self):
        events = []
        with patch.object(session, "save", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                session.collect(self.path, self.catalog, lambda _: "student-name", events.append)
        self.assertFalse(events)

    def test_symlink_rejected(self):
        self.path.symlink_to(self.path.parent / "elsewhere")
        with self.assertRaises(ValueError):
            session.save(self.path, self.catalog, {})
