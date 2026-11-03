# CI dependency planner preparation

`dependencies.plan(changed_paths, components, complete=True, all_scope=False)` is
a pure planning function. It runs no Git or GitHub commands and enables no job.
The workflow caller supplies a complete diff, including deleted paths and both
sides of renames, plus explicitly enabled components and their paths/dependencies.
Use `complete=False` when history or the diff is incomplete; use `all_scope=True`
for default-branch/full validation. Neither a plan nor `selected: false` is a
successful component execution.

Enabled component entries are `{"paths": ["code/*"], "depends_on": []}`. Declare
implementation dependencies for proof/benchmark consumers. Their transitive
closure determines additional work. Validate actual root paper proxy names in
the integrated configuration; test names here are synthetic fixtures. Unknown
changed paths select all enabled components instead of silently skipping work.

Dockerfiles, Dockerfile variants, `.dockerignore`, `.devcontainer/` inputs,
`devcontainer.json`, Compose files, root Makefile and CI/workflow helpers trigger
all enabled components in this initial conservative implementation. These files
are source/build inputs, not generated image artifacts. Template ownership still
comes from the maintenance baseline: a student-customized Dockerfile can contain
mixed/private data and is not automatically eligible for upstream copying.

Container integration must perform a real image build and a real execution of
the selected component smoke command, resolve latest bases/tools once per run,
and record Docker/BuildKit versions, build-input digest, image config ID, platform
and any manifest/registry digest. Distinguish a local image ID from a published
registry manifest digest. Never label a Dockerfile parse or image pull as a
successful container smoke test. Include required Dockerfile/context/.dockerignore
and related Compose/devcontainer source in selected reproduction packages.
GitHub Release immutability does not freeze a GHCR tag.

No shared host Docker socket is mounted into student jobs. The current persistent
BME runner has no supported container route; its owner must supply an independently
validated execution contract. This module changes neither runner routing nor host
installation. No integrated container smoke was run in this worktree because the
component source assembly/Dockerfiles and execution route are not yet integrated.

```sh
python3 -m unittest discover -s scripts/ci -v
```
