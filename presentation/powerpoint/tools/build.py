#!/usr/bin/env python3
"""Build native PowerPoint examples and layouts; Python standard library only.

The checked-in PPTX/POTX are student deliverables, not renders of Markdown.
All dimensions below are CSS pixels on the source theme's 1280 x 720 canvas.
"""
import argparse
import io
import json
import struct
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

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
    attrs = {} if inherited else dict(wrap="square", lIns=0, rIns=0, tIns=0, bIns=0, anchor="t")
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
    sp = sub(pp, "a:lnSpc")
    sub(sp, "a:spcPct", val=style.get("line", 125000))
    sub(sub(pp, "a:spcAft"), "a:spcPts", val=style.get("after", 1200))
    if style.get("bullets"):
        solid_dummy = sub(pp, "a:buClr")
        sub(solid_dummy, "a:schemeClr", val="accent1")
        sub(pp, "a:buSzPct", val=70000)
        sub(pp, "a:buFont", typeface="Arial")
        sub(pp, "a:buChar", char="▪" if level == 0 else "–")
    else:
        sub(pp, "a:buNone")
    rp = sub(pp, "a:defRPr", sz=round((style.get("size", 28) - level * 2) * 75),
             b=int(style.get("bold", False)), kern=1200)
    if style.get("tracking"):
        rp.set("spc", str(style["tracking"]))
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
        solid(ln, border) if border else sub(ln, "a:noFill")
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
        sub(f, "a:latin", typeface="Montserrat")
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
        shape(t, "Header rule", (64, 37, 1152, 1), fill="A8A8A8", deco=True)
        shape(t, "Project label — edit on master", (64, 12, 760, 21), "RESEARCH PROJECT",
              dict(size=14, color="555555", after=0, tracking=120))
        for file, x, h in [("ftsrg-grey.png", 1105, 20), ("bme-wordmark-grey.png", 1165, 15)]:
            p = ASSETS / "logos" / file
            picture(pkg, t, rels, p, png_box(p, x, 15, h), file, deco=True)
        s = shape(t, "Automatic slide number", (1229, 13, 36, 22), "1", dict(size=14, color="555555", after=0), ph=("sldNum", 90))
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
            picture(pkg, t, rels, p, png_box(p, 64, 650, 44), "BME VIK MIT FTSRG", deco=True)
    sub(m, "p:clrMap", **CMAP)
    ids = sub(m, "p:sldLayoutIdLst")
    for i in layouts:
        rid = "rId" + str(len(rels) + 1)
        sub(ids, "p:sldLayoutId", id=2147483648 + i, **{f"{{{NS['r']}}}id": rid})
        rels.append((rid, "slideLayout", f"../slideLayouts/slideLayout{i}.xml"))
    sub(m, "p:hf", hdr=0, ftr=0, dt=0, sldNum=int(number == 1))
    ts = sub(m, "p:txStyles")
    for kind, style in [("titleStyle", dict(size=36, color="accent1", align="ctr", font="+mj-lt")),
                        ("bodyStyle", dict(size=28, bullets=True)), ("otherStyle", dict(size=24))]:
        st = sub(ts, "p:" + kind)
        for level in range(9):
            paragraph_style(sub(st, f"a:lvl{level+1}pPr"), style, min(level, 2))
    path = f"ppt/slideMasters/slideMaster{number}.xml"
    pkg.put(path, m, PML + "slideMaster+xml")
    pkg.rels(path, rels)


def placeholder(name, kind, idx, box, text, **style):
    return dict(name=name, ph=(kind, idx), box=box, text=text, style=style)


