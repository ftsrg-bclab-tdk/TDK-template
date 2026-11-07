#!/usr/bin/env python3
"""Explicit maintainer checks, never skeleton generation or student-text replacement."""
from pathlib import Path
import os
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci.config import load_project


def run(argv, cwd=None):
    subprocess.run(argv, cwd=cwd, check=True)


def main():
    root = Path.cwd()
    config, digest = load_project(root)
    if sys.version_info < (3, 11):
        raise ValueError("Python 3.11 or newer is required")
    repository = os.environ.get("GITHUB_REPOSITORY", config["repository"])
    if not repository or not config["repository"] or repository.lower() != config["repository"].lower():
        raise ValueError("Configure this repository identity before running CI")
    for path in [config["paper_main"], *config["paper_entrypoints"].values()]:
        if not (root/path).is_file():
            raise ValueError("Required paper source/entrypoint missing: " + path)
    print("Validated project config " + digest, flush=True)
    if config["role"] != "template":
        print("Project role: maintainer template suites do not apply", flush=True)
        return
    if repository.lower() != "ftsrg-bclab-tdk/tdk-template":
        raise ValueError("Template role is reserved for canonical repository; initialize this copy as project")
    mode = sys.argv[1]
    if mode == "source":
        for suite in ("scripts/ci","scripts/external_inputs","scripts/onboarding/tests","scripts/release",
                      "scripts/readme","scripts/maintenance","scripts/overleaf","benchmark","proof",
                      "code/scripts/tests","scratch/scripts/tests"):
            run([sys.executable,"-m","unittest","discover","-s",suite,"-v"])
        run([sys.executable, "proof/acceptance.py"])
    elif mode == "paper":
        paper = root/"paper"
        if not (paper/"draft.pdf").is_file() or not (paper/"final.pdf").is_file():
            raise ValueError("Maintainer paper tests need the already-built PDFs")
        for path in (paper/"content").glob("0[1-7]-*.tex"):
            if path.read_bytes() != (paper/"scripts/lint/skeleton"/path.name).read_bytes():
                raise ValueError("Template skeleton differs: " + path.name)
        essentials = subprocess.check_output(["texlua","scripts/lint.lua","essentials","--guide"],cwd=paper)
        if essentials != (paper/"guide/essentials.tex").read_bytes():
            raise ValueError("Generated essentials differ")
        run(["texlua","scripts/lint.lua","criteria"],paper)
        run(["make","test"],paper)
    else:
        raise ValueError("Unknown template check mode")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(1)
