#!/usr/bin/env python3
"""Real texlua regressions for unfinished evaluation measurements; no PDF build needed."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PAPER = Path(__file__).resolve().parents[3]


def table(value, header="Time (s)", env="tabular", endrow=True):
    args = r"{\linewidth}{lr}" if env in ("tabularx", "tabular*") else "{lr}"
    return ("\\begin{" + env + "}" + args + "\n\\toprule\nMethod & " + header
            + " \\\\\n\\midrule\nThis work & " + value + (" \\\\" if endrow else "")
            + "\n\\bottomrule\n\\end{" + env + "}\n")


class EvaluationResultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("texlua"):
            raise RuntimeError("Run with TeX Live, e.g. inside the paper CI image")

    def lint(self, body, phase="polish", role="evaluation", extra=None):
        with tempfile.TemporaryDirectory(prefix="evaluation-lint-") as directory:
            root = Path(directory)
            shutil.copytree(PAPER / "scripts/lint", root / "scripts/lint")
            shutil.copy2(PAPER / "scripts/lint.lua", root / "scripts/lint.lua")
            (root / "content").mkdir()
            (root / "draft.tex").write_text(r"\include{content/results}" + "\n"
                                            + (r"\include{content/more}" if extra else ""))
            (root / "content/results.tex").write_text(
                "\\chapter{Evidence}\\label{ch:" + role + "}\n" + body)
            if extra:
                (root / "content/more.tex").write_text(
                    r"\chapter{More evidence}\label{ch:evaluation:more}" + "\n" + extra)
            env = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_")}
            run = subprocess.run(["texlua", "scripts/lint.lua", "evaluation-results", "--json", "--phase", phase],
                                 cwd=root, env=env, text=True, capture_output=True, timeout=15)
            self.assertIn(run.returncode, (0, 1), run.stdout + run.stderr)
            report = json.loads(run.stdout)
            result = dict(report["rules"][0], findings=report["findings"])
            self.assertEqual(result["rule"], "evaluation-results")
            self.assertNotEqual(result["status"], "error", run.stdout)
            return run.returncode, result

    def test_each_unfinished_measurement_fails(self):
        for value in ("", " ", "TODO", "TBD ms", "XXX", "?", "--", r"\textemdash",
                      r"\tbd{measured seconds}", r"\num{}", r"\SI{}{\second}",
                      r"\cite{bench2026}", r"\ref{tab:42}", r"\url{https://host/123}",
                      r"\unknownresult{42}", "N/A", "N/A: TODO", "12.3 (TODO repeats)"):
            with self.subTest(value=value):
                code, result = self.lint(table(value))
                self.assertEqual(code, 1, result)
                self.assertGreater(result["errors"], 0)

    def test_filled_numbers_and_explained_absence(self):
        for value in ("0", "-0.25", "1.2e-3", r"$1.2 \pm 0.1$", r"98.6\%",
                      r"\textbf{2.5}", r"\num{1.2e3}", r"\qty{12}{\milli\second}",
                      "N/A: no matching event", "N/A (operation unsupported)",
                      "not measured: solver exhausted memory", "timeout after 60 s"):
            with self.subTest(value=value):
                code, result = self.lint(table(value))
                self.assertEqual((code, result["status"]), (0, "pass"), result)

    def test_phase_gate(self):
        for phase in ("plan", "draft", "polish", "submit"):
            code, result = self.lint(table("TODO"), phase=phase)
            self.assertEqual(code, int(phase in ("polish", "submit")))
            self.assertEqual(result["status"], "fix" if code else "due at polish")

    def test_numerical_fields_in_prose_and_ranges(self):
        for value in (r"The median was \num{}.", r"It took \SI{TODO}{s}.",
                      r"Cost was \qty[round-mode=places]{}{\second}.", r"Between \numrange{2}{}.",
                      r"Between \qtyrange{}{3}{s}.", r"We measured \num{N/A: unavailable}."):
            with self.subTest(value=value):
                self.assertEqual(self.lint(value)[0], 1)
        self.assertEqual(self.lint(r"Between \numrange{0.1}{2.3}; runtime \SI{12}{\second}.")[0], 0)

    def test_notes_comments_code_and_other_roles_do_not_count(self):
        body = ("% " + table("TODO").replace("\n", "\n% ") + "\n"
                + r"\todo{Runtime \num{}} \advisortodo{\SI{}{s}} \verb|\num{}|" + "\n"
                + r"\begin{lstlisting}\num{}\end{lstlisting}" + "\n"
                + r"\iffalse\num{}\fi" + "\n")
        self.assertEqual(self.lint(body)[1]["status"], "skipped")
        self.assertEqual(self.lint(table("TODO"), role="background")[1]["status"], "skipped")

    def test_setup_digits_do_not_fill_a_result(self):
        self.assertEqual(self.lint("2026, 32 cores, 1000 runs. " + table(""))[0], 1)

    def test_qualitative_evaluation_is_not_forced_to_invent_numbers(self):
        code, result = self.lint(table("proved", header="Property status"))
        self.assertEqual((code, result["status"]), (0, "skipped"))

    def test_all_evaluation_chapters_and_arbitrary_filename(self):
        self.assertEqual(self.lint(table("2"), extra=table("TODO"))[0], 1)

    def test_literal_alignments_and_last_row_without_separator(self):
        for env in ("tabular", "tabular*", "tabularx", "longtable"):
            for endrow in (True, False):
                with self.subTest(env=env, endrow=endrow):
                    self.assertEqual(self.lint(table("", env=env, endrow=endrow))[0], 1)

    def test_multiline_grouped_and_escaped_separators(self):
        body = table("12.5").replace("Method &", r"Method \& variant &").replace("This work &", r"\makecell{This \\ work} &")
        self.assertEqual(self.lint(body)[0], 0)
        self.assertEqual(self.lint(body.replace("12.5", "\n  " ))[0], 1)

    def test_header_without_data_does_not_pass(self):
        body = r"\begin{tabular}{lr} Method & Time (s) \\ \end{tabular}"
        code, result = self.lint(body)
        self.assertEqual(code, 1)
        self.assertTrue(any("no result rows" in f["msg"] for f in result["findings"]))

    def test_complex_tables_request_manual_review(self):
        body = table(r"\multicolumn{1}{r}{TODO}")
        code, result = self.lint(body)
        self.assertEqual((code, result["status"]), (0, "skipped"))
        self.assertTrue(any("manual numerical review" in f["msg"] for f in result["findings"]))

    def test_measurement_not_completed_by_a_different_column(self):
        body = r"\begin{tabular}{lrr} Method & Time (s) & Memory (MiB) \\ Work & 12 & \\ \end{tabular}"
        code, result = self.lint(body)
        self.assertEqual(code, 1)
        self.assertTrue(any("column 3" in f["msg"] for f in result["findings"]))


if __name__ == "__main__":
    unittest.main()
