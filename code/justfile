# The recipes the paper and CI run. Name them after the paper: fig-scalability makes Figure 5.2.
# Every recipe that produces a number writes a CSV into out/ that the paper's pgfplots reads.
# out/ is never committed. The results the paper reports are committed under experiments/, and
# no recipe overwrites them; `just check` compares a fresh run with them.

set shell := ["bash", "-euo", "pipefail", "-c"]
# The runtime image sets OUT=/out, the directory `docker run -v "$PWD/out:/out"` mounts.
out := env("OUT", "out")

default:
    @just --list

# Build the system and its tools.
build:
    @echo "TODO build"

# The test suite; fails the CI on the first red test.
test:
    @echo "TODO run the tests"

# Correctness: the running example and every requirement case (Table 5.1).
evaluate: build
    mkdir -p {{out}}
    @echo "TODO evaluate -> {{out}}/correctness.csv"

# hyperfine repeats every run and records mean and spread per input size.
# Scalability: time as the input grows (Figure 5.2). `smoke` makes 2 runs per size instead of 10.
benchmark smoke="": build
    mkdir -p {{out}}
    hyperfine --warmup 1 --runs {{ if smoke == "" { "10" } else { "2" } }} \
      --parameter-list size 10,100,1000 --export-csv {{out}}/scalability.csv \
      'echo TODO replace with the command to time on input size {size}'

# Robustness: faults, adversarial input, load spikes, parameter sweeps (Table 5.4, Figure 5.4).
robustness smoke="": build
    mkdir -p {{out}}
    @echo "TODO robustness smoke={{smoke}} -> {{out}}/robustness.csv"

# Everything the paper shows, in one go. `just reproduce --smoke` runs reduced workloads.
reproduce *flags: evaluate (benchmark flags) (robustness flags)
    @echo "regenerated into {{out}}/"

# Timings differ on every machine; verdicts, counts and sizes must match exactly.
# Compare a fresh run in out/ with the results committed under experiments/, ignoring timings.
check:
    @echo "TODO diff {{out}}/ against the committed results in experiments/, ignoring wall-clock columns"

# The demonstration, recorded programmatically with captions; never by hand (see demo/).
demo: build
    mkdir -p {{out}}/demo
    @echo "TODO run demo/record.sh -> {{out}}/demo/"

# What must not reach a public repository: private links, local paths, paper sources, agent
# commit identities and agent files in the archive. `--publish` is the gate before the Zenodo release.
hygiene *flags:
    python3 scripts/hygiene.py {{flags}}

# The figures of the paper from the CSVs, if they are not drawn by pgfplots in the paper itself.
figures:
    @echo "TODO"
