#!/usr/bin/env python3
"""Produce the existing review bundle from the single completed paper execution."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    root = Path.cwd()
    paper = root/"paper"
    report = json.loads((root/".project/checks/paper/report.json").read_text())
    steps = {c["name"]:c for c in report["components"]["paper"]["checks"]}
    lint = root/".project/checks/paper/paper/lint.stdout"
    if lint.is_file():
        shutil.copyfile(lint,paper/"lint.json")
        shutil.copyfile(lint.with_suffix(".stderr"),paper/"lint.stderr")
    skim = subprocess.run(["python3","scripts/skim/skim.py","build",".","-o","skim","--lint","lint.json"],cwd=paper).returncode
    image = report["runtime"]["images"]["texlive"]
    argv = ["python3","scripts/review/review.py","bundle","--built",".","--lint","lint.json","--lint-stderr","lint.stderr","--skim","skim","--out","review-bundle",
            "--by","ci" if os.environ.get("GITHUB_ACTIONS") else "local","--sha",report["source"]["tested_sha"],
            "--repo",report["source"]["repository"],
            "--ref",os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME","local"),
            "--image-ref",image["requested"],"--image-digest",image["manifest_digest"]]
    for name in ("draft","final","lint"):
        argv += ["--exit",name+"="+str(steps.get(name,{}).get("raw_exit",2))]
    argv += ["--exit","skim="+str(skim)]
    if report["source"].get("dirty"):
        argv.append("--allow-dirty")
    bundle = subprocess.run(argv,cwd=paper).returncode
    if (paper/"review-bundle").exists():
        shutil.copytree(paper/"review-bundle",root/".project/review")
    return 1 if skim or bundle else 0


if __name__ == "__main__":
    sys.exit(main())
