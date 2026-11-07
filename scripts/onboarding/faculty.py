"""Bring a paper written in the BME VIK faculty LaTeX template into paper/.

A one-way import, not a template update. Student files are copied byte for byte; chapter
labels, the appendix's glossary lists and preamble definitions are suggested, and are written
only when the student confirms them; a file the student already wrote in this repository is
never overwritten. The faculty template is not redistributed here: only the SHA-256 digests of
its files are kept, so that its unchanged sample files are recognised and left out.
"""
import difflib
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import unicodedata
import zipfile

# The archive analysed for this importer, from the faculty TDK portal's download page.
FACULTY_SOURCE = {
    "page": "https://tdk.bme.hu/conference/VIK/2026/Download",
    "url": "https://tdk.bme.hu/upload/conference/VIK/DiplomatervSablon_LaTeX_v1_20241003-110113.zip",
    "version": "DiplomatervSablon_LaTeX_v1, uploaded 2024-10-03, files dated 2019-03-26",
    "sha256": "58838c914047d33ef75ee84a9d6875e33d2178b6b0e55443e8a318a66def5cba",
}

# Digests of the faculty archive's files. A sample file with its original digest is the
# faculty's placeholder text, not the student's, and is left out.
FACULTY = {
    "Makefile": "17261d0158e8fb030f0999051f776c8d8b70da1a48c549c69bde5a9cc722e916",
    "bib/mybib.bib": "e4f9a464360a3a8aaba218d3d2a4c9626b97fbf40f26811b37d896dd51e1f168",
    "content/abstract.tex": "fda5be919af552f8e4e33c47da7ce59d27bc56b4d6659ceb2be484feed2c1634",
    "content/acknowledgement.tex": "ffe5e72381bf6d6364578149f8873c73d0e4566c7690d04bddc3b97852b658d8",
    "content/appendices.tex": "c998ca8bde967296b9c5b6b01c18d935b299a8ae092d8a138b0eb6ff680d3e28",
    "content/introduction.tex": "770d86086f687c708334b0507b1093c071ae563cc87d4451604a124f190e8c8c",
    "content/latex-tools.tex": "b1a9e51b34780aa206ba424e66a67c0f86a4a389cf5b2efd6ca0303d866a7589",
    "content/template-usage.tex": "792d04a18e39b31cbf16161dff8870d04867adf68b74cd03c98502913f7381d5",
    "content/thesis-format.tex": "b269d49a9cc2d3d451bbbf8947552397b80fbb4b3916d98e6d0c0f9c7ddaffa2",
    "figures/TeXstudio.png": "8731849f9d7b9488ac9c43253ec74456c483cca05faafa0e98a8c97448952924",
    "figures/bme_logo.pdf": "db48960140580405f54cbbd7f0422f73792e44ce3f24ffd4bde9f87435594b0d",
    "figures/convert.cmd": "e5cc2c086376d4d04ce19e2759fe31c16459c5fb193652dfef31265a6e590c6b",
    "huplain.bst": "c8406060c955b3d9dc5b86509a2e353b9e6ea5e683ea20f2bc7b79e3e5166eef",
    "include/declaration.tex": "b52b4e7ae3458d3c8ce32de36ee74de0598205e28594d3ad07c6fcec3df03c8a",
    "include/guideline.tex": "f9357a21e8614e50a1bba66f87cd59829d46daaac920b12bf5df4d76f29dc09f",
    "include/packages.tex": "0dca7e15d852ab15729950102b4122ade28af6f33ecc83795fd7d2362e2dc284",
    "include/preamble.tex": "3af1b2e67cea24fdae615745768662c43e41723f7109edbc768a241dc6536089",
    "include/project.tex": "e27949ccdf19bcd2edbd8e2b8fba9e7b65439cc662f62bba815e75b7e0dc5c7a",
    "include/tdk-variables.tex": "040aa4ce725bdfe7cb5375a3446da44cc15890b177df4b5b69de6ca368453fcf",
    "include/thesis-en.tex": "859bf668244f815c0bd121994cec3e82a7d50811cbd2f84034a4bc6ff996e0b0",
    "include/thesis-hu.tex": "961b6f44ba6366d28bfa7ee016e77cb50398b5564b40ad735259ef090e8cb2f1",
    "include/titlepage-otdk.tex": "20a1ec90472d3ed915ad6b437cc71d3d535713b5af4cc5f444376f977f8709e3",
    "include/titlepage-tdk.tex": "2d50f5b404a2eaf44892bd8fe391b08c986b99d746ef5ab66f46722ff1ef4cb4",
    "include/titlepage.tex": "6b5a986a7cb6bf897df9198687413d69e69552ef03c2e277b7bcf1356ce2fb29",
    "lua/language.dat.lua": "9f0bd8cf5e8be8566bc490919653ea185a57db9e54c82765aa85393f18714941",
    "magyar.ldf": "f30c171240651a8d093c6a36591bf09ec3670bf848b50181e01fae85e2555841",
    "manual_build.bat": "902890c4ff952e422b22a24358dde7a4b0ee2a2adf8148992592aefaac2949d9",
    "thesis.tex": "57f3c2a865203473bcbe4bf84e9f5a15e72729577d78cd0ae8d3113ed9763cbb",
}
# The faculty's frame: this template has its own version of each, so they are never copied.
FRAME = {p for p in FACULTY if p.startswith("include/") or "/" not in p or p.startswith("lua/")} | {"figures/convert.cmd"}
# Definitions of the unchanged faculty frame that this template does not repeat; a changed frame
# file is searched for the student's own definitions, and these are not the student's.
# amsfonts and amssymb clash with unicode-math, which has their symbols (the lint's preamble rule).
FACULTY_ONLY = {"cmd:lstlistingname", "pkg:amsfonts", "pkg:amssymb"}

