import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("setup_entry", SCRIPTS / "setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        (self.root / ".gitignore").write_text("/.onboarding/\n")
        (self.root / "thesis.tex").write_text(
            "\\newcommand{\\vikcim}{Old title}\n"
            "\\newcommand{\\lintphase}{draft}\n"
            "\\todo{Keep student notes}\n")
        self.git("add", ".gitignore", "thesis.tex")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Fixture")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.DEVNULL)

    def call(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = setup.main([*args, "--root", str(self.root)])
        return code, output.getvalue()

    def test_advisor_dry_run_has_no_writes(self):
        before = self.git("status", "--porcelain")
        code, output = self.call("advisor", "--init-config", "org/project", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertEqual(before, self.git("status", "--porcelain"))
        self.assertFalse((self.root / ".onboarding").exists())
        self.assertFalse((self.root / "onboarding.json").exists())

    def test_student_resume_without_echoing_identifier(self):
        with patch("builtins.input", side_effect=["private-person", EOFError()]):
            code, output = self.call("student")
        self.assertEqual(code, 0, output)
        self.assertNotIn("private-person", output)
        with patch("builtins.input", side_effect=["yes", EOFError()]):
            code, output = self.call("student")
        self.assertEqual(code, 0, output)
        saved = json.loads((self.root / ".onboarding/accounts.json").read_text())
        self.assertEqual(saved["accounts"]["github"]["account"]["status"], "manual_attested")

    def test_metadata_preview_apply_idempotence_and_conflict(self):
        self.call("advisor", "--init-config", "org/project")
        config_path = self.root / "onboarding.json"
        config = json.loads(config_path.read_text())
        config["metadata"]["vikcim"]["value"] = "A & B"
        config_path.write_text(json.dumps(config))
        before = (self.root / "thesis.tex").read_bytes()
        code, output = self.call("advisor")
        self.assertEqual(code, 0, output)
        self.assertEqual((self.root / "thesis.tex").read_bytes(), before)
        code, output = self.call("advisor", "--apply-metadata")
        self.assertEqual(code, 0, output)
        after = (self.root / "thesis.tex").read_text()
        self.assertIn(r"A \& B", after)
        self.assertIn(r"\lintphase}{draft}", after)
        self.assertIn("Keep student notes", after)
        self.assertEqual(self.call("advisor", "--apply-metadata")[0], 0)
        (self.root / "thesis.tex").write_text(after.replace(r"A \& B", "Student edit"))
        code, output = self.call("advisor", "--apply-metadata")
        self.assertEqual(code, 2)
        self.assertIn("Student edit", (self.root / "thesis.tex").read_text())

    def test_rejects_tracked_or_unignored_state(self):
        self.assertEqual(self.call("status", "--state-dir", "unignored")[0], 2)
        local = self.root / ".onboarding"
        local.mkdir(mode=0o700)
        (local / "secret").write_text("fixture")
        self.git("add", "-f", ".onboarding/secret")
        self.assertEqual(self.call("status")[0], 2)

    def test_rejects_symlink_and_public_state_dir(self):
        local = self.root / ".onboarding"
        local.symlink_to(self.root, target_is_directory=True)
        self.assertEqual(self.call("status")[0], 2)
        local.unlink()
        local.mkdir(mode=0o755)
        self.assertEqual(self.call("status")[0], 2)

    def test_serialized_writers_and_readers(self):
        path = setup.state_path(self.root, ".onboarding")
        with setup.locked(path):
            code, output = self.call("student", "--skip-accounts")
            self.assertEqual(code, 2)
            self.assertIn("Another setup session", output)
            self.assertEqual(self.call("status")[0], 2)

    def test_once_per_run_latest_resolution_and_digest_execution(self):
        calls = []
        digest = "alpine@sha256:" + "a" * 64
        def fake(argv, timeout=30):
            calls.append(argv)
            if "inspect" in argv:
                return {"returncode": 0, "stdout": json.dumps({"RepoDigests": [digest], "Id": "sha256:fixture", "Os": "linux", "Architecture": "amd64"})}
            return {"returncode": 0, "stdout": "version"}
        report = setup.bootstrap_report(fake, smoke=True)
        self.assertTrue(report["ready"])
        self.assertEqual(sum("pull" in c for c in calls), 1)
        self.assertEqual(sum("inspect" in c for c in calls), 1)
        smoke = next(c for c in calls if "run" in c)
        self.assertIn(digest, smoke)
        self.assertNotIn("alpine:latest", smoke)

    def test_pull_failure_never_reuses_old_image(self):
        calls = []
        def fake(argv, timeout=30):
            calls.append(argv)
            return {"returncode": 1, "stdout": "private error"}
        report = setup.bootstrap_report(fake, smoke=True)
        self.assertFalse(report["ready"])
        self.assertEqual(len(calls), 1)
        self.assertNotIn("private error", json.dumps(report))

    def test_real_version_checks_without_smoke_do_not_start_container(self):
        # Run actual harmless Git/Python probes; Docker/gh may be unavailable.
        report = setup.bootstrap_report(smoke=False)
        self.assertFalse(report["ready"])
        self.assertIsNone(report["resolution"])

    def test_external_observation_retry_and_conflict(self):
        class Fake:
            count = 0
            def observe(self, step, config):
                self.count += 1
                if self.count == 1:
                    raise TimeoutError
                return {"project": "org/project", "status": "verified", "method": "fake", "checked_at": "fixture", "reference": "fixture"}
        fake = Fake()
        self.assertEqual(setup.workflow.observations({"repository": "org/project"}, fake)[0]["status"], "pending")
        self.assertEqual(setup.workflow.observations({"repository": "org/project"}, fake)[0]["status"], "verified")
        self.assertEqual(setup.workflow.observations({"repository": "different/project"}, fake)[0]["status"], "failed")

    def test_dry_run_never_calls_remote_or_bootstrap(self):
        with patch.object(setup, "bootstrap_report", side_effect=AssertionError):
            code, output = self.call("student", "--dry-run", "--smoke")
        self.assertEqual(code, 0, output)
        self.assertFalse((self.root / ".onboarding").exists())

    def test_rejects_unknown_config_and_managed_phase(self):
        config = setup.scaffold(self.root, "org/project")
        config["metadata"]["lintphase"] = {"expected": "draft", "value": "submit"}
        with self.assertRaises(ValueError):
            setup.validate_config(config)

    def test_comment_braces_and_macro_text_are_preserved(self):
        path = self.root / "thesis.tex"
        path.write_text("\\newcommand{\\vikcim}{Old title} % {keep comment}\n")
        config = setup.scaffold(self.root, "org/project")
        config["metadata"]["vikcim"]["value"] = "Path \\ {x}"
        setup.metadata(self.root, config, apply=True)
        self.assertTrue(path.read_text().endswith(" % {keep comment}\n"))
        self.assertEqual(setup.metadata(self.root, config), "")
        config = setup.scaffold(self.root, "org/project")
        config["token"] = "must not survive"
        with self.assertRaises(ValueError):
            setup.validate_config(config)
