#!/usr/bin/env python3
"""Regenerate the lifecycle inventory from the paper phase and monorepo files."""
import datetime as dt
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
PHASES = {
    "topic": 1,
    "setup": 2,
    "research": 3,
    "plan": 4,
    "draft": 5,
    "polish": 6,
    "submit": 7,
}
PAPER = "paper/draft.tex"
STUB = 200


def root_path(path):
    return ROOT / path


def size(path):
    path = root_path(path)
    return path.stat().st_size if path.is_file() else -1


def exists(path):
    return root_path(path).exists()


def nonempty_dir(path):
    path = root_path(path)
    return path.is_dir() and any(path.iterdir())


def read(path):
    try:
        return root_path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def phase():
    match = re.search(r"\\newcommand\{\\lintphase\}\{(\w+)\}", read(PAPER))
    return match.group(1) if match else "plan"


def consultations():
    directory = root_path("scratch/notes/consultations")
    if not directory.is_dir():
        return []
    return sorted(name for name in os.listdir(directory)
                  if re.match(r"\d{4}-\d{2}-\d{2}.*\.md$", name))


def path_age(pathspec):
    """Days since a path changed, or None when full history cannot establish it."""
    try:
        shallow = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "--is-shallow-repository"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if shallow != "false":
            return None
        value = subprocess.check_output(
            ["git", "-C", str(ROOT), "log", "--full-history", "-1", "--format=%ct",
             "--", pathspec],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if not value:
            return None
        timestamp = dt.datetime.fromtimestamp(int(value), dt.timezone.utc)
        age = (dt.datetime.now(dt.timezone.utc) - timestamp).days
        return max(0, age)
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


def recent_path(pathspec):
    age = path_age(pathspec)
    if age is None:
        return None, f"history unavailable for `{pathspec}`"
    return age <= 14, f"latest `{pathspec}` change {age} days ago"


ROWS = [
    ("Topic manifest (anchor)", "topic", lambda: (size("scratch/notes/anchors/manifest.md") > STUB,
                                                       "scratch/notes/anchors/manifest.md")),
    ("Paper project", "setup", lambda: (exists(PAPER), PAPER)),
    ("Code project", "setup", lambda: (nonempty_dir("code"), "code/")),
    ("First consultation summary", "setup", lambda: (len(consultations()) >= 1,
                                                         f"{len(consultations())} files in scratch/notes/consultations/")),
    ("Spine (anchor)", "research", lambda: (size("scratch/notes/anchors/spine.md") > STUB,
                                               "scratch/notes/anchors/spine.md")),
    ("Running example named", "research", lambda: (bool(read(PAPER)) and not re.search(
        r"\\newcommand\{\\exname\}\{TODO", read(PAPER)), f"\\exname in {PAPER}")),
    ("Code: README, LICENSE, justfile", "plan", lambda: (
        all(exists("code/" + name) for name in ("README.md", "LICENSE", "justfile")),
        "code/README.md, code/LICENSE, code/justfile")),
    ("Code: tests", "plan", lambda: (exists("code/tests") or exists("code/test"), "code/tests/")),
    ("Paper updated in the last 14 days", "draft", lambda: recent_path("paper")),
    ("Code updated in the last 14 days", "draft", lambda: recent_path("code")),
    ("Weekly consultations kept up", "draft", lambda: (len(consultations()) >= 3,
                                                           f"{len(consultations())} summaries")),
    ("Full draft (anchor)", "polish", lambda: (size("scratch/notes/anchors/full-draft.md") > STUB,
                                                   "scratch/notes/anchors/full-draft.md")),
    ("Code: Dockerfile and .zenodo.json", "polish", lambda: (
        exists("code/Dockerfile") and exists("code/.zenodo.json"),
        "code/Dockerfile, code/.zenodo.json")),
    ("Presentation", "submit", lambda: (nonempty_dir("presentation"), "presentation/")),
]


def main():
    current_phase = phase()
    due_rank = PHASES.get(current_phase, PHASES["topic"])
    lines = [
        "# Lifecycle",
        "",
        f"Phase **{current_phase}** (from `\\lintphase` in `{PAPER}`), checked {dt.date.today()}.",
        "",
        "A row is present when its file exists and is more than a stub. Git-age rows are unknown "
        "when full path history is unavailable. Judgement stays with the consultation.",
        "",
        "| Step | Due | State | Where |",
        "|---|---|---|---|",
    ]
    failed = 0
    for step, due, check in ROWS:
        try:
            ok, detail = check()
        except Exception as exc:
            ok, detail = False, f"check failed: {exc}"
        is_due = PHASES[due] <= due_rank
        if ok is None:
            state = "unknown"
        elif ok:
            state = "present"
        elif is_due:
            state = "**missing**"
            failed += 1
            if os.environ.get("GITHUB_ACTIONS"):
                print(f"::warning::{step}: missing ({detail})")
        else:
            state = "not yet"
        lines.append(f"| {step} | {due} | {state} | {detail} |")
    output = "\n".join(lines) + "\n"
    root_path("scratch/lifecycle.md").write_text(output, encoding="utf-8")
    print(output)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(output)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
