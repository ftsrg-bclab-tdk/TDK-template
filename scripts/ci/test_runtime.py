import json
from pathlib import Path
import tempfile
import unittest

from runtime import prepare_npm, resolve_oci


class RuntimeTests(unittest.TestCase):
    def test_latest_image_resolved_once_and_invalid_digest_fails(self):
        calls = []
        def run(argv):
            calls.append(argv)
            return "sha256:" + "a" * 64
        value = resolve_oci("danteev/texlive:latest", run)
        self.assertEqual(len(calls), 1)
        self.assertEqual(value["resolved"], "danteev/texlive@sha256:" + "a" * 64)
        with self.assertRaises(ValueError):
            resolve_oci("danteev/texlive:2024", run)
        with self.assertRaises(ValueError):
            resolve_oci("danteev/texlive:latest", lambda argv: "")

    def test_latest_npm_uses_fresh_lock_and_preserves_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "presentation"
            source.mkdir()
            (source / "package.json").write_text(json.dumps({"devDependencies":{"some-package":"1.0.0"}}))
            (source / "package-lock.json").write_text("old source lock")
            calls = []
            def run(argv, cwd):
                calls.append(argv)
                self.assertEqual(json.loads((cwd/"package.json").read_text())["devDependencies"]["some-package"],"latest")
                if "install" in argv:
                    self.assertFalse((cwd/"package-lock.json").exists())
                    (cwd/"package-lock.json").write_text(json.dumps({"packages":{"node_modules/some-package":{"version":"9.0.0"}}}))
                return ""
            value = prepare_npm(root, "presentation", ".project/runtime/presentation", run)
            self.assertEqual([a[1] for a in calls],["install","ci"])
            self.assertEqual(value["versions"]["node_modules/some-package"],"9.0.0")
            self.assertEqual((source/"package-lock.json").read_text(),"old source lock")
            with self.assertRaisesRegex(ValueError,"fresh"):
                prepare_npm(root,"presentation",".project/runtime/presentation",run)


if __name__ == "__main__":
    unittest.main()
