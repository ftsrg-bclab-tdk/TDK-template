#!/usr/bin/env python3
"""Check the distributed templates and their editable OOXML contracts.

Does not claim complete ECMA schema, rendering, or native PowerPoint validation.
Uses only Python's standard library, including in CI.
"""
import hashlib
import io
import posixpath
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from font_embedding import FONTS

ROOT = Path(__file__).resolve().parents[1]
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relationships(z, part):
    name = str(Path(part).parent / "_rels" / (Path(part).name + ".rels"))
    return {r.get("Id"): (r.get("Type").rsplit("/", 1)[-1],
                          posixpath.normpath(posixpath.join(posixpath.dirname(part), r.get("Target"))))
            for r in ET.fromstring(z.read(name))}


def inspect_fonts(z, presentation, rels, content):
    require(presentation.get("embedTrueTypeFonts") == "1" and presentation.get("saveSubsetFonts") == "0",
            "Font embedding must be enabled for all characters")
    entries = presentation.findall("p:embeddedFontLst/p:embeddedFont", NS)
    families = [entry.find("p:font", NS).get("typeface") for entry in entries]
    require(len(families) == len(set(families)) and set(families) == set(FONTS), "Missing or duplicate embedded font family")
    types = {e.get("PartName"): e.get("ContentType") for e in content}
    embedded_parts = set()
    for entry, family in zip(entries, families):
        faces = {child.tag.rsplit("}", 1)[-1]: child for child in entry if child.tag != "{" + NS["p"] + "}font"}
        require(set(faces) == set(FONTS[family]), f"Missing embedded font style: {family}")
        for style, filename in FONTS[family].items():
            typ, part = rels[faces[style].get("{" + NS["r"] + "}id")]
            require(typ == "font" and types.get("/" + part) == "application/x-fontdata", "Wrong embedded font part type")
            embedded_parts.add(part)
            data = z.read(part)
            source = (ROOT / "fonts" / filename).read_bytes()
            require(len(data) >= 100, "Truncated embedded font")
            size, payload_size, version, flags = struct.unpack_from("<4I", data)
            require((size, payload_size, version, flags) == (len(data), len(source), 0x00020001, 0),
                    "Invalid embedded font header or subset")
            require(struct.unpack_from("<HH", data, 32) == (0, 0x504C), "Invalid embedded font permissions or signature")
            cursor = 80
            strings = []
            for _ in range(5):
                require(cursor + 4 <= len(data) - payload_size, "Truncated embedded font names")
                padding, length = struct.unpack_from("<HH", data, cursor)
                require(padding == 0 and length % 2 == 0, "Invalid embedded font name header")
                cursor += 4
                strings.append(data[cursor:cursor + length].decode("utf-16le"))
                cursor += length
            expected_style = {"regular": "Regular", "bold": "Bold", "italic": "Italic", "boldItalic": "Bold Italic"}[style]
            require(strings[0] == family and strings[1] == expected_style and strings[4] == "", "Embedded font name mismatch")
            require(cursor == len(data) - payload_size and data[cursor:] == source,
                    "Embedded font payload differs from the complete bundled font")
    require(embedded_parts == {p for t, p in rels.values() if t == "font"}, "Unregistered embedded font part")
    for name in z.namelist():
        if name.startswith("ppt/") and name.endswith(".xml"):
            root = ET.fromstring(z.read(name))
            for font in root.findall(".//a:latin", NS) + root.findall(".//a:buFont", NS):
                family = font.get("typeface", "")
                require(not family or family.startswith("+") or family in FONTS, f"Unbundled text font: {family}")


