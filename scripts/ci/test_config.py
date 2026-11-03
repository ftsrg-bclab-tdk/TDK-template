import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from config import load_project, validate_project

ROOT = Path(__file__).resolve().parents[2]


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = json.loads((ROOT / "project.json").read_text())

    def load(self):
        path = self.root / "project.json"
        path.write_text(json.dumps(self.config))
        return load_project(self.root)

    def test_raw_digest_and_unset_identity_without_files(self):
        self.config["repository"] = None
        config, digest = self.load()
        self.assertIsNone(config["repository"])
        self.assertEqual(digest, hashlib.sha256((self.root / "project.json").read_bytes()).hexdigest())
        self.assertFalse((self.root / config["paper_main"]).exists())

    def test_metadata_preserves_ci_identity(self):
        self.config["metadata"] = {"vikcim": {"expected": "Old", "value": "New"}}
        config, _ = self.load()
        self.assertEqual(config, self.config)

    def test_source_cannot_be_proxy(self):
        self.config["paper_main"] = "paper-draft.tex"
        with self.assertRaisesRegex(ValueError, "distinct|proxies"):
            self.load()

    def test_traversal_and_symlinks_in_declared_paths(self):
        for path in ("../draft.tex", "/tmp/draft.tex", "paper/../draft.tex", "paper\\draft.tex", ".git/config"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.config["paper_main"] = path
                self.load()
        self.config["paper_main"] = "paper/draft.tex"
        (self.root / "paper").symlink_to("/tmp", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.load()

    def test_duplicate_json_keys_and_config_symlink(self):
        (self.root / "project.json").write_text('{"schema":1,"schema":1}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_project(self.root)
        (self.root / "other.json").symlink_to("project.json")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            load_project(self.root, "other.json")

    def test_dependency_errors(self):
        for deps in (["absent"], ["presentation", "presentation"], ["paper"], ["code"]):
            self.config["components"]["paper"]["depends_on"] = deps
            with self.subTest(deps=deps), self.assertRaises(ValueError):
                self.load()
        self.config["components"]["paper"]["depends_on"] = ["presentation"]
        self.config["components"]["presentation"]["depends_on"] = ["paper"]
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            self.load()

    def test_enabled_empty_and_placeholder_checks_fail(self):
        self.config["components"]["code"]["enabled"] = True
        with self.assertRaisesRegex(ValueError, "nonempty"):
            self.load()
        self.config["components"]["code"]["enabled"] = False
        self.config["components"]["paper"]["profiles"]["ordinary"][0]["argv"] = ["true"]
        with self.assertRaisesRegex(ValueError, "Placeholder"):
            self.load()

    def test_proof_requires_structured_result(self):
        step = self.config["components"]["paper"]["profiles"]["ordinary"][0]
        step["kind"] = "proof"
        with self.assertRaisesRegex(ValueError, "result_file"):
            self.load()

    def test_unknown_fields_and_bad_shapes(self):
        for mutation in (lambda c: c.update(unknown=1),
                         lambda c: c.update(schema=True),
                         lambda c: c["components"].update(unknown={}),
                         lambda c: c["components"]["paper"].update(paths=[{}]),
                         lambda c: c["metadata"].update(secret={"expected":"", "value":""})):
            candidate = copy.deepcopy(self.config)
            mutation(candidate)
            with self.assertRaises(ValueError):
                validate_project(candidate, self.root)


if __name__ == "__main__":
    unittest.main()