def layouts():
    title = lambda text: placeholder("Slide title", "title", 0, (64, 72, 1152, 100), text, size=36, color="accent1", align="ctr", font="+mj-lt", after=0)
    caption = lambda text: placeholder("Caption / source", "body", 10, (64, 619, 1152, 64), text, size=20, color="555555", align="ctr", after=0)
    body = lambda name, idx, box, text, **kw: placeholder(name, "body", idx, box, text, **kw)
    return [
        dict(name="01 Cover", master=2, kind="title", items=[
            placeholder("Presentation title", "ctrTitle", 0, (90, 190, 1100, 115), "YOUR RESEARCH TITLE", size=44, color="FFFFFF", align="ctr", font="+mj-lt", bold=True, tracking=180),
            placeholder("Subtitle", "subTitle", 1, (110, 315, 1060, 82), "The problem and your contribution", size=32, color="FFFFFF", align="ctr"),
            body("Author and event", 2, (160, 445, 960, 110), "Student name\nTDK conference · Presentation date", size=24, color="FFFFFF", align="ctr"),
            body("Affiliation", 3, (760, 650, 456, 46), "Critical Systems Research Group · BME", size=16, color="FFFFFF", align="r")],
             notes="Start here. Save a working copy with your own filename. Replace the title, subtitle, author, event and affiliation. Keep titles short; use a second line rather than reducing the font. View > Slide Master controls the shared artwork and logos. The PPTX and POTX contain the same editable examples."),
        dict(name="02 Section divider", master=3, kind="secHead", items=[
            placeholder("Section title", "title", 0, (100, 285, 1080, 145), "MAKE THE ASSUMPTIONS EXPLICIT", size=44, color="FFFFFF", align="ctr", font="+mj-lt"),
            body("Section label", 1, (120, 225, 1040, 40), "01 / METHOD", size=18, color="FFFFFF", align="ctr", tracking=160),
            body("Section summary", 2, (200, 460, 880, 95), "Describe the system, propose a rule, then try to break it.", size=28, color="FFFFFF", align="ctr")],
             notes="Use a divider only when the audience needs a change of topic. Edit the section label and the short transition sentence. Background contrast and artwork are inherited from the Section master."),
        dict(name="03 Title and text", master=1, kind="tx", items=[title("STATE A QUESTION YOU CAN TEST"),
            body("Main points", 1, (100, 210, 1080, 360), "What changes when a completed job is retried?\nState the assumptions behind your answer.\nName the evidence that could disprove it.", size=30, bullets=True)],
             notes="Home > New Slide > Title and text adds this layout. Use the title placeholder so the slide has an accessible title. Enter creates another bullet; Tab / Shift+Tab changes level. Use Home > Reset to restore placeholder geometry and inherited formatting. Change the project label once on the Content master."),
        dict(name="04 Two columns", master=1, kind="twoObj", items=[title("A RETRY CAN REPEAT A COMPLETED JOB"),
            body("Left column", 1, (86, 220, 517, 300), "Example scenario\nA worker completes a job, but its acknowledgement is lost. The queue sends the same job again.", size=28),
            body("Right column", 2, (677, 220, 517, 300), "Why it matters\nRunning a payment twice may change the result. The system needs an explicit rule for retries.", size=28),
            caption("Illustrative example only; replace it with your own research context.")], panels=[(64, 195, 561, 370, "FFFFFF"), (655, 195, 561, 370, "FDEBD6")],
             notes="Reading order is title, left column, right column, caption. The colored panels live on the layout; the text remains editable in Normal view. Duplicate the slide for a second comparison rather than shrinking the text."),
        dict(name="05 Three columns", master=1, kind="cust", items=[title("CONNECT EACH STEP TO AN OUTPUT"),
            body("Model", 1, (86, 220, 331, 330), "Model\nState which messages can be lost and what storage survives.", size=27),
            body("Rule", 2, (474, 220, 331, 330), "Rule\nRecord job completion together with its effect.", size=27),
            body("Check", 3, (862, 220, 331, 330), "Check\nExplore a retry before, during and after completion.", size=27),
            caption("Each step should produce something another researcher can inspect.")], panels=[(64 + i * 388, 195, 376, 390, "FFFFFF") for i in range(3)],
             notes="Use this layout for three short, genuinely parallel ideas. Do not add a third item just to fill the template. Use the two-column layout for two ideas. Read left to right."),
        dict(name="06 Figure and caption", master=1, kind="picTx", items=[title("SHOW THE SYSTEM YOU ARE REASONING ABOUT"),
            placeholder("Research figure", "pic", 1, (160, 215, 960, 330), "Insert your figure", size=30, align="ctr"),
            caption("Replace the example figure and describe its main point. Add the source.")], special="figure",
             notes="The example image is attached to a picture placeholder. Right-click > Change Picture replaces it; Crop > Fit preserves the full figure. On a new slide, use the picture icon. Add meaningful Alt Text describing the figure's conclusion, not its filename. Avoid screenshots of text. The source of this example is presentation/figures/workflow.svg."),
        dict(name="07 Code and explanation", master=1, kind="twoObj", items=[title("A COMPLETION RECORD IS PART OF THE RULE"),
            body("Editable code", 1, (86, 220, 730, 330), "within one atomic transaction:\n  if job.id is completed:\n    return its stored result\n  result = apply the effect\n  record completion and result", size=24, font="JetBrains Mono", line=145000, after=0),
            body("Explanation", 2, (878, 220, 310, 330), "Assumption\nThe effect and completion record share a transaction. An external effect needs a different protocol.", size=27),
            caption("Pseudocode for discussion, not a production implementation.")], panels=[(64, 195, 774, 390, "FFFFFF"), (856, 195, 360, 390, "FDEBD6")],
             notes="Code is editable text in JetBrains Mono, not an image. Keep lines short enough for the placeholder. Split a long listing across slides. The explanation follows the code in reading order. Replace the fictional mechanism with your own and make assumptions explicit."),
        dict(name="08 Table and caption", master=1, kind="tbl", items=[title("MAKE THE EXPECTED EVIDENCE VISIBLE"),
            placeholder("Editable table", "tbl", 1, (64, 210, 1152, 320), "Insert a table", size=26),
            caption("Evaluation plan only. Replace it with your results and cite their source.")], special="table",
             notes="This is a native PowerPoint table with a header row and no merged cells. Use Table Layout to add rows or columns. Keep the header descriptive, include units, and use a caption for the source. On a new slide use the table placeholder, then apply a high-contrast header. Do not present these planned observations as measured results."),
        dict(name="09 Chart and caption", master=1, kind="chart", items=[title("ILLUSTRATIVE CHART — REPLACE THE DATA"),
            placeholder("Editable chart", "chart", 1, (130, 190, 1020, 385), "Insert a chart", size=26),
            caption("Synthetic values for editing practice. No experiment is claimed.")], special="chart",
             notes="This native chart has an embedded workbook. Right-click > Edit Data changes both categories and values. Rename the axis units and series, describe the measurement conditions, and add uncertainty where appropriate. The illustrative values (12, 18, 9 ms) are synthetic. Replace the Alt Text with the conclusion of your real chart. No external workbook link is used."),
        dict(name="10 Title only / diagram", master=1, kind="titleOnly", items=[title("KEEP THE MECHANISM EDITABLE")], special="diagram",
             notes="The example uses native shapes and connected arrows. Drag a box: the connectors remain attached. Edit the labels, then inspect connector routes. Give the complete diagram a concise description in the notes. The example reads: Model leads to Rule, which leads to Evidence. Use this layout for diagrams or other native objects."),
        dict(name="11 Closing", master=2, kind="cust", items=[
            placeholder("Closing title", "title", 0, (90, 180, 1100, 150), "YOUR SUPPORTED CONCLUSION", size=44, color="FFFFFF", align="ctr", font="+mj-lt"),
            body("Take-home statement", 1, (160, 360, 960, 100), "State the answer, the evidence and the main limitation.", size=30, color="FFFFFF", align="ctr"),
            body("Author / project contact", 2, (240, 490, 800, 105), "Student name\nProject URL or contact", size=24, color="FFFFFF", align="ctr")],
             notes="Leave this slide visible during questions. Replace the instructional sentence with your supported conclusion. Enter your real project URL and add a hyperlink with Insert > Link. This starter has no live placeholder contact link."),
        dict(name="12 References / backup", master=1, kind="tx", items=[title("SOURCES AND REPRODUCIBILITY"),
            body("References and evidence", 1, (90, 200, 1100, 380), "[1] Author. Verified title. Venue, year. DOI or URL.\n[2] Dataset or artifact. Version and persistent identifier.\nReproduction: revision, configuration, commands and inputs.", size=27),
            caption("These are prompts, not citations. Replace them with verified sources.")],
             notes="Keep this and other backup slides after the close. Use actual source titles and persistent links. Cite borrowed figures on their own slides as well. Do not add an AI answer to the bibliography; follow the paper's AI-use declaration rules. Remove any unused example or prompt before sharing."),
    ]


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
    data = frame(t, "Evaluation plan table", (64, 210, 1152, 320), ("tbl", 1), "Evaluation plan with columns for scenario, evaluation question and evidence to record.")
    data.set("uri", "http://schemas.openxmlformats.org/drawingml/2006/table")
    tbl = sub(data, "a:tbl")
    sub(tbl, "a:tblPr", firstRow=1, bandRow=0)
    grid = sub(tbl, "a:tblGrid")
    for w in (300, 420, 432):
        sub(grid, "a:gridCol", w=emu(w))
    rows = [["Scenario", "Evaluation question", "Evidence to record"],
            ["No retry", "Does a job complete?", "Result and record"],
            ["Retry after completion", "Is the effect repeated?", "State before and after"],
            ["Failure during commit", "Are effect and record consistent?", "Trace or counterexample"]]
    for i, row in enumerate(rows):
        tr = sub(tbl, "a:tr", h=emu(80))
        for value in row:
            tc = sub(tr, "a:tc")
            text_body(tc, value, dict(size=25, color="FFFFFF" if i == 0 else "tx1", bold=i == 0, after=0), tag="a:txBody")
            props = sub(tc, "a:tcPr", marL=emu(16), marR=emu(14), marT=emu(12), marB=emu(10), anchor="ctr")
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


