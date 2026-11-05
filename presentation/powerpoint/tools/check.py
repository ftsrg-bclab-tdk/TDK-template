#!/usr/bin/env python3
"""Check the distributed templates and their editable OOXML contracts.

Does not claim complete ECMA schema, rendering, or native PowerPoint validation.
Uses only Python's standard library, including in CI.
"""
import hashlib
import io
import posixpath
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

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
        slides = [prs[e.get("{" + NS["r"] + "}id")][1] for e in p.findall("p:sldIdLst/p:sldId", NS)]
        require(len(slides) == 12, "Missing example slide")
        require(len(p.findall("p:sldMasterIdLst/p:sldMasterId", NS)) == 3, "Expected three shared masters")
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
            shapes = slide.find("p:cSld/p:spTree", NS)
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
            numbered = i not in (1, 2, 11)
            fields = slide.findall(".//a:fld[@type='slidenum']", NS)
            require(len(fields) == int(numbered), f"Incorrect automatic numbering on {i}")
        require(len(layout_names) == 12, "Examples must cover twelve distinct layouts")
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
        require(all(e.get("typeface") == "Montserrat" for e in theme.findall(".//a:fontScheme/*/a:latin", NS)), "Wrong theme fonts")


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
    print("PASS: hashes, relationships, layouts, placeholders, notes, native table/chart, workbook, connectors, numbering, and reproducible templates")


if __name__ == "__main__":
    main()
