-- Shared helpers for the lint rules: files, findings, reporting, the rule registry.
local lfs = require("lfs")
local M = {}
local T = require("texscan")
M.balanced_group = T.group
M.unformat = T.unformat
M.LINK_COMMANDS = T.LINK

M.opts = { dir = ".", doc = "draft", profile = os.getenv("LINT_PROFILE") or "tdk", tex = false, json = false }
-- the manual phase in draft.tex is the lifecycle phase; the four before draft share the checks' first level
M.PHASE_ORDER = { "topic", "setup", "research", "plan", "draft", "polish", "submit" }
M.PHASES = { topic = 1, setup = 1, research = 1, plan = 1, draft = 2, polish = 3, submit = 4 }

function M.readfile(p) local h = io.open(p, "r"); if not h then return nil end; local s = h:read("a"); h:close(); return s end
function M.lines(p)
  local t = {}
  for l in (M.readfile(p) or ""):gmatch("([^\n]*)\n?") do t[#t + 1] = l end
  if t[#t] == "" then t[#t] = nil end
  return t
end
function M.exists(p) return lfs.attributes(p) ~= nil end
function M.bpath(p) return M.opts.dir .. "/" .. p end
function M.strip_comment(l) return T.mask(l, "comments") end
function M.each_line(files, fn) for _, f in ipairs(files) do for n, l in ipairs(M.lines(f)) do fn(f, n, M.strip_comment(l)) end end end
function M.file_has(file, pattern) return (M.readfile(file) or ""):find(pattern) ~= nil end
function M.run(cmd) local h = io.popen(cmd .. " 2>&1"); if not h then return nil end; local s = h:read("a"); local ok = h:close(); return s, ok end
function M.run_quiet(cmd) local h = io.popen(cmd .. " 2>/dev/null"); if not h then return nil end; local s = h:read("a"); h:close(); return s end
function M.have(tool) local s = M.run("command -v " .. tool); return s ~= nil and s:match("%S") ~= nil end
function M.escape(s) return (s:gsub("%p", "%%%0")) end
function M.trim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end
-- a JSON document as Lua values (null is nil), or nil and the reason; enough for the TDK portal's API
function M.json_decode(s)
  local pos = 1
  local function ws() pos = s:find("[^ \t\r\n]", pos) or #s + 1 end
  local value
  local function str()
    local out, i = {}, pos + 1
    while true do
      local c = s:sub(i, i)
      if c == "" then error("unterminated string") end
      if c == '"' then pos = i + 1; return table.concat(out) end
      if c == "\\" then
        local e = s:sub(i + 1, i + 1)
        if e == "u" then
          local cp = tonumber(s:sub(i + 2, i + 5), 16); i = i + 6
          if cp >= 0xD800 and cp <= 0xDBFF and s:sub(i, i + 1) == "\\u" then
            local lo = tonumber(s:sub(i + 2, i + 5), 16); cp = 0x10000 + (cp - 0xD800) * 0x400 + (lo - 0xDC00); i = i + 6
          end
          out[#out + 1] = utf8.char(cp)
        else
          out[#out + 1] = ({ b = "\b", f = "\f", n = "\n", r = "\r", t = "\t" })[e] or e; i = i + 2
        end
      else
        local j = s:find('["\\]', i) or #s + 1
        out[#out + 1] = s:sub(i, j - 1); i = j
      end
    end
  end
  function value()
    ws()
    local c = s:sub(pos, pos)
    if c == "{" then
      local t = {}; pos = pos + 1; ws()
      if s:sub(pos, pos) == "}" then pos = pos + 1; return t end
      while true do
        ws(); local k = str(); ws(); pos = pos + 1 -- the colon
        t[k] = value(); ws()
        local d = s:sub(pos, pos); pos = pos + 1
        if d == "}" then return t elseif d ~= "," then error("bad object at " .. pos) end
      end
    elseif c == "[" then
      local t = {}; pos = pos + 1; ws()
      if s:sub(pos, pos) == "]" then pos = pos + 1; return t end
      while true do
        t[#t + 1] = value(); ws()
        local d = s:sub(pos, pos); pos = pos + 1
        if d == "]" then return t elseif d ~= "," then error("bad array at " .. pos) end
      end
    elseif c == '"' then return str()
    elseif s:sub(pos, pos + 3) == "true" then pos = pos + 4; return true
    elseif s:sub(pos, pos + 4) == "false" then pos = pos + 5; return false
    elseif s:sub(pos, pos + 3) == "null" then pos = pos + 4; return nil
    else
      local num = s:match("^-?%d+%.?%d*[eE]?[-+]?%d*", pos)
      if not num or num == "" then error("unexpected " .. c .. " at " .. pos) end
      pos = pos + #num; return tonumber(num)
    end
  end
  local ok, v = pcall(value)
  if ok then return v end
  return nil, v
end
function M.count(s, pat) return select(2, s:gsub(pat, "")) end

-- the content files are the ones draft.tex reaches through \include, \input and
-- \loadglsentries, in the order it reaches them; the frame under include/ is followed but not
-- counted, the guide is skipped, and commented-out lines do not count. M.BIB holds the .bib
-- files of \bibliography. A paper without a draft.tex that includes anything falls back to the
-- files in content/. The main-text chapters are the ones with a numbered \chapter; chapters are
-- found by role through their label, never by file name or folder, so a student may rename,
-- move or merge files. A chapter has role R if it carries \label{ch:R} or \label{ch:R:<name>}:
-- a role may span several chapters, and a chapter may have two roles. M.ROLES[R] lists the
-- chapters of R in reading order, M.ROLES_OF[file] is the set of a file's roles, and M.ROLE[R] is
-- the first chapter of R
M.CONTENT, M.MAIN, M.ROLE, M.ROLES, M.ROLES_OF, M.FILES, M.BIB, M.REACHED = {}, {}, {}, {}, {}, {}, {}, {}
M.ROLE_LABEL = { intro = "ch:intro", background = "ch:background", approach = "ch:approach", implementation = "ch:implementation", evaluation = "ch:evaluation", related = "ch:related", conclusion = "ch:conclusion" }
M.ROLE_NAME = { intro = "introduction", background = "background chapter", approach = "approach chapter", implementation = "implementation chapter", evaluation = "evaluation chapter", related = "related-work chapter", conclusion = "conclusion" }
M.MANDATORY = { "intro", "approach", "evaluation", "related", "conclusion" }
-- the roles in reading order, and the review-sheet criteria each role's chapters carry, as the
-- head of the role's section in guide/05-chapter-by-chapter.tex (guide:chapters:<role>) names them;
-- criterion A is scored on the whole paper and belongs to no role. The skim reads them from
-- --json; `lint.lua criteria` fails when the guide names other criteria
M.ROLE_SEQ = { "intro", "background", "approach", "implementation", "evaluation", "related", "conclusion" }
M.ROLE_CRITERIA = { intro = { "B/1", "C", "E" }, background = { "B/2" }, approach = { "D/1", "D/2" }, implementation = { "D/1", "D/2" },
  evaluation = { "D/2", "E" }, related = { "B/2", "D/1" }, conclusion = { "E" } }
do
  local seen = {}
  local function under(p, dir) return p:sub(1, #dir) == dir end
  local function follow(f)
    if seen[f] then return end
    seen[f] = true
    local s = M.readfile(f)
    if not s then return end
    M.REACHED[#M.REACHED + 1] = f
    if f ~= "draft.tex" and not under(f, "include/") then M.CONTENT[#M.CONTENT + 1] = f end
    for l in s:gmatch("[^\n]*") do
      for cmd, arg in M.strip_comment(l):gmatch("\\(%a+)%s*(%b{})") do
        arg = M.trim(arg:sub(2, -2))
        if cmd == "bibliography" then
          for b in arg:gmatch("[^,%s]+") do M.BIB[#M.BIB + 1] = b:match("%.bib$") and b or b .. ".bib" end
        elseif (cmd == "include" or cmd == "input" or cmd == "loadglsentries") and arg ~= "" and not arg:find("\\", 1, true) then
          local p = arg:match("%.tex$") and arg or arg .. ".tex"
          -- the paper's glossary is the one it loads, even with every entry deleted; the one
          -- under include/ is the template's common glossary
          if cmd == "loadglsentries" and under(p, "include/") then M.FILES.common_glossary = p
          elseif cmd == "loadglsentries" and not under(p, "guide/") then M.FILES.glossary = M.FILES.glossary or p end
          if not under(p, "guide/") then follow(p) end
        end
      end
    end
  end
  follow("draft.tex")
  if #M.CONTENT == 0 and M.exists("content") then
    for f in lfs.dir("content") do if f:match("%.tex$") then M.CONTENT[#M.CONTENT + 1] = "content/" .. f end end
    table.sort(M.CONTENT)
  end
  if #M.BIB == 0 then M.BIB = { "bib/references.bib", "bib/zotero.bib" } end
  for _, f in ipairs(M.CONTENT) do
    local s = M.readfile(f) or ""
    local body = s:gsub("%%[^\n]*", "")
    if body:match("\\chapter{") then M.MAIN[#M.MAIN + 1] = f end
    for lab in body:gmatch("\\label{(ch:[^}]*)}") do
      local role = lab:match("^ch:([%a]+)$") or lab:match("^ch:([%a]+):.+$")
      if role and M.ROLE_LABEL[role] and not (M.ROLES_OF[f] and M.ROLES_OF[f][role]) then
        M.ROLES_OF[f] = M.ROLES_OF[f] or {}
        M.ROLES_OF[f][role] = true
        M.ROLES[role] = M.ROLES[role] or {}
        table.insert(M.ROLES[role], f)
        M.ROLE[role] = M.ROLE[role] or f
      end
    end
    if body:match("\\chapter%*{Abstract}") then M.FILES.abstract = f end
    if body:find("\\label{aidecl}", 1, true) then M.FILES.aidecl = f end
    if body:match("\\DeclareAcronym") or body:match("\\newabbreviation") or body:match("\\newacronym") or body:match("\\newglossaryentry") then M.FILES.glossary = f end
  end
end
-- whether a file draft.tex reaches, the frame included, loads package p, or defines the macro
-- \m: a fix that writes \cref or \eg is only offered to a paper that has it, since a paper that
-- left the template may not load cleveref
local loads_cache, defines_cache = {}, {}
function M.loads(p)
  if loads_cache[p] == nil then
    loads_cache[p] = false
    for _, f in ipairs(M.REACHED) do
      for l in (M.readfile(f) or ""):gmatch("[^\n]*") do
        for list in M.strip_comment(l):gmatch("\\usepackage%s*%b[]%s*{([^}]*)}") do for q in list:gmatch("[^,%s]+") do if q == p then loads_cache[p] = true end end end
        for list in M.strip_comment(l):gmatch("\\usepackage%s*{([^}]*)}") do for q in list:gmatch("[^,%s]+") do if q == p then loads_cache[p] = true end end end
      end
    end
  end
  return loads_cache[p]
end
function M.defines(m)
  if defines_cache[m] == nil then
    defines_cache[m] = false
    local name = M.escape(m)
    for _, f in ipairs(M.REACHED) do
      for l in (M.readfile(f) or ""):gmatch("[^\n]*") do
        local c = M.strip_comment(l)
        for _, cmd in ipairs({ "newcommand", "renewcommand", "providecommand", "DeclareRobustCommand", "NewDocumentCommand" }) do
          if c:find("\\" .. cmd .. "%*?%s*{?\\" .. name .. "[}%s%[{]") then defines_cache[m] = true end
        end
        if c:find("\\def\\" .. name .. "[^%a]") then defines_cache[m] = true end
      end
    end
  end
  return defines_cache[m]
end

-- the tag lists the paper declares, the template's and any of its own: every
-- \NewTagList{<environment>}{<tag>}{<Name>}{<Names>} in a file draft.tex reaches, as
-- { assumptions = { tag = "AS", name = "Assumption" }, ... }
function M.tag_lists()
  local t = {}
  for _, f in ipairs(M.REACHED) do
    for l in (M.readfile(f) or ""):gmatch("[^\n]*") do
      local env, tag, name = M.strip_comment(l):match("\\NewTagList%s*{([^}]*)}%s*{([^}]*)}%s*{([^}]*)}")
      if env then t[M.trim(env)] = { tag = M.trim(tag), name = M.trim(name) } end
    end
  end
  return t
end

-- the criteria each role's section of guide/05-chapter-by-chapter.tex names in its bold
-- \textbf{Criterion ...} or \textbf{Criteria ...} heads, as { approach = { ["D/1"] = true, ... } }
function M.guide_criteria(file)
  local s = M.readfile(file or "guide/05-chapter-by-chapter.tex")
  if not s then return nil end
  local out, cuts = {}, {}
  -- a role's section runs to the next \section; its subsections carry guide:chapters:<name> labels too
  for pos, role in s:gmatch("()\\section%b{}%s*\\label{guide:chapters:(%a+)}") do cuts[#cuts + 1] = { pos = pos, role = role } end
  for i, c in ipairs(cuts) do
    local body = s:sub(c.pos, cuts[i + 1] and cuts[i + 1].pos - 1 or #s)
    for arg in body:gmatch("\\textbf(%b{})") do
      local head = arg:sub(2, -2)
      if head:match("^Criteri%a+") then
        head = head:gsub("^Criteri%a+", ""):gsub("%b()", "")
        for crit in head:gmatch("%f[%w]([A-E]/?%d?)%f[^%w/]") do
          out[c.role] = out[c.role] or {}
          out[c.role][crit] = true
        end
      end
    end
  end
  return out
end

-- the chapters of a role, in reading order; empty when no chapter has it
function M.role_files(r) return M.ROLES[r] or {} end
-- the text of all chapters of a role, joined in reading order
function M.role_text(r)
  local t = {}
  for _, f in ipairs(M.role_files(r)) do t[#t + 1] = M.readfile(f) or "" end
  return table.concat(t, "\n")
end
-- the main text's chapter files: the numbered chapters up to the appendix
function M.main_chapters()
  local out = {}
  for _, f in ipairs(M.MAIN) do
    if M.file_has(f, "\\appendix") then break end
    out[#out + 1] = f
  end
  return out
end
-- the environment of the running example's boxes: \lintexamplebox in draft.tex, or the template's
function M.example_box()
  local value, err = M.setting("lintexamplebox")
  if err then error(err) end
  return value or "runningexample"
end
-- the bibliography's entries by key: { type, body }, read once
local bib_cache
function M.bib_entries()
  if bib_cache then return bib_cache end
  bib_cache = {}
  for _, b in ipairs(M.BIB) do
    for typ, body in (M.readfile(b) or ""):gmatch("@(%a+)%s*(%b{})") do
      local key = body:match("^{%s*([^,%s]+)%s*,")
      if key then bib_cache[key] = { type = typ:lower(), body = body, file = b } end
    end
  end
  return bib_cache
end
-- every call of a command whose name passes want(name) in the printed text of the files (no
-- comments, commented-out environments, code, todo notes or beats: M.printed_lines), with up to
-- two optional [..] arguments and its first {..} argument, which may each be preceded by spaces
-- or a line break and may span lines, as TeX reads them: fn(file, line of the command, name, arg)
function M.each_call(files, want, fn)
  for _, f in ipairs(files) do
    local text = table.concat(M.printed_lines(f), "\n")
    local pos = 1
    while pos <= #text do
      if text:sub(pos, pos) ~= "\\" then pos = pos + 1
      else
        local start = pos
        local name, after = T.command(text, pos)
        pos = after
        local link = T.LINK[name] or name == "path"
        if want(name) or link then
          local arg, e
          if name == "url" or name == "path" or name == "nolinkurl" then arg, e = T.address(text, after)
          else arg, e = T.argument(text, after, link) end
          if e then
            if want(name) then fn(f, 1 + M.count(text:sub(1, start - 1), "\n"), name, arg, start, e, text) end
            pos = e + 1 -- never interpret a command in a key or an address
          end
        end
      end
    end
  end
end
-- every key cited by \cite, \citet, \citep, \citeauthor, \Citet and the rest of the family (not
-- \nocite, not the \citeneeded marker), as fn(file, line, key)
local function is_cite(name) return name:match("^[cC]ite%a*%*?$") ~= nil and name ~= "citeneeded" end
function M.each_cite(files, fn)
  M.each_call(files, is_cite, function(f, n, _, arg) for k in arg:gmatch("[^,%s]+") do fn(f, n, k) end end)
end
-- a rule that needs chapters by role calls this first; it fails with the right message and returns false
function M.roles_ok(list)
  local ok = true
  for _, r in ipairs(list) do
    if not M.ROLE[r] then M.fail(nil, nil, string.format("no %s: no chapter file carries \\label{%s} or \\label{%s:<name>}", M.ROLE_NAME[r], M.ROLE_LABEL[r], M.ROLE_LABEL[r])); ok = false end
  end
  return ok
end

-- Settings are literal, zero-argument declarations in draft.tex, in source order.
-- Support new/renew/providecommand (starred, multiline, optionally [0]) and def.
-- No expansion, included settings, local groups or conditional evaluation. A
-- declaration outside this subset is an error rather than a fallback to plan.
function M.setting(name)
  local text = T.mask(M.readfile("draft.tex") or "", "settings")
  local pos, depth, conditional, value = 1, 0, 0, nil
  while pos <= #text do
    local c = text:sub(pos, pos)
    if c == "{" then depth = depth + 1; pos = pos + 1
    elseif c == "}" then depth = math.max(0, depth - 1); pos = pos + 1
    elseif c ~= "\\" then pos = pos + 1
    else
      local cmd, after = T.command(text, pos)
      local bare = cmd:gsub("%*$", "")
      pos = after
      if bare:match("^if") then conditional = conditional + 1
      elseif bare == "fi" then conditional = math.max(0, conditional - 1) end
      if bare == "newcommand" or bare == "renewcommand" or bare == "providecommand" or bare == "def" or bare == "gdef" or bare == "edef" or bare == "let" or bare == "DeclareRobustCommand" or bare:match("DocumentCommand$") or bare == "xdef" then
        local at = T.space(text, after)
        local target, last = T.group(text, at)
        if not last then target, last = text:match("^(\\[%a@]+)()", at); if last then last = last - 1 end end
        if target and M.trim(target) == "\\" .. name then
          local function unsupported() return nil, "unsupported declaration of \\" .. name .. " in draft.tex: use a top-level literal zero-argument newcommand/renewcommand/providecommand or def" end
          if depth > 0 or conditional > 0 or bare == "gdef" or bare == "edef" or bare == "let" or bare == "xdef" or bare:match("DocumentCommand$") then return unsupported() end
          at = T.space(text, last + 1)
          if text:sub(at, at) == "[" then
            local n, e = T.group(text, at, "[")
            if not e or M.trim(n) ~= "0" then return unsupported() end
            at = T.space(text, e + 1)
          end
          local body, e = T.group(text, at)
          if not e or body:find("[\\{}#]") then return unsupported() end
          if bare ~= "providecommand" or value == nil then value = M.trim(body) end
          pos = e + 1
        end
      end
    end
  end
  return value
end
-- the phase the calendar has reached: the lifecycle's dates (guide, tab:lifecycle) in the year of
-- today's date, or of LINT_DATE (YYYY-MM-DD) in the tests. From 30 October the paper is being
-- submitted, whatever draft.tex says; before 1 October the calendar asks nothing
M.PHASE_DATES = { { "10-01", "draft" }, { "10-22", "polish" }, { "10-30", "submit" } }
function M.calendar_phase()
  local today = os.getenv("LINT_DATE")
  if not (today and today:match("^%d%d%d%d%-%d%d%-%d%d$")) then today = os.date("%Y-%m-%d") end
  local md, phase, since = today:sub(6), nil, nil
  for _, d in ipairs(M.PHASE_DATES) do if md >= d[1] then phase, since = d[2], d[1] end end
  return phase, since
end
-- the manual phase: --phase, else LINT_PHASE, else \lintphase in draft.tex, else plan. A value
-- that is none of the seven (final included: the lint has no aliases) is an error, never read as
-- plan: lint.lua stops on it before any rule. A phase from draft.tex or the default is raised to
-- the calendar's: a \lintphase left at polish does not keep a submitted paper out of the submit
-- checks. --phase and LINT_PHASE are taken as given
function M.resolve_phase()
  local p, src = M.opts.phase, "--phase"
  if not p then
    p, src = os.getenv("LINT_PHASE"), "LINT_PHASE"
    if p == "" then p = nil end -- an empty variable is an unset one
  end
  if not p then
    local err
    p, err = M.setting("lintphase"); src = "\\lintphase in draft.tex"
    if err then return nil, err end
  end
  if not p then p, src = "plan", "the default" end
  M.opts.phase, M.opts.phase_source = p, src
  if not M.PHASES[p] then return nil, string.format("unknown phase '%s' from %s: use one of %s", p, src, table.concat(M.PHASE_ORDER, ", ")) end
  if src ~= "--phase" and src ~= "LINT_PHASE" then
    local cal, since = M.calendar_phase()
    if cal and M.PHASES[cal] > M.PHASES[p] then
      M.opts.phase, M.opts.phase_source = cal, string.format("the date, %s since %d October; %s says %s", cal, tonumber(since:sub(4)), src, p)
      p = cal
    end
  end
  return p
end
-- the draft build: draft.tex prints the guide, the todos and the beats, which the reviewer build
-- hides, so what it shows of them, and its page count, is not what a reviewer gets
function M.draft_build() return M.opts.doc == "draft" end
function M.phase()
  if not M.opts.phase_source then M.resolve_phase() end
  return M.opts.phase
end
-- the level of the checks the phase asks for: 1 for topic to plan, then 2, 3, 4
function M.level() return M.PHASES[M.phase()] end
function M.phase_reached(due) if due == "always" then return true end; return M.level() >= M.PHASES[due] end

-- findings and reporting -------------------------------------------------------------
local gh = os.getenv("GITHUB_ACTIONS") ~= nil
local summary = os.getenv("GITHUB_STEP_SUMMARY")
-- JSON remains paper-relative for skim/review; GitHub annotations use repository paths.
local annotation_prefix = gh and M.trim(M.run_quiet("git rev-parse --show-prefix") or "") or ""
local function annotation_path(file)
  local parts = {}
  for part in (annotation_prefix .. file):gmatch("[^/]+") do
    if part == ".." then table.remove(parts) elseif part ~= "." then parts[#parts + 1] = part end
  end
  return table.concat(parts, "/")
end
-- a run that prints the Checks page (--tex, which write18 runs on every XeLaTeX pass), the JSON or
-- the fixes: the findings, the counts and the job summary stay out, since the plain run writes them
function M.quiet() return M.opts.tex or M.opts.json or M.opts.quiet or false end
M.findings = {}
M.ignored = 0
M.current_rule = nil
-- "% lint-ignore: <rule> <reason>" on the line or the line above silences a finding; the reason is required
local function ignored(file, line)
  if not (file and line and M.current_rule) then return false end
  local ls = M.lines(file)
  for _, l in ipairs({ ls[line] or "", ls[line - 1] or "" }) do
    local rule, reason = l:match("%%%s*lint%-ignore:%s*([%w%-]+)%s*(.*)$")
    if rule == M.current_rule or rule == "all" then
      if not reason or #M.trim(reason) < 3 then
        M.findings[#M.findings + 1] = { level = "warning", file = file, line = line, msg = "lint-ignore without a reason", help = "say why" }
        return false
      end
      M.ignored = M.ignored + 1
      return true
    end
  end
  return false
end
-- findings, help and fixes ----------------------------------------------------------------
-- A finding says what is wrong, its help what to do, and its fix, when the lint can compute one,
-- the text to write instead, the way a compiler reports them:
--   fail(f, n, "a typed reference with \\ref", "write \\cref{...}", fix)
-- Both help and fix are optional: a string after the message is the help, a table the fix. The
-- help is the general instruction; the fix's own help names the change, and stands in for the
-- help where a finding has none. A fix's safety says how far to trust it:
--   safe         the exact inverse of a slip; `lint.lua fix` writes it
--   review       most likely right, but read it first; `lint.lua fix --review` writes it
--   placeholder  the text to write, with <holes> only the author can fill; shown, never written
--   C.fix("safe", "write \\cref", C.replace("Figure~\\ref{" .. key .. "}", "\\cref{" .. key .. "}"))
-- An edit replaces the first old on the finding's line (every old with all), adds a line after
-- it, or names a command for the author to run; replace_at and after_at do the same elsewhere.
-- C.matches makes one edit per match of a pattern, each at its own column. An edit never touches
-- the comment after a %, which no rule reads. A fix covers every occurrence of its slip on its
-- line, so a fix offered again after it was written has not cleared its finding. A fix whose old
-- text is not on its line is dropped, never guessed (LINT_FIX_STRICT=1 makes that an error, for
-- the tests).
M.SAFETY = { safe = 1, review = 2, placeholder = 3 }
function M.fix(safety, help, ...) return { safety = safety, help = help, edits = { ... } } end
function M.replace(old, new, all) return { old = old, new = new, all = all } end
function M.after(text) return { after = text } end
function M.replace_at(file, line, old, new, all) return { file = file, line = line, old = old, new = new, all = all } end
function M.after_at(file, line, text) return { file = file, line = line, after = text } end
function M.command(cmd) return { cmd = cmd } end

-- the file's lines as they are on disk, read once per run
local raw_cache = {}
function M.raw_lines(file)
  if not raw_cache[file] then raw_cache[file] = M.lines(file) end
  return raw_cache[file]
end
-- The guard sees the full original file, including literals opened on earlier
-- lines. During planning, rescan the current line in that context after edits.
local protection_cache = {}
function M.edit_allowed(file, line, first, last, current)
  if not file or not line then return true end
  local raw = M.raw_lines(file)
  local cache = protection_cache[file]
  if not cache then
    local starts, at = {}, 1
    for n, l in ipairs(raw) do starts[n], at = at, at + #l + 1 end
    cache = { starts = starts, spans = T.spans(table.concat(raw, "\n"), "fix") }
    protection_cache[file] = cache
  end
  local offset = cache.starts[line]
  if not offset then return false end
  local spans = cache.spans
  if current and current ~= raw[line] then
    local ls = { table.unpack(raw) }; ls[line] = current
    spans = T.spans(table.concat(ls, "\n"), "fix")
  end
  return not T.overlaps(spans, offset + first - 1, offset + last - 1)
end
-- A bound edit has an exact byte column and cannot migrate to another occurrence.
function M.apply_edit(l, e)
  local s = e.at or l:find(e.old, 1, true)
  if not s or l:sub(s, s + #e.old - 1) ~= e.old then return nil end
  if not M.edit_allowed(e.file, e.line, s, s + #e.old - 1, l) then return nil end
  if not e.file and T.overlaps(T.spans(l, "fix"), s, s + #e.old - 1) then return nil end
  if e.all then
    local out, prev, pos = {}, 1, 1
    while true do
      local a, b = l:find(e.old, pos, true)
      if not a then break end
      if not M.edit_allowed(e.file, e.line, a, b, l) or (not e.file and T.overlaps(T.spans(l, "fix"), a, b)) then return nil end
      out[#out + 1] = l:sub(prev, a - 1) .. e.new; prev, pos = b + 1, b + 1
    end
    out[#out + 1] = l:sub(prev); return table.concat(out)
  end
  return l:sub(1, s - 1) .. e.new .. l:sub(s + #e.old)
end
-- one edit per match of pattern in the code part of line l, right to left, so each column still
-- holds when its edit comes; fn(match, column, code, captures...) gives the new text, nil skips it.
-- A match inside a literal span (M.literal_spans) is never an edit
function M.matches(l, pattern, fn, original)
  local code, found, init = T.mask(l, "fix"), {}, 1
  local literal = M.literal_spans(l)
  while init <= #code + 1 do
    local r = { code:find(pattern, init) }
    if not r[1] then break end
    local s, e = r[1], r[2]
    local new = not M.in_literal(literal, s, e) and (not original or original:sub(s, e) == code:sub(s, e)) and fn(code:sub(s, e), s, code, table.unpack(r, 3)) or nil
    if new then found[#found + 1] = { at = s, old = code:sub(s, e), new = new } end
    if pattern:sub(1, 1) == "^" then break end
    init = e >= s and e + 1 or s + 1
  end
  local edits = {}
  for i = #found, 1, -1 do edits[#edits + 1] = found[i] end
  return edits
end
-- the number of matches of pattern in s
function M.nmatch(s, pattern) local n = 0; for _ in s:gmatch(pattern) do n = n + 1 end; return n end
-- the spans of text that are literal, never prose: inline verbatim (\verb|..|,
-- \lstinline{..} or \lstinline|..|, \mintinline{lang}{..}), paths and links (\path, \url and the
-- address of \href) and inline maths ($..$). "abc" in \verb|"abc"| is the program's own text and
-- 10-20 in $10-20$ is a formula, so M.matches skips a match that touches one of them and
-- M.unliteral blanks them for a rule's pattern
function M.literal_spans(code) return T.spans(code, "fix") end
function M.in_literal(spans, s, e) return T.overlaps(spans, s, e) end
function M.unliteral(code) return T.mask(code, "fix") end
-- the fix bound to the finding's place and checked against the file; nil when it does not apply
local function bind(fx, file, line)
  if not fx or #fx.edits == 0 then return nil end
  assert(M.SAFETY[fx.safety], "unknown fix safety " .. tostring(fx.safety))
  local edits = {}
  for _, e in ipairs(fx.edits) do
    if e.cmd then edits[#edits + 1] = e
    else
      e.file, e.line = e.file or file, e.line or line
      local l = e.file and e.line and M.raw_lines(e.file)[e.line]
      local found = false
      if l and e.old and e.at and not M.edit_allowed(e.file, e.line, e.at, e.at + #e.old - 1) then
        found = true -- a reader's mask can contain spaces where the literal was
      elseif l and e.old and #e.old > 0 then
        local positions, pos = {}, e.at or 1
        while true do
          local a, b = l:find(e.old, pos, true)
          if not a or (e.at and a ~= e.at) then break end
          found = true
          if M.edit_allowed(e.file, e.line, a, b) then
            positions[#positions + 1] = { file=e.file, line=e.line, at=a, old=e.old, new=e.new }
            if not e.all then break end
          end
          if e.at then break end
          pos = b + 1
        end
        for i = #positions, 1, -1 do edits[#edits + 1] = positions[i] end
      elseif l and e.after then
        found = true
        if M.edit_allowed(e.file, e.line, #l + 1, #l + 1) then edits[#edits + 1] = e end
      end
      if not found then
        if os.getenv("LINT_FIX_STRICT") then error(string.format("fix %q does not apply at %s:%s", fx.help, tostring(e.file), tostring(e.line))) end
        return nil
      end
    end
  end
  if #edits == 0 then return nil end
  fx.edits = edits
  return fx
end
local FIX_WHO = { safe = "make fix writes it", review = "make fix-review writes it; read it first", placeholder = "fill in the <holes>" }
-- the fix as lines of text, under the finding: "fix (safe): ...", then "- old" and "+ new" for each
-- line it changes, "@ file:line" before a line elsewhere, "$ command" for a command
function M.fix_lines(f)
  local fx = f.fix
  local command = false
  for _, e in ipairs(fx.edits) do if e.cmd then command = true end end
  local out = { string.format("fix (%s): %s", fx.safety, command and "run it yourself" or FIX_WHO[fx.safety]) }
  local groups, order = {}, {}
  for _, e in ipairs(fx.edits) do
    local k = e.cmd and ("$" .. #order) or (e.file .. ":" .. e.line)
    if not groups[k] then groups[k] = { file = e.file, line = e.line, edits = {} }; order[#order + 1] = k end
    table.insert(groups[k].edits, e)
  end
  for _, k in ipairs(order) do
    local g = groups[k]
    if g.file and (g.file ~= f.file or g.line ~= f.line) then out[#out + 1] = "@ " .. g.file .. ":" .. g.line end
    local old = g.file and M.raw_lines(g.file)[g.line]
    local new = old
    for _, e in ipairs(g.edits) do if e.old then new = M.apply_edit(new, e) or new end end
    if old and new ~= old then out[#out + 1] = "- " .. old:gsub("%s+$", ""); out[#out + 1] = "+ " .. new:gsub("%s+$", "") end
    for _, e in ipairs(g.edits) do
      if e.after then out[#out + 1] = "+ " .. e.after end
      if e.cmd then out[#out + 1] = "$ " .. e.cmd end
    end
  end
  return out
end
-- the columns of the first replaced text on the finding's own line, in characters, for annotations
local function columns(f)
  for _, e in ipairs(f.fix and f.fix.edits or {}) do
    if e.old and e.file == f.file and e.line == f.line then
      local l = M.raw_lines(f.file)[f.line]
      local s = e.at or l:find(e.old, 1, true)
      local c = (utf8.len(l:sub(1, s - 1)) or (s - 1)) + 1
      return c, c + (utf8.len(e.old) or #e.old) - 1
    end
  end
end

local function finding(level, file, line, msg, help, fx)
  if type(help) ~= "string" then help, fx = nil, help end
  if ignored(file, line) then return end
  M.findings[#M.findings + 1] = { level = level, file = file, line = line, msg = msg, help = help, fix = bind(fx, file, line) }
end
-- the help a finding shows: its own, or else its fix's
function M.help_of(f) return f.help or (f.fix and f.fix.help) end
-- findings are printed by M.report, after sorting, so the output is the same on every run
-- GitHub's workflow commands end a message at a newline, and read % as an escape
local function ghesc(s) return (s:gsub("%%", "%%25"):gsub("\r", "%%0D"):gsub("\n", "%%0A")) end
-- a property (title=...) also ends at a comma or a colon
local function ghprop(s) return (ghesc(s):gsub(":", "%%3A"):gsub(",", "%%2C")) end
local function print_finding(f)
  local lines = {}
  local help = M.help_of(f)
  if help then lines[1] = "help: " .. help end
  for _, l in ipairs(f.fix and M.fix_lines(f) or {}) do lines[#lines + 1] = l end
  if gh then
    -- the message is the annotation's title, the help and the fix its body
    local loc = f.file and ("file=" .. ghprop(annotation_path(f.file)) .. (f.line and (",line=" .. f.line) or "")) or ""
    local c1, c2 = columns(f)
    if c1 then loc = loc .. string.format(",col=%d,endColumn=%d", c1, c2) end
    if #lines == 0 then io.write(string.format("::%s %s::%s\n", f.level, loc, ghesc(f.msg)))
    else io.write(string.format("::%s %s%stitle=%s::%s\n", f.level, loc, loc ~= "" and "," or "", ghprop(f.msg), ghesc(table.concat(lines, "\n")))) end
  else
    local tag = ({ error = " FAIL", warning = " warn", notice = "     " })[f.level]
    io.write(string.format("%s%s %s\n", f.file and (f.file .. (f.line and (":" .. f.line) or "") .. ":") or "", tag, f.msg))
    for _, l in ipairs(lines) do io.write("    ", l, "\n") end
  end
end
function M.fail(file, line, msg, help, fx) finding("error", file, line, msg, help, fx) end
-- the rule cannot run here (a tool is missing, the profile excludes it): its status is skipped,
-- not pass, and the reason is its one finding
M.skipped = nil
function M.skip(reason) M.skipped = reason; finding("notice", nil, nil, reason .. ": skipped") end
-- the rule's own code failed (lint.lua sets it): its status is error, whatever its severity and
-- phase, the run exits 2, and nothing it would have found or fixed is established
M.crashed = nil
function M.warn(file, line, msg, help, fx) finding("warning", file, line, msg, help, fx) end
function M.note(file, line, msg, help, fx) finding("notice", file, line, msg, help, fx) end

M.results = {}
-- severity: check (fails on errors once its phase is reached), advice (warns, never fails), count (numbers)
-- status, in the words the Checks page and the job summary use: pass, fix (a check that fails now),
-- due at <phase> (a check that fails, but not yet), suggestion (advice with findings), count,
-- skipped (the rule did not run, M.skip)
function M.status(r, errors, warnings)
  if M.crashed then return "error" end
  if M.skipped then return "skipped" end
  if r.severity == "check" then
    if errors == 0 then return "pass" end
    return M.phase_reached(r.phase) and "fix" or ("due at " .. r.phase)
  elseif r.severity == "advice" then return (errors + warnings == 0) and "pass" or "suggestion" end
  return "count"
end
local ICON = { pass = ":white_check_mark:", fix = ":x:", suggestion = ":information_source:", count = ":1234:", skipped = ":fast_forward:", error = ":bangbang:" }
function M.report(rule, r, counts)
  -- a stable order: pairs() differs between runs, and the Checks page that lists these findings
  -- is input by the build, so an unstable order kept latexmk recompiling
  table.sort(M.findings, function(a, b)
    if (a.file or "") ~= (b.file or "") then return (a.file or "") < (b.file or "") end
    if (a.line or 0) ~= (b.line or 0) then return (a.line or 0) < (b.line or 0) end
    return a.msg < b.msg
  end)
  -- quiet: nothing on stdout but the page or the JSON, and nothing in the job summary, which the
  -- plain run of the same rules writes
  local quiet = M.quiet()
  if not quiet then for _, f in ipairs(M.findings) do print_finding(f) end end
  local errors, warnings = 0, 0
  for _, f in ipairs(M.findings) do
    if f.level == "error" then errors = errors + 1 elseif f.level == "warning" then warnings = warnings + 1 end
  end
  local gate = r.severity == "check" and M.phase_reached(r.phase) and not M.skipped -- a rule that did not run gates nothing
  local ok = errors == 0 and not M.crashed
  local status = M.status(r, errors, warnings)
  M.results[#M.results + 1] = { rule = rule, family = r.family, severity = r.severity, phase = r.phase, status = status, errors = errors, warnings = warnings, counts = counts, findings = M.findings, ignored = M.ignored, crashed = M.crashed }
  if not quiet then
    io.write(string.format("%s %-13s %-7s %-18s %d error(s), %d warning(s)%s%s\n", gate and (ok and "ok  " or "FAIL") or "    ", rule, r.severity, status, errors, warnings, counts and (" " .. counts) or "", M.ignored > 0 and (" ignored=" .. M.ignored) or ""))
  end
  if summary and r.summary ~= false and not quiet then
    local h = io.open(summary, "a")
    if h then
      local P = require("pagemap")
      local found = r.severity == "count" and (counts or "") or ((errors + warnings == 0) and "" or string.format("%d error(s), %d warning(s)", errors, warnings))
      local fixes = 0
      for _, f in ipairs(M.findings) do if f.fix and f.fix.safety == "safe" then fixes = fixes + 1 end end
      if fixes > 0 then found = found .. string.format(", %d with a safe fix (`make fix`)", fixes) end
      h:write(string.format("| %s | %s %s | %s | `%s` | %s |\n", P.group_title(P.group(rule)), ICON[status] or ":hourglass:", status, (P.title(rule):gsub("%-%-", "–")), rule, (found:gsub("|", "\\|"))))
      h:close()
    end
  end
  if M.crashed then return false end -- a crash fails the run whatever the rule's severity or phase
  return not gate or ok
end
M.SUMMARY_HEADER = "| Group | Status | Check | Rule | Findings |\n|---|---|---|---|---|\n"
function M.summary_header(title)
  if not summary or M.quiet() then return end
  local h = io.open(summary, "a"); if h then h:write("\n## " .. title .. "\n\n" .. M.SUMMARY_HEADER); h:close() end
end

-- rule registry ------------------------------------------------------------------------
M.RULES, M.ORDER = {}, {}
-- opts.summary = false: the rule writes its own section of the job summary instead of a table row
function M.rule(name, family, severity, phase, desc, fn, opts)
  M.RULES[name] = { family = family, severity = severity, phase = phase, desc = desc, fn = fn, summary = (opts or {}).summary }; M.ORDER[#M.ORDER + 1] = name
end

-- label and reference index over the main chapters -------------------------------------
function M.collect_labels_and_refs(files)
  local labels, refs = {}, {}
  local depth = 0
  M.each_line(files, function(f, n, l)
    for key in l:gmatch("\\label{([^}]*)}") do labels[key] = { file = f, line = n, sub = depth > 0 } end
    depth = depth + M.count(l, "\\begin{sub[a-z]+}") - M.count(l, "\\end{sub[a-z]+}")
    for keys in l:gmatch("\\[Cc]ref{([^}]*)}") do for key in keys:gmatch("[^,%s]+") do refs[key] = (refs[key] or 0) + 1 end end
    for keys in l:gmatch("\\ref{([^}]*)}") do for key in keys:gmatch("[^,%s]+") do refs[key] = (refs[key] or 0) + 1 end end
    for key in l:gmatch("\\[Tt]plref{([^}]*)}") do refs[key] = (refs[key] or 0) + 1 end
  end)
  return labels, refs
end
function M.refs_in(file, pattern)
  local n = 0
  M.each_line({ file }, function(_, _, l)
    for keys in l:gmatch("\\[Cc]?ref{([^}]*)}") do for key in keys:gmatch("[^,%s]+") do if key:match(pattern) then n = n + 1 end end end
  end)
  return n
end

-- The prose reader hides comments, notes, literal \iffalse regions, code,
-- drawings and maths without changing byte columns or line numbers.
M.CODE = { "verbatim", "verbatim*", "Verbatim", "Verbatim*", "BVerbatim", "LVerbatim", "SaveVerbatim", "alltt", "lstlisting", "minted" }
M.NONPROSE = { "comment", "tikzpicture", "axis", "forest", "equation", "equation*", "align", "align*", "gather", "gather*", "multline", "multline*", "displaymath" }
-- Printed readers retain maths and drawings, where citations and links can print.
M.UNPRINTED = { "comment" }
for _, e in ipairs(M.CODE) do M.NONPROSE[#M.NONPROSE + 1] = e; M.UNPRINTED[#M.UNPRINTED + 1] = e end
function M.printed_lines(file) return M.prose_lines(file, M.UNPRINTED) end
local reader_cache = {}
local function masked_lines(file, mode, skip)
  local key = file .. ":" .. mode
  if not skip and reader_cache[key] then return reader_cache[key] end
  local extra = {}; for _, env in ipairs(skip or {}) do extra[env] = true end
  local text = T.mask(M.readfile(file) or "", mode, extra)
  local out = {}
  for l in text:gmatch("([^\n]*)\n?") do out[#out + 1] = l end
  if out[#out] == "" then out[#out] = nil end
  if not skip then reader_cache[key] = out end
  return out
end
function M.prose_lines(file, skip)
  return masked_lines(file, skip and "printed" or "prose", skip ~= M.UNPRINTED and skip or nil)
end
function M.editable_lines(file) return masked_lines(file, "fix") end
function M.each_editable_line(files, fn)
  for _, f in ipairs(files) do for n, l in ipairs(M.editable_lines(f)) do if l:match("%S") then fn(f, n, l) end end end
end
function M.each_prose_line(files, fn) for _, f in ipairs(files) do for n, l in ipairs(M.prose_lines(f)) do if l:match("%S") then fn(f, n, l) end end end end
-- the printed lines (M.printed_lines: no comments, commented-out environments or code listings)
function M.each_printed_line(files, fn) for _, f in ipairs(files) do for n, l in ipairs(M.printed_lines(f)) do if l:match("%S") then fn(f, n, l) end end end end

-- prose of a line: literal text (M.literal_spans), macros, math, labels, citations and urls
-- removed, for word-level rules
function M.prose(l)
  l = T.mask_calls(T.mask(l, "prose"), is_cite)
  local blank = T.blank
  l = l:gsub("%$[^$]*%$", blank)
  l = l:gsub("\\url%b{}", blank):gsub("\\href%b{}", blank):gsub("\\path%b{}", blank)
  l = l:gsub("\\[cC]?ref%b{}", blank):gsub("\\[aA]utoref%b{}", blank):gsub("\\pageref%b{}", blank):gsub("\\nameref%b{}", blank):gsub("\\label%b{}", blank)
  l = l:gsub("\\includegraphics%b[]%b{}", blank):gsub("\\includegraphics%b{}", blank):gsub("\\includesvg%b[]%b{}", blank):gsub("\\includesvg%b{}", blank):gsub("\\input%b{}", blank):gsub("\\cite[tp]?%*?%b[]?%b{}", blank):gsub("\\cite[tp]?%*?%b{}", blank)
  l = l:gsub("\\texttt%b{}", blank):gsub("\\verb(.)(.-)%1", blank):gsub("\\lstinline%b[]%b{}", blank):gsub("\\lstinline%b{}", blank):gsub("\\mintinline%b{}%b{}", blank)
  l = l:gsub("\\ac[slpf]*%*?%b{}", blank):gsub("\\[Gg]ls[%a]*%*?%b{}", blank):gsub("\\begin{tabularx}%b{}%b{}", blank):gsub("\\begin{xltabular}%b{}%b{}", blank):gsub("\\begin{tabular%*}%b{}%b{}", blank):gsub("\\begin{tabular}%b[]%b{}", blank):gsub("\\begin{tabular}%b{}", blank):gsub("\\begin{longtable}%b{}", blank)
  l = l:gsub("\\begin%b{}%b[]", blank):gsub("\\begin%b{}", blank):gsub("\\end%b{}", blank)
  l = l:gsub("\\[%a@]+%*?", blank)
  return l
end

-- A word view over the whole file, so a citation key split across lines is
-- still metadata. M.prose preserves columns as well as the source-line readers.
local word_cache = {}
function M.word_lines(file)
  if not word_cache[file] then
    local out = {}
    for l in (M.prose(table.concat(M.prose_lines(file), "\n")) .. "\n"):gmatch("([^\n]*)\n") do out[#out + 1] = l end
    word_cache[file] = out
  end
  return word_cache[file]
end

-- the template's skeleton chapters, copied into scripts/lint/skeleton by `make skeleton`: a line of
-- theirs is the template's, not the paper's, however long the skeleton chapter is
M.SKELETON = "scripts/lint/skeleton"
function M.skeleton_files()
  local out = {}
  if not M.exists(M.SKELETON) then return out end
  for e in lfs.dir(M.SKELETON) do if e:match("%.tex$") then out[#out + 1] = M.SKELETON .. "/" .. e end end
  table.sort(out)
  return out
end
function M.prose_key(l) return M.trim((M.prose(l):gsub("%s+", " "))) end
local skel_cache
function M.skeleton_lines()
  if skel_cache then return skel_cache end
  skel_cache = {}
  for _, f in ipairs(M.skeleton_files()) do
    for _, l in ipairs(M.prose_lines(f)) do
      local k = M.prose_key(l)
      if k ~= "" then skel_cache[k] = true end
    end
  end
  return skel_cache
end
-- own words of a prose line: not a TODO line, not a line of the template's skeleton
function M.own_words(l)
  if l:match("TODO") or M.skeleton_lines()[M.prose_key(l)] then return 0 end
  local n = 0
  for _ in M.prose(l):gmatch("%a%a+") do n = n + 1 end
  return n
end

return M