# This template's placeholders: a target with one of these digests holds no student text yet.
# A template update that changes one of these files adds its new digest here (the test fails).
PLACEHOLDERS = {
    "content/00-abstract.tex": {"f41d2a396b1e7a7703d7f31177fa5659ea71d0973aec62b6a4c12a8f1eb906f2"},
    "content/01-introduction.tex": {"9ee53360350d047438af378084e0ad5026786bb7ead4a6588c348d45e6932228"},
    "content/02-background.tex": {"1e6114365120171413e792629899b23e7484f8a068f683c6d4f5ae6bd106282a"},
    "content/03-approach.tex": {"e26d8b336d40dfa9841702dbd8448adca1699ac4abbca9894f3055df3fa018c4"},
    "content/04-implementation.tex": {"ca7a4704f2a186612821c8533fd97fa4d8d3d61f3ee9ef989f8cb4aa91802f1e"},
    "content/05-evaluation.tex": {"578832917247092da409dfbe1922b8419d4f2a17296c870b303d63c621052bf9"},
    "content/06-related-work.tex": {"377b282bb89f7b4806d39c1749d8ddb55a2715cc16ae0d05cb75749f08c2fe2a"},
    "content/07-conclusion.tex": {"6b522ef0f85dcc2efa47f018366d7fca98bafa7b1a65e2bd1741add2ea3b3281"},
    "content/08-acknowledgement.tex": {"b6c82ef35c1ee0ab29d51d639a93e9852e5035a140239c8a9bd6e761354c74c3"},
    "content/10-appendices.tex": {"d37a12cf5f3327116f40fcea522c9a04e9b9c74d13e5d6e8128409c8a7323209"},
    "bib/references.bib": {"aa367f4bb8122c640dfbcf888d5997e9921194240436d26d0e077879572fad21"},
    "include/macros.tex": {"fd2b1dfdec86191f8c6560a852672599103f67f6b630bb9880e5d9be02a743c0"},
    "include/tdk-variables.tex": {"b2876ea6f4359eb40a4136dd23b60181a606afe44168caa17082587ceda4eeab"},
}

# Title-page metadata in draft.tex: the template's values, and the faculty's placeholder values,
# which a student who never set them still has and which are therefore not imported.
TEMPLATE_DEFAULTS = {
    "vikszerzoVezeteknev": "Gipsz", "vikszerzoKeresztnev": "Jakab",
    "vikkonzulensAMegszolitas": "", "vikkonzulensAVezeteknev": "Farkas", "vikkonzulensAKeresztnev": "Martin",
    "vikkonzulensBMegszolitas": "Dr.~", "vikkonzulensBVezeteknev": "Kocsis", "vikkonzulensBKeresztnev": "Imre",
    "vikkonzulensCMegszolitas": "", "vikkonzulensCVezeteknev": "", "vikkonzulensCKeresztnev": "",
    "vikcim": "TODO Title of the paper", "viktanszek": r"\bmemit",
    "szerzoMeta": r"\vikszerzoVezeteknev{} \vikszerzoKeresztnev",
}
FACULTY_DEFAULTS = {
    "vikszerzoVezeteknev": "Gipsz", "vikszerzoKeresztnev": "Jakab",
    "vikkonzulensAMegszolitas": "dr.~", "vikkonzulensAVezeteknev": "Konzulens", "vikkonzulensAKeresztnev": "Egy",
    "vikkonzulensBMegszolitas": "", "vikkonzulensBVezeteknev": "Konzulens", "vikkonzulensBKeresztnev": "Kettő",
    "vikkonzulensCMegszolitas": "", "vikkonzulensCVezeteknev": "", "vikkonzulensCKeresztnev": "",
    "vikcim": "Elektronikus terelők", "viktanszek": r"\bmemit",
    "szerzoMeta": r"\vikszerzoVezeteknev{} \vikszerzoKeresztnev",
}
# The template's chapter list in draft.tex, replaced as a whole when it is still unchanged.
TEMPLATE_CHAPTERS = (
    "\\include{content/01-introduction} % the main text starts here; the lint counts its pages from the .toc\n"
    "\\include{content/02-background}\n\\include{content/03-approach}\n\\include{content/04-implementation}\n"
    "\\include{content/05-evaluation}\n\\include{content/06-related-work}\n\\include{content/07-conclusion}\n")
TEMPLATE_BIBLIOGRAPHY = "\\bibliography{bib/references,bib/zotero}"

