#!/usr/bin/env python3
"""A measured SHA-256 example for the template's smoke/full benchmark interface."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time


def payload(size, seed):
    """Generate identical bytes independently of Python's random implementation."""
    block = hashlib.sha256(str(seed).encode("ascii")).digest()
    return (block * ((size + len(block) - 1) // len(block)))[:size]


def measure(mode, size=None, repetitions=None, seed=2026, *,
            clock=time.perf_counter_ns, implementation=hashlib.sha256):
    if mode not in ("smoke", "full"):
        raise ValueError("Mode must be smoke or full")
    size = (256 * 1024 if mode == "smoke" else 16 * 1024 * 1024) if size is None else size
    repetitions = (3 if mode == "smoke" else 15) if repetitions is None else repetitions
    if type(size) is not int or not 1 <= size <= 64 * 1024 * 1024:
        raise ValueError("Input size must be 1..67108864 bytes")
    if type(repetitions) is not int or not 1 <= repetitions <= 1000:
        raise ValueError("Repetitions must be 1..1000")
    if type(seed) is not int or not 0 <= seed < 2**64:
        raise ValueError("Seed must be an unsigned 64-bit integer")
    data = payload(size, seed)
    expected = hashlib.sha256(data).hexdigest()
    if implementation(data).hexdigest() != expected:
        raise ValueError("Workload failed its correctness check")
    samples = []
    for _ in range(repetitions):
        start = clock()
        digest = implementation(data).hexdigest()
        elapsed = clock() - start
        if digest != expected:
            raise ValueError("Measured workload returned an incorrect digest")
        if elapsed <= 0:
            raise ValueError("Measurement clock did not advance")
        samples.append(elapsed)
    median_seconds = statistics.median(samples) / 1_000_000_000
    return {
        "schema": "component-result/v1", "kind": "benchmark", "outcome": "pass",
        "mode": mode,
        "parameters": {"workload": "sha256-example", "bytes_per_iteration": size,
                       "repetitions": repetitions, "warmup_iterations": 1, "seed": seed},
        "measurements": [
            {"name": "median_iteration", "value": median_seconds, "unit": "s"},
            {"name": "median_throughput", "value": size / median_seconds, "unit": "byte/s"},
        ],
        "input": {"generator": "repeat-sha256-of-decimal-seed/v1", "sha256": expected},
        "samples_ns": samples,
        "runtime": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                    "system": platform.system(), "release": platform.release(),
                    "architecture": platform.machine(), "processor": platform.processor() or None,
                    "logical_cpus": os.cpu_count(), "clock": "perf_counter_ns",
                    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "scope": "template example; validates execution/reporting, not research performance",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--bytes", type=int, dest="size")
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output", type=Path, required=True,
                        help="New result file; existing evidence is never overwritten")
    args = parser.parse_args(argv)
    try:
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Output already exists; choose a new evidence path")
        result = measure(args.mode, args.size, args.repetitions, args.seed)
        result["command"] = ["python3", "run.py", *(argv if argv is not None else sys.argv[1:])]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
        print(f"{args.mode}: {result['parameters']['repetitions']} measured iterations; {args.output}")
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
