# TODO Artifact for: <paper title>

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.TODO.svg)](https://doi.org/10.5281/zenodo.TODO)

Code, models and measurement scripts for the TDK paper *TODO title* (BME VIK, 2026). TODO two
sentences: what the artifact is and what it shows.

## Reproduce everything

```sh
mkdir -p out && docker run --rm --user "$(id -u):$(id -g)" -v "$PWD/out:/out" ghcr.io/<you>/<repo>:v1.0.0 reproduce
```

regenerates every figure and table of the paper into `out/`, owned by you. `just check` then
compares them with the results committed under `experiments/`, ignoring timings. With the repository cloned and the
dependencies below installed, `just reproduce` does the same, and `just reproduce --smoke` runs a
reduced workload in minutes; CI runs the smoke version on every push.

Dependencies, pinned: TODO.

## Results map

| Paper | Recipe | Output | Time on the stated hardware |
|---|---|---|---|
| Table 5.1 correctness | `just evaluate` | `out/correctness.csv` | TODO |
| Figure 5.2 scalability | `just benchmark` | `out/scalability.csv` | TODO |
| Table 5.4, Figure 5.4 robustness | `just robustness` | `out/robustness.csv` | TODO |

Hardware: TODO (cores, memory, OS); versions: TODO.

## What does not reproduce

TODO Anything that needs a secret, special hardware, a long run or is nondeterministic, with the
seed policy and the expected variance. This section stays even when it says everything reproduces
with fixed seeds.

## Results tag

The numbers in the paper come from tag `v1.0.0`, Zenodo version TODO. Later versions change the
packaging, never the results.

## Demo

`just demo` records the demonstration programmatically, a Playwright script for a web UI or an
asciinema cast for a terminal, with captions, and CI publishes it as an artifact on every push
(see `.github/workflows/demo.yml`). Nothing is recorded by hand.

## Cite

TODO BibTeX of the paper and of this artifact (the concept DOI).

## License

MIT, see `LICENSE`. For a tool meant to be used after the paper, switch to Apache 2.0 and add
`MAINTAINERS.md` and `SECURITY.md` (see the guide's README section).

<!--
## Tool README, if this is a tool and not only the paper's results
### Install
### Use it on your own input (one worked example)
### Contribute
### Maintainers
-->
