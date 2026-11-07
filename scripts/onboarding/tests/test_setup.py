import hashlib
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
        self.config = json.loads((SCRIPTS.parent / "project.json").read_text())
        self.config.update(repository=None, paper_main="thesis.tex", metadata={})
        (self.root / "project.json").write_text(json.dumps(self.config))
        self.git("add", ".gitignore", "thesis.tex", "project.json")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Fixture")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.DEVNULL)

    def call(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = setup.main([*args, "--root", str(self.root)])
        return code, output.getvalue()

    def test_init_preserves_raw_tex_until_explicit_replacement(self):
        path = self.root / "thesis.tex"
        path.write_text(r"\newcommand{\vikcim}{A \& B}" + "\n")
        before = path.read_bytes()
        code, output = self.call("advisor", "--init-config", "org/project", "--apply-metadata")
        self.assertEqual(code, 0, output)
        self.assertEqual(path.read_bytes(), before)
        config = json.loads((self.root / "project.json").read_text())
        config["metadata"]["vikcim"]["value"] = "New & title"
        setup.metadata(self.root, config, apply=True)
        self.assertIn(r"{New \& title}", path.read_text())

    def test_advisor_dry_run_has_no_writes(self):
        before = self.git("status", "--porcelain")
        code, output = self.call("advisor", "--init-config", "org/project", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertEqual(before, self.git("status", "--porcelain"))
        self.assertFalse((self.root / ".onboarding").exists())
        self.assertIsNone(json.loads((self.root / "project.json").read_text())["repository"])

    def test_advisor_uses_current_draft_name(self):
        self.git("mv", "thesis.tex", "draft.tex")
        code, output = self.call("advisor", "--init-config", "org/project", "--paper-source", "draft.tex", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn('"paper_main": "draft.tex"', output)
        self.assertIsNone(json.loads((self.root / "project.json").read_text())["repository"])

    def test_advisor_uses_monorepo_draft_source(self):
        (self.root / "paper").mkdir()
        self.git("mv", "thesis.tex", "paper/draft.tex")
        code, output = self.call("advisor", "--init-config", "org/project", "--paper-source", "paper/draft.tex", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn('"paper_main": "paper/draft.tex"', output)
        self.assertFalse((self.root / ".onboarding").exists())

    def test_init_preserves_ci_fields_and_replaces_template_identity(self):
        self.config["repository"] = "FTSRG-BCLab-TDK/TDK-template"
        (self.root / "project.json").write_text(json.dumps(self.config))
        code, output = self.call("advisor", "--init-config", "org/student-project")
        self.assertEqual(code, 0, output)
        result, digest = setup.load_project(self.root)
        for field in ("components", "paper_entrypoints"):
            self.assertEqual(result[field], self.config[field])
        self.assertEqual(result["role"], "project")
        self.assertEqual(result["repository"], "org/student-project")
        self.assertEqual(digest, hashlib.sha256((self.root / "project.json").read_bytes()).hexdigest())
        self.assertFalse((self.root / "onboarding.json").exists())

    def test_init_canonical_identity_preserves_template_role(self):
        result = setup.scaffold(self.root, "FTSRG-BCLab-TDK/TDK-template", self.config)
        self.assertEqual(result["role"], "template")

    def test_student_identity_dry_run_previews_project_role_without_mutation(self):
        before = (self.root / "project.json").read_bytes()
        code, output = self.call("advisor", "--init-config", "org/student-project", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn('"role": "project"', output)
        self.assertEqual((self.root / "project.json").read_bytes(), before)
        self.assertEqual(self.config["role"], "template")

    def test_canonical_paper_source_never_falls_back_to_legacy_or_proxy(self):
        self.config["paper_main"] = "paper/draft.tex"
        (self.root / "project.json").write_text(json.dumps(self.config))
        code, output = self.call("advisor", "--init-config", "org/project", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("Configured paper source", output)
        (self.root / "paper").mkdir()
        self.git("mv", "thesis.tex", "paper/draft.tex")
        (self.root / "paper-draft.tex").write_text("PROXY MUST REMAIN UNCHANGED")
        code, output = self.call("advisor", "--init-config", "org/project", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertEqual((self.root / "paper-draft.tex").read_text(), "PROXY MUST REMAIN UNCHANGED")

    def test_exact_raw_digest_and_config_change_invalidates_evidence(self):
        with patch.object(setup, "bootstrap_report", return_value={"ready": False}):
            self.assertEqual(self.call("student", "--skip-accounts", "--check-bootstrap")[0], 1)
        evidence = json.loads((self.root / ".onboarding/bootstrap.json").read_text())
        path = self.root / "project.json"
        self.assertEqual(evidence["config_digest"], hashlib.sha256(path.read_bytes()).hexdigest())
        path.write_text(path.read_text() + "\n")
        code, output = self.call("status")
        self.assertEqual(code, 0, output)
        self.assertIn("Saved bootstrap: stale", output)

    def test_initialization_does_not_reset_metadata_conflict(self):
        self.call("advisor", "--init-config", "org/project")
        path = self.root / "thesis.tex"
        path.write_text(path.read_text().replace("Old title", "Student title"))
        before = (self.root / "project.json").read_bytes()
        code, output = self.call("advisor", "--init-config", "org/renamed")
        self.assertEqual(code, 2)
        self.assertIn("Metadata conflict", output)
        self.assertEqual((self.root / "project.json").read_bytes(), before)

    def test_explicit_config_uses_same_loader_without_default_identity(self):
        self.git("mv", "project.json", "other.json")
        code, output = self.call("advisor", "--config", "other.json", "--init-config", "org/project", "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertFalse((self.root / "project.json").exists())

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
        config_path = self.root / "project.json"
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
            return {"returncode": 0, "stdout": "Python 3.11" if argv[0] == "python3" else "version"}
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
        unset = setup.workflow.observations({"repository": None}, fake)
        self.assertEqual(fake.count, 0)
        self.assertTrue(all(item["status"] == "pending" for item in unset))
        self.assertEqual(setup.workflow.observations({"repository": "org/project"}, fake)[0]["status"], "pending")
        self.assertEqual(setup.workflow.observations({"repository": "org/project"}, fake)[0]["status"], "verified")
        self.assertEqual(setup.workflow.observations({"repository": "different/project"}, fake)[0]["status"], "failed")

    def test_dry_run_never_calls_remote_or_bootstrap(self):
        with patch.object(setup, "bootstrap_report", side_effect=AssertionError):
            code, output = self.call("student", "--dry-run", "--smoke")
        self.assertEqual(code, 0, output)
        self.assertFalse((self.root / ".onboarding").exists())

    def test_install_and_github_flags_dry_run_do_not_execute(self):
        with patch.object(setup, "run_install", side_effect=AssertionError), patch.object(setup.provision.Gh, "request", side_effect=AssertionError):
            code, output = self.call("student", "--dry-run", "--skip-accounts", "--install-tools", "--github-account", "--inspect-repository")
        self.assertEqual(code, 0, output)
        self.assertFalse((self.root / ".onboarding").exists())

    def test_rejects_unknown_config_and_managed_phase(self):
        config = setup.scaffold(self.root, "org/project", self.config)
        config["metadata"]["lintphase"] = {"expected": "draft", "value": "submit"}
        with self.assertRaises(ValueError):
            setup.validate_project(config, self.root)

    def test_comment_braces_and_macro_text_are_preserved(self):
        path = self.root / "thesis.tex"
        path.write_text("\\newcommand{\\vikcim}{Old title} % {keep comment}\n")
        config = setup.scaffold(self.root, "org/project", self.config)
        config["metadata"]["vikcim"]["value"] = "Path \\ {x}"
        setup.metadata(self.root, config, apply=True)
        self.assertTrue(path.read_text().endswith(" % {keep comment}\n"))
        self.assertEqual(setup.metadata(self.root, config), "")
        config = setup.scaffold(self.root, "org/project", self.config)
        config["token"] = "must not survive"
        with self.assertRaises(ValueError):
            setup.validate_project(config, self.root)
