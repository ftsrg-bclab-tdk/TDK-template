#!/usr/bin/env python3
"""Assert essentials row levels and reasons from actual lint JSON, without a PDF build.

Run `python3 scripts/lint/tests/evidence.py [source-or-built-dir]` on the host (Docker)
or in CI (texlua). --scripts-ref be1c433 replays against the audited baseline;
--work-dir retains fixtures and JSON receipts, --report writes a machine-readable result.
The fixtures reuse mutations.py's public edit helpers; no source file is modified in place.
"""
import argparse
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

import mutations as m

TEMPLATE = Path(__file__).resolve().parents[3]
RELATED = "content/06-related-work.tex"
INTRO = "content/01-introduction.tex"
APPENDIX = "content/10-appendices.tex"
SC = r"\gapyes\,(\cref{sec:scalability})"
ROW = r"\ref{req:second} & Unlinkable checks & \gapno & \gapyes & " + SC + r" \\"
CASES = []


def case(name, edit, row="gapmatrix", level=4, reason="", checks=(), diagnostic=""):
    CASES.append((name, edit, [(row, level, reason), *checks], diagnostic))


def gap(name, *edits, level=4, reason="", checks=(), diagnostic=""):
    case(name, m.both(m.filled_gap, *edits), level=level, reason=reason,
         checks=checks, diagnostic=diagnostic)


def pointer(key):
    return m.sub(RELATED, SC, rf"\gapyes\,(\cref{{{key}}})")


def bib(typ, fields):
    return m.append("bib/references.bib", "@" + typ + "{art,\n  title = {The code},\n  " + fields + "\n}")


def artifact(name, typ, fields, level=4, reason="own artifact"):
    case(name, m.both(m.replace_line(m.EVAL, m.SETUP,
         m.words(120) + r" The code is archived~\cite{art}."), bib(typ, fields)),
         "setup", level, reason,
         diagnostic="Artifact identity and version need human review" if level == 4 else "")


gap("gap-filled-baseline", diagnostic="heuristic section pointer")
for key in ("ch:evaluation", "ch:background"):
    gap("gap-" + key.replace(":", "-"), pointer(key), level=3,
        reason=key + " is not an evaluation result")
gap("gap-second-evaluation-chapter", m.second_evaluation, pointer("ch:evaluation:more"),
    level=3, reason="ch:evaluation:more is not an evaluation result")
for key in ("sec:setup", "sec:validity"):
    gap("gap-heuristic-" + key[4:], pointer(key), diagnostic=key + " is a heuristic section pointer")
gap("gap-nonexistent", pointer("fig:missing"), level=3, reason="fig:missing, which no label defines")
gap("gap-existing-non-result", m.append(APPENDIX, r"\section{Details}\label{sec:details}"),
    pointer("sec:details"), level=3, reason="sec:details is not an evaluation result")
gap("gap-self-pointer", pointer("tab:related"), level=3, reason="tab:related is not an evaluation result")
for name, text in {
    "comment-line": "% \\label{fig:hidden}",
    "comment-env": r"\begin{comment}\label{fig:hidden}\end{comment}",
    "todo": r"Text.\todo{Add \label{fig:hidden} later.}",
    "todo-multiline": "Text.\\todo[inline] {Add\n\\label{fig:hidden}\n later.}",
    "lstlisting": "\\begin{lstlisting}\n\\label{fig:hidden}\n\\end{lstlisting}",
    "minted": "\\begin{minted}{tex}\n\\label{fig:hidden}\n\\end{minted}",
    "verbatim": "\\begin{verbatim}\n\\label{fig:hidden}\n\\end{verbatim}",
    "inline-code": r"Text.\verb|\label{fig:hidden}|",
}.items():
    gap("gap-hidden-" + name, m.append(m.EVAL, text), pointer("fig:hidden"),
        level=3, reason="fig:hidden, which no label defines")
for name, file, text, key in (
    ("theorem-in-approach", "content/03-approach.tex", r"\begin{theorem}\label{thm:main} It holds.\end{theorem}", "thm:main"),
    ("table-in-appendix", APPENDIX, r"\begin{table}\caption{Full results.}\label{tab:fullresults} x\end{table}", "tab:fullresults"),
    ("figure-in-appendix", APPENDIX, r"\begin{figure}\caption{Full results.}\label{fig:fullresults} x\end{figure}", "fig:fullresults"),
):
    gap("gap-" + name, m.append(file, text), pointer(key))
