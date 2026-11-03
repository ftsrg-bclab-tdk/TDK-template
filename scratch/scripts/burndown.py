#!/usr/bin/env python3
"""Append the paper's burn-down counts to burndown.csv and redraw burndown.svg.

Reads one JSON line from stdin, the output of `texlua scripts/lint.lua burndown` run in paper/.
Keeps one row per day. The chart is plain SVG, no dependencies.
"""
import csv, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "burndown.csv"); SVG = os.path.join(ROOT, "burndown.svg")
FIELDS = ["date", "pages", "todo", "beats", "notes", "placeholders", "citations", "figures"]

def main():
    data = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
    line = data.splitlines()[-1] if data else ""
    rows = list(csv.DictReader(open(CSV, encoding="utf-8"))) if os.path.exists(CSV) else []
    if line:
        rec = json.loads(line)
        rows = [r for r in rows if r["date"] != rec["date"]] + [{k: str(rec.get(k, "")) for k in FIELDS}]
    with open(CSV, "w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, FIELDS); w.writeheader(); w.writerows(rows)
    W, H, L, B = 720, 300, 50, 40
    series = [("todo", "#c8503c"), ("beats", "#e69f00"), ("placeholders", "#8064a2"), ("pages", "#2e7d32")]
    ymax = max([int(r[k] or 0) for r in rows for k, _ in series] + [35])
    n = max(len(rows), 2)
    def x(i): return L + (W - L - 20) * i / (n - 1)
    def y(v): return H - B - (H - B - 20) * v / ymax
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif" font-size="12">',
           f'<rect width="{W}" height="{H}" fill="white"/>',
           f'<line x1="{L}" y1="{H-B}" x2="{W-20}" y2="{H-B}" stroke="#888"/>',
           f'<line x1="{L}" y1="20" x2="{L}" y2="{H-B}" stroke="#888"/>',
           f'<line x1="{L}" y1="{y(30):.1f}" x2="{W-20}" y2="{y(30):.1f}" stroke="#2e7d32" stroke-dasharray="4 4"/>',
           f'<line x1="{L}" y1="{y(35):.1f}" x2="{W-20}" y2="{y(35):.1f}" stroke="#2e7d32" stroke-dasharray="4 4"/>',
           f'<text x="{W-18}" y="{y(35)-3:.1f}" fill="#2e7d32" text-anchor="end">30-35 pages</text>',
           f'<text x="{L-6}" y="{y(ymax)+4:.1f}" text-anchor="end">{ymax}</text><text x="{L-6}" y="{H-B+4}" text-anchor="end">0</text>']
    for k, c in series:
        pts = " ".join(f"{x(i):.1f},{y(int(r[k] or 0)):.1f}" for i, r in enumerate(rows))
        if rows: out.append(f'<polyline fill="none" stroke="{c}" stroke-width="2" points="{pts}"/>')
    lx = L + 10
    for k, c in series:
        out.append(f'<rect x="{lx}" y="{H-18}" width="12" height="12" fill="{c}"/><text x="{lx+16}" y="{H-8}">{k}</text>'); lx += 110
    if rows:
        out.append(f'<text x="{L}" y="14">{rows[0]["date"]}</text><text x="{W-20}" y="14" text-anchor="end">{rows[-1]["date"]}</text>')
    out.append("</svg>")
    open(SVG, "w", encoding="utf-8").write("\n".join(out))
    print(f"{len(rows)} rows")

if __name__ == "__main__":
    main()