ROLES = ("intro", "background", "approach", "implementation", "evaluation", "related", "conclusion")
ROLE_NAME = {"intro": "introduction", "background": "background", "approach": "approach",
             "implementation": "implementation", "evaluation": "evaluation",
             "related": "related-work", "conclusion": "conclusion"}
MANDATORY = ("intro", "approach", "evaluation", "related", "conclusion")
# The prefixes of the lint's labels rule (paper/scripts/lint/rules-source.lua).
LABEL_PREFIXES = {"fig", "tab", "lst", "alg", "eq", "def", "thm", "lem", "prop", "cor", "inv", "prty", "claim", "rem",
                  "not", "ex", "ch", "sec", "subsec", "par", "app", "c", "req", "dr", "asm", "g", "thr", "lim", "rq"}
# A suggestion from the chapter title, checked in this order; the student confirms it.
ROLE_WORDS = (
    ("intro", ("bevezet", "introduction")),
    ("conclusion", ("összefoglal", "osszefoglal", "conclusion", "konklúzió", "summary", "kitekintés", "future work")),
    ("related", ("kapcsolódó", "kapcsolodo", "related", "state of the art", "irodalmi áttekintés", "prior work")),
    ("evaluation", ("kiértékel", "értékel", "evaluat", "mérés", "measure", "experiment", "kísérlet", "eredmény", "result", "benchmark", "validáció", "validation")),
    ("implementation", ("implement", "megvalósít", "prototyp", "prototípus")),
    ("background", ("háttér", "background", "előzmény", "elméleti", "preliminar", "alapfogalm", "alapok")),
    ("approach", ("approach", "megközelítés", "módszer", "method", "tervezés", "design", "architekt", "concept", "koncepció", "javasolt")),
)
BUILD_OUTPUT = (".aux", ".log", ".out", ".toc", ".bbl", ".blg", ".lof", ".lot", ".lol", ".thm", ".fls",
                ".fdb_latexmk", ".synctex.gz", ".xdv", ".dvi", ".idx", ".ilg", ".ind", ".bcf", ".run.xml", ".tdo")
JUNK = {".git", "__MACOSX", ".DS_Store", "Thumbs.db"}
# Preamble lines that change the layout the call fixes; the lint's squeeze and frame rules fail on them.
SQUEEZE = re.compile(r"\\(linespread|setstretch|onehalfspacing|doublespacing|marginsize|geometry|enlargethispage|tolerance|"
                     r"setlength\s*\{?\\(parskip|parindent|baselineskip|textheight|textwidth|topmargin|oddsidemargin|evensidemargin|[a-z]*sep|[a-z]*skip))"
                     r"|\\usepackage\s*(\[[^\]]*\])?\s*\{[^}]*\b(geometry|setspace|titlesec|savetrees)\b")
DEFINITION = re.compile(
    r"\\(?P<new>newcommand|providecommand|DeclareMathOperator|DeclareRobustCommand|NewDocumentCommand)\*?\s*\{?\\(?P<cmd>[A-Za-z@]+)"
    r"|\\(?P<renew>renewcommand)\*?\s*\{?\\(?P<rcmd>[A-Za-z@]+)"
    r"|\\def\s*\\(?P<dcmd>[A-Za-z@]+)"
    r"|\\(?:newenvironment|newtheorem|newtcolorbox|NewDocumentEnvironment)\*?\s*(?:\[[^\]]*\])?\s*\{(?P<env>[A-Za-z@*]+)\}"
    r"|\\definecolor\s*\{(?P<color>[^}]+)\}"
    r"|\\lstdefinelanguage\s*(?:\[[^\]]*\])?\s*\{(?P<lang>[^}]+)\}"
    r"|\\usepackage\s*(?:\[[^\]]*\])?\s*\{(?P<pkg>[^}]+)\}")
LIMIT = 200 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strip_comment(line):
    return re.sub(r"(?<!\\)%.*", "", line)


def balanced(text, start):
    """Index of the brace closing the group opened at text[start] == '{'."""
    depth, index = 0, start
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise ValueError("Unbalanced braces")


def active(text):
    """The text with comments blanked, offsets kept."""
    return "\n".join(strip_comment(line).ljust(len(line)) for line in text.split("\n"))


def macro_value(text, name, span=False):
    """The argument of the uncommented \\newcommand{\\name}{...}, or None."""
    code = active(text)
    found = list(re.finditer(r"\\newcommand\{\\" + re.escape(name) + r"\}\{", code))
    if len(found) != 1:
        return None
    start = found[0].end() - 1
    end = balanced(code, start)
    return (start + 1, end) if span else text[start + 1:end]


def safe_name(name):
    name = name.replace("\\", "/") if "\\" in name and "/" not in name else name
    pure = PurePosixPath(name)
    if (not name or "\x00" in name or "\\" in name or pure.is_absolute() or
            any(part in ("..", "") for part in name.split("/")) or ":" in pure.parts[0]):
        raise ValueError("Unsafe path in the faculty paper: " + repr(name))
    return str(pure)


