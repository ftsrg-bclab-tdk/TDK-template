#!/usr/bin/env python3
"""Render distributed templates with isolated fallback fonts and retain evidence.

Requires LibreOffice, Fontconfig, Liberation fonts, Poppler and zbar-tools.
Checks rendering with LibreOffice, not native PowerPoint or visual similarity.
Each invocation uses fresh output, font caches and an application profile.
"""
import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from build import PROJECT_URL
from check import NS, ROOT, require

REQUIRED_FONTS = {"Montserrat-Regular", "Montserrat-Bold", "Montserrat-Light",
                  "Montserrat-Medium", "Montserrat-SemiBold", "JetBrainsMono-Regular"}
ALLOWED_FONTS = REQUIRED_FONTS | {"Montserrat-Italic", "Montserrat-BoldItalic"}
QR_SLIDES = (1, 11, 13, 14)


def check_fonts(report):
    fonts = set()
    for line in report.splitlines()[2:]:
        if not line.strip():
            continue
        name = re.sub(r"^[A-Z]{6}\+", "", line.split()[0])
        flags = re.search(r"\s(yes|no)\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$", line)
        require(flags is not None and flags[1] == "yes", f"PDF font is not embedded: {name}")
        require(name in ALLOWED_FONTS, f"Substituted PDF font: {name}")
        fonts.add(name)
    require(REQUIRED_FONTS <= fonts, f"Missing rendered font weights: {sorted(REQUIRED_FONTS - fonts)}")
    return sorted(fonts)


def normalized(text):
    return "".join(unicodedata.normalize("NFKC", text).casefold().split())


def check_text(slide_xml, rendered_text, page):
    """Allow line wrapping and native All Caps; require every native paragraph."""
    actual = normalized(rendered_text)
    require(bool(actual), f"Blank rendered slide {page}")
    for paragraph in ET.fromstring(slide_xml).findall(".//a:p", NS):
        expected = "".join(t.text or "" for t in paragraph.findall(".//a:t", NS))
        require(normalized(expected) in actual, f"Missing rendered text on slide {page}: {expected!r}")


def check_qr(decoded, page):
    require(decoded.splitlines() == [PROJECT_URL], f"Wrong or missing project QR on slide {page}: {decoded!r}")


def check_pdf_info(info):
    require(re.search(r"^Pages:\s+14\s*$", info, re.M) is not None, "Expected fourteen rendered slides")
    size = re.search(r"^Page size:\s+([\d.]+)\s+x\s+([\d.]+)\s+pts", info, re.M)
    # LibreOffice rounds EMUs through its internal units (960.009 pt is normal).
    require(size is not None and abs(float(size[1]) - 960) < .05 and abs(float(size[2]) - 540) < .05,
            "Wrong rendered canvas")


def render(fmt, output_root):
    output_root.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix=fmt + "-", dir=output_root)).resolve()
    source = ROOT / f"templates/ftsrg-current.{fmt}"
    report = {"format": fmt, "status": "failed", "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "claim_boundary": "LibreOffice rendering only; no native PowerPoint or complete accessibility validation."}
    env = {**os.environ, "LC_ALL": "C"}

    def run(*args, timeout=60):
        with (output / "commands.log").open("a") as log:
            log.write("$ " + shlex.join(str(a) for a in args) + "\n")
            log.flush()
            result = subprocess.run([str(a) for a in args], env=env, capture_output=True, text=True, timeout=timeout)
            log.write(result.stdout + result.stderr + f"\nExit: {result.returncode}\n")
        require(result.returncode == 0, f"Command failed ({result.returncode}): {args[0]}; see {output / 'commands.log'}")
        return result.stdout

    try:
        report["libreoffice"] = run("libreoffice", "--version").strip()
        run("pdftoppm", "-v")
        run("zbarimg", "--version")
        fallback = Path(run("fc-match", "-f", "%{file}\n", "Liberation Sans").strip()).parent
        with tempfile.TemporaryDirectory(prefix="ftsrg-render-profile-") as private:
            private = Path(private)
            config = ET.Element("fontconfig")
            ET.SubElement(config, "dir").text = str(fallback)
            ET.SubElement(config, "cachedir").text = str(private / "font-cache")
            config_path = private / "fonts.conf"
            config_path.write_bytes(ET.tostring(config, encoding="utf-8", xml_declaration=True))
            env["FONTCONFIG_FILE"] = str(config_path)
            available = run("fc-list", "-f", "%{family}\n")
            (output / "available-fonts.txt").write_text(available)
            families = set(available.splitlines())
            require("Liberation Sans" in families and all(f.startswith("Liberation ") for f in families),
                    "Install Liberation fonts; isolated rendering must have only Liberation fallback families")
            run("libreoffice", "-env:UserInstallation=" + (private / "profile").as_uri(),
                "--headless", "--convert-to", "pdf:impress_pdf_Export", "--outdir", output, source, timeout=180)
            pdf = output / "ftsrg-current.pdf"
            require(pdf.is_file(), "LibreOffice produced no PDF")
            info = run("pdfinfo", pdf)
            (output / "pdfinfo.txt").write_text(info)
            check_pdf_info(info)
            # Preserve previews even when a later font, text or QR check fails.
            run("pdftoppm", "-scale-to", "1280", "-png", pdf, output / "slide", timeout=180)
            require(len(list(output.glob("slide-*.png"))) == 14, "Missing slide previews")
            fonts = run("pdffonts", pdf)
            (output / "pdf-fonts.txt").write_text(fonts)
            report["fonts"] = check_fonts(fonts)
            with zipfile.ZipFile(source) as z:
                for page in range(1, 15):
                    text = run("pdftotext", "-f", page, "-l", page, pdf, "-")
                    (output / f"slide-{page:02}.txt").write_text(text)
                    check_text(z.read(f"ppt/slides/slide{page}.xml"), text, page)
            report["qr_destinations"] = {}
            for page in QR_SLIDES:
                decoded = run("zbarimg", "--quiet", "--raw", output / f"slide-{page:02}.png").strip()
                check_qr(decoded, page)
                report["qr_destinations"][str(page)] = decoded
            report["slide_count"] = 14
            report["status"] = "passed"
            print(f"PASS {fmt.upper()}: fourteen slides, embedded fonts, native text and four project QRs; evidence: {output}")
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("pptx", "potx"), required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT.parent / "dist/powerpoint/ci")
    args = parser.parse_args()
    render(args.format, args.output_dir)
