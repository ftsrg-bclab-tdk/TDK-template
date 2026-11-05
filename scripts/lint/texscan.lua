-- Bounded TeX readers, not macro expansion. All offsets are original byte offsets.
-- Supported literals: comments; standard verbatim/listing environments; verb,
-- lstinline, mintinline and texttt; url/path/href/weblink addresses; and TeX maths.
-- An unfinished literal protects the rest of the input. Masks preserve every
-- newline and byte column, so a reader's match can also locate an edit on disk.
local T = {}
local function blank(s) return (s:gsub('[^\r\n]', ' ')) end
T.blank = blank
function T.space(s, i, raw)
  i = s:match('^%s*()', math.min(i or 1, #s + 1))
  while not raw and s:sub(i, i) == '%' do
    i = s:find('\n', i, true) or (#s + 1)
    i = s:match('^%s*()', i)
  end
  return i
end
function T.command(s, i)
  if s:sub(i, i) ~= '\\' then return nil end
  local name, after = s:match('^\\([%a@]+%*?)()', i)
  if name then return name, after end
  return s:sub(i + 1, i + 1), math.min(i + 2, #s + 1)
end
-- A balanced {...} or [...] field after whitespace. Escaped braces are data;
-- braces inside [...] shield a closing bracket. Returns body, last byte, opener.
-- raw=true is for URL/verbatim arguments, where percent signs are literal.
function T.group(s, i, open, raw)
  i = T.space(s, i); open = open or '{'
  if s:sub(i, i) ~= open then return nil end
  local first, depth, braces = i, 1, 0
  local close = open == '[' and ']' or '}'
  i = i + 1
  while i <= #s do
    local c = s:sub(i, i)
    if c == '\\' then local _, after = T.command(s, i); i = after
    elseif c == '%' and not raw then i = s:find('\n', i, true) or (#s + 1)
    else
      if open == '[' and c == '{' then braces = braces + 1
      elseif open == '[' and c == '}' then braces = math.max(0, braces - 1)
      elseif braces == 0 then
        if c == open then depth = depth + 1
        elseif c == close then depth = depth - 1 end
      end
      if depth == 0 then return s:sub(first + 1, i - 1), i, first end
      i = i + 1
    end
  end
end
local CODE = { comment=true, lstlisting=true, minted=true, verbatim=true,
  ['verbatim*']=true, Verbatim=true, ['Verbatim*']=true, BVerbatim=true, LVerbatim=true, SaveVerbatim=true, alltt=true }
local MATH = { math=true, displaymath=true, equation=true, ['equation*']=true,
  align=true, ['align*']=true, alignat=true, ['alignat*']=true, flalign=true, ['flalign*']=true,
  gather=true, ['gather*']=true, multline=true, ['multline*']=true, eqnarray=true, ['eqnarray*']=true }
local PICTURE = { tikzpicture=true, axis=true, forest=true }
local NOTE = { todo=1, todoinline=1, atodo=1, advisortodo=1, guidetodo=2, beat=4, todoproof=1, todowrite=1, todoref=1, todofix=1, todoformula=1, todoidea=1 }
T.LINK = { url=true, href=true, weblink=true, nolinkurl=true }
local ADDRESS = { url=true, path=true, href=true, weblink=true, nolinkurl=true }
-- The first argument of a command, with at most two optional arguments.
function T.argument(s, i, raw)
  i = T.space(s, i)
  for _ = 1, 2 do
    if s:sub(i, i) ~= '[' then break end
    local _, e = T.group(s, i, '[', raw)
    if not e then return nil end
    i = T.space(s, e + 1)
  end
  return T.group(s, i, '{', raw)
end
local function delimited(s, i)
  i = T.space(s, i, true)
  if s:sub(i, i) == '{' then local _, e = T.group(s, i, '{', true); return e or (#s + 1) end
  local d = s:sub(i, i)
  if d == '' or d:match('%s') then return #s + 1 end
  return s:find(d, i + 1, true) or (#s + 1)
end
function T.address(s, i)
  i = T.space(s, i)
  if s:sub(i, i) == '{' then return T.group(s, i, '{', true) end
  local d = s:sub(i, i)
  if not d:match('%p') then return nil end
  local e = s:find(d, i + 1, true)
  if e then return s:sub(i + 1, e - 1), e, i end
end
local function ending(s, i, token)
  while i <= #s do
    if s:sub(i, i + #token - 1) == token then return i + #token - 1 end
    local c = s:sub(i, i)
    if c == '%' then i = s:find('\n', i, true) or (#s + 1)
    elseif c == '\\' then local _, after = T.command(s, i); i = after
    else i = i + 1 end
  end
  return #s + 1
end
-- Main's bounded \iffalse reader stops at the first literal \fi command.
-- Tokenize the delimiter so \figure and commented-out \fi cannot close it.
local function false_ending(s, i)
  while i <= #s do
    local c = s:sub(i, i)
    if c == '%' then i = s:find('\n', i, true) or (#s + 1)
    elseif c == '\\' then
      local name, after = T.command(s, i)
      if name == 'fi' then return after - 1 end
      i = after
    else i = i + 1 end
  end
  return #s + 1
end
-- mode: fix/prose protect literals, drawings and notes; printed
-- retains mathematics and link commands (but never inline code or notes).
function T.spans(s, mode, skip)
  mode = mode or 'fix'
  -- Settings must still see conditional declarations and reject them explicitly.
  local settings = mode == 'settings'
  if settings then mode = 'printed' end
  local spans, i = {}, 1
  local function add(a, b) if b >= a then spans[#spans + 1] = {a, b} end end
  while i <= #s do
    local c, stop, hide = s:sub(i, i), nil, false
    if c == '%' then stop, hide = (s:find('\n', i, true) or (#s + 1)) - 1, true
    elseif c == '$' and mode ~= 'printed' and mode ~= 'comments' then
      local token = s:sub(i, i + 1) == '$$' and '$$' or '$'
      stop, hide = ending(s, i + #token, token), true
    elseif c == '\\' then
      local name, after = T.command(s, i)
      local bare = name:gsub('%*$', '')
      if name == 'iffalse' and mode ~= 'comments' and not settings then
        stop, hide = false_ending(s, after), true
      elseif name == 'begin' then
        local env, e = T.group(s, after)
        if env and (CODE[env] or (mode ~= 'printed' and mode ~= 'comments' and (MATH[env] or PICTURE[env])) or (skip and skip[env])) then
          local token = '\\end{' .. env .. '}'
          local p = CODE[env] and s:find(token, e + 1, true)
          stop = CODE[env] and (p and (p + #token - 1) or (#s + 1)) or ending(s, e + 1, token)
          hide = mode ~= 'comments'
        end
      elseif (name == '(' or name == '[') and mode ~= 'printed' and mode ~= 'comments' then
        stop, hide = ending(s, after, name == '(' and '\\)' or '\\]'), true
      elseif bare == 'verb' then stop, hide = delimited(s, after), mode ~= 'comments'
      elseif bare == 'lstinline' or bare == 'mintinline' or bare == 'mint' then
        local at = T.space(s, after)
        if s:sub(at, at) == '[' then local _, e = T.group(s, at, '['); at = e and T.space(s, e + 1) or (#s + 1) end
        if bare == 'mintinline' or bare == 'mint' then local _, e = T.group(s, at); at = e and T.space(s, e + 1) or (#s + 1) end
        stop, hide = delimited(s, at), mode ~= 'comments'
      elseif bare == 'includegraphics' or bare == 'includesvg' or bare == 'lstinputlisting' or bare == 'verbatiminput' or bare == 'inputminted' then
        local _, e = T.argument(s, after, true)
        if e and bare == 'inputminted' then local _, last = T.group(s, e + 1, '{', true); e = last end
        stop, hide = e or (#s + 1), mode ~= 'printed' and mode ~= 'comments'
      elseif bare == 'texttt' then
        local _, e = T.group(s, after); stop, hide = e or (#s + 1), mode ~= 'comments'
      elseif ADDRESS[bare] then
        local at = T.space(s, after)
        stop, hide = delimited(s, at), mode ~= 'printed' and mode ~= 'comments'
      elseif NOTE[bare] and mode ~= 'comments' then
        local at = T.space(s, after)
        if s:sub(at, at) == '[' then local _, e = T.group(s, at, '['); at = e and T.space(s, e + 1) or (#s + 1) end
        for _ = 1, NOTE[bare] do
          local _, e = T.group(s, at)
          stop = e or (#s + 1); at = T.space(s, stop + 1)
        end
        hide = true
      end
      if not stop then i = after end
    else i = i + 1 end
    if stop then if hide then add(i, stop) end; i = stop + 1 end
  end
  return spans
end
function T.mask(s, mode, skip)
  local out, prev = {}, 1
  for _, sp in ipairs(T.spans(s, mode, skip)) do
    out[#out + 1] = s:sub(prev, sp[1] - 1); out[#out + 1] = blank(s:sub(sp[1], sp[2])); prev = sp[2] + 1
  end
  out[#out + 1] = s:sub(prev)
  return table.concat(out)
end
function T.overlaps(spans, first, last)
  for _, sp in ipairs(spans) do if first <= sp[2] and last >= sp[1] then return true end end
  return false
end
-- Mask complete calls selected by the caller, including multiline optional
-- arguments. Used for citation keys when measuring or fixing prose words.
function T.mask_calls(s, want)
  local out, i, prev = {}, 1, 1
  while i <= #s do
    if s:sub(i, i) ~= "\\" then i = i + 1
    else
      local name, after = T.command(s, i)
      local _, e = T.argument(s, after)
      if want(name) and e then
        out[#out + 1] = s:sub(prev, i - 1) .. blank(s:sub(i, e))
        i, prev = e + 1, e + 1
      else i = after end
    end
  end
  out[#out + 1] = s:sub(prev)
  return table.concat(out)
end
-- Strip only known presentational wrappers, preserving positions for diagnostics.
-- Unknown macros are intentionally not expanded.
function T.unformat(s)
  local formatting = { emph=true, enquote=true, textit=true, textbf=true, textnormal=true, textrm=true, textsf=true, textup=true }
  local out, i, prev = {}, 1, 1
  while i <= #s do
    if s:sub(i, i) == '\\' then
      local name, after = T.command(s, i)
      local body, e, start = T.group(s, after)
      if formatting[name] and e then
        out[#out + 1] = s:sub(prev, i - 1) .. blank(s:sub(i, start)) .. T.unformat(body) .. ' '
        i, prev = e + 1, e + 1
      else i = after end
    else i = i + 1 end
  end
  out[#out + 1] = s:sub(prev)
  return table.concat(out)
end
return T
