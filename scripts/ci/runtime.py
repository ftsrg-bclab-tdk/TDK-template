#!/usr/bin/env python3
"""Resolve latest inputs once, then record and reuse their exact run-local resolution."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

try:
    from .config import inside, load_project, read_json
except ImportError:
    from config import inside, load_project, read_json


def command(argv, cwd=None):
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise ValueError("Runtime resolution failed: " + " ".join(argv) + "\n" + result.stderr[-2000:])
    return result.stdout.strip()


def resolve_oci(reference, run=command):
    if not re.fullmatch(r"[a-zA-Z0-9._:/-]+:latest", reference):
        raise ValueError("Normal CI resolves the latest image tag")
    digest = run(["docker", "buildx", "imagetools", "inspect", reference, "--format", "{{.Manifest.Digest}}"])
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("Registry did not return a manifest digest")
    return {"requested": reference, "manifest_digest": digest,
            "resolved": reference.rsplit(":", 1)[0] + "@" + digest}


def prepare_npm(root, component, destination, run=command):
    source = inside(root, component)
    stage = inside(root, destination)
    if stage.exists() or source == stage or source in stage.parents:
        raise ValueError("Npm resolution needs a fresh staging directory outside the component")
    manifest, _ = read_json(source / "package.json")
    dependencies = {}
    for group in ("dependencies", "devDependencies", "optionalDependencies"):
        group_value = manifest.get(group, {})
        if not isinstance(group_value, dict):
            raise ValueError("Invalid npm dependency declaration")
        for name in group_value:
            if not re.fullmatch(r"(@[a-z0-9._-]+/)?[a-z0-9._-]+", name):
                raise ValueError("Invalid npm package name")
            dependencies[name] = "latest"
        if group in manifest:
            manifest[group] = {name: "latest" for name in group_value}
    if not dependencies:
        raise ValueError("No npm dependencies to resolve")
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlink in npm component source")
    shutil.copytree(source, stage, ignore=shutil.ignore_patterns("node_modules", "dist", "package-lock.json", ".git", "__pycache__"))
    (stage / "package.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # The source lock is intentionally not used in latest mode. Resolve once, then
    # npm ci consumes that exact new lock for every render/check in this run.
    run(["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=stage)
    lock = (stage / "package-lock.json").read_bytes()
    resolution = json.loads(lock)
    if not isinstance(resolution.get("packages"), dict) or not resolution["packages"]:
        raise ValueError("npm did not produce a resolution")
    run(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=stage)
    if (stage / "package-lock.json").read_bytes() != lock:
        raise ValueError("npm install changed the selected resolution")
    return {"requested": dependencies, "lock_sha256": hashlib.sha256(lock).hexdigest(),
            "lock_path": str((stage / "package-lock.json").relative_to(root)),
            "versions": {name: p.get("version") for name, p in resolution["packages"].items() if name},
            "staged_cwd": destination}


def snapshot(root, config_path, component, image=None, npm_stage=None, run=command):
    config, config_hash = load_project(root, config_path)
    value = {"schema": "runtime-resolution/v1", "source_sha": run(["git", "rev-parse", "HEAD"], cwd=root),
             "project_config_sha256": config_hash, "resolved_at": datetime.now(timezone.utc).isoformat(),
             "policy": "latest", "components": [component], "tools": {}, "images": {}, "staged_components": {}}
    probes = {"python": ["python3", "--version"], "git": ["git", "--version"]}
    if component == "paper":
        probes.update(tex=["xelatex", "--version"], latexmk=["latexmk", "-v"], inkscape=["inkscape", "--version"], pdfinfo=["pdfinfo", "-v"])
        probes["python_packages"] = ["python3", "-m", "pip", "freeze"]
    if component == "presentation":
        probes.update(node=["node", "--version"], npm=["npm", "--version"])
    for name, argv in probes.items():
        # Some version tools print on stderr (pdfinfo); record both streams.
        if run is command:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise ValueError("Cannot record tool version: " + name)
            value["tools"][name] = (result.stdout + result.stderr).strip()[:10000]
        else:
            value["tools"][name] = run(argv)
    if image:
        receipt, _ = read_json(image)
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", receipt.get("manifest_digest", "")):
            raise ValueError("Invalid resolved image receipt")
        value["images"]["texlive"] = receipt
    if npm_stage:
        npm = prepare_npm(root, config["components"][component]["cwd"], npm_stage, run)
        value["npm"] = npm
        value["staged_components"][component] = npm["staged_cwd"]
        stage=inside(root,npm_stage)
        browser=run(["node","--input-type=module","-e","import {browserPath} from './scripts/browser.mjs'; console.log(browserPath());"],cwd=stage)
        value["tools"]["browser"]=run([browser,"--version"])
        value["browser_path"]=browser
        value["fonts"]={str(p.relative_to(stage)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((stage/"assets/fonts").glob("*.ttf"))}
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("oci", "snapshot"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", default="project.json")
    parser.add_argument("--component", default="paper")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--reference", default="danteev/texlive:latest")
    parser.add_argument("--npm-stage")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.out.exists():
            raise ValueError("Runtime receipt already exists; reuse it instead of resolving twice")
        value = resolve_oci(args.reference) if args.operation == "oci" else snapshot(args.root.resolve(), args.config, args.component, args.image, args.npm_stage)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x") as stream:
            stream.write(json.dumps(value, indent=2) + "\n")
        print(json.dumps(value))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
