#!/usr/bin/env python3
"""Fault injection: crashed count/essentials rules stay visible on the Checks page."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def lint(folder, *args):
    command = ["texlua", "scripts/lint.lua", *args]
    env = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_")}
    env["LINT_OFFLINE"] = "1"
    if not shutil.which("texlua"):
        command = ["docker", "run", "--rm", "--network=none", "-u", f"{os.getuid()}:{os.getgid()}",
                   "-e", "HOME=/tmp", "-e", "LINT_OFFLINE=1", "-v", f"{folder}:/w", "-w", "/w",
                   os.environ.get("LINT_IMAGE", "danteev/texlive:latest"), *command]
    return subprocess.run(command, cwd=folder, env=env, capture_output=True, text=True)


for rule, filename in (("essentials", "rules-essentials.lua"), ("placeholders", "rules-source.lua")):
    with tempfile.TemporaryDirectory(prefix="tdk-execution-") as tmp:
        folder = Path(tmp)
        for name in ("scripts", "content", "include", "bib", "guide"):
            shutil.copytree(ROOT / name, folder / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(ROOT / "thesis.tex", folder / "thesis.tex")
        source = folder / "scripts/lint" / filename
        text = source.read_text()
        start = text.index(f'rule("{rule}",')
        at = text.index("function()", start) + len("function()")
        source.write_text(text[:at] + '\nerror("injected execution failure")\n' + text[at:])
        result = lint(folder, rule, "--json")
        assert result.returncode == 2, result.stderr
        data = json.loads(result.stdout)
        assert not data["ok"]
        assert next(r for r in data["rules"] if r["rule"] == rule)["status"] == "error"
        page = lint(folder, "overleaf", "--tex")
        assert page.returncode == 2, page.stderr
        assert "did not run" in page.stdout
        assert "injected execution failure" in page.stdout
        assert f"\\texttt{{{rule}}}" in page.stdout
        assert f"\\PackageWarningNoLine{{tdk-lint}}{{{rule}:" in page.stdout
        if rule == "essentials":
            assert "Essentials unavailable" in page.stdout
            assert "0 elements every paper" not in page.stdout
            assert "The paper at a glance" not in page.stdout
        print(f"ok: {rule} crash exits 2, reports JSON error and stays visible on the Checks page")
