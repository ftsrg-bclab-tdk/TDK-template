-- Presence checks, not measurement validation. Read literal result tables and
-- explicit siunitx quantities; never count a citation, label or setup year as a result.
local C = require("lintcore")
local T = require("texscan")
local E = require("rules-essentials")
local ALIGN = { tabular=true, ["tabular*"]=true, tabularx=true, longtable=true }
local METRIC = { time=true, runtime=true, latency=true, throughput=true, memory=true,
  accuracy=true, precision=true, recall=true, f1=true, duration=true, size=true,
  cost=true, mean=true, median=true, p95=true, p99=true, rate=true,
  ms=true, seconds=true, milliseconds=true, bytes=true, mib=true, mb=true, kb=true }
local QUANTITY = { num=1, SI=1, qty=1, numrange=2, SIrange=2, qtyrange=2 }
local function line_at(s, pos) return 1 + C.count(s:sub(1, pos - 1), "\n") end

local function undecorate(s)
  s = T.mask_calls(s, function(cmd) return cmd == "cmidrule" or cmd == "cline" or cmd == "label" end)
  s = s:gsub("\\([%a]+)", function(cmd)
    if cmd == "toprule" or cmd == "midrule" or cmd == "bottomrule" or cmd == "hline" then return " " end
  end)
  return T.unformat(s)
end

local function metric(s)
  s = undecorate(s):lower()
  for word in s:gmatch("[%w]+") do if METRIC[word] then return word end end
end

local function placeholder(s)
  if s:find("\\tbd%f[^%a]") then return true end
  local text = T.mask_calls(s, function(cmd)
    return cmd:lower():find("cite", 1, true) ~= nil or cmd:lower():find("ref", 1, true) ~= nil or T.LINK[cmd]
  end):upper()
  for _, token in ipairs({"TODO", "TBD", "XXX"}) do
    if text:find("%f[%w]" .. token .. "%f[^%w]") then return true end
  end
  return text:find("?", 1, true) ~= nil or text:find("\\dots%f[^%a]") ~= nil
    or text:find("\\ldots%f[^%a]") ~= nil or text:find("...", 1, true) ~= nil
end

local function filled(s, allow_reason)
  if placeholder(s) then return false end
  s = undecorate(s)
  -- Macro arguments of unknown commands, references, notes and URLs are not measurements.
  local values = T.mask_calls(s, function(cmd) return not QUANTITY[cmd] end)
  values = values:gsub("\\[%a@]+%*?", " ")
  if values:find("%d") then return true end -- includes zero, negative, decimal and scientific values
  local plain = C.trim(s:gsub("[{}$]", "")):lower()
  local reason = plain:match("^n/a%s*:%s*(.+)") or plain:match("^n/a%s*%((.+)%)")
    or plain:match("^not applicable%s*:%s*(.+)") or plain:match("^not measured%s*:%s*(.+)")
  return allow_reason and reason ~= nil and reason:find("%a") ~= nil
end

C.rule("evaluation-results", "source", "check", "polish",
  "evaluation measurement columns and explicit num/SI/qty values are filled, or explain unavailable results; source presence only, not numerical correctness", function()
  local cells, quantities, unsupported = 0, 0, 0
  for _, f in ipairs(C.role_files("evaluation")) do
    local text = T.mask(C.readfile(f) or "", "printed")
    text = T.mask_calls(text, function(cmd)
      return cmd == "label" or cmd:lower():find("cite", 1, true) ~= nil
        or cmd:lower():find("ref", 1, true) ~= nil or T.LINK[cmd] or cmd == "path"
    end)
    -- Explicit numerical fields also cover results written in prose, not only tables.
    local pos = 1
    while pos <= #text do
      local cmd, after = T.command(text, pos)
      if cmd then
        if QUANTITY[cmd] then
          local arg, last = T.argument(text, after)
          for n = 1, QUANTITY[cmd] do
            quantities = quantities + 1
            if not arg or not filled(arg) then
              C.fail(f, line_at(text, pos), "evaluation numerical field \\" .. cmd .. " is empty or unfinished",
                "fill the measured value; explain an unavailable result in prose instead of inventing a number")
            end
            if n < QUANTITY[cmd] and last then arg, last = T.group(text, last + 1) end
          end
        end
        pos = after
      else pos = pos + 1 end
    end
    pos = 1
    while pos <= #text do
      local a, b, env = text:find("\\begin%s*{([^}]+)}", pos)
      if not a then break end
      pos = b + 1
      if ALIGN[env] then
        local stop = text:find("\\end{" .. env .. "}", pos, true)
        local block = text:sub(a, stop and (stop + #env + 5) or #text)
        local rows, why = E.table_rows(block)
        local ln = line_at(text, a)
        if not rows then
          unsupported = unsupported + 1
          C.warn(f, ln, "evaluation table needs manual numerical review: " .. why:gsub("gap matrix", "evaluation table"))
        else
          local columns, header, count = {}, nil, 0
          for r, row in ipairs(rows) do
            if not header then
              for col, cell in ipairs(row) do columns[col] = metric(cell) end
              if next(columns) then header = r end
            else
              -- Ignore repeated literal headers, but check every data row, even the final row without \\\\.
              local repeated = true
              for col, name in pairs(columns) do if metric(row[col] or "") ~= name then repeated = false end end
              if not repeated then
                for col, name in pairs(columns) do
                  cells, count = cells + 1, count + 1
                  if not filled(row[col] or "", true) then
                    C.fail(f, ln, string.format("evaluation row %d, column %d (%s) has no filled measurement", r, col, name),
                      "replace blanks/placeholders with the result, including units; for unavailable results use N/A: <reason>; review macro-generated values manually")
                  end
                end
              end
            end
          end
          if header and count == 0 then C.fail(f, ln, "evaluation measurement table has no result rows") end
        end
        pos = stop and (stop + #env + 6) or (#text + 1)
      end
    end
  end
  local errors = false
  for _, finding in ipairs(C.findings) do if finding.level == "error" then errors = true end end
  if cells + quantities == 0 and not errors then
    C.skip("no supported measurement columns or explicit numerical fields; prose, plots and qualitative results require review")
  end
  return string.format("measurement-cells=%d numerical-fields=%d manual-tables=%d; not a check of numerical correctness", cells, quantities, unsupported)
end)

return true
