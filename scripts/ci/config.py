"""The single project configuration shared by setup and CI (standard library only)."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

COMPONENTS = {"paper", "code", "proof", "benchmark", "scratch", "presentation"}
MACROS = {"vikcim", "vikszerzoVezeteknev", "vikszerzoKeresztnev",
          "vikkonzulensAVezeteknev", "vikkonzulensAKeresztnev",
          "vikkonzulensBVezeteknev", "vikkonzulensBKeresztnev"}
KINDS = {"command", "build", "writing", "tests", "proof", "benchmark"}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json(path):
    try:
        raw = Path(path).read_bytes()
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("JSON exceeds 2 MiB")
        return json.loads(raw, object_pairs_hook=unique_object), raw
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read JSON {path}: {exc}") from exc


def relative_path(value, *, glob=False):
    if (not isinstance(value, str) or not value or len(value) > 1024 or
            "\\" in value or "\x00" in value or ":" in value or
            any(ord(c) < 32 for c in value) or value.startswith("/") or
            any(p in ("", ".", "..", ".git") for p in value.split("/")) or
            (not glob and any(c in value for c in "*?[]"))):
        raise ValueError("Expected a safe project-relative path: " + repr(value))
    return value


def inside(root, value):
    """Reject symlinks, including existing parents; a declared file may not exist yet."""
    root = Path(root).resolve()
    path = root / relative_path(value)
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        if candidate.is_symlink():
            raise ValueError("Symlink project path: " + value)
    if not path.resolve().is_relative_to(root):
        raise ValueError("Project path escapes root: " + value)
    return path


def keys(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise ValueError("Invalid fields; required: " + ", ".join(sorted(required)))


def validate_project(config, root):
    keys(config, {"schema", "repository", "role", "paper_main", "paper_entrypoints", "metadata", "components"})
    if type(config["schema"]) is not int or config["schema"] != 1:
        raise ValueError("Expected project schema 1")
    repo = config["repository"]
    if repo is not None and (not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)):
        raise ValueError("Repository must be ORG/REPO or null")
    if config["role"] not in ("template", "project"):
        raise ValueError("Role must be template or project")
    inside(root, config["paper_main"])
    keys(config["paper_entrypoints"], {"draft", "final"})
    entries = list(config["paper_entrypoints"].values())
    for entry in entries:
        inside(root, entry)
    if len(set(entries + [config["paper_main"]])) != 3:
        raise ValueError("Paper source and compilation entrypoints must be distinct")
    if config["paper_main"] in ("paper-draft.tex", "paper-final.tex"):
        raise ValueError("Root paper proxies are never editable metadata sources")
    metadata = config["metadata"]
    if not isinstance(metadata, dict) or metadata.keys() - MACROS:
        raise ValueError("Unknown managed paper metadata")
    for change in metadata.values():
        keys(change, {"expected", "value"})
        if any(not isinstance(v, str) or len(v) > 4096 or "\x00" in v for v in change.values()):
            raise ValueError("Invalid managed metadata value")
    components = config["components"]
    if (not isinstance(components, dict) or components.keys() - COMPONENTS or "paper" not in components
            or not all(isinstance(c, dict) for c in components.values())):
        raise ValueError("Unknown component or missing paper declaration")
    for name, component in components.items():
        keys(component, {"enabled", "cwd", "paths", "depends_on", "profiles"})
        if type(component["enabled"]) is not bool:
            raise ValueError("Component enabled must be boolean")
        cwd = inside(root, component["cwd"])
        patterns = component["paths"]
        if (not isinstance(patterns, list) or not patterns or not all(isinstance(p, str) for p in patterns)
                or len(set(patterns)) != len(patterns)):
            raise ValueError("Component paths must be unique and nonempty")
        for pattern in patterns:
            relative_path(pattern, glob=True)
        deps = component["depends_on"]
        if (not isinstance(deps, list) or not all(isinstance(d, str) and d in components for d in deps)
                or len(set(deps)) != len(deps) or name in deps):
            raise ValueError("Invalid or duplicate component dependency")
        if component["enabled"] and any(not components[d].get("enabled") for d in deps):
            raise ValueError("Enabled component depends on disabled component")
        profiles = component["profiles"]
        if not isinstance(profiles, dict) or (component["enabled"] and not profiles.get("ordinary")):
            raise ValueError("Enabled component needs nonempty ordinary checks")
        for profile, checks in profiles.items():
            if not isinstance(profile, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", profile) or not isinstance(checks, list) or not checks:
                raise ValueError("Invalid or empty check profile")
            names = set()
            for check in checks:
                keys(check, {"name", "kind", "argv", "timeout", "outputs"}, {"result_file"})
                if not isinstance(check["name"], str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", check["name"]) or check["name"] in names:
                    raise ValueError("Invalid or duplicate check name")
                names.add(check["name"])
                if not isinstance(check["kind"], str) or check["kind"] not in KINDS:
                    raise ValueError("Unknown check kind")
                argv = check["argv"]
                if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a and "\x00" not in a for a in argv):
                    raise ValueError("Check needs an argv array")
                if PurePosixPath(argv[0]).name in ("true", "echo", "printf", "false") or any(a.strip().upper() == "TODO" for a in argv):
                    raise ValueError("Placeholder command is not a configured check")
                if type(check["timeout"]) is not int or not 1 <= check["timeout"] <= 86400:
                    raise ValueError("Check timeout must be 1..86400 seconds")
                outputs = check["outputs"]
                if not isinstance(outputs, list) or not all(isinstance(o, str) for o in outputs) or len(set(outputs)) != len(outputs):
                    raise ValueError("Invalid output list")
                for output in outputs:
                    inside(cwd, output)
                if check["kind"] in ("tests", "proof", "benchmark") and "result_file" not in check:
                    raise ValueError("Tests/proof/benchmark require a structured result_file")
                if "result_file" in check:
                    inside(cwd, check["result_file"])
    visited, active = set(), set()

    def visit(name):
        if name in active:
            raise ValueError("Cyclic component dependency")
        if name in visited:
            return
        active.add(name)
        for dep in components[name]["depends_on"]:
            visit(dep)
        active.remove(name)
        visited.add(name)
    for name in components:
        visit(name)
    return config


def load_project(root, relative="project.json"):
    """Return (validated dict, SHA256 of the exact config bytes); errors are ValueError."""
    value, raw = read_json(inside(root, relative))
    return validate_project(value, root), hashlib.sha256(raw).hexdigest()