def inspect(path):
    with zipfile.ZipFile(path) as z:
        require(z.testzip() is None, "Corrupt ZIP member")
        names = z.namelist()
        require(len(names) == len(set(names)), "Duplicate package member")
        require(not any("vba" in n.lower() or "activeX" in n for n in names), "Unexpected active content")
        for n in names:
            if n.endswith(".xml") or n.endswith(".rels"):
                ET.fromstring(z.read(n))
            if n.endswith(".rels"):
                base = "" if n == "_rels/.rels" else n.split("/_rels/")[0]
                for rel in ET.fromstring(z.read(n)):
                    require(rel.get("TargetMode") != "External", f"Unexpected external link in {n}")
                    target = posixpath.normpath(posixpath.join(base, rel.get("Target")))
                    require(target in names, f"Missing relationship target: {target}")
        content = ET.fromstring(z.read("[Content_Types].xml"))
        main_type = next(e.get("ContentType") for e in content if e.get("PartName") == "/ppt/presentation.xml")
        expected = "template" if path.suffix == ".potx" else "presentation"
        require(main_type.endswith(f".{expected}.main+xml"), "Wrong PPTX/POTX content type")
        p = ET.fromstring(z.read("ppt/presentation.xml"))
        require(p.find("p:sldSz", NS).attrib == {"cx": "12192000", "cy": "6858000", "type": "screen16x9"}, "Wrong canvas")
        prs = relationships(z, "ppt/presentation.xml")
        inspect_fonts(z, p, prs, content)
        slides = [prs[e.get("{" + NS["r"] + "}id")][1] for e in p.findall("p:sldIdLst/p:sldId", NS)]
        require(len(slides) == 14, "Missing example slide")
        require(len(p.findall("p:sldMasterIdLst/p:sldMasterId", NS)) == 3, "Expected three shared masters")
        theme = ET.fromstring(z.read("ppt/theme/theme1.xml"))
        require(theme.find(".//a:clrScheme/a:lt2/a:srgbClr", NS).get("val") == "F4EFE7",
                "Content background must retain warm ivory")
        content_master = ET.fromstring(z.read("ppt/slideMasters/slideMaster1.xml"))
        require(content_master.find("p:cSld/p:bg/p:bgPr/a:solidFill/a:schemeClr", NS).get("val") == "lt2",
                "Content master must use the warm background theme color")
        for number, color, opacity in ((2, "101010", "42000"), (3, "24122A", "50000")):
            master = ET.fromstring(z.read(f"ppt/slideMasters/slideMaster{number}.xml"))
            overlay = [s for s in master.findall(".//p:sp", NS)
                       if s.find("p:nvSpPr/p:cNvPr", NS).get("name") == "Artwork contrast overlay"]
            require(len(overlay) == 1, "Missing original graph overlay")
            fill = overlay[0].find("p:spPr/a:solidFill/a:srgbClr", NS)
            require(fill is not None and fill.get("val") == color and fill.find("a:alpha", NS).get("val") == opacity,
                    "Only content backgrounds may be warmed; original graph overlay changed")
        layout_names = set()
        for i, part in enumerate(slides, 1):
            slide = ET.fromstring(z.read(part))
            require(slide.get("show", "1") == "1", f"Hidden example slide {i}")
            rs = relationships(z, part)
            layout_path = next(target for typ, target in rs.values() if typ == "slideLayout")
            layout = ET.fromstring(z.read(layout_path))
            layout_names.add(layout.find("p:cSld", NS).get("name"))
            phs = layout.findall(".//p:ph", NS)
            layout_phs = {(ph.get("type", "obj"), ph.get("idx", "0")) for ph in phs}
            require(len(layout_phs) == len(phs), f"Duplicate layout placeholder on {i}")
            for style in layout.findall(".//a:lstStyle/*", NS):
                if style.find("a:buNone", NS) is not None:
                    require(style.get("marL") == "0" and style.get("indent") == "0",
                            f"Non-bullet layout text inherits a hanging indent on {i}")
            layout_titles = [s for s in layout.findall(".//p:sp", NS)
                             if any(ph.get("type") in ("title", "ctrTitle") for ph in s.findall(".//p:ph", NS))]
            for title in layout_titles:
                require(title.find("p:txBody/a:lstStyle/a:lvl1pPr/a:defRPr", NS).get("cap") == "all",
                        f"Title loses automatic capitalization on {i}")
            subtitles = [s for s in layout.findall(".//p:sp", NS)
                         if s.find(".//p:ph[@type='subTitle']", NS) is not None]
            if subtitles:
                title_pos = layout_titles[0].find("p:spPr/a:xfrm", NS)
                subtitle_pos = subtitles[0].find("p:spPr/a:xfrm", NS)
                bottom = int(title_pos.find("a:off", NS).get("y")) + int(title_pos.find("a:ext", NS).get("cy"))
                require(bottom <= int(subtitle_pos.find("a:off", NS).get("y")),
                        f"Cover title overlaps subtitle on {i}")
            shapes = slide.find("p:cSld/p:spTree", NS)
            if i in (1, 13, 14):
                advisor = [s for s in shapes.findall("p:sp", NS)
                           if s.find("p:nvSpPr/p:cNvPr", NS).get("name") == "Advisor(s)"]
                require(len(advisor) == 1 and advisor[0].find(".//p:ph[@type='body'][@idx='7']", NS) is not None
                        and bool("".join(advisor[0].itertext()).strip()), f"Missing editable advisor field on cover {i}")
                rows = {s.find("p:nvSpPr/p:cNvPr", NS).get("name"): s.find("p:spPr/a:xfrm", NS)
                        for s in layout.findall(".//p:sp", NS)}
                for before, after in (("Authors", "Advisor(s)"), ("Advisor(s)", "Event and date")):
                    require(before in rows and after in rows, f"Missing cover row on {i}")
                    bottom = int(rows[before].find("a:off", NS).get("y")) + int(rows[before].find("a:ext", NS).get("cy"))
                    require(bottom <= int(rows[after].find("a:off", NS).get("y")), f"Overlapping advisor row on cover {i}")
            titles = [s for s in shapes if any(ph.get("type") in ("title", "ctrTitle") for ph in s.findall(".//p:ph", NS))]
            require(len(titles) == 1 and shapes[2] is titles[0], f"Title missing or not first in reading order on {i}")
            ids = [s.get("id") for s in slide.findall(".//p:cNvPr", NS)]
            require(len(ids) == len(set(ids)), f"Duplicate shape id on {i}")
            for shape in shapes:
                for ph in shape.findall(".//p:ph", NS):
                    require((ph.get("type", "obj"), ph.get("idx", "0")) in layout_phs, f"Unmatched placeholder on {i}")
                if shape.tag == "{" + NS["p"] + "}sp" and shape.find(".//p:ph", NS) is not None:
                    require(shape.find("p:spPr/a:xfrm", NS) is None, f"Text geometry overrides layout on {i}")
                for pic in shape.findall("p:nvPicPr/p:cNvPr", NS):
                    require(bool(pic.get("descr")), f"Missing figure alt text on {i}")
                for edge in shape.findall(".//a:stCxn", NS) + shape.findall(".//a:endCxn", NS):
                    require(edge.get("id") in ids, f"Detached connector on {i}")
            notes_path = next(target for typ, target in rs.values() if typ == "notesSlide")
            notes = ET.fromstring(z.read(notes_path))
            require(len("".join(notes.itertext())) > 150, f"Missing editing guidance on {i}")
            numbered = i not in (1, 2, 11, 13, 14)
            fields = slide.findall(".//a:fld[@type='slidenum']", NS)
            require(len(fields) == int(numbered), f"Incorrect automatic numbering on {i}")
        require(len(layout_names) == 14, "Examples must cover fourteen distinct layouts")
        table_slide = ET.fromstring(z.read(slides[7]))
        table_data = table_slide.find(".//a:graphicData[a:tbl]", NS)
        require(table_data is not None and table_data.get("uri") == "http://schemas.openxmlformats.org/drawingml/2006/table", "Table has an invalid graphicData type (can render invisible)")
        table = table_data.find("a:tbl", NS)
        require(table.find("a:tblPr", NS).get("firstRow") == "1", "Table must identify the header row")
        require(len(table.findall("a:tr", NS)) == 4 and all(len(r.findall("a:tc", NS)) == 3 for r in table.findall("a:tr", NS)), "Incomplete native table")
        chart = ET.fromstring(z.read("ppt/charts/chart1.xml"))
        require(chart.find("c:externalData", NS) is not None, "Chart needs an editable workbook")
        with zipfile.ZipFile(io.BytesIO(z.read("ppt/embeddings/chart-data.xlsx"))) as wb:
            sheet = ET.fromstring(wb.read("xl/worksheets/sheet1.xml"))
        cells = {c.get("r"): "".join(c.itertext()) for c in sheet.findall(".//s:c", NS)}
        cached = [v.text for v in chart.findall(".//c:val/c:numRef/c:numCache/c:pt/c:v", NS)]
        categories = [v.text for v in chart.findall(".//c:cat/c:strRef/c:strCache/c:pt/c:v", NS)]
        require(cached == [cells[f"B{i}"] for i in range(2, 5)], "Chart values disagree with its workbook")
        require(categories == [cells[f"A{i}"] for i in range(2, 5)], "Chart categories disagree with its workbook")
        require(chart.find(".//c:val/c:numRef/c:f", NS).text == "Data!$B$2:$B$4", "Chart formula points outside example data")
        require(chart.find(".//c:valAx/c:scaling/c:min", NS).get("val") == "0", "Bar chart must start at zero")
        theme = ET.fromstring(z.read("ppt/theme/theme1.xml"))
        for role, family in (("majorFont", "Montserrat Medium"), ("minorFont", "Montserrat")):
            require(theme.find(f".//a:fontScheme/a:{role}/a:latin", NS).get("typeface") == family, "Wrong theme fonts")


