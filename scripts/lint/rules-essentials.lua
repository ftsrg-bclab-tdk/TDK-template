-- The essentials rule. Every row of scripts/lint/essentials.lua is found in the paper, by its
-- label first and then by a heading, and placed on a five-level ladder:
--   ○ missing, ◔ placeholder (only TODO or the template's own text), ◑ started (own text, not
--   enough yet), ◕ written, ● written and used where the argument needs it.
-- A row with no "used" condition is ● once written. The phase asks every row for a level
-- (topic to plan ◔, draft ◑, polish and submit ●), and a row below it fails. The rows, with their level,
-- place and next step, stay in C.ESSENTIALS for the Checks page, the job summary and --json.
local C = require("lintcore")
local T = require("texscan")
local ROWS = require("essentials")
local fail, warn, note = C.fail, C.warn, C.note

local M = {}
M.ROWS = ROWS
M.GLYPH = { [0] = "○", "◔", "◑", "◕", "●" }
M.LEVEL_NAME = { [0] = "missing", "placeholder", "started", "written", "used" }
M.TARGET = { 1, 2, 4, 4 } -- by the phase's level: topic to plan, draft, polish, submit
M.ROLE_ORDER = { "front", "intro", "approach", "evaluation", "related", "conclusion" }
M.ROLE_TITLE = { front = "Front matter", intro = "Introduction", approach = "Approach", evaluation = "Evaluation", related = "Related work", conclusion = "Conclusion" }
M.ROLE_SHORT = { front = "front", intro = "intro", approach = "approach", evaluation = "evaluation", related = "related", conclusion = "concl." }
M.EXAMPLE_WORDS = 10 -- own words that make the introduction's example box written
C.ESS = M

function M.target() return M.TARGET[C.level()] end

-- lines, comment-stripped, and prose lines, read once per file
local raw_cache, prose_cache = {}, {}
local function lines(f)
  if not raw_cache[f] then
    local t = {}
    for i, l in ipairs(C.lines(f)) do t[i] = C.strip_comment(l) end
    raw_cache[f] = t
  end
  return raw_cache[f]
end
local function plines(f) prose_cache[f] = prose_cache[f] or C.prose_lines(f); return prose_cache[f] end

-- headings and spans ----------------------------------------------------------------------
local HLEVEL = { chapter = 0, section = 1, subsection = 2, subsubsection = 3, paragraph = 4 }
M.HLEVEL = HLEVEL
local function heading(l)
  for cmd, arg in l:gmatch("\\(%a+)%*?%s*(%b{})") do
    if HLEVEL[cmd] then return cmd, arg:sub(2, -2) end
  end
end
local function strip_headings(l)
  return (l:gsub("\\(%a+)%*?%s*(%b{})", function(cmd) if HLEVEL[cmd] then return " " end end))
end
-- the last line before the next heading at level lvl or above, after line n
local function span_end(f, n, lvl)
  local ls = lines(f)
  for m = n + 1, #ls do
    local cmd = heading(ls[m])
    if cmd and HLEVEL[cmd] <= lvl then return m - 1 end
  end
  return #ls
end
-- the line of the heading at level lvl or above that line n sits under
local function span_start(f, n, lvl)
  local ls = lines(f)
  for m = n, 1, -1 do
    local cmd = heading(ls[m])
    if cmd and HLEVEL[cmd] <= lvl then return m end
  end
  return 1
end
-- where an element sits, for the next step and for work/essentials-labels.py: its first and last
-- line, and the paragraph and section around it
local function place(f, first, last)
  return { file = f, line = first, last = last,
    para_start = span_start(f, first, 4), para_end = span_end(f, last, 4),
    sec_start = span_start(f, first, 1), sec_end = span_end(f, last, 1) }
end

-- text that is not the row's own: floats, tagged lists and the example's boxes have rows of their own
local SKIPENV = { figure = true, ["figure*"] = true, table = true, ["table*"] = true, sidewaysfigure = true, sidewaystable = true, wrapfigure = true,
  requirements = true, derivedrequirements = true, contributions = true, assumptions = true, guarantees = true, threats = true, limitations = true, rqlist = true }
local function span_words(f, a, b)
  local ls, ps, box = lines(f), plines(f), C.example_box()
  local depth, n = 0, 0
  for i = a, b do
    local l = ls[i] or ""
    local opens, closes = 0, 0
    for e in l:gmatch("\\begin{([%a%*]+)}") do if SKIPENV[e] or e == box then opens = opens + 1 end end
    for e in l:gmatch("\\end{([%a%*]+)}") do if SKIPENV[e] or e == box then closes = closes + 1 end end
    if depth == 0 and opens == 0 then n = n + C.own_words(strip_headings(ps[i] or "")) end
    depth = math.max(0, depth + opens - closes)
  end
  return n
end

-- references in the prose (notes and beats do not count) ----------------------------------
local function refs_in_span(f, a, b, pattern)
  local ps, n = plines(f), 0
  for i = a, b do
    for keys in (ps[i] or ""):gmatch("\\[Cc]?ref%*?{([^}]*)}") do
      for key in keys:gmatch("[^,%s]+") do if key:match(pattern) then n = n + 1 end end
    end
  end
  return n
