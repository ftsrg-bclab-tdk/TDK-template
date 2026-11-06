#!/usr/bin/env python3
"""Student/advisor local setup. No remote repository, access or publication mutations."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import difflib
import copy
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import subprocess
import sys
import tempfile

from onboarding import accounts, bootstrap, session, workflow, platforms, workspace, provision, checks, faculty

from readme.badges import invalidate_blocks

from ci.config import MACROS, inside, load_project, validate_project


def run(argv, timeout=30, cwd=None):
    try:
        result = subprocess.run(argv, cwd=cwd, timeout=timeout, capture_output=True, text=True)
    except FileNotFoundError:
        return {"returncode": 127, "stdout": ""}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": ""}
    return {"returncode": result.returncode, "stdout": result.stdout}


def run_install(argv, timeout=900):
    """Package managers retain their terminal prompts; no shell or captured secrets."""
    result = subprocess.run(argv, timeout=timeout)
    return {"returncode": result.returncode}


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
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
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
        desired = item["expected"] if item["value"] == item["expected"] else tex(item["value"])
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
    """Initialize project identity while preserving CI component settings."""
    config = copy.deepcopy(existing)
    config["repository"] = repository
    if repository != "FTSRG-BCLab-TDK/TDK-template":
        config["role"] = "project"
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
        if not re.search(r"^\\newcommand\{\\" + re.escape(macro) + r"\}\{", content, re.M):
            continue
        start, end = declaration(content, macro)
        config["metadata"][macro] = {"expected": content[start:end], "value": content[start:end]}
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
    value = input("Confirm [yes/no/edit]: " if prompt["field"] == "account_attested" else "Identifier (no passwords or tokens): ")
    if prompt["field"] == "account_attested":
        return "edit" if value.strip().lower() == "edit" else {"yes": True, "y": True, "no": False, "n": False}.get(value.strip().lower())
    return value


def import_faculty(root, args):
    """One-way import of a faculty-template paper; writes only paper/ files, never private state."""
    config, _ = load_project(root, args.config)
    main_file = inside(root, config["paper_main"])
    if main_file.name != "draft.tex" or not main_file.is_file():
        raise ValueError("The import needs paper_main to be the template's draft.tex")
    labels = {}
    for item in args.label:
        source, separator, role = item.partition("=")
        if not separator or not source or not role:
            raise ValueError("--label takes SOURCE=ROLE, such as content/intro.tex=intro")
        labels[PurePosixPath(source).as_posix()] = role
    report = faculty.plan(Path(args.import_faculty).resolve(), main_file.parent, labels, args.accept_suggestions)
    print(faculty.render(report, args.dry_run), end="")
    if report["conflicts"]:
        return 1
    if not args.dry_run:
        faculty.apply(report, main_file.parent)
        print("Imported. Build with `make -C paper draft`, review `git diff`, then commit.")
    return 0


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
    parser.add_argument("--install-plan", action="store_true")
    parser.add_argument("--install-tools", action="store_true", help="Execute the displayed package-manager commands (may request sudo)")
    parser.add_argument("--docker-runtime", choices=["existing", "engine", "desktop"], default="existing")
    parser.add_argument("--workspace", action="store_true", help="Generate tdk.code-workspace without overwriting edits")
    parser.add_argument("--github-account", action="store_true", help="Read authenticated GitHub identity and 2FA status")
    parser.add_argument("--inspect-repository", action="store_true", help="Read current repository identity/privacy/access")
    parser.add_argument("--inspect-access", metavar="GITHUB_USER", help="Read effective collaborator role without inviting")
    parser.add_argument("--provision-pilot", action="store_true", help="Create/initialize ONLY an onboarding-pilot-* private organization repository")
    parser.add_argument("--invite-pilot", metavar="GITHUB_USER", help="Scoped pilot invitation after authenticated organization 2FA readback")
    parser.add_argument("--template", default="FTSRG-BCLab-TDK/TDK-template")
    parser.add_argument("--ingest-ci", metavar="REPORT", help="Verify component report with shared CI verifier; native sync/clone remains separate")
    parser.add_argument("--report-sha256", help="Expected raw report digest from trusted receipt")
    parser.add_argument("--import-faculty", metavar="PATH_OR_ZIP", help="Bring a paper written in the BME VIK faculty LaTeX template into paper/")
    parser.add_argument("--label", action="append", default=[], metavar="SOURCE=ROLE",
                        help="With --import-faculty: confirm a chapter's role (intro, background, approach, implementation, evaluation, related, conclusion) or refuse a suggestion (none)")
    parser.add_argument("--accept-suggestions", action="store_true", help="With --import-faculty: add every suggested label, \\printlists and preamble definition")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error("Python 3.11+ is required; install a supported Python before setup")
    if platform.system() == "Windows":
        parser.error("Run setup inside WSL; native Windows is unsupported")
    if (args.init_config or args.apply_metadata or args.paper_source or args.provision_pilot or args.invite_pilot) and args.role != "advisor":
        parser.error("Only advisor mode prepares/applies shared metadata")
    if args.role == "status" and (args.check_bootstrap or args.smoke or args.install_tools or args.workspace or args.github_account or args.inspect_repository or args.inspect_access or args.ingest_ci):
        parser.error("Status is read-only; use student --check-bootstrap --smoke")
    if args.paper_source and not args.init_config:
        parser.error("--paper-source requires --init-config ORG/REPO")
    if args.import_faculty and args.role != "student":
        parser.error("--import-faculty is a student command")
    if (args.label or args.accept_suggestions) and not args.import_faculty:
        parser.error("--label and --accept-suggestions go with --import-faculty")
    try:
        exit_code = 0
        root = Path(git(Path(args.root).resolve(), "rev-parse", "--show-toplevel")).resolve()
        if args.import_faculty:
            return import_faculty(root, args)
        local = state_path(root, args.state_dir)
        for target in local.iterdir() if local.exists() else []:
            if target.is_symlink() or not target.is_file() or target.stat().st_mode & 0o077 or target.stat().st_uid != os.getuid():
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
                    if proposed["role"] == "project":
                        invalidate_blocks(root)
                    atomic_json(config_path, proposed)
                    config, config_digest = load_project(root, args.config)
                else:
                    config = proposed
            if args.role == "advisor" and config:
                print(metadata(root, config, apply=args.apply_metadata and not args.dry_run) or "Metadata unchanged.")
            if args.install_plan or args.install_tools:
                planned = platforms.plan(platforms.host(), args.docker_runtime)
                print(json.dumps(planned, indent=2))
                result = platforms.install(planned, run_install, execute=args.install_tools and not args.dry_run)
                if result["status"] == "failed":
                    exit_code = 1
                if args.install_tools and not args.dry_run:
                    atomic_json(local / "installation.json", result)
                    print("Installation commands completed; run Docker smoke separately to verify readiness.")
            if args.workspace:
                receipt_path = local / "workspace.json"
                prior = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
                prepared = workspace.prepare(root, config, prior)
                print(json.dumps(prepared["value"], indent=2))
                if not args.dry_run:
                    receipt = workspace.apply(prepared, atomic_json)
                    receipt["config_digest"] = config_digest
                    atomic_json(receipt_path, receipt)
            if args.github_account:
                if args.dry_run:
                    print("Would observe authenticated GitHub identity and 2FA; no invitation or permission change.")
                else:
                    expected = None
                    if args.role == "student":
                        saved = session.load(local / "accounts.json", catalog)["github"]["identifier"]
                        if not saved:
                            raise ValueError("Record student GitHub identifier before verifying authenticated account")
                        expected = saved["value"]
                    observed = provision.github_account(provision.Gh(), expected)
                    atomic_json(local / "github-account.json", observed)
                    print("Authenticated GitHub 2FA: " + observed["two_factor"])
                    if observed["two_factor"] != "verified":
                        exit_code = 1
            if args.inspect_repository:
                if args.dry_run:
                    print("Would observe repository identity, privacy and effective permissions.")
                else:
                    observed = provision.inspect_repository(provision.Gh(), config["repository"])
                    observed["config_digest"] = config_digest
                    atomic_json(local / "repository.json", observed)
                    print(json.dumps(observed, indent=2))
            if args.provision_pilot:
                receipt = provision.provision_pilot(provision.Gh(), config, args.template, root, execute=not args.dry_run,
                    prior=json.loads((local / "provision.json").read_text()) if (local / "provision.json").exists() else None,
                    persist=lambda value: atomic_json(local / "provision.json", value))
                print(json.dumps(receipt, indent=2))
                if not args.dry_run:
                    atomic_json(local / "provision.json", receipt)
            if args.invite_pilot:
                receipt = provision.invite_pilot(provision.Gh(), config["repository"], args.invite_pilot, execute=not args.dry_run)
                print(json.dumps(receipt, indent=2))
                if not args.dry_run:
                    atomic_json(local / "invitation.json", receipt)
            if args.inspect_access:
                if args.dry_run:
                    print("Would inspect collaborator effective access; no invitation or 2FA claim.")
                else:
                    observed = provision.inspect_access(provision.Gh(), config["repository"], args.inspect_access)
                    atomic_json(local / "access.json", observed)
                    print(json.dumps(observed, indent=2))
            if args.ingest_ci:
                if args.dry_run:
                    print("Would verify report for all enabled components with shared CI verifier; native sync/clone and artifact authority remain independent.")
                else:
                    if git(root, "status", "--porcelain"):
                        raise ValueError("Current checkout is dirty; CI evidence cannot qualify current working changes")
                    receipt = checks.ingest(Path(args.ingest_ci), config, config_digest,
                                            git(root, "rev-parse", "HEAD"), report_digest=args.report_sha256)
                    if load_project(root, args.config)[1] != config_digest:
                        raise ValueError("Project config changed during CI verification")
                    atomic_json(local / "component-checks.json", receipt)
                    print(json.dumps(receipt, indent=2))
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
            print("Settled policy: private tdk-maintenance controller with selected-repo organization App; org-required 2FA before new invitations; lead student publishes exact reviewed receipt via project workflow and own Zenodo repo secret.")
            print("Deployment/permission/roundtrip evidence remains pending. Advisor review is policy, not an enforced boundary on student-writable workflows.")
            print("Overall onboarding remains pending external access, sync and component evidence.")
        return exit_code
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        # Do not expose raw subprocess output or account state in errors.
        print("Setup failed: " + (str(error) if isinstance(error, ValueError) and not isinstance(error, json.JSONDecodeError) else type(error).__name__), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
