import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import project
from ci.config import load_project
from ci.evidence import verify_report
from ci.results import interpret


class ResultTests(unittest.TestCase):
    def test_writing_findings_advisory_and_submit_strict(self):
        native = {"ok": False, "rules": [{"rule": "outline", "status": "fix"}], "findings": [{"msg": "write this"}]}
        self.assertEqual(interpret("writing", 1, native)["gate_outcome"], "pass")
        self.assertEqual(interpret("writing", 1, native, strict=True)["gate_outcome"], "fail")

    def test_lint_crash_invalid_json_and_nonzero_are_not_advice(self):
        native = {"ok": False, "rules": [{"rule": "outline", "status": "error"}], "findings": []}
        self.assertEqual(interpret("writing", 1, native)["gate_outcome"], "fail")
        self.assertEqual(interpret("writing", 2, native)["gate_outcome"], "fail")
        with self.assertRaises(ValueError):
            interpret("writing", 0, {})

    def test_unknown_and_empty_proof_cannot_pass(self):
        native = {"schema": "component-result/v1", "kind": "proof", "outcome": "unknown",
                  "obligations": [{"id": "safety", "outcome": "unknown"}], "bounds": {"depth": 10}, "assumptions": []}
        self.assertEqual(interpret("proof", 0, native)["gate_outcome"], "fail")
        native["outcome"] = "verified"
        with self.assertRaisesRegex(ValueError, "disagrees"):
            interpret("proof", 0, native)
        native["obligations"] = []
        with self.assertRaisesRegex(ValueError, "no declared"):
            interpret("proof", 0, native)

    def test_test_and_benchmark_evidence_is_not_just_exit(self):
        tests = {"schema": "component-result/v1", "kind": "tests", "outcome": "pass", "tests": {"passed":0,"failed":0,"skipped":3}}
        with self.assertRaisesRegex(ValueError, "No executed"):
            interpret("tests", 0, tests)
        benchmark = {"schema": "component-result/v1", "kind": "benchmark", "outcome": "pass", "mode": "smoke", "parameters": {}, "measurements": [{"name":"latency","value":float('nan'),"unit":"s"}]}
        with self.assertRaisesRegex(ValueError, "Invalid benchmark"):
            interpret("benchmark", 0, benchmark)


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = json.loads((Path(__file__).resolve().parents[2] / "project.json").read_text())
        for c in self.config["components"].values():
            c["enabled"] = False
            c["profiles"] = {}
        paper = self.config["components"]["paper"]
        paper["enabled"] = True
        paper["profiles"] = {"ordinary": [{"name":"fixture", "kind":"build", "argv":[sys.executable,"build.py"], "outputs":["built.txt"], "timeout":10}]}
        (self.root / "paper").mkdir()
        (self.root / "paper/build.py").write_text("from pathlib import Path\nPath('built.txt').write_text('tested bytes')\n")
        (self.root / "project.json").write_text(json.dumps(self.config))
        (self.root / ".gitignore").write_text(".project/\npaper/built.txt\n")
        for args in (["init","-q"],["add","project.json","paper/build.py",".gitignore"],["-c","user.email=test@example.com","-c","user.name=Fixture","commit","-qm","fixture"]):
            subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)
        self.args = argparse.Namespace(head=None, base=None, scope="all", component=None, mode="ordinary", profile=None, draft=False)

    def run_report(self, directory="checks"):
        config, sha = load_project(self.root)
        plan = project.make_plan(self.root, config, sha, self.args)
        runtime = {"schema":"runtime-resolution/v1", "source_sha":plan["source"]["tested_sha"], "project_config_sha256":sha, "tools":{"python":sys.version}}
        report = project.check(self.root, config, sha, plan, self.root / ".project" / directory, runtime)
        return report

    def verify(self, directory="checks", **kwargs):
        config, sha = load_project(self.root)
        return verify_report(self.root / ".project" / directory / "report.json", repository=config["repository"],
                             tested_sha=project.git(self.root,"rev-parse","HEAD").strip(), config_sha256=sha,
                             required_components=["paper"], **kwargs)

    def test_real_command_portable_files_and_verifier(self):
        result = self.run_report()
        self.assertEqual(result["gate_outcome"], "pass")
        self.assertEqual(result["components"]["code"]["outcome"], "not_configured")
        self.assertTrue(result["acceptance_eligible"])
        self.verify()
        (self.root / ".project/checks/paper/files/fixture/built.txt").write_text("tampered")
        with self.assertRaisesRegex(ValueError, "size|digest"):
            self.verify()

    def test_missing_output_fails_even_exit_zero(self):
        (self.root / "paper/build.py").write_text("pass\n")
        report = self.run_report()
        self.assertEqual(report["gate_outcome"], "fail")

    def test_timeout_kills_command_and_preserves_log(self):
        config = self.config
        config["components"]["paper"]["profiles"]["ordinary"][0]["timeout"] = 1
        (self.root / "project.json").write_text(json.dumps(config))
        (self.root / "paper/build.py").write_text("import time\nprint('before timeout',flush=True)\ntime.sleep(60)\n")
        report = self.run_report()
        step = report["components"]["paper"]["checks"][0]
        self.assertEqual(step["raw_exit"],124)
        self.assertEqual(step["gate_outcome"],"fail")
        self.assertIn("before timeout", (self.root / ".project/checks/paper/fixture.stdout").read_text())

    def test_draft_and_requested_disabled_are_incomplete(self):
        self.args.draft = True
        self.assertEqual(self.run_report()["gate_outcome"], "incomplete")
        self.args.draft = False
        self.args.component = ["code"]
        self.assertEqual(self.run_report("disabled")["gate_outcome"], "fail")

    def test_incomplete_diff_and_actual_rename(self):
        self.args.scope = "affected"
        self.args.base = "missing-ref"
        config, sha = load_project(self.root)
        plan = project.make_plan(self.root, config, sha, self.args)
        self.assertFalse(plan["diff_complete"])
        self.assertTrue(plan["components"]["paper"]["selected"])
        self.args.base = project.git(self.root, "rev-parse", "HEAD").strip()
        subprocess.run(["git", "-C", str(self.root), "mv", "paper/build.py", "paper/renamed.py"], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c","user.email=test@example.com","-c","user.name=Fixture","commit","-qm","rename"], check=True)
        plan = project.make_plan(self.root, config, sha, self.args)
        self.assertEqual(plan["changed_paths"], ["paper/build.py", "paper/renamed.py"])

    def test_wrong_sha_stale_time_missing_runtime_and_deferred_evidence_rejected(self):
        report = self.run_report()
        with self.assertRaisesRegex(ValueError, "predates"):
            self.verify(after="2999-01-01T00:00:00+00:00")
        path = self.root / ".project/checks/report.json"
        report["runtime"] = None
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, "runtime"):
            self.verify()

    def test_cli_on_fresh_git_fixture(self):
        script = Path(project.__file__)
        result = subprocess.run([sys.executable, str(script), "check", "--root", str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(json.loads(result.stdout)["acceptance_eligible"])


if __name__ == "__main__":
    unittest.main()