def chart_text(parent, text, size=22):
    tx = sub(parent, "c:tx")
    rich = text_body(tx, text, dict(size=size, after=0), tag="c:rich")
    for r in rich.findall(".//a:rPr", NS):
        r.set("sz", str(round(size * 75)))
        sub(r, "a:latin", typeface="Montserrat")


def chart_font(parent):
    body = text_body(parent, "", tag="c:txPr")
    rp = sub(body.find("a:p/a:pPr", NS), "a:defRPr", sz=1650)
    solid(rp, "dk1")
    sub(rp, "a:latin", typeface="Montserrat")
    body.find("a:p/a:endParaRPr", NS).set("sz", "1650")


def add_chart(pkg, t, rels):
    data = frame(t, "Illustrative latency chart", (130, 190, 1020, 385), ("chart", 1), "Synthetic example: A is 12 ms, B is 18 ms, C is 9 ms. Replace with real measurements.")
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
        s = shape(t, label, (90 + i * 405, 280, 290, 180), label + "\n" + text,
                  dict(size=27, align="ctr", after=1200), fill="lt1", border="accent1")
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
        xfrm(sp, (380+i*405, 370, 115, 0))
        sub(sub(sp, "a:prstGeom", prst="line"), "a:avLst")
        ln = sub(sp, "a:ln", w=emu(3))
        solid(ln, "accent1")
        sub(ln, "a:tailEnd", type="triangle", w="med", len="med")
    shape(t, "Diagram explanation", (120, 530, 1040, 100), "Each arrow connects an explicit input to an inspectable output.", dict(size=28, align="ctr"))


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
        for x, y, w, h, color in spec.get("panels", []):
            shape(lt, "Shared panel", (x, y, w, h), fill=color, deco=True)
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
                    picture(pkg, st, rels, image, png_fit(image, (160, 215, 960, 330)), "Example workflow figure",
                            "A system model leads to a candidate rule, then to evidence from tests or proofs.", ph=("pic", 1))
            else:
                shape(st, ph["name"], text=ph["text"], ph=ph["ph"])
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
    pres = node("p:presentation", saveSubsetFonts=0, autoCompressPictures=0)
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
    paragraph_style(sub(sub(pres, "p:defaultTextStyle"), "a:lvl1pPr"), dict(size=28))
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
