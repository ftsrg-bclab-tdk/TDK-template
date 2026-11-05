"""Failures that package structure alone cannot reveal."""
import unittest

from check_render import REQUIRED_FONTS, check_fonts, check_pdf_info, check_qr, check_text


class RenderFailures(unittest.TestCase):
    def font_report(self):
        return "name type encoding emb sub uni object ID\n----\n" + "\n".join(
            f"BAAAAA+{name} TrueType WinAnsi yes yes yes 12 0" for name in sorted(REQUIRED_FONTS))

    def test_font_substitution(self):
        with self.assertRaisesRegex(ValueError, "Substituted PDF font"):
            check_fonts(self.font_report().replace("Montserrat-Light", "LiberationSans"))

    def test_missing_weight(self):
        with self.assertRaisesRegex(ValueError, "Missing rendered font weights"):
            check_fonts(self.font_report().replace("Montserrat-Light", "Montserrat-Regular"))

    def test_nonembedded_pdf_font(self):
        with self.assertRaisesRegex(ValueError, "PDF font is not embedded"):
            check_fonts(self.font_report().replace("yes yes yes", "no yes yes", 1))

    def test_missing_text_with_legitimate_caps_and_wrapping(self):
        slide = b'<a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:r><a:t>Advisor(s): Ada Lovelace</a:t></a:r></a:p>'
        # The paragraph must sit beneath a slide root, as it does in the package.
        slide = b'<slide>' + slide + b'</slide>'
        check_text(slide, "ADVISOR(S): ADA\nLOVELACE", 1)
        with self.assertRaisesRegex(ValueError, "Missing rendered text"):
            check_text(slide, "ADVISOR(S): ADA", 1)

    def test_wrong_qr_destination(self):
        with self.assertRaisesRegex(ValueError, "Wrong or missing project QR"):
            check_qr("https://example.org/wrong-project", 11)

    def test_canvas_rounding_and_missing_pages(self):
        report = "Pages: 14\nPage size: 960.009 x 540 pts\n"
        check_pdf_info(report)
        with self.assertRaisesRegex(ValueError, "fourteen rendered slides"):
            check_pdf_info(report.replace("14", "13"))
        with self.assertRaisesRegex(ValueError, "Wrong rendered canvas"):
            check_pdf_info(report.replace("960.009", "720"))


if __name__ == "__main__":
    unittest.main()
