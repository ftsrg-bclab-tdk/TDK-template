#!/usr/bin/env python3
"""Student/advisor local setup. No remote repository, access or publication mutations."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import difflib
import copy
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import tempfile

from onboarding import accounts, bootstrap, session, workflow

from ci.config import MACROS, inside, load_project, validate_project


def run(argv, timeout=30, cwd=None):
    try:
        result = subprocess.run(argv, cwd=cwd, timeout=timeout, capture_output=True, text=True)
    except FileNotFoundError:
        return {"returncode": 127, "stdout": ""}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": ""}
    return {"returncode": result.returncode, "stdout": result.stdout}


def git(root, *args):
    result = run(["git", "-C", str(root), *args])
    if result["returncode"]:
        raise ValueError("Git operation failed; verify this is a working checkout")
    return result["stdout"].strip()


def state_path(root, relative):
    path = inside(root, relative)
    probe = str((path / ".ignore-probe").relative_to(root))
    if git(root, "ls-files", "--", str(path.relative_to(root))):
        raise ValueError("State directory contains tracked files")
    if run(["git", "-C", str(root), "check-ignore", "--quiet", "--no-index", probe])["returncode"]:
        raise ValueError("State directory must be ignored by Git before use")
    for parent in [path, *path.parents]:
        if parent == root:
            break
        if parent.exists() and (parent.stat().st_uid != os.getuid() or parent.stat().st_mode & 0o077):
            raise ValueError("State path must use owned private directories (mode 0700)")
    return path


@contextmanager
def locked(path, readonly=False):
    import fcntl
    if readonly and not path.exists():
        yield
        return
    if not readonly:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = path / "session.lock"
    if readonly and not lock.exists():
        raise ValueError("Existing state has no lock; inspect it before running setup")
    flags = (os.O_RDONLY if readonly else os.O_CREAT | os.O_RDWR) | os.O_NOFOLLOW
    descriptor = os.open(lock, flags, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("Lock must be an owned private regular file")
        mode = fcntl.LOCK_SH if readonly else fcntl.LOCK_EX
        try:
            fcntl.flock(descriptor, mode | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another setup session is using this state") from None
        yield
    finally:
        os.close(descriptor)


def atomic_json(path, value):
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=".setup-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def tex(value):
    replacements = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}",
                    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
                    "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(replacements.get(c, c) for c in value)


def declaration(content, macro):
    starts = list(re.finditer(r"^\\newcommand\{\\" + re.escape(macro) + r"\}\{", content, re.M))
    if len(starts) != 1:
        raise ValueError("Metadata declaration missing or ambiguous: " + macro)
    start = starts[0].end()
    index, depth = start, 1
    while index < len(content):
        char = content[index]
        if char == "\n":
            break
        if char == "\\":
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return start, index
        index += 1
    raise ValueError("Metadata declaration must be balanced on one line: " + macro)


def metadata(root, config, apply=False):
    path = inside(root, config["paper_main"])
    if path.suffix != ".tex" or not git(root, "ls-files", "--", str(path.relative_to(root))):
        raise ValueError("Paper metadata target must be a tracked TeX file")
    before = path.read_text(encoding="utf-8")
    after = before
    for macro, item in config["metadata"].items():
        # Parse only the balanced argument, leaving trailing comments untouched.
        start, end = declaration(after, macro)
        desired = tex(item["value"])
        if after[start:end] == desired:
            continue
        if after[start:end] != item["expected"]:
            raise ValueError("Metadata conflict; student edit preserved: " + macro)
        after = after[:start] + desired + after[end:]
    diff = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile=str(path.relative_to(root)), tofile=str(path.relative_to(root))))
    if apply and before != after:
        # Recheck just before replacement; all fields were preflighted together.
        if path.read_text(encoding="utf-8") != before:
            raise ValueError("Paper changed during preview")
        descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=".metadata-")
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(after)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(name, path.stat().st_mode & 0o777)
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    return diff


def scaffold(root, repository, existing, paper_source=None):
    """Update setup-owned fields; CI identity/settings remain byte-value identical."""
    config = copy.deepcopy(existing)
    config["repository"] = repository
    if paper_source is not None:
        config["paper_main"] = paper_source
    validate_project(config, root)
    path = inside(root, config["paper_main"])
    if not path.is_file() or not git(root, "ls-files", "--", config["paper_main"]):
        raise ValueError("Configured paper source is not a tracked file; use --paper-source to initialize its actual location")
    content = path.read_text(encoding="utf-8")
    for macro in sorted(MACROS):
        if macro in config["metadata"]:
            continue  # Never reset an expected value over a student's edit.
        found = re.findall(r"^\\newcommand\{\\" + macro + r"\}\{([^{}]*)\}", content, re.M)
        if len(found) == 1:
            config["metadata"][macro] = {"expected": found[0], "value": found[0]}
    validate_project(config, root)
    metadata(root, config)  # All retained expectations must still be valid.
    return config


def bootstrap_report(runner=run, smoke=False):
    resolution = None
    if smoke:
        pull = runner(["docker", "pull", "alpine:latest"], timeout=180)
        if pull["returncode"]:
            return {"ready": False, "scope": "bootstrap_only", "reason": "latest_image_pull_failed"}
        inspected = runner(["docker", "image", "inspect", "alpine:latest", "--format", "{{json .}}"], timeout=30)
        if inspected["returncode"]:
            return {"ready": False, "scope": "bootstrap_only", "reason": "image_inspection_failed"}
        image = json.loads(inspected["stdout"])
        digests = image.get("RepoDigests", [])
        if not digests:
            return {"ready": False, "scope": "bootstrap_only", "reason": "image_digest_missing"}
        resolution = {"requested": "alpine:latest", "digest": digests[0], "image_id": image.get("Id"),
                      "os": image.get("Os"), "architecture": image.get("Architecture")}
    result = bootstrap.check(runner, execute_smoke=smoke, smoke_image=resolution["digest"] if resolution else None, smoke_command=["/bin/true"])
    result["resolution"] = resolution
    context = runner(["docker", "context", "show"], timeout=30)
    result["docker_context"] = context["stdout"].strip() if context["returncode"] == 0 else None
    result["checked_at"] = datetime.now(timezone.utc).isoformat()
    return result


def ask(prompt):
    print(prompt["service"] + ": " + prompt["text"])
    print("Sign up: " + prompt["signup_url"] + "\nProfile: " + prompt["profile_url"])
    value = input("Confirm [yes/no]: " if prompt["field"] == "account_attested" else "Identifier (no passwords or tokens): ")
    if prompt["field"] == "account_attested":
        return {"yes": True, "y": True, "no": False, "n": False}.get(value.strip().lower())
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=["student", "advisor", "status"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--state-dir", default=".onboarding")
    parser.add_argument("--config", default="project.json")
    parser.add_argument("--paper-source", help="Explicit editable source location during advisor initialization")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-accounts", action="store_true")
    parser.add_argument("--check-bootstrap", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Explicitly pull latest smoke image and run a container")
    parser.add_argument("--init-config", metavar="ORG/REPO")
    parser.add_argument("--apply-metadata", action="store_true")
    args = parser.parse_args(argv)
    if platform.system() == "Windows":
        parser.error("Run setup inside WSL; native Windows is unsupported")
    if (args.init_config or args.apply_metadata or args.paper_source) and args.role != "advisor":
        parser.error("Only advisor mode prepares/applies shared metadata")
    if args.role == "status" and (args.check_bootstrap or args.smoke):
        parser.error("Status is read-only; use student --check-bootstrap --smoke")
    if args.paper_source and not args.init_config:
        parser.error("--paper-source requires --init-config ORG/REPO")
    try:
        exit_code = 0
        root = Path(git(Path(args.root).resolve(), "rev-parse", "--show-toplevel")).resolve()
        local = state_path(root, args.state_dir)
        for child in ("accounts.json", "bootstrap.json", "session.lock"):
            target = local / child
            if target.exists() and (target.is_symlink() or not target.is_file()):
                raise ValueError("State entries must be regular files")
        config_path = inside(root, args.config)
        if config_path == local or config_path.is_relative_to(local):
            raise ValueError("Shared config must be separate from private state")
        readonly = args.dry_run or args.role == "status"
        catalog = json.loads((Path(__file__).parent / "onboarding/account-services.json").read_text())
        with locked(local, readonly):
            config, config_digest = load_project(root, args.config)
            if args.init_config:
                proposed = scaffold(root, args.init_config, config, args.paper_source)
                print("".join(difflib.unified_diff(
                    config_path.read_text().splitlines(True),
                    (json.dumps(proposed, indent=2, ensure_ascii=False) + "\n").splitlines(True),
                    fromfile=args.config, tofile=args.config)))
                if not args.dry_run:
                    # Refuse to overwrite edits made while preparing the proposal.
                    if load_project(root, args.config)[1] != config_digest:
                        raise ValueError("Project configuration changed during initialization")
                    atomic_json(config_path, proposed)
                    config, config_digest = load_project(root, args.config)
                else:
                    config = proposed
            if args.role == "advisor" and config:
                print(metadata(root, config, apply=args.apply_metadata and not args.dry_run) or "Metadata unchanged.")
            if args.role == "student" and not args.skip_accounts:
                outcome = session.collect(local / "accounts.json", catalog, ask,
                    lambda event: print("Saved " + event["service"] if event["event"] == "saved" else "Invalid answer; try again."), dry_run=args.dry_run)
                if args.dry_run:
                    for prompt in outcome["prompts"]:
                        print(prompt["service"] + ": " + prompt["text"] + "\n" + prompt["signup_url"] + "\n" + prompt["profile_url"])
            if args.check_bootstrap or args.smoke:
                if args.dry_run:
                    print("Would check Git/Python/gh/Docker and daemon access" + ("; pull latest smoke image once and execute its digest" if args.smoke else "; smoke remains pending"))
                else:
                    report = bootstrap_report(smoke=args.smoke)
                    report["source_sha"] = git(root, "rev-parse", "HEAD")
                    report["dirty"] = bool(git(root, "status", "--porcelain"))
                    report["config_digest"] = config_digest
                    if load_project(root, args.config)[1] != config_digest:
                        raise ValueError("Project configuration changed during checks; evidence discarded")
                    atomic_json(local / "bootstrap.json", report)
                    print(json.dumps(report, indent=2))
                    if not report["ready"]:
                        exit_code = 1
            current = accounts.status(catalog, session.load(local / "accounts.json", catalog))
            if config["repository"] is None:
                print("Repository unconfigured: advisor must initialize project.json; account/bootstrap checks do not establish project access.")
            previous = local / "bootstrap.json"
            if previous.exists():
                if previous.is_symlink() or previous.stat().st_mode & 0o077:
                    raise ValueError("Bootstrap evidence must be a private regular file")
                evidence = json.loads(previous.read_text())
                digest = config_digest
                stale = evidence.get("source_sha") != git(root, "rev-parse", "HEAD") or evidence.get("config_digest") != digest
                print("Saved bootstrap: " + ("stale" if stale else "recorded ready" if evidence.get("ready") else "incomplete") + "; rerun checks to verify current runtime.")
            for item in current["steps"]:
                print(item["service"] + ": " + item["next_action"] + " (" + item["account"] + ")")
            for item in workflow.observations(config or {}):
                print(item["status"] + " — " + item["actor"] + ": " + item["action"])
            print("Unconfigured policy: maintenance controller/authentication; publication credential/execution; 2FA. No remote mutations performed.")
            print("Overall onboarding remains pending external access, sync and component evidence.")
        return exit_code
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        # Do not expose raw subprocess output or account state in errors.
        print("Setup failed: " + (str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError) else type(error).__name__), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
