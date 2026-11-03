"""The default guide must supply the review sheet to the published skim view."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("skim", Path(__file__).with_name("skim.py"))
skim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(skim)


class TestReviewSheet(unittest.TestCase):
    def test_default_guide_has_every_scored_criterion(self):
        root = Path(__file__).resolve().parents[2]
        notes = []
        criteria, _ = skim.load_criteria(root / skim.GUIDE, None, notes)
        self.assertEqual([c["id"] for c in criteria], ["A", "B/1", "B/2", "C", "D/1", "D/2", "E"])
        self.assertTrue(all(c["top"] for c in criteria))
        self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