def read_source(path):
    """The files of a faculty-template paper, from a directory or a zip, as {path: bytes}."""
    path = Path(path)
    files, skipped, total = {}, [], 0

    def add(name, data):
        nonlocal total
        total += len(data)
        if total > LIMIT:
            raise ValueError("The faculty paper exceeds 200 MiB")
        files[safe_name(name)] = data

    if path.is_dir():
        for directory, dirnames, filenames in os.walk(path):
            for name in list(dirnames):
                full = Path(directory, name)
                if name in JUNK or full.is_symlink():
                    dirnames.remove(name)
                    if full.is_symlink():
                        skipped.append(full.relative_to(path).as_posix())
            for name in filenames:
                full = Path(directory, name)
                relative = full.relative_to(path).as_posix()
                if name in JUNK:
                    continue
                if full.is_symlink() or not full.is_file():
                    skipped.append(relative)
                    continue
                add(relative, full.read_bytes())
    elif path.is_file() and zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                parts = info.filename.rstrip("/").split("/")
                if info.is_dir() or JUNK.intersection(parts):
                    continue
                if stat.S_ISLNK(info.external_attr >> 16):
                    skipped.append(info.filename)
                    continue
                if total + info.file_size > LIMIT:
                    raise ValueError("The faculty paper exceeds 200 MiB")
                add(info.filename, archive.read(info))
    else:
        raise ValueError("Expected a directory or a .zip of the faculty-template paper: " + str(path))
    # An Overleaf or GitHub download often wraps the project in one folder.
    while files and not any("/" not in p and p.endswith(".tex") and is_main(d) for p, d in files.items()):
        tops = {p.split("/", 1)[0] for p in files}
        if len(tops) != 1 or all("/" not in p for p in files):
            break
        top = tops.pop() + "/"
        files = {p[len(top):]: d for p, d in files.items()}
    return files, skipped


def is_main(data):
    return b"\\documentclass" in data and b"\\begin{document}" in data


def find_main(files):
    candidates = sorted(p for p, d in files.items() if "/" not in p and p.endswith(".tex") and is_main(d))
    if "thesis.tex" in candidates:
        return "thesis.tex"
    if len(candidates) == 1:
        return candidates[0]
    raise ValueError("Cannot tell the main file of the faculty paper; candidates: " + (", ".join(candidates) or "none"))


def text_of(data, path):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(path + " is not UTF-8; save it as UTF-8 first") from None


def statements(text):
    """Preamble text split into statements: lines joined until their braces balance."""
    result, current, depth = [], [], 0
    for line in text.splitlines(True):
        current.append(line)
        code = strip_comment(line).replace("\\{", "").replace("\\}", "")
        depth += code.count("{") - code.count("}")
        if depth <= 0:
            result.append("".join(current))
            current, depth = [], 0
    if current:
        result.append("".join(current))
    return result


def definitions(text):
    """The commands, environments, colours and packages a piece of TeX defines or loads."""
    found = set()
    for match in DEFINITION.finditer(active(text)):
        if match["cmd"] or match["dcmd"]:
            found.add("cmd:" + (match["cmd"] or match["dcmd"]))
        elif match["env"]:
            found.add("env:" + match["env"])
        elif match["color"]:
            found.add("color:" + match["color"].strip())
        elif match["lang"]:
            found.add("lang:" + match["lang"].strip())
        elif match["pkg"]:
            found.update("pkg:" + p.strip() for p in match["pkg"].split(",") if p.strip())
    return found


def template_definitions(paper):
    """What the template's frame defines; macros.tex is the student's, so a rerun finds the same suggestions."""
    found = set()
    for path in sorted((paper / "include").glob("*.tex")) + [paper / "draft.tex"]:
        if path.name != "macros.tex":
            found |= definitions(path.read_text(encoding="utf-8"))
    return found


