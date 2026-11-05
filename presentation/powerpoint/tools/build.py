#!/usr/bin/env python3
"""Build native PowerPoint examples and layouts; Python standard library only.

The checked-in PPTX/POTX are student deliverables, not renders of Markdown.
All dimensions below are CSS pixels on the source theme's 1280 x 720 canvas.
"""
import argparse
import copy
import io
import json
import struct
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from font_embedding import FONTS, eot

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT.parent / "assets"
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PML = "application/vnd.openxmlformats-officedocument.presentationml."
COLORS = {"dk1": "1A1A1A", "lt1": "FFFFFF", "dk2": "555555", "lt2": "E6E6E6",
          "accent1": "8A2432", "accent2": "29ABE2", "accent3": "F7931E",
          "accent4": "8CC63F", "accent5": "201161", "accent6": "9A9A9A",
          "hlink": "8A2432", "folHlink": "201161"}
CMAP = dict(bg1="lt1", tx1="dk1", bg2="lt2", tx2="dk2", **{k: k for k in COLORS if k.startswith("accent") or k in ("hlink", "folHlink")})


def node(tag, **attrs):
    pre, local = tag.split(":")
    return ET.Element(f"{{{NS[pre]}}}{local}", {k: str(v) for k, v in attrs.items()})


def sub(parent, tag, **attrs):
    child = node(tag, **attrs)
    parent.append(child)
    return child


def xml(element):
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def emu(value):
    return str(round(value * 9525))


def solid(parent, color, alpha=None):
    fill = sub(parent, "a:solidFill")
    child = sub(fill, "a:schemeClr" if color in COLORS or color in CMAP else "a:srgbClr", val=color)
    if alpha is not None:
        sub(child, "a:alpha", val=round(alpha * 100000))


def xfrm(parent, box, tag="a:xfrm"):
    x, y, w, h = box
    t = sub(parent, tag)
    sub(t, "a:off", x=emu(x), y=emu(y))
    sub(t, "a:ext", cx=emu(w), cy=emu(h))


def tree(parent):
    t = sub(parent, "p:spTree")
    nv = sub(t, "p:nvGrpSpPr")
    sub(nv, "p:cNvPr", id=1, name="")
    sub(nv, "p:cNvGrpSpPr")
    sub(nv, "p:nvPr")
    x = sub(sub(t, "p:grpSpPr"), "a:xfrm")
    for tag, attrs in [("off", {"x": 0, "y": 0}), ("ext", {"cx": 0, "cy": 0}),
                       ("chOff", {"x": 0, "y": 0}), ("chExt", {"cx": 0, "cy": 0})]:
        sub(x, "a:" + tag, **attrs)
    return t


def decorative(cnv):
    ext = sub(sub(cnv, "a:extLst"), "a:ext", uri="{C183D7F6-B498-43B3-948B-1728B52AA6E4}")
    ET.SubElement(ext, "{http://schemas.microsoft.com/office/drawing/2017/decorative}decorative", val="1")


def text_body(parent, texts, style=None, inherited=False, tag="p:txBody"):
    b = sub(parent, tag)
    attrs = {} if inherited else dict(wrap="square", lIns=0, rIns=0, tIns=0, bIns=0, anchor=(style or {}).get("anchor", "t"))
    bp = sub(b, "a:bodyPr", **attrs)
    if not inherited:
        sub(bp, "a:noAutofit")
    ls = sub(b, "a:lstStyle")
    if style:
        for level in range(3):
            paragraph_style(sub(ls, f"a:lvl{level + 1}pPr"), style, level)
    for i, text in enumerate(texts.split("\n")):
        p = sub(b, "a:p")
        sub(p, "a:pPr", lvl=0)
        run = sub(p, "a:r")
        sub(run, "a:rPr", lang="en-US", dirty=0)
        sub(run, "a:t").text = text
        sub(p, "a:endParaRPr", lang="en-US")
    return b


def paragraph_style(pp, style, level=0):
    pp.set("algn", style.get("align", "l"))
    if style.get("bullets"):
        pp.set("marL", emu(28 + level * 30))
        pp.set("indent", emu(-22))
    else:
        # buNone alone does not clear the master body's hanging indent.
        pp.set("marL", "0")
        pp.set("indent", "0")
    sp = sub(pp, "a:lnSpc")
    # Fixed leading matches CSS line-height; percentage leading depends on the
    # application's font metrics and made the first revision much too loose.
    sub(sp, "a:spcPts", val=round(style.get("leading", style.get("size", 23) * 1.4) * 75))
    sub(sub(pp, "a:spcAft"), "a:spcPts", val=style.get("after", 0))
    if style.get("bullets"):
        solid_dummy = sub(pp, "a:buClr")
        sub(solid_dummy, "a:schemeClr", val="accent1")
        sub(pp, "a:buSzPct", val=70000)
        # Montserrat lacks U+25AA; the bundled mono font supplies the square.
        sub(pp, "a:buFont", typeface="JetBrains Mono")
        sub(pp, "a:buChar", char="▪" if level == 0 else "–")
    else:
        sub(pp, "a:buNone")
    rp = sub(pp, "a:defRPr", sz=round((style.get("size", 28) - level * 2) * 75),
             b=int(style.get("bold", False)), kern=1200)
    if style.get("tracking"):
        rp.set("spc", str(round(style["tracking"] * 75)))
    if style.get("caps"):
        rp.set("cap", "all")
    solid(rp, style.get("color", "tx1"))
    sub(rp, "a:latin", typeface=style.get("font", "+mn-lt"))


def shape(t, name, box=None, text="", style=None, ph=None, fill=None, border=None, deco=False):
    s = sub(t, "p:sp")
    nv = sub(s, "p:nvSpPr")
    cnv = sub(nv, "p:cNvPr", id=len(t), name=name)
    if deco:
        decorative(cnv)
    locks = sub(nv, "p:cNvSpPr")
    if ph:
        sub(locks, "a:spLocks", noGrp=1)
    nvp = sub(nv, "p:nvPr")
    if ph:
        sub(nvp, "p:ph", type=ph[0], idx=ph[1])
    sp = sub(s, "p:spPr")
    if box:
        xfrm(sp, box)
        sub(sub(sp, "a:prstGeom", prst="rect"), "a:avLst")
        if fill:
            solid(sp, *fill) if isinstance(fill, tuple) else solid(sp, fill)
        else:
            sub(sp, "a:noFill")
        ln = sub(sp, "a:ln", w=emu(1 if border else 0))
        if border:
            solid(ln, *border) if isinstance(border, tuple) else solid(ln, border)
        else:
            sub(ln, "a:noFill")
    text_body(s, text, style, inherited=box is None)
    return s


