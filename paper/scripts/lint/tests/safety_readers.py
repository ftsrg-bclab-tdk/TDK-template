#!/usr/bin/env python3
"""Focused write-safety and reader regressions; every case runs on a temporary copy.

    python3 scripts/lint/tests/safety_readers.py
    python3 scripts/lint/tests/safety_readers.py --helper /path/to/tl.sh
    tl.sh <checkout> python3 scripts/lint/tests/safety_readers.py --native

Uses texlua when installed; otherwise starts one offline TeX Live container.
No build or baseline auxiliaries required. Tests actual fix writes, byte-for-byte
preservation, idempotence, original JSON edit columns, reader findings and exits.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

TEMPLATE = Path(__file__).resolve().parents[3]
MAIN = "content/01-main.tex"
BIB = "bib/references.bib"
PLAN = r"\newcommand{\lintphase}{plan}"
ENTRY = "@article{known,\n author = {Doe, Jane},\n title = {A title},\n year = {2020},\n journal = {Journal}\n}\n"
LINK = "https://www.overleaf.com/read/abcdefghijkl"


def launch(args):
    if shutil.which("texlua"):
        return
    if args.native:
        raise SystemExit("texlua is required for --native")
    tail = ["python3", "scripts/lint/tests/safety_readers.py", "--native"]
    if args.only:
        tail += ["--only", args.only]
    if args.helper:
        cmd = [str(Path(args.helper).resolve()), str(TEMPLATE), *tail]
    else:
        cmd = ["docker", "run", "--rm", "--network=none", "-u", f"{os.getuid()}:{os.getgid()}",
               "-e", "HOME=/tmp", "-v", f"{TEMPLATE}:/w:ro", "-w", "/w",
               os.environ.get("LINT_IMAGE", "danteev/texlive:latest"), *tail]
    raise SystemExit(subprocess.run(cmd).returncode)


def fixture(d, body="", bib=ENTRY, phase=PLAN):
    for name in ("content", "bib", "include"):
        (d / name).mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE / "scripts", d / "scripts")
    (d / "draft.tex").write_text(
        "\\documentclass{article}\n" + phase + "\n" + r"""\usepackage{cleveref,csquotes,glossaries-extra}