def slug(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-") or "chapter"


def chapter_title(text):
    code = active(text)
    match = re.search(r"\\chapter\s*(\[[^\]]*\])?\s*\{", code)
    if not match:
        return None, None
    end = balanced(code, match.end() - 1)
    return text[match.end():end], end + 1


def suggest(title):
    words = re.sub(r"\\bevezetes\b", "bevezetés", title or "").lower()
    for role, needles in ROLE_WORDS:
        if any(n in words for n in needles):
            return role
    return None


def plan(source, paper, labels=None, accept=False):
    """Everything the import would do, computed without writing."""
    labels = dict(labels or {})
    files, skipped = read_source(source)
    main = find_main(files)
    main_text = text_of(files[main], main)
    begin = main_text.find("\\begin{document}")
    preamble, body = main_text[:begin], main_text[begin:]
    report = {"source": str(source), "main": main, "writes": [], "conflicts": [], "labels": [],
              "suggestions": [], "metadata": [], "notes": [], "lint": [], "skipped": sorted(skipped),
              "left_out": [], "chapters": []}
    handled = {main}
    language = "hu" if re.search(r"^[^%\n]*\\input\{include/thesis-hu\}", preamble, re.M) else "en"
    report["language"] = language
    if language == "hu":
        report["notes"].append("The paper is Hungarian (include/thesis-hu). This template builds English papers: headings, "
                               "captions and hyphenation will be English. Decide the paper's language with your advisors before importing.")
    options = re.search(r"^[^%\n]*\\documentclass\[([^\]]*)\]", preamble, re.M)
    if options and "12pt" not in options[1]:
        report["notes"].append("The faculty paper uses \\documentclass[" + options[1] + "]; the TDK call asks for 12 pt, which draft.tex keeps.")

    # The body: which file plays which part, in reading order.
    parts, zone = [], "front"
    for match in re.finditer(r"\\(include|input|bibliography|pagenumbering|appendix)\b(?:\s*\{([^}]*)\})?", active(body)):
        command, argument = match[1], (match[2] or "").strip()
        if command == "pagenumbering" and argument == "arabic":
            zone = "main"
        elif command in ("bibliography", "appendix"):
            zone = "back"
            if command == "bibliography":
                report["bibliography"] = [b.strip() for b in argument.split(",") if b.strip()]
        elif command in ("include", "input") and argument:
            parts.append((zone, argument if argument.endswith(".tex") else argument + ".tex"))

    mapped = {}  # source -> (target, kind, data)
    chapters = []
    for zone, path in parts:
        if path in FRAME or path.startswith("include/titlepage") or path in ("include/guideline.tex", "include/project.tex"):
            handled.add(path)
            if path.startswith("include/titlepage") and path != "include/titlepage-tdk.tex":
                report["notes"].append("The faculty paper uses " + path + "; draft.tex keeps the TDK title page (include/titlepage-tdk). "
                                       "For the OTDK, switch the \\include in draft.tex.")
            if path == "include/declaration.tex":
                report["notes"].append("Not imported: the thesis declaration (include/declaration.tex). The TDK has none; "
                                       "the AI declaration is content/09-ai-declaration.tex.")
            continue
        if path not in files:
            report["notes"].append("The faculty main file includes " + path + ", which is not in the source.")
            continue
        handled.add(path)
        data = files[path]
        if FACULTY.get(path) == sha(data):
            report["left_out"].append(path + " (the faculty template's sample text)")
            continue
        text = text_of(data, path)
        code = active(text)
        if re.search(r"\\chapter\*\s*\{(Abstract|Kivonat)\}", code) and "content/00-abstract.tex" not in {t for t, *_ in mapped.values()}:
            mapped[path] = ("content/00-abstract.tex", "abstract", data)
        elif "\\appendix" in code and "content/10-appendices.tex" not in {t for t, *_ in mapped.values()}:
            if "\\printlists" not in code:
                report["suggestions"].append(("printlists", path))
                if accept:
                    first = re.search(r"^\\section", text, re.M)
                    at = first.start() if first else len(text)
                    insert = "% Abbreviations, notation and terms are appendix material; only used entries print.\n\\printlists\n\n"
                    data = (text[:at] + insert + text[at:]).encode("utf-8")
            mapped[path] = ("content/10-appendices.tex", "appendices", data)
        elif re.search(r"\\chapter\*\s*\{\s*(\\koszonetnyilvanitas|K\u00f6sz\u00f6netnyilv\u00e1n\u00edt\u00e1s|Acknowledge?ments?)\s*\}", code):
            mapped[path] = ("content/08-acknowledgement.tex", "acknowledgement", data)
        elif zone == "main":
            chapters.append((path, text))
        else:
            mapped[path] = (path if path.startswith("content/") else "content/" + path.rsplit("/", 1)[-1], "other", data)
            report["notes"].append(path + " stands outside the main text in the faculty paper; it is copied but not "
                                   "included. Include it in draft.tex where it belongs.")

    # Chapters: role, label and the NN-name.tex the lint's frame rule expects, in reading order.
    used, labelled = {}, set()
    for number, (path, text) in enumerate(chapters, 1):
        if path not in files:
            continue
        title, after = chapter_title(text)
        code = active(text)
        existing = re.findall(r"\\label\{ch:([a-z]+)(?::[^}]*)?\}", code)
        existing = [r for r in existing if r in ROLES]
        suggestion = suggest(title)
        explicit = labels.pop(path, None)
        if explicit is not None and explicit != "none" and explicit not in ROLES:
            raise ValueError("Unknown role " + explicit + "; use one of " + ", ".join(ROLES) + " or none")
        role, confirmed = None, False
        if existing:
            role, confirmed = existing[0], True
            labelled.add(role)
        elif explicit and explicit != "none":
            role, confirmed = explicit, True
        elif suggestion and explicit != "none":
            role, confirmed = suggestion, accept
        data = files[path]
        if role and not existing and title is not None:
            label = "ch:" + role if role not in labelled else "ch:" + role + ":" + slug(PurePosixPath(path).stem)
            labelled.add(role)
            entry = {"source": path, "title": title.strip(), "label": label, "applied": confirmed,
                     "basis": "your --label" if explicit else "the chapter title"}
            report["labels"].append(entry)
            if confirmed:
                data = (text[:after] + "\\label{" + label + "}" + text[after:]).encode("utf-8")
        elif title is None:
            report["notes"].append(path + " has no numbered \\chapter; the lint counts main-text chapters by \\chapter.")
        if confirmed and role and role not in used:
            name = ROLE_NAME[role]
            used[role] = path
        else:
            name = slug(PurePosixPath(path).stem)
        target = "content/%02d-%s.tex" % (number, name)
        mapped[path] = (target, "chapter", data)
        report["chapters"].append({"source": path, "target": target, "role": role if confirmed else None,
                                   "suggested": None if confirmed else role})
    if labels:
        raise ValueError("--label names files that are not chapters of the main text: " + ", ".join(sorted(labels)))
    if len(chapters) > 7:
        report["notes"].append("More than seven chapters: their numbers reach the back matter's 08-10; renumber "
                               "08-acknowledgement, 09-ai-declaration and 10-appendices after the last chapter.")

    # Bibliography: the first .bib becomes bib/references.bib, the others keep their names.
    extra_bib = []
    for index, name in enumerate(report.get("bibliography", [])):
        path = name if name.endswith(".bib") else name + ".bib"
        if path not in files:
            report["notes"].append("\\bibliography names " + path + ", which is not in the source.")
            continue
        handled.add(path)
        if FACULTY.get(path) == sha(files[path]):
            report["left_out"].append(path + " (the faculty template's sample entries)")
            continue
        target = "bib/references.bib" if index == 0 else "bib/" + path.rsplit("/", 1)[-1]
        mapped[path] = (target, "bibliography", files[path])
        if index:
            extra_bib.append(target[:-4])
    if re.search(r"^[^%\n]*\\(addbibresource|printbibliography)\b", main_text, re.M):
        report["notes"].append("The faculty paper uses biblatex; this template uses BibTeX with natbib. Its .bib files are "
                               "copied with their paths: add them to \\bibliography in draft.tex and replace "
                               "biblatex-only commands such as \\textcite or \\autocite.")
    if re.search(r"^[^%\n]*\\bibliographystyle\{", main_text, re.M) or language == "hu":
        report["notes"].append("The bibliography style is this template's tdkieee (IEEE, numbered), not the faculty's "
                               "plainnat or huplain; \\cite, \\citet and \\citep keep working.")

    # title-page variables
    tdk_variables = files.get("include/tdk-variables.tex")
    handled.add("include/tdk-variables.tex")
    if tdk_variables is not None and sha(tdk_variables) != FACULTY["include/tdk-variables.tex"]:
        mapped["include/tdk-variables.tex"] = ("include/tdk-variables.tex", "title page", tdk_variables)

    # Preamble: the student's own definitions, carried to include/macros.tex when confirmed.
    ours = template_definitions(paper)
    carried = []
    frame_statement = re.compile(r"\\documentclass|\\input\{include/(packages|tdk-variables|thesis-en|thesis-hu|preamble)\}"
                                 r"|\\newcommand\{\\(vik[A-Za-z]+|szerzoMeta)\}")
    for statement in statements(preamble):
        code = strip_comment(statement)
        if not code.strip() or frame_statement.search(code):
            continue
        defined = definitions(statement)
        if SQUEEZE.search(active(statement)):
            report["notes"].append("Not carried from " + main + ": " + code.strip() + " (it changes the layout the call fixes).")
        elif defined and defined <= ours | FACULTY_ONLY and not re.search(r"\\renewcommand", code):
            report["notes"].append("Not carried from " + main + ": " + code.strip() + " (this template has it already).")
        else:
            carried.append((main, statement))
    for path, data in sorted(files.items()):
        if path in FRAME and path.startswith("include/") and path.endswith(".tex") and FACULTY.get(path) != sha(data) \
                and path != "include/tdk-variables.tex":
            handled.add(path)
            text = text_of(data, path)
            new = [s for s in statements(text) if (definitions(s) - ours - FACULTY_ONLY) and not SQUEEZE.search(active(s))]
            carried += [(path, s) for s in new]
            report["notes"].append("You changed the faculty's " + path + "; this template replaces it. "
                                   + ("Its definitions this template lacks are among those suggested for include/macros.tex. " if new else "")
                                   + "Compare it with the faculty original for other changes.")
    if carried:
        block, last = "", None
        for path, statement in carried:
            if path != last:
                block += ("\n" if last else "") + "% Carried over from the faculty paper's " + path + "\n"
                last = path
            block += statement.rstrip("\n") + "\n"
        report["suggestions"].append(("macros", block))

    # Every other file of the student keeps its path; the faculty's own files are left out.
    for path, data in sorted(files.items()):
        if path in handled or path in mapped:
            continue
        lower = path.lower()
        if lower.endswith(BUILD_OUTPUT) or path == PurePosixPath(main).stem + ".pdf":
            report["left_out"].append(path + " (build output)")
        elif path in FACULTY and (path in FRAME or FACULTY[path] == sha(data)):
            if path not in FRAME:
                report["left_out"].append(path + " (the faculty template's sample)")
        elif path in FRAME:
            report["left_out"].append(path + " (changed faculty frame; this template has its own)")
        elif "/" not in path:
            report["left_out"].append(path + " (top-level file; move it by hand if the paper needs it)")
        elif path.startswith(("guide/", "scripts/", "docs/")):
            report["left_out"].append(path + " (this template's own folder; move it by hand)")
        else:
            mapped[path] = (path, "file", data)

    # Writes, each checked against what is in paper/ now.
    targets = {}
    for path, (target, kind, data) in mapped.items():
        if target in targets:
            report["conflicts"].append(target + ": both " + targets[target] + " and " + path + " would go here")
            continue
        targets[target] = path
        destination = paper / target
        current = destination.read_bytes() if destination.is_file() else None
        if destination.is_symlink() or (destination.exists() and not destination.is_file()):
            report["conflicts"].append(target + ": not a regular file")
            continue
        if current == data:
            action = "unchanged"
        elif current is None:
            action = "create"
        elif sha(current) in PLACEHOLDERS.get(target, ()) or current == skeleton(paper, target):
            action = "replace template placeholder"
        else:
            report["conflicts"].append(target + ": already holds your text; not overwritten (from " + path + ")")
            continue
        exact = data == files.get(path)
        report["writes"].append({"source": path, "target": target, "kind": kind, "action": action, "data": data,
                                 "before": None if current is None else sha(current), "exact": exact})

    accept_suggestion(report, paper, accept)
    draft_changes(report, paper, main_text, extra_bib)
    lint_forecast(report)
    return report


def skeleton(paper, target):
    path = paper / "scripts/lint/skeleton" / PurePosixPath(target).name
    return path.read_bytes() if target.startswith("content/") and path.is_file() else None


def accept_suggestion(report, paper, accept):
    for kind, value in report["suggestions"]:
        if kind == "macros" and accept:
            target = paper / "include/macros.tex"
            current = target.read_bytes()
            if value.encode("utf-8") in current:
                report["macros_done"] = True
                continue
            if sha(current) not in PLACEHOLDERS["include/macros.tex"]:
                report["notes"].append("include/macros.tex already holds your own definitions, so the suggested ones were "
                                       "not appended; add those you need by hand.")
                continue
            data = current + b"\n" + value.encode("utf-8")
            report["writes"].append({"source": "preamble", "target": "include/macros.tex", "kind": "macros",
                                     "action": "append the suggested definitions", "data": data, "before": sha(current), "exact": False})


def draft_changes(report, paper, main_text, extra_bib):
    path = paper / "draft.tex"
    before = path.read_text(encoding="utf-8")
    after = before
    for macro, default in TEMPLATE_DEFAULTS.items():
        wanted = macro_value(main_text, macro)
        if wanted is None or wanted == FACULTY_DEFAULTS.get(macro):
            continue
        span = macro_value(after, macro, span=True)
        if span is None:
            report["metadata"].append((macro, wanted, "draft.tex has no \\" + macro + "; set it by hand"))
            continue
        current = after[span[0]:span[1]]
        if current == wanted:
            continue
        if current != default:
            report["metadata"].append((macro, wanted, "kept draft.tex's " + current + "; set it by hand if the faculty paper's is right"))
            continue
        after = after[:span[0]] + wanted + after[span[1]:]
        report["metadata"].append((macro, wanted, "set"))
    chapters = [c["target"][:-4] for c in report["chapters"]]
    if chapters:
        lines = "".join("\\include{%s}%s\n" % (c, " % the main text starts here; the lint counts its pages from the .toc" if i == 0 else "")
                        for i, c in enumerate(chapters))
        if lines in after:
            pass  # an earlier import already wrote this list
        elif TEMPLATE_CHAPTERS in after:
            after = after.replace(TEMPLATE_CHAPTERS, lines, 1)
            written = {w["target"] for w in report["writes"]}
            left = [p for p in sorted(PLACEHOLDERS) if re.match(r"content/0[1-7]-", p) and p not in written and (paper / p).is_file()]
            if left:
                report["lint"].append("orphans (advice): the template skeletons " + ", ".join(left) + " are no longer in the "
                                      "chapter list. Include one when you write that chapter, or delete it.")
        else:
            report["notes"].append("draft.tex's chapter list is no longer the template's; replace it by hand with:\n" + lines.rstrip())
    if extra_bib:
        wanted = "\\bibliography{bib/references," + ",".join(extra_bib) + ",bib/zotero}"
        if TEMPLATE_BIBLIOGRAPHY in after:
            after = after.replace(TEMPLATE_BIBLIOGRAPHY, wanted, 1)
        else:
            report["notes"].append("Add " + ", ".join(extra_bib) + " to \\bibliography in draft.tex by hand.")
    if after != before:
        report["writes"].append({"source": report["main"], "target": "draft.tex", "kind": "metadata and chapter list",
                                 "action": "edit", "data": after.encode("utf-8"), "before": sha(before.encode("utf-8")), "exact": False})
        report["draft_diff"] = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                            "draft.tex", "draft.tex", n=0))


