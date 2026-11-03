"""Bounded command execution with logs and process-group cleanup on Linux/WSL/macOS."""
import os
from pathlib import Path
import signal
import subprocess
import time


def execute(argv, cwd, log_dir, name, timeout):
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout, stderr = log_dir / (name + ".stdout"), log_dir / (name + ".stderr")
    result = {"argv": argv, "cwd": str(cwd), "raw_exit": None,
              "stdout": str(stdout), "stderr": str(stderr), "execution_status": "error"}
    proc = None
    started = time.monotonic()
    with stdout.open("xb") as out, stderr.open("xb") as err:
        try:
            proc = subprocess.Popen(argv, cwd=cwd, stdout=out, stderr=err, start_new_session=True)
            result["raw_exit"] = proc.wait(timeout=timeout)
            result["execution_status"] = "completed" if result["raw_exit"] in (0, 1) else "error"
        except subprocess.TimeoutExpired:
            result.update(raw_exit=124, reason="timeout")
        except FileNotFoundError as exc:
            result.update(raw_exit=127, reason=str(exc))
        except KeyboardInterrupt:
            result.update(raw_exit=130, execution_status="cancelled", reason="interrupted")
        finally:
            if proc:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
    result["duration_seconds"] = round(time.monotonic() - started, 6)
    return result
