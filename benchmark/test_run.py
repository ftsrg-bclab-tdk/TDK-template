import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from run import measure, payload


class BenchmarkTests(unittest.TestCase):
    def test_deterministic_input_and_exact_units(self):
        clock = iter((0, 1000000000, 2000000000, 5000000000, 6000000000, 8000000000))
        result = measure("smoke", size=100, repetitions=3, seed=7, clock=lambda: next(clock))
        self.assertEqual(result["measurements"], [
            {"name": "median_iteration", "value": 2, "unit": "s"},
            {"name": "median_throughput", "value": 50, "unit": "byte/s"},
        ])
        self.assertEqual(payload(100, 7), (hashlib.sha256(b"7").digest() * 4)[:100])
        self.assertEqual(result["input"]["sha256"], hashlib.sha256(payload(100, 7)).hexdigest())
        self.assertNotEqual(payload(100, 7), payload(100, 8))

    def test_incorrect_workload_and_zero_time_fail(self):
        class WrongDigest:
            def hexdigest(self):
                return "0" * 64
        with self.assertRaisesRegex(ValueError, "correctness"):
            measure("smoke", size=10, implementation=lambda _: WrongDigest())
        with self.assertRaisesRegex(ValueError, "clock"):
            measure("smoke", size=10, clock=lambda: 0)

    def test_invalid_resource_parameters_fail(self):
        for kwargs in ({"size": 0}, {"size": 67108865}, {"repetitions": 0},
                       {"repetitions": 1001}, {"seed": -1}, {"seed": 2**64}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                measure("smoke", **kwargs)

    def test_actual_cli_both_modes_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            for mode in ("smoke", "full"):
                target = Path(tmp) / (mode + ".json")
                argv = [sys.executable, "-B", str(Path(__file__).with_name("run.py")),
                        "--mode", mode, "--bytes", "4096", "--repetitions", "2", "--output", str(target)]
                result = subprocess.run(argv, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                before = target.read_bytes()
                report = json.loads(before)
                self.assertEqual(report["schema"], "component-result/v1")
                self.assertEqual(report["outcome"], "pass")
                self.assertEqual(report["mode"], mode)
                self.assertEqual(len(report["samples_ns"]), 2)
                self.assertTrue(all(m["value"] > 0 for m in report["measurements"]))
                self.assertEqual(len(report["runtime"]["script_sha256"]), 64)
                self.assertNotEqual(subprocess.run(argv, capture_output=True).returncode, 0)
                self.assertEqual(target.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
