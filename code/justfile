# The recipes the paper and CI run. Name them after the paper: fig-scalability makes Figure 5.2.
# Every recipe that produces a number writes a CSV into out/ that the paper's pgfplots reads.

set shell := ["bash", "-euo", "pipefail", "-c"]
out := "out"

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

# Scalability: time and resource use as the input grows (Figure 5.2). `smoke` runs a small sweep.
benchmark smoke="": build
    mkdir -p {{out}}
    @echo "TODO benchmark smoke={{smoke}} -> {{out}}/scalability.csv"

# Robustness: faults, adversarial input, load spikes, parameter sweeps (Table 5.4, Figure 5.4).
robustness smoke="": build
    mkdir -p {{out}}
    @echo "TODO robustness smoke={{smoke}} -> {{out}}/robustness.csv"

# Everything the paper shows, in one go. `just reproduce --smoke` runs reduced workloads.
reproduce *flags: evaluate (benchmark flags) (robustness flags)
    @echo "regenerated into {{out}}/"

# The demonstration, recorded programmatically with captions; never by hand (see demo/).
demo: build
    mkdir -p {{out}}/demo
    @echo "TODO run demo/record.sh -> {{out}}/demo/"

# What must not reach a public repository: private links, local paths, paper sources, agent
# commit identities and agent files in the archive. Pass --strict before the repository goes public.
hygiene *flags:
    python3 scripts/hygiene.py {{flags}}

# The figures of the paper from the CSVs, if they are not drawn by pgfplots in the paper itself.
figures:
    @echo "TODO"
