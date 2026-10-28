# Independent student-facing review of the FTSRG TDK template

Reviewed commit: `9eda539` in `/home/blacklight/.t3/worktrees/tdk-template/t3-3bd95abb`.

## Verdict

The template is helpful, especially for a first measured systems or security paper. Its strongest feature is making the route from a claim to evidence explicit. It is too restrictive where it turns one successful research story into the admission condition for every paper. I recommend a substantive revision before treating it as a general template for theoretical, empirical and systems TDK work. Keep the evidential standard; relax the prescribed shape of the result and the means of presenting it.

The intended outcome should be that the paper makes its deserved maximum score easy to verify. A comparison whose winning column is prescribed in advance and a skim score that cannot inspect the proofs work against that outcome.

This review read AGENTS.md, the guide and student chapter files, relevant reviewer skills/personas, and lint/CI implementation. It does not assess PDF appearance; the parent is doing the builds and visual inspection. No source edits, commits, PRs, delegation or external messages were made. The only file written for this review is this report. P1 means repair before general rollout; P2 means a material student or evidence problem; P3 means a smaller avoidable burden. Findings distinguish implementation mismatches from explicit advisor policy.

## Severity-ranked findings

### 1. P1: The required gap matrix prescribes victory, excluding honest trade-offs and some strong contributions

Locations: `guide/05-chapter-by-chapter.tex:513`, `guide/05-chapter-by-chapter.tex:523`, `guide/05-chapter-by-chapter.tex:525`; `scripts/lint/essentials.lua:122`; `scripts/lint/rules-essentials.lua:416`, `scripts/lint/rules-essentials.lua:429`.

This is explicit advisor policy implemented faithfully. The guide requires the sole column satisfying every requirement, an empty positioning cell occupied by this work, and a gap closed by its results. At polish/submit, lint rejects any unmet requirement in this work and any competitor satisfying them all.

A student who finds a substantial speed/space trade-off, proves an existing algorithm correct under weaker assumptions, discovers a limitation, or publishes a careful negative result cannot necessarily tell this story honestly. Even a new system may improve an established solution without having a unique all-green feature column. The incentives are to choose requirements after seeing the results, omit a competitor's strengths, relabel aspirations as exclusions, or make the contribution seem stronger than the evidence warrants. These are risks to D/1 and D/2, rather than mere stylistic inconvenience.

Strong counterevidence: every requirement needs an evidence pointer; limitations are required; the panel checks overclaiming; the sheet explicitly rewards novelty (`guide/06-tdk-rules-and-dates.tex:122`). These are valuable safeguards. They do not establish that novelty entails feature dominance, and the sheet also recognises valuable incremental contributions. A different substantive result can deserve a high score without this matrix shape.

Minimal recommendation: keep complete, evidenced comparisons as requirements. Make all-green dominance and the empty-cell positioning diagram one recommended pattern. Permit partial/negative cells with an explicit trade-off or result statement, and flag an all-green competitor for human novelty review rather than making it a universal failure. Do not weaken the requirement to explain exactly what is new.

Verification: an in-memory fixture run through the actual `gapmatrix()` function rejected a `gappartial` result cell even though it pointed to an evaluation result. No files were changed for the fixture.

### 2. P1: A student following the worked example gets an invalid-evidence lint failure

Locations: `guide/05-chapter-by-chapter.tex:208`, `guide/05-chapter-by-chapter.tex:221`, `guide/05-chapter-by-chapter.tex:594`; `scripts/lint/rules-essentials.lua:400`, `scripts/lint/rules-essentials.lua:405`.

This is an implementation mismatch. The guide allows guarantees to be proved in the approach chapter. Its completed gap-matrix example cites `thm:guide:stale`, which is proved there. Following the copying instructions at `guide/05-chapter-by-chapter.tex:4` yields a reference to `thm:stale` in that chapter.

`result_problem()` accepts a label defined in an evaluation-role file, or an `rq:`, `g:` or `dr:` label. It rejects the theorem in the approach. Thus a stronger, direct evidence pointer is rejected in favour of an indirect research-question or guarantee reference. A novice may move or duplicate the proof to satisfy a tool rather than follow the guide's argument structure.

Strong counterevidence: citing the corresponding guarantee or RQ is a supported workaround. Multiple chapter roles are also supported. Neither is an obvious repair for a student who copied the supplied example, and marking a whole method chapter as evaluation just to permit its theorem is unnecessary.

Minimal recommendation: accept references to proved theorem-like results wherever they belong in the paper, preserving any separate evaluation traceability check. Add a check that copies the guide's completed matrix into a student fixture and verifies its evidence links.