def lint_forecast(report):
    roles = {c["role"] for c in report["chapters"] if c["role"]}
    missing = [r for r in MANDATORY if r not in roles]
    if missing:
        report["lint"].append("roles/frame: no chapter carries ch:" + ", ch:".join(missing)
                              + "; the frame rule stops there and the roles rule fails from the draft phase.")
    text = b"".join(w["data"] for w in report["writes"] if w["target"].startswith("content/"))
    text = active(text.decode("utf-8", "replace"))
    counts = {
        "crefs: \\autoref or a bare \\ref (the template uses \\cref)": len(re.findall(r"\\autoref\{|\\ref\{", text)),
        "markers: typed TODO, TBD or XXX (use \\tbd{...})": len(re.findall(r"\b(TODO|TBD|XXX)\b", text)),
        "labels: a label prefix the lint does not know, such as chap: (it wants ch:, sec:, fig:, tab:, ...)": len(
            [p for p in re.findall(r"\\label\{([^:}]*):", text) if p not in LABEL_PREFIXES]),
        "acronyms: no \\gls, so every abbreviation is typed by hand": 0 if "\\gls" in text else 1,
    }
    for message, count in counts.items():
        if count:
            report["lint"].append(message + ("" if message.startswith("acronyms") else ": %d" % count))
    report["lint"].append("essentials: the tagged lists (requirements, contributions, threats, ...) and the running example "
                          "the lint measures are not in a paper written elsewhere; they come due by phase (guide:writing:essentials).")


