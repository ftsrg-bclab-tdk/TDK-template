#!/usr/bin/env bash
# Records the terminal demonstration as an asciinema cast and renders it. Replace the scripted
# session below with the real one; keep the captions.
set -euo pipefail
out=${OUT:-out}/demo; mkdir -p "$out"
cat > "$out/session.sh" <<'SESSION'
echo "# Caption: the running example, before"
echo "TODO the command that shows the problem"
sleep 1
echo "# Caption: this work: the revoked credential is rejected"
echo "TODO the command that shows the result"
SESSION
if command -v asciinema >/dev/null; then
  asciinema rec --overwrite -c "bash $out/session.sh" "$out/demo.cast"
  command -v agg >/dev/null && agg "$out/demo.cast" "$out/demo.gif" || true
else
  echo "asciinema not installed; the session script is in $out/session.sh" >&2
fi