Verification: actual Lua `gapmatrix()` on an in-memory fixture returned `thm:main is not an evaluation result` when `thm:main` was in the approach. This used Lua 5.4 with a read-only filesystem shim because texlua/lfs were unavailable on the host; it was a function-level reproduction, not a full lint/build run.

### 3. P2: The supported topic boundary is narrower than the universal requirements suggest

Locations: `guide/02-lifecycle.tex:42`, `guide/02-lifecycle.tex:44`, `guide/02-lifecycle.tex:53`; `guide/05-chapter-by-chapter.tex:269`, `guide/05-chapter-by-chapter.tex:280`, `guide/05-chapter-by-chapter.tex:295`; `scripts/lint/essentials.lua:64`, `scripts/lint/essentials.lua:69`, `scripts/lint/essentials.lua:89`; `scripts/lint/rules-essentials.lua:501`, `scripts/lint/rules-essentials.lua:574`.

This is an advisor-scope decision, with a missing adaptation route. The S/F/T alternatives exist and are useful. But F is principally tool-assisted formal verification with model-size runtime experiments; T is benchmarked analysis software. A pen-and-paper theory result, a non-security modelling result, or an empirical study of existing systems still inherits an architecture figure, adversaries, guarantees, a working implementation, test suite, code archive, and three fixed evaluation questions. Some of those may be inappropriate rather than merely difficult.

For example, verification time versus lemma count need not be a meaningful scalability study of a mathematical theorem. An observational empirical paper should derive its questions from its study, rather than invent an artifact that "solves" its observations. The universal constraints invite artificial experiments and security terminology.

Strong counterevidence: F/T genuinely adapt the evidence, the mean mathematician covers pen-and-paper proofs, implementation can be merged into approach (`guide/05-chapter-by-chapter.tex:231`), roles can be merged/split (`guide/09-latex-template.tex:79`), and the sheet's top E band really does request scalability and robustness (`guide/06-tdk-rules-and-dates.tex:124`). Do not remove those dimensions for a system claiming industrial applicability. Also do not promise that an unsuitable topic automatically earns the faculty's top band.

The generic escape hatch is incomplete: `lint-ignore` is documented at `guide/09-latex-template.tex:41`, but requires a finding's file and line (`scripts/lint/lintcore.lua:291`). A completely missing essential has no `where.line`, so its failure at `scripts/lint/rules-essentials.lua:572` cannot be waived by placing the advertised comment beside the natural insertion point. Keeping a dummy item merely to suppress it is a poor adaptation method.

Minimal recommendation: state the template's supported scope at topic selection, and let advisors approve a short mapping from the actual contribution to required evidence. Make genuinely inapplicable structures explicit and traceable, including a usable waiver for an absent item. Allow the number and wording of RQs to follow the work while retaining coverage of relevant correctness, scale and robustness questions.

### 4. P2: The skim pass conflates visible support with a justified maximum score

Locations: `guide/02-lifecycle.tex:90`, `guide/02-lifecycle.tex:92`; `guide/05-chapter-by-chapter.tex:17`; `.claude/skills/reviewer-passes/personas/skim.md:12`, `.claude/skills/reviewer-passes/personas/skim.md:22`, `.claude/skills/reviewer-passes/personas/skim.md:32`, `.claude/skills/reviewer-passes/personas/skim.md:47`.

This is an explicit evaluation policy, not a claim that structural lint establishes quality. The skim persona is told to decide whether the skim alone justifies maximum marks on every category, including technical correctness, while unread prose, equations and listings carry no evidence. The chapter guide tells students to repeat claims from unmarked sections in retained items. A fully tagged correctness table can therefore make a proof look supported without allowing the reader to check its steps, abstraction or assumptions. Conversely, coherent technical exposition can be penalised because it contains mostly paragraphs.

Strong counterevidence: the persona explicitly calls itself a visibility gate, not a correctness gate (`skim.md:15`); the full-PDF self-score reads the whole paper (`.claude/skills/self-score/SKILL.md:21`); the panel checks actual reasoning; the skim loop is capped at three passes. These substantially reduce the risk. The remaining problem is the incompatible request for a score justified by evidence the persona is forbidden to see.

Minimal recommendation: have the skim pass decide whether the claim, scope, contribution and route to checking the evidence are visible. Mark substantive correctness/novelty as "requires full reading" rather than forcing another packaging repair to achieve a maximum. Let full-PDF review determine deserved marks. Keep the skim as a communication diagnostic.

### 5. P2: The novice route front-loads infrastructure without defining the smallest useful first week

