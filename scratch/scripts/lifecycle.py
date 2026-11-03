#!/usr/bin/env python3
"""Regenerate lifecycle.md: the lifecycle steps that can be checked from files, by phase.

Checks are presence and size, on purpose: a row is present when its artifact exists and is more
than a stub (200 bytes). Judgement stays with the consultation. The phase comes from \\lintphase
in paper/thesis.tex. Exit status 1 when a row due in the current phase is missing.
"""
import datetime as dt, os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHASES = {"plan": 1, "draft": 2, "polish": 3, "final": 4}
STUB = 200

def size(p):
    p = os.path.join(ROOT, p)
    return os.path.getsize(p) if os.path.isfile(p) else -1

def exists(p): return os.path.exists(os.path.join(ROOT, p))

def nonempty_dir(p):
    p = os.path.join(ROOT, p)
    return os.path.isdir(p) and bool(os.listdir(p))

def read(p):
    try: return open(os.path.join(ROOT, p), encoding="utf-8").read()
    except OSError: return ""

def phase():
    m = re.search(r"\\newcommand\{\\lintphase\}\{(\w+)\}", read("paper/thesis.tex"))
    return m.group(1) if m else "plan"

def consultations():
    d = os.path.join(ROOT, "notes", "consultations")
    if not os.path.isdir(d): return []
    return sorted(f for f in os.listdir(d) if re.match(r"\d{4}-\d{2}-\d{2}.*\.md$", f))

def submodule_age(name):
    try:
        out = subprocess.check_output(["git", "-C", os.path.join(ROOT, name), "log", "-1", "--format=%ct"], text=True, stderr=subprocess.DEVNULL).strip()
        return (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromtimestamp(int(out), dt.timezone.utc)).days
    except Exception:
        return None

ROWS = [
    ("Topic manifest (anchor)", "plan", lambda: (size("notes/anchors/manifest.md") > STUB, "notes/anchors/manifest.md")),
    ("Paper submodule", "plan", lambda: (exists("paper/thesis.tex"), "paper/")),
    ("Code submodule", "plan", lambda: (nonempty_dir("code"), "code/")),
    ("First consultation summary", "plan", lambda: (len(consultations()) >= 1, f"{len(consultations())} files in notes/consultations/")),
    ("Spine (anchor)", "draft", lambda: (size("notes/anchors/spine.md") > STUB, "notes/anchors/spine.md")),
    ("Running example named", "draft", lambda: (bool(read("paper/thesis.tex")) and not re.search(r"\\newcommand\{\\exname\}\{TODO", read("paper/thesis.tex")), "\\exname in paper/thesis.tex")),
    ("Code: README, LICENSE, justfile", "draft", lambda: (all(exists("code/" + f) for f in ("README.md", "LICENSE", "justfile")), "code/README.md, LICENSE, justfile")),
    ("Code: tests", "draft", lambda: (exists("code/tests") or exists("code/test"), "code/tests/")),
    ("Paper moved in the last 14 days", "draft", lambda: ((submodule_age("paper") or 999) <= 14, f"last paper commit {submodule_age('paper')} days ago")),
    ("Code moved in the last 14 days", "draft", lambda: ((submodule_age("code") or 999) <= 14, f"last code commit {submodule_age('code')} days ago")),
    ("Weekly consultations kept up", "draft", lambda: (len(consultations()) >= 3, f"{len(consultations())} summaries")),
    ("Full draft (anchor)", "polish", lambda: (size("notes/anchors/full-draft.md") > STUB, "notes/anchors/full-draft.md")),
    ("Code: Dockerfile and .zenodo.json", "polish", lambda: (exists("code/Dockerfile") and exists("code/.zenodo.json"), "code/Dockerfile, code/.zenodo.json")),
    ("Slides", "final", lambda: (nonempty_dir("slides/tdk"), "slides/tdk/")),
]

def main():
    ph = phase(); due_rank = PHASES.get(ph, 1)
    lines = ["# Lifecycle", "", f"Phase **{ph}** (from `\\lintphase` in `paper/thesis.tex`), checked {dt.date.today()} by CI.", "",
             "A row is present when its file exists and is more than a stub. Judgement is the consultation's; this is the inventory.", "",
             "| Step | Due | State | Where |", "|---|---|---|---|"]
    failed = 0
    for step, due, fn in ROWS:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"check failed: {e}"
        is_due = PHASES[due] <= due_rank
        state = "present" if ok else ("**missing**" if is_due else "not yet")
        if is_due and not ok:
            failed += 1
            if os.environ.get("GITHUB_ACTIONS"): print(f"::warning::{step}: missing ({detail})")
        lines.append(f"| {step} | {due} | {state} | {detail} |")
    out = "\n".join(lines) + "\n"
    open(os.path.join(ROOT, "lifecycle.md"), "w", encoding="utf-8").write(out)
    print(out)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8").write(out)
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
