---
source:
  - https://github.com/BlackLight54/TDK-template/commit/9eda539b251b3d18472b399e2f222e6d190b54bd
  - ../../docs/TDK2025_biralati_pontozolap_hallgatoi.pdf
---

# Template review: helpfulness, restrictions and maximum-mark evidence

The template is helpful, particularly for students doing their first research project. It explains what a reviewer needs to see, supplies worked examples, and links claims to evidence. It is too restrictive where it dictates the shape or outcome of the research. Preserve its demanding standard for evidence; relax prescriptions that do not establish a rubric criterion.

The user's goal is the right organizing principle: a reviewer should readily find sound reasons to award the maximum in every category. Those reasons must survive reading the supporting argument. A clean lint run, an attractive diagram or an automated score cannot establish scientific quality by itself.

## Scope and rendered result

Reviewed the consolidated commit [9eda539](https://github.com/BlackLight54/TDK-template/commit/9eda539b251b3d18472b399e2f222e6d190b54bd), which the user selected after both fetched remote `main` branches proved older. The review worktree was fast-forwarded to this commit. No tracked template sources were edited.

- `make all`: success. `thesis.pdf` has 111 physical PDF pages.
- `make reviewer`: success. `reviewer.pdf` has 18 physical PDF pages; its empty main-text skeleton has 8 numbered pages.
- Built using `danteev/texlive@sha256:0d9a3e04eb3a6918c64c502c2129e9ffbf5ec0c55ea74f0eff277bc564ae5c41`.
- Every page was surveyed in rendered contact sheets. Representative opening pages, checklist, navigation, proof, evaluation table and figures were inspected at reading resolution. No major clipping or overlap was found in those pages. Some near-empty continuation pages need attention.
- Plan-phase lint: exit 0, 49 rules, with 32 passes, 9 checks deferred to later phases, 6 counts, 1 suggestion and 1 skipped link check. All 24 essentials are placeholders, which meets the plan-phase threshold. This is an expected structural pass for a blank template, not submission readiness.
- The lint's two existing mutation tests for an unmet requirement and a competitor meeting everything both passed, confirming that the restrictions below are implemented.
- Skim generation succeeded: 3/3 figures, 2/2 tables, 8/8 boxes, 7/7 tagged items and 3/3 theorem-like blocks detected, zero unsure items, 40 visible placeholder blocks. This is appropriate for the empty skeleton.
- The draft build has no overfull-box or unresolved-reference warnings in its final LaTeX log. It does have underfull-box and Font Awesome Unicode-map warnings. The reviewer lint flags a line-spacing estimate for the sparse skeleton as due at polish; this review has not established whether that heuristic is valid for a filled paper.

The scoring analysis uses the bundled **2025** review sheet. The guide discusses the 2026 conference. The current call could not be retrieved through the web tool, and the faculty downloads page exposes older links; applicability to 2026 remains unverified. This review does not certify deadlines or policy compliance.

## What already works

The chapter guidance explicitly quotes the top scoring bands and explains the lower bands. Contributions point to their support; assumptions and guarantees have stable labels; the evaluation checks requirements and guarantees; the conclusion closes the promises made in the introduction. This is valuable scaffolding.

The system, formal and analysis-tool evaluation tracks are already present and readable (draft PDF page 72, printed page 57). They are a substantial improvement over a purely systems-oriented template. Implementation may already be merged into Approach when it is not a contribution ([guide/05-chapter-by-chapter.tex:231](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/05-chapter-by-chapter.tex:231)), and chapter roles may span or share chapters. Do not remove that flexibility.

The running example, worked captions, closest-neighbour comparison, reproducibility instructions, source verification and reviewer-PDF checks all help. The guide distinguishes faculty requirements, advisor requirements and recommendations, and explicitly says automated review can be wrong. The reader should keep these safeguards.

## Findings and proposed repairs

### R1. High: the novelty check requires a predetermined winner

**Evidence:** [guide/05-chapter-by-chapter.tex:513,523,525](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/05-chapter-by-chapter.tex:513); [scripts/lint/rules-essentials.lua:416,429](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/scripts/lint/rules-essentials.lua:416); [scripts/lint/essentials.lua:122](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/scripts/lint/essentials.lua:122). Draft PDF pages 76-77, printed pages 61-62.

The matrix must have the student's work meet every requirement while every competitor misses at least one. The lint refuses both a non-yes cell for this work and a competitor column containing only yes cells. Explaining an unmet requirement in the limitations does not change that result. The targeted mutation tests confirmed both behaviours.

This is a useful example of one novelty argument, but an inappropriate universal condition. Two methods can satisfy the same functional requirements while differing scientifically in efficiency, guarantees, explanation, assumptions or applicability. A rigorous negative result or a new trade-off also needs an honest account. Adding a criterion solely to manufacture the desired empty cell can make the novelty argument less credible.

**Repair:** keep requirements coverage, fair comparison and evidence links mandatory. Treat absence of a distinguishing contribution as a reviewer objection requiring an explanation. Accept partial, negative and equivalent outcomes with explicit scope and evidence. Let the work's actual contribution determine whether the right comparison is a requirement matrix, a theorem comparison, an empirical finding or a trade-off plot. This does not promise top marks for every result; it makes the genuine ceiling visible early.

### R2. High: the worked freshness proof does not follow from its assumptions

**Evidence:** [guide/05-chapter-by-chapter.tex:200,210,218,225,252](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/05-chapter-by-chapter.tex:200). Draft PDF pages 69-70, printed pages 54-55. Reproduction: `clock-counterexample.json` beside this report.

The example allows registry and verifier clocks to differ by less than delta, yet asserts that a signed value accepted by `now - signedAt <= DELTA` is at most delta old in real time. These are different bounds.

Take delta=10 seconds. Let the registry's clock match true time and the verifier lag by 9 seconds, which satisfies the assumption. An old signed accumulator value is issued at true time 0; a credential in it is revoked at time 1. At true time 15 the verifier reads time 6, so the old value passes the age test. A valid old membership witness can still accompany that old signed value. Revocation is now 14 seconds old, contradicting the promised rejection after 10 seconds.

**Repair:** separate allowed snapshot age from clock uncertainty, specify timestamp semantics, and derive the actual bound. For a fixed offset uncertainty epsilon and accepted measured age tau, actual age can approach tau+epsilon. A promised bound delta needs an appropriate margin, such as tau <= delta-epsilon, plus the necessary assumptions about registry updates. Align the theorem, pseudocode, scenario and captions. Fictional measurements are acceptable in a teaching example; its reasoning must still be sound.

### R3. High: the lint rejects the guide's own evidence-link pattern

**Evidence:** [guide/05-chapter-by-chapter.tex:208,221,594](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/05-chapter-by-chapter.tex:208); [scripts/lint/rules-essentials.lua:405](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/scripts/lint/rules-essentials.lua:405). Draft PDF page 77, printed page 62.

The guide permits proving a guarantee in the approach chapter, and its completed gap matrix links directly to that theorem. The lint accepts a result label in an evaluation file or an `rq:`, `g:` or `dr:` label, but rejects a `thm:` label defined in Approach. A student who follows the worked example can fail the gate despite providing the intended evidence. A temporary student fixture run through the actual texlua lint reproduced this failure; see `theorem-evidence-lint.json`.

**Repair:** accept proved theorem-like evidence in its appropriate chapter, while keeping the separate requirement to show which claims the evaluation checks. Verify the supplied completed example as a student fixture. A reference through the guarantee is an existing workaround, but the direct theorem reference should work as taught.

### R4. Medium: a strong reference guide is hard to enter

**Evidence:** [thesis.tex:70](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/thesis.tex:70); [guide/00-start-here.tex:1](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/00-start-here.tex:1); draft PDF pages 1-6 and 35-36.

The draft opens with three pages of todos and three pages of checks, then the title and six pages of contents. "Start here" is on physical PDF page 35. Its final navigation item spills onto an almost empty page 36. Guide demonstrations and advisor-owned notes also appear in the initial todo list, including example gaps from the LaTeX tutorial.

The opening prioritizes unfinished items before explaining the student's next action. The first-week route also front-loads three repositories, submodules, synchronisation and a VM ([guide/01-getting-started.tex:14](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/01-getting-started.tex:14); [guide/02-lifecycle.tex:36](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/02-lifecycle.tex:36)). Give the student a minimum first-week outcome, such as a problem paragraph, initial sources and a consultation, with an explicit stopping point for setup. The sheer length is not itself a defect: much of the 78-page guide is useful reference material. The problem is the reading path and the mixed task list.

**Repair:** put a compact entry panel before the todo list, with links for first week, current phase, current chapter and before upload. Keep the dashboard near the front for returning students. Filter tutorial examples and advisor-maintenance notes out of the student's outstanding work. Keep the reference guide intact, and fit "Start here" on one page. These are small navigation changes with a larger payoff than cutting explanations.

### R5. Medium: some presentation conventions exceed what the rubric needs

**Evidence:** [guide/05-chapter-by-chapter.tex:295](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/05-chapter-by-chapter.tex:295); [guide/04-writing.tex:146,257](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/04-writing.tex:146); [guide/02-lifecycle.tex:149,155](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/02-lifecycle.tex:149); [scripts/lint/essentials.lua:24,56,61](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/scripts/lint/essentials.lua:24); [scripts/lint/rules-essentials.lua:465](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/scripts/lint/rules-essentials.lua:465). Draft PDF pages 54-56, 59 and 71-72.

The guide requires three research questions in a prescribed pattern, says every work has at least two components, requires adversaries and an architecture figure, and demands an example box in every main chapter. It also relegates other exported PDFs to a last resort while recommending TikZ and requiring pgfplots for plots. Some of these are prose policies; others are lint gates. They should not be described as equally enforced.

These defaults fit many of the advisors' current security and systems topics. They fit less well when the contribution is a theoretical result, an empirical discovery or a non-security analysis. Requiring an invented adversary or extra components can obscure the contribution. Redrawing a sound vector plot does not inherently improve its evidential value.

**Repair:** state the intended topic scope, keep strong defaults, and permit justified equivalent presentations. Require assumptions, scope and evidence relevant to the claims. Treat correctness, scale and robustness as evaluation prompts whose applicability must be explained, while allowing different numbers of RQs. Accept reproducible, legible vector figures from the student's existing toolchain. Use a running example where it explains a step, without making repetition a completeness condition in every chapter.

The 100-word floors for the gap, summary and future work can also penalize concise, complete arguments ([scripts/lint/essentials.lua:127](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/scripts/lint/essentials.lua:127)). Keep missing-content detection strict; make a short but evidenced section a reading check.

There is already a documented per-finding `lint-ignore` mechanism. That is useful for a local false positive, but less clear than an explicit, advisor-reviewed applicability decision for a whole research design.

### R6. Medium: calibrate the skim pass to visibility of the case for full marks

**Evidence:** [guide/02-lifecycle.tex:90](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/02-lifecycle.tex:90); [.claude/skills/reviewer-passes/personas/skim.md:15,22,32,56](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/.claude/skills/reviewer-passes/personas/skim.md:15); [.claude/skills/self-score/SKILL.md:21-25](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/.claude/skills/self-score/SKILL.md:21).

The skim pass is a good test of the user's goal. It already describes itself as a visibility check, yet asks whether the skim alone justifies maximum academic scores and produces a total out of 35. Its inputs deliberately hide ordinary prose and proof bodies. A skimmer can see that a proof is claimed and where it is, but cannot establish its validity or whether the prose is nearly error-free.

**Repair:** keep the ambitious target: every category should have an immediately visible case for its top band. Have the skim identify the visible claim, its evidence pointer and the full-reading check still required. Keep full-PDF scoring and expert verification as separate evidence. If numerical skim estimates are retained, label them as first-impression estimates and require a full-reading disposition of every unresolved concern. This preserves the maximum-marks goal while preventing polished presentation from substituting for support.

### R7. Medium: make the final inference to top-band E explicit

**Evidence:** [guide/05-chapter-by-chapter.tex:265,280-288,303](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/05-chapter-by-chapter.tex:265); [guide/06-tdk-rules-and-dates.tex:124](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/06-tdk-rules-and-dates.tex:124). Draft PDF pages 71-75 and 83.

The S/F/T tracks cover much of E well. What is still easy to miss is why the selected scale, workloads, assumptions and perturbations support the claimed practical use. More prover-time points do not by themselves establish industrial relevance. A completed scalability plot is not the same as an adequate evaluation.

**Repair:** add a short evaluation prompt: target use and scale; why the workload or model represents it; acceptance threshold; observed result; remaining limitation. Explain how formal work supplies relevant evidence without implying that verifier runtime alone proves deployability. Give the reviewer a concise answer stating how far the results support the target use.

### R8. Medium: the reproducibility deadline is contradictory

**Evidence:** [guide/02-lifecycle.tex:176](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/02-lifecycle.tex:176); [guide/08-zenodo.tex:54](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/08-zenodo.tex:54). Draft PDF pages 47 and 90.

The polish checklist requires the Docker reproduction command to regenerate the figures and tables from the named results tag. The archive chapter also allows students about two days after submission to finish the README, Docker images, results map and reproduction-limit notes. Some of that work is necessary for the reviewer to reproduce results, rather than optional polish.

**Repair:** require a working, documented minimum reproduction path before upload. Define post-upload polish as improvements that do not prevent checking the submitted results. Keep immutable results tags and clearly record what the later package adds.

### R9. Low: preserve the full rubric arithmetic and its provenance

**Evidence:** bundled review sheet, physical page 1; [guide/06-tdk-rules-and-dates.tex:120](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/06-tdk-rules-and-dates.tex:120); [.claude/skills/self-score/SKILL.md:10](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/.claude/skills/self-score/SKILL.md:10); [.claude/skills/reviewer-passes/personas/skim.md:58](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/.claude/skills/reviewer-passes/personas/skim.md:58).

B is normally the average of B/1 and B/2. The sheet also says that when B/1 is not applicable, B equals B/2. The guide and scoring summaries omit that exception. The bundled sheet is named 2025, while the guide is framed around 2026.

**Repair:** carry the exception into scoring instructions and record which year's rubric has been confirmed. This is a small, factual correction, not a reason to reopen the whole structure.

### R10. Low: remove conflicting figure advice

**Evidence:** [guide/05-chapter-by-chapter.tex:385,424](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/05-chapter-by-chapter.tex:385); [guide/04-writing.tex:269](/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb/guide/04-writing.tex:269). Draft PDF pages 59 and 74.

The scalability text tells students to put better results higher, reversing a lower-is-better axis. The formal-track verification-time example immediately below uses the conventional upward time axis, as does the earlier caption example. Each individual plot is readable, but the examples disagree about whether the rule is compulsory.

**Repair:** make orientation a choice based on the comparison. Label the direction of improvement clearly and keep related panels consistent. Do not force a reversed latency axis simply to put this work visually on top.

## Coverage of every review category

The template has no completely omitted category. Its remaining problem is how to distinguish convincing evidence from completion of the requested form.

| Criterion | Maximum | Top-band case a reviewer should be able to make | Current support and remaining improvement |
| --- | ---: | --- | --- |
| A: structure and style | 5 | The argument is easy to follow and the writing is nearly error-free. | Strong cross-references, example and style guidance. Permit the structure that explains this research best; verify full prose as well as the skim. |
| B/1: figures, tables and references | 4 before averaging | The visuals explain the work and references are accurate. | Worked figures and captions are useful. Correct the examples and prioritize legibility and provenance over drawing software. |
| B/2: literature | 4 before averaging | The comparison covers relevant research and modern industrial approaches. | Good source verification, search log and closest-neighbour work. Preserve fair comparisons when a competitor also meets the requirements. |
| C: topic | 8 | The problem is current, unresolved and requires substantial scientific investigation. | Motivation and non-triviality are prompted. Ask explicitly why existing knowledge cannot settle the question. |
| D/1: originality | 5 | The contribution is new at the sheet's stated level, with a clear difference from the closest work. | Ownership and gap are highly visible. Remove the assumption that novelty requires winning every matrix row. |
| D/2: soundness | 5 | The results are convincingly established within stated assumptions and can be checked. | Excellent claim/evidence and artifact structure. Repair the worked proof and distinguish proof, testing and reproducibility. |
| E: introduction and evaluation | 8 | The introduction is complete and the results are accurately evaluated beyond toy examples, including relevant scale and robustness. | Strongest practical scaffolding, including F/T tracks. Add the explicit inference from the chosen evaluation to the target use and its limits. |

A + B + C + D + E = 35; D = D/1 + D/2. B normally averages B/1 and B/2, with the applicability exception above. C, D and E account for 26/35 points, so the student's early effort should establish the research case and evaluation plan before polishing presentation.

## Recommended next revision

Keep the current structure of the guide. Make a focused revision in this order:

1. Repair the worked proof and theorem-reference mismatch, then remove the universal-winner condition from the matrix gate.
2. Put the route into the guide at the start, and separate tutorial/advisor notes from the student's task list.
3. Add a compact rubric-to-evidence sheet to planning and final review: criterion, top-band reason, visible location, supporting evidence, unresolved objection. This makes the intended maximum-mark case reviewable without inventing a score.
4. Clarify applicability and equivalent presentations, calibrate skim scoring, and correct the B exception, figure-policy inconsistencies and reproduction deadline.

No template content was changed during this review. The report, local renders and verification outputs are in `work/template-review/`; they are untracked review artifacts.