Locations: `guide/01-getting-started.tex:4`, `guide/01-getting-started.tex:14`, `guide/01-getting-started.tex:20`, `guide/01-getting-started.tex:60`, `guide/01-getting-started.tex:62`; `guide/02-lifecycle.tex:33`, `guide/02-lifecycle.tex:36`.

This is advisor workflow policy. A beginner told to work through the first-week chapter in order encounters three repositories, recursive submodules, Overleaf synchronisation, Zotero integration, calendar sharing and a reachable VM before the guide's first research milestone. The lifecycle makes the VM and repository topology completion conditions, even when Overleaf and an existing machine suffice to start. A warning not to overdo setup does not tell a novice which tasks can wait or how to recover when submodule and Overleaf state diverge.

Strong counterevidence: ownership is unusually clear; advisors create the Overleaf project; the templates supply much of the tooling; the guide says to limit setup time at line 64. Linux, editors and agent harnesses are recommendations, not enforceable OS requirements, and should not be reported as such.

Minimal recommendation: add a short minimum route with a concrete first artifact: open the paper, set the title, write a problem paragraph, save the first sources, arrange consultation. Put VM/local build/submodule sophistication behind a point-of-need step or have advisors provision it. Keep version control, provenance and weekly summaries.

### 6. P2: Reproduction is due before upload and also explicitly allowed to remain unfinished after it

Locations: `guide/02-lifecycle.tex:57`, `guide/02-lifecycle.tex:74`, `guide/02-lifecycle.tex:176`; `guide/07-code-tools-checks.tex:52`, `guide/07-code-tools-checks.tex:67`; `guide/08-zenodo.tex:54`.

This is conflicting advisor guidance. Polish requires `docker run ... reproduce` to regenerate the results from the named results tag, and the README's first command must select its image. Yet the archive chapter gives students about two days after upload to finish the README, Docker images, results map and reproduction-limits section. Those are the instructions a reviewer needs to check the paper, not merely later packaging. With the concept DOI opening the latest release, two reviewers arriving on different days can see materially different readiness.

Strong counterevidence: the results tag must remain immutable, a pre-upload archive is already required, and post-upload prose says reviewers may have looked. Those preserve the identity of the measurements. They do not resolve whether the runnable reproduction path is a submission prerequisite.

Minimal recommendation: require a tested minimal reproduction command, results map and stated limits at the results tag before upload. Reserve post-upload work for extra examples, documentation polish and presentation/demo packaging. Preserve the immutable results-tag policy and later releases.

### 7. P2: The completed worked proof states a freshness bound its clock assumption does not establish

Locations: `guide/05-chapter-by-chapter.tex:200`, `guide/05-chapter-by-chapter.tex:219`, `guide/05-chapter-by-chapter.tex:225`, `guide/05-chapter-by-chapter.tex:255`.

This is a pedagogical correctness defect. The clock difference is less than delta, and the acceptance test permits a measured age up to delta. That does not imply a real age below delta: clock error consumes additional freshness budget. For delta = 2 seconds, a registry clock 1.5 seconds ahead signs a value at real time 0 with timestamp 1.5. At real time 3 an accurate verifier measures age 1.5 and accepts it. The clock-difference assumption holds, but the accepted value is 3 seconds old, contradicting the fresh-values lemma. If revocation happened at real time 0.1, an old accumulator snapshot can retain a valid pre-revocation witness beyond the promised 2 seconds; ordinary accumulator soundness does not revoke an old signed snapshot.

Strong counterevidence: the paper and its numbers are explicitly fictional (`guide/05-chapter-by-chapter.tex:6`). The objection is not that illustrative results lack a real experimental archive. The guide supplies this as a completed proof for students to learn from and copy, and the error changes its logical bound.

Minimal recommendation: separate clock error epsilon from allowable staleness Delta and account for both in the acceptance test and theorem. State the snapshot-specific accumulator assumption precisely. Alternatively label the proof as an incomplete outline whose timing argument still needs checking. Keep the explicit assumptions and proof trace.

Verification: a read-only Python arithmetic check confirmed clock difference 1.5 < 2, measured age 1.5 <= 2, actual age 3 > 2.

### 8. P2: Per-element prose floors can force filler even when concise evidence is complete

Locations: `scripts/lint/essentials.lua:127`, `scripts/lint/essentials.lua:133`, `scripts/lint/essentials.lua:143`; `scripts/lint/rules-essentials.lua:74`, `scripts/lint/rules-essentials.lua:204`; `guide/05-chapter-by-chapter.tex:603`, `guide/05-chapter-by-chapter.tex:621`.

