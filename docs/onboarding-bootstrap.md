# Bootstrap integration preparation

`scripts/onboarding/bootstrap.py` is an orchestration building block, not a
complete setup command or installer. It requires Git, Python 3, GitHub CLI and
Docker. Component-specific local toolchains remain optional. Platform plans
cover Linux, WSL and macOS; native Windows directs the student to WSL.

The platform plan deliberately leaves Docker runtime installation to the agreed
host policy. It neither selects Docker Desktop nor changes group membership,
starts services, upgrades hosts or exposes a shared Docker socket to CI.

The caller supplies a command runner with bounded timeouts. Version checks and
daemon access alone cannot report bootstrap readiness: a successful container
smoke is required. Container execution is explicit. Resolve the chosen latest
smoke image once per run, pass its digest reference and command to the checker,
and retain the resolution/platform evidence in the outer report. This is runtime
identity, not a committed source pin. The container gets no host mounts and no
network; pulling its image can still use the network. Do not run this operation
when the enclosing onboarding command is in dry-run mode.

The result covers bootstrap capabilities only. It does not establish GitHub
authentication, repository permissions, account ownership or project readiness.
The runner and outer report must identify the actual Docker context/platform;
the module does not infer a local daemon from a successful remote Docker context.

Account logic remains the unchanged canonical component from commit
`51a46c42245f701795f0d935aa68b610cc803497`. Connect its structured prompts and
accepted-answer state to atomic local persistence in the eventual entrypoint.
Do not duplicate its account validation or treat account format as access proof.

The working terminal entrypoint and explicit package/workspace/GitHub adapters are
in `scripts/setup.py`; see `docs/onboarding-orchestration.md`. Python 3.11+ is the
shared runtime minimum. Installation or a successful version probe is never a
substitute for daemon/container execution. No real host installation or remote
provisioning was performed during implementation; package and mutation adapters
were exercised with injected service responses.