for key, file in (("rq:correct", m.EVAL), ("g:example", "content/03-approach.tex")):
    gap("gap-contract-" + key.replace(":", "-"), pointer(key))
gap("gap-contract-derived", m.append("content/03-approach.tex", r"\begin{derivedrequirements}\item\label{dr:check} Check it.\end{derivedrequirements}"), pointer("dr:check"))
gap("gap-row-wrapped", m.sub(RELATED, ROW, ROW.replace(" & " + SC, "\n & " + SC)))
gap("gap-row-terminator-next-line", m.sub(RELATED, ROW, ROW[:-2] + "\n\\\\"))
gap("gap-row-makecell", m.sub(RELATED, "Unlinkable checks", r"\makecell[l]{Unlinkable\\checks}"))
gap("gap-braced-ampersand", m.sub(RELATED, "Unlinkable checks", r"\makecell{Unlinkable \& checks\\{with details}}"))
gap("gap-source-rows-on-one-line", m.sub(RELATED, "\\\\\n    \\ref{req:second}", "\\\\ \\ref{req:second}"))
gap("gap-wrapped-invalid-pointer", m.sub(RELATED, ROW, ROW.replace(" & " + SC, "\n & " + SC)),
    pointer("ch:evaluation"), level=3, reason="ch:evaluation is not an evaluation result")
for env, args in (("tabular", "{l l c c c}"), ("tabular*", r"{\linewidth}{@{\extracolsep{\fill}}l l c c c}"),
                  ("tabularx", r"[t]{\linewidth}{l X c c c}"), ("longtable", "[c]{l l c c c}")):
    gap("gap-environment-" + env.replace("*", "-star"),
        m.sub(RELATED, r"\begin{tabularx}{\linewidth}{l X c c c}", "\\begin{" + env + "}" + args),
        m.sub(RELATED, r"\end{tabularx}", "\\end{" + env + "}"))
gap("gap-merged-cells-deferred", m.sub(RELATED, "Unlinkable checks", r"\multicolumn{1}{l}{Unlinkable checks}"),
    level=3, reason="cannot check merged cells")
gap("gap-spaced-reference", m.sub(RELATED, SC, r"\gapyes\,(\cref {sec:scalability})"))
gap("gap-mixed-result-list", m.sub(RELATED, SC, r"\gapyes\,(\cref{rq:correct,ch:evaluation})"),
    level=3, reason="ch:evaluation is not an evaluation result")
REQS = (("requirements", 1, "3 items, all TODO"),)
gap("requirements-label-in-table", m.sub(RELATED, r"\ref{req:third}  & Auditable",
    r"\ref{req:fourth}\label{req:fourth} & Extra & \gapno & \gapno & \gapyes\,(\cref{rq:correct}) \\" + "\n" + r"\ref{req:third}  & Auditable"),
    level=3, reason="req:fourth is a row of the gap matrix but no requirement carries that label", checks=REQS)
for name, extra in {
    "comment-env": r"\begin{comment}\begin{requirements}\item\label{req:old} Old requirement.\end{requirements}\end{comment}",
    "todo": r"\todo{\begin{requirements}\item\label{req:old} Old requirement.\end{requirements}}",
    "listing": "\\begin{lstlisting}\n\\begin{requirements}\\item\\label{req:old} Old requirement.\\end{requirements}\n\\end{lstlisting}",
    "bare-label": r"\label{req:old} An arbitrary label.",
    "ordinary-item": r"\begin{itemize}\item\label{req:old} Ordinary item.\end{itemize}",
}.items():
    gap("requirements-hidden-or-untyped-" + name, m.append(INTRO, extra), checks=REQS)
# Printed requirements may also be table items, with a makecell inner linebreak.
def tagrow_rows(d):
    p = d / INTRO
    s = p.read_text().replace(r"\begin{requirements}", r"\begin{tabular}{ll}").replace(r"\end{requirements}", r"\end{tabular}")
    s = s.replace(r"\item\label{req:", r"\tagrow{requirements}\label{req:")
    s = "\n".join(line + r" \\" if r"\tagrow{requirements}" in line else line for line in s.splitlines())
    p.write_text(s.replace("TODO Second.", r"TODO \makecell{Second\\line}."))
