# Optional proof and verification tools

Status: draft proposal for the monorepo plan. Official sources checked on 2026-11-03. The profiles, commands, examples, and CI policy below are proposed; this report does not implement or test them.

Accepted policy: resolve the latest selected tooling for each run and record actual versions/digests/solver dependencies in evidence. Reuse that resolution within the run. Tool compatibility and limitations still apply; unsupported combinations must be reported rather than silently counted as verified. This does not require committed toolchain pins.

Keep `proof/` optional and let each project select the tools needed for its claims. A protocol model, an implementation contract, and a mathematical theorem establish different results. Record the relationship between the artifact and the paper's claim, including assumptions, abstractions, and bounds.

## What a successful result establishes

| Method | Scope of the result |
| --- | --- |
| Theorem proving | A stated proposition follows from definitions and accepted axioms, checked by the proof system. The correspondence to the intended problem still needs review. |
| Explicit-state model checking | The selected finite model satisfies the checked properties after exploration completes. A fixed model size does not establish correctness for every size. |
| Bounded checking | No violation exists within the checked input and execution bounds. A stronger claim needs completeness evidence, such as successful unwinding checks, or a separate inductive argument. |
| Automated deductive verification | Code satisfies specified contracts under the verifier's semantics and assumptions. Contracts, loop invariants, auxiliary lemmas, and library specifications may require substantial author effort. |
| Symbolic protocol verification | Security properties hold in a symbolic protocol/adversary model, sometimes for unbounded sessions. This does not by itself verify a concrete cryptographic implementation. |

These categories overlap. For example, SMT solving supports several methods, and a tool can offer both bounded and deductive modes. The tool choices below provide the source evidence for these distinctions.

## Candidate profiles

All names in the first column are proposed profile identifiers.