\newcommand{\eg}{e.g.}
\newcommand{\ie}{i.e.}
\newcommand{\etal}{et al.}
\newcommand{\tbd}[1]{#1}
\newcommand{\citeneeded}[1][]{#1}
\include{content/01-main}
\loadglsentries{content/glossary}
\bibliography{bib/references}
""")
    (d / MAIN).write_text("\\chapter{Background}\\label{ch:background}\n" + body + "\n")
    (d / "content/glossary.tex").write_text(r"\newabbreviation{vc}{VC}{verifiable credential}" + "\n")
    (d / "include/tdk-variables.tex").write_text(r"\newcommand{\tdkev}{2026}" + "\n")
    (d / BIB).write_text(bib)


def snapshot(d):
    return {str(p.relative_to(d)): p.read_bytes() for p in d.rglob("*")
            if p.is_file() and p.suffix in (".tex", ".bib")}


def run(d, *args, exit=None, env=None):
    clean = {k: v for k, v in os.environ.items() if not k.startswith(("GITHUB_", "LINT_"))}
    # a date before October: the calendar does not raise the phase the case declares
    clean.update(LINT_OFFLINE="1", LINT_FIX_STRICT="1", LINT_DATE="2026-06-01")
    clean.update(env or {})
    r = subprocess.run(["texlua", "scripts/lint.lua", *args], cwd=d,
                       capture_output=True, text=True, env=clean)
    if exit is not None:
        assert r.returncode == exit, (args, r.returncode, r.stdout, r.stderr)
    return r


def lint(d, rule, phase="submit", exit=None, env=None):
    args = [rule, "--json"] + (["--phase", phase] if phase else [])
    r = run(d, *args, exit=exit, env=env)
    assert r.returncode in (0, 1), (r.returncode, r.stdout, r.stderr)
    data = json.loads(r.stdout)
    assert data["ok"] == (r.returncode == 0), data
    assert len(data["rules"]) == 1 and data["rules"][0]["rule"] == rule, data
    assert data["rules"][0]["status"] not in ("error", "skipped"), data
    # The edits in JSON must point at the original on-disk bytes, including UTF-8.
    for f in data["findings"]:
        for e in f.get("fix", {}).get("edits", []):
            if "old" in e:
                raw = (d / e["file"]).read_bytes().split(b"\n")[e["line"] - 1]
                old = e["old"].encode()
                assert raw[e["at"] - 1:e["at"] - 1 + len(old)] == old, (e, raw)
    return data


CASES = []


def case(name):
    def register(fn):
        CASES.append((name, fn))
        return fn
    return register


def fix_case(name, body, expected=None, rule="typography", review=False, bib=None, bib_after=None):
    @case(name)
    def test(d):
        fixture(d, body, bib or ENTRY)
        before = snapshot(d)
        lint(d, rule)
        run(d, "fix", rule, "--phase", "submit", "--dry-run", *(["--review"] if review else []), exit=0)
        assert snapshot(d) == before, "dry run wrote source"
        args = ("fix", rule, "--phase", "submit", "--allow-dirty", *(["--review"] if review else []))
        run(d, *args, exit=0)
        want = dict(before)
        if expected is not None:
            want[MAIN] = ("\\chapter{Background}\\label{ch:background}\n" + expected + "\n").encode()
        if bib_after is not None:
            want[BIB] = bib_after.encode()
        assert snapshot(d) == want, {k: (want.get(k), v) for k, v in snapshot(d).items() if v != want.get(k)}
        lint(d, rule)
        run(d, *args, exit=0)
        assert snapshot(d) == want, "second fix pass changed source"


literals = {
    "url-percent": r"\url{https://example.org/2019-2020/report%20final.pdf}",
    "url-multiline": "\\url{https://example.org/long/\npath/10-20/report}",
    "href-percent": r"\href{https://example.org/10-20/a%20b}{the report}",
    "url-delimited": r"\url|https://example.org/10-20/a%20b|",
    "math-paren": r"\(10-20\)",
    "math-display": "$$10-20$$",
    "math-multiline": "$x +\n10-20$",
    "math-brackets": "\\[x +\n10-20\\]",
    "math-environment": "\\begin{align*}\nx &= 10-20\n\\end{align*}",
    "verb": r'\verb|10-20 "text"|',
    "verb-percent-delimiter": r'\verb%10-20%',
    "lstinline": r'\lstinline[language=TeX]|10-20 "text"|',
    "mintinline": r'\mintinline{python}|10-20 "text"|',
    "mint-oneliner": r'\mint{python}|10-20 "text"|',
    "graphics-path": r'\includegraphics[width=.5\textwidth]{figures/10-20}',
    "svg-path": r'\includesvg{figures/10-20}',
    "picture": "\\begin{tikzpicture}\nrange 10-20\n\\end{tikzpicture}",
    "mintinline-braces": r'\mintinline[breaklines]{python}{10-20 "text"}',
    "texttt": r'\texttt{10-20 "text"}',
    "todo": r'\todo{10-20 "text"}',
    "todo-multiline-options": '\\todo[inline,\n caption={a ] bracket}]\n {10-20 "text"}',
}
for name, literal in literals.items():
    for review in (False, True):
        fix_case(name + ("-review" if review else "-safe"),
                 "Literal " + literal + ". Pages 30-40 follow.",
                 "Literal " + literal + ". Pages 30--40 follow.", review=review)

for env in ("lstlisting", "minted", "verbatim", "verbatim*", "Verbatim", "comment"):
    opening = "\\begin{" + env + "}" + ("{tex}" if env == "minted" else "")
    literal = opening + "\nFigure~\\ref{fig:x}\n\\begin{figure}[h]\n\\end{" + env + "}"
    fix_case("crefs-" + env, literal + "\nSee Figure~\\ref{fig:x}.",
             literal + "\nSee \\cref{fig:x}.", "crefs", review=True)
    fix_case("figures-" + env, literal, rule="figures", review=True)

fix_case("prose-columns-after-note", r'Á.\todo{hidden "quote"} He says "hello".',
         r'Á.\todo{hidden "quote"} He says \enquote{hello}.', review=True)
fix_case("cref-columns-after-note", r"\todo{Figure~\ref{fig:x}} See Figure~\ref{fig:x}.",
         r"\todo{Figure~\ref{fig:x}} See \cref{fig:x}.", "crefs", review=True)
fix_case("note-group-prose", r"\todo{later}{See pages 10-20.}", r"\todo{later}{See pages 10--20.}")
fix_case("eg-prose-only", r"We use e.g. a proof.\todo{e.g. later}", r"We use \eg a proof.\todo{e.g. later}")
fix_case("escaped-dollar-prose", r"Costs \$5-10; maths $10-20$.", r"Costs \$5--10; maths $10-20$.")
fix_case("unterminated-url", "Before 30-40. \\url{https://example.org/\n10-20", "Before 30--40. \\url{https://example.org/\n10-20")
fix_case("unterminated-math", "Before 30-40. $x +\n10-20", "Before 30--40. $x +\n10-20")
fix_case("figures-prose-control", r"\begin{figure}[h]\caption{A figure}\label{fig:x}\end{figure}",
         r"\begin{figure}[!ht]\caption{A figure}\label{fig:x}\end{figure}", "figures")
math_bib = ENTRY.replace("A title", r"Proof that $P \neq NP$ Holds for SAT")
fix_case("bib-title-math", "", rule="bib", bib=math_bib,
         bib_after=math_bib.replace("for SAT", "for {SAT}"))
math_bib2 = ENTRY.replace("A title", "Proof that $P \\neq\n NP$ Holds for SAT")
fix_case("bib-title-multiline-math", "", rule="bib", review=True, bib=math_bib2,
         bib_after=math_bib2.replace("for SAT", "for {SAT}"))

fix_case("quote-columns-next-to-verbatim", r'The \verb|"| character opens "abc" and "def"; see \verb|"|.',
         r'The \verb|"| character opens \enquote{abc} and \enquote{def}; see \verb|"|.', review=True)
fix_case("cref-after-multiline-math", "$x +\n10-20$ See Figure~\\ref{fig:x}.",
         "$x +\n10-20$ See \\cref{fig:x}.", "crefs")
fix_case("cref-after-multiline-url", "\\url{https://example.org/\nFigure~\\ref{fig:x}} See Figure~\\ref{fig:x}.",
         "\\url{https://example.org/\nFigure~\\ref{fig:x}} See \\cref{fig:x}.", "crefs")
fix_case("unfinished-note", "Pages 10-20. \\todo[inline", "Pages 10--20. \\todo[inline")


@case("direct-insertion-at-unfinished-eof")
def direct_eof(d):
    fixture(d, "")
    (d / MAIN).write_bytes(b"\\chapter{Background}\\label{ch:background}\n\\begin{lstlisting}\nOLD")
    with (d / "scripts/lint/rules-source.lua").open("a") as f:
        f.write(r'''
C.rule("direct", "source", "advice", "always", "test", function()
  C.warn("content/01-main.tex", 3, "insert", C.fix("safe", "insert", C.after("NEVER INSERT")))
end)
''')
    before = snapshot(d)
    assert not lint(d, "direct")["findings"][0].get("fix")
    run(d, "fix", "direct", "--allow-dirty", exit=0)
    assert snapshot(d) == before

fix_case("citation-keys-unchanged", r"ISO~\cite{iso:27001-2022} covers the years 2019-2020.",
         r"ISO~\cite{iso:27001-2022} covers the years 2019--2020.")
fix_case("citation-keys-multiline", "See~\\citep[pp.~2-3]\n{iso:27001-2022} for pages 10-20.",
         "See~\\citep[pp.~2-3]\n{iso:27001-2022} for pages 10--20.")
fix_case("link-label-is-prose", r'\href{https://example.org/"10-20"}{the "report"} covers 30-40.',
         r'\href{https://example.org/"10-20"}{the \enquote{report}} covers 30--40.', review=True)


@case("direct-replace-all-and-insert")
def direct(d):
    fixture(d, '\\begin{lstlisting}\nOLD\n\\end{lstlisting}\n' + r'\verb|OLD| OLD % OLD')
    extra = r'''
C.rule("direct", "source", "advice", "always", "test direct writers", function()
  for n, l in ipairs(C.raw_lines("content/01-main.tex")) do
    if l:find("OLD", 1, true) then
      C.warn("content/01-main.tex", n, "direct", C.fix("safe", "replace direct",
        C.replace_at("content/01-main.tex", n, "OLD", "NEW", true)))
    end
  end
  C.warn("content/01-main.tex", 3, "protected insert", C.fix("safe", "insert",
    C.after_at("content/01-main.tex", 3, "NEVER INSERT")))
end)
'''
    with (d / "scripts/lint/rules-source.lua").open("a") as f:
        f.write(extra)
    before = snapshot(d)
    data = lint(d, "direct")
    assert sum(len(f.get("fix", {}).get("edits", [])) for f in data["findings"]) == 1, data
    run(d, "fix", "direct", "--allow-dirty", exit=0)
    want = dict(before)
    want[MAIN] = before[MAIN].replace(b"| OLD %", b"| NEW %")
    assert snapshot(d) == want


def reader(name, text, present, rule="companion", needle="Overleaf"):
    @case(name)
    def test(d):
        fixture(d, text)
        before = snapshot(d)
        data = lint(d, rule, exit=1 if present else 0)
        findings = [f for f in data["findings"] if needle in f["msg"]]
        assert bool(findings) == present, data
        assert snapshot(d) == before


hidden = [r"\verb|TEXT|", r"\verb%TEXT%", r"\lstinline[language=TeX]|TEXT|",
          r"\mintinline{tex}|TEXT|", r"\texttt{TEXT}", "% TEXT",
          "\\begin{verbatim}\nTEXT\n\\end{verbatim}",
          "\\todo[inline,\ncaption={bracket ] here}]\n {TEXT}",
          "\\todo[inline]% comment\n {TEXT}",
          r"\guidetodo{TEXT}{TEXT}", r"\beat{TEXT}{TEXT}{TEXT}{TEXT}"]
# Citation placement: explicit blocks are checkable; continued prose is not.
for name, attribution in (
    ("missing", "Author"), ("empty", ""), ("author-only", r"\citeauthor{known}"),
    ("empty-cite", r"Author, \cite{}"),
    ("url", r"\url{https://example.org/\cite{known}}"),
    ("note", r"Author\todo{\cite{known}}"),
    ("literal", r"Author \texttt{\cite{known}}"),
):
    reader("quotation-" + name, r"\begin{sourcequote}{" + attribution +
           r"}Words.\cite{known}\end{sourcequote}", True, "quotations", "has no citation")
for name, attribution in (
    ("valid", r"Author, \cite[p.~12]{known}"),
    ("nested", r"\emph{Author}, \citep[see][Section~2]{known}"),
    ("multiline", "Author, \\citet*% comment\n [p.~12]\n{known}"),
):
    reader("quotation-" + name, r"\begin{sourcequote}" + "\n{" + attribution +
           r"}Words [\textit{sic}] [\ldots].\end{sourcequote}", False, "quotations", "has no citation")
reader("quotation-body-cite-is-checked", r"\begin{sourcequote}{Author, \cite[p.~12]{missingkey}}Words.\end{sourcequote}",
       True, "bib", "missingkey")
reader("quotation-prose-continuation", "\\citet{known} describe a protocol.\n\nTheir next phase verifies it.\n\nWe call this \\enquote{verification}.",
       False, "quotations", "citation")
for i, template in enumerate(hidden):
    reader(f"quotation-hidden-{i}", template.replace("TEXT", r"\begin{sourcequote}{Author}Words.\end{sourcequote}"),
           False, "quotations", "has no citation")

@case("quotation-warning-and-phase")
def quotation_warning_and_phase(d):
    fixture(d, r"\begin{sourcequote}{Author, \cite{known}}Words.\end{sourcequote}" +
            r"\begin{quote}Words.\end{quote}")
    data = lint(d, "quotations", exit=0)
    assert any("no locator" in f["msg"] for f in data["findings"]), data
    assert any("plain quote" in f["msg"] for f in data["findings"]), data
    (d / MAIN).write_text(r"\begin{sourcequote}{Author}Words.\end{sourcequote}")
    lint(d, "quotations", phase="plan", exit=0)
    lint(d, "quotations", phase="draft", exit=1)

for i, template in enumerate(hidden):
    reader(f"hidden-link-{i}", template.replace("TEXT", "\\url{" + LINK + "}"), False)
    reader(f"hidden-cite-{i}", template.replace("TEXT", r"\cite{missingkey}"), False, "bib", "missingkey")
    reader(f"hidden-phrase-{i}", template.replace("TEXT", r"companion paper~\cite{known}"), False, needle="attached")
for i, prefix in enumerate((r"\todo{hidden}", r"\todo[inline]{hidden}", "\\todo[inline,\ncaption={x}]\n{hidden}",
                            r"\guidetodo{hidden}{label}", r"\beat{one}{two}{three}{four}")):
    reader(f"following-group-{i}", prefix + r" {A companion paper~\cite{known}.}", True, needle="attached")
for i, phrase in enumerate((r"\emph{\enquote{companion paper}}", r"\emph{companion} paper",
                            r"companion \textbf{paper}", r"``companion paper''", '"companion paper"')):
    reader(f"formatted-phrase-{i}", "A " + phrase + r"~\citep[see][p. 2]{known}.", True, needle="attached")
    reader(f"formatted-link-label-{i}", r"\href{https://example.org}{A " + phrase + "}.", True, needle="attached")
reader("separate-tool-citation", r"A companion paper verifies it in Tamarin~\cite{known}.", False, needle="attached")
for i, body in enumerate(("https://www.overleaf.com/\n read/abcdefghijkl", "https://www.overleaf.com/ read/abcdefghijkl",
                         "https://www.overleaf.com/read/\nabcdefghijkl")):
    reader(f"url-whitespace-{i}", "\\url{" + body + "}", True)
reader("delimited-url-reader", "\\url|" + LINK + "|", True)
reader("math-link-reader", "\\[\\text{\\url{" + LINK + "}}\\]", True)
reader("math-phrase-reader", r"\[\text{companion paper~\cite{known}}\]", True, needle="attached")
reader("url-does-not-contain-citation", r"\url{https://example.org/\cite{missingkey}}", False, "bib", "missingkey")


def phase_case(name, decl, want, error=None):
    @case(name)
    def test(d):
        fixture(d, r"Proving takes \tbd{time}.", phase=decl)
        if error:
            r = run(d, "markers", "--json", exit=2)
            assert error in r.stderr, r.stderr
            assert '"ok":true' not in r.stdout
        else:
            data = lint(d, "markers", phase=None, exit=1 if want == "submit" else 0)
            assert data["phase"] == want, data


for i, decl in enumerate((r"\newcommand* {\lintphase} {submit}", "\\newcommand{\\lintphase}\n {submit}",
                          "\\newcommand{\\lintphase}% comment\n {submit}", r"\newcommand\lintphase[0]{submit}",
                          PLAN + "\n" + r"\renewcommand*{\lintphase}{submit}", r"\providecommand{\lintphase}{submit}",
                          r"\def\lintphase{submit}")):
    phase_case(f"supported-phase-{i}", decl, "submit")
@case("phase-raised-by-the-date")
def test(d):
    fixture(d, r"Proving takes \tbd{time}.", phase=PLAN)
    for date, want in (("2026-09-30", "plan"), ("2026-10-01", "draft"), ("2026-10-22", "polish"), ("2026-10-30", "submit"), ("2026-12-31", "submit")):
        data = lint(d, "markers", phase=None, exit=1 if want == "submit" else 0, env={"LINT_DATE": date})
        assert data["phase"] == want, (date, data["phase"], data["phase_source"])
    data = lint(d, "markers", phase=None, exit=0, env={"LINT_DATE": "2026-10-31", "LINT_PHASE": "plan"})
    assert data["phase"] == "plan", data


phase_case("phase-provide-keeps-existing", PLAN + r"\providecommand{\lintphase}{submit}", "plan")
phase_case("phase-last-renew", r"\newcommand{\lintphase}{submit}\renewcommand{\lintphase}{plan}", "plan")
phase_case("phase-comment-environment", "\\begin{comment}\n\\newcommand{\\lintphase}{submit}\n\\end{comment}\n" + PLAN, "plan")
phase_case("phase-code", r"\verb|\newcommand{\lintphase}{submit}|" + "\n" + PLAN, "plan")
phase_case("phase-unknown", "\\newcommand*{\\lintphase}\n{fnial}", None, "unknown phase 'fnial'")
phase_case("phase-empty", r"\newcommand{\lintphase}{}", None, "unknown phase ''")
phase_case("phase-unsupported-args", r"\newcommand{\lintphase}[1]{submit}", None, "unsupported declaration")
phase_case("phase-unsupported-xparse", r"\NewDocumentCommand{\lintphase}{}{submit}", None, "unsupported declaration")
phase_case("phase-unsupported-conditional", r"\iffalse\newcommand{\lintphase}{submit}\fi" + PLAN, None, "unsupported declaration")


@case("phase-precedence")
def precedence(d):
    fixture(d, r"Proving takes \tbd{time}.", phase=r"\newcommand{\lintphase}{fnial}")
    assert lint(d, "markers", phase=None, env={"LINT_PHASE": "submit"}, exit=1)["phase"] == "submit"
    assert lint(d, "markers", phase="plan", env={"LINT_PHASE": "submit"}, exit=0)["phase"] == "plan"


@case("example-setting-shares-reader")
def example(d):
    fixture(d, phase=PLAN + "\n" + r"\newcommand*{\lintexamplebox}" + "\n{custombox}")
    with (d / "scripts/lint/rules-source.lua").open("a") as f:
        f.write('\nC.rule("probe", "source", "check", "always", "probe", function() assert(C.example_box() == "custombox") end)\n')
    lint(d, "probe", exit=0)


@case("placeholder-beside-hidden-note")
def placeholder(d):
    fixture(d, r"The proving time is TBD.\todo{TBD later}")
    before = snapshot(d)
    data = lint(d, "markers", exit=1)
    fixes = [f["fix"] for f in data["findings"] if f.get("fix")]
    assert len(fixes) == 1 and fixes[0]["safety"] == "placeholder", fixes
    assert len(fixes[0]["edits"]) == 1
    assert fixes[0]["edits"][0]["at"] == 21, fixes
    run(d, "fix", "markers", "--review", "--allow-dirty", exit=0)
    assert snapshot(d) == before


@case("bib-title-still-compiles")
def bib_compile(d):
    fixture(d, "", math_bib)
    title = r"Proof that $P \neq NP$ Holds for SAT"
    def compile_title(text):
        (d / "probe.tex").write_text("\\documentclass{article}\n\\begin{document}\n" + text + "\n\\end{document}\n")
        r = subprocess.run(["xelatex", "-halt-on-error", "-interaction=batchmode", "probe.tex"], cwd=d,
                           capture_output=True, text=True)
        assert r.returncode == 0, (r.stdout, r.stderr, (d / "probe.log").read_text())
    compile_title(title)
    run(d, "fix", "bib", "--allow-dirty", exit=0)
    assert (d / BIB).read_text() == math_bib.replace("for SAT", "for {SAT}")
    compile_title(title.replace("for SAT", "for {SAT}"))


@case("balanced-groups-and-mask-columns")
def helpers(d):
    fixture(d, '\\todo[caption={x ] y}]{hidden} {Visible \\{brace\\} and Á.}\n$10-20\n+30$ More.')
    with (d / "scripts/lint/rules-source.lua").open("a") as f:
        f.write(r'''
C.rule("probe", "source", "check", "always", "probe", function()
  local body, last, first = C.balanced_group("  {one {two} \\{three\\}} tail", 1)
  assert(body == "one {two} \\{three\\}" and first == 3 and last == 23)
  local raw, printed, prose = C.raw_lines("content/01-main.tex"), C.printed_lines("content/01-main.tex"), C.prose_lines("content/01-main.tex")
  assert(#raw == #printed and #raw == #prose)
  for n, l in ipairs(raw) do assert(#l == #printed[n] and #l == #prose[n]) end
  assert(printed[2]:find("Visible", 1, true) and not printed[2]:find("hidden", 1, true))
end)
''')
    lint(d, "probe", exit=0)


for severity in ("check", "advice", "count"):
    @case("crash-" + severity)
    def crash(d, severity=severity):
        fixture(d, "Pages 10-20.")
        with (d / "scripts/lint/rules-source.lua").open("a") as f:
            f.write(f'\nC.rule("crash", "source", "{severity}", "submit", "probe", function() error("safety-reader-test") end)\n')
        before = snapshot(d)
        r = run(d, "crash", "--phase", "plan", "--json", exit=2)
        data = json.loads(r.stdout)
        assert not data["ok"] and data["rules"][0]["status"] == "error", data
        run(d, "fix", "typography", "crash", "--phase", "plan", "--allow-dirty", exit=2)
        assert snapshot(d) == before, "a crashing run wrote a fix"



# Integration regressions: main's hidden regions and punctuation behavior must
# coexist with exact-byte edit guards and the stricter phase-setting reader.
for name, literal in (
    ("alltt", "\\begin{alltt}\n10-20 \"text\"\n\\end{alltt}"),
    ("iffalse", "\\iffalse\n10-20 \"text\"\n\\fi"),
    ("iffalse-delimiter", "\\iffalse\\figure 10-20 % \\fi\n30-40\\fi"),
):
    for review in (False, True):
        fix_case("merged-" + name + ("-review" if review else "-safe"),
                 "Before 50-60. " + literal + " After 70-80.",
                 "Before 50--60. " + literal + " After 70--80.", review=review)
    reader("merged-hidden-link-" + name, literal.replace("10-20", "\\url{" + LINK + "}"), False)
    reader("merged-hidden-cite-" + name, literal.replace("10-20", r"\cite{missingkey}"), False, "bib", "missingkey")
    reader("merged-hidden-phrase-" + name, literal.replace("10-20", r"companion paper~\cite{known}"), False, needle="attached")
    reader("merged-visible-link-after-" + name, literal + "\\url{" + LINK + "}", True)

for name, literal in (
    ("url", r"\url{https://example.org/10-20/a%20b}"),
    ("url-multiline", "\\url{https://example.org/\n10-20/a%20b}"),
    ("url-delimited", r"\url|https://example.org/10-20|"),
    ("math", r"\(10-20\)"),
    ("verbatim", r'\verb|10-20 "quote"|'),
    ("texttt", r"\texttt{x : Nat}"),
    ("note", r"\todo{10-20 and hidden .}"),
    ("iffalse", r"\iffalse hidden .\fi"),
):
    @case("merged-punctuation-" + name)
    def punctuation(d, literal=literal):
        body = "The report is " + literal + ". More text."
        fixture(d, body)
        before = snapshot(d)
        assert not lint(d, "typography")["findings"], "masked bytes created a finding"
        run(d, "fix", "typography", "--review", "--allow-dirty", exit=0)
        assert snapshot(d) == before
        # Both a masked span and real punctuation on the same line: only the
        # genuine source space is diagnosed and written, at its original column.
        (d / MAIN).write_text((d / MAIN).read_text().rstrip() + " Actual prose .\n")
        before = snapshot(d)
        findings = lint(d, "typography")["findings"]
        assert len(findings) == 1 and findings[0]["msg"] == "space before punctuation", findings
        assert findings[0]["fix"]["safety"] == "safe", findings
        run(d, "fix", "typography", "--dry-run", exit=0)
        assert snapshot(d) == before
        run(d, "fix", "typography", "--allow-dirty", exit=0)
        want = dict(before)
        want[MAIN] = before[MAIN].replace(b"Actual prose .", b"Actual prose.")
        assert snapshot(d) == want
        assert not lint(d, "typography")["findings"]
        run(d, "fix", "typography", "--allow-dirty", exit=0)
        assert snapshot(d) == want

fix_case("merged-crefs-alltt", "\\begin{alltt}\nFigure~\\ref{fig:x}\n\\end{alltt} See Figure~\\ref{fig:x}.",
         "\\begin{alltt}\nFigure~\\ref{fig:x}\n\\end{alltt} See \\cref{fig:x}.", "crefs", review=True)
fix_case("merged-crefs-iffalse", "\\iffalse\nFigure~\\ref{fig:x}\n\\fi See Figure~\\ref{fig:x}.",
         "\\iffalse\nFigure~\\ref{fig:x}\n\\fi See \\cref{fig:x}.", "crefs", review=True)

for same_line in (False, True):
    @case("merged-newacronym-with-literals" + ("-same-line" if same_line else "-separate-line"))
    def acronym(d, same_line=same_line):
        fixture(d, r"\begin{alltt}VC\end{alltt} \iffalse VC\fi" + (" " if same_line else "\n") + "Every VC works.")
        (d / "content/glossary.tex").write_text(r"\newacronym{vc}{VC}{verifiable credential}" + "\n")
        data = lint(d, "acronyms", exit=1)
        findings = [f for f in data["findings"] if "VC typed by hand" in f["msg"]]
        assert len(findings) == 1, data
        assert not any("not declared" in f["msg"] for f in data["findings"]), data
        # The existing acronym rule offers a fix only when raw and visible
        # occurrence counts agree. Preserve its conservative same-line behavior.
        assert bool(findings[0].get("fix")) == (not same_line), findings
        before = snapshot(d)
        run(d, "fix", "acronyms", "--review", "--allow-dirty", exit=0)
        want = dict(before)
        if not same_line:
            want[MAIN] = before[MAIN].replace(b"Every VC works.", b"Every \\gls{vc} works.")
        assert snapshot(d) == want

phase_case("merged-phase-hidden-prose", PLAN + "\n" + r"\iffalse XXX and \url{https://example.org}\fi", "plan")
phase_case("merged-phase-conditional-renew", PLAN + "\n" + r"\iffalse\renewcommand{\lintphase}{submit}\fi", None, "unsupported declaration")
phase_case("merged-phase-alltt", "\\begin{alltt}\n\\newcommand{\\lintphase}{submit}\n\\end{alltt}\n" + PLAN, "plan")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--native", action="store_true")
    p.add_argument("--helper", help="run through this tl.sh helper when host texlua is absent")
    p.add_argument("--only", help="case-name substring")
    args = p.parse_args()
    launch(args)
    failures, count = [], 0
    with tempfile.TemporaryDirectory(prefix="lint-safety-readers-") as root:
        for name, test in CASES:
            if args.only and args.only not in name:
                continue
            count += 1
            d = Path(root) / str(count)
            d.mkdir()
            try:
                test(d)
                print("ok  " + name, flush=True)
            except (AssertionError, ValueError) as e:
                failures.append(name)
                print(f"FAIL {name}: {e}", flush=True)
            finally:
                shutil.rmtree(d)
    print(f"{count - len(failures)}/{count} passed", flush=True)
    if count == 0:
        p.error("no matching cases")
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
