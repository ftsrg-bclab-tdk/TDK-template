#!/usr/bin/env python3
"""Run a deliberately narrow TLC finite-state invariant profile with real evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "scripts"))
from ci.config import inside
from ci.process import execute


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def configuration(text):
    """Reject unsupported cfg constructs instead of hiding constraints/obligations.

    V1: INIT, NEXT, integer CONSTANT assignments, named state INVARIANTs.
    Richer TLC configurations remain tool-native, not claimed supported here.
    """
    constants, obligations, operators = {}, [], {}
    for raw in text.splitlines():
        line = raw.split(r"\*", 1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r"CONSTANTS?\s+([A-Za-z_]\w*)\s*=\s*(-?\d+)", line)
        if match:
            name, value = match.groups()
            if name in constants:
                raise ValueError("Duplicate constant")
            constants[name] = int(value)
            continue
        match = re.fullmatch(r"(INIT|NEXT)\s+([A-Za-z_]\w*)", line)
        if match:
            kind, name = match.groups()
            if kind in operators:
                raise ValueError("Duplicate model operator")
            operators[kind] = name
            continue
        match = re.fullmatch(r"INVARIANTS?\s+([A-Za-z_]\w*(?:\s+[A-Za-z_]\w*)*)", line)
        if match:
            obligations.extend(match[1].split())
            continue
        raise ValueError("Unsupported TLC config statement: " + line)
    if set(operators) != {"INIT", "NEXT"} or not obligations or len(obligations) != len(set(obligations)):
        raise ValueError("Declare INIT, NEXT and unique nonempty INVARIANT obligations")
    return constants, obligations


def resolve_latest():
    """Resolve GitHub's latest stable release once per invocation; never fall back."""
    response = subprocess.run(["gh", "api", "repos/tlaplus/tlaplus/releases/latest"],
                              capture_output=True, text=True, timeout=30, check=True)
    release = json.loads(response.stdout)
    assets = [a for a in release["assets"] if a["name"] == "tla2tools.jar"]
    if (release.get("draft") or release.get("prerelease") or len(assets) != 1
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", release["tag_name"])
            or not 0 < assets[0]["size"] <= 64 * 1024 * 1024):
        raise ValueError("Unexpected latest TLC release")
    tools = inside(ROOT, ".tools")
    tools.mkdir(exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="tlc-", dir=tools))
    try:
        subprocess.run(["gh", "release", "download", release["tag_name"], "--repo", "tlaplus/tlaplus",
                        "--pattern", "tla2tools.jar", "--dir", str(destination)],
                       capture_output=True, timeout=120, check=True)
        jar = destination / "tla2tools.jar"
        actual = digest(jar)
        expected = assets[0].get("digest")
        if jar.stat().st_size != assets[0]["size"] or not zipfile.is_zipfile(jar):
            raise ValueError("Invalid TLC archive/size")
        if expected is not None and expected != "sha256:" + actual:
            raise ValueError("TLC release asset digest mismatch")
        return jar, {"requested": "tlaplus/tlaplus latest stable", "tag": release["tag_name"],
                     "release_id": release["id"], "asset_id": assets[0]["id"], "sha256": actual,
                     "publisher_digest": expected, "resolved_at": datetime.now(timezone.utc).isoformat()}
    except BaseException:
        shutil.rmtree(destination)
        raise


def outcome(returncode, output, obligations):
    violations = set(re.findall(r"Error: Invariant ([A-Za-z_]\w*) is violated\.", output))
    count = re.search(r"(\d+) distinct states found, (\d+) states left on queue\.", output)
    complete = (returncode == 0 and "Model checking completed. No error has been found." in output
                and "Error:" not in output and count and int(count[1]) > 0 and int(count[2]) == 0)
    if violations and violations <= set(obligations) and returncode not in (0, 124, 127, 130):
        rows = [{"id": name, "outcome": "violated" if name in violations else "unknown"} for name in obligations]
    else:
        rows = [{"id": name, "outcome": "verified" if complete else "unknown"} for name in obligations]
    values = {r["outcome"] for r in rows}
    summary = "violated" if "violated" in values else "unknown" if "unknown" in values else "verified"
    return summary, rows, int(count[1]) if count else None


