#!/usr/bin/env bash
# CI reports paper findings (exit 1), but still fails if the lint cannot run.
# Local make check-* targets keep the lint's strict exit status.
set -euo pipefail
rc=0
texlua scripts/lint.lua "$@" || rc=$?
if (( rc == 1 )); then
  exit 0
fi
exit "$rc"
