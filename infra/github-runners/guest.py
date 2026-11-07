#!/usr/bin/env python3
"""Consume one JIT configuration on an expendable pilot VM. Never an isolation boundary."""
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys

STATE = Path("/var/lib/tdk-runner")
RUNTIME = Path("/run/tdk-runner")
RUNNER = Path("/opt/actions-runner")
MAX_JIT_SIZE = 128 * 1024


def arm(stream):
    if os.geteuid() != 0:
        raise ValueError("root required to arm the disposable guest")
    # Atomic and persistent across reboots. A failed attempt also consumes this VM.
    (STATE / "consumed").mkdir(mode=0o700)
    raw = stream.read(MAX_JIT_SIZE + 1)
    credential = raw.strip()
    if not credential or len(raw) > MAX_JIT_SIZE or not re.fullmatch(r"[A-Za-z0-9+/=]+", credential):
        raise ValueError("invalid JIT configuration")
    user = pwd.getpwnam("runner")
    RUNTIME.mkdir(mode=0o700)
    os.chown(RUNTIME, user.pw_uid, user.pw_gid)
    fd = os.open(RUNTIME / "jit", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as dest:
        os.fchown(dest.fileno(), user.pw_uid, user.pw_gid)
        dest.write(credential)
    subprocess.run(["systemctl", "start", "tdk-runner.service"], check=True)


def run():
    if os.geteuid() == 0:
        raise ValueError("runner must not run as root")
    credential = (RUNTIME / "jit").read_text()
    (RUNTIME / "jit").unlink()
    os.chdir(RUNNER)
    # GitHub's runner accepts JIT via argv. This credential is guest-local, single-use;
    # the GitHub admin credential never reaches this VM. Do not collect process dumps.
    os.execve(str(RUNNER / "run.sh"), ["run.sh", "--jitconfig", credential],
              {"HOME": "/home/runner", "USER": "runner", "LOGNAME": "runner",
               "PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"})


def main():
    try:
        if sys.argv[1:] == ["arm"]:
            arm(sys.stdin)
        elif sys.argv[1:] == ["run"]:
            run()
        else:
            raise ValueError("expected arm or run")
    except Exception:
        # Do not dump exceptions containing stdin, argv or runner credentials.
        print("Guest start refused or failed. Destroy this pilot VM; do not reuse it.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
