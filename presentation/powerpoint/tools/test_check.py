"""Regression cases for editable-template failures, not screenshot similarity."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from check import ROOT, inspect


class BrokenTemplates(unittest.TestCase):
    def damaged(self, part, old, new, expected):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "broken.pptx"
            with zipfile.ZipFile(ROOT / "templates/ftsrg-current.pptx") as source, zipfile.ZipFile(path, "w") as out:
                for n in source.namelist():
                    data = source.read(n)
                    if n == part:
                        self.assertIn(old, data)
                        data = data.replace(old, new, 1)
                    out.writestr(n, data)
            with self.assertRaisesRegex(ValueError, expected):
                inspect(path)

    def test_invisible_table_namespace(self):
        self.damaged("ppt/slides/slide8.xml", b'drawingml/2006/table', b'drawingml/2006/main/table', "invalid graphicData")

    def test_lost_title_semantics(self):
        self.damaged("ppt/slides/slide3.xml", b'type="title"', b'type="body"', "Title missing")

    def test_inherited_hanging_indent(self):
        self.damaged("ppt/slideLayouts/slideLayout4.xml", b' marL="0" indent="0"', b'', "inherits a hanging indent")

    def test_stale_chart_cache(self):
        self.damaged("ppt/charts/chart1.xml", b'<c:v>12</c:v>', b'<c:v>99</c:v>', "values disagree")

    def test_external_workbook(self):
        self.damaged("ppt/charts/_rels/chart1.xml.rels", b'Target="../embeddings/chart-data.xlsx"', b'Target="https://example.org/data.xlsx" TargetMode="External"', "Unexpected external")


if __name__ == "__main__":
    unittest.main()
