#!/usr/bin/env python3
"""Shared local/CI planning and checks. Never installs tools or changes paper phase."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from ci.config import inside, load_project, read_json
from ci.dependencies import plan as dependency_plan
from ci.process import execute
from ci.results import interpret
from ci.evidence import validate_runtime, uses_tlc


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError("Git failed: " + " ".join(args))
    return result.stdout.decode()


def identity(root, config):
    return {"repository": config["repository"], "source_sha": git(root, "rev-parse", "HEAD").strip(),
            "tested_sha": git(root, "rev-parse", "HEAD").strip(),
            "dirty": bool(git(root, "status", "--porcelain", "--untracked-files=normal").strip()),
            "tracked_diff_sha256": hashlib.sha256(git(root, "diff", "HEAD", "--binary").encode()).hexdigest()}


def make_plan(root, config, config_digest, args):
    source = identity(root, config)
    if args.head and args.head != source["tested_sha"]:
        raise ValueError("Requested head is not the checked-out commit")
    graph = {n: {"paths": c["paths"], "depends_on": c["depends_on"]}
             for n, c in config["components"].items() if c["enabled"]}
    paths, complete, merge_base = [], True, None
    if args.scope == "affected":
        try:
            if not args.base:
                raise ValueError("No base")
            merge_base = git(root, "merge-base", args.base, source["tested_sha"]).strip()
            # --no-renames includes both deleted and added sides without parsing quoted paths.
            paths = git(root, "diff", "--no-renames", "--name-only", "-z", merge_base, source["tested_sha"], "--").split("\0")[:-1]
        except ValueError:
            complete = False
    value = dependency_plan(paths, graph, complete=complete, all_scope=args.scope == "all")
    requested = args.component or []
    if len(set(requested)) != len(requested) or any(n not in config["components"] for n in requested):
        raise ValueError("Unknown or duplicate requested component")
    if requested:
        selected = set(requested)
        pending = list(requested)
        while pending and not getattr(args, "no_dependencies", False):
            for dep in config["components"][pending.pop()]["depends_on"]:
                if dep not in selected:
                    selected.add(dep)
                    pending.append(dep)
        for name in graph:
            value["components"][name] = {"selected": name in selected, "reasons": ["explicit scope"] if name in selected else []}
    for name, component in config["components"].items():
        if not component["enabled"]:
            value["components"][name] = {"selected": name in requested, "reasons": ["not configured"]}
    value.update(source=source, configuration={"project_config_sha256": config_digest},
                 base_sha=args.base, merge_base_sha=merge_base, changed_paths=paths, diff_complete=complete,
                 draft=args.draft, mode=args.mode, profile=args.profile, requested_components=requested,
                 dependency_execution="external" if getattr(args, "no_dependencies", False) else "included")
    return value


def doctor(root, config, config_digest):
    issues = []
    if sys.version_info < (3, 11):
        issues.append("Python 3.11 or newer is required")
    for label, path in [("paper source", config["paper_main"]), *config["paper_entrypoints"].items()]:
        if not inside(root, path).is_file():
            issues.append(label + " missing: " + path)
    for name, component in config["components"].items():
        if component["enabled"] and not inside(root, component["cwd"]).is_dir():
            issues.append("Enabled component directory missing: " + name)
    if config["repository"] is None:
        issues.append("Repository identity is not configured")
    tools = {tool: shutil.which(tool) for tool in ("git", "python3", "gh", "docker")}
    return {"schema": "project-doctor/v1", "configuration": {"project_config_sha256": config_digest},
            "source": identity(root, config), "tools": tools, "issues": issues,
            "outcome": "fail" if issues or not all(tools.values()) else "pass",
            "scope": "configuration and executable discovery; no component or service access verified"}


def run_check(root, component, step, output, strict, mode="ordinary", runtime=None):
    cwd = inside(root, component["cwd"])
    result_file = inside(cwd, step["result_file"]) if "result_file" in step else None
    if result_file and result_file.exists():
        raise ValueError("Stale adapter result exists before execution: " + str(result_file))
    for relative in step["outputs"]:
        path = inside(cwd, relative)
        if path.exists() or path.is_symlink():
            raise ValueError("Stale required output exists before execution: " + relative)
    argv = list(step["argv"])
    if any(Path(arg).name == "tlc.py" for arg in argv) and runtime and runtime.get("proof_tools_path"):
        if read_json(runtime["proof_tools_path"])[0] != runtime.get("proof_tools"):
            raise ValueError("Proof tool receipt changed before execution")
        argv += ["--runtime", runtime["proof_tools_path"]]
    result = execute(argv, cwd, output, step["name"], step["timeout"])
    result.update(name=step["name"], kind=step["kind"], files=[])
    native = None
    try:
        if step["kind"] == "writing" and result["raw_exit"] in (0, 1):
            native, _ = read_json(result["stdout"])
        elif result_file and result_file.is_file():
            native, _ = read_json(result_file)
            shutil.copyfile(result_file, output / (step["name"] + ".result.json"))
        if (runtime and runtime.get("proof_tools") and native and step["kind"] == "proof"
                and native.get("runtime") != runtime["proof_tools"]):
            raise ValueError("Proof result differs from resolved TLC/JVM runtime")
        result.update(interpret(step["kind"], result["raw_exit"], native, strict=strict))
        if step["kind"] == "benchmark" and native and native.get("mode") != ("full" if mode == "full" else "smoke"):
            raise ValueError("Benchmark result mode differs from requested execution")
    except ValueError as exc:
        result.update(execution_status="error", outcome="unknown", gate_outcome="fail", reason=str(exc))
    for relative in step["outputs"]:
        path = inside(cwd, relative)
        paths = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else []
        if not paths or any(p.is_symlink() for p in path.rglob("*")):
            result.update(outcome="unknown", gate_outcome="fail", reason="Required output missing: " + relative)
            continue
        for member in paths:
            if member.stat().st_size == 0 and relative not in step.get("allow_empty_outputs", []):
                result.update(outcome="unknown", gate_outcome="fail", reason="Required output empty: " + relative)
                continue
            target = output / "files" / step["name"] / member.relative_to(cwd)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(member, target)
            result["files"].append({"path": str(target.relative_to(output)), "source_path": str(member.relative_to(cwd)),
                                    "sha256": file_hash(target), "bytes": target.stat().st_size,
                                    "audience": "private_review"})
    return result


def check(root, config, config_digest, plan, output, runtime=None, config_path="project.json"):
    if not config["repository"]:
        raise ValueError("Configure repository identity before checking")
    ci_repo = os.environ.get("GITHUB_REPOSITORY")
    if ci_repo and ci_repo.lower() != config["repository"].lower():
        raise ValueError("Configured repository differs from this GitHub run")
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema": "project-checks/v1", "source": plan["source"],
              "configuration": {"project_config_sha256": config_digest, "dependency_plan_sha256": digest(plan)},
              "control": {"checker_sha256": digest({str(p.relative_to(Path(__file__).parent)): file_hash(p) for p in [Path(__file__), *sorted(Path(__file__).parent.joinpath('ci').glob('*.py'))]})},
              "execution": {"started_at": now(), "actor": os.environ.get("GITHUB_ACTOR") or os.environ.get("USER", "unknown"),
                            "method": "github_actions" if os.environ.get("GITHUB_ACTIONS") else "local",
                            "run_id": os.environ.get("GITHUB_RUN_ID"), "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
                            "job_id": os.environ.get("GITHUB_JOB"), "workflow_sha": os.environ.get("GITHUB_WORKFLOW_SHA"),
                            "log_reference": (os.environ.get("GITHUB_SERVER_URL", "https://github.com") + "/" + ci_repo + "/actions/runs/" + os.environ.get("GITHUB_RUN_ID", "")) if ci_repo else str(output)},
              "plan": plan, "components": {}, "runtime": runtime,
              "runtime_sha256": digest(runtime) if runtime else None}
    (output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    if runtime:
        if runtime.get("schema") != "runtime-resolution/v1" or runtime.get("source_sha") != plan["source"]["tested_sha"] or runtime.get("project_config_sha256") != config_digest:
            raise ValueError("Runtime identity differs from checked source/config")
        (output / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")
        if runtime.get("npm"):
            lock = inside(root, runtime["npm"]["lock_path"])
            if file_hash(lock) != runtime["npm"]["lock_sha256"]:
                raise ValueError("Run-local npm resolution changed before checking")
            shutil.copyfile(lock, output/"package-lock.json")
    pending = set(config["components"])
    while pending:
        ready = sorted(n for n in pending if not set(config["components"][n]["depends_on"]) & pending)
        for name in ready:
            pending.remove(name)
            component = dict(config["components"][name])
            decision = plan["components"][name]
            result = {"execution_status": "not_run", "checks": [], "gate_outcome": "incomplete"}
            report["components"][name] = result
            if not component["enabled"]:
                result.update(outcome="not_configured")
                continue
            if not decision["selected"]:
                result.update(outcome="unaffected")
                continue
            if plan["draft"]:
                result.update(outcome="deferred")
                continue
            if any(report["components"][d]["gate_outcome"] != "pass" for d in component["depends_on"] if plan["components"][d]["selected"]):
                result.update(outcome="unknown", reason="dependency did not pass")
                continue
            mode = plan["profile"] or (plan["mode"] if (plan["mode"] == "submit" and name == "paper" or plan["mode"] == "full" and name == "benchmark") else "ordinary")
            component_output = output / name
            component_output.mkdir()
            try:
                if runtime and runtime.get("staged_components", {}).get(name):
                    staged = runtime["staged_components"][name]
                    if not staged.startswith(".project/runtime/"):
                        raise ValueError("Resolved component must be staged under .project/runtime/")
                    component["cwd"] = staged
                if mode not in component["profiles"]:
                    raise ValueError("No configured profile: " + mode)
                if uses_tlc(component["profiles"][mode]):
                    validate_runtime(runtime, plan["source"]["tested_sha"], config_digest, name, require_tlc=True)
                for step in component["profiles"][mode]:
                    try:
                        record = run_check(root, component, step, component_output, mode == "submit", mode, runtime)
                    except (ValueError, OSError) as exc:
                        record = {"name": step["name"], "kind": step["kind"], "execution_status": "error", "outcome": "unknown", "gate_outcome": "fail", "reason": str(exc)}
                    result["checks"].append(record)
                    if name == "presentation" and step["kind"] == "build" and record["gate_outcome"] == "pass":
                        exported = component_output / "files" / step["name"] / "dist"
                        browser = runtime.get("browser_path") if runtime else os.environ.get("CHROME_PATH")
                        if not browser:
                            raise ValueError("Export verification requires resolved browser identity")
                        exported_check = execute(["node", str(Path(__file__).parent / "ci/export_check.mjs"),
                                                  str(inside(root, component["cwd"])), str(exported), browser],
                                                 root, component_output, step["name"] + "-export", step["timeout"])
                        exported_check.update(name=step["name"] + "-export", kind="command", files=[])
                        exported_check.update(interpret("command", exported_check["raw_exit"]))
                        result["checks"].append(exported_check)
                passed = all(c["gate_outcome"] == "pass" for c in result["checks"])
                result.update(execution_status="completed" if all(c["execution_status"] == "completed" for c in result["checks"]) else "error",
                              outcome="findings" if passed and any(c["outcome"] == "findings" for c in result["checks"]) else "pass" if passed else "unknown",
                              gate_outcome="pass" if passed else "fail", profile=mode)
            except (ValueError, OSError) as exc:
                result.update(execution_status="error", outcome="unknown", gate_outcome="fail", reason=str(exc))
    selected = [report["components"][n] for n, d in plan["components"].items() if d["selected"]]
    report["gate_outcome"] = "incomplete" if plan["draft"] else "pass" if all(c["gate_outcome"] == "pass" for c in selected) else "fail"
    report["execution"]["completed_at"] = now()
    report["acceptance_eligible"] = report["gate_outcome"] == "pass" and not plan["source"]["dirty"] and not plan["draft"] and not plan["requested_components"] and all(d["selected"] for n, d in plan["components"].items() if config["components"][n]["enabled"]) and runtime is not None
    if load_project(root, config_path)[1] != config_digest:
        report.update(gate_outcome="fail", acceptance_eligible=False, error="Configuration changed during execution")
    if git(root, "rev-parse", "HEAD").strip() != plan["source"]["tested_sha"]:
        report.update(gate_outcome="fail", acceptance_eligible=False, error="Source revision changed during execution")
    if identity(root, config)["tracked_diff_sha256"] != plan["source"]["tracked_diff_sha256"]:
        report.update(gate_outcome="fail", acceptance_eligible=False, error="Tracked source changed during execution")
    report["source_after"] = identity(root, config)
    if report["source_after"]["dirty"]:
        report["acceptance_eligible"] = False
    report["files"] = []
    for path in sorted(output.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlink in check evidence")
        if path.is_file():
            report["files"].append({"path": str(path.relative_to(output)), "bytes": path.stat().st_size, "sha256": file_hash(path)})
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("doctor", "plan", "check"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", default="project.json")
    parser.add_argument("--scope", choices=("all", "affected"), default="all")
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--component", action="append")
    parser.add_argument("--no-dependencies", action="store_true", help="Run only requested components; an outer aggregate must verify dependencies")
    parser.add_argument("--mode", choices=("ordinary", "submit", "full"), default="ordinary")
    parser.add_argument("--profile")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--report-dir", default=".project/checks")
    parser.add_argument("--runtime", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        config, config_digest = load_project(root, args.config)
        if args.operation == "doctor":
            value = doctor(root, config, config_digest)
        else:
            value = make_plan(root, config, config_digest, args)
            if args.operation == "check":
                runtime = read_json(args.runtime)[0] if args.runtime else None
                value = check(root, config, config_digest, value, inside(root, args.report_dir), runtime, args.config)
        print(json.dumps(value, indent=2))
        return 1 if value.get("gate_outcome") in ("fail", "incomplete") or value.get("outcome") == "fail" else 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"schema": "project-error/v1", "gate_outcome": "fail", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