gap("requirements-tagrow-balanced", tagrow_rows, checks=REQS)
gap("requirements-nested-table-label", m.sub(INTRO, r"\end{requirements}",
    r"\begin{table}\caption{Details.}\label{req:planted} Text.\end{table}" + "\n" + r"\end{requirements}"), checks=REQS)
gap("requirements-multiline-label", m.sub(INTRO, r"\item\label{req:second}", "\\item\n\\label {req:second}"), checks=REQS)
artifact("artifact-software-doi", "software", "doi = {10.5281/zenodo.1234567}")
artifact("artifact-uppercase-doi", "Software", 'DOI = "10.5281/ZENODO.1234567"')
artifact("artifact-url", "dataset", 'URL = {https://doi.org/10.5281/ZENODO.1234567}')
artifact("artifact-braced-doi", "misc", 'doi = {{10.5281/zenodo.1234567}}')
artifact("artifact-note-before-real-field", "software", 'note = {see url = {irrelevant}},\n DOI = {10.5281/zenodo.1234567}')
for name, fields in {
    "plain-note": 'note = {Archived as 10.5281/zenodo.1234567}',
    "fake-url-in-note": 'note = {see url = {https://doi.org/10.5281/zenodo.1234567}}',
    "comma-fake-doi-in-note": 'note = {see, doi = {10.5281/zenodo.1234567}}',
    "quoted-note": 'note = "see, url = {https://doi.org/10.5281/zenodo.1234567}"',
    "unrelated-doi-field": 'doi = {10.1000/other}, note = {url = {10.5281/zenodo.1234567}}',
}.items():
    artifact("artifact-" + name, "misc", fields, 3, "cite the archived artifact")
artifact("artifact-publication", "article", 'doi = {10.5281/zenodo.1234567}', 3, "art is an @article entry with a Zenodo DOI")

# Follow-up cases retain all 56 original cases and their expectations above. Membership
# counts printed items, while exactly one usable, unique req: label identifies each item.
def extra_requirement(text):
    return m.sub(INTRO, r"\end{requirements}", text + "\n" + r"\end{requirements}")


FOUR_REQS = (("requirements", 1, "4 items, all TODO"),)
for name, edit, reason, counts in (
    ("unlabeled-addition", extra_requirement(r"\item TODO Fourth printed property."), "has no req: label", FOUR_REQS),
    ("unlabeled-existing", m.sub(INTRO, r"\label{req:third}", ""), "has no req: label", REQS),
    ("duplicate-addition", extra_requirement(r"\item\label{req:third} TODO Fourth printed property."), "req:third is duplicated", FOUR_REQS),
    ("duplicate-existing", m.sub(INTRO, r"\label{req:second}", r"\label{req:third}"), "req:third is duplicated", REQS),
    ("duplicate-across-files", m.append(m.EVAL, r"\begin{requirements}\item\label{req:third} TODO Fourth property.\end{requirements}"), "req:third is duplicated", FOUR_REQS),
    ("multiple-labels", m.sub(INTRO, r"\label{req:third}", r"\label{req:third}\label{req:fourth}"), "has multiple req: labels", REQS),
    ("repeated-label", m.sub(INTRO, r"\label{req:third}", r"\label{req:third}\label{req:third}"), "has multiple req: labels", REQS),
    ("empty-key", m.sub(INTRO, r"\label{req:third}", r"\label{req:}"), "has an unusable req: label", REQS),
    ("spaced-key", m.sub(INTRO, r"\label{req:third}", r"\label{req:third property}"), "has an unusable req: label", REQS),
    ("comma-key", m.sub(INTRO, r"\label{req:third}", r"\label{req:third,fourth}"), "has an unusable req: label", REQS),
):
    gap("requirements-identity-" + name, edit, level=3, reason=reason, checks=counts)