class Package:
    def __init__(self):
        self.parts = {}
        self.types = {}

    def put(self, name, content, content_type=None):
        self.parts[name] = content if isinstance(content, bytes) else xml(content)
        if content_type:
            self.types[name] = content_type

    def rels(self, part, relationships):
        r = ET.Element("Relationships", xmlns=REL)
        for rid, typ, target in relationships:
            ET.SubElement(r, "Relationship", Id=rid, Type=typ if typ.startswith("http") else NS["r"] + "/" + typ, Target=target)
        name = str(Path(part).parent / "_rels" / (Path(part).name + ".rels")) if part else "_rels/.rels"
        self.put(name, r)

    def write(self, path):
        ct = ET.Element("Types", xmlns=CT)
        for ext, typ in {"rels": "application/vnd.openxmlformats-package.relationships+xml", "xml": "application/xml", "png": "image/png", "jpg": "image/jpeg", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}.items():
            ET.SubElement(ct, "Default", Extension=ext, ContentType=typ)
        for name, typ in sorted(self.types.items()):
            ET.SubElement(ct, "Override", PartName="/" + name, ContentType=typ)
        self.put("[Content_Types].xml", ct)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in sorted(self.parts.items()):
                info = zipfile.ZipInfo(name, (2026, 11, 5, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, data)


def picture(pkg, t, rels, source, box, name, description="", ph=None, deco=False):
    filename = source.name
    pkg.put("ppt/media/" + filename, source.read_bytes())
    rid = "rId" + str(len(rels) + 1)
    rels.append((rid, "image", "../media/" + filename))
    p = sub(t, "p:pic")
    nv = sub(p, "p:nvPicPr")
    cnv = sub(nv, "p:cNvPr", id=len(t), name=name, descr=description)
    if deco:
        decorative(cnv)
    sub(sub(nv, "p:cNvPicPr"), "a:picLocks", noChangeAspect=1)
    nvp = sub(nv, "p:nvPr")
    if ph:
        sub(nvp, "p:ph", type=ph[0], idx=ph[1])
    bf = sub(p, "p:blipFill")
    sub(bf, "a:blip", **{f"{{{NS['r']}}}embed": rid})
    sub(sub(bf, "a:stretch"), "a:fillRect")
    sp = sub(p, "p:spPr")
    xfrm(sp, box)
    sub(sub(sp, "a:prstGeom", prst="rect"), "a:avLst")


def png_box(path, x, y, height):
    width, native_height = struct.unpack(">II", path.read_bytes()[16:24])
    return x, y, height * width / native_height, height


def png_fit(path, box):
    width, height = struct.unpack(">II", path.read_bytes()[16:24])
    x, y, w, h = box
    scale = min(w / width, h / height)
    return x + (w - width * scale) / 2, y + (h - height * scale) / 2, width * scale, height * scale


def theme():
    t = node("a:theme", name="FTSRG current design")
    te = sub(t, "a:themeElements")
    cs = sub(te, "a:clrScheme", name="BME / FTSRG")
    for name, value in COLORS.items():
        sub(sub(cs, "a:" + name), "a:srgbClr", val=value)
    fs = sub(te, "a:fontScheme", name="Montserrat")
    for role in ("majorFont", "minorFont"):
        f = sub(fs, "a:" + role)
        sub(f, "a:latin", typeface="Montserrat Medium" if role == "majorFont" else "Montserrat")
        sub(f, "a:ea", typeface="")
        sub(f, "a:cs", typeface="")
    fmt = sub(te, "a:fmtScheme", name="FTSRG")
    fills = sub(fmt, "a:fillStyleLst")
    for _ in range(3):
        solid(fills, "phClr")
        # phClr is a scheme token outside the semantic map.
        fills[-1][0].tag = "{" + NS["a"] + "}schemeClr"
    lines = sub(fmt, "a:lnStyleLst")
    for width in (9525, 19050, 28575):
        line = sub(lines, "a:ln", w=width, cap="flat", cmpd="sng", algn="ctr")
        sub(sub(line, "a:solidFill"), "a:schemeClr", val="phClr")
        sub(line, "a:prstDash", val="solid")
        sub(line, "a:miter", lim=800000)
    effects = sub(fmt, "a:effectStyleLst")
    for _ in range(3):
        sub(sub(effects, "a:effectStyle"), "a:effectLst")
    bg = sub(fmt, "a:bgFillStyleLst")
    for _ in range(3):
        sub(sub(bg, "a:solidFill"), "a:schemeClr", val="phClr")
    sub(t, "a:objectDefaults")
    sub(t, "a:extraClrSchemeLst")
    return t


def background(cs, color):
    pr = sub(sub(cs, "p:bg"), "p:bgPr")
    solid(pr, color)
    sub(pr, "a:effectLst")


def make_master(pkg, number, name, layouts):
    m = node("p:sldMaster")
    cs = sub(m, "p:cSld", name=name)
    background(cs, "lt2" if number == 1 else "dk1")
    t = tree(cs)
    rels = [("rId1", "theme", "../theme/theme1.xml")]
    if number == 1:
        shape(t, "Header rule", (64, 27, 1152, 1.5), fill="8A8A8A", deco=True)
        shape(t, "Project label (edit on master)", (64, 14, 174, 20), "RESEARCH PROJECT",
              dict(size=13, leading=20, color="4A4A4A", font="Montserrat Medium", tracking=1.56), fill="lt2")
        shape(t, "Event and authors (edit on master)", (481.5, 14, 317, 20), "TDK CONFERENCE · STUDENT NAME",
              dict(size=13, leading=20, color="4A4A4A", font="Montserrat Medium", tracking=1.56, align="ctr"), fill="lt2")
        shape(t, "Header logo backing", (1113.2, 17, 102.8, 20), fill="lt2", deco=True)
        for file, x, y, h in [("ftsrg-grey.png", 1125.2, 17, 20), ("bme-wordmark-grey.png", 1176.25, 19.5, 15)]:
            p = ASSETS / "logos" / file
            picture(pkg, t, rels, p, png_box(p, x, y, h), file, deco=True)
        s = shape(t, "Automatic slide number", (1232, 15, 34, 20), "1", dict(size=13, leading=20, color="7A7A7A", font="Montserrat Medium", tracking=1.04), ph=("sldNum", 90))
        p = s.find("p:txBody/a:p", NS)
        p.remove(p.find("a:r", NS))
        field = node("a:fld", id="{" + str(uuid.uuid5(uuid.NAMESPACE_URL, name)) + "}", type="slidenum")
        sub(field, "a:rPr", lang="en-US")
        sub(field, "a:t").text = "1"
        p.insert(1, field)
    else:
        art = "divider-graph.jpg" if number == 3 else "cover-graph.jpg"
        picture(pkg, t, rels, ASSETS / art, (0, 0, 1280, 720), "Shared graph background", deco=True)
        shape(t, "Artwork contrast overlay", (0, 0, 1280, 720), fill=("24122A", .50) if number == 3 else ("101010", .42), deco=True)
        if number == 2:
            p = ASSETS / "logos/bme-vik-mit-ftsrg-white.png"
            picture(pkg, t, rels, p, png_box(p, 64, 648, 44), "BME VIK MIT FTSRG", deco=True)
    sub(m, "p:clrMap", **CMAP)
    ids = sub(m, "p:sldLayoutIdLst")
    for i in layouts:
        rid = "rId" + str(len(rels) + 1)
        sub(ids, "p:sldLayoutId", id=2147483648 + i, **{f"{{{NS['r']}}}id": rid})
        rels.append((rid, "slideLayout", f"../slideLayouts/slideLayout{i}.xml"))
    sub(m, "p:hf", hdr=0, ftr=0, dt=0, sldNum=int(number == 1))
    ts = sub(m, "p:txStyles")
    for kind, style in [("titleStyle", dict(size=30, leading=36, color="accent1", align="ctr", font="+mj-lt", tracking=2.1)),
                        ("bodyStyle", dict(size=23, leading=32.2, bullets=True)), ("otherStyle", dict(size=23))]:
        st = sub(ts, "p:" + kind)
        for level in range(9):
            paragraph_style(sub(st, f"a:lvl{level+1}pPr"), style, min(level, 2))
    path = f"ppt/slideMasters/slideMaster{number}.xml"
    pkg.put(path, m, PML + "slideMaster+xml")
    pkg.rels(path, rels)


def placeholder(name, kind, idx, box, text, **style):
    if kind in ("title", "ctrTitle", "subTitle"):
        style["caps"] = True
    return dict(name=name, ph=(kind, idx), box=box, text=text, style=style)


def layouts():
    # CSS pixels on the BPM deck's 1280 x 720 canvas. The cover and closing
    # positions also follow the talk's inline CSS, not only the shared theme.
    title = lambda text, y=91.625: placeholder("Slide title", "title", 0, (64, y, 1152, 48), text, size=30, leading=36, color="accent1", align="ctr", font="+mj-lt", tracking=2.1)
    caption = lambda text, y=560: placeholder("Caption / source", "body", 10, (100, y, 1080, 64), text, size=18, leading=25.2, color="3D3D3D", align="ctr")
    body = lambda name, idx, box, text, **kw: placeholder(name, "body", idx, box, text, **kw)
    eyebrow = lambda text: body("Section / topic", 11, (64, 70, 1152, 19), text.upper(), size=12.5, leading=15.625, font="Montserrat SemiBold", color="4A4A4A", tracking=2.75, align="ctr", caps=True)
    label = lambda name, idx, box, text, color="accent1": body(name, idx, box, text, size=12, leading=17.4, bold=True, tracking=2.4, color=color, caps=True)
    specs = [
        dict(name="01 Cover", master=2, kind="title", items=[
            placeholder("Presentation title", "ctrTitle", 0, (90, 184.4, 1100, 49), "Research title", size=38, leading=49.4, color="FFFFFF", align="ctr", font="Montserrat SemiBold", tracking=4.56),
            placeholder("Subtitle", "subTitle", 1, (90, 233.8, 1100, 104), "The problem and\nyour contribution", size=32, leading=49, color="FFFFFF", align="ctr", font="Montserrat Light", tracking=4.8),
            body("Authors", 2, (160, 396, 960, 24), "STUDENT NAME · COAUTHOR NAME", size=16, leading=22.4, color="E8E6E1", align="ctr", tracking=3.2),
            body("Event and date", 3, (160, 418.4, 960, 24), "TDK CONFERENCE · PRESENTATION DATE", size=13, leading=18.2, color="E3C6CB", align="ctr", tracking=3.64),
            body("Presenter name", 4, (630, 613.6, 380, 23), "STUDENT NAME", size=15, leading=21, bold=True, tracking=1.8, color="FFFFFF", align="r"),
            body("Presenter affiliation", 5, (630, 637.6, 380, 33), "Critical Systems Research Group\nBudapest University of Technology and Economics", size=11.5, leading=15.525, color="D8D6D1", align="r"),
            body("Presenter link", 6, (630, 673.6, 380, 20), "Your project URL", size=12, leading=16.8, font="JetBrains Mono", tracking=.24, color="FFFFFF", align="r"),
            placeholder("Optional presenter photo", "pic", 20, (1028, 611, 82, 82), "", size=12),
            placeholder("Optional contact QR", "pic", 21, (1128, 608, 88, 88), "", size=12)],
             panels=[(510, 367, 260, 1, "D9B9BE")],
             notes="Save a copy with your own filename. Replace the title, two-line subtitle, authors, event and presenter details. The composition follows the BPM 2026 cover. Optional picture placeholders at bottom right accept your portrait and a QR code whose destination you have checked; leave them empty if unneeded. Select the photo and use Crop > Crop to Shape > Oval. The PPTX and POTX contain the same examples."),
        dict(name="02 Section divider", master=3, kind="secHead", items=[
            placeholder("Section title", "title", 0, (120, 305, 1040, 115), "ASSUMPTIONS\nAND METHOD", size=44, leading=52.8, color="FFFFFF", align="ctr", font="Montserrat Light", tracking=4.4),
            body("Section label", 1, (120, 264, 1040, 24), "01 / METHOD", size=14, leading=19.6, font="Montserrat Medium", color="E3C6CB", align="ctr", tracking=4.9),
            body("Section summary", 2, (260, 466, 760, 64), "Describe the system, propose a rule,\nthen try to break it.", size=20, leading=29, color="F0E4EE", align="ctr")],
             panels=[(618, 433, 44, 1, "D9B9BE")],
             notes="This optional divider comes from the BPM/AVM shared CSS; the final BPM 2026 talk itself does not use a divider. Edit the section label and transition sentence. The purple graph artwork and overlay are shared on the Section master. Keep the title to two lines and the summary short."),
        dict(name="03 Title and text", master=1, kind="tx", items=[title("ASSUMPTIONS AND LIMITATIONS"), eyebrow("Research scope"),
            body("Main points", 1, (64, 165, 1152, 150), "A stable identifier must refer to the same logical job.\nA database transaction does not automatically cover an external service.\nA successful test covers the tested execution; a proof depends on its model.", size=23, leading=32.2, after=430, bullets=True),
            label("Note label", 2, (86, 348, 1108, 20), "NEXT EXPERIMENT"),
            body("Supporting note", 3, (86, 377, 1108, 72), "Introduce an external notification and inspect the gap between sending it and recording completion.", size=20.7, leading=30.015)],
             panels=[(64, 330, 1152, 137, "FFFFFF")],
             notes="Home > New Slide > Title and text adds this layout. Titles, topic labels and body text inherit their formatting from the layout. Enter creates another bullet; Tab / Shift+Tab changes level. Home > Reset restores geometry. Edit the project label and centered event/author line on the Content master."),
        dict(name="04 Two columns", master=1, kind="twoObj", items=[title("A RETRY CAN REPEAT A COMPLETED JOB"), eyebrow("Running example"),
            label("Left column label", 12, (86, 178, 517, 21), "EXAMPLE SCENARIO"),
            body("Left column", 1, (86, 207, 517, 108), "A worker completes a job, but its acknowledgement is lost. The queue sends the same job again.", size=20.7, leading=30.015),
            label("Right column label", 13, (677, 178, 517, 21), "WHY IT MATTERS", "A85E08"),
            body("Right column", 2, (677, 207, 517, 108), "Running a payment twice may change the result. The system needs an explicit rule for retries.", size=20.7, leading=30.015),
            body("Discussion question", 3, (88, 355, 1104, 49), "What happens when the same request arrives twice?", size=21.16, leading=29.624, align="ctr", color="3D3D3D"),
            caption("Illustrative example only. Replace it with your own research context.", 431)],
             panels=[(64, 160, 561, 170, "FFFFFF"), (655, 160, 561, 170, "FDEBD6"), (64, 343, 1152, 1, "A8A8A8"), (64, 411, 1152, 1, "A8A8A8")],
             notes="The two-column layout uses the BPM CSS's 30 px column gap, 22 px card padding and compact label/body hierarchy. Every label and paragraph is editable. The panels and discussion rules are on the layout. Read left to right. Replace the fictional scenario before using it as evidence."),
        dict(name="05 Three columns", master=1, kind="cust", items=[title("MODEL, RULE AND EVIDENCE"), eyebrow("Research method"),
            label("Model label", 12, (86, 178, 325.33, 21), "MODEL"),
            body("Model", 1, (86, 207, 325.33, 108), "State which messages can be lost and what storage survives.", size=20.7, leading=30.015),
            label("Rule label", 13, (477.33, 178, 325.33, 21), "RULE"),
            body("Rule", 2, (477.33, 207, 325.33, 108), "Record job completion together with its effect.", size=20.7, leading=30.015),
            label("Check label", 14, (868.67, 178, 325.33, 21), "CHECK"),
            body("Check", 3, (868.67, 207, 325.33, 108), "Explore a retry before, during and after completion.", size=20.7, leading=30.015),
            caption("Each step produces something another researcher can inspect.", 360)],
             panels=[(64 + i * (1174/3), 160, 1108/3, 170, "FFFFFF") for i in range(3)],
             notes="The three columns follow the BPM CSS's 22 px gap, 22 px horizontal padding and separate compact labels. Use this layout for parallel material. Use two columns when there are only two ideas. Keep labels short and replace the example text with your own method."),
        dict(name="06 Figure and caption", master=1, kind="picTx", items=[title("SYSTEM MODEL"), eyebrow("Research method"),
            placeholder("Research figure", "pic", 1, (80, 155, 1120, 400), "Insert your figure", size=23, align="ctr"),
            caption("Replace the example figure and describe its main point. Add the source.", 578)], special="figure",
             notes="The full-width figure area follows the BPM talk's diagram slides. Right-click > Change Picture replaces the example; Crop > Fit preserves the whole image. Use the picture icon on a new slide. Add meaningful Alt Text. The example comes from presentation/figures/workflow.svg; the separate native diagram is editable."),
        dict(name="07 Code and explanation", master=1, kind="twoObj", items=[title("A COMPLETION RECORD IS PART OF THE RULE"), eyebrow("Mechanism"),
            body("Editable code", 1, (82, 174, 1120, 155), "within one atomic transaction:\n    if job.id is already completed:\n        return its stored result\n    result = apply the job's effect\n    record completion and result", size=18.5, leading=25.9, font="JetBrains Mono"),
            label("Assumption label", 12, (86, 368, 1108, 21), "ASSUMPTION", "A85E08"),
            body("Explanation", 2, (86, 397, 1108, 75), "The effect and the completion record share a transaction. An external side effect needs a different protocol.", size=20.7, leading=30.015),
            caption("Pseudocode for discussion, not a production implementation.", 516)],
             panels=[(64, 160, 1152, 175, "FFFFFF"), (64, 350, 1152, 137, "FDEBD6")],
             notes="The full-width white code block uses the BPM CSS's 18.5 px JetBrains Mono and 25.9 px leading. The assumption follows below in an orange panel. Code stays editable. Replace the pseudocode and assumption together; no production behavior or measured result is claimed."),
        dict(name="08 Table and caption", master=1, kind="tbl", items=[title("EVALUATION PLAN", 72),
            placeholder("Editable table", "tbl", 1, (100, 140, 1080, 216), "Insert a table", size=18.86),
            caption("Evaluation plan only. Replace it with your results and cite their source.", 384)], special="table",
             notes="The native table follows BPM's compact red header and white rows. Header text is Montserrat SemiBold; body text is regular. Use Table Layout to edit rows and columns. Keep units and a source caption. Duplicate the example to retain its formatting. The rows are planned observations, not measured results."),
        dict(name="09 Chart and caption", master=1, kind="chart", items=[title("LATENCY BY SCENARIO"), eyebrow("Illustrative data"),
            placeholder("Editable chart", "chart", 1, (130, 155, 1020, 400), "Insert a chart", size=23),
            caption("Synthetic values for editing practice. No experiment is claimed.", 578)], special="chart",
             notes="This additional layout uses BPM typography and colors for a native chart with an embedded workbook. Right-click > Edit Data changes categories and values. Update units, conditions, uncertainty and Alt Text for your data. The example values (12, 18, 9 ms) are synthetic and require no external file."),
        dict(name="10 Title only / diagram", master=1, kind="titleOnly", items=[title("MODEL, RULE AND EVIDENCE"), eyebrow("Research method")], special="diagram",
             notes="The diagram uses native boxes and attached arrows, with the BPM palette and compact text. Drag a box and inspect the connector route. The example reads: Model leads to Rule, which leads to Evidence. Replace the labels and give a short explanation of your actual mechanism."),
        dict(name="11 Closing", master=2, kind="cust", items=[
            placeholder("Closing title", "title", 0, (64, 127, 1152, 44), "YOUR RESEARCH CONTRIBUTION", size=30, leading=42, color="FFFFFF", align="ctr", font="Montserrat SemiBold", tracking=2.4),
            body("Take-home statement", 1, (64, 169, 1152, 91), "THE ANSWER TO YOUR QUESTION\nWITH ITS EVIDENCE AND LIMITATIONS", size=30, leading=42, color="FFFFFF", align="ctr", font="Montserrat Light", tracking=2.4),
            *[item for i, (heading, text) in enumerate([
                ("RESULT", "The contribution supported by your evidence."),
                ("BOUNDARY", "The assumptions under which the result holds."),
                ("OPEN QUESTION", "The uncertainty that remains after this work."),
                ("NEXT STEP", "The next experiment or proof to investigate.")])
              for item in [
                body(f"Closing label {i+1}", 12+i, (79+i*291.5, 318, 247.5, 22), heading, size=13, leading=17.55, font="Montserrat SemiBold", tracking=2.6, color="E3C6CB"),
                body(f"Closing detail {i+1}", 22+i, (79+i*291.5, 338, 247.5, 108), text, size=18, leading=24.3, color="F3EFEA")]],
            body("Invitation", 2, (64, 462.5, 1152, 40), "Your project link and invitation to discuss", size=22, leading=30.8, font="Montserrat SemiBold", color="FFFFFF", align="ctr"),
            body("Contact name", 3, (730, 610.4, 360, 24), "STUDENT NAME", size=15, leading=21, bold=True, tracking=1.8, color="FFFFFF", align="r"),
            body("Contact details", 4, (730, 634.4, 360, 50), "Your email address\nYour project URL", size=14, leading=19.6, color="D8D6D1", align="r"),
            placeholder("Optional project QR", "pic", 30, (1114, 594, 96, 96), "", size=12)],
             panels=[(64+i*291.5, 304.7, 277.5, 146.7, ("0C0C0E", .55), ("FFFFFF", .16)) for i in range(4)] + [(64+i*291.5, 304.7, 277.5, 3, "D9B9BE") for i in range(4)],
             notes="This layout follows the actual BPM 2026 closing slide's three-line statement, four compact panels, invitation and bottom-right contact block. Replace the prompts with your supported conclusion and useful next questions. Delete unused panels and their text in Slide Master. The optional picture placeholder accepts a verified project QR. Leave the slide visible during questions."),
        dict(name="12 References / backup", master=1, kind="tx", items=[title("SOURCES AND REPRODUCIBILITY", 72),
            body("Backup tag", 11, (64, 72, 130, 20), "BACKUP", size=12, leading=16.8, bold=True, tracking=2.4, color="555555"),
            body("References and evidence", 1, (100, 150, 1080, 320), "[1] Author. Verified title. Venue, year. DOI or URL.\n[2] Dataset or artifact. Version and persistent identifier.\nReproduction: revision, configuration, commands and inputs.", size=23, leading=32.2, after=600),
            caption("These are prompts, not citations. Replace them with verified sources.", 520)],
             notes="The backup tag and 30 px title follow the BPM talk's backup pages. Use actual source titles and persistent links. Cite borrowed figures on their slides too. Follow the paper's AI declaration rules. Remove unused prompts and keep detailed evidence after the close."),
    ]
    # Keep the BPM portrait composition as an explicit choice. With empty picture
    # slots, it leaves a misleading gap beside the presenter on the default cover.
    portrait = copy.deepcopy(specs[0])
    portrait["name"] = "14 Cover with portrait and QR"
    specs[0]["items"] = [p for p in specs[0]["items"] if p["ph"][0] != "pic"]
    for item in specs[0]["items"]:
        if item["name"].startswith("Presenter"):
            x, y, w, h = item["box"]
            item["box"] = (x + 206, y, w, h)
    specs[0]["notes"] = "The default cover follows BPM's title, subtitle, rule and author hierarchy. It has no empty image slots: the presenter block aligns to the right margin. For a portrait and QR code choose layout 14. For a longer title choose layout 13, keeping the original type size. Title and subtitle use native All Caps formatting, so normal-case editing preserves the visual style. Save a copy and replace the example details."
    long_title = copy.deepcopy(specs[0])
    long_title["name"] = "13 Cover with two-line title"
    for item in long_title["items"]:
        if item["name"] == "Presentation title":
            item["box"] = (90, 150, 1100, 100)
            item["text"] = "Formal analysis of\nreliable job execution"
        elif item["name"] == "Subtitle":
            item["box"] = (90, 259, 1100, 88)
            item["style"]["leading"] = 41.6
            item["text"] = "Assumptions and evidence\nfor retries and failures"
    long_title["notes"] = "Use this cover when the main research title needs two lines. Insert a deliberate line break at a phrase boundary. The title keeps BPM's 38 px SemiBold type and the subtitle keeps its 32 px Light type. Their separate boxes do not overlap. Keep the main title within two lines and the subtitle within two lines. The fictional job-execution title is an editing example, not a reported finding."
    specs.extend([long_title, portrait])
    return specs


def frame(t, name, box, ph, descr):
    f = sub(t, "p:graphicFrame")
    nv = sub(f, "p:nvGraphicFramePr")
    sub(nv, "p:cNvPr", id=len(t), name=name, descr=descr)
    sub(sub(nv, "p:cNvGraphicFramePr"), "a:graphicFrameLocks", noGrp=1)
    sub(sub(nv, "p:nvPr"), "p:ph", type=ph[0], idx=ph[1])
    xfrm(f, box, "p:xfrm")
    return sub(sub(f, "a:graphic"), "a:graphicData")


def slide_number(t, number):
    s = shape(t, "Automatic slide number", text=str(number), ph=("sldNum", 90))
    paragraph = s.find("p:txBody/a:p", NS)
    paragraph.remove(paragraph.find("a:r", NS))
    field = node("a:fld", id="{" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"ftsrg-slide-{number}")) + "}", type="slidenum")
    sub(field, "a:rPr", lang="en-US")
    sub(field, "a:t").text = str(number)
    paragraph.insert(1, field)


