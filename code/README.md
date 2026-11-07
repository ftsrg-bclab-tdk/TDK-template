# Research code

Implement the project's software in `src/` and tests in `tests/`. Formal models
belong in root `proof/`; measurement workloads and their reproduction evidence
belong in root `benchmark/`. Record exact commands, hardware, datasets, seeds,
versions and units alongside the measurements. Large inputs and outputs stay
outside tracked source.

The inherited `justfile` supplies recipe names for build, test, evaluation,
robustness, reproduction and demos. Those research recipes are unconfigured and
exit with an error until replaced. `just hygiene` checks this component's source
and imported history. Root `project.json` leaves code checks disabled; enable them
only after real commands and structured test results exist. The old workflows in
`code/.github/workflows/` are retained source, not active GitHub workflows.

## Development container

From the monorepo root:

```sh
docker build --pull -t tdk-code-dev -f code/Dockerfile code
docker run --rm tdk-code-dev --list
```

The image installs the current Ubuntu packages and latest Just. Its default
command lists recipes. It does not reproduce a research result. The VS Code
configuration in `.devcontainer/` uses the same Dockerfile and a non-root user.
Record the resolved base image, installed versions and resulting image digest
when using a build as research evidence. A mutable image tag alone is insufficient.

When real reproduction is implemented, write outputs to a mounted directory:

```sh
mkdir -p code/out
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD/code/out:/out" tdk-code-dev reproduce
```

Document the paper's result-to-command mapping here once it exists, including
limits, special hardware and nondeterminism. Add DOI/citation links only after
publication is verified. The root selective-release tooling selects research
packages; the nested legacy release workflow is not the publication interface.

## License

The inherited starter code is MIT; see `LICENSE`. Select and record an appropriate
license for new research code before publishing it.
