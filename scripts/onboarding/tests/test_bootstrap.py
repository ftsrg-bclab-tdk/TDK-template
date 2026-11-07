import unittest

from scripts.onboarding.bootstrap import check, installation_plan


class BootstrapTest(unittest.TestCase):
    def runner(self, fail=None):
        calls = []
        def run(argv, *, timeout):
            calls.append(argv)
            return {"returncode": 1 if fail and fail(argv) else 0, "stdout": "Python 3.11" if argv[0] == "python3" else "version"}
        return calls, run

    def test_version_only_never_ready_or_runs_container(self):
        calls, run = self.runner()
        self.assertFalse(check(run)["ready"])
        self.assertFalse(any("run" in command for command in calls))

    def test_daemon_failure_blocks_smoke(self):
        calls, run = self.runner(lambda argv: "info" in argv)
        result = check(run, execute_smoke=True)
        self.assertFalse(result["ready"])
        self.assertEqual(result["checks"][-1]["reason"], "daemon_unavailable")
        self.assertFalse(any("run" in command for command in calls))

    def test_mutable_tag_not_accepted_as_resolution(self):
        calls, run = self.runner()
        result = check(run, execute_smoke=True, smoke_image="alpine:latest", smoke_command=["true"])
        self.assertFalse(result["ready"])
        self.assertEqual(result["checks"][-1]["reason"], "resolved_image_required")

    def test_container_failure_is_not_ready(self):
        _, run = self.runner(lambda argv: "run" in argv)
        result = check(run, execute_smoke=True, smoke_image="alpine@sha256:" + "a" * 64, smoke_command=["true"])
        self.assertFalse(result["ready"])

    def test_success_records_runtime_resolution(self):
        calls, run = self.runner()
        image = "alpine@sha256:" + "a" * 64
        result = check(run, execute_smoke=True, smoke_image=image, smoke_command=["true"])
        self.assertTrue(result["ready"])
        self.assertEqual(result["checks"][-1]["image"], image)
        self.assertNotIn("-v", calls[-1])

    def test_os_routes_do_not_choose_desktop(self):
        self.assertFalse(installation_plan("Windows")["supported"])
        self.assertEqual(installation_plan("Linux", wsl=True)["route"], "wsl")
        self.assertTrue(installation_plan("Darwin")["runtime_choice_required"])
        self.assertIn("docker", installation_plan("Linux")["required"])

    def test_python_below_shared_minimum_fails_readiness(self):
        def old(argv, timeout=30):
            return {"returncode": 0, "stdout": "Python 3.10" if argv[0] == "python3" else "version"}
        result = check(old, execute_smoke=True, smoke_image="alpine@sha256:" + "a" * 64, smoke_command=["true"])
        self.assertFalse(result["ready"])
        self.assertEqual(next(row for row in result["checks"] if row["check"] == "python3")["reason"], "python_3_11_required")