| Profile | Suitable work and method | Limits and setup implications | Official sources |
| --- | --- | --- | --- |
| `lean` | Mathematical results, semantics, and algorithm proofs using interactive theorem proving with automation. | Local Lean/Lake toolchain. Proofs are relative to definitions and axioms; a successful build can still contain admitted proofs. Audit the exported claims' axiom dependencies. | [Kernel](https://lean-lang.org/doc/reference/latest/Elaboration-and-Compilation/), [proof validation](https://lean-lang.org/doc/reference/latest/ValidatingProofs/) |
| `tamarin` | Stateful security protocols, trace properties and equivalence; automated and interactive symbolic reasoning with unbounded role instances. | Separate local prover and its dependencies. Search may not terminate; manual lemmas and guidance may be needed. Results concern the specified symbolic model and equational theory. | [Introduction](https://tamarin-prover.com/manual/master/book/001_introduction.html) |
| `proverif` | Automated secrecy, authentication/correspondence, and equivalence analysis of symbolic cryptographic protocols, with unbounded sessions and messages. | Local tool. Abstraction can prevent proofs or produce spurious attack derivations; distinguish a reconstructed attack from an inconclusive result. | [Project](https://bblanche.gitlabpages.inria.fr/proverif/), [manual](https://bblanche.gitlabpages.inria.fr/proverif/manual.pdf) |
| `tlaplus-tlc` | Concurrent/distributed designs modeled in TLA+ or translated from PlusCal; explicit-state checking of safety and liveness. | Local Java toolchain. Commit model configuration and finite constants. State explosion limits practical models; completion for one model does not prove all instances. | [TLA+ tools](https://lamport.org/tla/tools.html), [TLC chapter](https://lamport.azurewebsites.net/tla/book-02-03-04.pdf) |
| `tlaplus-tlaps` | Machine-checked TLA+ proofs, especially inductive safety arguments beyond a single finite instance. | Separate proof system/backends and human proof effort. Its documented release does not support full temporal reasoning; do not assume arbitrary liveness proofs. | [TLAPS](https://proofs.tlapl.us/) |
| `rust-verus` | Functional correctness of supported Rust code using specifications, proof code, and SMT-based deductive verification. | Dedicated Verus/Rust/solver combination. Supports selected Rust features and libraries, not arbitrary Cargo projects; Rust/LLVM and the verifier remain trusted. | [Verus guide](https://verus-lang.github.io/verus/guide/) |
| `rust-kani` | Harness-based model checking for panics, assertions, arithmetic errors, and supported undefined behavior, including unsafe Rust. | Local Kani/Rust toolchain. Record input bounds and retain unwinding assertions. Language coverage is incomplete, including concurrency. Experimental contracts support modular reasoning; assess that mode separately from the basic bounded profile. | [Overview](https://model-checking.github.io/kani/), [bounds](https://model-checking.github.io/kani/tutorial-loop-unwinding.html), [contracts](https://model-checking.github.io/kani/reference/experimental/contracts.html) |
| `java-openjml` | Automated deductive checking of Java methods against JML contracts. | Local OpenJML and solver. Static checking and runtime assertion checking are distinct modes. Java/JML feature coverage and library specifications are incomplete; multithreaded checking is not generally available. | [Deductive verification](https://www.openjml.org/tutorial/Introduction), [feature status](https://www.openjml.org/documentation/features.shtml) |
| `java-key` | Functional verification of supported sequential Java using JML or Java Dynamic Logic, with automatic and interactive proof steps. | Local Java tool. Language/JML coverage is selective; complex obligations may need interactive work. Validate headless proof replay for the chosen examples before promising CI support. | [KeY overview](https://www.key-project.org/about/), [program verification and supported features](https://www.key-project.org/applications/program-verification/) |
| `go-gobra` | Deductive verification of annotated Go, including heap manipulation, concurrency permissions, data-race freedom, and partial correctness. | Local JVM/Viper/solver stack. Upstream calls it a prototype supporting a large subset of Go; ordinary Go compilation is not verification. Contracts and permissions require annotations. | [Repository/setup](https://github.com/viperproject/gobra), [tutorial](https://github.com/viperproject/gobra/blob/master/docs/tutorial.md) |
| `solidity-smtchecker` | Compiler-integrated verification of assertions and selected safety targets. Prefer CHC reasoning, which handles loops and unbounded transaction sequences. | Local Solidity compiler with a compatible solver. Select engine and targets explicitly. Unsupported features and external calls introduce abstractions; warnings can be inconclusive or false positives. The documented BMC engine has narrower semantics and is deprecated in the development documentation. | [SMTChecker](https://docs.soliditylang.org/en/latest/smtchecker.html) |
| `solidity-certora-local` / `solidity-certora-cloud` | SMT-based verification of smart contracts against rules and invariants written in CVL. | The GPL-3.0 local source build and credentialed hosted service are separate installation choices. Local setup has several compiler/solver dependencies. Specifications, summaries, and loop/recursion settings constrain claims; optimistic loop settings can exclude executions. | [Method](https://docs.certora.com/en/latest/docs/user-guide/index.html), [local build](https://github.com/Certora/CertoraProver), [hosted setup](https://docs.certora.com/en/latest/docs/user-guide/install.html), [options](https://docs.certora.com/en/latest/docs/prover/cli/options.html) |

TLC should be the initial TLA+ model-checking option. Apalache is a possible later profile for SMT-based bounded checks and inductive invariants; keep it separate because its execution model and configuration differ. [TLA+ tools](https://lamport.org/tla/tools.html)

## Proposed interface and installation policy

Use one small wrapper with three operations, illustrated here as `proof doctor --profile lean`, `proof smoke --profile lean`, and `proof check --profile lean`. These are interface examples, not existing commands.

- `doctor` checks the selected toolchain and reports missing or incompatible dependencies without installing anything.
- `smoke` runs the profile's supplied acceptance examples and verifies their expected outcomes.
- `check` verifies the project's explicitly selected claims, models, harnesses, or contracts.

Store profile selection and artifact paths in committed project configuration. Each adapter declares its latest-tool resolution procedure, compatible solver requirements, supported host or container route, installation instructions, resource limits, and expected result format. Keep tool-native files and commands available for debugging. A project may enable several profiles.

Install only selected profiles through explicit onboarding setup. Prefer isolated environments or containers, resolving latest images once per run and recording their digests; keep prover environments separate from the paper image. Validate Linux/WSL and the accepted macOS container route, including its actual architecture. Native macOS verifier support is not promised. Treat local Certora compilation and hosted credentials as separate onboarding steps; installing the client alone does not establish access or completed verification.

## Acceptance examples and CI

Each adapter needs a small passing example and a deliberately invalid variant that the checker rejects for the intended reason. A syntax error is not an adequate negative example.

| Profiles | Proposed smoke examples |
| --- | --- |
| Lean | A small arithmetic/inductive theorem and an invalid claim; check named theorem dependencies for admitted proofs and unexpected axioms. |
| Tamarin, ProVerif | A tiny secrecy/authentication model, an executable honest trace, and a variant that reveals the secret or permits the attack. Reachability guards against vacuous success. |
| TLC, TLAPS | A small counter/state-machine invariant with fixed TLC parameters and a violating transition; a separate small inductive proof replay for TLAPS. |
| Verus, Kani, OpenJML, KeY | A function with a meaningful contract and an incorrect implementation. Kani also needs a too-small unwind example that cannot pass as verified. |
| Gobra | A small heap update with permission and postcondition annotations, plus an invalid update or missing permission. |
| SMTChecker, Certora | A small stateful contract with an assertion/CVL invariant and a violating transaction. Check the selected engine, rule list, and actual solver results. |

A passing smoke run establishes that an adapter works, not that the student's project is verified. Keep the project's proof/model sources and configuration in `proof/`; reference implementation files in `code/` explicitly to avoid stale copies.

Run only enabled profiles in student CI, with path filters that include their implementation dependencies. The template's adapter maintenance CI exercises every profile it claims to support. Record the resolved toolchains, solvers, libraries, actions and image identities alongside source revision, configuration, assumptions/bounds, named obligations and result summary. A later same-source run can resolve newer tools and produces separate evidence.

Normalize results as verified, violated, unknown/timeout, error, or not configured. Include whether a verified result is bounded, finite-model, or deductive. An enabled profile with missing tools or no checked obligations must fail. Unknown results must not satisfy a required proof check. Unselected profiles should be visibly skipped.

Keep hosted runs separately opt-in, with an explicit source-upload policy and protected credentials. Wait for completed verification and inspect every required obligation; a successful job submission is insufficient. Certora documents this distinction in its [wait-for-results options](https://docs.certora.com/en/latest/docs/prover/cli/options.html#wait-for-results). Apply time and memory limits to local jobs, and publish full logs as CI artifacts rather than committing generated proof/build outputs.
