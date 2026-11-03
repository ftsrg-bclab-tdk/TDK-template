"""Generate a VS Code workspace without replacing user modifications."""
import hashlib
import json
from pathlib import Path
from ci.config import inside


def prepare(root, config, previous=None):
    folders = [{"name": "Project", "path": "."}]
    for name, component in config["components"].items():
        if inside(root, component["cwd"]).is_dir():
            folders.append({"name": name, "path": component["cwd"]})
    value = {"folders": folders, "settings": {
        "files.exclude": {"**/.onboarding": True},
        "search.exclude": {"**/.onboarding/**": True},
    }}
    data = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
    target = inside(root, "tdk.code-workspace")
    current = target.read_bytes() if target.exists() else None
    digest = hashlib.sha256(data).hexdigest()
    if current is not None and current != data:
        if not previous or hashlib.sha256(current).hexdigest() != previous.get("sha256"):
            raise ValueError("Workspace has user edits; refusing to overwrite")
    if not inside(root, "AGENTS.md").is_file():
        raise ValueError("Root AGENTS.md missing; restore template instructions before workspace setup")
    return {"path": str(target), "value": value, "sha256": digest,
            "before_sha256": hashlib.sha256(current).hexdigest() if current is not None else None,
            "changed": current != data}


def apply(prepared, write_json):
    target = Path(prepared["path"])
    current = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
    if current != prepared["before_sha256"]:
        raise ValueError("Workspace changed during preview")
    if prepared["changed"]:
        write_json(target, prepared["value"])
    return {"sha256": prepared["sha256"], "path": target.name}
