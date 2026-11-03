"""Tests for review.py. No network: `gh` is replaced by a fake. Run from the repository root:

    python3 -m unittest scripts/review/test_review.py
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review  # noqa: E402

SHA = "0123456789abcdef0123456789abcdef01234567"
DIGEST = "sha256:" + "ab" * 32
LOG = "This is XeTeX, Version 3.141592653 (TeX Live 2025)\n! Undefined control sequence.\n! Missing $ inserted.\n"
LOG += "LaTeX Warning: Reference `fig:a' on page 3 undefined on input line 9.\n"
LOG += "Package natbib Warning: Citation `very-long-key' on page 12\n(natbib)  undefined on input line 70.\n"
LOG += "LaTeX Warning: There were undefined references.\n"
CI_ENV = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "BlackLight54/TDK26-Example", "GITHUB_SHA": SHA,
          "GITHUB_REF_NAME": "main", "GITHUB_SERVER_URL": "https://github.com", "GITHUB_RUN_ID": "42", "GITHUB_RUN_ATTEMPT": "2"}


def call(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = review.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


def write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content if isinstance(content, bytes) else content.encode())
    return path


def cp(code=0, out="", err=""):
    return subprocess.CompletedProcess([], code, out, err)


class Workdir(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="test-review-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def make_bundle(self, name="bundle", extra=()):
        """A CI bundle made by `review.py bundle` from a fake build."""
        built = self.tmp / f"{name}-built"
        for doc in ("draft", "final"):
            write(built / f"{doc}.pdf", b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n2 0 obj << /Type /Pages >> endobj\n")
            write(built / f"{doc}.log", LOG)
        write(self.tmp / f"{name}-lint.json", json.dumps({"phase": "polish", "phase_source": "\\lintphase in draft.tex", "profile": "tdk"}))
        write(self.tmp / f"{name}-skim" / "skim.md", "# skim\n![Figure 1](assets/fig1.png)\n")
        write(self.tmp / f"{name}-skim" / "skim.html", "<html></html>")
        write(self.tmp / f"{name}-skim" / "assets" / "fig1.png", b"png1")
        write(self.tmp / f"{name}-skim" / "assets" / "page-001.png", b"png2")
        out = self.tmp / name
        args = ["bundle", "--built", built, "--lint", self.tmp / f"{name}-lint.json", "--skim", self.tmp / f"{name}-skim",
                "--out", out, "--exit", "draft=0", "--exit", "final=0", "--exit", "lint=1", "--exit", "skim=0",
                "--image-ref", "texlive/texlive:latest", "--image-digest", DIGEST, *extra]
        with mock.patch.dict(os.environ, CI_ENV):
            code, _, err = call(*args)
        self.assertEqual(code, 0, err)
        return out


class TestBundle(Workdir):
    def test_counts_in_a_log(self):
        self.assertEqual(review.count_errors(LOG), 2)
        self.assertEqual(review.count_undefined(LOG), 2)  # the second one is wrapped; the summary line is not a warning

    def test_manifest_has_every_field_of_the_contract(self):
        m = review.load_manifest(self.make_bundle())
        self.assertEqual([m["schema"], m["repo"], m["sha"], m["ref"]], [2, "BlackLight54/TDK26-Example", SHA, "main"])
        self.assertEqual(m["built"], {"by": "ci", "run_url": "https://github.com/BlackLight54/TDK26-Example/actions/runs/42", "run_attempt": 2})
        self.assertEqual(m["image"], {"ref": "texlive/texlive:latest", "digest": DIGEST})
        self.assertEqual([m["phase"], m["phase_source"], m["profile"]], ["polish", "\\lintphase in draft.tex", "tdk"])
        self.assertEqual(m["builds"][1], {"doc": "final", "engine": "xelatex", "latexmk_exit": 0, "started": True, "errors": 2, "undefined": 2, "pages": 1})
        self.assertEqual([m["lint"], m["skim"]], [{"exit": 1}, {"exit": 0}])
        self.assertEqual(set(m["files"]), {"draft.pdf", "final.pdf", "logs/draft.log", "logs/final.log", "lint.json",
                                           "skim/skim.md", "skim/skim.html", "skim/assets/fig1.png", "skim/assets/page-001.png"})

    def test_a_build_that_never_started_is_recorded_not_refused(self):
        built = self.tmp / "half-built"
        # This stale PDF must not become evidence for a build that has no log.
        write(built / "draft.pdf", b"%PDF-1.4 stale")
        write(built / "final.pdf", b"%PDF-1.4\n1 0 obj << /Type /Page >> endobj\n")
        write(built / "final.log", LOG)
        write(self.tmp / "half-lint.json", "{}")
        write(self.tmp / "half-skim" / "skim.md", "x")
        args = ["bundle", "--built", built, "--lint", self.tmp / "half-lint.json", "--skim", self.tmp / "half-skim", "--out", self.tmp / "half",
                "--exit", "draft=1", "--exit", "final=0", "--exit", "lint=2", "--exit", "skim=1"]
        with mock.patch.dict(os.environ, CI_ENV):
            code, _, err = call(*args)
        self.assertEqual(code, 0, err)
        self.assertIn("draft build is recorded as not started", err)
        m = review.load_manifest(self.tmp / "half")
        self.assertEqual(m["builds"][0], {"doc": "draft", "engine": None, "latexmk_exit": 1, "started": False, "errors": None, "undefined": None, "pages": None})
        self.assertTrue(m["builds"][1]["started"])
        self.assertEqual(set(m["files"]), {"final.pdf", "logs/final.log", "lint.json", "skim/skim.md"})
        # a success without a log is a contradiction, and no log at all is no evidence
        base = ["bundle", "--built", built, "--lint", self.tmp / "half-lint.json", "--skim", self.tmp / "half-skim"]
        with mock.patch.dict(os.environ, CI_ENV):
            code, _, err = call(*base, "--out", self.tmp / "half2", "--exit", "draft=0", "--exit", "final=0")
        self.assertEqual(code, 1)
        self.assertIn("draft=0 says the build succeeded", err)
        (built / "final.log").unlink()
        with mock.patch.dict(os.environ, CI_ENV):
            code, _, err = call(*base, "--out", self.tmp / "half3", "--exit", "draft=1", "--exit", "final=1")
        self.assertEqual(code, 1)
        self.assertIn("neither build left a log", err)

    def test_lint_startup_failure_keeps_diagnostics_without_claiming_json(self):
        self.make_bundle()
        lint = self.tmp / "bundle-lint.json"
        stderr = self.tmp / "lint.stderr"
        write(stderr, "lint: unknown phase 'finall'\n")
        base = ["bundle", "--built", self.tmp / "bundle-built", "--lint", lint,
                "--lint-stderr", stderr,
                "--skim", self.tmp / "no-skim", "--exit", "draft=0", "--exit", "final=0", "--exit", "skim=1"]
        for name, raw in (("empty", ""), ("broken", "not JSON"), ("array", "[]"), ("missing", None)):
            with self.subTest(name=name):
                if raw is None:
                    lint.unlink()
                else:
                    write(lint, raw)
                out = self.tmp / name
                with mock.patch.dict(os.environ, CI_ENV):
                    code, _, err = call(*base, "--exit", "lint=2", "--out", out)
                self.assertEqual(code, 0, err)
                manifest, problems = review.verify_bundle(out, SHA)
                self.assertEqual(problems, [])
                self.assertEqual(manifest["lint"]["exit"], 2)
                self.assertEqual(manifest["lint"]["status"], "unavailable")
                self.assertIsNone(manifest["phase"])
                self.assertIn("logs/final.log", manifest["files"])
                self.assertIn("final.pdf", manifest["files"])
                self.assertNotIn("lint.json", manifest["files"])
                self.assertIn("logs/lint-stderr.txt", manifest["files"])
                self.assertEqual((out / "logs/lint-stderr.txt").read_text(), stderr.read_text())
                if raw is not None:
                    self.assertEqual((out / "logs/lint-output.txt").read_text(), raw)
                with mock.patch.dict(os.environ, CI_ENV):
                    code, _, err = call(*base, "--exit", "lint=0", "--out", self.tmp / (name + "-success"))
                self.assertEqual(code, 1)
                self.assertIn("not readable JSON", err)

    def test_sha_and_ref_options_override_the_environment(self):
        other = "f" * 40
        m = review.load_manifest(self.make_bundle(extra=["--sha", other, "--ref", "feature"]))
        self.assertEqual([m["sha"], m["ref"]], [other, "feature"])

    def test_a_digest_is_recorded_as_given_and_checked_for_its_form(self):
        built = self.tmp / "b"
        code, _, err = call("bundle", "--built", built, "--lint", "x", "--skim", "x", "--out", self.tmp / "o",
                            "--exit", "draft=0", "--exit", "final=0", "--image-digest", "latest")
        self.assertEqual(code, 1)
        self.assertIn("sha256:<hex>", err)

    def test_a_missing_or_empty_lint_file_is_recorded_as_lint_exit_2(self):
        built = self.tmp / "nolint-built"
        for doc in ("draft", "final"):
            write(built / f"{doc}.pdf", b"%PDF-1.4 /Type /Page")
            write(built / f"{doc}.log", LOG)
        write(self.tmp / "nolint-skim" / "skim.md", "x")
        for lint in (self.tmp / "absent.json", write(self.tmp / "empty.json", "")):
            out = self.tmp / f"out-{lint.stem}"
            with mock.patch.dict(os.environ, CI_ENV):
                code, _, err = call("bundle", "--built", built, "--lint", lint, "--skim", self.tmp / "nolint-skim", "--out", out,
                                    "--exit", "draft=0", "--exit", "final=0", "--exit", "lint=2", "--exit", "skim=0")
            self.assertEqual(code, 0, err)
            self.assertIn("lint exited 2", err)
            m = review.load_manifest(out)
            self.assertEqual(m["lint"]["exit"], 2)
            self.assertEqual(m["lint"]["status"], "unavailable")
            self.assertEqual([m["phase"], m["phase_source"]], [None, None])
            self.assertNotIn("lint.json", m["files"])
            self.assertFalse((out / "lint.json").exists())
        # a file with content that is not JSON is garbage, not a lint that did not run
        write(self.tmp / "garbage.json", "not json")
        with mock.patch.dict(os.environ, CI_ENV):
            code, _, err = call("bundle", "--built", built, "--lint", self.tmp / "garbage.json", "--skim", self.tmp / "nolint-skim",
                                "--out", self.tmp / "out-garbage", "--exit", "draft=0", "--exit", "final=0")
        self.assertEqual(code, 1)
        self.assertIn("not readable JSON", err)

    def test_a_build_outside_git_is_recorded_as_unverified(self):
        built = self.tmp / "nogit"
        for doc in ("draft", "final"):
            write(built / f"{doc}.pdf", b"%PDF-1.4 /Type /Page")
            write(built / f"{doc}.log", LOG)
        write(self.tmp / "nogit-lint.json", "{}")
        write(self.tmp / "nogit-skim" / "skim.md", "x")
        self.assertIsNone(review.git(built, "rev-parse", "HEAD"))  # the test's premise: no checkout here
        code, _, err = call("bundle", "--built", built, "--lint", self.tmp / "nogit-lint.json", "--skim", self.tmp / "nogit-skim",
                            "--out", self.tmp / "nogit-out", "--exit", "draft=0", "--exit", "final=0", "--by", "local",
                            "--repo", "a/b", "--ref", "main", "--sha", SHA)
        self.assertEqual(code, 0, err)
        self.assertIn("unverified", err)
        b = review.load_manifest(self.tmp / "nogit-out")["built"]
        self.assertEqual([b["by"], b["unverified"]], ["local", True])
        self.assertNotIn("dirty", b)

    def test_a_dirty_local_tree_is_refused_unless_allowed(self):
        repo = self.tmp / "paper"
        git = lambda *a: subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True, capture_output=True)
        repo.mkdir()
        git("init", "-q")
        write(repo / "draft.tex", "x")
        git("add", "draft.tex")
        git("commit", "-q", "-m", "x")
        for doc in ("draft", "final"):
            write(repo / f"{doc}.log", LOG)
            write(repo / f"{doc}.pdf", b"%PDF-1.4 /Type /Page")
        write(self.tmp / "lint.json", "{}")
        write(self.tmp / "skim" / "skim.md", "x")
        write(repo / "draft.tex", "edited")
        args = ["bundle", "--built", repo, "--lint", self.tmp / "lint.json", "--skim", self.tmp / "skim", "--exit", "draft=0",
                "--exit", "final=0", "--by", "local", "--repo", "a/b"]
        code, _, err = call(*args, "--out", self.tmp / "o1")
        self.assertEqual(code, 1)
        self.assertIn("dirty", err)
        code, _, err = call(*args, "--out", self.tmp / "o2", "--allow-dirty")
        self.assertEqual(code, 0, err)
        built = review.load_manifest(self.tmp / "o2")["built"]
        self.assertTrue(built["dirty"])
        self.assertNotIn("run_url", built)


class TestFetch(Workdir):
    def fake_gh(self, bundle, runs=None, downloads=True):
        runs = [{"databaseId": 7, "status": "completed", "conclusion": "failure", "createdAt": "2026-10-28"}] if runs is None else runs
        calls = []
        def gh(args):
            calls.append(args)
            if args[:2] == ["run", "list"]:
                return cp(out=json.dumps(runs))
            if args[:2] == ["run", "download"]:
                if not downloads:
                    return cp(1, err="no valid artifacts found to download")
                shutil.copytree(bundle, args[args.index("-D") + 1], dirs_exist_ok=True)
                return cp()
            raise AssertionError(args)
        gh.calls = calls
        return gh

    def fetch(self, gh, *extra):
        with mock.patch.object(review, "gh", gh):
            return call("fetch", "--legacy", "--repo", "BlackLight54/TDK26-Example", "--sha", SHA, "--out", self.tmp / "got", *extra)

    def test_a_whole_bundle_is_fetched_and_its_path_printed(self):
        bundle = self.make_bundle()
        gh = self.fake_gh(bundle)
        code, out, err = self.fetch(gh)
        self.assertEqual((code, out.strip()), (0, str(self.tmp / "got")), err)
        self.assertEqual(gh.calls[1][:5], ["run", "download", "7", "-R", "BlackLight54/TDK26-Example"])
        self.assertIn(f"review-{SHA[:7]}", gh.calls[1])

    def test_a_changed_file_fails_the_verification_and_is_named(self):
        bundle = self.make_bundle()
        write(bundle / "final.pdf", b"another build")
        code, _, err = self.fetch(self.fake_gh(bundle))
        self.assertEqual(code, 1)
        self.assertIn("final.pdf: SHA-256 differs", err)

    def test_an_unlisted_or_missing_file_fails_the_verification(self):
        bundle = self.make_bundle()
        write(bundle / "extra.txt", "x")
        (bundle / "lint.json").unlink()
        _, problems = review.verify_bundle(bundle, SHA)
        self.assertEqual(sorted(problems), ["extra.txt: in the bundle but not listed in manifest.json",
                                            "lint.json: listed in manifest.json but missing"])

    def test_a_bundle_of_another_commit_is_refused(self):
        bundle = self.make_bundle()
        m = review.load_manifest(bundle)
        m["sha"] = "e" * 40
        write(bundle / "manifest.json", json.dumps(m))
        code, _, err = self.fetch(self.fake_gh(bundle))
        self.assertEqual(code, 1)
        self.assertIn("manifest.json: sha is", err)

    def test_an_expired_artifact_prints_the_rerun_command(self):
        code, _, err = self.fetch(self.fake_gh(None, downloads=False))
        self.assertEqual(code, 1)
        self.assertIn("gh run rerun 7 -R BlackLight54/TDK26-Example", err)

    def test_no_run_is_said_plainly(self):
        code, _, err = self.fetch(self.fake_gh(None, runs=[]))
        self.assertEqual(code, 1)
        self.assertIn("no paper.yml run", err)


class TestModernFetch(Workdir):
    def invoke(self, bundle, *, transport_error=None, run=42, attempt=2):
        def gh(args):
            if args[:2] == ["run", "list"]:
                return cp(out=json.dumps([{"databaseId":42,"status":"completed","createdAt":"2026-11-04"}]))
            if args == ["api", "repos/BlackLight54/TDK26-Example"]:
                return cp(out=json.dumps({"id":123}))
            if args == ["api", "repos/BlackLight54/TDK26-Example/actions/runs/42"]:
                return cp(out=json.dumps({"run_attempt":2}))
            raise AssertionError(args)
        calls=[]
        def transport(**kwargs):
            calls.append(kwargs)
            if transport_error:
                raise review.Fail(transport_error)
            shutil.copytree(bundle, kwargs["output"])
            return {"artifact_id":19,"artifact_sha256":"ab"*32,"run_id":42,"run_attempt":2}
        selectors=[] if run is None else ["--run",run,"--attempt",attempt]
        with mock.patch.object(review,"gh",gh), mock.patch.object(review,"fetch_transport",transport):
            result=call("fetch","--repo","BlackLight54/TDK26-Example","--sha",SHA,
                        "--out",self.tmp/"got",*selectors)
        return result,calls

    def test_exact_attempt_contract_and_separate_transport_receipt(self):
        result,calls=self.invoke(self.make_bundle())
        self.assertEqual(result[0],0,result[2])
        self.assertEqual(calls[0]["artifact_name"],f"review-{SHA}-42-2")
        self.assertEqual(calls[0]["workflow_path"],".github/workflows/ci.yml")
        self.assertEqual(calls[0]["repository_id"],123)
        receipt=json.loads((self.tmp/"got.transport.json").read_text())
        self.assertEqual(receipt["manifest_sha256"],review.sha256_file(self.tmp/"got/manifest.json"))
        self.assertEqual(review.verify_bundle(self.tmp/"got",SHA)[1],[])

    def test_latest_completed_selection_does_not_fall_back_on_missing_artifact(self):
        result,calls=self.invoke(None,transport_error="Exact attempt artifact missing",run=None)
        self.assertEqual(result[0],1)
        self.assertEqual(len(calls),1)
        self.assertFalse((self.tmp/"got.transport.json").exists())

    def test_attempt_mismatch_is_rejected_after_file_verification(self):
        result,_=self.invoke(self.make_bundle(),attempt=3)
        self.assertEqual(result[0],1)
        self.assertIn("does not match",result[2])

    def test_downloaded_file_tamper_is_rejected(self):
        bundle=self.make_bundle()
        (bundle/"final.pdf").write_bytes(b"changed")
        result,_=self.invoke(bundle)
        self.assertEqual(result[0],1)
        self.assertIn("SHA-256 differs",result[2])


class TestInputs(Workdir):
    def inputs(self, bundle, *personas, spine=None):
        extra = ["--spine", spine] if spine else []
        code, out, err = call("inputs", bundle, *personas, *extra)
        self.assertEqual(code, 0, err)
        result = json.loads(out)
        for entry in result.values():
            self.addCleanup(shutil.rmtree, entry["dir"], ignore_errors=True)
        return result

    def test_every_persona_file_has_valid_frontmatter(self):
        for path in sorted(review.PERSONAS.glob("*.md")):
            reads = review.persona_reads(review.PERSONAS, path.stem)
            self.assertTrue(set(reads) <= set(review.READS), path.name)
        self.assertEqual(review.persona_reads(review.PERSONAS, "skim"), ["skim-view"])

    def test_a_persona_directory_holds_its_reads_and_nothing_else(self):
        bundle = self.make_bundle()
        spine = write(self.tmp / "my-spine.md", "claims")
        r = self.inputs(bundle, "skim", "cryptographer", "champion", spine=spine)

        skim = Path(r["skim"]["dir"])
        self.assertEqual(sorted(r["skim"]["files"]), ["assets/fig1.png", "assets/page-001.png", "skim.md"])
        self.assertFalse((skim / "final.pdf").exists())
        self.assertFalse((skim / "spine.md").exists())
        self.assertFalse(r["skim"]["spine"])

        self.assertEqual(sorted(r["cryptographer"]["files"]), ["final.pdf", "spine.md"])
        self.assertTrue(r["cryptographer"]["spine"])
        self.assertEqual(review.walk_files(r["cryptographer"]["dir"]), ["final.pdf", "spine.md"])

        self.assertEqual(len({r[p]["dir"] for p in r}), 3)  # one directory each
        self.assertFalse(review.inside_repo(r["champion"]["dir"]))
        m = review.load_manifest(bundle)
        self.assertEqual(r["cryptographer"]["files"]["final.pdf"], m["files"]["final.pdf"])

    def test_each_persona_directory_names_the_persona_file_it_was_made_for(self):
        bundle = self.make_bundle()
        got = json.loads(call_inputs(bundle, "cryptographer"))
        self.addCleanup(shutil.rmtree, got["cryptographer"]["dir"], ignore_errors=True)
        v = got["cryptographer"]["persona"]
        self.assertEqual(v["file"], "cryptographer.md")
        self.assertEqual(v["sha256"], review.sha256_file(review.PERSONAS / "cryptographer.md"))
        self.assertIn("commit", v)

    def test_without_a_spine_the_entry_says_so(self):
        r = self.inputs(self.make_bundle(), "cryptographer")
        self.assertFalse(r["cryptographer"]["spine"])
        self.assertEqual(review.walk_files(r["cryptographer"]["dir"]), ["final.pdf"])

    def test_a_tampered_bundle_yields_no_directories(self):
        bundle = self.make_bundle()
        write(bundle / "skim" / "skim.md", "edited")
        before = set(Path(tempfile.gettempdir()).glob("review-*"))
        code, _, err = call("inputs", bundle, "skim")
        self.assertEqual(code, 1)
        self.assertIn("skim/skim.md", err)
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("review-*")), before)


class TestRecord(Workdir):
    def setUp(self):
        super().setUp()
        self.bundle = self.make_bundle()
        self.inputs = json.loads(call_inputs(self.bundle, "skim", "cryptographer"))
        for e in self.inputs.values():
            self.addCleanup(shutil.rmtree, e["dir"], ignore_errors=True)
        write(self.tmp / "inputs.json", json.dumps(self.inputs))
        self.findings = {
            "sha": SHA, "bundle": f"review-{SHA[:7]}", "mode": "draft", "panel": ["skim", "cryptographer"],
            "skipped": {"process-modeling": "no BPMN"}, "model": "claude-opus-5-5",
            "scores": {"A": [4, 5], "B/1": [3, 4], "B/2": [2, 4], "C": [7, 8], "D/1": [3, 5], "D/2": [3, 5], "E": [5, 8]},
            "findings": [
                {"id": "F1", "persona": "cryptographer", "criterion": "D/2", "severity": "blocker",
                 "where": 'p. 14 "the verifier learns nothing"', "objection": "No adversary is defined.\nIt is implied.", "answer": "Add Def. 2 to ch. 4"},
                {"id": "F2", "persona": "skim", "criterion": "E", "severity": "major", "where": "SG2", "objection": "SG2 has no row", "answer": "Add it"},
            ]}

    def record(self, *extra, findings=None):
        write(self.tmp / "findings.json", json.dumps(findings or self.findings))
        return call("record", self.tmp / "findings.json", "--bundle", self.bundle, "--inputs", self.tmp / "inputs.json", *extra)

    def test_dry_run_renders_every_finding_and_the_manifest(self):
        code, out, err = self.record("--dry-run")
        self.assertEqual(code, 0, err)
        self.assertRegex(out, r"Title: Review \d{4}-\d\d-\d\d 0123456\n")
        self.assertIn("- [ ] F1 cryptographer · D/2 · blocker · p. 14 \"the verifier learns nothing\": No adversary is defined. It is implied. Answer: Add Def. 2 to ch. 4", out)
        self.assertIn("- [ ] F2 skim · E · major · SG2: SG2 has no row. Answer: Add it", out)
        self.assertIn("| E | 5 | 8 |", out)
        self.assertIn("Total 24.5 of 35", out)
        self.assertIn("`review-confirmed`", out)
        self.assertIn("https://github.com/BlackLight54/TDK26-Example/actions/runs/42", out)
        manifest = review.load_manifest(self.bundle)
        self.assertIn(json.dumps(manifest, indent=2), out)
        self.assertIn(manifest["files"]["final.pdf"], out)  # in the manifest block and in the inputs block

    def test_the_issue_names_the_persona_versions(self):
        code, out, err = self.record("--dry-run")
        self.assertEqual(code, 0, err)
        self.assertIn("Persona versions", out)
        self.assertIn(f"cryptographer  {self.inputs['cryptographer']['persona']['sha256']}", out)
        self.assertIn(f"skim  {self.inputs['skim']['persona']['sha256']}", out)

    def test_inline_inputs_still_record_the_supplied_persona_versions(self):
        self.findings["inputs"] = {p: v["files"] for p, v in self.inputs.items()}
        code, out, err = self.record("--dry-run")
        self.assertEqual(code, 0, err)
        self.assertIn(f"skim  {self.inputs['skim']['persona']['sha256']}", out)
        self.assertNotIn("not recorded", out)

    def test_inline_inputs_cannot_borrow_versions_from_different_inputs(self):
        self.findings["inputs"] = {p: dict(v["files"]) for p, v in self.inputs.items()}
        self.findings["inputs"]["cryptographer"]["final.pdf"] = "0" * 64
        code, _, err = self.record("--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("differs between findings.json and --inputs", err)

    def test_a_dirty_bundle_is_never_recorded(self):
        mp = self.bundle / "manifest.json"
        m = json.loads(mp.read_text())
        m["built"] = {"by": "local", "host": "laptop", "dirty": True}
        mp.write_text(json.dumps(m))
        code, _, err = self.record("--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("dirty tree", err)
        self.assertIn("ad hoc run", err)

    def test_an_unverified_bundle_is_never_recorded(self):
        mp = self.bundle / "manifest.json"
        m = json.loads(mp.read_text())
        m["built"] = {"by": "local", "host": "laptop", "unverified": True}
        mp.write_text(json.dumps(m))
        code, _, err = self.record("--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("unverified", err)
        self.assertIn("ad hoc run", err)

    def test_a_finding_outside_the_contract_is_refused(self):
        self.findings["findings"][0]["severity"] = "fatal"
        self.findings["findings"][1]["persona"] = "nobody"
        code, _, err = self.record("--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("finding F1: severity must be one of", err)
        self.assertIn("finding F2: persona 'nobody' is not in the panel", err)

    def test_scores_go_with_the_skim(self):
        del self.findings["scores"]
        code, _, err = self.record("--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("scores: the skim ran", err)

    def test_inapplicable_b1_uses_b2_and_records_the_reason(self):
        self.findings["scores"]["B/1"] = [None, 4]
        self.findings["score_na_reasons"] = {"B/1": "The topic needs no figures or tables.\nChecked against the sheet."}
        code, out, err = self.record("--dry-run")
        self.assertEqual(code, 0, err)
        self.assertIn("| B/1 | N/A | 4 |", out)
        self.assertIn("B/1 is N/A: The topic needs no figures or tables. Checked against the sheet.", out)
        self.assertIn("Total 24 of 35", out)
        self.assertIn("or B/2 when B/1 is N/A", out)

    def test_inapplicable_b1_requires_a_nonempty_reason(self):
        self.findings["scores"]["B/1"] = [None, 4]
        for reasons in ({}, {"B/1": ""}, {"B/1": "  "}, {"B/1": None}, {"B/2": "Not applicable"}, []):
            with self.subTest(reasons=reasons):
                self.findings["score_na_reasons"] = reasons
                code, _, err = self.record("--dry-run")
                self.assertEqual(code, 1)
                self.assertIn("score_na_reasons:", err)

    def test_only_b1_accepts_an_explicit_na_score(self):
        for criterion in review.CRITERIA:
            if criterion == "B/1":
                continue
            with self.subTest(criterion=criterion):
                original = self.findings["scores"][criterion]
                self.findings["scores"][criterion] = [None, original[1]]
                code, _, err = self.record("--dry-run")
                self.assertEqual(code, 1)
                self.assertIn("scores:", err)
                self.findings["scores"][criterion] = original
        self.findings["scores"]["B/1"] = [None, 5]
        code, _, err = self.record("--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("scores:", err)

    def test_an_omitted_b1_stays_incomplete_and_is_not_na(self):
        del self.findings["scores"]["B/1"]
        code, out, err = self.record("--dry-run")
        self.assertEqual(code, 0, err)
        self.assertNotIn("Total ", out)
        self.assertNotIn("N/A", out)
        self.findings["score_na_reasons"] = {"B/1": "Not applicable"}
        code, _, err = self.record("--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("score_na_reasons:", err)

    def test_zero_b1_is_scored_in_the_average(self):
        self.findings["scores"]["B/1"] = [0, 4]
        code, out, err = self.record("--dry-run")
        self.assertEqual(code, 0, err)
        self.assertIn("Total 23 of 35", out)
        self.findings["score_na_reasons"] = {"B/1": "Not applicable"}
        code, _, err = self.record("--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("score_na_reasons:", err)

    def test_input_hashes_must_come_from_the_bundle(self):
        self.inputs["cryptographer"]["files"]["final.pdf"] = "0" * 64
        write(self.tmp / "inputs.json", json.dumps(self.inputs))
        code, _, err = self.record("--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("cryptographer/final.pdf", err)

    def test_filing_runs_gh_issue_create_and_prints_the_url(self):
        seen = {}
        def gh(args):
            seen["args"] = args
            seen["body"] = Path(args[args.index("--body-file") + 1]).read_text()
            return cp(out="https://github.com/BlackLight54/TDK26-Example/issues/3\n")
        with mock.patch.object(review, "gh", gh):
            code, out, err = self.record()
        self.assertEqual((code, out.strip()), (0, "https://github.com/BlackLight54/TDK26-Example/issues/3"), err)
        self.assertEqual(seen["args"][:4], ["issue", "create", "-R", "BlackLight54/TDK26-Example"])
        self.assertIn("F2 skim", seen["body"])


def call_inputs(bundle, *personas):
    code, out, err = call("inputs", bundle, *personas)
    assert code == 0, err
    return out


if __name__ == "__main__":
    unittest.main()