for name, edit, reason in (
    ("unlabeled", m.sub(INTRO, r"\label{req:third}", ""), "has no req: label"),
    ("duplicate", m.sub(INTRO, r"\label{req:second}", r"\label{req:third}"), "req:third is duplicated"),
    ("multiple", m.sub(INTRO, r"\label{req:third}", r"\label{req:third}\label{req:fourth}"), "has multiple req: labels"),
):
    gap("requirements-identity-tagrow-" + name, tagrow_rows, edit,
        level=3, reason=reason, checks=REQS)
    # Identity defects also keep fully written Requirements below level 4.
    gap("requirements-identity-written-" + name, m.own_items(INTRO, "req"), edit,
        level=3, reason=reason, checks=(("requirements", 3, reason),))

for name, file, text, key in (
    ("theorem", "content/03-approach.tex", r"\begin{theorem}\label{thm:direct} It holds.\end{theorem}", "thm:direct"),
    ("table", APPENDIX, r"\begin{table}\caption{Full results.}\label{tab:direct} x\end{table}", "tab:direct"),
    ("figure", APPENDIX, r"\begin{figure}\caption{Full results.}\label{fig:direct} x\end{figure}", "fig:direct"),
):
    gap("gap-direct-result-reminder-" + name, m.append(file, text),
        *(m.sub(RELATED, source, key) for source in ("rq:correct", "sec:scalability", "sec:robustness")),
        reason="the reader must check that each cited result is sufficient",
        diagnostic="Matrix claim sufficiency needs human review")

gap("gap-tabularnewline-unsupported", m.sub(RELATED, ROW, ROW[:-2] + r"\tabularnewline"),
    level=3, reason=r"cannot check \tabularnewline row terminators")


# Main-policy interactions with the audited printed reader and balanced matrix parser.
# The original 76 cases and their assertions above remain unchanged.
APPROACH = "content/03-approach.tex"
for status in ("gappartial", "gapno"):
    gap("interaction-" + status + "-wrapped-evidence",
        m.sub(RELATED, ROW, ROW.replace(" & " + SC, "\n & " + SC.replace("gapyes", status))),
        diagnostic="Matrix claim sufficiency needs human review")
    gap("interaction-" + status + "-missing-evidence",
        m.sub(RELATED, SC, "\\" + status), level=3, reason="points at no evaluation result")
# Reporting a competitor that meets every requirement does not itself refute a gap.
gap("interaction-competitor-meets-all", m.sub(RELATED,
    r"Fast revocation & \gapyes & \gappartial", r"Fast revocation & \gapyes & \gapyes"),
    m.sub(RELATED, r"Unlinkable checks & \gapno", r"Unlinkable checks & \gapyes"),
    m.sub(RELATED, r"Auditable history & \gappartial & \gapno", r"Auditable history & \gapyes & \gapyes"))

for name, file, text, key in (
    ("appendix-theorem", APPENDIX, r"\begin{theorem}\label{sec:appendix-result} It holds.\end{theorem}", "sec:appendix-result"),
    ("arbitrary-prefix", APPROACH, r"\begin{corollary}\label{result:bounded} It holds.\end{corollary}", "result:bounded"),
    ("multiline", APPROACH, "\\begin {proposition}\n\\label\n {result:multiline} It holds.\\end {proposition}", "result:multiline"),
    ("printed-math", APPROACH, r"\begin{theorem}\[x=1\label{result:math}\]\end{theorem}", "result:math"),
    ("literal-end", APPROACH, r"\begin{claim}\verb|\end{claim}|\label{result:literal-end} It holds.\end{claim}", "result:literal-end"),
):
    gap("interaction-result-" + name, m.append(file, text), pointer(key))
