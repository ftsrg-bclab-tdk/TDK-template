#!/usr/bin/env python3
"""Make static desktop fonts from the starter's OFL variable fonts.

Maintainer-only: uv run --with fonttools==4.67.0 python tools/prepare_fonts.py
Students can install the bundled static fonts without running this script.
"""
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "assets/fonts"
OUTPUT = ROOT / "fonts"


def main():
    OUTPUT.mkdir(exist_ok=True)
    for source, family, styles in [
        ("Montserrat.ttf", "Montserrat", [("Regular", 400), ("Bold", 700)]),
        ("Montserrat-Italic.ttf", "Montserrat", [("Italic", 400), ("Bold Italic", 700)]),
        ("JetBrainsMono.ttf", "JetBrains Mono", [("Regular", 400)]),
    ]:
        for style, weight in styles:
            font = TTFont(SOURCE / source, recalcTimestamp=False)
            if font["OS/2"].fsType != 0:
                raise ValueError(f"Unexpected embedding restriction in {source}")
            instantiateVariableFont(font, {"wght": weight}, inplace=True, updateFontNames=True)
            postscript = family.replace(" ", "") + "-" + style.replace(" ", "")
            for ident, value in [(1, family), (2, style), (4, family + " " + style),
                                 (6, postscript), (16, family), (17, style)]:
                font["name"].setName(value, ident, 3, 1, 0x409)
                font["name"].setName(value, ident, 1, 0, 0)
            font.save(OUTPUT / (postscript + ".ttf"))
    for filename in ["OFL-Montserrat.txt", "OFL-JetBrainsMono.txt"]:
        (OUTPUT / filename).write_bytes((SOURCE / filename).read_bytes())


if __name__ == "__main__":
    main()
