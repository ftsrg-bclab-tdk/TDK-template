# Formal verification

Keep models, claims, contracts and proof sources here. Reference implementation
files in `code/` explicitly and declare that dependency in `project.json`.
Choose a tool for the property being checked; no single prover is mandatory.

The [tool catalog](../docs/proof-tool-options.md) offers Lean, Tamarin, ProVerif,
TLA+, Verus/Kani for Rust, OpenJML/KeY for Java, Gobra for Go, and Solidity
SMTChecker/Certora. At present, **only the TLC profile below has an implemented
and exercised adapter**. The other entries document options and limitations;
they are not installed adapters or a claim of CI support.

## TLC finite-state invariant profile

Install Java 11+ and GitHub CLI, then run from `proof/`:

```sh
python3 tlc.py smoke --output results/adapter-smoke.json
python3 tlc.py check --model examples/tlc/Counter.tla \
  --config examples/tlc/Counter.cfg --output results/counter.json
python3 -B -m unittest discover -s . -p 'test_*.py'
```

Each invocation resolves the [latest stable TLA+ tools release](https://github.com/tlaplus/tlaplus/releases/latest)
once, downloads its `tla2tools.jar`, records release/asset IDs and SHA-256, and
uses that one JAR throughout the invocation. Smoke reuses it for both examples.
Download failure stops the run; there is no cached-version fallback. The runtime
JAR is removed afterwards; logs and result files remain. The [upstream command
documentation](https://github.com/tlaplus/tlaplus/blob/master/USE.md) describes
the native tools. No host package installer runs in this adapter.

The supported configuration subset contains `INIT`, `NEXT`, integer `CONSTANT`
assignments, and named state `INVARIANT` declarations. Unsupported constructs,
including state constraints, temporal properties and substitutions, are rejected
rather than omitted from the reported scope. Model dependencies must be sibling
`.tla` files or standard modules in the tools JAR. Expand the adapter and its
acceptance cases before claiming support for other TLC features.

The checked counter visits values 0 through 3. Its negative example has an
off-by-one transition that reaches 4 and violates `WithinBounds`; this is a real
counterexample, not a syntax error. Smoke reports adapter tests, not a verified
student project. The check result names the actual obligations, integer
constants, explored-state count, model/config hashes, Java version, tool identity
and raw process outcome. Timeout, parse failure, empty exploration or incomplete
search remains unknown and fails. Every output path must be new.

This is finite-state model checking for the supplied constants, not a proof of
every parameter value or an implementation. Read the model assumptions and TLC's
fingerprint-collision estimate in the preserved logs. One worker, a fixed seed
and fingerprint polynomial are used; Java heap is limited to 512 MiB and the
default process timeout is 60 seconds (`--timeout`, maximum 3600).

## Project configuration

Proof is disabled in the starter. To select the example, enable `components.proof`
in `project.json` and set `profiles.ordinary` to the following. Replace the model,
configuration and declared dependencies for your actual project:

```json
[{
  "name": "counter", "kind": "proof",
  "argv": ["python3", "tlc.py", "check", "--model", "examples/tlc/Counter.tla",
           "--config", "examples/tlc/Counter.cfg", "--output", "results/counter.json"],
  "timeout": 240,
  "outputs": ["results/counter.json", "results/counter.json.logs/Counter.stdout",
              "results/counter.json.logs/Counter.stderr"],
  "result_file": "results/counter.json"
}]
```

The shared dispatcher validates `component-result/v1` and binds execution to the
repository, source, configuration and runtime. Keep raw prover logs in evidence,
not tracked source. Unknown results cannot satisfy a required proof check.
Maintainer smoke coverage must include both acceptance examples whenever this
adapter is offered as supported.
