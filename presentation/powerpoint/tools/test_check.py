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

    def test_lost_title_capitalization(self):
        self.damaged("ppt/slideLayouts/slideLayout1.xml", b' cap="all"', b'', "automatic capitalization")

    def test_overlapping_cover_title(self):
        from xml.etree import ElementTree as ET
        from check import NS
        part = "ppt/slideLayouts/slideLayout1.xml"
        with zipfile.ZipFile(ROOT / "templates/ftsrg-current.pptx") as z:
            layout = ET.fromstring(z.read(part))
        subtitle = next(s for s in layout.findall(".//p:sp", NS)
                        if s.find(".//p:ph[@type='subTitle']", NS) is not None)
        y = subtitle.find("p:spPr/a:xfrm/a:off", NS).get("y")
        self.damaged(part, f'y="{y}"'.encode(), b'y="0"', "overlaps subtitle")

    def test_stale_chart_cache(self):
        self.damaged("ppt/charts/chart1.xml", b'<c:v>12</c:v>', b'<c:v>99</c:v>', "values disagree")

    def test_external_workbook(self):
        self.damaged("ppt/charts/_rels/chart1.xml.rels", b'Target="../embeddings/chart-data.xlsx"', b'Target="https://example.org/data.xlsx" TargetMode="External"', "Unexpected external")

    def test_disabled_font_embedding(self):
        self.damaged("ppt/presentation.xml", b'embedTrueTypeFonts="1"', b'embedTrueTypeFonts="0"', "Font embedding must be enabled")

    def test_wrong_embedded_font_style(self):
        self.damaged("ppt/presentation.xml", b'<p:boldItalic ', b'<p:missingStyle ', "Missing embedded font style")

    def test_corrupt_embedded_font_payload(self):
        # Last bytes are inside the full TTF, beyond the EOT names and header.
        part = "ppt/fonts/Montserrat-Light.fntdata"
        with zipfile.ZipFile(ROOT / "templates/ftsrg-current.pptx") as z:
            data = z.read(part)
        self.damaged(part, data, data[:-1] + bytes([data[-1] ^ 1]), "payload differs")

    def test_warm_overlay_leaking_onto_cover(self):
        self.damaged("ppt/slideMasters/slideMaster2.xml", b'val="101010"', b'val="806459"', "original graph overlay changed")

    def test_cold_content_background(self):
        self.damaged("ppt/theme/theme1.xml", b'val="F4EFE7"', b'val="E6E6E6"', "Content background")

    def test_advisor_field_removed(self):
        self.damaged("ppt/slides/slide13.xml", b'name="Advisor(s)"', b'name="Unused"', "Missing editable advisor")

    def test_advisor_row_overlaps_event(self):
        from xml.etree import ElementTree as ET
        from check import NS
        part = "ppt/slideLayouts/slideLayout14.xml"
        with zipfile.ZipFile(ROOT / "templates/ftsrg-current.pptx") as z:
            layout = ET.fromstring(z.read(part))
        positions = {s.find("p:nvSpPr/p:cNvPr", NS).get("name"): s.find("p:spPr/a:xfrm/a:off", NS).get("y")
                     for s in layout.findall(".//p:sp", NS)}
        self.damaged(part, f'y="{positions["Event and date"]}"'.encode(),
                     f'y="{positions["Advisor(s)"]}"'.encode(), "Overlapping advisor row")


if __name__ == "__main__":
    unittest.main()
