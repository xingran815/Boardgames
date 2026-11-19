#!/usr/bin/env python3
"""Build the full-colour, printable rules manual for Azul.

    python3 tools/build_azul_color_manual.py

* Every picture (tiles, walls, pattern lines, factory displays, boards) is
  drawn as inline SVG by this script, with the original tile designs, colours
  and component styling of docs/azul/STYLE.md (as in tools/azul/render.py).
  No image files are needed.
* Every number is computed with tools/azul/engine.py (loaded by path, because
  tests/conftest.py maps the name `engine` to Spirits of the Wild) and the
  script asserts that each figure agrees with the text next to it.
* One HTML section per A4 page (mirrored inner/outer margins for double-sided
  printing, even page count), printed to docs/azul/manual-color.pdf with
  Chromium through the node `playwright` module. Pages whose content overflows
  their box are reported as warnings (the build exits non-zero if any).

Content follows docs/azul/manual.md and docs/azul/quick-reference.md.
Requires node + playwright (Chromium). Fonts: Cinzel and Caladea from tools/azul/fonts
(SIL OFL), embedded with @font-face.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import math
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "azul"
OUT_PDF = DOCS / "manual-color.pdf"

_spec = importlib.util.spec_from_file_location("azul_engine", ROOT / "tools" / "azul" / "engine.py")
E = importlib.util.module_from_spec(_spec)
sys.modules["azul_engine"] = E
_spec.loader.exec_module(E)

# ================================================================ palette (docs/azul/STYLE.md)
PARCH, CREAM, SAND, TRAY = "#EFE4CF", "#FAF5EA", "#EAD9BE", "#E6D6B8"
NAVY, COBALT, SKY = "#1E3A72", "#2C5AA8", "#9CC0E3"
GOLD, GOLD_LT, OCHRE = "#C08A2E", "#F4CD78", "#F1B852"
RED, HL = "#9E2A22", "#B32A1E"
INK, BROWN = "#1B2A4E", "#68543C"
SLOT, RIM = "#BE9C68", "#B05E34"          # gold-tan slot edge, terracotta factory rim
LIGHT = "#F6EEDD"                          # light parchment (centre of the table, table area)
GREY_SPACE, GREY_EDGE = "#C4BEB4", "#9E968A"
SERIF = "Caladea, 'DejaVu Serif', 'DejaVu Sans', serif"
DISPLAY = "Cinzel, 'DejaVu Serif', serif"

# ================================================================ tiles
FILL = {"B": "#2F62AC", "Y": "#E9A238", "R": "#D2492F", "K": "#24272F", "W": "#F4EFE2"}
EDGE = {"B": "#1A3A6E", "Y": "#9C6214", "R": "#822819", "K": "#0C0E12", "W": "#8FA8C4"}
MARK_INK = {"B": "#B4D4F2", "Y": "#C23E1E", "R": "#F8DCC4", "K": "#6CACCC", "W": "#5E9ACE"}
LETTER_INK = {"B": "#FFFFFF", "Y": "#5A2C00", "R": "#FFFFFF", "K": "#E8EEF4", "W": NAVY}
NAME = {"B": "blue", "Y": "yellow", "R": "red", "K": "black", "W": "white"}
LET = {v: k for k, v in NAME.items()}          # colour name -> letter
LETTERS = "BYRKW"
assert [E.LETTERS[c] for c in E.COLOURS] == list(LETTERS)


def L(c):
    """Engine colour name or letter -> letter."""
    return LET.get(c, c)


def mix(a, b, t):
    """Blend hex colour a towards b by t (0 = a, 1 = b)."""
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(pa, pb))


def _pts(pts):
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)


def diamond(cx, cy, r, fill):
    return f'<polygon fill="{fill}" points="{_pts([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)])}"/>'


def star8(cx, cy, ro, ri, fill, rot=0.0):
    pts = [(cx + (ro if i % 2 == 0 else ri) * math.cos(rot - math.pi / 2 + i * math.pi / 8),
            cy + (ro if i % 2 == 0 else ri) * math.sin(rot - math.pi / 2 + i * math.pi / 8)) for i in range(16)]
    return f'<polygon fill="{fill}" points="{_pts(pts)}"/>'


def mark(cx, cy, s, c, ink, bg):
    """Original geometric motif of each colour (as in tools/azul/render.py)."""
    if c == "B":       # ring with a centre dot
        return (f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{s*.19:.2f}" fill="none" stroke="{ink}" stroke-width="{s*.065:.2f}"/>'
                f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{s*.065:.2f}" fill="{ink}"/>')
    if c == "Y":       # four-petal rosette with four dots
        o, r, q, rr = s * .13, s * .105, s * .17, s * .035
        g = "".join(f'<circle cx="{cx+dx*o:.2f}" cy="{cy+dy*o:.2f}" r="{r:.2f}" fill="{ink}"/>'
                    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)))
        g += "".join(f'<circle cx="{cx+dx*q:.2f}" cy="{cy+dy*q:.2f}" r="{rr:.2f}" fill="{ink}"/>'
                     for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)))
        return g + f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{s*.055:.2f}" fill="{bg}"/>'
    if c == "R":       # diamond with a diamond window
        return diamond(cx, cy, s * .23, ink) + diamond(cx, cy, s * .09, bg)
    if c == "K":       # lattice: plus sign and four small diamonds
        a, t = s * .22, s * .05
        g = (f'<rect x="{cx-a:.2f}" y="{cy-t:.2f}" width="{2*a:.2f}" height="{2*t:.2f}" fill="{ink}"/>'
             f'<rect x="{cx-t:.2f}" y="{cy-a:.2f}" width="{2*t:.2f}" height="{2*a:.2f}" fill="{ink}"/>')
        return g + "".join(diamond(cx + dx * s * .17, cy + dy * s * .17, s * .055, ink)
                           for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)))
    # W: eight-ray star of slim rhombi
    ro, hw, g = s * .31, s * .06, []
    for i in range(8):
        a = i * math.pi / 4
        ux, uy = math.cos(a), math.sin(a)
        px, py = -uy, ux
        mx, my = cx + ux * ro * .5, cy + uy * ro * .5
        g.append(f'<polygon fill="{ink}" points="{_pts([(cx + ux*s*.05, cy + uy*s*.05), (mx + px*hw, my + py*hw), (cx + ux*ro, cy + uy*ro), (mx - px*hw, my - py*hw)])}"/>')
    return "".join(g) + f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{s*.05:.2f}" fill="{ink}"/>'


def tile(x, y, s, c, faint=False, letter=True, base=TRAY):
    """One tile with its top-left corner at (x, y), side s. faint=True: an untiled wall
    space (the colour at about 35% strength on `base`, same motif)."""
    c = L(c)
    rad = s * .12
    fill, edge, ink = FILL[c], EDGE[c], MARK_INK[c]
    cx, cy = x + s / 2, y + s / 2
    if faint:
        fill = mix(base, fill, .36)
        ink = mix(base, NAVY if c == "W" else ink, .4)
        edge = mix(base, edge, .45)
        g = (f'<rect x="{x:.2f}" y="{y:.2f}" width="{s:.2f}" height="{s:.2f}" rx="{rad:.2f}" fill="{fill}" '
             f'stroke="{edge}" stroke-width="{s*.03:.2f}"/>')
        g += mark(cx, cy, s, c, ink, fill)
        if letter:
            g += (f'<text x="{x+s*.09:.2f}" y="{y+s*.9:.2f}" font-size="{s*.24:.2f}" font-weight="700" '
                  f'fill="{mix(base, BROWN, .7)}">{c}</text>')
        return g
    g = (f'<rect x="{x:.2f}" y="{y:.2f}" width="{s:.2f}" height="{s:.2f}" rx="{rad:.2f}" fill="{fill}" '
         f'stroke="{edge}" stroke-width="{s*.045:.2f}"/>'
         f'<rect x="{x+s*.1:.2f}" y="{y+s*.07:.2f}" width="{s*.8:.2f}" height="{s*.08:.2f}" rx="{s*.04:.2f}" '
         f'fill="{mix(fill, "#FFFFFF", .22)}"/>'
         f'<rect x="{cx-s*.36:.2f}" y="{cy-s*.36:.2f}" width="{s*.72:.2f}" height="{s*.72:.2f}" rx="{s*.05:.2f}" '
         f'fill="none" stroke="{mix(fill, ink, .45)}" stroke-width="{s*.022:.2f}"/>')
    g += mark(cx, cy, s, c, ink, fill)
    if letter:
        g += (f'<text x="{x+s*.09:.2f}" y="{y+s*.92:.2f}" font-size="{s*.24:.2f}" font-weight="700" '
              f'fill="{LETTER_INK[c]}">{c}</text>')
    return g


def marker(x, y, s):
    """Starting player marker: a cream tile in a deep-blue frame with the numeral 1."""
    return (f'<rect x="{x:.2f}" y="{y:.2f}" width="{s:.2f}" height="{s:.2f}" rx="{s*.12:.2f}" fill="#FBF8EF" '
            f'stroke="{NAVY}" stroke-width="{s*.07:.2f}"/>'
            f'<rect x="{x+s*.15:.2f}" y="{y+s*.15:.2f}" width="{s*.7:.2f}" height="{s*.7:.2f}" rx="{s*.08:.2f}" '
            f'fill="none" stroke="{COBALT}" stroke-width="{s*.03:.2f}"/>'
            f'<text x="{x+s/2:.2f}" y="{y+s*.69:.2f}" font-size="{s*.5:.2f}" font-family="{DISPLAY}" font-weight="700" '
            f'text-anchor="middle" fill="{NAVY}">1</text>')


def hole(x, y, s, floor=False):
    """Empty pattern-line slot (sand, gold-tan edge) or floor-line slot (cobalt edge)."""
    return (f'<rect x="{x:.2f}" y="{y:.2f}" width="{s:.2f}" height="{s:.2f}" rx="{s*.12:.2f}" '
            f'fill="{"#EEE6D6" if floor else SAND}" stroke="{COBALT if floor else SLOT}" stroke-width="{s*.05:.2f}"/>')


def item(x, y, s, it):
    """Floor-line item: a tile letter, the marker ("1") or an empty floor space."""
    if it == "1":
        return marker(x, y, s)
    return tile(x, y, s, it) if it else hole(x, y, s, floor=True)


def svg(w, h, body, cls="fig"):
    return (f'<svg class="{cls}" viewBox="0 0 {w:.1f} {h:.1f}" xmlns="http://www.w3.org/2000/svg" '
            f'font-family="{SERIF}">{body}</svg>')


def T(c, cls="it"):
    """Inline tile for running text."""
    return svg(40, 40, tile(2, 2, 36, c), cls)


def Ts(s):
    return "".join(T(c) for c in s)


def txt(x, y, s, size=14, fill=INK, weight=700, anchor="start", font=None):
    fam = f' font-family="{DISPLAY}"' if font == "display" else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:.1f}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}"{fam}>{s}</text>')


def badge(x, y, n, r=13, fill=NAVY):
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{GOLD_LT}" stroke-width="2"/>'
            f'<text x="{x}" y="{y+r*.4:.1f}" font-size="{r*1.2:.1f}" font-weight="700" fill="#FFFFFF" '
            f'text-anchor="middle">{n}</text>')


def ring(x, y, s, w=.11):
    """Highlight-red frame around a tile (like the rulebook's red frames)."""
    return (f'<rect x="{x-s*.1:.2f}" y="{y-s*.1:.2f}" width="{s*1.2:.2f}" height="{s*1.2:.2f}" rx="{s*.2:.2f}" '
            f'fill="none" stroke="{HL}" stroke-width="{s*w:.2f}"/>')


def frame(x0, y0, x1, y1, r=10, w=2.2, fill=CREAM):
    """Cream panel in a deep-blue frame with a thin ochre-gold inner line."""
    g = w + 2.2
    return (f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1-x0:.1f}" height="{y1-y0:.1f}" rx="{r}" fill="{fill}" '
            f'stroke="{NAVY}" stroke-width="{w}"/>'
            f'<rect x="{x0+g:.1f}" y="{y0+g:.1f}" width="{x1-x0-2*g:.1f}" height="{y1-y0-2*g:.1f}" rx="{max(2, r-g):.1f}" '
            f'fill="none" stroke="{GOLD}" stroke-width="{w*.45:.2f}"/>')


def azulejo(cx, cy, s, kind, bg=SKY, ink=NAVY):
    """One small decorative wall tile (original geometric patterns) for borders."""
    x0, y0 = cx - s / 2, cy - s / 2
    g = f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{s:.2f}" height="{s:.2f}" fill="{bg}"/>'
    if kind == 0:
        g += star8(cx, cy, s * .42, s * .2, ink) + f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{s*.08:.2f}" fill="{bg}"/>'
    elif kind == 1:
        q, x1, y1 = s * .32, x0 + s, y0 + s
        for (x, y), (sx, sy) in (((x0, y0), (1, 1)), ((x1, y0), (-1, 1)), ((x0, y1), (1, -1)), ((x1, y1), (-1, -1))):
            g += f'<polygon fill="{ink}" points="{_pts([(x, y), (x + sx*q, y), (x, y + sy*q)])}"/>'
        g += diamond(cx, cy, s * .22, ink)
    else:
        r = s * .13
        g += "".join(f'<circle cx="{cx+dx*s*.2:.2f}" cy="{cy+dy*s*.2:.2f}" r="{r:.2f}" fill="{ink}"/>'
                     for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)))
        g += f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r*.6:.2f}" fill="{bg}"/>'
    return g


