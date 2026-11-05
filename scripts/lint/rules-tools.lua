-- Rules that wrap the tools TeX Live and the CI container provide: chktex, lacheck, texcount,
-- checkcites, the BibTeX log, aspell. All report; none is a gate, because each has its noise.
local C = require("lintcore")
local rule, fail, warn, note = C.rule, C.fail, C.warn, C.note

rule("chktex", "tools", "advice", "always", "chktex: typographic slips in the sources (dashes, quotes, spacing before citations, \\ldots, maths in text)", function()
  if not C.have("chktex") then C.skip("chktex not installed"); return end
  local n = 0
  -- off: 1 command terminated with space, 3 \( \) advice, 8 dash length, 13 \@ after a capital, 24 space before \label (the template puts it on its own line), 36 brace spacing, 44 user regex, 46 \( \).
  -- 6 italic correction: \\textit and \\emph add it themselves, and \\itshape in a table head needs none.
  -- Also off, because the typography rule reports the same slip once, with a fix: 2 a tie before
  -- \cite (\cref needs none), 11 three dots, 12 the space after e.g. and et al., 18 straight quotes,
  -- 26 a space before punctuation. 38 punctuation before a quote is right in Hungarian (,,...''),
  -- and 39 a double space prints as one
  local out = C.run("chktex -q -I0 -n1 -n2 -n3 -n6 -n8 -n11 -n12 -n13 -n18 -n24 -n26 -n36 -n38 -n39 -n44 -n46 -f '%f:%l:%n:%m\n' " .. table.concat(C.MAIN, " ") .. " " .. (C.FILES.abstract or "")) or ""
  for l in out:gmatch("[^\n]+") do
    local f, ln, code, msg = l:match("^([^:]+):(%d+):(%d+):(.*)$")
    if f then n = n + 1; if n <= 60 then warn(f, tonumber(ln), string.format("chktex %s: %s", code, msg)) end end
  end
  return string.format("findings=%d", n)
end)