This is explicit advisor policy encoded as a hard polish/submit gate. The gap, summary and future-work elements each require 100 own prose words; floats, tagged lists and example boxes do not count. A precise gap sentence with a complete cited matrix, or a short future-work paragraph explicitly linked to tagged limitations, can therefore fail despite doing its job. Adding language to clear the threshold uses the same scarce 30–35 pages needed for the substantive evidence. The concern is the hard lower bound, not that structural checks pretend to measure scientific quality.

Strong counterevidence: the thresholds are openly documented (`guide/essentials.tex:6`), skeleton text is excluded, and these floors catch abandoned outlines. They are not per-chapter word budgets, and some explanatory prose really is needed. The question is whether a length heuristic should overrule a completed argument in every case.

Minimal recommendation: make below-floor prose an advisory finding once the element has evidence and references, or support an explicit concise-but-complete disposition. Keep missing elements, untouched skeletons and missing trace links as gates. Let the advisor assess whether the short element is adequate.

### 9. P3: Figure instructions prescribe tools and visual conventions beyond the readability requirement

Locations: `guide/04-writing.tex:257`; `guide/02-lifecycle.tex:155`; `guide/05-chapter-by-chapter.tex:385`, `guide/05-chapter-by-chapter.tex:525`.

This is mainly advisor presentation policy, with inconsistent wording. The prose recommends TikZ, permits SVG and calls other PDF exports a last resort; the requirements table restricts figure sources to TikZ or SVG apart from justified rasters. A reproducibly generated vector PDF plot can be perfectly readable while violating that stated source-format rule. Requiring higher-is-better display, reversed latency axes, and exactly two positioning axes with three levels each adds work that is not necessary for the faculty's B/1 top band. A property lattice or continuous trade-off plot may communicate a theoretical or empirical contribution better.

Strong counterevidence: ownership colours, sharp text, reproducible plot generation and labelled units are useful. SVG is supported, raster exceptions exist, and the lint mostly warns rather than gates on these conventions. This is not a claim that matplotlib output automatically breaks CI. The dependency-graph option also gives genuine freedom for the leading figure.

Minimal recommendation: require readable, editable/reproducible figure sources and clear ownership. Present TikZ/pgfplots, reversed axes and the 3x3 positioning grid as defaults/examples. Explicitly allow a generated vector PDF when it meets the same checks.

## Strengths to preserve

- `guide/00-start-here.tex:12` distinguishes faculty requirements, advisor requirements, recommendations and options; `guide/02-lifecycle.tex:128` adds source, checker and due phase. This is much clearer than an undifferentiated checklist.
- The problem → contribution → evidence → conclusion chain is explicit and actionable (`guide/05-chapter-by-chapter.tex:81`, `guide/05-chapter-by-chapter.tex:309`, `guide/05-chapter-by-chapter.tex:612`). Requirements and guarantees have stable references rather than repeated inconsistent prose.
- The actual S/F/T table and formal/tool alternatives are substantive (`guide/05-chapter-by-chapter.tex:269`). Formal verification gets timeouts, assumptions and attacks; analysis tools get ground truth, precision/recall and independent benchmarks. Their existence is not a finding to fix.
- The guide already calls essentials structural and publishes their thresholds (`guide/essentials.tex:6`). The issue is which structures/outcomes are universal gates, not an absent disclaimer about lint quality.
- The formal-methods persona asks about vacuity, reachability, deliberately broken variants and trusted assumptions (`.claude/skills/reviewer-passes/personas/formal-methods.md:18`). The empiricist asks about baseline fairness, repetitions and variance (`personas/empiricist.md:16`). These defend deserved marks.
- Weekly meetings are encouraged precisely when students are blocked, and the guide offers to write an unclear first problem paragraph together (`guide/03-weekly-consultations.tex:6`, `guide/04-writing.tex:7`). Preserve that supportive route and optional consultation slides.
- Draft and reviewer builds are separated; `make check-submit` forces the submission phase (`Makefile:43`). Tool failures are distinguished from a passed check. Students are warned that hidden todos do not make a finished paper.
- Immutable results tags, verified CI bundles and read-only reviewer defaults protect reproducibility and student ownership (`guide/08-zenodo.tex:52`, `guide/07-code-tools-checks.tex:38`, `AGENTS.md:40`).

The two changes most likely to improve the outcome are allowing honest comparative results instead of mandatory dominance, and separating skim visibility from the substantive judgment that maximum marks are deserved. The theorem-reference mismatch is the clearest immediate implementation repair.
