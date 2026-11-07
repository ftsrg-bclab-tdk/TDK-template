#!/usr/bin/env python3
"""CI accepts paper findings, while preserving execution failures and output."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]

with tempfile.TemporaryDirectory(prefix="tdk-ci-") as tmp:
    texlua = Path(tmp) / "texlua"
    texlua.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\nprintf "diagnostic\\n" >&2\nexit "$TEST_LINT_RC"\n')
    texlua.chmod(0o755)
    for status in (0, 1, 2, 127, 139):
        result = subprocess.run(
            ["bash", "scripts/lint-ci.sh", "all", "--doc", "reviewer"], cwd=ROOT,
            env={**os.environ, "PATH": tmp + os.pathsep + os.environ["PATH"], "TEST_LINT_RC": str(status)},
            capture_output=True, text=True,
        )
        assert result.returncode == (0 if status == 1 else status), result
        assert result.stdout == "scripts/lint.lua\nall\n--doc\nreviewer\n", result.stdout
        assert result.stderr == "diagnostic\n", result.stderr
        print(f"ok: lint exit {status} -> CI exit {result.returncode}, output preserved")
