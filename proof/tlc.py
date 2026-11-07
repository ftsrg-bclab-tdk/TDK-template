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
import urllib.request
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
    request = urllib.request.Request("https://api.github.com/repos/tlaplus/tlaplus/releases/latest",
                                     headers={"Accept": "application/vnd.github+json", "User-Agent": "tdk-tlc"})
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    assets = [a for a in release["assets"] if a["name"] == "tla2tools.jar"]
    if (release.get("draft") or release.get("prerelease") or len(assets) != 1
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", release["tag_name"])
            or not 0 < assets[0]["size"] <= 64 * 1024 * 1024):
        raise ValueError("Unexpected latest TLC release")
    tools = inside(ROOT, ".tools")
    tools.mkdir(exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="tlc-", dir=tools))
    try:
        jar = destination / "tla2tools.jar"
        url = assets[0]["browser_download_url"]
        if not url.startswith("https://github.com/tlaplus/tlaplus/releases/download/"):
            raise ValueError("Unexpected TLC download URL")
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tdk-tlc"}), timeout=120) as response, jar.open("xb") as stream:
            remaining = 64 * 1024 * 1024
            while chunk := response.read(min(65536, remaining + 1)):
                remaining -= len(chunk)
                if remaining < 0:
                    raise ValueError("TLC archive exceeds limit")
                stream.write(chunk)
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
    violations = set(re.findall(r"Error: Invariant ([A-Za-z_]\w*) is violated(?:\.| by the initial state:)", output))
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


def resolve_java():
    executable = Path(shutil.which("java") or "").resolve()
    if not executable.is_file():
        raise ValueError("Java executable missing")
    version = subprocess.run([str(executable), "-version"], capture_output=True, text=True, timeout=10, check=True)
    return {"executable": str(executable), "sha256": digest(executable), "version": (version.stdout + version.stderr).strip()}


def resolve_runtime():
    jar, tool = resolve_latest()
    try:
        return {"tlc": dict(tool, jar=str(jar.resolve())), "java": resolve_java()}
    except BaseException:
        shutil.rmtree(jar.parent)
        raise


def checked_runtime(runtime):
    jar, java = runtime["tlc"], runtime["java"]
    if digest(jar["jar"]) != jar["sha256"] or digest(java["executable"]) != java["sha256"]:
        raise ValueError("Resolved TLC/JVM bytes changed")
    return Path(jar["jar"]), jar, java


def check(jar, tool, model_path, config_path, logs, timeout, java=None):
    java = java or resolve_java()
    model, cfg = inside(ROOT, model_path), inside(ROOT, config_path)
    if model.suffix != ".tla" or not re.fullmatch(r"[A-Za-z_]\w*", model.stem) or cfg.suffix != ".cfg":
        raise ValueError("Expected a named .tla module and .cfg file")
    constants, obligations = configuration(cfg.read_text())
    sources = sorted(model.parent.glob("*.tla"))
    if not model.is_file() or any(p.is_symlink() or not p.is_file() for p in sources):
        raise ValueError("Model sources must be regular files")
    inputs = {str(p.relative_to(ROOT)): digest(p) for p in [*sources, cfg]}
    with tempfile.TemporaryDirectory(prefix="tdk-tlc-model-") as tmp:
        for p in sources:
            shutil.copyfile(p, Path(tmp) / p.name)
        shutil.copyfile(cfg, Path(tmp) / "model.cfg")
        argv = [java["executable"], "-Xmx512m", "-XX:+UseParallelGC", "-cp", str(jar.resolve()), "tlc2.TLC",
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
            "inputs": inputs, "runtime": {"tlc": tool, "java": java},
            "native_execution": raw, "completed_at": datetime.now(timezone.utc).isoformat()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("check", "smoke", "resolve"))
    parser.add_argument("--model")
    parser.add_argument("--config")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--output", required=True, help="New result path relative to proof/")
    parser.add_argument("--runtime", type=Path)
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
        if args.runtime:
            runtime = json.loads(args.runtime.read_text())
        else:
            runtime = resolve_runtime()
        resolved_jar, tool, java = checked_runtime(runtime)
        if not args.runtime:
            jar = resolved_jar
        if args.operation == "resolve":
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(runtime, indent=2) + "\n")
            jar = None  # receipt owns this run-local download
            return 0
        if args.operation == "smoke":
            positive = check(resolved_jar, tool, "examples/tlc/Counter.tla", "examples/tlc/Counter.cfg", logs, args.timeout, java)
            negative = check(resolved_jar, tool, "examples/tlc/BrokenCounter.tla", "examples/tlc/BrokenCounter.cfg", logs, args.timeout, java)
            passed = int(positive["outcome"] == "verified") + int(negative["outcome"] == "violated")
            result = {"schema": "component-result/v1", "kind": "tests", "outcome": "pass" if passed == 2 else "violated",
                      "tests": {"passed": passed, "failed": 2 - passed, "skipped": 0},
                      "examples": [positive, negative], "scope": "adapter acceptance, not project verification"}
        else:
            result = check(resolved_jar, tool, args.model, args.config, logs, args.timeout, java)
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