for name, file, text, key, reason in (
    ("fake-prefix", APPROACH, r"\paragraph{Assertion}\label{thm:fake} Unproved assertion.", "thm:fake", "is not an evaluation result"),
    ("fake-prefix-evaluation", m.EVAL, r"\paragraph{Assertion}\label{thm:fake} Unproved assertion.", "thm:fake", "is not an evaluation result"),
    ("after-close", APPROACH, r"\begin{theorem} It holds.\end{theorem}\label{thm:after}", "thm:after", "is not an evaluation result"),
    ("definition", APPROACH, r"\begin{definition}\label{thm:definition} A definition.\end{definition}", "thm:definition", "is not an evaluation result"),
    ("escaped-begin", APPROACH, r"\\begin{theorem}\label{thm:escaped} Text.", "thm:escaped", "is not an evaluation result"),
    ("address-begin", APPROACH, r"\href{https://example.org/\begin{theorem}}{Address}\label{thm:address} Text.", "thm:address", "is not an evaluation result"),
    ("printed-duplicate-after", APPROACH, r"\begin{theorem}\label{thm:collision} Result.\end{theorem}\paragraph{Other}\label{thm:collision}", "thm:collision", "is not an evaluation result"),
    ("chapter-prefix", APPROACH, r"\begin{theorem}\label{ch:fake} It holds.\end{theorem}", "ch:fake", "is not an evaluation result"),
):
    gap("interaction-result-" + name, m.append(file, text), pointer(key), level=3, reason=key + " " + reason)
for name, text in {
    "todo": r"\todo{\begin{theorem}\label{thm:hidden} Result.\end{theorem}}",
    "comment": r"\begin{comment}\begin{theorem}\label{thm:hidden} Result.\end{theorem}\end{comment}",
    "false": r"\iffalse\begin{theorem}\label{thm:hidden} Result.\end{theorem}\fi",
    "listing": "\\begin{lstlisting}\n\\begin{theorem}\\label{thm:hidden} Result.\\end{theorem}\n\\end{lstlisting}",
    "inline": r"\verb|\begin{theorem}\label{thm:hidden}\end{theorem}|",
    "texttt": r"\texttt{\begin{theorem}\label{thm:hidden}\end{theorem}}",
    "address": r"\url{https://example.org/\begin{theorem}\label{thm:hidden}\end{theorem}}",
}.items():
    gap("interaction-result-hidden-" + name, m.append(APPROACH, text), pointer("thm:hidden"),
        level=3, reason="thm:hidden, which no label defines in the printed paper")
for name, text in {
    "todo": r"\todo{No revocation operation exists in the offline model}",
    "multiline-note": "\\advisortodo[inline]{No revocation\noperation exists in the offline model}",
    "false": r"\iffalse No revocation operation exists in the offline model\fi",
    "inline": r"\verb|No revocation operation exists in the offline model|",
    "address": r"\url{https://example.org/no revocation operation exists}",
}.items():
    gap("interaction-na-hidden-reason-" + name, m.sub(RELATED, SC, r"\gapna{} " + text),
        level=3, reason="N/A cell needs a reason")
for name, text in {
    "hidden": r"\todo{\paragraph{Scope}\label{par:scope} This operation is absent.}",
    "literal": r"\verb|\paragraph{Scope}\label{par:scope} This operation is absent.|",
}.items():
    gap("interaction-na-" + name + "-scope", m.append(APPROACH, text),
        m.sub(RELATED, SC, r"\gapna\,(\cref{par:scope})"), level=3,
        reason="par:scope, which no label defines")
gap("interaction-na-visible-makecell", m.sub(RELATED, SC,
    r"\makecell{\gapna{} No revocation operation\\exists in the offline model}"))
gap("interaction-na-appendix-scope", m.append(APPENDIX,
    r"\section{Scope}\label{sec:scope} The offline model has no revocation operation."),
    m.sub(RELATED, SC, r"\gapna\,(\cref{sec:scope})"))
gap("interaction-na-self-pointer", m.sub(RELATED, SC, r"\gapna\,(\cref{tab:related})"),
    level=3, reason="N/A cell needs a reason")
for name, cell, reason in (
    ("escaped-pointer", r"\gapyes\\cref{rq:correct}", "points at no evaluation result"),
    ("address-pointer", r"\gapyes\url{https://example.org/\cref{rq:correct}}", "points at no evaluation result"),
    ("escaped-status", r"\\gapyes\cref{rq:correct}", "this work's cell needs one status"),
    ("address-status", r"\url{https://example.org/\gapyes}\cref{rq:correct}", "this work's cell needs one status"),
):
    gap("interaction-cell-" + name, m.sub(RELATED, SC, cell), level=3, reason=reason)


