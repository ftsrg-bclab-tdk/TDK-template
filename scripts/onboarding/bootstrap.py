"""Bootstrap checks for onboarding; no installer, CLI or implicit host changes.

The caller supplies platform facts and a command runner. Container smoke requires
an explicitly supplied immutable image reference; normal resolution selects latest
once per run and records that resolution outside this module.
"""

import re
import subprocess


def installation_plan(system, *, wsl=False):
    """Describe required capabilities without choosing a host installation policy."""
    if system == "Windows":
        return {"supported": False, "next_action": "Run onboarding inside WSL",
                "required": [], "steps": []}
    if system not in ("Linux", "Darwin"):
        return {"supported": False, "next_action": "Unsupported host platform",
                "required": [], "steps": []}
    route = "wsl" if wsl and system == "Linux" else ("macos" if system == "Darwin" else "linux")
    return {
        "supported": True, "route": route,
        "required": ["git", "python3", "gh", "docker"],
        "steps": [
            "Show the platform installation plan before installing missing tools",
            "Install missing Git, Python 3, GitHub CLI and Docker using the agreed host policy",
            "Start the selected Docker runtime and verify this user's daemon access",
            "Resolve the selected smoke image once and record its digest",
            "Execute the container smoke test against that digest",
        ],
        "runtime_choice_required": route in ("wsl", "macos"),
        "optional": "Local paper, code, proof and benchmark tools follow selected components",
    }


def check(run, *, smoke_image=None, smoke_command=(), execute_smoke=False):
    """Return bootstrap observations, never account/project readiness.

    run(argv, timeout=seconds) returns {returncode, stdout}; it must implement
    timeouts and must not use a shell. stdout is retained only for successful
    version probes. Raw errors and container output are deliberately not retained.
    Without execute_smoke, no container starts or image pulls. With it, the
    caller authorizes image pull/container execution, not installation or upgrades.
    """
    results = []

    def probe(name, argv, *, version=False, timeout=30):
        try:
            outcome = run(argv, timeout=timeout)
            code = outcome["returncode"]
            ok = type(code) is int and code == 0
            row = {"check": name, "status": "verified" if ok else "failed",
                   "exit_code": code if type(code) is int else None}
            if ok and version:
                row["version"] = str(outcome.get("stdout", "")).strip()[:1000]
        except FileNotFoundError:
            row = {"check": name, "status": "failed", "reason": "executable_missing"}
        except (OSError, TimeoutError, subprocess.TimeoutExpired):
            row = {"check": name, "status": "failed", "reason": "execution_unavailable"}
        results.append(row)
        return row["status"] == "verified"

    for name in ("git", "python3", "gh", "docker"):
        probe(name, [name, "--version"], version=True)
        if name == "python3" and results[-1]["status"] == "verified":
            match = re.search(r"Python (\d+)\.(\d+)", results[-1].get("version", ""))
            if not match or tuple(map(int, match.groups())) < (3, 11):
                results[-1].update(status="failed", reason="python_3_11_required")
    daemon = probe("docker_daemon", ["docker", "info", "--format", "{{.ServerVersion}}"], version=True)
    if not execute_smoke:
        results.append({"check": "container_smoke", "status": "pending",
                        "reason": "execution_not_requested"})
    elif not daemon:
        results.append({"check": "container_smoke", "status": "pending",
                        "reason": "daemon_unavailable"})
    elif not isinstance(smoke_image, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*@sha256:[0-9a-f]{64}", smoke_image):
        results.append({"check": "container_smoke", "status": "failed",
                        "reason": "resolved_image_required"})
    elif not smoke_command or not all(isinstance(arg, str) for arg in smoke_command):
        results.append({"check": "container_smoke", "status": "failed",
                        "reason": "explicit_smoke_command_required"})
    else:
        probe("container_smoke", ["docker", "run", "--rm", "--pull=missing",
              "--network=none", smoke_image, *smoke_command], timeout=180)
        results[-1]["image"] = smoke_image
    return {"ready": all(row["status"] == "verified" for row in results),
            "scope": "bootstrap_only", "checks": results}