rule("lacheck", "tools", "advice", "always", "lacheck: unmatched braces and environments, missing \\@ after capitals, punctuation inside maths", function()
  if not C.have("lacheck") then C.skip("lacheck not installed"); return end
  local n = 0
  for _, f in ipairs(C.MAIN) do
    -- lacheck reads a listing as LaTeX, and one odd $ (Tamarin's $N) cascades to the end of the
    -- file: it gets the file with the code blanked, on the same line numbers
    local text = C.readfile(f) or ""
    for _, env in ipairs(C.CODE) do
      local e = env:gsub("%p", "%%%0")
      text = text:gsub("(\\begin{" .. e .. "})(.-)(\\end{" .. e .. "})", function(a, body, z) return a .. body:gsub("[^\n]", "") .. z end)
    end
    local tmp = os.tmpname()
    local h = io.open(tmp, "w")
    h:write(text); h:close()
    local out = C.run("lacheck " .. tmp) or ""
    os.remove(tmp)
    for l in out:gmatch("[^\n]+") do
      local file, ln, msg = l:match('^"([^"]+)", line (%d+): (.*)$')
      if file == tmp then file = f end
      -- what typography reports with a fix, or what is not a slip: a tie before \ref (crefs asks for
      -- \cref, which needs none), a double space (it prints as one), a space before punctuation, and
      -- "possible unwanted space at {", which fires on TikZ and pgfplots options
      if file and (msg:match('before "\\ref') or msg:match("^double space") or msg:match("^Whitespace before punctation") or msg:match("^possible unwanted space")) then file = nil end
      if file then n = n + 1; if n <= 60 then warn(file, tonumber(ln), "lacheck: " .. msg) end end
    end
  end
  return string.format("findings=%d", n)
end)

rule("words", "tools", "count", "polish", "texcount: words per chapter and in the abstract; there are no per-chapter budgets, this is for seeing where the paper is", function()
  if not C.have("texcount") then C.skip("texcount not installed"); return end
  local parts, total = {}, 0
  for _, f in ipairs(C.MAIN) do
    local out = C.run_quiet("texcount -q -1 -sum " .. f) or ""
    local w = tonumber(out:match("^%s*(%d+)")) or 0
    total = total + w
    local name = f:match("([^/]+)%.tex$") or f
    parts[#parts + 1] = (name:match("^%d%d%-(.+)$") or name) .. "=" .. w
  end
  -- the English abstract: the text after \chapter*{Abstract}, with the todo and the bracketed placeholders removed
  local abs = C.readfile(C.FILES.abstract or "content/00-abstract.tex") or ""
  local eng = abs:match("\\chapter%*{Abstract}(.*)$") or ""
  eng = eng:gsub("\\todo%b[]%b{}", ""):gsub("\\todo%b{}", ""):gsub("%%[^\n]*", ""):gsub("\\vfill.*$", "")
  local placeholders = C.count(eng, "%[%d ")
  local words = 0
  for _ in C.prose(eng):gmatch("%a[%a%-']+") do words = words + 1 end
  if placeholders > 0 then warn(C.FILES.abstract, nil, placeholders .. " of the seven placeholders of the abstract are still there")
  elseif words < 150 then warn(C.FILES.abstract, nil, string.format("the abstract is %d words: too short to say the problem, the approach and the result", words)) end
  return string.format("main=%d abstract=%d %s", total, words, table.concat(parts, " "))
end)

rule("checkcites", "tools", "count", "always", "checkcites: bibliography entries never cited (your reading list that has not reached the paper) and citations with no entry", function()
  if not C.have("checkcites") then C.skip("checkcites not installed"); return end
  local aux = C.bpath(C.opts.doc .. ".aux")
  if not C.exists(aux) then warn(nil, nil, "no " .. aux .. ": build first"); return end
  local out = C.run("checkcites --backend bibtex " .. aux) or ""
  -- guide: keys are the guide's citations; guide/guide.bbl resolves them, so the paper's BibTeX
  -- run, which reads the guide's .aux files of the draft build, finds no entry for them
  local unused, undefined, mode = 0, 0, nil
  for l in out:gmatch("[^\n]+") do
    if l:match("Unused references") then mode = "unused" elseif l:match("Undefined references") then mode = "undefined" end
    local key = l:match("^%s*=>%s*(%S+)")
    if key and not key:match("^guide:") then
      if mode == "unused" then unused = unused + 1; if unused <= 40 then note(nil, nil, "not cited: " .. key) end
      elseif mode == "undefined" then undefined = undefined + 1; warn(nil, nil, "cited but not in any .bib: " .. key) end
    end
  end
  return string.format("unused=%d undefined=%d", unused, undefined)
end)

rule("bibtex-log", "tools", "count", "always", "the BibTeX log: empty fields and other warnings BibTeX prints while building the bibliography", function()
  local blg = C.bpath(C.opts.doc .. ".blg")
  if not C.exists(blg) then warn(nil, nil, "no " .. blg .. ": build first"); return end
  local n = 0
  for _, l in ipairs(C.lines(blg)) do
    local msg = l:match("^Warning%-%-(.*)$")
    -- the guide's citations, as in checkcites
    if msg and not msg:match("entry for \"guide:") then n = n + 1; if n <= 40 then warn(nil, nil, "bibtex: " .. msg) end end
  end
  return string.format("warnings=%d", n)
end)

rule("spelling", "tools", "advice", "always", "aspell on the detexed chapters: unknown words, and whether British and American spellings are mixed", function()
  if not (C.have("aspell") and C.have("detex")) then C.skip("aspell or detex not installed"); return end
  local dicts = C.run("aspell dump dicts 2>/dev/null") or ""
  local have_gb, have_us = dicts:match("%f[%w]en_GB%f[%W]") ~= nil, dicts:match("%f[%w]en_US%f[%W]") ~= nil
  if not (have_gb or have_us) then C.skip("no English aspell dictionary"); return end
  -- the project's own words, one per line; aspell's personal lists need a header line, so the
  -- words are dropped from its output here instead
  local personal = {}
  for w in (C.readfile("scripts/words.txt") or ""):gmatch("[^%s]+") do personal[w] = true end
  -- the prose only: todos, beats, pictures, code and maths removed, and the arguments that are not
  -- words (labels, references, citations, glossary keys, file names), written to a file for detex
  local tmp = os.tmpname()
  do
    local h = io.open(tmp, "w")
    for _, f in ipairs(C.MAIN) do h:write(C.prose(table.concat(C.prose_lines(f), "\n")), "\n") end
    -- the title and the English abstract, which the reviewer reads first
    local title = (C.readfile("thesis.tex") or ""):match("\\newcommand{\\vikcim}{([^}]*)}")
    if title then h:write(C.prose(title), "\n") end
    local abs = C.FILES.abstract and (C.readfile(C.FILES.abstract) or ""):match("\\chapter%*{Abstract}(.*)$")
    if abs then h:write(C.prose(table.concat((function() local t = {}; for l in abs:gmatch("[^\n]*") do t[#t + 1] = C.strip_comment(l) end; return t end)(), "\n")), "\n") end
    h:close()
  end
  local function unknown(dict)
    local out = C.run("detex " .. tmp .. " | tr -c \"[:alpha:]'\" '\\n' | grep -E \"^[A-Za-z][a-z']{3,}$\" | aspell -d " .. dict .. " list | sort | uniq -c | sort -rn") or ""
    local t, order = {}, {}
    for l in out:gmatch("[^\n]+") do local c, w = l:match("^%s*(%d+)%s+(%S+)"); if w and not personal[w] then t[w] = tonumber(c); order[#order + 1] = w end end
    return t, order
  end
  local gb, gborder = {}, {}; local us, usorder = {}, {}
  if have_gb then gb, gborder = unknown("en_GB") end
  if have_us then us, usorder = unknown("en_US") end
  local american, british = {}, {}
  if have_gb and have_us then
    -- names (capitalised) are not spellings
    for w in pairs(gb) do if not us[w] and not w:match("^%u") then american[#american + 1] = w end end
    for w in pairs(us) do if not gb[w] and not w:match("^%u") then british[#british + 1] = w end end
    table.sort(american); table.sort(british)
    if #american >= 3 and #british >= 3 then
      note(nil, nil, string.format("words only one dictionary knows: American %s; British %s (the terms rule checks the known pairs)", table.concat(american, ", ", 1, math.min(8, #american)), table.concat(british, ", ", 1, math.min(8, #british))))
    end
  end
  local both, order = gb, gborder
  if have_gb and have_us then both = {}; order = {}; for w, c in pairs(gb) do if us[w] then both[w] = c; order[#order + 1] = w end end; table.sort(order, function(a, b) if both[a] ~= both[b] then return both[a] > both[b] end; return a < b end) end
  local shown = 0
  for _, w in ipairs(order) do
    if not w:match("^%u") then shown = shown + 1; if shown <= 40 then note(nil, nil, string.format("unknown word (%d): %s", both[w], w)) end end
  end
  os.remove(tmp)
  return string.format("unknown=%d american=%d british=%d (add project words to scripts/words.txt)", #order, #american, #british)
end)

-- the words of a text, lower case, for comparing the portal's copy with the source: LaTeX
-- commands, comments, notes and punctuation go, accented letters stay
local function words_of(text)
  text = text:gsub("\\%%", "%%"):gsub("%%[^\n]*", "")
  -- soft hyphens and zero-width spaces the portal's copy carries from a PDF or a word processor
  text = text:gsub("\194\173", ""):gsub("\226\128\139", "")
  text = text:gsub("\\begin{comment}.-\\end{comment}", " "):gsub("\\iffalse.-\\fi", " ")
  text = text:gsub("\\addcontentsline%s*%b{}%s*%b{}%s*%b{}", " ")
  text = text:gsub("\\todo%s*%b[]%s*%b{}", " "):gsub("\\todo%s*%b{}", " ")
  text = text:gsub("\\%a+%*?", " "):gsub("[{}%[%]~]", " ")
  local w = {}
  for x in text:lower():gmatch("[%w\128-\255]+") do w[#w + 1] = x end
  return w
end
-- the portal's copy: often pasted from a PDF, with words hyphenated across its lines
local function portal_words(text) return words_of((text or ""):gsub("([^%s%-])%-%s*\n%s*([^%s])", "%1%2")) end
-- how alike two word lists are: 2 * longest common subsequence / total length, 1 when equal
local function likeness(a, b)
  if #a == 0 and #b == 0 then return 1 end
  local prev = {}
  for j = 0, #b do prev[j] = 0 end
  for i = 1, #a do
    local cur = { [0] = 0 }
    for j = 1, #b do cur[j] = a[i] == b[j] and prev[j - 1] + 1 or math.max(prev[j], cur[j - 1]) end
    prev = cur
  end
  return 2 * prev[#b] / (#a + #b)
end
-- up to n words of a that b lacks, in a's order
local function missing(a, b, n)
  local have, out = {}, {}
  for _, x in ipairs(b) do have[x] = (have[x] or 0) + 1 end
  for _, x in ipairs(a) do
    if (have[x] or 0) > 0 then have[x] = have[x] - 1 elseif #out < n then out[#out + 1] = x end
  end
  return table.concat(out, " ")
end
local function fetch_json(url)
  local body = C.run(string.format("curl -sS -f -L --max-time 30 -A 'tdk-lint' %q", url))
  if not body or body == "" then return nil end
  return C.json_decode(body)
end

-- 0.95: the portal holds plain text and the source LaTeX, so a glossary macro, a dash or a quote
-- may differ; a changed sentence does not pass
local PORTAL_ALIKE = 0.95
rule("portal", "tools", "check", "always", "once the abstract is submitted to the TDK portal, the paper's title, English abstract and Hungarian Kivonat match the portal's copy; skipped offline or before the portal has the paper", function()
  if os.getenv("LINT_OFFLINE") or not C.have("curl") then C.skip("offline"); return end
  local last, first, title = C.setting("vikszerzoVezeteknev"), C.setting("vikszerzoKeresztnev"), C.setting("vikcim")
  if not (last and first and title) or last == "Gipsz" or title:match("TODO") then C.skip("no author or title in thesis.tex yet"); return end
  local vars = C.readfile("include/tdk-variables.tex") or ""
  local year = vars:match("\\newcommand{\\tdkev}{(%d%d%d%d)}") or (os.getenv("LINT_DATE") or os.date("%Y-%m-%d")):sub(1, 4)
  local list = fetch_json("https://tdk.bme.hu/api/conference/VIK/" .. year .. "/Paper")
  if type(list) ~= "table" then C.skip("the portal's paper list for " .. year .. " did not load"); return end
  -- the author's papers: the surname, and every given name the paper's title page uses
  local mine = {}
  for _, p in ipairs(list) do
    for _, a in ipairs(p.paperAuthors or {}) do
      local ok = (a.lastName or "") == last
      for g in first:gmatch("%S+") do if not (a.firstName or ""):find(g, 1, true) then ok = false end end
      if ok and not p.isDeleted then mine[#mine + 1] = p end
    end
  end
  if #mine == 0 then C.skip(string.format("no %d paper of %s %s on the portal yet", tonumber(year), last, first)); return end
  -- with two papers (a companion), the one whose title is closest
  local tw, best, bestscore = words_of(title), nil, -1
  for _, p in ipairs(mine) do
    local sc = math.max(likeness(tw, words_of(p.title or "")), likeness(tw, words_of(p.titleEn or "")))
    if sc > bestscore then best, bestscore = p, sc end
  end
  local rec = fetch_json("https://tdk.bme.hu/api/conference/VIK/" .. year .. "/Paper/" .. best.slug)
  if type(rec) ~= "table" then C.skip("the portal record " .. best.slug .. " did not load"); return end
  local where = "https://tdk.bme.hu" .. (rec.detailsUrl or "")
  if bestscore < PORTAL_ALIKE then
    fail("thesis.tex", nil, string.format("the title differs from the portal's (%s): %q", where, rec.titleEn ~= "" and rec.titleEn or rec.title), "the submitted title is fixed: \\vikcim must be the portal's English title")
  elseif likeness(tw, words_of(rec.titleEn or "")) < likeness(tw, words_of(rec.title or "")) then
    note("thesis.tex", nil, "the portal has the English title in its Hungarian title field and the other way round", "ask the TDK office to swap them, if the portal still allows it")
  end
  local abs = C.FILES.abstract or "content/00-abstract.tex"
  local src = C.readfile(abs) or ""
  local hu = src:match("\\chapter%*{Kivonat}(.-)\\selectenglish") or src:match("\\chapter%*{Kivonat}(.-)\\chapter") or ""
  local en = src:match("\\chapter%*{Abstract}(.*)$") or ""
  -- each abstract against the closer of the portal's two fields: a student may have typed either
  -- into the other, as with the title
  local fields = { portal_words(rec.abstractEn), portal_words(rec.abstract) }
  for _, part in ipairs({ { "English abstract", en, 1 }, { "Kivonat", hu, 2 } }) do
    local a = words_of(part[2])
    local b, sc = fields[part[3]], likeness(a, fields[part[3]])
    local other = likeness(a, fields[3 - part[3]])
    if other > sc then b, sc = fields[3 - part[3]], other end
    if #b > 0 then
      if sc < PORTAL_ALIKE then
        local lack, extra = missing(b, a, 8), missing(a, b, 8)
        fail(abs, nil, string.format("the %s is %.0f%% like the portal's (%s)%s%s", part[1], 100 * sc, where,
          lack ~= "" and "; the paper lacks: " .. lack or "", extra ~= "" and "; the portal lacks: " .. extra or ""),
          "the submitted abstract is fixed: copy the portal's text into " .. abs)
      end
    end
  end
  return string.format("record=%s title=%.2f", best.slug, bestscore)
end)

rule("zenodo", "tools", "check", "always", "every cited Zenodo record is cited by its concept DOI, which opens the newest version, with the results tag named beside it; a version DOI fails; skipped offline", function()
  if os.getenv("LINT_OFFLINE") or not C.have("curl") then C.skip("offline"); return end
  local bib, seen, n = C.bib_entries(), {}, 0
  local files = {}
  for _, f in ipairs(C.CONTENT) do files[#files + 1] = f end
  C.each_cite(files, function(f, line, key)
    local e = bib[key]
    local id = e and e.body:lower():match("10%.5281/zenodo%.(%d+)")
    if not id or seen[id] then return end
    seen[id] = true; n = n + 1
    local rec = C.json_decode(C.run(string.format("curl -sS -f -L --max-time 20 -A 'tdk-lint' %q", "https://zenodo.org/api/records/" .. id)) or "")
    if type(rec) ~= "table" or not rec.conceptrecid then note(e.file, nil, "Zenodo record " .. id .. " (" .. key .. ") did not load; not checked"); return end
    if tostring(rec.conceptrecid) ~= id then
      fail(e.file, nil, string.format("%s cites the version DOI 10.5281/zenodo.%s", key, id),
        string.format("cite the concept DOI 10.5281/zenodo.%s, which opens the newest version, and name the results tag beside it", tostring(rec.conceptrecid)))
    end
  end)
  return string.format("records=%d", n)
end)

rule("links", "tools", "advice", "always", "every \\url and \\href answers over the network; skipped when LINT_OFFLINE is set", function()
  if os.getenv("LINT_OFFLINE") or not C.have("curl") then C.skip("offline"); return end
  local urls, seen = {}, {}
  C.each_line(C.MAIN, function(f, n, l)
    for u in l:gmatch("\\url{([^}]*)}") do if not seen[u] then seen[u] = true; urls[#urls + 1] = { u = u, f = f, n = n } end end
    for u in l:gmatch("\\href{([^}]*)}") do if not seen[u] then seen[u] = true; urls[#urls + 1] = { u = u, f = f, n = n } end end
  end)
  local bad = 0
  for i, e in ipairs(urls) do
    if i > 60 then break end
    if e.u:match("^https?://") and not e.u:match("TODO") then
      local code = C.trim(C.run(string.format("curl -sS -o /dev/null -L --max-time 15 -A 'tdk-lint' -w '%%{http_code}' %q", (e.u:gsub("\\%%", "%%"):gsub("\\#", "#")))) or "000")
      if not code:match("^[23]%d%d$") and code ~= "405" then bad = bad + 1; warn(e.f, e.n, string.format("link answered %s: %s", code, e.u)) end
    end
  end
  return string.format("checked=%d broken=%d", math.min(#urls, 60), bad)
end)

-- tracked files no paper needs: build output (the CI publishes the PDFs as artifacts) and the
-- personal settings of an AI coding agent. git exists in CI and in a clone, not on Overleaf
local BUILD_OUTPUT = { "aux", "bbl", "blg", "fdb_latexmk", "fls", "lof", "lol", "lot", "out", "synctex.gz", "tdo", "thm", "toc", "xdv" }
rule("repo-hygiene", "tools", "check", "always", "the repository tracks no build output (aux, log, thesis.pdf, reviewer.pdf, minted caches, ...) and no personal agent settings", function()
  if not C.exists(".git") or not C.have("git") then C.skip("not a git checkout"); return end
  if not (C.run("git rev-parse --is-inside-work-tree 2>/dev/null") or ""):match("true") then C.skip("git cannot read this checkout"); return end
  local n = 0
  for f in (C.run_quiet("git ls-files") or ""):gmatch("[^\n]+") do
    local why
    for _, ext in ipairs(BUILD_OUTPUT) do if f:sub(-#ext - 1) == "." .. ext and f ~= "guide/guide.bbl" then why = "build output" end end
    if f:match("%.log$") or f == "thesis.pdf" or f == "reviewer.pdf" or f == "lint-checks.tex" or f:match("^_minted") or f:match("^_[^/]*%.data%.minted$") or f:match("^svg%-inkscape/") then why = "build output" end
    if f:match("^%.claude/settings%.local%.json$") then why = "personal settings of an AI coding agent" end
    if why then
      -- a command, so the fix is shown and never written
      local q = f:match("^[%w%._/%-]+$") and f or "'" .. f:gsub("'", "'\\''") .. "'"
      n = n + 1; fail(f, nil, why .. " is tracked", "git rm --cached it (the .gitignore keeps it out afterwards)", C.fix("review", "stop tracking it", C.command("git rm --cached " .. q)))
    end
  end
  return string.format("tracked=%d", n)
end)
