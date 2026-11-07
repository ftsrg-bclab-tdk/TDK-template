import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pilot = module("pilot")
guest = module("guest")
NAME = "bme-pilot-" + "a" * 32


class RegistrationTests(unittest.TestCase):
    def test_bad_repository_group_and_label_rejected(self):
        for repo, group, name in [("a/b/c", 1, NAME), ("a/b;echo x", 1, NAME),
                                  ("a/b", 0, NAME), ("a/b", 1, "ubuntu-latest")]:
            with self.subTest(repo=repo, group=group, name=name), self.assertRaises(ValueError):
                pilot.request(repo, group, name)

    def test_dry_run_never_calls_github(self):
        with patch.object(pilot.subprocess, "run") as run, patch("sys.argv", [
            "pilot.py", "--repo", "a/b", "--runner-group-id", "1"]), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(pilot.main(), 0)
            self.assertEqual(json.loads(output.getvalue())["repository"], "a/b")
            run.assert_not_called()

    def test_apply_requires_explicit_pilot_gate(self):
        with patch.object(pilot.subprocess, "run") as run, patch("sys.argv", [
            "pilot.py", "--repo", "a/b", "--runner-group-id", "1", "--apply"]), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(pilot.main(), 1)
            run.assert_not_called()

    def test_real_cli_with_fake_github_keeps_credential_out_of_logs_and_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake = tmp / "gh"
            fake.write_text("#!/usr/bin/env python3\nimport json,sys\n"
                            "assert sys.argv[1:7] == ['api','--hostname','github.com','--method','POST',"
                            "'repos/a/b/actions/runners/generate-jitconfig']\n"
                            "p=json.load(sys.stdin)\n"
                            "assert p['labels'][-1] == p['name']\n"
                            "assert p['work_folder'] == '_work'\n"
                            "print(json.dumps({'runner':{'id':42},'encoded_jit_config':'c2VjcmV0'}))\n")
            fake.chmod(0o700)
            dest = tmp / "jit"
            command = ["python3", str(ROOT / "pilot.py"), "--repo", "a/b",
                       "--runner-group-id", "1", "--name", NAME,
                       "--apply", "--isolated-disposable-pilot", "--output", str(dest)]
            result = subprocess.run(command, text=True, capture_output=True,
                                    env={**os.environ, "PATH": str(tmp) + ":" + os.environ["PATH"]})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(dest.read_text(), "c2VjcmV0\n")
            self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("c2VjcmV0", result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["runner_id"], 42)
            # Repeating cannot overwrite credentials or register another runner.
            repeated = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(repeated.returncode, 1)
            self.assertEqual(dest.read_text(), "c2VjcmV0\n")

    def test_existing_file_or_symlink_refused_before_api(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(pilot.subprocess, "run") as run:
            dest = Path(tmp) / "jit"
            dest.symlink_to(Path(tmp) / "absent")
            with self.assertRaises(FileExistsError):
                pilot.create("a/b", pilot.request("a/b", 1, NAME), dest)
            run.assert_not_called()

    def test_failed_response_is_not_echoed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(pilot.subprocess, "run",
                return_value=subprocess.CompletedProcess([], 1, "SECRET", "SECRET")):
            with self.assertRaises(RuntimeError) as error:
                pilot.create("a/b", pilot.request("a/b", 1, NAME), Path(tmp) / "jit")
            self.assertNotIn("SECRET", str(error.exception))


class GuestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        state = Path(self.tmp.name) / "state"
        state.mkdir()
        runtime = Path(self.tmp.name) / "run"
        for attr, value in [("STATE", state), ("RUNTIME", runtime)]:
            p = patch.object(guest, attr, value)
            p.start()
            self.addCleanup(p.stop)

    def mocks(self):
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(guest.os, "geteuid", return_value=0))
        stack.enter_context(patch.object(guest.os, "chown"))
        stack.enter_context(patch.object(guest.os, "fchown"))
        stack.enter_context(patch.object(guest.pwd, "getpwnam", return_value=type(
            "User", (), {"pw_uid": 1001, "pw_gid": 1001})()))
        return stack

    def test_nonroot_cannot_arm(self):
        with patch.object(guest.os, "geteuid", return_value=1001):
            with self.assertRaises(ValueError):
                guest.arm(io.StringIO("c2VjcmV0"))
            self.assertFalse((guest.STATE / "consumed").exists())

    def test_root_cannot_run_job(self):
        with patch.object(guest.os, "geteuid", return_value=0):
            with self.assertRaises(ValueError):
                guest.run()

    def test_one_use_even_across_restart(self):
        with self.mocks(), patch.object(guest.subprocess, "run") as run:
            guest.arm(io.StringIO("c2VjcmV0\n"))
            self.assertEqual((guest.RUNTIME / "jit").read_text(), "c2VjcmV0")
            self.assertEqual((guest.RUNTIME / "jit").stat().st_mode & 0o777, 0o600)
            run.assert_called_once_with(["systemctl", "start", "tdk-runner.service"], check=True)
            with self.assertRaises(FileExistsError):
                guest.arm(io.StringIO("bmV3"))
            self.assertEqual(run.call_count, 1)

    def test_invalid_or_oversized_input_consumes_vm_without_starting(self):
        for value in ["", "bad; shell", "x" * (guest.MAX_JIT_SIZE + 1)]:
            with self.subTest(value=value[:20]), self.mocks(), \
                    patch.object(guest.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    guest.arm(io.StringIO(value))
                self.assertTrue((guest.STATE / "consumed").is_dir())
                run.assert_not_called()
                (guest.STATE / "consumed").rmdir()

    def test_start_failure_does_not_allow_reuse(self):
        with self.mocks(), patch.object(guest.subprocess, "run", side_effect=OSError):
            with self.assertRaises(OSError):
                guest.arm(io.StringIO("c2VjcmV0"))
            with self.assertRaises(FileExistsError):
                guest.arm(io.StringIO("c2VjcmV0"))

    def test_runner_consumes_file_and_drops_inherited_secrets(self):
        guest.RUNTIME.mkdir()
        (guest.RUNTIME / "jit").write_text("c2VjcmV0")
        with patch.object(guest.os, "geteuid", return_value=1001), \
                patch.object(guest.os, "chdir"), patch.object(guest.os, "execve") as execute, \
                patch.dict(os.environ, {"GH_TOKEN": "ADMIN", "OS_PASSWORD": "CLOUD"}):
            guest.run()
            self.assertFalse((guest.RUNTIME / "jit").exists())
            _, argv, env = execute.call_args.args
            self.assertEqual(argv, ["run.sh", "--jitconfig", "c2VjcmV0"])
            self.assertNotIn("GH_TOKEN", env)
            self.assertNotIn("OS_PASSWORD", env)


if __name__ == "__main__":
    unittest.main()
