import base64
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPTS))
from onboarding import platforms, provision, workspace, checks
from ci.config import load_project
import project

spec = importlib.util.spec_from_file_location("setup_adapters", SCRIPTS / "setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class FakeGithub:
    def __init__(self, config):
        self.source = copy.deepcopy(config)
        self.target = None
        self.config = None
        self.calls = []
        self.interrupt = False
        self.two_factor = True

    def request(self, method, endpoint, body=None):
        self.calls.append((method, endpoint, body))
        if endpoint == "user":
            return 200, {"login": "advisor", "id": 1, "two_factor_authentication": self.two_factor}
        if "/memberships/" in endpoint:
            return 200, {"state": "active", "role": "admin"}
        if endpoint == "orgs/FTSRG-BCLab-TDK":
            return 200, {"two_factor_requirement_enabled": self.two_factor}
        if endpoint == "repos/FTSRG-BCLab-TDK/TDK-template":
            return 200, {"is_template": True}
        if endpoint.endswith("/generate"):
            self.target = {"id": 2, "full_name": "FTSRG-BCLab-TDK/" + body["name"], "private": body["private"],
                           "owner": {"login": "FTSRG-BCLab-TDK"},
                           "template_repository": {"full_name": "FTSRG-BCLab-TDK/TDK-template"}}
            self.config = copy.deepcopy(self.source)
            if self.interrupt:
                self.interrupt = False
                raise TimeoutError("Response lost after server created repository")
            return 201, self.target
        if endpoint.endswith("/contents/project.json"):
            if method == "PUT":
                self.config = json.loads(base64.b64decode(body["content"]))
            return 200, {"encoding": "base64", "sha": "blob-sha", "content": base64.b64encode(json.dumps(self.config).encode()).decode()}
        return (200, self.target) if self.target else (404, {})


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = json.loads((SCRIPTS.parent / "project.json").read_text())

    def test_install_plan_and_dry_run_never_execute(self):
        plan = platforms.plan({"system": "Linux", "distro": "ubuntu", "wsl": False}, "engine", lambda _: None)
        calls = []
        result = platforms.install(plan, lambda *a, **k: calls.append(a))
        self.assertEqual(result["status"], "planned")
        self.assertFalse(calls)
        self.assertIn("docker.io", plan["commands"][-1])
        self.assertFalse(any("upgrade" in cmd for cmd in plan["commands"]))

    def test_install_failure_stops_before_later_commands(self):
        plan = {"commands": [["one"], ["two"]], "manual": []}
        calls = []
        def run(argv, timeout):
            calls.append(argv)
            return {"returncode": 1}
        self.assertEqual(platforms.install(plan, run, execute=True)["status"], "failed")
        self.assertEqual(calls, [["one"]])

    def test_wsl_desktop_does_not_install_competing_engine(self):
        plan = platforms.plan({"system": "Linux", "distro": "ubuntu", "wsl": True}, "desktop", lambda _: None)
        self.assertNotIn("docker.io", plan["commands"][-1])
        self.assertTrue(any("WSL" in step for step in plan["manual"]))

    def test_macos_runtime_is_explicit(self):
        facts = {"system": "Darwin", "distro": "", "wsl": False}
        plan = platforms.plan(facts, "desktop", lambda tool: "/brew" if tool == "brew" else None)
        self.assertIn(["brew", "install", "--cask", "docker-desktop"], plan["commands"])
        with self.assertRaises(ValueError):
            platforms.plan(facts, "engine")

    def test_workspace_idempotence_and_user_conflict(self):
        (self.root / "AGENTS.md").write_text("Keep these instructions")
        (self.root / "paper").mkdir()
        proposed = workspace.prepare(self.root, self.config)
        receipt = workspace.apply(proposed, setup.atomic_json)
        self.assertFalse(workspace.prepare(self.root, self.config, receipt)["changed"])
        (self.root / "tdk.code-workspace").write_text("User preferences")
        with self.assertRaises(ValueError):
            workspace.prepare(self.root, self.config, receipt)
        self.assertEqual((self.root / "AGENTS.md").read_text(), "Keep these instructions")

    def test_workspace_concurrent_edit_blocks_application(self):
        (self.root / "AGENTS.md").write_text("Instructions")
        plan = workspace.prepare(self.root, self.config)
        (self.root / "tdk.code-workspace").write_text("New user file")
        with self.assertRaises(ValueError):
            workspace.apply(plan, setup.atomic_json)

    def test_provision_preview_never_calls_api(self):
        fake = FakeGithub(self.config)
        desired = copy.deepcopy(self.config)
        desired["repository"] = "FTSRG-BCLab-TDK/onboarding-pilot-example"
        result = provision.provision_pilot(fake, desired, "FTSRG-BCLab-TDK/TDK-template", self.root)
        self.assertEqual(result["role"], "project")
        self.assertFalse(fake.calls)
        with self.assertRaises(ValueError):
            provision.provision_pilot(fake, self.config, "FTSRG-BCLab-TDK/TDK-template", self.root, execute=True)
        self.assertFalse(fake.calls)

    def test_provision_retry_observes_created_repo_and_initializes_project_role(self):
        fake = FakeGithub(self.config)
        fake.interrupt = True
        desired = copy.deepcopy(self.config)
        desired["repository"] = "FTSRG-BCLab-TDK/onboarding-pilot-example"
        with self.assertRaises(TimeoutError):
            provision.provision_pilot(fake, desired, "FTSRG-BCLab-TDK/TDK-template", self.root, execute=True)
        result = provision.provision_pilot(fake, desired, "FTSRG-BCLab-TDK/TDK-template", self.root, execute=True)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(fake.config["role"], "project")
        self.assertEqual(fake.config["repository"], desired["repository"])
        self.assertEqual(sum(method == "POST" for method, _, _ in fake.calls), 1)
        self.assertEqual(fake.config["components"], self.config["components"])
        provision.provision_pilot(fake, desired, "FTSRG-BCLab-TDK/TDK-template", self.root, execute=True)
        self.assertEqual(sum(method == "PUT" for method, _, _ in fake.calls), 1)

    def test_provision_2fa_and_remote_edit_fail_closed(self):
        fake = FakeGithub(self.config)
        desired = copy.deepcopy(self.config)
        desired["repository"] = "FTSRG-BCLab-TDK/onboarding-pilot-example"
        fake.two_factor = False
        with self.assertRaises(ValueError):
            provision.provision_pilot(fake, desired, "FTSRG-BCLab-TDK/TDK-template", self.root, execute=True)
        self.assertFalse(any(m != "GET" for m, _, _ in fake.calls))
        fake.two_factor = True
        provision.provision_pilot(fake, desired, "FTSRG-BCLab-TDK/TDK-template", self.root, execute=True)
        fake.config["metadata"] = {"vikcim": {"expected": "Old", "value": "Student"}}
        before = len(fake.calls)
        with self.assertRaises(ValueError):
            provision.provision_pilot(fake, desired, "FTSRG-BCLab-TDK/TDK-template", self.root, execute=True)
        self.assertFalse(any(m != "GET" for m, _, _ in fake.calls[before:]))

    def test_2fa_missing_field_is_not_verified(self):
        class Remote:
            def request(self, *args):
                return 200, {"login": "student"}
        self.assertEqual(provision.github_account(Remote(), "student")["two_factor"], "unavailable")
        with self.assertRaises(ValueError):
            provision.github_account(Remote(), "other")

    def test_gh_http_error_is_not_missing(self):
        fake = subprocess.CompletedProcess([], 1, "HTTP/2.0 403 Forbidden\nContent-Type: application/json\n\n{\"message\":\"private\"}", "")
        with patch.object(provision.subprocess, "run", return_value=fake):
            with self.assertRaisesRegex(ValueError, "403"):
                provision.Gh().request("GET", "user")

    def test_gh_status_and_body_parser(self):
        fake = subprocess.CompletedProcess([], 0, 'HTTP/2.0 200 OK\r\nContent-Type: application/json\r\n\r\n{"login":"student"}', "")
        with patch.object(provision.subprocess, "run", return_value=fake):
            self.assertEqual(provision.Gh().request("GET", "user"), (200, {"login": "student"}))

    def test_invitation_requires_enforcement_and_preserves_pending_until_acceptance(self):
        class Remote:
            enforced = None
            invited = False
            accepted = False
            writes = 0
            def request(self, method, endpoint, body=None):
                if endpoint == "user":
                    return 200, {"login": "advisor"}
                if endpoint.endswith("/memberships/advisor"):
                    return 200, {"role": "admin", "state": "active"}
                if endpoint.endswith("/memberships/student"):
                    return 404, {}
                if endpoint == "orgs/FTSRG-BCLab-TDK":
                    return 200, {"two_factor_requirement_enabled": self.enforced}
                if endpoint.endswith("/permission"):
                    if self.accepted:
                        return 200, {"user": {"login": "student"}, "role_name": "write"}
                    return 404, {}
                if "/invitations?" in endpoint:
                    return 200, ([{"id": 7, "invitee": {"login": "student"}, "permissions": "write"}] if self.invited else [])
                if method == "PUT":
                    self.writes += 1
                    self.invited = True
                    return 201, {"id": 7}
                return 200, {"full_name": "FTSRG-BCLab-TDK/onboarding-pilot-demo", "private": True, "permissions": {"admin": True}}
        remote = Remote()
        repo = "FTSRG-BCLab-TDK/onboarding-pilot-demo"
        for state in (None, False):
            remote.enforced = state
            with self.assertRaisesRegex(ValueError, "2FA enforcement"):
                provision.invite_pilot(remote, repo, "student", execute=True)
            self.assertEqual(remote.writes, 0)
        remote.enforced = True
        self.assertEqual(provision.invite_pilot(remote, repo, "student", execute=True)["status"], "pending")
        self.assertEqual(provision.invite_pilot(remote, repo, "student", execute=True)["status"], "pending")
        self.assertEqual(remote.writes, 1)
        remote.accepted = True
        self.assertEqual(provision.invite_pilot(remote, repo, "student", execute=True)["status"], "accepted")
        self.assertEqual(remote.writes, 1)

    def test_real_dispatcher_receipt_ingestion_and_file_tamper(self):
        for component in self.config["components"].values():
            component.update(enabled=False, profiles={})
        self.config["repository"] = "org/project"
        self.config["components"]["paper"].update(enabled=True, profiles={"ordinary": [{
            "name": "fixture", "kind": "build", "argv": [sys.executable, "build.py"],
            "timeout": 10, "outputs": ["built.txt"]}]})
        (self.root / "paper").mkdir()
        (self.root / "paper/build.py").write_text("from pathlib import Path\nPath('built.txt').write_text('real output')\n")
        (self.root / "project.json").write_text(json.dumps(self.config))
        (self.root / ".gitignore").write_text(".project/\npaper/built.txt\n")
        for args in (["init", "-q"], ["add", "project.json", "paper/build.py", ".gitignore"],
                     ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Fixture"]):
            subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)
        config, digest = load_project(self.root)
        args = argparse.Namespace(head=None, base=None, scope="all", component=None, mode="ordinary", profile=None, draft=False)
        plan = project.make_plan(self.root, config, digest, args)
        sha = plan["source"]["tested_sha"]
        runtime = {"schema": "runtime-resolution/v1", "source_sha": sha, "project_config_sha256": digest,
                   "tools": {"python": sys.version}}
        output = self.root / ".project/checks"
        project.check(self.root, config, digest, plan, output, runtime)
        result = checks.ingest(output / "report.json", config, digest, sha)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["roundtrip_and_clone"], "pending")
        self.assertFalse(result["onboarding_ready"])
        with self.assertRaises(ValueError):
            checks.ingest(output / "report.json", config, "wrong-config", sha)
        (output / "paper/files/fixture/built.txt").write_text("tampered")
        with self.assertRaises(ValueError):
            checks.ingest(output / "report.json", config, digest, sha)