def main():
    for line in (ROOT / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ", 1)
        path = ROOT / name
        require(path.resolve().is_relative_to(ROOT.resolve()), "Manifest path escapes component")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, f"Changed distributed asset: {name}")
    for ext in ("pptx", "potx"):
        inspect(ROOT / f"templates/ftsrg-current.{ext}")
    # Build in isolation; never overwrite the distributed templates in CI.
    with tempfile.TemporaryDirectory(prefix="ftsrg-pptx-check-") as d:
        subprocess.run([sys.executable, str(ROOT / "tools/build.py"), "--output-dir", d], check=True, capture_output=True)
        for ext in ("pptx", "potx"):
            name = f"ftsrg-current.{ext}"
            require((Path(d) / name).read_bytes() == (ROOT / "templates" / name).read_bytes(), f"Stale generated template: {name}")
    legacy = ROOT / "legacy/ftsrg-montserrat-2025.pptx"
    require(hashlib.sha256(legacy.read_bytes()).hexdigest() == "4b162aaa6eb526f9617181ab1800499c6acf8cabe907a47c1a876218e3750cd9", "Legacy file must remain unchanged")
    print("PASS: hashes, embedded full fonts, relationships, layouts, placeholders, notes, native table/chart, workbook, connectors, numbering, and reproducible templates")


if __name__ == "__main__":
    main()
