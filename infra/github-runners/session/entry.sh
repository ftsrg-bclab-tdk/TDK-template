#!/bin/bash
set -euo pipefail
# The host socket accepts only this session UID; there are no external IP routes.
/infra/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 \
  --library-path /infra/usr/lib/x86_64-linux-gnu /infra/usr/bin/socat \
  TCP4-LISTEN:3128,bind=127.0.0.1,reuseaddr,fork UNIX-CONNECT:/run/egress.sock &
relay=$!
trap 'kill "$relay" 2>/dev/null || true' EXIT
jit=$(cat /run/jit)
./run.sh --jitconfig "$jit"