def azulejo_band(n, s=20):
    """A light strip of n small azulejo tiles between thin gold rules (print-friendly)."""
    b = []
    for i in range(n):
        bg, ink = (CREAM, COBALT) if i % 2 else (SKY, NAVY)
        b.append(azulejo(i * s + s / 2, s / 2 + 2, s - 1, i % 3, bg=bg, ink=ink))
    b.append(f'<line x1="0" y1="1" x2="{n*s}" y2="1" stroke="{GOLD}" stroke-width="1.2"/>'
             f'<line x1="0" y1="{s+3}" x2="{n*s}" y2="{s+3}" stroke="{GOLD}" stroke-width="1.2"/>')
    return svg(n * s, s + 4, "".join(b), "band")


# ================================================================ drawings
GAP = 0.12  # gap between cells, as a fraction of the cell size


def wall_cells(wall, c, x, y, hl=None, grey=False, options=(), tray=True):
    """SVG body for the 5x5 wall on its stone tray; returns (body, size)."""
    st = c * (1 + GAP)
    hl = hl or {}
    size = 5 * st - c * GAP
    b = []
    if tray:
        m = c * .08
        b.append(f'<rect x="{x-m:.2f}" y="{y-m:.2f}" width="{size+2*m:.2f}" height="{size+2*m:.2f}" rx="{c*.2:.2f}" '
                 f'fill="{TRAY}" stroke="{GOLD}" stroke-width="{c*.03:.2f}"/>')
    for r in range(5):
        for k in range(5):
            xx, yy = x + k * st, y + r * st
            if hl.get((r, k)) == "run":
                b.append(f'<rect x="{xx-c*.11:.2f}" y="{yy-c*.11:.2f}" width="{c*1.22:.2f}" height="{c*1.22:.2f}" '
                         f'rx="{c*.2:.2f}" fill="{GOLD}"/>')
            t = wall[r][k]
            if t:
                b.append(tile(xx, yy, c, t))
            elif grey:
                b.append(f'<rect x="{xx:.2f}" y="{yy:.2f}" width="{c}" height="{c}" rx="{c*.12:.2f}" fill="{GREY_SPACE}" '
                         f'stroke="{GREY_EDGE}" stroke-width="{c*.04:.2f}"/>')
            else:
                b.append(tile(xx, yy, c, E.LETTERS[E.wall_colour(r, k)], faint=True))
            if (r, k) in options:
                b.append(f'<rect x="{xx-c*.05:.2f}" y="{yy-c*.05:.2f}" width="{c*1.1:.2f}" height="{c*1.1:.2f}" rx="{c*.18:.2f}" '
                         f'fill="none" stroke="{NAVY}" stroke-width="{c*.1:.2f}" stroke-dasharray="{c*.2:.2f} {c*.12:.2f}"/>')
            if hl.get((r, k)) == "new":
                b.append(ring(xx, yy, c, .11))
    return "".join(b), size


def board(x, y, c, lines=(), wall=None, floor=(), hl=None, grey=False, marks=None):
    """Draw a player board area (pattern lines, wall and floor line).

    lines  5 items (letter|None, count); filled from the right
    wall   5x5 grid of engine colour names / None (placed tiles)
    floor  up to 7 items: letters, or "1" for the starting player marker
    hl     {(r, col): 'new' | 'run'} highlights on the wall
    marks  {line_index: 'ok'|'no'} badge to the left of a pattern line
    Returns (svg-body, width, height).
    """
    st = c * (1 + GAP)
    wall = wall or E.empty_wall()
    b = []
    px = x + c * 0.9
    for i in range(5):
        yy = y + i * st
        b.append(txt(x + c * .25, yy + c * .68, i + 1, c * .5, BROWN, 700, "middle"))
        if marks and i in marks:
            ok = marks[i] == "ok"
            cx, cy = x - c * .85, yy + c / 2
            b.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{c*.3:.2f}" fill="{NAVY if ok else HL}"/>'
                     + txt(cx, cy + c * .15, "&#10003;" if ok else "&#10007;", c * .42, "#FFFFFF", 700, "middle"))
        col, n = lines[i] if i < len(lines) else (None, 0)
        for j in range(i + 1):
            xx = px + (4 - j) * st
            b.append(tile(xx, yy, c, col) if j < n else hole(xx, yy, c))
    ax = px + 5 * st + c * .1
    for i in range(5):
        yy = y + i * st + c / 2
        b.append(f'<polygon fill="{NAVY}" points="{_pts([(ax, yy - c*.2), (ax + c*.36, yy), (ax, yy + c*.2)])}"/>')
    wx = px + 5 * st + c * .65
    wb, _ = wall_cells(wall, c, wx, y, hl, grey)
    b.append(wb)
    fy = y + 5 * st + c * .35
    for k in range(7):
        xx = px + k * st
        b.append(item(xx, fy, c, floor[k] if k < len(floor) else None))
        b.append(txt(xx + c / 2, fy + c * 1.42, f"&minus;{abs(E.FLOOR_VALUES[k])}", c * .46, RED, 700, "middle"))
    return "".join(b), (wx + 5 * st) - x, (fy + c * 1.7) - y


def board_panel(x, y, c, name=None, score=0, pad=None, **kw):
    """A board in its frame: cream surface, deep-blue frame with a gold inner line and, when
    `name` is given, a deep-blue header band with the name and the 0-100 score track.
    (x, y) is the top-left of the frame. Returns (body, width, height, extra) where extra
    holds the positions of the parts (for numbered badges)."""
    pad = c * .55 if pad is None else pad
    hdr = c * 1.05 if name else 0
    inner, w, h = board(x + pad, y + pad + hdr, c, **kw)
    W, H = w + 2 * pad - c * GAP, h + 2 * pad + hdr - c * .2
    b = [frame(x, y, x + W, y + H, r=c * .35, w=max(1.6, c * .07))]
    info = {"lines": (x + pad, y + pad + hdr), "floor_y": y + pad + hdr + 5 * c * (1 + GAP) + c * .35}
    if name:
        bw = max(1.6, c * .07)
        b.append(f'<path d="M{x+bw/2:.1f} {y+hdr+bw/2:.1f} V{y+c*.35:.1f} q0 {-c*.35+bw/2:.1f} {c*.35:.1f} {-c*.35+bw/2:.1f} '
                 f'H{x+W-c*.35:.1f} q{c*.35-bw/2:.1f} 0 {c*.35-bw/2:.1f} {c*.35:.1f} V{y+hdr+bw/2:.1f} Z" fill="{NAVY}"/>')
        b.append(f'<line x1="{x+bw/2:.1f}" y1="{y+hdr+bw/2:.1f}" x2="{x+W-bw/2:.1f}" y2="{y+hdr+bw/2:.1f}" '
                 f'stroke="{GOLD}" stroke-width="{bw*.6:.2f}"/>')
        b.append(txt(x + pad, y + hdr * .68, name, c * .5, CREAM, 700, font="display"))
        tx0, tx1, ty = x + W * .38, x + W - c * 2.4, y + hdr * .5
        b.append(f'<rect x="{tx0:.1f}" y="{ty-c*.12:.1f}" width="{tx1-tx0:.1f}" height="{c*.24:.1f}" rx="{c*.12:.1f}" '
                 f'fill="#3A5C96" stroke="{SKY}" stroke-width="{c*.04:.2f}"/>')
        for v in range(0, 101, 10):
            t = tx0 + (tx1 - tx0) * v / 100
            b.append(f'<line x1="{t:.1f}" y1="{ty-c*.08:.1f}" x2="{t:.1f}" y2="{ty+c*.08:.1f}" stroke="{SKY}" stroke-width="{c*.04:.2f}"/>')
        b.append(txt(tx0 - c * .2, ty + c * .14, "0", c * .38, SKY, 700, "end"))
        b.append(txt(tx1 + c * .15, ty + c * .14, "100", c * .38, SKY, 700))
        mx = tx0 + (tx1 - tx0) * min(score, 100) / 100
        b.append(f'<rect x="{mx-c*.2:.1f}" y="{ty-c*.2:.1f}" width="{c*.4:.1f}" height="{c*.4:.1f}" fill="#121216" '
                 f'stroke="{CREAM}" stroke-width="{c*.04:.2f}"/>')
        b.append(f'<rect x="{x+W-c*1.25:.1f}" y="{y+hdr*.14:.1f}" width="{c*.95:.1f}" height="{hdr*.72:.1f}" rx="{c*.15:.1f}" '
                 f'fill="{OCHRE}" stroke="{GOLD_LT}" stroke-width="{c*.04:.2f}"/>')
        b.append(txt(x + W - c * .775, y + hdr * .68, score, c * .5, INK, 700, "middle"))
        info.update(track=((tx0 + tx1) / 2, ty), cube=(mx, ty))
    b.append(inner)
    return "".join(b), W, H, info


def run_cells(wall, r, k):
    """Cells counted when a tile is placed at (r, k) (the tile itself included)."""
    cells = {(r, k)}
    for dr, dk in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        rr, kk = r + dr, k + dk
        while 0 <= rr < 5 and 0 <= kk < 5 and wall[rr][kk]:
            cells.add((rr, kk))
            rr, kk = rr + dr, kk + dk
    return cells


def factory(cx, cy, r, tiles=(), hl=()):
    """Factory display: terracotta rim, cream ring with deep-blue beads, a gold ring and a
    cobalt centre with light rays; up to 4 tiles in a 2x2 block on top."""
    b = [f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{RIM}" stroke="{mix(RIM, "#3C140A", .35)}" stroke-width="{r*.03:.2f}"/>',
         f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r*.88:.1f}" fill="#F2E6D0"/>']
    for i in range(16):
        a = i * math.pi / 8
        bx_, by_ = cx + r * .72 * math.cos(a), cy + r * .72 * math.sin(a)
        if i % 2:
            b.append(f'<circle cx="{bx_:.2f}" cy="{by_:.2f}" r="{r*.055:.2f}" fill="{NAVY}"/>')
        else:
            b.append(f'<circle cx="{bx_:.2f}" cy="{by_:.2f}" r="{r*.075:.2f}" fill="none" stroke="{NAVY}" stroke-width="{r*.025:.2f}"/>')
    b.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r*.56:.2f}" fill="{GOLD}"/>'
             f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r*.5:.2f}" fill="{NAVY}"/>'
             f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r*.44:.2f}" fill="{COBALT}"/>')
    for i in range(24):
        a = i * math.pi / 12
        b.append(f'<line x1="{cx+r*.1*math.cos(a):.2f}" y1="{cy+r*.1*math.sin(a):.2f}" x2="{cx+r*.42*math.cos(a):.2f}" '
                 f'y2="{cy+r*.42*math.sin(a):.2f}" stroke="{SKY}" stroke-width="{r*.018:.2f}"/>')
    b.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r*.09:.2f}" fill="#F2E6D0" stroke="{GOLD}" stroke-width="{r*.02:.2f}"/>')
    ts = r * .6
    g = ts * .08
    pos = [(-ts - g / 2, -ts - g / 2), (g / 2, -ts - g / 2), (-ts - g / 2, g / 2), (g / 2, g / 2)]
    for i, t in enumerate(tiles):
        px, py = cx + pos[i][0], cy + pos[i][1]
        if i in hl:
            b.append(ring(px, py, ts))
        b.append(tile(px, py, ts, t))
    return "".join(b)


def centre_area(x, y, w, h):
    """The centre of the table: a lighter parchment area with a thin gold-tan edge."""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{LIGHT}" '
            f'stroke="{SLOT}" stroke-width="1.6"/>')