end
local function refs_in_files(files, pattern)
  local n = 0
  for _, f in ipairs(files) do n = n + refs_in_span(f, 1, #plines(f), pattern) end
  return n
end
local function exact(key) return "^" .. C.escape(key) .. "$" end
local function role_refs(role, key) return refs_in_files(C.role_files(role), exact(key)) end
local function main_refs(key) return refs_in_files(C.main_chapters(), exact(key)) end
local function labels_in_span(f, a, b)
  local out, ls = {}, lines(f)
  for i = a, b do for key in (ls[i] or ""):gmatch("\\label{([^}]*)}") do out[#out + 1] = key end end
  return out
end

-- text rows ------------------------------------------------------------------------------
local function find_text(row)
  local files = C.role_files(row.role)
  for _, f in ipairs(files) do
    local ls = lines(f)
    for n, l in ipairs(ls) do
      for key in l:gmatch("\\label{([^}]*)}") do
        local pre, suf = key:match("^(%a+):(.+)$")
        if suf == row.key and (pre == "par" or pre == "sec" or pre == "subsec") then
          for m = n, math.max(1, n - 2), -1 do
            local cmd = heading(ls[m])
            if cmd and cmd ~= "chapter" then return { file = f, line = m, cmd = cmd, via = "label", label = key } end
          end
          return { file = f, line = n, cmd = pre == "par" and "paragraph" or "section", via = "label", label = key }
        end
      end
    end
  end
  for _, f in ipairs(files) do
    for n, l in ipairs(lines(f)) do
      local cmd, title = heading(l)
      if cmd and cmd ~= "chapter" then
        local t = title:lower()
        for _, h in ipairs(row.headings or {}) do
          if t:find(h, 1, true) then return { file = f, line = n, cmd = cmd, via = "heading" } end
        end
      end
    end
  end
end

-- the canonical label for a row found by its heading: par: on a paragraph, sec: otherwise
function M.label_for(row, cmd) return (cmd == "paragraph" and "par:" or "sec:") .. row.key end

-- the first cited entry of the files whose doi or url field is a Zenodo record (10.5281/zenodo.N),
-- the archive the template's code repository releases to, and whose type is an artifact's (@software,
-- @dataset, @misc, @online): a paper with a Zenodo DOI, or a DOI mentioned only in a note, is not the
-- artifact. Whether the record is this paper's code, and the version the results came from, the
-- lint cannot tell; the reader checks that. Returns the key, or nil and why the nearest miss fails
local ARTIFACT_TYPES = { software = true, dataset = true, misc = true, online = true, electronic = true, www = true, data = true }
-- Split only at field-level commas, respecting nested braces, quotes and escapes. Text such
-- as "url = {...}" inside a note is a value, never another field. BibTeX string expansion is
-- not attempted: a DOI assembled using @string macros still needs human inspection.
local function artifact_fields(body)
  local fields, pos = {}, (body:find(",", 1, true) or #body) + 1
  body = body:sub(1, -2) -- C.bib_entries includes the entry's outer braces
  while pos <= #body do
    pos = body:match("^[%s,]*()", pos)
    local _, e, name = body:find("^([%a][%w_]*)%s*=%s*", pos)
    local start = e and e + 1 or pos
    local i, depth, quoted = start, 0, false
    while i <= #body do
      local c = body:sub(i, i)
      if c == "\\" then i = i + 2
      elseif c == '"' and depth == 0 then quoted = not quoted; i = i + 1
      elseif c == "{" then depth = depth + 1; i = i + 1
      elseif c == "}" then depth = depth - 1; i = i + 1
      elseif c == "," and depth == 0 and not quoted then break
      else i = i + 1 end
    end
    if name then fields[name:lower()] = body:sub(start, i - 1) end
    pos = i + 1
  end
  return fields
end
local function zenodo_in(fields, field)
  local v = fields[field]
  return v and v:lower():match("10%.5281/zenodo%.%d+")
end
local function cited_artifact(files)
  local bib, found, why = C.bib_entries(), nil, nil
  C.each_cite(files, function(_, _, key)
    local e = bib[key]
    if found or not e then return end
    local fields = artifact_fields(e.body)
    local doi = zenodo_in(fields, "doi") or zenodo_in(fields, "url")
    if not doi then return end
    if ARTIFACT_TYPES[e.type] then found = key
    else why = why or string.format("%s is an @%s entry with a Zenodo DOI, a publication rather than the artifact: cite the artifact's own record (@software or @misc)", key, e.type) end
  end)
  return found, why
end

local TEXT_USED = {
  introgap = function(f, a, b)
    if refs_in_span(f, a, b, "^ch:related") + refs_in_span(f, a, b, "^tab:related$") + refs_in_span(f, a, b, "^fig:positioning$") > 0 then return true end
    return false, "point to the full comparison: \\cref{ch:related}, \\cref{tab:related} or \\cref{fig:positioning}"
  end,
  setup = function()
    local key, why = cited_artifact(C.role_files("evaluation"))
    if key then return true, "Zenodo record found: the reader must check that it is this paper's own artifact and the version used for the results" end
    return false, why or "cite the archived artifact in the evaluation: a bibliography entry with its Zenodo DOI, 10.5281/zenodo.<number>; the reader must check artifact identity and the version used for the results"
  end,
  scalability = function(f, a, b)
    for _, key in ipairs(labels_in_span(f, a, b)) do if (key:match("^fig:") or key:match("^tab:")) and main_refs(key) > 0 then return true end end
    return false, "show the measurements in a figure or table, and reference it"
  end,
  gap = function(f, a, b)
    if refs_in_span(f, a, b, "^tab:related$") > 0 then return true end
    return false, "base the gap on the gap matrix: reference \\cref{tab:related}"
  end,
  summary = function(f, a, b)
    for _, p in ipairs({ "^ch:evaluation", "^rq:", "^fig:", "^tab:", "^thm:" }) do if refs_in_span(f, a, b, p) > 0 then return true end end
    return false, "restate each contribution with the evaluation result behind it (\\cref a result)"
  end,
}
TEXT_USED.robustness = TEXT_USED.scalability

local function eval_text(row, r)
  local found = find_text(row)
  if not found then return 0, row.add end
  local lvl = HLEVEL[found.cmd] or 1
  local last = span_end(found.file, found.line, lvl)
  r.where = place(found.file, found.line, last)
  r.via, r.cmd, r.label = found.via, found.cmd, found.label or M.label_for(row, found.cmd)
  local w = span_words(found.file, found.line, last)
  r.words = w
  if w == 0 then return 1, "only TODO or the template's text so far: write it" end
  if w < row.words then return 2, string.format("%d own words; it counts as written from %d", w, row.words) end
  local used = TEXT_USED[row.id]
  if not used then return 4 end
  local ok, why = used(found.file, found.line, last)
  if ok then return 4, why end
  return 3, why
end

-- tagged lists ---------------------------------------------------------------------------
-- every label with the prefix in the main chapters, in reading order, with its item's text
-- Requirement membership comes from printed list items or explicit \tagrow{requirements}
-- items, not arbitrary req: labels. Retain one record per printed item, even when its
-- identity is missing or ambiguous. Keep source lines for the essentials interface.
local function requirement_items()
  local items = {}
  for _, f in ipairs(C.main_chapters()) do
    local text = table.concat(C.printed_lines(f), "\n")
    local pos, envs, current = 1, {}, nil
    local function row_end(start)
      local i, depth = start, 0
      while i <= #text do
        local c = text:sub(i, i)
        if c == "\\" then
          if text:sub(i + 1, i + 1) == "\\" and depth == 0 then return i end
          local cmd = text:match("^\\%a+", i)
          i = i + (cmd and #cmd or 2)
        elseif c == "{" then depth = depth + 1; i = i + 1
        elseif c == "}" then depth = depth - 1; i = i + 1
        else i = i + 1 end
      end
      return #text + 1
    end
    local function finish(stop)
      if current then
        current.text = text:sub(current.start, stop - 1)
        current.stop = 1 + C.count(text:sub(1, stop - 1), "\n")
        items[#items + 1] = { labels = current.labels, file = f,
          line = 1 + C.count(text:sub(1, current.start - 1), "\n"),
          text = current.text, stop = current.stop }
        current = nil
      end
    end
    while pos <= #text do
      local a, b, cmd = text:find("\\([%a]+)", pos)
      local rowend = current and current.rowend
      -- tagrow's scope is its table row; a list item's scope ends at the next item/end.
      if current and current.row and rowend and (not a or rowend < a) then
        finish(rowend); pos = rowend + 2
      elseif not a then break
      else
        pos = b + 1
        local argpos = text:match("^%s*()", pos)
        local arg = text:match("^%b{}", argpos)
        local name = arg and arg:sub(2, -2)
        if cmd == "begin" and name then
          envs[#envs + 1] = name; pos = argpos + #arg
        elseif cmd == "end" and name then
          if name == "requirements" then finish(a) end
          envs[#envs] = nil; pos = argpos + #arg
        elseif cmd == "item" and envs[#envs] == "requirements" then
          finish(a)
          current = { start = a, labels = {} }
        elseif cmd == "tagrow" and name == "requirements" then
          finish(a)
          current = { start = a, labels = {}, row = true, rowend = row_end(a), envdepth = #envs }
          pos = argpos + #arg
        elseif cmd == "label" and current and name and name:match("^req:")
            and ((not current.row and envs[#envs] == "requirements") or (current.row and #envs == current.envdepth)) then
          current.labels[#current.labels + 1] = { key = name, line = 1 + C.count(text:sub(1, a - 1), "\n") }
          pos = argpos + #arg
        end
      end
    end
    finish(#text + 1)
  end
  local counts = {}
  for _, it in ipairs(items) do
    for _, label in ipairs(it.labels) do counts[label.key] = (counts[label.key] or 0) + 1 end
  end
  for _, it in ipairs(items) do
    local where = string.format("requirement item at %s:%d", it.file, it.line)
    if #it.labels == 0 then
      it.identity_problem = where .. " has no req: label: give every printed requirement exactly one usable, unique identity"
    elseif #it.labels ~= 1 then
      it.identity_problem = where .. " has multiple req: labels: give it exactly one usable, unique identity"
    else
      local key = it.labels[1].key
      if not key:match("^req:.+") or key:find("[%s{},\\]") then
        it.identity_problem = where .. " has an unusable req: label: use a nonempty literal requirement key without spaces, commas, braces or commands"
      else
        it.key = key
        if counts[key] > 1 then it.identity_problem = key .. " is duplicated across printed requirement labels: give each item a unique identity" end
      end
    end
  end
  return items
end
local function tag_items(prefix)
  if prefix == "req" then return requirement_items() end
  local items = {}
  for _, f in ipairs(C.main_chapters()) do
    local ls = lines(f)
    for n, l in ipairs(ls) do
      local s = l:find("\\label{" .. prefix .. ":", 1, true)
      if s then
        local key = l:match("\\label{([^}]*)}", s)
        local t = { l:sub(s) }
        for m = n + 1, math.min(#ls, n + 15) do
          if ls[m]:match("\\item") or ls[m]:match("\\end{") then break end
          t[#t + 1] = ls[m]
        end
        local stop = n
        for m = n, math.min(#ls, n + 300) do if ls[m]:match("\\end{") then stop = m; break end end
        items[#items + 1] = { key = key, file = f, line = n, text = table.concat(t, " "), stop = stop }
      end
    end
  end
  return items
end
local function own_item(it)
  if it.text:match("TODO") then return false end
  if C.skeleton_lines()[C.prose_key(plines(it.file)[it.line] or "")] then return false end
  local n = 0
  for _ in C.prose(it.text):gmatch("%a%a+") do n = n + 1 end
  return n >= 2
end
local function each_unreferenced(items, role, what, miss)
  for _, it in ipairs(items) do if it.key and role_refs(role, it.key) == 0 then miss[#miss + 1] = it.key .. " " .. what end end
end
local TAG_USED = {
  req = function(items, miss)
    for _, it in ipairs(items) do if it.identity_problem then miss[#miss + 1] = it.identity_problem end end
    each_unreferenced(items, "related", "is not in the related work", miss)
    each_unreferenced(items, "evaluation", "is not checked in the evaluation", miss)
    each_unreferenced(tag_items("dr"), "evaluation", "is not checked in the evaluation", miss)
  end,
  c = function(items, miss)
    for _, it in ipairs(items) do if not it.text:match("\\[cC]ref{ch:") then miss[#miss + 1] = it.key .. " points to no chapter" end end
    each_unreferenced(items, "conclusion", "is not restated in the conclusion", miss)
  end,
  thr = function(items, miss) each_unreferenced(items, "approach", "is not met in the approach", miss) end,
  asm = function(items, miss) each_unreferenced(items, "approach", "is used by no guarantee or proof", miss) end,
  g = function(items, miss) each_unreferenced(items, "evaluation", "is not checked in the evaluation", miss) end,
  rq = function(items, miss) each_unreferenced(items, "evaluation", "is not answered in the evaluation", miss) end,
}
local function first_of(list, n)
  local out = {}
  for i = 1, math.min(n, #list) do out[i] = list[i] end
  local s = table.concat(out, "; ")
  if #list > n then s = s .. string.format("; and %d more", #list - n) end
  return s
end

local function eval_tags(row, r)
  local items = tag_items(row.prefix)
  if #items == 0 then return 0, row.add end
  r.where = place(items[1].file, items[1].line, items[1].stop)
  local own = 0
  for _, it in ipairs(items) do if own_item(it) then own = own + 1 end end
  r.items, r.own = #items, own
  if own == 0 then return 1, string.format("%d item%s, all TODO or the template's text: write them", #items, #items == 1 and "" or "s") end
  if own < #items then return 2, string.format("%d of %d items written; the rest are TODO or the template's text", own, #items) end
  local used = TAG_USED[row.prefix]
  if not used then return 4 end
  local miss = {}
  used(items, miss)
  if #miss == 0 then return 4 end
  return 3, first_of(miss, 2)
end

-- floats ---------------------------------------------------------------------------------
local FLOATENV = { figure = true, ["figure*"] = true, table = true, ["table*"] = true, sidewaysfigure = true, sidewaystable = true, wrapfigure = true }
local function find_float(files, key)
  for _, f in ipairs(files) do
    local ls = lines(f)
    for n, l in ipairs(ls) do
      if l:find("\\label{" .. key .. "}", 1, true) then
        local b, env = n, nil
        for m = n, math.max(1, n - 400), -1 do
          for e in ls[m]:gmatch("\\begin{([%a%*]+)}") do if FLOATENV[e] then env = e end end
          if env then b = m; break end
        end
        local e = n
        if env then for m = n, #ls do if ls[m]:find("\\end{" .. env .. "}", 1, true) then e = m; break end end end
        local block = table.concat(ls, "\n", b, e)
        return { file = f, line = b, last = e, block = block }
      end
    end
  end
end
local function captions(block)
  local out, i = {}, 1
  while true do
    local s, e = block:find("\\caption%s*", i)
    if not s then break end
    local j = e + 1
    local opt = block:match("^%b[]", j)
    if opt then j = j + #opt end
    j = j + #(block:match("^%s*", j))
    local arg = block:match("^%b{}", j)
    if arg then out[#out + 1] = { from = s, to = j + #arg - 1, text = arg:sub(2, -2) }; i = j + #arg else i = e + 1 end
  end
  return out
end
local function float_parts(fl, key)
  local caps = captions(fl.block)
  local at = fl.block:find("\\label{" .. key .. "}", 1, true) or 1
  local main
  for _, c in ipairs(caps) do if not main or math.abs(c.from - at) < math.abs(main.from - at) then main = c end end
  local body = fl.block
  for i = #caps, 1, -1 do body = body:sub(1, caps[i].from - 1) .. " " .. body:sub(caps[i].to + 1) end
  body = body:gsub("\\label%b{}", " "):gsub("%s+", " ")
  return C.trim(body), main and main.text or ""
end

local FLOAT_USED = {
  correctness = function(fl)
    if main_refs("tab:correctness") == 0 then return false, "reference the table from the text" end
    local inblock = {}
    for keys in fl.block:gmatch("\\[Cc]?ref%*?{([^}]*)}") do for k in keys:gmatch("[^,%s]+") do inblock[k] = true end end
    local miss = {}
    for _, it in ipairs(tag_items("g")) do if not inblock[it.key] then miss[#miss + 1] = it.key .. " has no row" end end
    if #miss == 0 then return true end
    return false, first_of(miss, 2)
  end,
  gapmatrix = function()
    local fails = M.gapmatrix()
    if #fails == 0 then return true, "the reader must check that each cited result is sufficient to support its matrix claim" end
    return false, first_of(fails, 1)
  end,
}

local function eval_float(row, r)
  local fl = find_float(C.main_chapters(), row.label)
  if not fl then return 0, row.add end
  r.where = place(fl.file, fl.line, fl.last)
  local body, cap = float_parts(fl, row.label)
  local sk = find_float(C.skeleton_files(), row.label)
  local skbody = sk and float_parts(sk, row.label)
  if body:match("[Pp]laceholder") or (skbody and skbody == body) then return 1, "still the template's placeholder: make it your own" end
  local words = 0
  for _ in C.prose(cap):gmatch("%a%a+") do words = words + 1 end
  if body:match("TODO") then return 2, "the figure or table still holds TODO" end
  if cap:match("TODO") then return 2, "the caption is still a TODO" end
  if words < 6 or not C.trim(cap):match("%.$") then return 2, "the caption is shorter than a sentence: say what the reader should see" end
  local used = FLOAT_USED[row.id]
  local ok, why
  if used then ok, why = used(fl) else ok = main_refs(row.label) > 0; why = "reference it from the text: \\cref{" .. row.label .. "}" end
  if ok then return 4, used and why or nil end
  return 3, why
end

-- Labels inside printed theorem-like result environments, independent of their prefix.
-- Use the shared command reader so escaped commands, literal code, notes and link addresses
-- cannot open a result environment. Read all content, including appendix results.
local RESULT_ENV = { theorem = true, lemma = true, proposition = true, corollary = true,
  invariant = true, property = true, claim = true }
local function theorem_labels()
  local out, stacks = {}, {}
  C.each_call(C.CONTENT, function(cmd) return cmd == "begin" or cmd == "end" or cmd == "label" end,
    function(f, n, cmd, key, start)
      local stack = stacks[f] or {}; stacks[f] = stack
      if cmd == "begin" then stack[#stack + 1] = key
      elseif cmd == "end" and stack[#stack] == key then stack[#stack] = nil
      elseif cmd == "label" and RESULT_ENV[stack[#stack]] then
        out[key] = { file = f, line = n, start = start }
      end
    end)
  return out
end

-- The gap matrix: one row per requirement, each exactly once; this work reports a status with
-- a pointer to a result, or justifies why the requirement is not applicable. Returns the failures;
-- warnings go out as the rule's own findings. Whether a pointed-at result shows what the cell
-- claims is for the reader to judge.
-- Read a literal alignment rather than physical source lines. Braced cells (makecell,
-- shortstack, etc.) and nested environments own their separators. Macro-generated rows,
-- merged cells and TeX alignment primitives cannot be checked reliably without TeX expansion.
local ALIGNMENT = { tabular = 1, ["tabular*"] = 2, tabularx = 2, longtable = 1 }
local function matrix_rows(block)
  local a, b, env = block:find("\\begin%s*{(tabular%*?)}")
  local xa, xb, xe = block:find("\\begin%s*{(tabularx)}")
  if xa and (not a or xa < a) then a, b, env = xa, xb, xe end
  local la, lb, le = block:find("\\begin%s*{(longtable)}")
  if la and (not a or la < a) then a, b, env = la, lb, le end
  if not a then return nil, "the gap matrix has no supported tabular (tabular, tabular*, tabularx or longtable)" end
  local pos = block:match("^%s*()", b + 1)
  local opt = block:match("^%b[]", pos)
  if opt then pos = block:match("^%s*()", pos + #opt) end
  for _ = 1, ALIGNMENT[env] do
    local arg = block:match("^%b{}", pos)
    if not arg then return nil, "cannot read the gap matrix's literal alignment arguments; review the matrix manually" end
    pos = block:match("^%s*()", pos + #arg)
  end
  local last = block:find("\\end{" .. env .. "}", pos, true)
  if not last then return nil, "the gap matrix's alignment has no matching end; review it manually" end
  local text = block:sub(pos, last - 1)
  if text:match("\\tabularnewline%f[^%a]") then
    return nil, "cannot check \\tabularnewline row terminators in the gap matrix; use literal \\\\ or review it manually"
  end
  if text:match("\\multicolumn%f[^%a]") or text:match("\\multirow%f[^%a]") or text:match("\\input%f[^%a]")
      or text:match("\\[oO]mit%f[^%a]") or text:match("\\span%f[^%a]") or text:match("\\cr%f[^%a]") then
    return nil, "cannot check merged cells, external rows or TeX alignment primitives in the gap matrix; use literal cells or review it manually"
  end
  local rows, cells, start, depth, nested, i = {}, {}, 1, 0, 0, 1
  while i <= #text do
    local c = text:sub(i, i)
    if c == "\\" then
      local cmd = text:match("^\\(%a+)", i)
      if cmd == "begin" or cmd == "end" then
        local _, e = text:find("^\\%a+%s*%b{}", i)
        if e then nested = nested + (cmd == "begin" and 1 or -1); i = e + 1
        else return nil, "cannot read a nested environment in the gap matrix; review it manually" end
      elseif text:sub(i + 1, i + 1) == "\\" and depth == 0 and nested == 0 then
        cells[#cells + 1] = C.trim(text:sub(start, i - 1))
        rows[#rows + 1] = cells; cells = {}
        i = i + 2
        if text:sub(i, i) == "*" then i = i + 1 end
        local sp = text:match("^%s*()", i)
        local gap = text:match("^%b[]", sp)
        if gap then i = sp + #gap end
        start = i
      else i = i + (cmd and #cmd + 1 or 2) end
    elseif c == "{" then depth = depth + 1; i = i + 1
    elseif c == "}" then depth = depth - 1; i = i + 1
    elseif c == "&" and depth == 0 and nested == 0 then
      cells[#cells + 1] = C.trim(text:sub(start, i - 1)); i = i + 1; start = i
    else i = i + 1 end
    if depth < 0 or nested < 0 then return nil, "unbalanced groups or environments in the gap matrix; review it manually" end
  end
  if depth ~= 0 or nested ~= 0 then return nil, "unbalanced groups or environments in the gap matrix; review it manually" end
  -- TeX permits the final row without \\; keep it, but ignore trailing \bottomrule, etc.
  local tail = C.trim(text:sub(start))
  if #cells > 0 or tail:match("\\ref%s*{req:") then cells[#cells + 1] = tail; rows[#rows + 1] = cells end
  return rows
end
M.gapwarn = {}
-- Read cell commands as TeX tokens, skipping addresses and reference arguments. A literal
-- \\cref or a command written inside a URL cannot supply a status or an evidence pointer.
local function cell_commands(text, fn)
  local pos = 1
  while pos <= #text do
    if text:sub(pos, pos) ~= "\\" then pos = pos + 1
    else
      local cmd, after = T.command(text, pos)
      pos = after
      local bare = cmd:gsub("%*$", "")
      if T.LINK[bare] or bare == "path" then
        local _, e
        if bare == "url" or bare == "path" or bare == "nolinkurl" then _, e = T.address(text, after)
        else _, e = T.argument(text, after, true) end
        if e then pos = e + 1 end
      elseif bare == "ref" or bare == "cref" or bare == "Cref" then
        local arg, e = T.argument(text, after)
        if e then fn(bare, arg); pos = e + 1 end
      else fn(cmd) end
    end
  end
end
function M.gapmatrix()
  local fails = {}
  M.gapwarn = {}
  local fl = find_float(C.main_chapters(), "tab:related")
  if not fl then return { "no gap matrix table labelled tab:related" } end
  fl.block = table.concat(C.printed_lines(fl.file), "\n", fl.line, fl.last)
  local parsed, problem = matrix_rows(fl.block)
  if not parsed then return { problem } end
  local rows, ncols, seen = {}, nil, {}
  for _, cells in ipairs(parsed) do
    local req = cells[1]:match("\\ref%s*{(req:[^}]*)}")
    if req then
      rows[#rows + 1] = cells; ncols = ncols or #cells
      if #cells ~= ncols then fails[#fails + 1] = "gap matrix rows have different numbers of cells" end
      if seen[req] then fails[#fails + 1] = req .. " has two rows in the gap matrix" end
      seen[req] = true
    elseif table.concat(cells, " "):match("\\ref%s*{req:") then
      fails[#fails + 1] = "a gap matrix requirement reference is outside the first cell; review that row manually"
    end
  end
  if #rows == 0 then return { "the gap matrix has no rows starting with \\ref{req:...}" } end
  local declared = {}
  for _, it in ipairs(tag_items("req")) do
    if it.identity_problem then fails[#fails + 1] = it.identity_problem end
    if it.key then
      declared[it.key] = true
      if not seen[it.key] then fails[#fails + 1] = it.key .. " has no row in the gap matrix" end
    end
  end
  for req in pairs(seen) do
    if not declared[req] then fails[#fails + 1] = req .. " is a row of the gap matrix but no requirement carries that label" end
  end
  -- Index only printed labels, including appendices. Theorem evidence comes from its
  -- environment; figure/table prefixes and evaluation sections remain source heuristics.
  local labels = {}
  C.each_call(C.CONTENT, function(cmd) return cmd == "label" end, function(f, n, _, key, start)
    labels[key] = { file = f, line = n, start = start }
  end)
  local theorems = theorem_labels()
  local evalfile, heuristic = {}, {}
  for _, f in ipairs(C.role_files("evaluation")) do evalfile[f] = true end
  local function result_problem(key)
    local at = labels[key]
    if not at then return key .. ", which no label defines in the printed paper" end
    if not key:match("^ch:") and key ~= "tab:related" then
      if key:match("^rq:") or key:match("^g:") or key:match("^dr:") then return nil end
      local thm = theorems[key]
      if thm and thm.file == at.file and thm.start == at.start then return nil end
      if key:match("^fig:") or key:match("^tab:") then return nil end
      if evalfile[at.file] and (key:match("^par:") or key:match("^sec:") or key:match("^subsec:") or key:match("^subsubsec:")) then
        if not heuristic[key] then
          heuristic[key] = true
          M.gapwarn[#M.gapwarn + 1] = key .. " is a heuristic section pointer in the evaluation: the reader must check that it contains a result sufficient for the matrix claim"
        end
        return nil
      end
    end
    return key .. " is not an evaluation result: point at a result figure, table or theorem, an evaluation section, or the research question or guarantee it answers"
  end
  local approaches = ncols - 3 -- tag, name, approaches..., this work
  if approaches < 2 then M.gapwarn[#M.gapwarn + 1] = "fewer than two other approaches in the gap matrix: the gap is argued against the closest existing work, plural" end
  for _, r in ipairs(rows) do
    local last = r[#r]
    local status, count = nil, 0
    local keys = {}
    cell_commands(last, function(cmd, arg)
      if cmd:match("^gap%a+$") then status = cmd; count = count + 1 end
      if arg then for k in arg:gmatch("[^,%s]+") do keys[#keys + 1] = k end end
    end)
    if count ~= 1 or not ({ gapyes = true, gappartial = true, gapno = true, gapna = true })[status] then
      fails[#fails + 1] = string.format("row %s: this work's cell needs one status: \\gapyes, \\gappartial, \\gapno or \\gapna", r[1])
    elseif status == "gapna" then
      local justified = false
      for _, k in ipairs(keys) do
        local prefix, suffix = k:match("^([^:]+):(.+)$")
        if not labels[k] then fails[#fails + 1] = string.format("row %s: this work's cell points at %s, which no label defines", r[1], k)
        elseif prefix == "lim" or ((prefix == "par" or prefix == "sec" or prefix == "subsec")
          and (suffix == "scope" or suffix == "out-of-scope" or suffix == "limitations")) then justified = true end
      end
      -- A short reason in the cell also suffices; a bare marker or "not applicable" does not.
      local reason = last:gsub("\\[cC]?ref%*?%s*%b{}", " ")
      local words = 0
      for _ in C.prose(reason):gmatch("%a%a+") do words = words + 1 end
      if words >= 3 and not reason:match("TODO") then justified = true end
      if not justified then fails[#fails + 1] = string.format("row %s: this work's N/A cell needs a reason or a reference to its scope or limitations", r[1]) end
    else
      if #keys == 0 then fails[#fails + 1] = string.format("row %s: this work's cell points at no evaluation result: add \\cref to the result that shows it", r[1]) end
      for _, k in ipairs(keys) do
        local why = result_problem(k)
        if why then fails[#fails + 1] = string.format("row %s: this work's cell points at %s", r[1], why) end
      end
    end
    if (r[2] or ""):match("TODO") then M.gapwarn[#M.gapwarn + 1] = string.format("row %s: the requirement's short name is a TODO", r[1]) end
  end
  M.gapcounts = string.format("rows=%d approaches=%d", #rows, approaches)
  return fails
end

-- the running example --------------------------------------------------------------------
local function eval_example(row, r)
  local box = C.example_box()
  local name = (C.readfile("thesis.tex") or ""):match("\\newcommand{\\exname}{([^}]*)}")
  local found
  for _, f in ipairs(C.role_files("intro")) do
    local ls = lines(f)
    for n, l in ipairs(ls) do
      if l:find("\\begin{" .. box .. "}", 1, true) then
        local e = n
        for m = n, #ls do if ls[m]:find("\\end{" .. box .. "}", 1, true) then e = m; break end end
        found = { file = f, line = n, last = e }
        break
      end
    end
    if found then break end
  end
  if not found then return 0, row.add end
  r.where = place(found.file, found.line, found.last)
  if not name or name:match("TODO") then
    -- the finding sits on the example box; the fix shows the line to edit, in thesis.tex
    for n, raw in ipairs(C.raw_lines("thesis.tex")) do
      local def = C.strip_comment(raw):match("\\newcommand{\\exname}%b{}")
      if def then r.fix = C.fix("placeholder", "name the running example", C.replace_at("thesis.tex", n, def, "\\newcommand{\\exname}{<the example's name>}")); break end
    end
    return 1, "name the example: \\exname in thesis.tex is still a TODO"
  end
  local w, ps = 0, plines(found.file)
  for i = found.line, found.last do w = w + C.own_words(ps[i] or "") end
  if w < M.EXAMPLE_WORDS then return 2, "write the introduction's example box in your own words: the actors, what they want, what goes wrong" end
  local without = {}
  for _, f in ipairs(C.main_chapters()) do
    if not C.file_has(f, "\\begin{" .. box .. "}") then without[#without + 1] = f:match("([^/]+)%.tex$") end
  end
  if #without == 0 then return 4 end
  return 3, "no example box in " .. first_of(without, 3)
end

-- the two abstracts ----------------------------------------------------------------------
local function eval_front(row, r)
  local f = C.FILES.abstract
  if not f then return 0, row.add end
  local ls, ps = lines(f), plines(f)
  local kiv, abs = nil, nil
  for n, l in ipairs(ls) do
    if l:match("\\chapter%*{Kivonat}") then kiv = n end
    if l:match("\\chapter%*{Abstract}") then abs = n end
  end
  local function words(a, b) local n = 0; for i = a, b do n = n + C.own_words(strip_headings(ps[i] or "")) end; return n end
  -- from the line after each heading, which carries \addcontentsline as well
  local wa = abs and words(abs + 1, (kiv and kiv > abs) and kiv - 1 or #ls) or 0
  local wk = kiv and words(kiv + 1, (abs and abs > kiv) and abs - 1 or #ls) or 0
  r.where = place(f, math.min(kiv or abs or 1, abs or kiv or 1), #ls)
  r.words = wa + wk
  if wa + wk == 0 then return 1, "only TODO or the template's text so far: write both" end
  if wa >= row.words and wk >= row.words then return 4 end
  local parts = {}
  parts[#parts + 1] = kiv and string.format("Kivonat %d", wk) or "no Kivonat"
  parts[#parts + 1] = abs and string.format("Abstract %d", wa) or "no Abstract"
  return 2, string.format("%s own words; each counts as written from %d", table.concat(parts, ", "), row.words)
end

local EVAL = { text = eval_text, tags = eval_tags, float = eval_float, example = eval_example, front = eval_front }

-- every row, evaluated; a row that the lint cannot evaluate is missing, with the error as its step
function M.evaluate()
  local out = {}
  for i, row in ipairs(ROWS) do
    local r = { row = row, index = i }
    local ok, level, nxt = pcall(EVAL[row.kind], row, r)
    if not ok then level, nxt = 0, "the lint could not read this row: " .. tostring(level) end
    r.level, r.next = level, nxt or ""
    -- the file the row belongs in, for a row that has no place yet
    r.home = r.where and r.where.file or (row.role == "front" and C.FILES.abstract) or C.ROLE[row.role]
    if r.level == 0 and row.role ~= "front" and #C.role_files(row.role) == 0 then
      r.next = r.next .. string.format(" (no %s: label a chapter \\label{ch:%s})", C.ROLE_NAME[row.role], row.role)
    end
    out[#out + 1] = r
  end
  return out
end

-- one line of glyphs per role, in reading order
function M.fingerprint(rows)
  local parts = {}
  for _, role in ipairs(M.ROLE_ORDER) do
    local g = {}
    for _, r in ipairs(rows) do if r.row.role == role then g[#g + 1] = M.GLYPH[r.level] end end
    parts[#parts + 1] = M.ROLE_SHORT[role] .. " " .. table.concat(g)
  end
  return table.concat(parts, " · ")
end
function M.at_target(rows)
  local t, n = M.target(), 0
  for _, r in ipairs(rows) do if r.level >= t then n = n + 1 end end
  return n
end

-- the job summary's first section: the fingerprint, then every row
local function write_summary(rows)
  local path = os.getenv("GITHUB_STEP_SUMMARY")
  if not path then return end
  local h = io.open(path, "a")
  if not h then return end
  local t = M.target()
  h:write(string.format("## Essentials: %d of %d at the %s level\n\n", M.at_target(rows), #rows, C.phase()))
  h:write("`" .. M.fingerprint(rows) .. "`\n\n")
  h:write("○ missing · ◔ placeholder · ◑ started · ◕ written · ● used where the argument needs it. The phase asks for: topic to plan ◔, draft ◑, polish ●, submit ●. **Bold** rows are below it.\n\n")
  h:write("| | Essential | Next step | Where |\n|---|---|---|---|\n")
  for _, r in ipairs(rows) do
    local name = r.level < t and ("**" .. r.row.title .. "**") or r.row.title
    local where = r.where and (r.where.file .. ":" .. r.where.line) or r.home or ""
    h:write(string.format("| %s | %s | %s | %s |\n", M.GLYPH[r.level], name, (r.next or ""):gsub("|", "\\|"), where ~= "" and ("`" .. where .. "`") or ""))
  end
  h:write("\n")
  h:close()
end

-- the label of a row found by its heading, right after the heading; safe, since a label prints
-- nothing, unless a file of the paper already defines it
local function label_fix(r)
  local label = "\\label{" .. r.label .. "}"
  local taken = false
  for _, f in ipairs(C.CONTENT) do if C.file_has(f, label) then taken = true end end
  local first = true
  return C.fix(taken and "review" or "safe", "add " .. label, table.unpack(C.matches(C.raw_lines(r.where.file)[r.where.line], "\\" .. r.cmd .. "%*?%s*%b{}", function(m)
    if first then first = false; return m .. label end
  end)))
end

C.rule("essentials", "source", "check", "always", "the essentials every paper of this kind contains, from scripts/lint/essentials.lua, each missing, a placeholder, started, written or used where the argument needs it; the phase asks for a level of every row (topic to plan: present, draft: started, polish and submit: used)", function()
  local rows = M.evaluate()
  C.ESSENTIALS = rows
  local t = M.target()
  local counts = { [0] = 0, 0, 0, 0, 0 }
  for _, r in ipairs(rows) do
    counts[r.level] = counts[r.level] + 1
    local file = r.home
    local line = r.where and r.where.line
    local msg = string.format("%s %s", M.GLYPH[r.level], r.row.title)
    if r.level < t then fail(file, line, msg, r.next ~= "" and r.next or M.LEVEL_NAME[r.level], r.fix) end
    if r.row.id == "setup" and r.level == 4 then note(file, line, "Artifact identity and version need human review", r.next) end
    if r.row.id == "gapmatrix" and r.level == 4 then note(file, line, "Matrix claim sufficiency needs human review", r.next) end
    if r.via == "heading" then note(file, line, string.format("%s found by its heading", r.row.title), string.format("add \\label{%s} so it is found when the heading changes", r.label), label_fix(r)) end
  end
  for _, w in ipairs(M.gapwarn) do warn(C.ROLE.related, nil, w) end
  if not C.quiet() then io.write(M.fingerprint(rows), "\n"); write_summary(rows) end
  return string.format("at-target=%d/%d %s=%d %s=%d %s=%d %s=%d %s=%d", M.at_target(rows), #rows, M.GLYPH[4], counts[4], M.GLYPH[3], counts[3], M.GLYPH[2], counts[2], M.GLYPH[1], counts[1], M.GLYPH[0], counts[0])
end, { summary = false })

return M