def render(report, dry_run):
    out = ["Faculty-template import from " + report["source"] + " (main file " + report["main"] + ", "
           + ("Hungarian" if report["language"] == "hu" else "English") + ")",
           "Analysed against " + FACULTY_SOURCE["url"] + " (" + FACULTY_SOURCE["version"] + ")", ""]
    out.append("Files" + (" that would be written" if dry_run else " written") + " under paper/:")
    for write in sorted(report["writes"], key=lambda w: w["target"]):
        how = "byte-identical" if write["exact"] else "changed as listed"
        out.append("  %-34s <- %-30s %s, %s" % (write["target"], write["source"], write["action"], how))
    if not report["writes"]:
        out.append("  (none)")
    if report["chapters"]:
        out += ["", "Chapters in reading order:"]
        for c in report["chapters"]:
            out.append("  %-30s -> %-30s %s" % (c["source"], c["target"],
                       "role " + c["role"] if c["role"] else ("suggested role " + c["suggested"] if c["suggested"] else "no role yet")))
    pending = [l for l in report["labels"] if not l["applied"]]
    applied = [l for l in report["labels"] if l["applied"]]
    if applied:
        out += ["", "Labels added after \\chapter{...} (you confirmed them):"]
        out += ["  %s: \\label{%s}  (%s)" % (l["source"], l["label"], l["title"]) for l in applied]
    if pending:
        out += ["", "Labels to confirm (not added; confirm one with --label SOURCE=ROLE, all with --accept-suggestions, refuse with --label SOURCE=none):"]
        out += ["  %s: \\label{%s}  from the title \"%s\"" % (l["source"], l["label"], l["title"]) for l in pending]
    for kind, value in report["suggestions"]:
        if kind == "printlists":
            out += ["", "Suggested for " + value + " (the appendix): \\printlists before its first \\section, which prints "
                    "the abbreviation, notation and term lists. " + ("Added." if any(w["source"] == value and not w["exact"] for w in report["writes"]) else "Confirm with --accept-suggestions.")]
        if kind == "macros":
            done = report.get("macros_done") or any(w["target"] == "include/macros.tex" for w in report["writes"])
            out += ["", "Your preamble definitions, suggested for include/macros.tex"
                    + (" (appended):" if done else " (confirm with --accept-suggestions):")]
            out += ["  " + line for line in value.rstrip("\n").split("\n")]
    if report["metadata"]:
        out += ["", "Title-page metadata in draft.tex:"]
        out += ["  \\%s = {%s}: %s" % (m, v, s) for m, v, s in report["metadata"]]
    if report.get("draft_diff"):
        out += ["", "The change to draft.tex (title-page values and the chapter list only):"]
        out += ["  " + line for line in report["draft_diff"].rstrip("\n").split("\n")]
    if report["conflicts"]:
        out += ["", "Refused (nothing is written while any of these stand):"] + ["  " + c for c in report["conflicts"]]
    if report["left_out"]:
        out += ["", "Left out:"] + ["  " + p for p in report["left_out"]]
    if report["skipped"]:
        out += ["", "Skipped (symlinks or special files):"] + ["  " + p for p in report["skipped"]]
    if report["notes"]:
        out += ["", "Review by hand:"] + ["  - " + n.replace("\n", "\n    ") for n in report["notes"]]
    out += ["", "What the lint will flag after the import:"] + ["  - " + l for l in report["lint"]]
    out += ["", "Your prose is copied unchanged; rewriting it to the template's conventions (\\cref, \\gls, \\tbd) is yours to do."]
    if dry_run:
        out.append("Dry run: nothing was written.")
    return "\n".join(out) + "\n"


def apply(report, paper):
    if report["conflicts"]:
        raise ValueError("Import refused; resolve the listed conflicts first. Nothing was written.")
    # Recheck every target before the first write, so an edit made since planning stops all of them.
    for write in report["writes"]:
        destination = paper / write["target"]
        current = sha(destination.read_bytes()) if destination.is_file() else None
        if current != write["before"]:
            raise ValueError(write["target"] + " changed during the import; nothing was written")
    for write in report["writes"]:
        if write["action"] == "unchanged":
            continue
        destination = paper / write["target"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(dir=destination.parent, prefix=".import-")
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(write["data"])
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(name, destination.stat().st_mode & 0o777 if destination.exists() else 0o644)
            os.replace(name, destination)
        finally:
            if os.path.exists(name):
                os.unlink(name)
