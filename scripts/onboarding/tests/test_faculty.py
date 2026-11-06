"""The faculty-template import: byte-identical copies, confirmed markup only, no overwrites."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

SCRIPTS = Path(__file__).resolve().parents[2]
REPO = SCRIPTS.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures/faculty-paper"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("setup_entry", SCRIPTS / "setup.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
from onboarding import faculty  # noqa: E402


def tree(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file() and ".git" not in p.parts}


class FacultyImportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "project"
        self.paper = self.root / "paper"
        for part in ("content", "include", "bib", "scripts/lint/skeleton"):
            shutil.copytree(REPO / "paper" / part, self.paper / part)
        shutil.copy(REPO / "paper/draft.tex", self.paper / "draft.tex")
        shutil.copy(REPO / "project.json", self.root / "project.json")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def call(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = setup.main(["student", "--root", str(self.root), *args])
        return code, output.getvalue()

    def test_dry_run_writes_nothing_and_lists_every_move(self):
        before = tree(self.root)
        code, output = self.call("--import-faculty", str(FIXTURE), "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertEqual(before, tree(self.root))
        for line in ("content/04-measurements.tex", "content/00-abstract.tex", "bib/references.bib",
                     "\\label{ch:evaluation}", "\\usepackage{siunitx}", "Dry run: nothing was written."):
            self.assertIn(line, output)
        self.assertIn("\\linespread{1.05} (it changes the layout the call fixes)", output)
        self.assertNotIn("Files written", output)

    def test_import_copies_prose_byte_for_byte_and_adds_no_markup_unasked(self):
        code, output = self.call("--import-faculty", str(FIXTURE))
        self.assertEqual(code, 0, output)
        pairs = {"content/abstract.tex": "content/00-abstract.tex", "content/bevezetes.tex": "content/01-bevezetes.tex",
                 "content/measurements.tex": "content/04-measurements.tex", "content/appendices.tex": "content/10-appendices.tex",
                 "bib/mybib.bib": "bib/references.bib", "figures/flow.tex": "figures/flow.tex",
                 "include/tdk-variables.tex": "include/tdk-variables.tex"}
        for source, target in pairs.items():
            self.assertEqual((FIXTURE / source).read_bytes(), (self.paper / target).read_bytes(), target)
        self.assertEqual((REPO / "paper/include/macros.tex").read_bytes(), (self.paper / "include/macros.tex").read_bytes())
        self.assertFalse((self.paper / "include/preamble.tex").read_bytes() == (FIXTURE / "include/preamble.tex").read_bytes())
        draft = (self.paper / "draft.tex").read_text()
        self.assertIn("\\newcommand{\\vikcim}{Revocation registries for verifiable credentials}", draft)
        self.assertIn("\\newcommand{\\vikkonzulensAVezeteknev}{Tanár}", draft)
        # The faculty's placeholder second advisor is not imported over the template's.
        self.assertIn("\\newcommand{\\vikkonzulensBVezeteknev}{Kocsis}", draft)
        self.assertIn("\\include{content/01-bevezetes} % the main text starts here", draft)
        self.assertNotIn("\\include{content/02-background}", draft)
        self.assertIn("\\newcommand{\\lintphase}{plan}", draft)
        # Unused template skeletons stay, unchanged.
        self.assertEqual((REPO / "paper/content/02-background.tex").read_bytes(), (self.paper / "content/02-background.tex").read_bytes())

    def test_confirmed_suggestions_add_only_labels_lists_and_definitions(self):
        code, output = self.call("--import-faculty", str(FIXTURE), "--accept-suggestions", "--label", "content/lessons.tex=implementation")
        self.assertEqual(code, 0, output)
        expected = {"content/bevezetes.tex": ("content/01-introduction.tex", "ch:intro"),
                    "content/design.tex": ("content/02-approach.tex", "ch:approach"),
                    "content/lessons.tex": ("content/03-implementation.tex", "ch:implementation"),
                    "content/measurements.tex": ("content/04-evaluation.tex", "ch:evaluation"),
                    "content/related.tex": ("content/05-related-work.tex", "ch:related"),
                    "content/summary.tex": ("content/06-conclusion.tex", "ch:conclusion")}
        for source, (target, label) in expected.items():
            written = (self.paper / target).read_text()
            self.assertIn("}\\label{" + label + "}", written)
            # Removing the one added label gives back the student's bytes.
            self.assertEqual(written.replace("\\label{" + label + "}", "", 1), (FIXTURE / source).read_text(), target)
        appendix = (self.paper / "content/10-appendices.tex").read_text()
        self.assertIn("\\printlists\n\n\\section{The pilot", appendix.replace("%----------------------------------------------------------------------------\n\\section", "\\section"))
        macros = (self.paper / "include/macros.tex").read_text()
        self.assertTrue(macros.startswith((REPO / "paper/include/macros.tex").read_text()))
        for line in ("\\usepackage{siunitx}", "\\newcommand{\\registry}", "\\lstdefinelanguage{Policy}{", "\\newcommand{\\issuerset}"):
            self.assertIn(line, macros)
        for line in ("\\linespread", "\\usepackage{booktabs}", "\\newcommand{\\code}"):
            self.assertNotIn(line, macros)
        self.assertIn("\\include{content/06-conclusion}\n", (self.paper / "draft.tex").read_text())

    def test_refuses_to_overwrite_student_text_and_writes_nothing(self):
        (self.paper / "content/00-abstract.tex").write_text("\\chapter*{Abstract}\nMy own abstract.\n")
        before = tree(self.root)
        code, output = self.call("--import-faculty", str(FIXTURE))
        self.assertEqual(code, 1, output)
        self.assertIn("content/00-abstract.tex: already holds your text; not overwritten", output)
        self.assertEqual(before, tree(self.root))

    def test_rerun_is_unchanged(self):
        for extra in ([], ["--accept-suggestions", "--label", "./content/lessons.tex=implementation"]):
            with self.subTest(extra=extra):
                self.setUp()
                self.assertEqual(self.call("--import-faculty", str(FIXTURE), *extra)[0], 0)
                before = tree(self.root)
                code, output = self.call("--import-faculty", str(FIXTURE), *extra)
                self.assertEqual(code, 0, output)
                self.assertEqual(before, tree(self.root))
                self.assertNotIn("no longer the template's", output)
                self.assertNotIn("create,", output)

    def test_zip_with_wrapping_folder_build_output_and_refused_role(self):
        archive = Path(self.tmp.name) / "overleaf.zip"
        with zipfile.ZipFile(archive, "w") as out:
            for path in sorted(FIXTURE.rglob("*")):
                if path.is_file():
                    out.write(path, "my-paper/" + path.relative_to(FIXTURE).as_posix())
            out.writestr("my-paper/thesis.aux", "\\relax\n")
            out.writestr("my-paper/thesis.pdf", "%PDF-1.5\n")
        code, output = self.call("--import-faculty", str(archive), "--dry-run", "--accept-suggestions",
                                 "--label", "content/related.tex=none")
        self.assertEqual(code, 0, output)
        self.assertIn("thesis.aux (build output)", output)
        self.assertIn("thesis.pdf (build output)", output)
        self.assertIn("content/05-related.tex", output)
        self.assertNotIn("\\label{ch:related}", output)

    def test_unsafe_archive_paths_are_rejected(self):
        archive = Path(self.tmp.name) / "evil.zip"
        with zipfile.ZipFile(archive, "w") as out:
            out.writestr("thesis.tex", "\\documentclass{report}\\begin{document}\\end{document}")
            out.writestr("../escape.tex", "x")
        code, output = self.call("--import-faculty", str(archive), "--dry-run")
        self.assertEqual(code, 2, output)
        self.assertIn("Unsafe path", output)

    def test_hungarian_paper_is_reported(self):
        source = Path(self.tmp.name) / "hu"
        shutil.copytree(FIXTURE, source)
        main = source / "thesis.tex"
        main.write_text(main.read_text().replace("%\\input{include/thesis-hu}\n\\input{include/thesis-en}", "\\input{include/thesis-hu}"))
        code, output = self.call("--import-faculty", str(source), "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn("(main file thesis.tex, Hungarian)", output)
        self.assertIn("This template builds English papers", output)

    def test_label_on_a_non_chapter_is_an_error(self):
        code, output = self.call("--import-faculty", str(FIXTURE), "--dry-run", "--label", "content/abstract.tex=intro")
        self.assertEqual(code, 2, output)
        self.assertIn("not chapters of the main text", output)


class TemplateBaselineTest(unittest.TestCase):
    """The importer's knowledge of this template must follow the template's own files."""

    def test_placeholder_digests_match_the_template(self):
        for path, digests in faculty.PLACEHOLDERS.items():
            current = hashlib.sha256((REPO / "paper" / path).read_bytes()).hexdigest()
            self.assertIn(current, digests, path + " changed: add its new digest to faculty.PLACEHOLDERS")

    def test_draft_defaults_match_the_template(self):
        draft = (REPO / "paper/draft.tex").read_text()
        for macro, value in faculty.TEMPLATE_DEFAULTS.items():
            self.assertEqual(faculty.macro_value(draft, macro), value, macro)
        self.assertIn(faculty.TEMPLATE_CHAPTERS, draft)
        self.assertIn(faculty.TEMPLATE_BIBLIOGRAPHY, draft)

    def test_project_config_names_the_draft(self):
        self.assertTrue(json.loads((REPO / "project.json").read_text())["paper_main"].endswith("/draft.tex"))


if __name__ == "__main__":
    unittest.main()
