"""Explicit package-install adapters. No installation on import or plan creation."""
import platform
from pathlib import Path
import shutil


def host():
    system = platform.system()
    release = platform.release().lower()
    distro = ""
    path = Path("/etc/os-release")
    if system == "Linux" and path.exists():
        for line in path.read_text().splitlines():
            if line.startswith("ID="):
                distro = line[3:].strip('"')
    return {"system": system, "distro": distro, "wsl": "microsoft" in release}


def plan(facts, runtime, which=shutil.which):
    if runtime not in {"existing", "engine", "desktop"}:
        raise ValueError("Choose existing, engine or desktop Docker runtime explicitly")
    system, distro, wsl = facts["system"], facts["distro"], facts["wsl"]
    commands, manual = [], []
    tools = [name for name in ("git", "python3", "gh") if not which(name)]
    docker_missing = not which("docker")
    if system == "Darwin":
        if runtime == "engine":
            raise ValueError("macOS needs a Linux VM runtime; select existing or desktop")
        if not which("brew"):
            manual.append("Install Homebrew using https://brew.sh/ then rerun; no remote installer is executed automatically")
        else:
            if tools:
                commands.append(["brew", "install", *["python" if x == "python3" else x for x in tools]])
            if runtime == "desktop" and docker_missing:
                commands.append(["brew", "install", "--cask", "docker-desktop"])
    elif system == "Linux" and distro in {"ubuntu", "debian"}:
        packages = tools[:]
        if runtime == "engine" and docker_missing:
            packages.append("docker.io")
        if packages:
            commands += [["sudo", "apt-get", "update"], ["sudo", "apt-get", "install", *packages]]
    elif system == "Linux" and distro == "arch":
        packages = [{"python3": "python", "gh": "github-cli"}.get(x, x) for x in tools]
        if runtime == "engine" and docker_missing:
            packages.append("docker")
        if packages:
            commands.append(["sudo", "pacman", "-S", "--needed", *packages])
    elif system == "Windows":
        raise ValueError("Run onboarding inside WSL, not native Windows")
    else:
        manual.append("No tested package adapter for this host; install Git, Python3, gh and Docker with its supported package manager")
    if runtime == "desktop" and system == "Linux":
        if wsl:
            manual.append("Install/start Docker Desktop on Windows and enable this WSL distro: https://docs.docker.com/desktop/features/wsl/ ; do not mix it with an in-distro engine")
        else:
            manual.append("Install Docker Desktop for Linux following https://docs.docker.com/desktop/setup/install/linux/")
    if runtime == "existing" and docker_missing:
        manual.append("Docker executable missing; configure an existing runtime or choose engine/desktop explicitly")
    manual.append("Start the selected runtime and establish user access manually, then run --check-bootstrap --smoke; installation alone is not readiness")
    return {"host": facts, "runtime": runtime, "commands": commands, "manual": manual}


def install(plan, runner, *, execute=False):
    if not execute:
        return {"status": "planned", "plan": plan}
    results = []
    for argv in plan["commands"]:
        code = runner(argv, timeout=900)["returncode"]
        results.append({"argv": argv, "exit_code": code})
        if code:
            return {"status": "failed", "results": results, "manual": plan["manual"]}
    return {"status": "commands_completed", "results": results, "manual": plan["manual"]}