def check(jar, tool, model_path, config_path, logs, timeout):
    model, cfg = inside(ROOT, model_path), inside(ROOT, config_path)
    if model.suffix != ".tla" or not re.fullmatch(r"[A-Za-z_]\w*", model.stem) or cfg.suffix != ".cfg":
        raise ValueError("Expected a named .tla module and .cfg file")
    constants, obligations = configuration(cfg.read_text())
    sources = sorted(model.parent.glob("*.tla"))
    if not model.is_file() or any(p.is_symlink() or not p.is_file() for p in sources):
        raise ValueError("Model sources must be regular files")
    inputs = {str(p.relative_to(ROOT)): digest(p) for p in [*sources, cfg]}
    java = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=10, check=True)
    with tempfile.TemporaryDirectory(prefix="tdk-tlc-model-") as tmp:
        for p in sources:
            shutil.copyfile(p, Path(tmp) / p.name)
        shutil.copyfile(cfg, Path(tmp) / "model.cfg")
        argv = ["java", "-Xmx512m", "-XX:+UseParallelGC", "-cp", str(jar.resolve()), "tlc2.TLC",
                "-workers", "1", "-seed", "1", "-fp", "0", "-config", "model.cfg", model.stem]
        raw = execute(argv, tmp, logs, model.stem, timeout)
    output = Path(raw["stdout"]).read_text(errors="replace") + Path(raw["stderr"]).read_text(errors="replace")
    result, rows, states = outcome(raw["raw_exit"], output, obligations)
    if inputs != {str(p.relative_to(ROOT)): digest(p) for p in [*sources, cfg]}:
        raise ValueError("Model inputs changed while checking")
    return {"schema": "component-result/v1", "kind": "proof", "outcome": result,
            "profile": "tlaplus-tlc", "method": "finite-state invariant model checking",
            "obligations": rows, "bounds": {"constants": constants, "distinct_states": states},
            "assumptions": ["The model represents the intended system.",
                            "Only this finite instance and declared state invariants are checked.",
                            "TLC uses state fingerprints; retain its collision estimate in the logs."],
            "inputs": inputs, "runtime": {"tlc": tool, "java": (java.stdout + java.stderr).strip()},
            "native_execution": raw, "completed_at": datetime.now(timezone.utc).isoformat()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("check", "smoke"))
    parser.add_argument("--model")
    parser.add_argument("--config")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--output", required=True, help="New result path relative to proof/")
    args = parser.parse_args(argv)
    jar = None
    try:
        if not 1 <= args.timeout <= 3600:
            raise ValueError("Timeout must be 1..3600 seconds")
        output = inside(ROOT, args.output)
        logs = inside(ROOT, args.output + ".logs")
        if output.exists() or logs.exists():
            raise ValueError("Evidence already exists; select a new output path")
        if args.operation == "check" and (not args.model or not args.config):
            raise ValueError("check requires --model and --config")
        jar, tool = resolve_latest()
        if args.operation == "smoke":
            positive = check(jar, tool, "examples/tlc/Counter.tla", "examples/tlc/Counter.cfg", logs, args.timeout)
            negative = check(jar, tool, "examples/tlc/BrokenCounter.tla", "examples/tlc/BrokenCounter.cfg", logs, args.timeout)
            passed = int(positive["outcome"] == "verified") + int(negative["outcome"] == "violated")
            result = {"schema": "component-result/v1", "kind": "tests", "outcome": "pass" if passed == 2 else "violated",
                      "tests": {"passed": passed, "failed": 2 - passed, "skipped": 0},
                      "examples": [positive, negative], "scope": "adapter acceptance, not project verification"}
        else:
            result = check(jar, tool, args.model, args.config, logs, args.timeout)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x") as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
        print(result["outcome"] + ": " + str(output))
        return 0 if result["outcome"] in ("pass", "verified") else 1
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print("TLC adapter failed: " + str(exc), file=sys.stderr)
        return 2
    finally:
        if jar is not None:
            shutil.rmtree(jar.parent)


if __name__ == "__main__":
    raise SystemExit(main())