def add_table(t):
    data = frame(t, "Evaluation plan table", (100, 140, 1080, 216), ("tbl", 1), "Evaluation plan with columns for scenario, evaluation question and evidence to record.")
    data.set("uri", "http://schemas.openxmlformats.org/drawingml/2006/table")
    tbl = sub(data, "a:tbl")
    sub(tbl, "a:tblPr", firstRow=1, bandRow=0)
    grid = sub(tbl, "a:tblGrid")
    for w in (280, 400, 400):
        sub(grid, "a:gridCol", w=emu(w))
    rows = [["Scenario", "Evaluation question", "Evidence to record"],
            ["No retry", "Does a job complete?", "Result and record"],
            ["Retry after completion", "Is the effect repeated?", "State before and after"],
            ["Failure during commit", "Are effect and record consistent?", "Trace or counterexample"]]
    for i, row in enumerate(rows):
        tr = sub(tbl, "a:tr", h=emu(54))
        for value in row:
            tc = sub(tr, "a:tc")
            text_body(tc, value, dict(size=18.86, leading=26.404, color="FFFFFF" if i == 0 else "tx1", font="Montserrat SemiBold" if i == 0 else "+mn-lt", tracking=.7544 if i == 0 else 0), tag="a:txBody")
            props = sub(tc, "a:tcPr", marL=emu(14), marR=emu(14), marT=emu(8), marB=emu(8), anchor="ctr")
            for edge in ("lnL", "lnR", "lnT", "lnB"):
                line = sub(props, "a:" + edge, w=emu(1))
                solid(line, "lt2") if edge == "lnB" else sub(line, "a:noFill")
            solid(props, "accent1" if i == 0 else "lt1")