def centre_tiles(x, y, w, tiles, ts, hl=(), marker_first=False):
    """Loose tiles in the centre of the table, in a wrapped row."""
    b, per = [], max(1, int(w // (ts * 1.12)))
    items = (["1"] if marker_first else []) + list(tiles)
    for i, t in enumerate(items):
        px, py = x + (i % per) * ts * 1.12, y + (i // per) * ts * 1.12
        if t == "1":
            b.append(marker(px, py, ts))
        else:
            if i in hl:
                b.append(ring(px, py, ts))
            b.append(tile(px, py, ts, t))
    return "".join(b)


def bag(cx, top, w):
    """Cloth bag: washed cotton blue with a cream print of small stars and diamonds, a cream
    drawstring and a cream label plaque. Returns (body, (label_x, label_y))."""
    blue, prt = "#4F7CBE", "#E4EAF0"
    ex0, ex1, ey0, ey1 = cx - w / 2, cx + w / 2, top + w * .27, top + w * 1.15
    ecx, ecy, rx, ry = cx, (ey0 + ey1) / 2, w / 2, (ey1 - ey0) / 2
    b = [f'<polygon fill="{blue}" points="{_pts([(cx - w*.27, top + w*.36), (cx - w*.17, top + w*.18), (cx + w*.17, top + w*.18), (cx + w*.27, top + w*.36)])}"/>']
    b += [f'<circle cx="{cx + k*w*.042:.1f}" cy="{top + w*.17:.1f}" r="{w*.035:.1f}" fill="{blue}"/>' for k in range(-4, 5)]
    b.append(f'<ellipse cx="{ecx:.1f}" cy="{ecy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{blue}" stroke="{mix(blue, NAVY, .5)}" stroke-width="1.5"/>')
    for j in range(-4, 5):
        for i in range(-5, 6):
            px, py = ecx + i * w * .12 + (w * .06 if j % 2 else 0), ecy + j * w * .11
            if ((px - ecx) / (rx - 10)) ** 2 + ((py - ecy) / (ry - 10)) ** 2 > 1:
                continue
            b.append(star8(px, py, w * .034, w * .015, prt) if (i + j) % 2 else diamond(px, py, w * .018, prt))
    for k in (-2, -1, 1, 2):
        b.append(f'<line x1="{cx + k*w*.05:.1f}" y1="{top + w*.2:.1f}" x2="{cx + k*w*.085:.1f}" y2="{top + w*.35:.1f}" '
                 f'stroke="{mix(blue, NAVY, .45)}" stroke-width="1.5"/>')
    b.append(f'<rect x="{cx - w*.2:.1f}" y="{top + w*.24:.1f}" width="{w*.4:.1f}" height="{w*.04:.1f}" rx="2" fill="{prt}"/>')
    for sx in (-1, 1):
        b.append(f'<ellipse cx="{cx + sx*w*.09:.1f}" cy="{top + w*.26:.1f}" rx="{w*.055:.1f}" ry="{w*.045:.1f}" '
                 f'fill="none" stroke="{prt}" stroke-width="3"/>')
    b.append(f'<path d="M{cx-2:.1f} {top + w*.27:.1f} l{-w*.05:.1f} {w*.11:.1f} M{cx+2:.1f} {top + w*.27:.1f} l{w*.06:.1f} {w*.1:.1f}" '
             f'stroke="{prt}" stroke-width="3" fill="none"/>')
    ly = ecy - w * .12
    b.append(frame(cx - w * .32, ly - w * .17, cx + w * .32, ly + w * .2, r=7, w=2))
    return "".join(b), (cx, ly)


def box_lid(x, y, w, h):
    """Box lid: deep blue with a light-blue inner line and a sand well for the tiles."""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{NAVY}"/>'
            f'<rect x="{x+4}" y="{y+4}" width="{w-8}" height="{h-8}" rx="9" fill="none" stroke="{SKY}" stroke-width="1.5"/>'
            f'<rect x="{x+10}" y="{y+h*.45}" width="{w-20}" height="{h*.55-10}" rx="8" fill="{SAND}" stroke="{GOLD}" stroke-width="1.5"/>')


def arrow(x1, y1, x2, y2, col=HL, w=3):
    """Highlight-red arrow with a cream halo, like the rulebook's arrows."""
    a = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2 - 11 * math.cos(a), y2 - 11 * math.sin(a)
    head = (f'{x2},{y2} {x2-14*math.cos(a-.45):.1f},{y2-14*math.sin(a-.45):.1f} '
            f'{x2-14*math.cos(a+.45):.1f},{y2-14*math.sin(a+.45):.1f}')
    return (f'<line x1="{x1}" y1="{y1}" x2="{hx:.1f}" y2="{hy:.1f}" stroke="{CREAM}" stroke-width="{w+4}" stroke-linecap="round"/>'
            f'<polygon points="{head}" fill="{CREAM}" stroke="{CREAM}" stroke-width="4" stroke-linejoin="round"/>'
            f'<line x1="{x1}" y1="{y1}" x2="{hx:.1f}" y2="{hy:.1f}" stroke="{col}" stroke-width="{w}" stroke-linecap="round"/>'
            f'<polygon points="{head}" fill="{col}"/>')


# ================================================================ worked data (all from the engine)
def explain(wall, r, k):
    """(across, down) run lengths of the tile at (r, k) on `wall` (tile included)."""
    h = v = 1
    for dk in (-1, 1):
        kk = k + dk
        while 0 <= kk < 5 and wall[r][kk]:
            h += 1
            kk += dk
    for dr in (-1, 1):
        rr = r + dr
        while 0 <= rr < 5 and wall[rr][k]:
            v += 1
            rr += dr
    return h, v


def describe(h, v):
    parts = ([f"across {h}"] if h > 1 else []) + ([f"down {v}"] if v > 1 else [])
    return " + ".join(parts) if parts else "no neighbours"


# scoring examples: alone, across, down, across + down
SC_EX = []
_want = {"alone": 1, "across": 3, "down": 2, "across + down": 7}
for _name, _rows, (_r, _k) in [
        ("alone", ["B....", ".....", ".....", ".....", "....."], (2, 2)),
        ("across", [".....", "...RK", ".....", ".....", "....."], (1, 2)),
        ("down", [".....", "..Y..", ".....", ".....", "....."], (2, 2)),
        ("across + down", ["...K.", "...R.", ".WB.R", ".....", "....."], (2, 3))]:
    _w = E.wall_from_rows(_rows)
    assert _w[_r][_k] is None
    _w[_r][_k] = E.wall_colour(_r, _k)
    _p = E.score_placement(_w, _r, _k)
    _h, _v = explain(_w, _r, _k)
    assert _p == _want[_name] == (1 if (_h, _v) == (1, 1) else (_h if _h > 1 else 0) + (_v if _v > 1 else 0))
    SC_EX.append({"name": _name, "wall": _w, "cell": (_r, _k), "pts": _p, "run": run_cells(_w, _r, _k),
                  "col": E.LETTERS[E.wall_colour(_r, _k)]})
assert SC_EX[1]["col"] == "Y" and SC_EX[2]["col"] == "B" and SC_EX[3]["col"] == "Y"

# floor line
FLOOR_TOTALS = [E.floor_penalty(n) for n in range(1, 8)]
assert FLOOR_TOTALS == [-1, -2, -4, -6, -8, -11, -14] and E.floor_penalty(9) == -14

# end bonus example (Ana): 1 row, 2 columns, all 5 blue tiles
ANA = E.wall_from_rows(["BYRKW", "WB...", "KWB..", "RK.B.", "YR..B"])
ANA_BD = E.bonus_breakdown(ANA)
assert (ANA_BD["rows"], ANA_BD["columns"], ANA_BD["colours"], ANA_BD["total"]) == (1, 2, 1, 26)
assert E.end_bonus(ANA) == 26

# full worked end-of-game score: Ana's last wall-tiling phase
FINAL_NEW = [(0, 4), (2, 2), (4, 4)]                      # lines 1, 3 and 5
FW_BEFORE = [row[:] for row in ANA]
for _r, _k in FINAL_NEW:
    FW_BEFORE[_r][_k] = None
assert E.complete_rows(FW_BEFORE) == 0                    # the final row is completed this phase
FW_START = 52                                             # story choice: marker position before phase B
FW_LINES = [("W", 1), ("R", 1), ("B", 3), ("Y", 2), ("B", 5)]
FW_FLOOR = ["B", "R", "1"]                                # 2 tiles + the starting player marker
for _line in (0, 2, 4):                                   # complete lines are legal and fit the wall colours
    _c, _n = FW_LINES[_line]
    assert _n == _line + 1 and _c == E.LETTERS[E.wall_colour(*[x for x in FINAL_NEW if x[0] == _line][0])]
FW_WALL = [row[:] for row in FW_BEFORE]
FW_STEPS = []
for _r, _k in FINAL_NEW:
    FW_WALL[_r][_k] = E.wall_colour(_r, _k)
    FW_STEPS.append((_r, _k, explain(FW_WALL, _r, _k), E.score_placement(FW_WALL, _r, _k)))
assert FW_WALL == ANA
FW_PTS = [s[3] for s in FW_STEPS]
FW_FLOOR_PEN = E.floor_penalty(len(FW_FLOOR))
FW_BONUS = E.end_bonus(FW_WALL)
FW_TOTAL = FW_START + sum(FW_PTS) + FW_FLOOR_PEN + FW_BONUS
assert FW_FLOOR_PEN == -4 and FW_BONUS == 26

# Andrea's pattern-line example (2 yellow tiles)
AND_WALL = E.wall_from_rows(["B....", "..Y..", "...Y.", ".....", "....."])
AND_BOARD = E.new_board()
AND_BOARD["wall"] = AND_WALL
AND_BOARD["lines"][3] = {"colour": "blue", "count": 1}
assert [E.can_place(AND_BOARD, i, "yellow") for i in range(5)] == [True, False, False, False, True]

# grey-wall examples
GREY_A = E.empty_wall()
for _r, _k, _c in [(0, 0, "blue"), (0, 1, "yellow"), (1, 1, "blue"), (2, 0, "red")]:
    GREY_A[_r][_k] = _c
GREY_A_OPT = E.grey_columns(GREY_A, 2, "blue")
assert GREY_A_OPT == [2, 3, 4]
GREY_B = E.empty_wall()
for _r, _k, _c in [(1, 4, "blue"), (2, 3, "blue"), (4, 0, "yellow"), (4, 1, "red"), (4, 2, "black")]:
    GREY_B[_r][_k] = _c
assert E.grey_columns(GREY_B, 4, "blue") == []

FACT_N = {n: (E.FACTORIES[n], E.FACTORIES[n] * E.TILES_PER_FACTORY) for n in (2, 3, 4)}
assert FACT_N == {2: (5, 20), 3: (7, 28), 4: (9, 36)} and E.TOTAL_TILES == 100


# ================================================================ pictures
def img_cover():
    c = 62
    wall = E.wall_from_rows(["BYRKW", "WBYR.", "KWB..", "RK.B.", "Y...."])
    body, w = wall_cells(wall, c, 8, 8)
    return svg(w + 16, w + 16, frame(1, 1, w + 15, w + 15, r=14, w=2) + body, "cover-art")


def img_board_anatomy():
    c = 34
    body, W, H, inf = board_panel(4, 4, c, name="Your board", score=0,
                                  lines=[("R", 1), ("B", 2), (None, 0), ("K", 2), ("W", 3)],
                                  wall=E.wall_from_rows(["B....", "..Y..", ".....", ".....", "....."]), floor=["B", "1"])
    st = c * (1 + GAP)
    lx, ly = inf["lines"]
    px = lx + c * .9
    wy = ly + 2.5 * st
    lab = [badge(W + 22, 4 + c * .52, 1), badge(lx + c * 1.4, ly + c * .5, 2),
           badge(W + 22, wy, 3), badge(px + 7 * st + c * .45, inf["floor_y"] + c / 2, 4)]
    return svg(W + 42, H + 8, body + "".join(lab))


def img_setup():
    W, H = 1000, 790
    b = [f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="18" fill="#FBF6EC" stroke="{SLOT}" stroke-width="1.6"/>']
    c, bx = 22, 349
    pos = {}
    for (by, lab) in [(10, "Player 2"), (569, "Player 1")]:
        body, bw, bh, inf = board_panel(bx, by, c, name=lab)
        b.append(body)
        pos[lab] = (by, bw, bh, inf)
    cx, cy, R = 500, 402, 112
    b.append(f'<circle cx="{cx}" cy="{cy}" r="58" fill="{LIGHT}" stroke="{SLOT}" stroke-width="1.6"/>')
    rnd = random.Random(7)
    pool = list(LETTERS) * 4
    rnd.shuffle(pool)
    for i in range(5):
        a = -math.pi / 2 + i * 2 * math.pi / 5
        b.append(factory(cx + R * math.cos(a), cy + R * math.sin(a), 46, pool[i * 4:i * 4 + 4]))
    b.append(txt(cx, cy - 2, "centre of", 14, BROWN, 700, "middle"))
    b.append(txt(cx, cy + 15, "the table", 14, BROWN, 700, "middle"))
    bag_body, (lx, ly) = bag(140, 290, 150)
    b.append(bag_body)
    b.append(txt(lx, ly - 2, "BAG", 17, NAVY, 700, "middle", font="display"))
    b.append(txt(lx, ly + 17, f"{E.TOTAL_TILES} tiles", 13, INK, 700, "middle"))
    b.append(box_lid(790, 340, 170, 130))
    b.append(txt(875, 370, "BOX LID", 18, CREAM, 700, "middle", font="display"))
    b.append(txt(875, 391, "(empty)", 13, GOLD_LT, 700, "middle"))
    b.append(marker(700, 640, 40))
    b.append(txt(720, 702, "starting player marker", 12.5, BROWN, 700, "middle"))
    p1y, _, _, p1 = pos["Player 1"]
    for (x, y, n, r) in [(bx - 14, p1y + 60, 1, 13), (p1["cube"][0], p1y - 15, 2, 12), (655, 330, 3, 13), (74, 322, 4, 13),
                         (754, 638, 5, 13), (528, 254, 6, 12), (790, 340, 7, 13)]:
        b.append(badge(x, y, n, r))
    return svg(W, H, "".join(b))


def panel(x, w, h, title):
    return frame(x, 4, x + w, h - 4, r=12, w=1.8, fill="#FFFDF8") + txt(x + 16, 32, title, 15, RED, 700, font="display")


def img_turn_a():
    """Option 1: take a colour from a factory display; the rest goes to the centre."""
    W, H = 1000, 310
    A, Bf = ["R", "R", "Y", "W"], ["B", "K", "B", "Y"]
    b = [panel(4, 470, H, "Before")]
    b.append(factory(90, 125, 66, A, hl=[0, 1]))
    b.append(factory(250, 125, 66, Bf))
    b.append(txt(90, 220, "Factory display A", 13.5, BROWN, 700, "middle"))
    b.append(txt(250, 220, "Factory display B", 13.5, BROWN, 700, "middle"))
    b.append(centre_area(330, 71, 130, 108))
    b.append(centre_tiles(344, 87, 110, ["K", "W"], 40))
    b.append(txt(395, 220, "centre of the table", 13.5, BROWN, 700, "middle"))
    b.append(txt(240, 262, "Take both red tiles from A (ringed).", 14, INK, 700, "middle"))
    b.append(txt(240, 282, "Yellow and white go to the centre.", 13.5, BROWN, 700, "middle"))
    b.append(arrow(480, 160, 526, 160, HL, 5))
    b.append(panel(530, 466, H, "After"))
    b.append(factory(612, 125, 66, []))
    b.append(txt(612, 220, "A is now empty", 13.5, BROWN, 700, "middle"))
    b.append(factory(762, 125, 66, Bf))
    b.append(txt(762, 220, "B unchanged", 13.5, BROWN, 700, "middle"))
    b.append(centre_area(842, 71, 140, 108))
    b.append(centre_tiles(852, 81, 122, ["K", "W", "Y", "W"], 40))
    b.append(txt(912, 220, "centre: 4 tiles", 13.5, BROWN, 700, "middle"))
    b.append(txt(548, 262, "Your board:", 13.5, BROWN, 700))
    for j in range(3):
        b.append(tile(680 - j * 29, 243, 26, "R") if j < 2 else hole(680 - j * 29, 243, 26))
    b.append(txt(720, 262, "line 2 gets both red tiles", 14, INK, 700))
    return svg(W, H, "".join(b))


def img_turn_b():
    """Option 2: take a colour from the centre; the first taker also takes the marker."""
    W, H = 1000, 250
    b = [panel(4, 470, H, "Before: centre of the table")]
    b.append(centre_area(30, 52, 420, 96))
    b.append(centre_tiles(44, 66, 400, ["K", "W", "Y", "W"], 56, hl=(2, 4), marker_first=True))
    b.append(txt(240, 186, "Take both white tiles (ringed). You are the first", 14, INK, 700, "middle"))
    b.append(txt(240, 206, "to take from the centre: take the marker too.", 14, INK, 700, "middle"))
    b.append(arrow(480, 105, 526, 105, HL, 5))
    b.append(panel(530, 466, H, "After: your floor line and line 5"))
    c = 30
    for j in range(5):
        b.append(tile(556 + (4 - j) * c * 1.12, 56, c, "W") if j < 2 else hole(556 + (4 - j) * c * 1.12, 56, c))
    b.append(txt(556, 50, "pattern line 5: two white tiles", 12.5, BROWN, 700))
    for k in range(7):
        b.append(item(556 + k * c * 1.12, 130, c, "1" if k == 0 else None))
        b.append(txt(556 + k * c * 1.12 + c / 2, 130 + c + 17, f"&minus;{abs(E.FLOOR_VALUES[k])}", 14, RED, 700, "middle"))
    b.append(txt(556, 124, "floor line: the marker in the leftmost space", 12.5, BROWN, 700))
    b.append(txt(880, 232, "The centre keeps: K Y", 13.5, BROWN, 700, "middle"))
    return svg(W, H, "".join(b))


def img_andrea():
    c = 40
    body, W, H, _ = board_panel(c * .65 + 2, 4, c, lines=[(None, 0), (None, 0), (None, 0), ("B", 1), (None, 0)],
                                wall=AND_WALL, marks={0: "ok", 1: "no", 2: "no", 3: "no", 4: "ok"})
    return svg(W + c * .65 + 6, H + 8, body)


def floor_row(items, c, width_cls="fig"):
    body = "".join(item(10 + k * c * (1 + GAP), 8, c, items[k] if k < len(items) else None) for k in range(7))
    body += "".join(txt(10 + k * c * (1 + GAP) + c / 2, 8 + c + 21, f"&minus;{abs(E.FLOOR_VALUES[k])}", 20, RED, 700, "middle")
                    for k in range(7))
    return svg(10 + 7 * c * (1 + GAP), 8 + c + 30, body, width_cls)


def img_score_ex(ex, c=34):
    hl = {cell: "run" for cell in ex["run"]}
    hl[ex["cell"]] = "new"
    body, w = wall_cells(ex["wall"], c, 6, 6, hl)
    return svg(w + 12, w + 12, body)


def img_final_board():
    c = 34
    body, W, H, _ = board_panel(4, 4, c, name="Ana", score=FW_START, lines=[(a, n) for a, n in FW_LINES],
                                wall=FW_BEFORE, floor=FW_FLOOR)
    return svg(W + 8, H + 8, body)


def img_final_wall_after():
    body, w = wall_cells(ANA, 34, 6, 6, {cell: "new" for cell in FINAL_NEW})
    return svg(w + 12, w + 12, body)


def img_bonus():
    c = 34
    hl = {(r, k): "run" for r in range(5) for k in (0, 1)}
    hl.update({(0, k): "run" for k in range(5)})
    hl.update({(i, i): "new" for i in range(5)})
    body, w = wall_cells(ANA, c, 6, 6, hl)
    return svg(w + 12, w + 12, body)


def img_grey(wall, opts=(), cross=()):
    c = 34
    body, w = wall_cells(wall, c, 6, 6, grey=True, options={(2, k) for k in opts})
    st = c * (1 + GAP)
    body += "".join(txt(6 + k * st + c / 2, 6 + 4 * st + c * .72, "&#10007;", c * .62, HL, 700, "middle")
                    for k in cross)
    return svg(w + 12, w + 12, body)


# ================================================================ HTML helpers
FONT_DIR = ROOT / "tools" / "azul" / "fonts"     # SIL OFL, see OFL.txt there


def font_faces():
    """@font-face rules for the bundled fonts, embedded as data URIs."""
    out = []
    for fam, file, weight in (("Cinzel", "Cinzel-Bold.ttf", 700), ("Caladea", "Caladea-Regular.ttf", 400),
                              ("Caladea", "Caladea-Bold.ttf", 700)):
        data = base64.b64encode((FONT_DIR / file).read_bytes()).decode()
        out.append(f'@font-face {{ font-family: "{fam}"; font-weight: {weight}; font-style: normal; '
                   f'src: url(data:font/ttf;base64,{data}) format("truetype"); }}')
    return "\n".join(out)


CSS = r"""
@page { size: A4; margin: 0; }
:root {
  --ink: #1B2A4E; --muted: #68543C; --rule: #C9B28C; --paper: #FFFDF8;
  --navy: #1E3A72; --cobalt: #2C5AA8; --sky: #9CC0E3; --gold: #C08A2E; --red: #9E2A22; --hl: #B32A1E;
  --terra: #B05E34;
  --navy-t: #EEF3FA; --navy-b: #B9CDE6; --tan-t: #FBF4E6; --tan-b: #DCC59C;
  --par-t: #F6EEDD; --par-b: #D3BE96; --red-t: #FBEEEA; --red-b: #E4BDB5; --grey-t: #F3F0EA; --grey-b: #D3CCC0;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--paper); }
body { font-family: Caladea, "DejaVu Serif", "DejaVu Sans", serif; color: var(--ink); font-size: 10pt;
       line-height: 1.34; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.page { width: 210mm; height: 297mm; position: relative; overflow: hidden; background: var(--paper);
        page-break-after: always; break-after: page; padding: 13mm 14mm 17mm 19mm; }
.page.even { padding: 13mm 19mm 17mm 14mm; }
.page::before { content: ""; position: absolute; inset: 6mm; border: 0.7pt solid var(--navy);
                border-radius: 2.5mm; pointer-events: none; }
.page::after { content: ""; position: absolute; inset: 7.1mm; border: 0.35pt solid var(--gold);
               border-radius: 1.8mm; pointer-events: none; }
.corner { position: absolute; width: 4.2mm; height: 4.2mm; z-index: 1; }
.corner.tl { top: 4.4mm; left: 4.4mm; } .corner.tr { top: 4.4mm; right: 4.4mm; }
.corner.bl { bottom: 4.4mm; left: 4.4mm; } .corner.br { bottom: 4.4mm; right: 4.4mm; }
.content { height: 100%; overflow: hidden; display: flex; flex-direction: column; position: relative; z-index: 2; }
footer { position: absolute; bottom: 9.2mm; left: 19mm; right: 14mm; display: flex; z-index: 2;
         justify-content: space-between; align-items: center; font-size: 8pt; color: var(--muted);
         flex-direction: row-reverse; border-top: 0.5pt solid var(--gold); padding-top: 1.2mm; }
.even footer { left: 14mm; right: 19mm; flex-direction: row; }
footer .pn { font-family: Cinzel, "DejaVu Serif", serif; font-weight: 700; font-size: 10pt; color: var(--navy); }
footer .pn::before, footer .pn::after { content: "\25C6"; font-size: 5pt; color: var(--cobalt); margin: 0 1.4mm;
                                         vertical-align: .25em; }
h1, h2, h3, h4 { margin: 0; line-height: 1.15; }
h1, h2, h3 { font-family: Cinzel, "DejaVu Serif", serif; font-weight: 700; color: var(--red); }
h1.pt { font-size: 21pt; margin-bottom: 1mm; letter-spacing: .01em; }
.kick { font-size: 8.4pt; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; color: var(--cobalt); }
.lead { font-size: 11pt; margin: 1mm 0 3mm; }
h2 { font-size: 12.6pt; margin: 3.5mm 0 2mm; padding-bottom: 1mm; border-bottom: 0.8pt solid var(--cobalt);
     position: relative; }
h2::after { content: "\25C6"; position: absolute; right: -.6mm; bottom: -1.2mm; font-size: 6.5pt; line-height: 1;
            color: var(--cobalt); background: var(--paper); padding: 0 .6mm; }
h3 { font-size: 10pt; margin: 0 0 1.2mm; letter-spacing: .01em; }
h4 { font-weight: 700; }
p { margin: 0 0 2mm; }
ul, ol { margin: 0 0 2mm; padding-left: 5mm; }
li { margin: 0 0 1mm; }
ul li::marker { color: var(--cobalt); }
ol li::marker { color: var(--navy); font-weight: 700; }
b, strong { font-weight: 700; }
code { font-size: 8.4pt; font-family: "DejaVu Sans Mono", monospace; }
.it { height: 1.3em; width: 1.3em; vertical-align: -0.3em; margin: 0 .04em; }
.itl { height: 1.7em; width: 1.7em; vertical-align: -0.5em; }
.box { border: 0.7pt solid var(--navy-b); border-radius: 2.5mm; padding: 3mm 3.5mm; background: #fff; break-inside: avoid; }
.tint-n { background: var(--navy-t); border-color: var(--navy-b); }
.tint-t { background: var(--tan-t); border-color: var(--tan-b); }
.tint-g { background: var(--par-t); border-color: var(--par-b); }
.tint-r { background: var(--red-t); border-color: var(--red-b); }
.tint-k { background: var(--grey-t); border-color: var(--grey-b); }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 3.5mm; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 3mm; }
.tag { display: inline-block; font-size: 7.4pt; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
       border: 0.7pt solid currentColor; border-radius: 1.2mm; padding: 0 1.4mm; vertical-align: .1em; }
.tag.house { color: var(--red); background: var(--red-t); }
.tag.ed { color: var(--muted); background: var(--tan-t); }
.tag.tip { color: var(--cobalt); background: var(--navy-t); }
.need { font-size: 8.8pt; color: var(--muted); }
svg.fig { display: block; width: 100%; height: auto; }
svg.band { display: block; width: 100%; height: auto; }
.cap { font-size: 8.4pt; color: var(--muted); margin-top: 1.2mm; }
table { border-collapse: collapse; }
table.pts { margin: 1.5mm 0 1mm; font-size: 9.4pt; }
table.pts th, table.pts td { border: 0.7pt solid #9DB0CC; padding: .7mm 2.4mm; text-align: center; }
table.pts th { background: var(--navy-t); color: var(--navy); font-weight: 700; text-align: left; }
table.data { width: 100%; font-size: 9.2pt; }
table.data th, table.data td { border: 0.7pt solid #A9B9D2; padding: .9mm 2mm; text-align: left; vertical-align: top; }
table.data th { background: var(--navy-t); color: var(--navy); font-weight: 700; }
.num { display: inline-flex; width: 6mm; height: 6mm; border-radius: 50%; background: var(--navy); color: #fff;
       font-weight: 700; align-items: center; justify-content: center; font-size: 9.4pt; flex: none;
       box-shadow: 0 0 0 0.5pt var(--gold); }
.num.s { width: 5mm; height: 5mm; font-size: 8.4pt; }
.steps { list-style: none; padding: 0; margin: 0 0 2mm; }
.steps li { display: flex; gap: 2.5mm; align-items: flex-start; margin-bottom: 1.8mm; }
.spacer { flex: 1; }
.pts-big { font-family: Cinzel, "DejaVu Serif", serif; font-size: 15pt; font-weight: 700; color: var(--navy); }
.phase { display: flex; gap: 3mm; align-items: flex-start; margin-bottom: 2.2mm; }
.phase .ph { flex: none; width: 9mm; height: 9mm; border-radius: 2mm; background: var(--navy); color: #fff;
             font-family: Cinzel, "DejaVu Serif", serif; font-weight: 700; font-size: 13pt; display: flex; align-items: center;
             justify-content: center; box-shadow: 0 0 0 0.6pt var(--gold); }
.cover-art { display: block; width: 100%; max-width: 110mm; margin: 0 auto; height: auto; }
.sw { display: flex; align-items: center; gap: 2.5mm; }
.sw svg { width: 11mm; height: 11mm; flex: none; }
.sheet { width: 100%; font-size: 8pt; border: 0.9pt solid var(--navy); }
.sheet th, .sheet td { border: 0.6pt solid #A9B9D2; padding: 0 1mm; height: 6mm; text-align: left; }
.sheet th { background: var(--navy-t); color: var(--navy); font-weight: 700; }
.sheet td { text-align: center; }
.sheet tr.g th { background: var(--navy); color: #fff; font-family: Cinzel, "DejaVu Serif", serif; font-size: 8.4pt; letter-spacing: .04em; }
.cb { display: inline-block; width: 2.8mm; height: 2.8mm; border: 0.8pt solid var(--navy); vertical-align: -0.4mm; }
.fq h4 { font-size: 9.6pt; color: var(--navy); margin: 0 0 .4mm; }
.fq p { font-size: 9.2pt; margin: 0 0 2mm; line-height: 1.28; }
.qr { font-size: 8.8pt; line-height: 1.3; }
.qr h3 { font-size: 9.4pt; margin: 0 0 1mm; }
.qr p, .qr li { margin-bottom: .8mm; }
.ok { color: var(--navy); } .no { color: var(--hl); }
"""

# small azulejo tiles on the corners of the thin page frame
CORNERS = "".join(svg(20, 20, azulejo(10, 10, 19, 0, bg=COBALT, ink=CREAM)
                      + f'<rect x=".5" y=".5" width="19" height="19" fill="none" stroke="{NAVY}" stroke-width="1"/>',
                      f"corner {k}") for k in ("tl", "tr", "bl", "br"))

FOOT = "Azul &middot; Player manual (unofficial)"


def table_floor():
    head = "".join(f"<td>{n}</td>" for n in range(1, 8))
    sp = "".join(f"<td>&minus;{abs(v)}</td>" for v in E.FLOOR_VALUES)
    tot = "".join(f"<td><b>{abs(t)}</b></td>" for t in FLOOR_TOTALS)
    return (f'<table class="pts"><tr><th>Items on the floor line</th>{head}</tr>'
            f'<tr><th>Space value</th>{sp}</tr><tr><th>Points lost in total</th>{tot}</tr></table>')


def letters_row(cls="itl"):
    return "".join(f'<div style="text-align:center">{T(ch, cls)}<div class="need"><b>{ch}</b> {NAME[ch]}</div></div>'
                   for ch in LETTERS)


# ================================================================ pages
def page_cover():
    return f"""
{azulejo_band(20)}
<div style="text-align:center;margin-top:5mm">
<div class="kick">Illustrated rules &amp; table reference</div>
<h1 style="font-size:54pt;color:var(--navy);letter-spacing:.06em;margin:2mm 0 0">Azul</h1>
<div style="font-family:Cinzel,'DejaVu Serif',serif;font-weight:700;font-size:12.5pt;color:var(--red);letter-spacing:.04em">2 to 4 players &nbsp;&#9670;&nbsp; about 30&ndash;45 minutes</div>
</div>
<p class="lead" style="max-width:150mm;margin:4mm auto 0;text-align:center">Decorate the palace wall with glazed tiles. Collect
tiles from the factory displays, fill your pattern lines, move tiles onto your wall for points and avoid
dropping tiles on the floor line. This booklet explains every rule in plain words, with pictures, and ends with a
score sheet and a one-page quick reference.</p>
<div style="margin:4mm 0 3mm">{img_cover()}</div>
<div style="display:flex;gap:5mm;justify-content:center;margin-bottom:3mm">{letters_row()}</div>
<div class="spacer"></div>
<div class="box tint-n">
  <h3>Inside</h3>
  <div class="grid3" style="font-size:8.8pt;gap:.6mm 4mm">
    <div>2 &nbsp;Goal, components, words</div><div>7 &nbsp;Phase B: wall-tiling</div><div>11 &nbsp;Grey wall &amp; tips</div>
    <div>3 &nbsp;Setup</div><div>8 &nbsp;Floor line &amp; phase C</div><div>12 &nbsp;FAQ &amp; glossary</div>
    <div>4 &nbsp;Your board &amp; the round</div><div>9 &nbsp;A full worked score</div><div>13 &nbsp;Score sheet</div>
    <div>5 &nbsp;Phase A: taking tiles</div><div>10 &nbsp;End, bonuses, tie-break</div><div>14 &nbsp;Quick reference</div>
    <div>6 &nbsp;Phase A: placing tiles</div><div></div><div></div>
  </div>
</div>
<p style="font-size:7.4pt;color:var(--muted);margin:4mm 0 0">Unofficial player aid for personal use, written in our own
words with original tile designs; it does not reproduce the rulebook&rsquo;s text or artwork. <i>Azul</i> is a game by
Michael Kiesling, published by Plan B Games / Next Move (German edition: Pegasus Spiele). Azul is a trademark of
Plan B Games / Next Move Games. Every point value was checked with the rules engine in <code>tools/azul/engine.py</code>.</p>
<div style="margin-top:3mm">{azulejo_band(20)}</div>
"""


def page_goal():
    LOOK = {"B": "ring", "Y": "rosette", "R": "diamond", "K": "lattice", "W": "star"}
    comp = [
        ("Tiles", "100", "Square plastic tiles, <b>20 in each of 5 colours</b>."),
        ("Bag", "1", "A cloth bag. Tiles are drawn from it at random."),
        ("Factory displays", "9", "Round discs that offer tiles to players. You use 5, 7 or 9, depending on the number of players."),
        ("Player boards", "4", "One per player. Each has a <b>coloured side</b> (normal game) and a <b>grey side</b> (variant, page 11)."),
        ("Score markers", "4", "Small black cubes, one per player, that show your points on the score track."),
        ("Starting player marker", "1", "A square token with a &ldquo;1&rdquo;. It is <b>not</b> a tile and never goes on a wall."),
    ]
    rows = "".join(f"<tr><th>{a}</th><td style='text-align:center'><b>{n}</b></td><td>{d}</td></tr>" for a, n, d in comp)
    sw = "".join(f'<div class="sw">{T(ch, "")}<div><b>{ch}</b> &nbsp;{NAME[ch]}<br><span class="need">&times;{E.TILES_PER_COLOUR} &middot; {LOOK[ch]}</span></div></div>'
                 for ch in LETTERS)
    gl = [
        ("Turn", "one player&rsquo;s go. Players take turns one after another."),
        ("Clockwise", "the next player is the one on your left. Turns go around the table this way."),
        ("Round", "one cycle of the game: collect tiles, move tiles to walls, prepare the next round. A game has several rounds (usually 5 or 6)."),
        ("Draw", "reach into the bag without looking and take tiles out at random."),
    ]
    g = "".join(f"<li><b>{a}:</b> {d}</li>" for a, d in gl)
    return f"""
<div class="kick">Start here</div>
<h1 class="pt">Goal, components &amp; words</h1>
<h2 style="margin-top:2mm">The story</h2>
<p>Long ago, a king of Portugal saw the beautiful glazed wall tiles of a Spanish palace and wanted the same for his
own palace. In Azul, you are a tile-layer decorating that palace wall.</p>
<h2>Goal of the game</h2>
<p>Each player has their own <b>wall</b> to decorate, on their own <b>player board</b>. Every round, players take turns
collecting <b>tiles</b> from the middle of the table. Tiles you collect wait in rows on your board until a row is full.
At the end of each round, one tile from every full row moves onto your wall and scores points. Tiles you collect but
cannot use cost you points.</p>
<div class="box tint-n"><p style="margin:0">The game ends after the round in which someone fills a complete
<b>horizontal row</b> of their wall (5 tiles side by side). After some bonus points,
<b>the player with the most points wins</b>.</p></div>
<h2>Components</h2>
<table class="data"><tr><th>Item</th><th>Count</th><th>What it is</th></tr>{rows}</table>
<p class="need" style="margin-top:1.4mm">The box lid is also used during play: tiles that leave the game for a while are put in it (page 8).
<span class="tag ed">Edition note</span> The German rulebook has no separate component list; the counts follow its setup and the 4-player maximum.</p>
<h3 style="margin-top:2mm">The five tile colours: each one also has a letter</h3>
<div class="grid3" style="grid-template-columns:repeat(5,1fr);gap:2mm;margin-bottom:2mm">{sw}</div>
<h2>Words used in this manual</h2>
<ul>{g}</ul>
<p class="need">All other game words are explained where they first appear. The names are the same everywhere in this
booklet: factory display, centre of the table, pattern line, wall, floor line, box lid, starting player marker, score track.</p>
"""


def page_setup():
    steps = [
        ("Player boards.", "Each player takes a player board and puts it in front of them with the <b>coloured side</b> up. "
         "<b>All players use the same side</b>: everyone on the coloured side, or everyone on the grey side (variant, page 11). "
         "<b>All player boards are identical</b>: the same wall pattern, pattern lines and floor line."),
        ("Score markers.", "Each player puts a score marker on space <b>0</b> of their score track."),
        ("Factory displays.", "Put factory displays in a circle in the middle of the table. The space inside the circle is the "
         "<b>centre of the table</b> (or just &ldquo;the centre&rdquo;). Use 5, 7 or 9, depending on the players (table at right)."),
        ("Bag.", f"Put all {E.TOTAL_TILES} tiles in the bag and mix them."),
        ("Starting player.", "Choose who starts. (The rulebook suggests: whoever visited Portugal most recently.) That player is "
         "the <b>starting player</b> and takes the starting player marker."),
        ("Fill the factory displays.", f"The starting player draws tiles from the bag and puts <b>exactly {E.TILES_PER_FACTORY} tiles</b> on each "
         "factory display. Then put the bag aside."),
        ("Box lid.", "Put unused player boards, score markers and factory displays back in the box. Keep the box lid nearby, empty."),
    ]
    st = "".join(f'<li><span class="num">{i}</span><div><b>{a}</b> {b}</div></li>' for i, (a, b) in enumerate(steps, 1))
    return f"""
<div class="kick">Before the first round</div>
<h1 class="pt">Setup</h1>
<p class="need" style="margin-bottom:2mm">The picture shows a <b>2-player game</b> (5 factory displays). The numbers match the steps below.</p>
<div class="box" style="padding:2mm"><div style="width:166mm;margin:auto">{img_setup()}</div></div>
<div class="grid2" style="margin-top:3mm;grid-template-columns:1.7fr 1fr;align-items:start">
<ol class="steps" style="font-size:9pt">{st}</ol>
<div>
<table class="pts" style="width:100%"><tr><th>Players</th><td>2</td><td>3</td><td>4</td></tr>
<tr><th>Factory displays</th>{"".join(f"<td>{FACT_N[n][0]}</td>" for n in (2, 3, 4))}</tr>
<tr><th>Tiles drawn</th>{"".join(f"<td>{FACT_N[n][1]}</td>" for n in (2, 3, 4))}</tr></table>
<div class="box tint-t" style="margin-top:2mm;font-size:8.6pt"><h3>With 3 or 4 players</h3>
<p style="margin-bottom:1mm"><b>3 players:</b> {FACT_N[3][0]} factory displays ({FACT_N[3][1]} tiles drawn).</p>
<p style="margin-bottom:1mm"><b>4 players:</b> {FACT_N[4][0]} factory displays ({FACT_N[4][1]} tiles drawn).</p>
<p style="margin:0">Everything else is the same: one identical board each, score markers on 0, 4 tiles per display.
Turns go clockwise.</p></div>
<div class="box tint-n" style="margin-top:2mm;font-size:8.6pt"><b>You are ready to play.</b> Tile letters (B Y R K W) are
always printed on the tiles.</div>
</div></div>
"""


def page_turn():
    rows = "".join("<tr><th>Row %d</th>%s</tr>" % (r, "".join(
        "<td>%s %s</td>" % (T(E.LETTERS[E.wall_colour(r - 1, k)]), E.COLOURS[(k - (r - 1)) % 5]) for k in range(5)))
        for r in range(1, 6))
    return f"""
<div class="kick">Reading the board · how a round runs</div>
<h1 class="pt">Your board &amp; the round</h1>
<div class="box" style="padding:2mm 4mm"><div style="width:100mm;margin:auto">{img_board_anatomy()}</div></div>
<div class="grid2" style="font-size:8.9pt;margin-top:2.5mm;gap:0 6mm">
<div>
<p><span class="num s">1</span> <b>Score track:</b> the numbered spaces 0 to 100 along the edge. Your score marker moves along it.</p>
<p><span class="num s">2</span> <b>Pattern lines:</b> five rows of empty spaces shaped like a staircase. Line 1 (top) has 1 space, line 5 (bottom) has 5. Tiles you collect wait here.</p>
</div><div><p><span class="num s">3</span> <b>Wall:</b> the 5 &times; 5 grid. Each space shows the colour that belongs there. An arrow joins pattern line 1 to wall <b>row</b> 1, line 2 to row 2, and so on.</p>
<p><span class="num s">4</span> <b>Floor line:</b> seven spaces along the bottom, with <b>&minus;1 &minus;1 &minus;2 &minus;2 &minus;2 &minus;3 &minus;3</b> printed under them. Tiles you cannot use go here and cost points.</p>
</div></div>
<p style="margin-top:2mm">A <b>row</b> of the wall goes across (left to right); a <b>column</b> goes down (top to bottom). Both are numbered 1 to 5, from the top and from the left.
<b>The coloured wall:</b> every row holds each of the 5 colours exactly once, and so does every column. Each row is the row above it shifted one space to the right.
Faint spaces are not yet tiled.</p>
<h2>How a round works</h2>
<p>Every round has three phases, always in this order:</p>
<div class="box tint-n phase"><div class="ph">A</div><div><h3>Factory offer</h3>
Players take turns collecting tiles and putting them on their pattern lines. <span class="need">(pages 5&ndash;6)</span></div></div>
<div class="box tint-t phase"><div class="ph" style="background:var(--red)">B</div><div><h3>Wall-tiling</h3>
Full pattern lines move one tile to the wall and score; the floor line costs points. <span class="need">(pages 7&ndash;8)</span></div></div>
<div class="box tint-g phase"><div class="ph" style="background:var(--terra)">C</div><div><h3>Preparing the next round</h3>
Refill the factory displays. <span class="need">(page 8)</span></div></div>
<p>Then a new round begins with phase A, <b>unless the game has ended</b> (page 10).</p>
<div class="spacer"></div>
<div class="box"><h3>The coloured wall, row by row</h3>
<table class="data" style="font-size:8.4pt"><tr><th></th><th>Column 1</th><th>Column 2</th><th>Column 3</th><th>Column 4</th><th>Column 5</th></tr>{rows}</table></div>
"""


def page_phase_a1():
    return f"""
<div class="kick">Phase A · factory offer</div>
<h1 class="pt">Taking tiles</h1>
<p>At the start of this phase, the starting player puts the <b>starting player marker in the centre of the table</b>
and takes the first turn. Turns go clockwise. On your turn you <b>must take tiles</b>. Choose <b>one</b> of two options.</p>
<div class="grid2">
<div class="box tint-n"><h3>Option 1: take from a factory display</h3>
<p style="margin:0">Pick any factory display that has tiles. Pick one colour on it. Take <b>all</b> tiles of that colour from that display.
Then push all the other tiles on that display into the centre of the table. The display is now empty.</p></div>
<div class="box tint-t"><h3>Option 2: take from the centre</h3>
<p style="margin:0">Pick one colour in the centre. Take <b>all</b> tiles of that colour from the centre. Leave the other tiles there.
If you are the <b>first player this round</b> to take tiles from the centre, you also take the <b>starting player marker</b> and
put it on the <b>leftmost empty space of your floor line</b>.</p></div></div>
<p style="margin-top:2mm"><b>You can&rsquo;t take only some tiles of a colour, and you can&rsquo;t take two colours.</b></p>
<h2>One turn, in a picture</h2>
<p class="need" style="margin-bottom:1.5mm"><b>Option 1.</b> Take the two red tiles from factory display A. The yellow and the white tile go to the centre.</p>
<div class="box" style="padding:2mm">{img_turn_a()}</div>
<p class="need" style="margin:3mm 0 1.5mm"><b>Option 2.</b> Later in the round, take the two white tiles from the centre. You are the first to take from the centre, so the marker goes to the leftmost space of your floor line.</p>
<div class="box" style="padding:2mm">{img_turn_b()}</div>
<p class="cap">The marker costs points like a tile (page 8), but it also makes you the starting player of the next round.</p>
<h2>End of phase A, and example turns</h2>
<p>Phase A ends when <b>every factory display and the centre of the table are empty</b>. Turns may go around the table several times before that happens.</p>
<ol style="font-size:9pt">
<li>Peter takes the 2 black tiles ({Ts("KK")}) from a factory display. That display also had 1 yellow and 1 white tile; Peter pushes those into the centre.</li>
<li>Martin takes 1 yellow tile ({T("Y")}) from another factory display and pushes its 3 red tiles into the centre.</li>
<li>Andrea takes the 3 red tiles ({Ts("RRR")}) from the centre. She is the first player this round to take from the centre, so she also takes the starting player marker and puts it on the leftmost space of her floor line.</li></ol>
"""


def page_phase_a2():
    return f"""
<div class="kick">Phase A · factory offer</div>
<h1 class="pt">Placing the tiles you took</h1>
<p>Right away, put <b>all</b> the tiles you just took into <b>one</b> of your five pattern lines:</p>
<ul>
<li>Fill the line <b>from right to left</b>: the first tile goes in the space next to the wall.</li>
<li>A pattern line holds <b>one colour only</b>. If the line already has tiles, you may only add tiles of that same colour.</li>
<li>You may <b>not</b> put a colour into a pattern line if the wall row beside that line <b>already has a tile of that colour</b>.</li>
<li>When every space of a pattern line is filled, the line is <b>complete</b>.</li>
<li>If you took more tiles than the line has empty spaces, fill the line and put the extra tiles on your <b>floor line</b>.</li></ul>
<p>Instead of a pattern line, you may put all the tiles you took straight onto your floor line. You <b>must</b> do this if no pattern line can take that colour.</p>
<div class="box tint-g"><p style="margin:0"><b>Your aim in this phase:</b> complete as many pattern lines as you can. Only complete lines put tiles on your wall, and only tiles on the wall score points.</p></div>
<h2>Example: where can the tiles go?</h2>
<p>Andrea takes 2 yellow tiles ({Ts("YY")}). Her wall already has yellow in rows 2 and 3, and her pattern line 4 has 1 blue tile.</p>
<div class="grid2" style="grid-template-columns:1fr 1fr;align-items:center">
<div class="box" style="padding:2mm 2mm 1mm">{img_andrea()}</div>
<div>
<table class="data" style="font-size:8.6pt"><tr><th>Line</th><th style="white-space:nowrap"></th><th>Why</th></tr>
<tr><td>1</td><td><b class="ok" style="white-space:nowrap">&#10003; legal</b></td><td>1 yellow fills it; the 2nd yellow goes to the floor line.</td></tr>
<tr><td>2</td><td><b class="no" style="white-space:nowrap">&#10007; illegal</b></td><td>Yellow is already in wall row 2.</td></tr>
<tr><td>3</td><td><b class="no" style="white-space:nowrap">&#10007; illegal</b></td><td>Yellow is already in wall row 3.</td></tr>
<tr><td>4</td><td><b class="no" style="white-space:nowrap">&#10007; illegal</b></td><td>The line already holds blue.</td></tr>
<tr><td>5</td><td><b class="ok" style="white-space:nowrap">&#10003; legal</b></td><td>Both yellow tiles go there; 3 spaces stay empty.</td></tr>
<tr><td>Floor</td><td><b class="ok" style="white-space:nowrap">&#10003; legal</b></td><td>Both yellow tiles go on the floor line.</td></tr></table></div></div>
<p class="cap" style="margin:0">The legality of each line was checked with the engine&rsquo;s <code>can_place</code>.</p>
<h2>More pattern-line examples</h2>
<div class="grid3" style="font-size:8.8pt">
<div class="box"><h3>Too many tiles</h3><p style="margin:0">You take {Ts("RRR")} and choose line 2 (2 spaces). Two red tiles
fill the line; the 3rd goes to the first free floor space.</p></div>
<div class="box"><h3>Adding to a line</h3><p style="margin:0">Line 4 already holds {Ts("KK")}. Taking {T("K")} lets you add it
(same colour). Taking {T("W")} does not: the line keeps its colour.</p></div>
<div class="box"><h3>Unfinished lines stay</h3><p style="margin:0">An incomplete pattern line keeps its tiles into the next round.
You can add more of the same colour later; the colour cannot be changed.</p></div></div>
<h2>The floor line</h2>
<p>Tiles go onto the floor line <b>from left to right</b>, into the leftmost empty space. They count as broken, and each costs the points printed under its space.
If all 7 floor spaces are full, any further tiles go into the <b>box lid</b> instead and cost nothing extra.</p>
<div style="display:flex;gap:5mm;align-items:center"><div style="width:70mm">{floor_row(["Y", "Y", "R", "W", "1"], 46)}</div>
<p class="need" style="margin:0">Four tiles and the starting player marker fill the first 5 spaces. Penalties: page 8.</p></div>
"""


def page_phase_b():
    descr = {
        "alone": "A tile with no neighbour across or down. Touching only at a corner does not count.",
        "across": "A tile in row 2 with red and black right beside it: the unbroken line across is 3 tiles.",
        "down": "A tile in row 3 with a yellow tile directly above it and nothing beside it: the unbroken line down is 2 tiles.",
        "across + down": "A tile in row 3, column 4. Across, it joins white, blue and red: a line of 4. Down, it joins black and red above it: a line of 3. 4 + 3.",
    }
    cards = "".join(f"""<div class="box"><div style="display:flex;justify-content:space-between;align-items:baseline">
<h3 style="text-transform:capitalize">{ex['name']}</h3><span class="pts-big">{ex['pts']} {'point' if ex['pts'] == 1 else 'points'}</span></div>
<div style="display:flex;gap:2.5mm;align-items:center;margin-top:1mm"><div style="width:30mm;flex:none">{img_score_ex(ex)}</div><p class="need" style="margin:0">{T(ex['col'])} {descr[ex['name']]}</p></div></div>"""
                    for ex in SC_EX)
    return f"""
<div class="kick">Phase B · wall-tiling</div>
<h1 class="pt">Wall-tiling &amp; scoring</h1>
<p>All players can do this phase <b>at the same time</b>, each on their own board.</p>
<ol class="steps">
<li><span class="num">1</span><div>Go through your pattern lines <b>from top to bottom</b> (line 1 first, line 5 last).</div></li>
<li><span class="num">2</span><div>For each <b>complete</b> pattern line: move its <b>rightmost tile</b> onto the wall space of <b>the same colour</b> in the row beside it. Score that tile right away.</div></li>
<li><span class="num">3</span><div>Skip every pattern line that is not complete. Its tiles stay where they are for the next round.</div></li>
<li><span class="num">4</span><div>When you have gone through all five lines: from every pattern line whose rightmost space is now empty (the ones you just moved a tile from), put the remaining tiles in the <b>box lid</b>. Only those lines are emptied.</div></li>
<li><span class="num">5</span><div>Score your floor line (page 8).</div></li></ol>
<h2>How a new wall tile scores</h2>
<p>Score each tile at the moment it is placed. Tiles placed earlier this phase (higher rows) already count.</p>
<ul>
<li><b>No neighbours:</b> if the new tile does not touch any other tile on the wall horizontally or vertically, it scores <b>1 point</b>.</li>
<li><b>With neighbours:</b> count two things.
<b>Across:</b> if the new tile touches a tile to its left or right, count all tiles in the unbroken line across that includes the new tile. Score that many points.
<b>Down:</b> if it touches a tile above or below, count all tiles in the unbroken line down that includes it. Score that many points too.</li></ul>
<p>An empty space stops the count. If a tile has neighbours both across and down, it scores both counts, so it counts itself twice.
Move your score marker forward by the points right away.</p>
<h2>Scoring examples</h2>
<p class="need" style="margin-bottom:1.5mm">Red ring = the new tile. Tiles shaded gold = the tiles that are counted.</p>
<div class="grid2">{cards}</div>
<p class="cap">All four totals were computed with the engine&rsquo;s <code>score_placement</code>.</p>
<div class="box tint-t" style="margin-top:1.5mm"><b>Peter&rsquo;s round.</b> His complete lines are line 2 (2 red tiles) and line 4 (4 blue tiles). His wall is empty.
Red goes to row 2 and scores <b>1</b>; blue goes to row 4 and scores <b>1</b>. He puts 1 red and 3 blue tiles in the box lid.
His lines 3 and 5 are not complete and stay as they are.</div>
"""


def page_floor_c():
    peter = ["K", "K", "Y", "W", "1"]
    assert E.floor_penalty(len(peter)) == -8 and 1 + 1 + 2 + 2 + 2 == 8
    return f"""
<div class="kick">Phase B (end) · phase C</div>
<h1 class="pt">The floor line &amp; the next round</h1>
<p>At the end of phase B, each player loses points for every item on their floor line. Each item loses the number printed under its space.
<b>The starting player marker counts as an item.</b></p>
<div class="box" style="padding:3mm 3mm 1mm"><div style="width:100mm;margin:auto">{floor_row(peter, 44)}</div></div>
{table_floor()}
<ul>
<li>Your score <b>can never go below 0</b>. If a penalty would take you below 0, stop at 0.</li>
<li>Then put every tile from your floor line in the <b>box lid</b>.</li>
<li>If the starting player marker is on your floor line, keep it in front of you instead of putting it in the lid. You are the starting player of the next round.</li></ul>
<div class="box tint-r"><p style="margin:0"><b>Example:</b> Peter has 4 tiles and the starting player marker on his floor line (5 items), as in the picture.
He loses 1 + 1 + 2 + 2 + 2 = <b>{abs(E.floor_penalty(5))} points</b>. The most anyone can lose in a round is <b>{abs(E.floor_penalty(7))}</b>: all 7 spaces
filled. Extra tiles go to the box lid without costing more.</p></div>
<h2>Phase C: preparing the next round</h2>
<p>If nobody has completed a horizontal row of their wall, play another round:</p>
<ol class="steps">
<li><span class="num">1</span><div>The player who has the starting player marker draws tiles from the bag and puts <b>exactly 4 tiles</b> on each factory display again.</div></li>
<li><span class="num">2</span><div><b>If the bag runs empty</b> while filling, put <b>all tiles from the box lid</b> into the bag, mix them, and keep filling.</div></li>
<li><span class="num">3</span><div>In the rare case that the bag <b>and</b> the box lid are both empty, stop. Start the new round anyway, even if some factory displays have fewer than 4 tiles or none.</div></li></ol>
<p>The new round begins with phase A. The player with the starting player marker puts it in the centre and takes the first turn.
The box lid is only emptied into the bag when the bag runs out during filling, never at any other time.</p>
<div class="spacer"></div>
<div class="box tint-n"><h3>Where do tiles go? A quick map</h3>
<table class="data" style="font-size:8.6pt"><tr><th>When</th><th>What happens</th></tr>
<tr><td>Phase A</td><td>Tiles go from factory displays / the centre to a pattern line or the floor line.</td></tr>
<tr><td>Phase B, complete line</td><td>1 tile to the wall (it scores); the rest of that line to the box lid.</td></tr>
<tr><td>Phase B, floor line</td><td>Penalty paid; tiles to the box lid; the marker stays with its owner.</td></tr>
<tr><td>Phase C</td><td>Tiles from the bag to the factory displays. Bag empty: pour the box lid into it.</td></tr></table></div>
"""


def page_worked():
    names = ["line 1 (white) &rarr; row 1, column 5", "line 3 (blue) &rarr; row 3, column 3", "line 5 (blue) &rarr; row 5, column 5"]
    trs = "".join(f"<tr><td>{i}</td><td>{nm}</td><td>{describe(*s[2])}</td><td><b>{s[3]}</b></td></tr>"
                  for i, (nm, s) in enumerate(zip(names, FW_STEPS), 1))
    n_before = sum(1 for row in FW_BEFORE for t in row if t)
    return f"""
<div class="kick">Scoring · worked example</div>
<h1 class="pt">A full end-of-game score</h1>
<p>Ana is about to play the <b>last wall-tiling phase</b> of the game. Her score marker is on <b>{FW_START}</b>.
She has three complete pattern lines (1, 3 and 5), two unfinished ones, and 2 tiles plus the starting player marker on her floor line.
Her wall already has {n_before} tiles. Tiles are placed from the top line down.</p>
<div class="grid2" style="grid-template-columns:1.35fr 1fr;gap:4mm;align-items:center">
<div class="box" style="padding:2mm 2mm 1mm">{img_final_board()}<p class="cap" style="text-align:center">Ana&rsquo;s board before phase B</p></div>
<div class="box" style="padding:2mm"><div style="width:52mm;margin:auto">{img_final_wall_after()}</div>
<p class="cap" style="text-align:center">Her wall after phase B (new tiles ringed)</p></div></div>
<h2>Step 1: wall-tiling, top line to bottom line</h2>
<table class="data"><tr><th>#</th><th>Tile moved</th><th>What counts</th><th>Points</th></tr>{trs}
<tr><th colspan="3" style="text-align:right">Wall points this phase</th><th>{sum(FW_PTS)}</th></tr></table>
<p class="need" style="margin-top:1mm">Line 1 completes row 1 (5 tiles in a line), so the game ends after this round. Lines 2 and 4 are not complete and keep their tiles.</p>
<h2>Step 2: floor line</h2>
<p>2 tiles + the starting player marker = 3 items: &minus;1 &minus;1 &minus;2 = <b>{FW_FLOOR_PEN}</b>.</p>
<h2>Step 3: end-of-game bonuses</h2>
<p>Her final wall has <b>{ANA_BD['rows']} complete row</b> (+{E.ROW_BONUS}), <b>{ANA_BD['columns']} complete columns</b> (columns 1 and 2, +{E.COLUMN_BONUS} each)
and <b>all 5 blue tiles</b> (+{E.COLOUR_BONUS}): {ANA_BD['row_points']} + {ANA_BD['column_points']} + {ANA_BD['colour_points']} = <b>{FW_BONUS}</b>.</p>
<h2>Total</h2>
<table class="data" style="font-size:10pt;width:90mm"><tr><th>Start of phase B</th><td>{FW_START}</td></tr>
<tr><th>+ wall points</th><td>{sum(FW_PTS)}</td></tr>
<tr><th>&minus; floor line</th><td>{FW_FLOOR_PEN}</td></tr>
<tr><th>+ end bonuses</th><td>+{FW_BONUS}</td></tr>
<tr><th style="font-size:11pt">Final score</th><td class="pts-big">{FW_TOTAL}</td></tr></table>
<p class="cap">Every number in this example was computed with the engine (<code>score_placement</code>, <code>floor_penalty</code>,
<code>end_bonus</code>, <code>bonus_breakdown</code>) and checked by the build script. The starting score {FW_START} is just a story choice.</p>
"""


def page_end():
    return f"""
<div class="kick">End of the game</div>
<h1 class="pt">End, bonuses &amp; tie-break</h1>
<p>The game ends <b>after phase B of the round</b> in which at least one player has completed at least one <b>horizontal row</b> on their wall (5 tiles across).
Finish that whole round&rsquo;s phase B for all players first, including floor line penalties. Then do <b>not</b> play phase C.
A full <b>column</b> does not end the game.</p>
<h2>End bonuses</h2>
<p>Each player now scores extra points for their wall:</p>
<div class="grid3">
<div class="box tint-n" style="text-align:center"><div class="pts-big">+{E.ROW_BONUS}</div><b>each complete horizontal row</b><br><span class="need">5 tiles across</span></div>
<div class="box tint-t" style="text-align:center"><div class="pts-big">+{E.COLUMN_BONUS}</div><b>each complete vertical column</b><br><span class="need">5 tiles down</span></div>
<div class="box tint-g" style="text-align:center"><div class="pts-big">+{E.COLOUR_BONUS}</div><b>each colour with all 5 tiles</b><br><span class="need">on your wall</span></div></div>
<h2>Bonus example</h2>
<div class="grid2" style="grid-template-columns:1fr 1.15fr;align-items:center;gap:5mm">
<div class="box" style="padding:3mm"><div style="width:56mm;margin:auto">{img_bonus()}</div>
<p class="cap" style="text-align:center">Ana&rsquo;s final wall. Shaded gold: the full row and the two full columns. Ringed in red: her five blue tiles.</p></div>
<div><p>At the end, Ana&rsquo;s wall has <b>{ANA_BD['rows']} complete row</b>, <b>{ANA_BD['columns']} complete columns</b>, and <b>all 5 blue tiles</b> ({Ts("BBBBB")}).</p>
<table class="pts" style="width:100%"><tr><th>Bonus</th><td>how many</td><td>points</td></tr>
<tr><th>Rows &times; {E.ROW_BONUS}</th><td>{ANA_BD['rows']}</td><td>{ANA_BD['row_points']}</td></tr>
<tr><th>Columns &times; {E.COLUMN_BONUS}</th><td>{ANA_BD['columns']}</td><td>{ANA_BD['column_points']}</td></tr>
<tr><th>Colours &times; {E.COLOUR_BONUS}</th><td>{ANA_BD['colours']}</td><td>{ANA_BD['colour_points']}</td></tr>
<tr><th>Bonus total</th><td></td><td><b>{ANA_BD['total']}</b></td></tr></table>
<p class="need">2 + 7 + 7 + 10 = <b>{ANA_BD['total']} points</b>.</p></div></div>
<h2>Winner and tie-break</h2>
<div class="grid2"><div class="box tint-n"><h3>Winner</h3><p style="margin:0">The player with the <b>most points</b> wins.</p></div>
<div class="box tint-t"><h3>Tie</h3><p style="margin:0">If players are tied for the most points, the tied player with <b>more complete horizontal rows</b>
on their wall wins. If they are still tied, they <b>share the victory</b>.</p></div></div>
<h2>The three bonuses side by side</h2>
<table class="data" style="font-size:8.4pt"><tr><th>Goal</th><th>Bonus</th><th>On the wall</th></tr>
<tr><td>Complete row</td><td>+{E.ROW_BONUS}</td><td>5 tiles side by side (also ends the game)</td></tr>
<tr><td>Complete column</td><td>+{E.COLUMN_BONUS}</td><td>5 tiles down, one in each row</td></tr>
<tr><td>All 5 of one colour</td><td>+{E.COLOUR_BONUS}</td><td>5 tiles of that colour anywhere on the wall</td></tr></table>
<div class="box tint-g" style="margin-top:3mm"><span class="tag tip">Tip, not a rule</span>
A full column (+{E.COLUMN_BONUS}) and a full colour (+{E.COLOUR_BONUS}) are worth more than a full row (+{E.ROW_BONUS}). Plan for them before someone ends the game.
Completing the first full row ends the game after that round, so don&rsquo;t rush it if you are behind.</div>
"""


def page_grey():
    tips = [
        "<b>Complete lines before the round ends.</b> An unfinished pattern line scores nothing this round. Start with the short lines (1, 2 and 3); they are easy to finish.",
        "<b>Count before you take.</b> Before taking 4 tiles of a colour, check which of your lines has room for 4. Extra tiles fall to the floor and cost points.",
        "<b>The floor line hurts fast.</b> The first two items cost 1 each, but the 6th and 7th cost 3 each.",
        "<b>Build next to your own tiles.</b> A tile that touches others scores more. Placing tiles in a cross (across and down) scores both counts.",
        "<b>The starting player marker has a price.</b> It costs at least 1 point, but going first next round lets you pick the best tiles. Sometimes that is worth it.",
        "<b>Watch what you leave in the centre.</b> Tiles pushed to the centre pile up. Late in the round, someone may be forced to take a big pile they can&rsquo;t use.",
        "<b>Watch your opponents&rsquo; boards.</b> If someone needs exactly 3 red for their line 3, taking the red first can block them.",
    ]
    return f"""
<div class="kick">Variant · and some advice</div>
<h1 class="pt">The grey wall variant</h1>
<p>If you like, all players can play on the <b>grey side</b> of their player boards. On the grey side, the wall spaces have no colours.
Remember: all players use the same side. The rules are exactly the same as the normal game, except for these points:</p>
<div class="grid3">
<div class="box tint-n"><h3>Free choice of space</h3><p style="margin:0">In phase B, when you move a tile from a complete pattern line to your wall, you may put it on <b>any empty space</b> in the wall row beside that line.</p></div>
<div class="box tint-t"><h3>Column rule</h3><p style="margin:0">Each colour may appear <b>only once in each column</b> of your wall. (Each colour already may appear only once in each row; that rule is unchanged.)</p></div>
<div class="box tint-r"><h3>Special case</h3><p style="margin:0">If there is no allowed space for the tile in its row, put <b>all</b> tiles of that pattern line on your floor line. Tiles beyond the 7th space go to the box lid.</p></div></div>
<div class="grid2" style="margin-top:3mm">
<div class="box" style="padding:2.5mm"><div style="width:52mm;margin:auto">{img_grey(GREY_A, GREY_A_OPT)}</div>
<p class="cap"><b>Free choice.</b> Line 3 is complete with blue ({T("B")}). Blue is already in columns 1 and 2, so the spaces of row 3 where it may go are the three dashed ones (columns 3, 4 and 5).</p></div>
<div class="box" style="padding:2.5mm"><div style="width:52mm;margin:auto">{img_grey(GREY_B, (), (3, 4))}</div>
<p class="cap"><b>Special case.</b> Line 5 is complete with blue, but row 5&rsquo;s two empty spaces are in columns 4 and 5, which already hold blue. No space is allowed, so all 5 blue tiles go to the floor line.</p></div></div>
<p class="cap">Both pictures were checked with the engine&rsquo;s <code>grey_columns</code>.</p>
<p>Scoring, floor penalties, the end of the game, bonuses and the tie-break are unchanged. The colour bonus (+{E.COLOUR_BONUS}) counts tiles of that colour anywhere on your wall.</p>
<h2>Beginner tips <span class="tag tip">not rules</span></h2>
<ul style="font-size:8.9pt">{"".join(f"<li>{t}</li>" for t in tips)}</ul>
"""


def page_faq():
    qa = [
        ("Can I put only some of my tiles in a pattern line and drop the rest on the floor?",
         "All the tiles you take go into one pattern line, and only the extra tiles that don&rsquo;t fit go to the floor line. You may also put the whole group on the floor line."),
        ("Can I choose the floor line even when a pattern line could take the tiles?", "Yes."),
        ("Can I take tiles from the centre if it holds only the starting player marker?",
         "No. You must take tiles. The marker alone is not a choice; it is only taken together with tiles."),
        ("What if my floor line is already full when I take the starting player marker?",
         "The rules don&rsquo;t cover this. <span class='tag house'>House rule</span> keep the marker beside your board. You don&rsquo;t lose extra points for it, but you are still the starting player of the next round."),
        ("What if nobody takes tiles from the centre all round?",
         "Very rare (every factory display would need to hold 4 tiles of a single colour). <span class='tag house'>House rule</span> the same starting player starts the next round."),
        ("My score goes past 100. What now?",
         "The score track ends at 100; the rules don&rsquo;t say more. <span class='tag house'>House rule</span> keep going round the track and remember that you have passed 100."),
        ("Does a pattern line keep its tiles if it isn&rsquo;t complete?", "Yes. You can add more of the same colour later."),
        ("Can I change the colour of a pattern line that has tiles?", "No. A line keeps its colour until it is complete and emptied in phase B."),
        ("Do tiles I put on the wall in the same phase count for later tiles?", "Yes. Tiles are placed from the top line down; a tile already placed this phase counts as a neighbour."),
        ("What is the most I can lose on the floor line in one round?", f"{abs(E.floor_penalty(7))} points: all 7 spaces filled. Extra tiles go to the box lid without costing more."),
        ("Can my score drop below 0?", "No. It stops at 0."),
        ("Does a full column end the game?", "No. Only a full horizontal row ends the game, at the end of that round&rsquo;s phase B."),
        ("When does the bag get refilled?", "Only while filling factory displays in phase C (or setup), at the moment the bag runs empty. Then all tiles from the box lid go back into the bag."),
        ("On the grey wall, may I take tiles into a pattern line whose colour has no space left in that row?",
         "Yes. The rules only forbid a colour that is already in that wall row. But if the line is complete in phase B and there is no allowed space, all of its tiles go to your floor line."),
    ]
    half = (len(qa) + 1) // 2
    col = lambda items: "".join(f"<h4>{q}</h4><p>{a}</p>" for q, a in items)
    gl = [("Fliese", "tile"), ("Beutel", "bag"), ("Manufakturpl&auml;ttchen", "factory display"), ("Tischmitte", "centre of the table"),
          ("Spielerablage", "player board"), ("Punktemarker", "score marker"), ("Punkteleiste", "score track"),
          ("Musterreihen", "pattern lines"), ("Wand", "wall"), ("Bodenreihe", "floor line"),
          ("Startspielermarker", "starting player marker"), ("(Schachtel-)Deckel", "box lid"),
          ("Musterphase", "factory offer (phase A)"), ("Fliesungsphase", "wall-tiling (phase B)"),
          ("Vorbereiten der n&auml;chsten Runde", "preparing the next round (phase C)"),
          ("Wertung", "scoring"), ("Spielende", "end of the game"), ("Variante", "variant")]
    gtab = "".join("<table class='data' style='font-size:7.8pt'><tr><th>German</th><th>English</th></tr>"
                   + "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in gl[i * 6:(i + 1) * 6]) + "</table>"
                   for i in range(3))
    return f"""
<div class="kick">Questions</div>
<h1 class="pt">FAQ &amp; glossary</h1>
<div class="grid2 fq" style="gap:6mm;margin-top:2mm"><div>{col(qa[:half])}</div><div>{col(qa[half:])}</div></div>
<h2>Glossary: German rulebook &rarr; this manual</h2>
<div class="grid3" style="gap:2.5mm">{gtab}</div>
<p class="cap" style="margin-top:3mm">This manual follows the German rulebook (2018), which gives the same numbers as the published English rules.</p>
"""


def page_scoresheet():
    def block(n):
        head = "".join(f"<th>Player {i}</th>" for i in range(1, 5))
        blank = "<td></td>" * 4
        rows = "".join(f"<tr><th>{lbl}</th>{blank}</tr>" for lbl in (
            "Name", "Score before bonus", f"Rows &times; {E.ROW_BONUS}", f"Columns &times; {E.COLUMN_BONUS}",
            f"Colours &times; {E.COLOUR_BONUS}", "Final score", "Complete rows"))
        return (f'<table class="sheet"><tr class="g"><th colspan="5">Game {n}</th></tr><tr><th></th>{head}</tr>{rows}'
                f'<tr><th>Winner</th>{"<td><span class=cb></span></td>" * 4}</tr></table>')
    tail = ("<table class='sheet' style='margin-top:3.5mm'><tr class='g'><th colspan='5'>Games won over the session</th></tr>"
            "<tr><th>Player</th><th>1</th><th>2</th><th>3</th><th>4</th></tr>"
            "<tr><th>Games won</th><td></td><td></td><td></td><td></td></tr></table>")
    return f"""
<div class="kick">Photocopy me</div>
<h1 class="pt">Score sheet</h1>
<p class="need" style="margin-bottom:2.5mm">For 2 to 4 players, six games per sheet. Write the score from the score track <b>before</b> the end bonuses,
then add rows (+{E.ROW_BONUS} each), columns (+{E.COLUMN_BONUS} each) and colours (+{E.COLOUR_BONUS} each). Most points wins; tie: more complete rows (write the number in the last row); still tied: shared victory.</p>
<div class="grid2" style="gap:3.5mm">{"".join(block(i) for i in range(1, 7))}</div>
{tail}
"""


def page_quickref():
    ft = "".join(f"<td>&minus;{abs(v)}</td>" for v in E.FLOOR_VALUES)
    fh = "".join(f"<td>{n}</td>" for n in range(1, 8))
    tt = "".join(f"<td>{abs(t)}</td>" for t in FLOOR_TOTALS)
    mini = "".join(f'<div style="width:25mm">{img_score_ex(SC_EX[i])}<div class="need" style="text-align:center"><b>{SC_EX[i]["pts"]}</b></div></div>'
                   for i in (0, 1, 3))
    return f"""
<div class="kick">Keep this side up</div>
<h1 class="pt">Quick reference</h1>
<div class="qr">
<div class="box tint-n" style="margin-bottom:2mm"><p style="margin:0"><b>Goal:</b> collect tiles, complete pattern lines, move tiles to your wall for points.
The game ends after the round in which someone completes a horizontal wall row. Most points wins.</p></div>
<p><b>Setup:</b> all players use the <b>same board side</b> (coloured; grey = variant) · score markers on 0 · factory displays: <b>5 / 7 / 9</b> for <b>2 / 3 / 4</b> players ·
{E.TOTAL_TILES} tiles ({E.TILES_PER_COLOUR} &times; {Ts("BYRKW")} B blue, Y yellow, R red, K black, W white) in the bag · the starting player takes the marker and puts <b>4 tiles</b> on each factory display.</p>
<h2 style="margin-top:2mm">Each round</h2>
<div class="grid3" style="margin-bottom:2mm">
<div class="box tint-n"><h3>A. Factory offer</h3>
<p>The starting player puts the marker in the centre and goes first; then clockwise.</p>
<ol><li>Take <b>all tiles of one colour</b> from <b>one factory display</b> (push the rest into the centre) <b>or</b> from <b>the centre</b>. The first to take from the centre also takes the marker &rarr; leftmost floor space.</li>
<li>Put them all in <b>one pattern line</b>, right to left. One colour per line; not a colour already in that wall row. Extras &rarr; floor line. You may put them all on the floor line instead.</li>
<li>Phase ends when all factory displays <b>and</b> the centre are empty.</li></ol></div>
<div class="box tint-t"><h3>B. Wall-tiling</h3>
<p>Everyone at once, lines top to bottom.</p>
<ul><li><b>Complete</b> line &rarr; rightmost tile to the same-colour space in that wall row, score it now; rest of the line &rarr; box lid.</li>
<li>Incomplete lines stay as they are.</li><li>Then pay the floor line.</li></ul></div>
<div class="box tint-g"><h3>C. Prepare</h3>
<p>If nobody has a full row: the marker holder puts 4 tiles on each factory display.</p>
<ul><li>Bag empty &rarr; pour in the box lid and continue.</li><li>Bag and lid both empty &rarr; start anyway.</li></ul></div></div>
<div class="grid2">
<div class="box"><h3>Scoring a new wall tile</h3>
<ul><li>No neighbour across or down &rarr; <b>1</b>.</li>
<li>Otherwise: tiles in its unbroken line <b>across</b> (if &ge; 2) <b>+</b> tiles in its unbroken line <b>down</b> (if &ge; 2).</li></ul>
<div style="display:flex;gap:3mm;align-items:flex-end">{mini}</div>
<p class="need" style="margin:0">Lone tile {SC_EX[0]['pts']} · line of 3 across = {SC_EX[1]['pts']} · across 4 and down 3 = <b>{SC_EX[3]['pts']}</b></p></div>
<div class="box tint-r"><h3>Floor line (end of phase B)</h3>
<table class="pts" style="width:100%;font-size:8pt"><tr><th>Items</th>{fh}</tr><tr><th>Spaces</th>{ft}</tr><tr><th>Total lost</th>{tt}</tr></table>
<p style="margin:0">The starting player marker counts as an item (then keep it: you start next round) · tiles past space 7 &rarr; box lid, no extra cost · score never below 0.</p></div></div>
<div class="grid2" style="margin-top:2mm">
<div class="box tint-t"><h3>End of game</h3>
<p>After phase B of the round in which <b>any player completes a horizontal row</b> (a full column doesn&rsquo;t end it). Bonuses:</p>
<table class="pts" style="width:100%"><tr><th>Each</th><th>Bonus</th></tr>
<tr><td>complete row (across)</td><td><b>+{E.ROW_BONUS}</b></td></tr>
<tr><td>complete column (down)</td><td><b>+{E.COLUMN_BONUS}</b></td></tr>
<tr><td>colour with all 5 tiles on the wall</td><td><b>+{E.COLOUR_BONUS}</b></td></tr></table>
<p style="margin:0"><b>Tie:</b> more complete rows wins; still tied &rarr; shared victory.</p></div>
<div class="box tint-k"><h3>Grey-wall variant</h3>
<p style="margin:0">Place each tile on <b>any empty space</b> of its row · each colour <b>once per column</b> (and once per row) · no allowed space &rarr; <b>all</b> tiles of that line go to the floor line.</p>
<h3 style="margin-top:3mm">Tile letters</h3>
<div style="display:flex;gap:3mm">{letters_row()}</div></div></div>
</div>
"""


PAGES = [page_cover, page_goal, page_setup, page_turn, page_phase_a1, page_phase_a2, page_phase_b,
         page_floor_c, page_worked, page_end, page_grey, page_faq, page_scoresheet, page_quickref]
assert len(PAGES) % 2 == 0


def build_html():
    out = []
    for n, fn in enumerate(PAGES, 1):
        side = "odd" if n % 2 else "even"
        foot = "" if n == 1 else f'<footer><span class="pn">{n}</span><span>{FOOT}</span></footer>'
        out.append(f'<section class="page {side}" id="p{n}">{CORNERS}<div class="content">{fn()}</div>{foot}</section>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Azul · Player manual</title>'
            f'<style>{font_faces()}{CSS}</style></head><body>{"".join(out)}</body></html>')


NODE = r"""
const { chromium } = require('playwright');
(async () => {
  const [htmlPath, pdfPath] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + htmlPath, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  const over = await page.evaluate(() => [...document.querySelectorAll('.page')].map((p, i) => {
    const c = p.querySelector('.content');
    const r = c.getBoundingClientRect();
    let worst = 0;
    c.querySelectorAll('*').forEach(e => { const b = e.getBoundingClientRect();
      if (b.height) worst = Math.max(worst, b.bottom - r.bottom, b.right - r.right); });
    return [i + 1, Math.round(worst), c.scrollHeight > c.clientHeight + 1];
  }).filter(([, w, s]) => w > 1 || s));
  await page.pdf({ path: pdfPath, preferCSSPageSize: true, printBackground: true });
  await browser.close();
  console.log(JSON.stringify(over));
})().catch(e => { console.error(e); process.exit(1); });
"""


def main():
    with tempfile.TemporaryDirectory() as tmp:
        hp = Path(tmp) / "manual-color.html"
        hp.write_text(build_html(), encoding="utf-8")
        if "--html" in sys.argv:
            Path(os.environ.get("AZUL_HTML", "/tmp/azul-preview.html")).write_text(hp.read_text(), encoding="utf-8")
        js = Path(tmp) / "print.js"
        js.write_text(NODE)
        env = dict(os.environ)
        npm_root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
        env["NODE_PATH"] = os.pathsep.join(filter(None, [env.get("NODE_PATH"), npm_root]))
        res = subprocess.run(["node", str(js), str(hp), str(OUT_PDF)], cwd=ROOT, env=env,
                             capture_output=True, text=True)
        if res.returncode:
            sys.exit(res.stderr)
    over = json.loads(res.stdout.strip().splitlines()[-1])
    for n, px, _ in over:
        print(f"WARNING: page {n} content overflows by {px}px")
    print(f"Wrote {OUT_PDF.relative_to(ROOT)} ({len(PAGES)} pages)")
    if over:
        sys.exit(1)


if __name__ == "__main__":
    main()