def lint(d):
    cmd = ["texlua", "scripts/lint.lua", "essentials", "--phase", "submit", "--json"]
    env = dict(os.environ, LINT_OFFLINE="1")
    # Match the existing host/CI convention, without requiring a host TeX installation.
    if not shutil.which("texlua"):
        cmd = ["docker", "run", "--rm", "--network=none", "-u", f"{os.getuid()}:{os.getgid()}",
               "-e", "HOME=/tmp", "-e", "LINT_OFFLINE=1", "-v", f"{d}:/w", "-w", "/w",
               os.environ.get("LINT_IMAGE", "danteev/texlive:latest"), *cmd]
    return subprocess.run(cmd, cwd=d, env=env, text=True, capture_output=True, timeout=90)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("built", type=Path, nargs="?", default=TEMPLATE)
    ap.add_argument("--only", help="regular expression selecting case names")
    ap.add_argument("--scripts-ref", help="git revision of lint scripts to test instead of the working tree")
    ap.add_argument("--work-dir", type=Path, help="retain fixtures and lint JSON receipts here")
    ap.add_argument("--report", type=Path)
    a = ap.parse_args()
    temporary = None if a.work_dir else tempfile.TemporaryDirectory(prefix="lint-evidence-")
    work = (a.work_dir or Path(temporary.name)).resolve()
    work.mkdir(parents=True, exist_ok=True)
    results = []
    for name, edit, checks, diagnostic in CASES:
        if a.only and not re.search(a.only, name):
            continue
        d = work / name
        if d.exists():
            raise SystemExit(f"refusing to overwrite existing fixture {d}")
        shutil.copytree(a.built, d, ignore=shutil.ignore_patterns(".git", "_minted-*", "svg-inkscape", "review-bundle", "skim", "__pycache__"))
        shutil.rmtree(d / "scripts")
        if a.scripts_ref:
            # Support both pre-monorepo audit baselines and current paper trees.
            nested = subprocess.run(["git", "cat-file", "-e", a.scripts_ref + ":paper/scripts"],
                                    cwd=TEMPLATE, capture_output=True).returncode == 0
            tree = a.scripts_ref + (":paper" if nested else "")
            archive = subprocess.run(["git", "archive", tree, "scripts"], cwd=TEMPLATE,
                                     capture_output=True, check=True).stdout
            with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
                tf.extractall(d, filter="data")
        else:
            shutil.copytree(TEMPLATE / "scripts", d / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        errors = []
        rows = {}
        try:
            edit(d)
            run = lint(d)
            (d / "evidence.stdout").write_text(run.stdout)
            (d / "evidence.stderr").write_text(run.stderr)
            if run.returncode not in (0, 1):
                raise AssertionError(f"lint execution failed: exit {run.returncode}, {run.stderr[-500:]}")
            j = json.loads(run.stdout)
            rule = next(r for r in j["rules"] if r["rule"] == "essentials")
            if rule.get("crashed") or rule["status"] == "error":
                raise AssertionError("essentials crashed")
            rows = {r["id"]: r for r in j["rows"]}
            for rid, level, reason in checks:
                row = rows[rid]
                if row["level"] != level or reason not in row["next"]:
                    errors.append(f"{rid}: expected level {level}, reason {reason!r}; got {row['level']}, {row['next']!r}")
            if diagnostic and diagnostic not in run.stdout:
                errors.append(f"missing diagnostic {diagnostic!r}")
        except (Exception, SystemExit) as e:
            errors.append(str(e))
        results.append({"name": name, "ok": not errors, "errors": errors,
                        "rows": {rid: rows.get(rid) for rid, _, _ in checks}})
        print(("FAIL" if errors else "ok  ") + " " + name)
        for error in errors:
            print("     " + error)
        if not a.work_dir:
            shutil.rmtree(d)
    if not results:
        raise SystemExit("no cases selected")
    failed = sum(not r["ok"] for r in results)
    report = {"scripts_ref": a.scripts_ref or "working tree", "passed": len(results) - failed,
              "failed": failed, "cases": results}
    if a.report:
        a.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{len(results) - failed}/{len(results)} passed; {failed} failed")
    if temporary:
        temporary.cleanup()
    raise SystemExit(bool(failed))


if __name__ == "__main__":
    main()