def workbook():
    p = Package()
    w = node("s:workbook")
    sh = sub(w, "s:sheets")
    sub(sh, "s:sheet", name="Data", sheetId=1, **{f"{{{NS['r']}}}id": "rId1"})
    p.put("xl/workbook.xml", w, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
    ws = node("s:worksheet")
    rows = sub(ws, "s:sheetData")
    for i, values in enumerate([("Scenario", "Latency (ms)"), ("A", 12), ("B", 18), ("C", 9)], 1):
        row = sub(rows, "s:row", r=i)
        for col, value in zip("AB", values):
            cell = sub(row, "s:c", r=f"{col}{i}", t="n" if isinstance(value, int) else "inlineStr")
            if isinstance(value, int):
                sub(cell, "s:v").text = str(value)
            else:
                sub(sub(cell, "s:is"), "s:t").text = value
    p.put("xl/worksheets/sheet1.xml", ws, "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
    p.rels("", [("rId1", "officeDocument", "xl/workbook.xml")])
    p.rels("xl/workbook.xml", [("rId1", "worksheet", "worksheets/sheet1.xml")])
    out = io.BytesIO()
    p.write(out)
    return out.getvalue()


def chart_text(parent, text, size=18):
    tx = sub(parent, "c:tx")
    rich = text_body(tx, text, dict(size=size, after=0), tag="c:rich")
    for r in rich.findall(".//a:rPr", NS):
        r.set("sz", str(round(size * 75)))
        sub(r, "a:latin", typeface="Montserrat")


def chart_font(parent):
    body = text_body(parent, "", tag="c:txPr")
    rp = sub(body.find("a:p/a:pPr", NS), "a:defRPr", sz=1350)
    solid(rp, "dk1")
    sub(rp, "a:latin", typeface="Montserrat")
    body.find("a:p/a:endParaRPr", NS).set("sz", "1350")


def add_chart(pkg, t, rels):
    data = frame(t, "Illustrative latency chart", (130, 155, 1020, 400), ("chart", 1), "Synthetic example: A is 12 ms, B is 18 ms, C is 9 ms. Replace with real measurements.")
    data.set("uri", NS["c"])
    rid = "rId" + str(len(rels) + 1)
    sub(data, "c:chart", **{f"{{{NS['r']}}}id": rid})
    rels.append((rid, "chart", "../charts/chart1.xml"))
    cs = node("c:chartSpace")
    sub(cs, "c:date1904", val=0)
    sub(cs, "c:lang", val="en-US")
    ch = sub(cs, "c:chart")
    sub(ch, "c:autoTitleDeleted", val=1)
    plot = sub(ch, "c:plotArea")
    sub(plot, "c:layout")
    bar = sub(plot, "c:barChart")
    sub(bar, "c:barDir", val="col")
    sub(bar, "c:grouping", val="clustered")
    sub(bar, "c:varyColors", val=0)
    ser = sub(bar, "c:ser")
    sub(ser, "c:idx", val=0)
    sub(ser, "c:order", val=0)
    tx = sub(ser, "c:tx")
    ref = sub(tx, "c:strRef")
    sub(ref, "c:f").text = "Data!$B$1"
    cache = sub(ref, "c:strCache")
    sub(cache, "c:ptCount", val=1)
    sub(sub(cache, "c:pt", idx=0), "c:v").text = "Latency (ms)"
    solid(sub(ser, "c:spPr"), "accent1")
    for kind, typ, formula, values in [("cat", "str", "Data!$A$2:$A$4", ["A", "B", "C"]),
                                        ("val", "num", "Data!$B$2:$B$4", [12, 18, 9])]:
        ref = sub(sub(ser, "c:" + kind), "c:" + typ + "Ref")
        sub(ref, "c:f").text = formula
        cache = sub(ref, "c:" + typ + "Cache")
        if typ == "num":
            sub(cache, "c:formatCode").text = "0"
        sub(cache, "c:ptCount", val=len(values))
        for i, value in enumerate(values):
            sub(sub(cache, "c:pt", idx=i), "c:v").text = str(value)
    sub(bar, "c:gapWidth", val=120)
    sub(bar, "c:axId", val=101)
    sub(bar, "c:axId", val=102)
    for typ, ident, cross, pos, title in [("catAx", 101, 102, "b", "Scenario"), ("valAx", 102, 101, "l", "Latency (ms)")]:
        axis = sub(plot, "c:" + typ)
        sub(axis, "c:axId", val=ident)
        scaling = sub(axis, "c:scaling")
        sub(scaling, "c:orientation", val="minMax")
        if typ == "valAx":
            sub(scaling, "c:min", val=0)
        sub(axis, "c:delete", val=0)
        sub(axis, "c:axPos", val=pos)
        if typ == "valAx":
            sub(axis, "c:majorGridlines")
        chart_text(sub(axis, "c:title"), title)
        sub(axis, "c:numFmt", formatCode="0" if typ == "valAx" else "General", sourceLinked=0)
        sub(axis, "c:majorTickMark", val="none")
        sub(axis, "c:minorTickMark", val="none")
        sub(axis, "c:tickLblPos", val="nextTo")
        chart_font(axis)
        sub(axis, "c:crossAx", val=cross)
        sub(axis, "c:crosses", val="autoZero")
        if typ == "valAx":
            sub(axis, "c:crossBetween", val="between")
            sub(axis, "c:majorUnit", val=5)
        else:
            sub(axis, "c:auto", val=1)
            sub(axis, "c:lblAlgn", val="ctr")
            sub(axis, "c:lblOffset", val=100)
    sub(ch, "c:plotVisOnly", val=1)
    sub(ch, "c:dispBlanksAs", val="gap")
    sp = sub(cs, "c:spPr")
    solid(sp, "lt1")
    chart_font(cs)
    sub(sub(cs, "c:externalData", **{f"{{{NS['r']}}}id": "rId1"}), "c:autoUpdate", val=0)
    pkg.put("ppt/charts/chart1.xml", cs, "application/vnd.openxmlformats-officedocument.drawingml.chart+xml")
    pkg.rels("ppt/charts/chart1.xml", [("rId1", "package", "../embeddings/chart-data.xlsx")])
    pkg.put("ppt/embeddings/chart-data.xlsx", workbook())


def add_diagram(t):
    ids = []
    for i, (label, text) in enumerate([("Model", "Failures and state"), ("Rule", "Completion and effect"), ("Evidence", "Tests or proofs")]):
        s = shape(t, label, (90 + i * 405, 230, 290, 110), label + "\n" + text,
                  dict(size=23, leading=32.2, align="ctr", after=900, anchor="ctr"), fill="lt1", border="accent1")
        ids.append(s.find("p:nvSpPr/p:cNvPr", NS).get("id"))
    for i in range(2):
        c = sub(t, "p:cxnSp")
        nv = sub(c, "p:nvCxnSpPr")
        sub(nv, "p:cNvPr", id=len(t), name=f"{i+1}. Flow connector")
        pr = sub(nv, "p:cNvCxnSpPr")
        sub(pr, "a:stCxn", id=ids[i], idx=3)
        sub(pr, "a:endCxn", id=ids[i+1], idx=1)
        sub(nv, "p:nvPr")
        sp = sub(c, "p:spPr")
        xfrm(sp, (380+i*405, 285, 115, 0))
        sub(sub(sp, "a:prstGeom", prst="line"), "a:avLst")
        ln = sub(sp, "a:ln", w=emu(3))
        solid(ln, "accent1")
        sub(ln, "a:tailEnd", type="triangle", w="med", len="med")
    shape(t, "Diagram explanation", (120, 375, 1040, 75), "Each arrow connects an explicit input to an inspectable output.", dict(size=18, leading=25.2, align="ctr"))


def notes_master(pkg):
    m = node("p:notesMaster")
    cs = sub(m, "p:cSld", name="Speaker notes")
    t = tree(cs)
    shape(t, "Slide preview", (48, 36, 624, 351), "", ph=("sldImg", 2))
    shape(t, "Speaker notes", (48, 420, 624, 480), "", dict(size=18), ph=("body", 3))
    sub(m, "p:clrMap", **CMAP)
    sub(m, "p:hf", hdr=0, ftr=0, dt=0, sldNum=0)
    paragraph_style(sub(sub(m, "p:notesStyle"), "a:lvl1pPr"), dict(size=18))
    pkg.put("ppt/notesMasters/notesMaster1.xml", m, PML + "notesMaster+xml")
    pkg.rels("ppt/notesMasters/notesMaster1.xml", [("rId1", "theme", "../theme/theme1.xml")])


def build(output):
    specs = layouts()
    pkg = Package()
    pkg.put("ppt/theme/theme1.xml", theme(), "application/vnd.openxmlformats-officedocument.theme+xml")
    for number, name in [(1, "Content — project label and logos"), (2, "Cover and closing"), (3, "Section divider")]:
        make_master(pkg, number, name, [i for i, s in enumerate(specs, 1) if s["master"] == number])
    notes_master(pkg)
    for i, spec in enumerate(specs, 1):
        layout = node("p:sldLayout", type=spec["kind"], preserve=1)
        lt = tree(sub(layout, "p:cSld", name=spec["name"]))
        for x, y, w, h, color, *border in spec.get("panels", []):
            shape(lt, "Shared panel", (x, y, w, h), fill=color, border=border[0] if border else None, deco=True)
        for ph in spec["items"]:
            shape(lt, **ph)
        if spec["master"] == 1:
            slide_number(lt, i)
        sub(sub(layout, "p:clrMapOvr"), "a:masterClrMapping")
        sub(layout, "p:hf", hdr=0, ftr=0, dt=0, sldNum=int(spec["master"] == 1))
        path = f"ppt/slideLayouts/slideLayout{i}.xml"
        pkg.put(path, layout, PML + "slideLayout+xml")
        pkg.rels(path, [("rId1", "slideMaster", f"../slideMasters/slideMaster{spec['master']}.xml")])
        slide = node("p:sld")
        st = tree(sub(slide, "p:cSld", name=spec["name"]))
        rels = [("rId1", "slideLayout", f"../slideLayouts/slideLayout{i}.xml"), ("rId2", "notesSlide", f"../notesSlides/notesSlide{i}.xml")]
        for ph in spec["items"]:
            if ph["ph"][0] in ("tbl", "chart", "pic"):
                if spec.get("special") == "table":
                    add_table(st)
                elif spec.get("special") == "chart":
                    add_chart(pkg, st, rels)
                elif spec.get("special") == "figure":
                    image = ROOT / "assets/workflow.png"
                    picture(pkg, st, rels, image, png_fit(image, (80, 155, 1120, 400)), "Example workflow figure",
                            "A system model leads to a candidate rule, then to evidence from tests or proofs.", ph=("pic", 1))
                else:
                    shape(st, ph["name"], text="", ph=ph["ph"])
            else:
                s = shape(st, ph["name"], text=ph["text"], ph=ph["ph"])
                if ph["name"] == "Authors":
                    p = s.find("p:txBody/a:p", NS)
                    r = p.find("a:r", NS)
                    first, separator, rest = ph["text"].partition(" · ")
                    r.find("a:rPr", NS).set("b", "1")
                    solid(r.find("a:rPr", NS), "FFFFFF")
                    r.find("a:t", NS).text = first
                    tail = node("a:r")
                    sub(tail, "a:rPr", lang="en-US")
                    sub(tail, "a:t").text = separator + rest
                    p.insert(list(p).index(r) + 1, tail)
        if spec.get("special") == "diagram":
            add_diagram(st)
        if spec["master"] == 1:
            slide_number(st, i)
        sub(sub(slide, "p:clrMapOvr"), "a:masterClrMapping")
        path = f"ppt/slides/slide{i}.xml"
        pkg.put(path, slide, PML + "slide+xml")
        pkg.rels(path, rels)
        notes = node("p:notes")
        nt = tree(sub(notes, "p:cSld"))
        shape(nt, "Slide preview", text="", ph=("sldImg", 2))
        shape(nt, "Speaker notes", text=spec["notes"] + "\n\nDesign: presentation/theme/bme.css; provenance and rights: presentation/PROVENANCE.md. Before delivery, check font rendering, reading order and accessibility in PowerPoint, and remove unused example slides.", ph=("body", 3))
        sub(sub(notes, "p:clrMapOvr"), "a:masterClrMapping")
        path = f"ppt/notesSlides/notesSlide{i}.xml"
        pkg.put(path, notes, PML + "notesSlide+xml")
        pkg.rels(path, [("rId1", "notesMaster", "../notesMasters/notesMaster1.xml"), ("rId2", "slide", f"../slides/slide{i}.xml")])
    pres = node("p:presentation", embedTrueTypeFonts=1, saveSubsetFonts=0, autoCompressPictures=0)
    mids = sub(pres, "p:sldMasterIdLst")
    rels = []
    for i in range(1, 4):
        rid = "rId" + str(len(rels) + 1)
        sub(mids, "p:sldMasterId", id=2147483647 + i, **{f"{{{NS['r']}}}id": rid})
        rels.append((rid, "slideMaster", f"slideMasters/slideMaster{i}.xml"))
    sub(sub(pres, "p:notesMasterIdLst"), "p:notesMasterId", **{f"{{{NS['r']}}}id": "rId4"})
    rels.append(("rId4", "notesMaster", "notesMasters/notesMaster1.xml"))
    ids = sub(pres, "p:sldIdLst")
    for i in range(1, len(specs) + 1):
        rid = "rId" + str(len(rels) + 1)
        sub(ids, "p:sldId", id=255+i, **{f"{{{NS['r']}}}id": rid})
        rels.append((rid, "slide", f"slides/slide{i}.xml"))
    sub(pres, "p:sldSz", cx=emu(1280), cy=emu(720), type="screen16x9")
    sub(pres, "p:notesSz", cx=emu(720), cy=emu(960))
    embedded = sub(pres, "p:embeddedFontLst")
    for family, faces in FONTS.items():
        entry = sub(embedded, "p:embeddedFont")
        sub(entry, "p:font", typeface=family)
        for style, filename in faces.items():
            rid = "rId" + str(len(rels) + 1)
            target = "fonts/" + filename.replace(".ttf", ".fntdata")
            sub(entry, "p:" + style, **{f"{{{NS['r']}}}id": rid})
            rels.append((rid, "font", target))
            pkg.put("ppt/" + target, eot((ROOT / "fonts" / filename).read_bytes(), family), "application/x-fontdata")
    paragraph_style(sub(sub(pres, "p:defaultTextStyle"), "a:lvl1pPr"), dict(size=23, leading=32.2))
    pkg.rels("ppt/presentation.xml", rels)
    pkg.rels("", [("rId1", "officeDocument", "ppt/presentation.xml"),
                  ("rId2", "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "docProps/core.xml"),
                  ("rId3", "extended-properties", "docProps/app.xml")])
    core = ET.Element("{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}coreProperties")
    for local, value in [("title", "FTSRG editable PowerPoint starter"), ("creator", "FTSRG Blockchain Lab TDK"), ("description", "Current FTSRG design with reusable layouts and illustrative examples. See the companion README and provenance.")]:
        ET.SubElement(core, "{http://purl.org/dc/elements/1.1/}" + local).text = value
    pkg.put("docProps/core.xml", core, "application/vnd.openxmlformats-package.core-properties+xml")
    app = ET.Element("Properties", xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties")
    for tag, value in [("Application", "FTSRG template builder"), ("PresentationFormat", "On-screen Show (16:9)"), ("Slides", str(len(specs))), ("Notes", str(len(specs))), ("HiddenSlides", "0")]:
        ET.SubElement(app, tag).text = value
    pkg.put("docProps/app.xml", app, "application/vnd.openxmlformats-officedocument.extended-properties+xml")
    output.mkdir(parents=True, exist_ok=True)
    for ext, subtype in [("pptx", "presentation"), ("potx", "template")]:
        pkg.put("ppt/presentation.xml", pres, PML + subtype + ".main+xml")
        pkg.write(output / ("ftsrg-current." + ext))
    print(json.dumps({"slides": len(specs), "layouts": [s["name"] for s in specs], "masters": 3, "output": str(output)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT.parent / "dist/powerpoint")
    build(parser.parse_args().output_dir)
