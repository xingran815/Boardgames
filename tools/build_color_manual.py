#!/usr/bin/env python3
"""Build the full-colour, printable rules manual for Spirits of the Wild.

    python3 tools/build_color_manual.py

1. Draws original illustrations with the project's own renderer
   (tools/sotw/render.py) in a light "print" theme and saves them to
   docs/spirits-of-the-wild/manual-assets/.
2. Writes an HTML page per A4 page (fixed page boxes, mirrored inner/outer
   margins for double-sided printing, page numbers on the outer edge).
3. Prints it to docs/spirits-of-the-wild/manual-color.pdf with Chromium via
   the node `playwright` module, and warns about any page whose content
   overflows its box.

Requires Pillow, node + playwright (Chromium) and the Inter font.
Content follows docs/spirits-of-the-wild/manual.md (Owl pairs = 4 points).
"""
from __future__ import annotations

import html
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "sotw"))
import engine as E  # noqa: E402
import render as R  # noqa: E402

DOCS = ROOT / "docs" / "spirits-of-the-wild"
ASSETS = DOCS / "manual-assets"
OUT_PDF = DOCS / "manual-color.pdf"

# ============================================================ light theme
# The renderer reads these module globals at draw time, so swapping them gives
# a white-paper version of every board/card drawing (saves ink when printed).
R.BG = (255, 255, 255)
R.PANEL = (248, 246, 240)
R.INK = (28, 32, 48)
R.MUTED = (84, 92, 116)
R.ACCENT = (31, 78, 121)
R.GOLD = (140, 88, 8)
R.HL = (205, 78, 28)
R.CARD_UP = (128, 72, 48)
R.CARD_DOWN = (226, 222, 230)
R.ANIMAL_LABEL = {  # British spelling to match the manual text
    a: (n, req.replace("color", "colour"), pts) for a, (n, req, pts) in R.ANIMAL_LABEL.items()}

LETTER = {"green": "G", "yellow": "Y", "blue": "B", "purple": "P", "white": "W",
          "red": "R", "clear": "S"}
DARK_LETTER = {"green", "yellow", "white", "clear"}
BOLD = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"


def _bold(px):
    try:
        return ImageFont.truetype(BOLD, int(px))
    except OSError:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(px))


def stone(d, cx, cy, r, color, outline=None):
    """Print-friendly stone: soft shadow, dark rim and the colour's initial
    (so the drawings still read on a black-and-white printer)."""
    if color is None:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(150, 158, 182), width=2.5)
        return
    fill = R.STONE[color]
    d.ellipse((cx - r + 1.5, cy - r + 3, cx + r + 1.5, cy + r + 3), fill=(205, 207, 216))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill,
              outline=outline or (45, 45, 60), width=2.5 if not outline else 5)
    d.ellipse((cx - r * 0.62, cy - r * 0.70, cx - r * 0.25, cy - r * 0.40),
              fill=tuple(min(255, v + 55) for v in fill))
    if color == "clear":
        d.ellipse((cx - r * 0.72, cy - r * 0.72, cx + r * 0.72, cy + r * 0.72),
                  outline=(120, 150, 175), width=1.5)
    if r >= 11:
        f = _bold(r * 1.0 * d.s)
        ink = (25, 25, 35) if color in DARK_LETTER else (255, 255, 255)
        d.d.text((cx * d.s, (cy + r * 0.04) * d.s), LETTER[color], font=f, anchor="mm", fill=ink)


R.stone = stone  # bstone() and friends look the name up at call time


class LightDraw(R.SDraw):
    def veil(self, box, color=(255, 255, 255), alpha=150, radius=16):
        super().veil(box, color=(255, 255, 255), alpha=150, radius=radius)


def canvas(w, h, s=3):
    im = Image.new("RGB", (int(w * s), int(h * s)), R.BG)
    return im, LightDraw(im, s)


def section(d, x, y, w, h, board, animal, blocked=False):
    R.CTX["player"] = 0
    R.draw_section(d, x, y, w, h, board, animal, blocked=blocked)
    if not board["bonus"][animal]:  # redraw the empty x2 space with more contrast
        bx, by, br = x + w - 34, y + 30, 20
        d.ellipse((bx - br, by - br, bx + br, by + br), fill=R.PANEL, outline=R.ACCENT, width=2.5)
        R.text_center(d, (bx, by - 12), "x2", R.F["xsb"], fill=R.ACCENT)


def board_with(**kw):
    b = E.new_board()
    for k, v in kw.items():
        if k == "bonus":
            for a in v:
                b["bonus"][a] = True
        else:
            b[k] = v
    return b


def save(im, name):
    ASSETS.mkdir(parents=True, exist_ok=True)
    im.save(ASSETS / name, optimize=True)
    return name


def badge(d, cx, cy, n, r=24):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(47, 107, 79), outline=(255, 255, 255), width=3)
    d.d.text((cx * d.s, (cy + 1) * d.s), str(n), font=_bold(r * 1.25 * d.s), anchor="mm",
             fill=(255, 255, 255))


def label(d, x, y, s, f="xsb", fill=None, center=False):
    if center:
        R.text_center(d, (x, y), s, R.F[f], fill=fill or R.MUTED)
    else:
        d.text((x, y), s, font=R.F[f], fill=fill or R.MUTED)


# ------------------------------------------------------------ illustrations
def img_swatches():
    names = []
    for c in E.COLORS + [E.CLEAR]:
        im, d = canvas(64, 64, s=6)
        stone(d, 31, 30, 27, c)
        names.append(save(im, f"stone-{c}.png"))
    return names


def img_cover():
    W, H = 1500, 820
    im, d = canvas(W, H, s=2)
    # a constellation of the five animal spirits, drawn with stones
    pts = [(170, 300, "green"), (380, 170, "yellow"), (610, 260, "blue"), (860, 140, "purple"),
           (1090, 250, "white"), (1320, 160, "red")]
    for (x0, y0, _), (x1, y1, _) in zip(pts, pts[1:]):
        d.line((x0, y0, x1, y1), fill=(170, 182, 205), width=3)
    for x, y, c in pts:
        stone(d, x, y, 46, c)
    import random
    rnd = random.Random(4)
    for _ in range(70):  # little stars
        x, y = rnd.randrange(30, W - 30), rnd.randrange(20, 420)
        if any(abs(x - px) < 70 and abs(y - py) < 70 for px, py, _ in pts):
            continue
        rr = rnd.choice([3, 3, 4, 6])
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(190, 198, 220))
    # a hill with the coyote and the bowl
    d.ellipse((-200, 560, W + 200, 1500), fill=(236, 241, 230), outline=(190, 205, 180), width=3)
    R.draw_coyote(d, 980, 420, 3.1)
    bx, by = 290, 600
    d.ellipse((bx, by, bx + 520, by + 180), fill=(205, 180, 140), outline=(120, 90, 60), width=4)
    d.ellipse((bx + 26, by + 18, bx + 494, by + 150), fill=(232, 214, 180))
    for i, c in enumerate(["red", "clear", "green", "yellow", "blue"]):
        stone(d, bx + 130 + i * 66, by + 84 - (i % 2) * 10, 30, c)
    return save(im, "cover.png")


def img_sections():
    ex = {
        "rabbit": board_with(rabbit=["green", "yellow", "red"]),
        "turtle": board_with(turtle=["blue"] * 4),
        "salmon": board_with(salmon=["green", "yellow", "blue", "purple", "red"]),
        "owl": board_with(owl=[["red", "red"], ["white", "white"], ["green"]]),
        "beaver": board_with(beaver={"triple": ["purple"] * 3, "pair": ["yellow"] * 2}),
    }
    out = {}
    for a, b in ex.items():
        im, d = canvas(340, 206)
        section(d, 3, 3, 334, 200, b, a)
        out[a] = (save(im, f"animal-{a}.png"), E.animal_score(b, a))
    # spirit stone doubling a full turtle
    b = board_with(turtle=["red"] * 5, bonus=["turtle"])
    im, d = canvas(340, 206)
    section(d, 3, 3, 334, 200, b, "turtle")
    out["spirit"] = (save(im, "spirit-turtle.png"), E.animal_score(b, "turtle"))
    # coyote blocking a salmon
    b = board_with(salmon=["green", "blue", "white"])
    im, d = canvas(340, 206)
    section(d, 3, 3, 334, 200, b, "salmon", blocked=True)
    out["blocked"] = (save(im, "coyote-blocked.png"), E.animal_score(b, "salmon"))
    return out


EXAMPLE = board_with(
    rabbit=["green", "blue", "red"], turtle=["blue"] * 4,
    salmon=["yellow", "purple", "red"],
    owl=[["white", "white"], ["green", "green"], ["red"]],
    beaver={"triple": ["yellow"] * 3, "pair": []}, bonus=["turtle"])


def img_example():
    w, h, g = 300, 200, 14
    im, d = canvas(5 * w + 4 * g + 6, h + 6, s=2.4)
    for i, a in enumerate(E.ANIMALS):
        section(d, 3 + i * (w + g), 3, w, h, EXAMPLE, a)
    return save(im, "example-board.png")


def img_cards(cards, name, hl=None, pad=6):
    W = 3 * R.CW + 2 * R.CG + 2 * pad
    H = 2 * R.CH + R.CG + 2 * pad
    im, d = canvas(W, H, s=3)
    R.draw_cards(d, pad, pad, cards, hl=hl)
    return save(im, name)


def img_card_faces():
    out = {}
    im, d = canvas(3 * R.CW + 2 * R.CG + 12, 2 * R.CH + R.CG + 12, s=3)
    R.draw_cards(d, 6, 6, {c: True for c in E.CARD_ORDER})
    for i, c in enumerate(E.CARD_ORDER):
        x0, y0, x1, y1 = R.card_rect(6, 6, i)
        crop = im.crop((int((x0 - 3) * 3), int((y0 - 3) * 3), int((x1 + 3) * 3), int((y1 + 3) * 3)))
        out[c] = save(crop, f"card-{c}.png")
    return out


def light_card(d, x, y, w, h, title, lines, top=True):
    d.rounded_rectangle((x, y, x + w, y + h), 14, fill=(236, 242, 250) if top else (222, 230, 242),
                        outline=(31, 78, 121), width=3)
    if title:
        R.text_center(d, (x + w / 2, y + 14), title, R.F["h3"], fill=R.ACCENT)
        for j, ln in enumerate(lines):
            R.text_center(d, (x + w / 2, y + 62 + j * 28), ln, R.F["xs"], fill=R.INK)


def img_setup():
    g = E.Game(seed=2)
    g.setup()
    st = g.snapshot()
    W, H = 2030, 935
    im, d = canvas(W, H, s=2.0)
    sw, sh, sg = 300, 196, 12

    def player(p, y, name):
        R.CTX["player"] = p
        R.draw_cards(d, 20, y + 20, st["cards"][p])
        bx = 420
        bw = 5 * sw + 4 * sg + 36
        d.rounded_rectangle((bx, y, bx + bw, y + sh + 66), 20, fill=(252, 251, 247),
                            outline=(120, 132, 160), width=3)
        d.text((bx + 18, y + 10), name, font=R.F["h3"], fill=R.INK)
        for i, a in enumerate(E.ANIMALS):
            section(d, bx + 18 + i * (sw + sg), y + 54, sw, sh, st["boards"][p], a)
        return bx, bw

    bx, bw = player(1, 16, "Ben's board")
    bx, bw = player(0, 660, "Ana's board  (start player)")
    my = 330
    # bag
    d.rounded_rectangle((40, my + 40, 300, my + 300), 40, fill=(122, 92, 70),
                        outline=(70, 50, 36), width=4)
    d.polygon([(110, my + 40), (230, my + 40), (200, my + 8), (140, my + 8)], fill=(100, 74, 56))
    R.text_center(d, (170, my + 110), "BAG", R.F["h2"], fill=(255, 245, 230))
    R.text_center(d, (170, my + 170), f"{st['bag']} stones", R.F["s"], fill=(255, 245, 230))
    R.text_center(d, (170, my + 206), "(all 8 Spirit", R.F["xs"], fill=(255, 235, 215))
    R.text_center(d, (170, my + 234), "Stones inside)", R.F["xs"], fill=(255, 235, 215))
    # bowl
    cx = 650
    d.ellipse((cx - 260, my + 60, cx + 260, my + 290), fill=(205, 180, 140),
              outline=(120, 90, 60), width=4)
    d.ellipse((cx - 232, my + 82, cx + 232, my + 266), fill=(232, 214, 180))
    for i, c in enumerate(st["bowl"]):
        stone(d, cx - 105 + i * 70, my + 172, 28, c)
    R.text_center(d, (cx, my + 14), "BOWL: 4 regular stones", R.F["sb"], fill=R.INK)
    # spirit piles
    px = 1130
    R.text_center(d, (px + 250, my - 2), "SPIRIT POWER CARDS: 2 piles of 3", R.F["sb"], fill=R.INK)
    for i, pile in enumerate(st["piles"]):
        x = px + i * 260
        for k in (2, 1):
            light_card(d, x + k * 9, my + 44 + k * 9, 220, 190, None, [], top=False)
        light_card(d, x, my + 44, 220, 190, pile[0].upper(),
                   [s for s in R.SPIRIT_SHORT[pile[0]]])
        R.text_center(d, (x + 110, my + 262), "top card face-up", R.F["xs"], fill=R.MUTED)
    # coyote waiting at the side
    R.draw_coyote(d, 1885, my + 90, 1.9)
    R.text_center(d, (1936, my + 230), "Coyote", R.F["xsb"], fill=R.INK)
    R.text_center(d, (1936, my + 258), "waits aside", R.F["xs"], fill=R.MUTED)
    # step numbers
    badge(d, 1940, my + 60, 1)
    badge(d, 70, my + 40, 2)
    badge(d, cx - 250, my + 76, 3)
    badge(d, bx + bw - 30, 660 + 30, 4)
    badge(d, bx + bw - 30, 16 + 30, 4)
    badge(d, px - 30, my + 60, 5)
    x0, y0, x1, y1 = R.card_rect(20, 680, 2)
    d.rounded_rectangle((x0, y0, x1, y1), 10, fill=R.CARD_DOWN, outline=(90, 80, 100), width=2)
    R.text_center(d, ((x0 + x1) / 2, y0 + 34), "face-", R.F["sb"], fill=R.INK)
    R.text_center(d, ((x0 + x1) / 2, y0 + 64), "down", R.F["sb"], fill=R.INK)
    d.rounded_rectangle((x0 - 4, y0 - 4, x1 + 4, y1 + 4), 12, outline=R.HL, width=5)
    badge(d, x1 + 4, y0 + 2, 6)
    return save(im, "setup-table.png")


def build_images():
    imgs = {"swatch": img_swatches(), "cover": img_cover(), "sections": img_sections(),
            "example": img_example(), "faces": img_card_faces(), "setup": img_setup()}
    up = {c: True for c in E.CARD_ORDER}
    imgs["cycle"] = img_cards({**up, E.TAKE1A: False, E.TAKE1B: False, E.ADD2: False},
                              "cards-ready-to-recover.png", hl=E.SPIRIT)
    imgs["backs"] = img_cards({**up, E.TAKE1A: False, E.TAKE1B: False}, "cards-coyote-backs.png")
    im, d = canvas(70, 80, s=5)
    R.draw_coyote(d, 8, 7, 1.0)
    imgs["coyote"] = save(im, "coyote.png")
    return imgs




# ================================================================== HTML
def src(name):
    return (ASSETS / name).as_uri()


def st(c, cls="st"):
    nm = "Spirit Stone (clear)" if c == "clear" else c
    return f'<img class="{cls}" src="{src(f"stone-{c}.png")}" alt="{nm}">'


def stones(*cs):
    return "".join(st(c) for c in cs)


def table_pts(head, pts):
    th = "".join(f"<td>{h}</td>" for h in head)
    tp = "".join(f"<td>{p}</td>" for p in pts)
    return (f'<table class="pts"><tr><th>Stones</th>{th}</tr>'
            f'<tr><th>Points</th>{tp}</tr></table>')


CSS = r"""
@page { size: A4; margin: 0; }
:root {
  --ink: #1d2433; --muted: #566079; --rule: #c9cfdb; --paper: #ffffff;
  --forest: #2f6b4f; --forest-t: #eaf3ee; --blue: #1f4e79; --blue-t: #eaf1f8;
  --amber: #8c5808; --amber-t: #fbf3e2; --coyote: #b8561b; --coyote-t: #fbeee4;
  --plum: #6b3f87; --plum-t: #f3edf8;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #fff; }
body { font-family: "Inter", "DejaVu Sans", sans-serif; color: var(--ink); font-size: 9.5pt;
       line-height: 1.38; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.page { width: 210mm; height: 297mm; position: relative; overflow: hidden; background: #fff;
        page-break-after: always; break-after: page; padding: 13mm 14mm 17mm 19mm; }
.page.even { padding: 13mm 19mm 17mm 14mm; }
.content { height: 100%; overflow: hidden; display: flex; flex-direction: column; }
footer { position: absolute; bottom: 8.5mm; left: 19mm; right: 14mm; display: flex;
         justify-content: space-between; align-items: center; font-size: 7.6pt; color: var(--muted);
         flex-direction: row-reverse; border-top: 0.6pt solid var(--rule); padding-top: 1.6mm; }
.even footer { left: 14mm; right: 19mm; flex-direction: row; }
footer .pn { font-weight: 800; font-size: 10pt; color: var(--forest); }
h1, h2, h3, h4 { font-family: "Inter Display", "Inter", sans-serif; margin: 0; line-height: 1.15; }
h1.pt { font-size: 22pt; font-weight: 800; color: var(--forest); margin-bottom: 1mm; }
.kick { font-size: 8pt; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
        color: var(--muted); }
.lead { font-size: 10.5pt; color: var(--ink); margin: 1mm 0 4mm; }
h2 { font-size: 13.5pt; font-weight: 800; color: var(--blue); margin: 4mm 0 2mm;
     padding-bottom: 1mm; border-bottom: 1.2pt solid var(--blue); }
h3 { font-size: 11pt; font-weight: 800; color: var(--ink); margin: 0 0 1.2mm; }
p { margin: 0 0 2mm; }
ul, ol { margin: 0 0 2mm; padding-left: 5mm; }
li { margin: 0 0 1mm; }
b, strong { font-weight: 700; }
.st { height: 1.25em; width: 1.25em; vertical-align: -0.28em; margin: 0 .05em; }
.box { border: 0.8pt solid var(--rule); border-radius: 3mm; padding: 3mm 3.5mm; background: #fff;
       break-inside: avoid; }
.tint-f { background: var(--forest-t); border-color: #b8d5c4; }
.tint-b { background: var(--blue-t); border-color: #bcd0e6; }
.tint-a { background: var(--amber-t); border-color: #e8d2a6; }
.tint-c { background: var(--coyote-t); border-color: #ecc7ad; }
.tint-p { background: var(--plum-t); border-color: #d6c5e4; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 3.5mm; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 3mm; }
.tag { display: inline-block; font-size: 7pt; font-weight: 800; letter-spacing: .06em;
       text-transform: uppercase; border: 0.8pt solid currentColor; border-radius: 1.2mm;
       padding: .2mm 1.4mm; vertical-align: .1em; }
.tag.house { color: var(--plum); background: var(--plum-t); }
.tag.ed { color: var(--amber); background: var(--amber-t); }
.tag.tip { color: var(--forest); background: var(--forest-t); }
.need { font-size: 8.6pt; color: var(--muted); }
.need b { color: var(--ink); }
img.fig { display: block; width: 100%; }
.cap { font-size: 8pt; color: var(--muted); margin-top: 1.2mm; }
table { border-collapse: collapse; }
table.pts { margin: 1.5mm 0 1mm; font-size: 9pt; }
table.pts th, table.pts td { border: 0.8pt solid #9aa3b5; padding: .8mm 2.4mm; text-align: center; }
table.pts th { background: #eef0f5; font-weight: 700; text-align: left; }
table.pts tr:last-child td { font-weight: 800; }
table.data { width: 100%; font-size: 8.8pt; }
table.data th, table.data td { border: 0.8pt solid #aeb6c6; padding: 1mm 2mm; text-align: left;
                               vertical-align: top; }
table.data th { background: #e9eef5; font-weight: 700; }
.num { display: inline-flex; width: 6mm; height: 6mm; border-radius: 50%; background: var(--forest);
       color: #fff; font-weight: 800; align-items: center; justify-content: center; font-size: 9pt;
       flex: none; }
.steps { list-style: none; padding: 0; margin: 0; }
.steps li { display: flex; gap: 2.5mm; align-items: flex-start; margin-bottom: 2.2mm; }
.spacer { flex: 1; }
"""


def page_cover(I):
    FIVE = "".join(
        f'<div class="sp"><div class="spn">{n}</div><div class="sps">{stones(*cs)}</div>'
        f'<div class="need">{t}</div></div>' for n, cs, t in [
            ("Rabbit", ("green", "yellow", "red"), "3 different colours"),
            ("Turtle", ("blue", "blue", "blue"), "all one colour"),
            ("Salmon", ("green", "blue", "purple"), "all different"),
            ("Owl", ("red", "red"), "same-colour pairs"),
            ("Beaver", ("white", "white", "white"), "3 of a kind + a pair")])
    return f"""
<div class="cover">
  <div class="kick" style="margin-top:6mm">Illustrated rules &amp; table reference</div>
  <h1 style="font-size:46pt;font-weight:900;color:var(--forest);letter-spacing:-.01em;margin:3mm 0 1mm">
    Spirits of the Wild</h1>
  <div style="font-size:15pt;font-weight:600;color:var(--blue)">2 players &nbsp;·&nbsp; about 30 minutes</div>
  <p class="lead" style="max-width:150mm;margin-top:4mm">Gather precious stones, offer them to five
  animal spirits and keep the jealous Coyote off your board. This booklet explains every rule in plain
  words, with pictures, and ends with a score sheet and a one-page quick reference.</p>
  <img class="fig" src="{src(I['cover'])}" style="margin:3mm 0 4mm">
  <div class="five">{FIVE}</div>
  <div class="spacer"></div>
  <div class="box tint-b">
    <h3 style="color:var(--blue)">Inside</h3>
    <div class="grid3" style="font-size:9pt;gap:1mm 4mm">
      <div>2 &nbsp;Goal &amp; components</div><div>6 &nbsp;Animals: Rabbit, Turtle, Salmon</div>
      <div>10 &nbsp;End of game &amp; FAQ</div>
      <div>3 &nbsp;Setup</div><div>7 &nbsp;Animals: Owl, Beaver, example</div>
      <div>11 &nbsp;Score sheet</div>
      <div>4 &nbsp;Your turn</div><div>8 &nbsp;Spirit Stones &amp; the Coyote</div>
      <div>12 &nbsp;Quick reference</div>
      <div>5 &nbsp;The action cards</div><div>9 &nbsp;Spirit Power cards</div><div></div>
    </div>
  </div>
  <div style="height:5mm"></div>
  <p style="font-size:7.6pt;color:var(--muted);margin:0">Unofficial player aid for personal use, written in
  our own words with original illustrations. <i>Spirits of the Wild</i> is a game by Nick Hayes,
  published by Mattel; the name is a trademark of Mattel. <span class="tag ed">Edition</span> This manual
  scores Owl pairs at <b>4 points</b> (German 2019 rules); the English 2017 printing says 3 &mdash; agree
  before you play.</p>
</div>"""


def page_goal(I):
    sw = "".join(
        f'<div class="sw">{st(c, "big")}<div><b>{"Spirit Stone" if c == "clear" else c.title()}</b>'
        f'<br><span class="need">{"clear / opalescent · ×8" if c == "clear" else "×8"}</span></div></div>'
        for c in E.COLORS + [E.CLEAR])
    return f"""
<div class="kick">Overview</div>
<h1 class="pt">The goal of the game</h1>
<p class="lead">Long ago five forest animals became stars, and they have returned as spirits. Each spirit
loves certain gifts. Bring them the right stones and earn their favour &mdash; but the jealous Coyote
blocks any animal he sits on.</p>
<div class="box tint-f" style="font-size:10.2pt">
  <b>Win by having the most points.</b> On each turn you play one action card to collect stones and place
  them on the five animals of your board &mdash; each animal accepts only certain stones and scores for the
  sets you build. The game ends as soon as <b>five clear Spirit Stones</b> have come out of the bag.
</div>
<h2>A game in four sentences</h2>
<ol class="steps">
  <li><span class="num">1</span><div>Play one <b>face-up action card</b>, do what it says, then flip it
  face-down.</div></li>
  <li><span class="num">2</span><div>Put every stone you take on an animal that <b>accepts</b> it; if none
  does, the stone goes back to the bowl.</div></li>
  <li><span class="num">3</span><div>When three of your other cards are face-down you may use a
  <b>Spirit Power</b> and turn all your cards face-up again.</div></li>
  <li><span class="num">4</span><div>A clear <b>Spirit Stone</b> doubles an animal&rsquo;s points but closes
  it &mdash; and the fifth one out of the bag ends the game.</div></li>
</ol>
<h2>Components</h2>
<div class="grid2" style="grid-template-columns: 1fr 1.25fr">
  <table class="data">
    <tr><th>Item</th><th>Qty</th></tr>
    <tr><td>Bowl</td><td>1</td></tr><tr><td>Cloth bag</td><td>1</td></tr>
    <tr><td>Coyote pawn</td><td>1</td></tr><tr><td>Player boards (5 animals each)</td><td>2</td></tr>
    <tr><td>Action cards (6 per player)</td><td>12</td></tr>
    <tr><td>Spirit Power cards: Bear, Wolf, Ram, Eagle, Deer, Bison</td><td>6</td></tr>
    <tr><td>Stones (8 of each of 7 kinds)</td><td>56</td></tr>
  </table>
  <div>
    <div class="swatches">{sw}</div>
    <p class="need" style="margin-top:2mm">Six <b>regular colours</b> plus the clear <b>Spirit Stones</b>.
    A Spirit Stone is <b>not</b> a seventh colour. In this booklet every stone carries its initial
    (G Y B P W R, S = Spirit Stone), so the pictures also work in black and white.</p>
  </div>
</div>
<h2>Words used in this booklet</h2>
<table class="data">
  <tr><th style="width:30mm">Bowl</th><td>The open pool of stones in the middle. &ldquo;Take&rdquo; always
  means take from the bowl, choosing freely.</td></tr>
  <tr><th>Bag</th><td>The hidden supply. &ldquo;Draw&rdquo; or &ldquo;add&rdquo; means pull stones blindly
  from the bag.</td></tr>
  <tr><th>Section</th><td>One animal on your board: its stone spaces plus a <b>×2 bonus space</b> for a
  Spirit Stone.</td></tr>
  <tr><th>Open / closed</th><td>A section is closed once it holds a Spirit Stone; it is blocked while the
  Coyote sits on it. Neither accepts new stones.</td></tr>
  <tr><th>Face-up / face-down</th><td>Face-up action cards are available; face-down cards are used until
  you recover them.</td></tr>
</table>
"""


def page_setup(I):
    return f"""
<div class="kick">Before you play</div>
<h1 class="pt">Setup</h1>
<p class="lead">Takes about two minutes. The numbers match the picture.</p>
<img class="fig" src="{src(I['setup'])}" style="border:0.8pt solid var(--rule);border-radius:3mm;padding:2mm">
<p class="cap">Example table after setup (Ana starts). Ben sits opposite; his board is shown the right way up
for reading.</p>
<div class="grid2" style="margin-top:4mm;gap:4mm 7mm;font-size:10.2pt">
  <ol class="steps">
    <li><span class="num">1</span><div><b>Middle of the table.</b> Place the bowl between the players. Put the
    Coyote pawn to one side &mdash; at the start it blocks nobody.</div></li>
    <li><span class="num">2</span><div><b>Fill the bag.</b> All 56 stones go in the cloth bag. Shake it.</div></li>
    <li><span class="num">3</span><div><b>Seed the bowl.</b> Draw stones into the bowl until it holds
    <b>4 regular stones</b>. Any clear Spirit Stone drawn now goes straight back into the bag and you draw
    again.</div></li>
  </ol>
  <ol class="steps">
    <li><span class="num">4</span><div><b>Player areas.</b> Each player takes a board and lays their
    6 action cards <b>face-up</b> in front of it.</div></li>
    <li><span class="num">5</span><div><b>Spirit Powers.</b> Shuffle the 6 Spirit Power cards into
    <b>two face-up piles of 3</b>. Only the top card of each pile can be used.</div></li>
    <li><span class="num">6</span><div><b>Start player.</b> Choose any way you like. The start player
    turns their <b>Take Two Stones</b> card face-down &mdash; it stays unavailable until they recover
    their cards. This balances the advantage of going first.</div></li>
  </ol>
</div>
<div class="spacer"></div>
<div class="box tint-f" style="margin-bottom:3mm"><span class="tag tip">First game?</span> Read pages 4&ndash;6
together, then start playing and look things up as they come. Keep the quick reference (back page) face-up
next to the bowl, and say the Spirit Stone count out loud whenever a clear stone leaves the bag.</div>
<div class="box tint-a"><b>Check before the first turn:</b> 4 regular stones in the bowl ·
0 Spirit Stones out of the bag · 2 Spirit piles, top cards visible · start player&rsquo;s
Take Two Stones face-down · Coyote off both boards.</div>
"""


def flow_box(n, title, body, cls="tint-f"):
    return (f'<div class="box {cls} flow"><div style="display:flex;gap:2mm;align-items:center;'
            f'margin-bottom:1.2mm"><span class="num">{n}</span><h3 style="margin:0">{title}</h3></div>'
            f'{body}</div>')


def page_turn(I):
    arrow = '<div class="arr">&#10140;</div>'
    return f"""
<div class="kick">How to play</div>
<h1 class="pt">Your turn</h1>
<p class="lead">Players alternate. A turn is always the same three steps.</p>
<div class="flowrow">
  {flow_box(1, "Choose", "Pick <b>one face-up</b> action card. You may only choose a card you can carry out: any stones it tells you to <b>take</b> must already be in the bowl.")}
  {arrow}
  {flow_box(2, "Do it", "Carry out the whole card. Place each stone you take on your board <b>at once</b> (see below).")}
  {arrow}
  {flow_box(3, "Flip it", "Turn the card <b>face-down</b>. It can&rsquo;t be used again until you recover your cards.")}
</div>
<div class="endturn"><b>End of every turn:</b> count the clear Spirit Stones that are out of the bag
(bowl + both boards). <b>Five or more? The game ends now</b> &mdash; go to final scoring (page 10).
Otherwise it&rsquo;s your opponent&rsquo;s turn.</div>

<h2>Getting your cards back</h2>
<div class="grid2" style="grid-template-columns: 1fr 62mm; align-items:start">
  <div>
    <p>Each card works once per cycle, so you will run out. Your sixth card,
    <b>Use Spirit Power &amp; Recover Cards</b>, can be chosen only when <b>at least three of your other five
    cards are face-down</b>. It lets you:</p>
    <ol class="steps">
      <li><span class="num">a</span><div>use one of the two face-up <b>Spirit Power</b> cards (page 9),</div></li>
      <li><span class="num">b</span><div>slide that Spirit card to the <b>bottom of its pile</b>,</div></li>
      <li><span class="num">c</span><div>turn <b>all six</b> of your action cards face-up again &mdash;
      this one included.</div></li>
    </ol>
    <p class="need">Recovering is optional: you may keep playing other face-up cards instead.</p>
  </div>
  <div><img class="fig" src="{src(I['cycle'])}">
  <p class="cap">Three cards are face-down, so <b>Spirit Power &amp; Recover</b> (outlined) may be
  played. Both <i>Take One Stone</i> backs are down, which also shows the complete Coyote
  (page 8).</p></div>
</div>

<h2>Placing stones</h2>
<div class="grid2">
  <ul>
    <li>A stone may go only on an animal whose <b>requirement</b> it meets (pages 6&ndash;7).</li>
    <li>If a stone you take fits <b>nowhere</b> on your board, put it <b>back in the bowl</b>. That
    is still a legal play.</li>
    <li>Placed stones stay put. (Only the Deer power moves one back to the bowl.)</li>
  </ul>
  <ul>
    <li>A clear Spirit Stone goes only in an animal&rsquo;s <b>×2 bonus space</b> (page 8).</li>
    <li>No stone of any kind may be added to a <b>closed</b> animal (holds a Spirit Stone) or a
    <b>blocked</b> one (the Coyote sits on it).</li>
    <li>Cards that only <b>add</b> stones to the bowl, and the optional Coyote move, never stop you from
    playing a card.</li>
  </ul>
</div>
<div class="spacer"></div>
<div class="box tint-a"><h3>Example turn</h3>
Ana&rsquo;s Turtle holds two {st('blue')} blue stones. She plays <b>Add Two Stones &amp; Take One</b>: she
draws a {st('red')} red and a {st('clear')} Spirit Stone from the bag into the bowl (now 1 Spirit Stone is
out). She takes a {st('blue')} blue stone that was already in the bowl and adds it to her Turtle (3 blue =
6 points), then flips the card face-down. At the end of her turn only one Spirit Stone is out, so Ben plays
next.</div>
"""


def card_box(I, key, title, count, body, need=None, extra=""):
    cnt = f' <span class="tag tip">×{count} per player</span>' if count > 1 else ""
    nd = f'<p class="need"><b>Playable when:</b> {need}</p>' if need else ""
    return f"""<div class="box card">
  <img class="cardimg" src="{src(I['faces'][key])}" alt="">
  <div><h3>{title}{cnt}</h3>{body}{nd}{extra}</div></div>"""


def page_cards(I):
    return f"""
<div class="kick">Reference</div>
<h1 class="pt">The action cards</h1>
<p class="lead">Each player has the same six cards (two of them identical). Play one per turn, then flip it
face-down.</p>
<div class="cards">
{card_box(I, E.TAKE1A, "Take One Stone", 2,
  "<p>Take <b>1 stone</b> of your choice from the bowl and place it on your board.</p>",
  "the bowl holds at least 1 stone.",
  '<p class="need"><b>Card back:</b> half a Coyote (see the Coyote box on this page).</p>')}
{card_box(I, E.TAKE2, "Take Two Stones", 1,
  "<p>Take <b>2 stones</b> of your choice from the bowl and place them on your board.</p>",
  "the bowl holds at least 2 stones.",
  '<p class="need">The start player begins the game with this card face-down.</p>')}
{card_box(I, E.ADD2, "Add Two Stones &amp; Take One", 1,
  "<p><b>Draw 2 stones</b> from the bag (without looking) into the bowl. Then <b>take 1 stone</b> of "
  "your choice from the bowl and place it.</p>",
  None, '<p class="need">You may take one of the new stones or one that was already there.</p>')}
{card_box(I, E.ADD3, "Add Three Stones &amp; Move Coyote", 1,
  "<p><b>Draw 3 stones</b> from the bag into the bowl. Then you <b>may</b> put the Coyote on any one "
  "animal of your <b>opponent&rsquo;s</b> board.</p>",
  None, '<p class="need">You take <b>no</b> stone with this card. Think about what you leave in the bowl '
  'for your opponent.</p>')}
{card_box(I, E.SPIRIT, "Use Spirit Power &amp; Recover Cards", 1,
  "<ol><li>Choose the top card of either Spirit Power pile.</li>"
  "<li>Do its effect, step by step in the order written (page 9).</li>"
  "<li>Put that card at the bottom of its own pile.</li>"
  "<li>Turn all six of your action cards face-up.</li></ol>",
  "at least <b>3 of your other 5</b> cards are face-down.")}
<div class="box tint-c card">
  <img class="cardimg" src="{src(I['coyote'])}" alt="" style="width:16mm;height:auto;padding:1mm">
  <div><h3 style="color:var(--coyote)">The two Coyote halves</h3>
  <p>The back of each <b>Take One Stone</b> card shows half of the Coyote. When the second of them is
  turned face-down the picture is complete: after taking your stone you <b>may move the Coyote</b> to any
  animal on your opponent&rsquo;s board.</p>
  <p class="need">This can happen once per cycle of your cards, because recovering flips both back
  face-up.</p></div>
</div>
</div>
<div style="height:5mm"></div>
<div class="box tint-b" style="display:flex;gap:4mm;align-items:center">
  <img src="{src(I['backs'])}" style="width:52mm">
  <div><b>Both Take One Stone cards face-down = a whole Coyote.</b> Together with
  <i>Add Three Stones &amp; Move Coyote</i>, that gives you two ways per cycle to send the Coyote to your
  opponent. Full Coyote rules: page 8.</div>
</div>
"""


def animal_panel(I, a, title, rule, bullets, pts_html, caption, cls, tip=None):
    img, _ = I["sections"][a]
    lis = "".join(f"<li>{b}</li>" for b in bullets)
    if tip:
        pts_html += f'<p class="need" style="margin-top:1.5mm"><span class="tag tip">Tip</span> {tip}</p>'
    return f"""<div class="box {cls} animal">
  <div class="aimg"><img class="fig" src="{src(img)}"><p class="cap">{caption}</p></div>
  <div><h3 style="font-size:14pt">{title}</h3>
  <div class="rule">{rule}</div><ul>{lis}</ul>{pts_html}</div></div>"""


def page_animals1(I):
    return f"""
<div class="kick">Your board · 1 of 2</div>
<h1 class="pt">The five animals</h1>
<p class="lead">Every animal accepts only certain stones and scores for what it holds at the end. Any
animal may also take one Spirit Stone in its ×2 space (page 8).</p>
{animal_panel(I, "rabbit", "Rabbit", "Three stones, all of different colours",
  ["Scores <b>6 points</b>, but only when all 3 stones are in place.",
   "An unfinished Rabbit scores <b>nothing</b>."],
  table_pts([3], [6]),
  f"{stones('green', 'yellow', 'red')} green, yellow, red: complete = <b>6</b>.", "tint-f",
  "An easy 6 points &mdash; but it counts only once all three stones are there. Don&rsquo;t leave it "
  "unfinished when the Spirit Stones run low.")}
{animal_panel(I, "turtle", "Turtle", "Every stone the same colour",
  ["Up to 5 stones, all of <b>one</b> colour.",
   "The 5th stone is the big jump: 9 &rarr; 14."],
  table_pts([1, 2, 3, 4, 5], [1, 3, 6, 9, 14]),
  f"Four {st('blue')} blue = <b>9</b>. A fifth blue would make it 14.", "tint-b",
  "Choose a colour that is easy to get. A full Turtle with a Spirit Stone is worth 28.")}
{animal_panel(I, "salmon", "Salmon", "Every stone a different colour",
  ["Up to 6 stones, <b>one of each</b> regular colour.",
   "Points grow fastest at the end: 9 &rarr; 13."],
  table_pts([1, 2, 3, 4, 5, 6], [1, 2, 4, 6, 9, 13]),
  f"Five different ({stones('green', 'yellow', 'blue', 'purple', 'red')}) = <b>9</b>. "
  f"Adding {st('white')} white would make 13.", "tint-a",
  "Almost any stone fits early on, which makes the Salmon a good home for leftovers. Full with a "
  "Spirit Stone: 26.")}
"""


def page_animals2(I):
    rows = [("Rabbit", "green, blue, red: complete", "6", "", "6"),
            ("Turtle", "4 blue + Spirit Stone", "9", "×2", "18"),
            ("Salmon", "yellow, purple, red", "4", "", "4"),
            ("Owl", "2 pairs (white, green) + 1 single red", "8", "", "8"),
            ("Beaver", "three yellow; pair not started", "5", "", "5")]
    tr = "".join(f"<tr><td><b>{a}</b></td><td>{d}</td><td>{p}</td><td>{x}</td><td><b>{t}</b></td></tr>"
                 for a, d, p, x, t in rows)
    total = E.total_score(EXAMPLE)
    return f"""
<div class="kick">Your board · 2 of 2</div>
<h1 class="pt" style="margin-bottom:3mm">The five animals (continued)</h1>
{animal_panel(I, "owl", "Owl", "Pairs of the same colour",
  ["Each <b>completed pair</b> scores <b>4 points</b>. A lone half-pair scores nothing.",
   "Pairs may be different colours from each other, and you may start a new pair before finishing "
   "another.",
   '<span class="tag ed">Edition</span> English 2017 rules: 3 points per pair.'],
  "",
  f"{stones('red', 'red')} + {stones('white', 'white')} + {st('green')} = 2 pairs = <b>8</b>. "
  "Use the number of Owl spaces printed on your board.", "tint-p")}
{animal_panel(I, "beaver", "Beaver", "Three of a kind + a pair",
  ["<b>Three-of-a-kind</b> (3 of one colour) = <b>5</b>.",
   "<b>Pair</b> (2 of one colour) = <b>2</b>.",
   "Both complete: <b>+7 bonus</b>, so <b>14</b> in total. Work on either set first; only completed sets "
   "score."],
  '<table class="pts"><tr><th>Sets</th><td>3 same</td><td>2 same</td><td>both</td></tr>'
  '<tr><th>Points</th><td>5</td><td>2</td><td>14</td></tr></table>',
  f"Three {st('purple')} purple + two {st('yellow')} yellow = 5 + 2 + 7 = <b>14</b>.", "tint-c")}
<h2>Worked scoring example</h2>
<img class="fig" src="{src(I['example'])}">
<p class="cap">Mia&rsquo;s board at the end of the game. The number at the bottom right of each animal is
its final score.</p>
<div class="grid2" style="grid-template-columns: 1.6fr 1fr;margin-top:2mm;align-items:start">
  <table class="data">
    <tr><th>Animal</th><th>What&rsquo;s there</th><th>Pts</th><th>Spirit</th><th>Score</th></tr>
    {tr}
    <tr><th colspan="4" style="text-align:right">Total</th><th>{total}</th></tr>
  </table>
  <div class="box tint-a"><b>Notice:</b> the single red stone on the Owl and the missing Beaver pair
  score nothing. The Spirit Stone on the 4-stone Turtle doubled 9 to 18 &mdash; on a full Turtle it would
  have been 28.</div>
</div>
"""


def page_spirit_coyote(I):
    clk = "".join(st("clear", "big") for _ in range(5))
    return f"""
<div class="kick">Special pieces</div>
<h1 class="pt">Spirit Stones</h1>
<div class="grid2" style="grid-template-columns: 1fr 64mm; align-items:start">
  <div>
    <p>The 8 clear (opalescent) stones {st('clear')} are not a colour. They follow their own rules:</p>
    <ul>
      <li>Only in an animal&rsquo;s <b>×2 bonus space</b>, never in a normal space.</li>
      <li>At the end, that animal&rsquo;s points are <b>doubled</b>.</li>
      <li>It <b>closes</b> the animal: no more stones of any kind may be added there.</li>
      <li>Never counts toward a colour requirement (Rabbit, Salmon&hellip;).</li>
      <li>Taken but no open bonus space (all closed or blocked)? It goes <b>back to the bowl</b>.</li>
    </ul>
    <p class="need"><span class="tag tip">Tip</span> Place it when the animal is full or nearly full &mdash;
    unless the game is about to end. Double zero is still zero.</p>
  </div>
  <div><img class="fig" src="{src(I['sections']['spirit'][0])}">
  <p class="cap">Five {st('red')} red on the Turtle (14) with a Spirit Stone = <b>28</b>. The Turtle is now
  closed.</p></div>
</div>
<div class="box tint-b clock">
  <div class="clk">{clk}</div>
  <div><b>The game clock.</b> Spirit Stones out of the bag &mdash; in the bowl <i>and</i> on both boards
  &mdash; count towards the end. Check at the <b>end of every turn</b>: with <b>five or more out</b>, the game
  ends immediately. If the Bison power puts one back in the bag before the turn ends, the count drops and
  play goes on.</div>
</div>

<h1 class="pt" style="margin-top:6mm;color:var(--coyote)">The Coyote</h1>
<div class="grid2" style="grid-template-columns: 1fr 64mm; align-items:start">
  <div>
    <p>The jealous trickster. While the Coyote sits on one of your animals you <b>can&rsquo;t add any
    stone</b> there &mdash; not even a Spirit Stone. Stones already there stay and still score. The block
    ends when the Coyote moves on.</p>
    <h3 style="margin-top:2mm">Two ways to move him onto your opponent&rsquo;s board</h3>
    <ol class="steps">
      <li><span class="num" style="background:var(--coyote)">1</span><div><b>Add Three Stones &amp; Move
      Coyote</b>: after adding the 3 stones you <i>may</i> put him on any of your opponent&rsquo;s
      animals.</div></li>
      <li><span class="num" style="background:var(--coyote)">2</span><div><b>Both Take One Stone cards
      face-down</b>: their backs form a whole Coyote, and you may move him the same way.</div></li>
    </ol>
  </div>
  <div><img class="fig" src="{src(I['sections']['blocked'][0])}">
  <p class="cap">Coyote on the Salmon: its 3 stones still score 4, but nothing more can be added.</p></div>
</div>
<div class="grid2" style="margin-top:1mm">
  <ul>
    <li>There is one Coyote: it is on at most one animal. Moving it frees the animal it left.</li>
    <li>Always onto your <b>opponent&rsquo;s</b> board, never your own.</li>
  </ul>
  <ul>
    <li>A closed animal (with a Spirit Stone) may be chosen, but blocking it achieves nothing.</li>
    <li><b>Ties:</b> the player with the Coyote on their board wins (page 10).</li>
  </ul>
</div>
"""


SPIRITS = [
    ("Bear", "Shake up the bowl", ["Count the stones in the bowl.", "Put them all back in the bag.",
                                   "Draw the <b>same number</b> from the bag into the bowl.",
                                   "Take <b>1 stone</b> from the bowl."]),
    ("Wolf", "Big refill", ["Draw <b>4 stones</b> from the bag into the bowl.",
                            "Take <b>1 stone</b> from the bowl."]),
    ("Ram", "Straight from the bag", ["Draw <b>2 stones</b> from the bag.",
                                      "Place both <b>directly on your board</b> &mdash; you must if you "
                                      "legally can (a Spirit Stone too).",
                                      "Any you can&rsquo;t place go into the bowl."]),
    ("Eagle", "Extra turn", ["Take <b>1 stone</b> from the bowl.",
                             "Recover your action cards as usual.",
                             "Take <b>another turn</b> at once, with all six cards face-up."]),
    ("Deer", "Swap", ["Move <b>1 stone</b> from your board back to the bowl.",
                      "Take <b>2 stones</b> from the bowl."]),
    ("Bison", "Take one, send one back", ["Draw <b>3 stones</b> from the bag into the bowl.",
                                          "Take <b>1 stone</b> from the bowl.",
                                          "Return <b>another stone</b> from the bowl to the bag (any "
                                          "stone, new or old &mdash; even a Spirit Stone)."]),
]


def page_spirits(I):
    cards = ""
    for name, tag, steps in SPIRITS:
        li = "".join(f'<li><span class="num" style="background:var(--blue)">{i}</span><div>{s}</div></li>'
                     for i, s in enumerate(steps, 1))
        cards += (f'<div class="box tint-b spirit"><div class="sname">{name}</div>'
                  f'<div class="stag">{tag}</div><ol class="steps">{li}</ol></div>')
    return f"""
<div class="kick">Reference</div>
<h1 class="pt">Spirit Power cards</h1>
<p class="lead">Played through <b>Use Spirit Power &amp; Recover Cards</b>. Pick the top card of
either pile and resolve it <b>in the order written</b>. Every stone you take is placed on your board as
usual (or returned to the bowl if it fits nowhere).</p>
<div class="grid2 spirits">{cards}</div>
<div class="box tint-f" style="margin-top:4mm"><b>After every Spirit Power:</b> slide the used card to the
<b>bottom of its own pile</b> (a new top card appears), then turn <b>all six</b> of your action cards
face-up.</div>
<h2>Good to know</h2>
<div class="grid2">
  <ul>
    <li><b>Eagle</b> is the only way to play two turns in a row &mdash; and you start the extra turn with
    all cards ready.</li>
    <li><b>Deer</b> can break a set (e.g. an Owl pair) if you remove a stone from it.</li>
  </ul>
  <ul>
    <li><b>Bison</b> can pull a Spirit Stone back into the bag: handy to delay the end when you&rsquo;re
    behind, or to deny one to your opponent.</li>
    <li>Look at both top cards early and time your recovery for the one you want.</li>
  </ul>
</div>
"""


FAQ = [
    ("Can I play a card if part of it can&rsquo;t be done?",
     "Stones you must <b>take</b> have to be in the bowl. Adding stones from the bag and the optional "
     "Coyote move never block a card. Taking a stone you can&rsquo;t place is legal: it goes back to the "
     "bowl."),
    ("How many spaces does each animal have?",
     "The scoring implies Rabbit 3, Turtle 5, Salmon 6, Beaver 3 + 2. For the Owl use the spaces printed "
     "on your board. Always follow your physical board."),
    ("Can a Spirit Stone go on an empty animal?",
     "Nothing forbids it, but it closes the animal and double zero is zero &mdash; almost never worth it."),
    ("Does the game end the moment the 5th Spirit Stone appears?",
     "No: you finish the turn first, then check. That matters for the Bison, which can return one."),
    ("Eagle: do I recover before the extra turn?",
     "Yes. Take your stone, turn all six cards face-up, then play your extra turn."),
    ("Ram: must I place a drawn Spirit Stone?",
     "Yes, if you have an open bonus space. Anything you can&rsquo;t place goes to the bowl."),
    ("When exactly do the Coyote halves trigger?",
     "When the second Take One Stone card is flipped face-down, after taking its stone. Once per cycle."),
    ("Deer: can I remove a Spirit Stone, or a stone from a blocked animal?",
     'The rules don&rsquo;t restrict which stone. <span class="tag house">House rule</span> Any of your stones '
     "may be removed, but you still can&rsquo;t add stones to a closed or blocked animal. Agree before play."),
    ("What if the bag runs out?",
     '<span class="tag house">House rule</span> Draw what is left; with an empty bag a draw step does '
     "nothing. Carry out the rest of the card as far as possible."),
    ("Tie, and the Coyote was never used?",
     '<span class="tag house">House rule</span> Share the victory.'),
]


def page_end(I):
    faq = "".join(f'<div class="qa"><div class="q">{q}</div><div>{a}</div></div>' for q, a in FAQ)
    return f"""
<div class="kick">Finishing</div>
<h1 class="pt">End of the game &amp; scoring</h1>
<div class="grid2" style="align-items:stretch">
  <div class="box tint-b"><h3>When does it end?</h3>
  At the <b>end of any turn</b> in which <b>5 Spirit Stones are out of the bag</b> (bowl + both boards
  together), the game ends immediately. No further turns.</div>
  <div class="box tint-f"><h3>Who wins?</h3>
  The higher total wins. <b>Tie:</b> the player who has the <b>Coyote on their board</b> wins &mdash; the
  spirits take pity on the one he bothered.</div>
</div>
<h2>Final scoring, step by step</h2>
<div class="grid2" style="grid-template-columns: 1fr 1.15fr; align-items:start">
  <ol class="steps">
    <li><span class="num">1</span><div>Score each of your five animals (table right). Unfinished sets score
    nothing.</div></li>
    <li><span class="num">2</span><div><b>Double</b> each animal with a Spirit Stone in its bonus
    space.</div></li>
    <li><span class="num">3</span><div>Add the five results. The score sheet on page 11 helps.</div></li>
  </ol>
  <table class="data">
    <tr><th>Animal</th><th>Points</th></tr>
    <tr><td>Rabbit</td><td>6 if complete (3 different)</td></tr>
    <tr><td>Turtle</td><td>1 · 3 · 6 · 9 · 14 for 1&ndash;5 same colour</td></tr>
    <tr><td>Salmon</td><td>1 · 2 · 4 · 6 · 9 · 13 for 1&ndash;6 different</td></tr>
    <tr><td>Owl</td><td>4 per complete pair <span class="need">(3 in English 2017 ed.)</span></td></tr>
    <tr><td>Beaver</td><td>3 same = 5 · pair = 2 · both = 14</td></tr>
  </table>
</div>
<h2>FAQ &amp; clarifications</h2>
<p class="need" style="margin-bottom:2.5mm">Answers follow the printed rules. Where the rules are silent, a
suggestion is marked <span class="tag house">House rule</span> &mdash; agree on it before you start.</p>
<div class="faq">{faq}</div>
<div class="spacer"></div>
<div class="box tint-f"><h3>Strategy tips <span class="tag tip">Not rules</span></h3>
<div class="grid2" style="gap:0 6mm"><ul>
<li>Count the Spirit Stones out of the bag. At three or four, every draw could end the game &mdash; make sure
your board scores <i>now</i>.</li>
<li>Rabbit, Owl pairs and Beaver sets score nothing unfinished. Avoid many half-sets late in the game.</li>
</ul><ul>
<li>Send the Coyote to your opponent&rsquo;s best <i>open</i> animal, usually a Turtle or Salmon just
before its big jump.</li>
<li>Stones you add to the bowl help your opponent too &mdash; check what colours they need first.</li>
</ul></div></div>
"""


def page_scoresheet(I):
    rows = ["Rabbit", "Turtle", "Salmon", "Owl", "Beaver"]

    def block(n):
        body = "".join(
            f'<tr><th>{a}</th><td></td><td class="x"><span class="cb"></span></td><td></td>'
            f'<td class="x"><span class="cb"></span></td></tr>' for a in rows)
        return f"""<table class="sheet">
<tr class="g"><th>Game {n}</th><th colspan="2">Player 1: <span class="line"></span></th>
<th colspan="2">Player 2: <span class="line"></span></th></tr>
<tr class="sub"><th></th><th>points</th><th>×2</th><th>points</th><th>×2</th></tr>
{body}
<tr class="tot"><th>Total</th><td colspan="2"></td><td colspan="2"></td></tr>
<tr class="tie"><th>Coyote on board?</th><td colspan="2"><span class="cb"></span> yes (wins a tie)</td>
<td colspan="2"><span class="cb"></span> yes (wins a tie)</td></tr>
</table>"""
    return f"""
<div class="kick">Photocopy me</div>
<h1 class="pt">Score sheet</h1>
<p class="need" style="margin-bottom:3mm">Write each animal&rsquo;s points <b>before</b> doubling and tick ×2
if it holds a Spirit Stone; doubled animals count twice in the total. Rabbit 6 · Turtle 1/3/6/9/14 ·
Salmon 1/2/4/6/9/13 · Owl 4 per pair · Beaver 5 + 2 (+7 if both).</p>
<div class="grid2 sheets">{"".join(block(i) for i in range(1, 7))}</div>
"""


def page_quickref(I):
    return f"""
<div class="quick">
<div class="kick">Keep this side up</div>
<h1 class="pt" style="font-size:19pt">Quick reference</h1>
<div class="grid2 qr">
  <div class="box tint-f"><h3>Your turn</h3>
  <ol class="steps">
    <li><span class="num">1</span><div>Choose one <b>face-up</b> card (stones it takes must be in the
    bowl).</div></li>
    <li><span class="num">2</span><div>Do it. Place stones at once; unplaceable &rarr; bowl.</div></li>
    <li><span class="num">3</span><div>Flip it <b>face-down</b>.</div></li>
    <li><span class="num">!</span><div>End of turn: <b>5 Spirit Stones out</b> of the bag? Game over.</div></li>
  </ol></div>
  <div class="box tint-a"><h3>Setup</h3>
  Bowl: 4 regular stones (redraw clear ones) · 6 cards face-up each · Spirit cards in 2 face-up piles
  of 3 · start player flips <b>Take Two Stones</b> face-down · Coyote aside.</div>
</div>
<h2>Action cards</h2>
<table class="data">
  <tr><th style="width:52mm">Card</th><th>Effect</th></tr>
  <tr><td><b>Take One Stone</b> (×2)</td><td>Take 1 from the bowl. Both face-down = whole Coyote: move it to
  an opponent&rsquo;s animal.</td></tr>
  <tr><td><b>Take Two Stones</b></td><td>Take 2 from the bowl (needs 2 there).</td></tr>
  <tr><td><b>Add Two &amp; Take One</b></td><td>Bag &rarr; bowl 2, then take 1.</td></tr>
  <tr><td><b>Add Three &amp; Move Coyote</b></td><td>Bag &rarr; bowl 3, then <i>may</i> put the Coyote on an
  opponent&rsquo;s animal. No stone taken.</td></tr>
  <tr><td><b>Spirit Power &amp; Recover</b></td><td>Needs &ge; 3 other cards face-down. Use a top Spirit
  card, put it under its pile, flip <b>all 6</b> cards face-up.</td></tr>
</table>
<h2>Spirit Powers</h2>
<table class="data">
  <tr><td style="width:17mm"><b>Bear</b></td><td>Bowl &rarr; bag, redraw the same number, take 1.</td>
      <td style="width:17mm"><b>Eagle</b></td><td>Take 1; after recovering, take another turn.</td></tr>
  <tr><td><b>Wolf</b></td><td>Bag &rarr; bowl 4, take 1.</td>
      <td><b>Deer</b></td><td>1 of your stones &rarr; bowl, then take 2.</td></tr>
  <tr><td><b>Ram</b></td><td>2 from bag straight to your board (must if possible; rest &rarr; bowl).</td>
      <td><b>Bison</b></td><td>Bag &rarr; bowl 3, take 1, return 1 bowl stone to the bag.</td></tr>
</table>
<h2>Animals</h2>
<table class="data">
  <tr><th style="width:20mm">Animal</th><th>Accepts</th><th>Points</th></tr>
  <tr><td><b>Rabbit</b></td><td>3 different colours</td><td>6 (complete only)</td></tr>
  <tr><td><b>Turtle</b></td><td>all one colour</td><td>1 · 3 · 6 · 9 · 14 &nbsp;(1&ndash;5 stones)</td></tr>
  <tr><td><b>Salmon</b></td><td>all different colours</td><td>1 · 2 · 4 · 6 · 9 · 13 &nbsp;(1&ndash;6 stones)</td></tr>
  <tr><td><b>Owl</b></td><td>same-colour pairs</td><td>4 per complete pair <span class="need">(3 in English 2017 ed.)</span></td></tr>
  <tr><td><b>Beaver</b></td><td>3 of a kind + a pair</td><td>5 + 2, +7 bonus if both = 14</td></tr>
</table>
<div class="grid2 qr" style="margin-top:3.5mm">
  <div class="box tint-b"><h3>{st('clear')} Spirit Stone</h3>Only in a <b>×2 bonus space</b> · doubles that
  animal · <b>closes</b> it · not a colour · no open space &rarr; bowl.</div>
  <div class="box tint-c"><h3><img class="st" src="{src(I['coyote'])}" alt=""> Coyote</h3>No stones (not even
  Spirit Stones) may be added to the animal he sits on. Always moved onto the opponent&rsquo;s board.</div>
</div>
<div class="box tint-p" style="margin-top:3.5mm"><b>End &amp; winner:</b> end of a turn with 5 Spirit Stones
out of the bag (Bison returning one in time keeps play going) &rarr; score, double animals with a Spirit
Stone, highest total wins. <b>Tie:</b> the player with the Coyote on their board wins.</div>
</div>
"""


CSS += r"""
.cover { display: flex; flex-direction: column; height: 100%; }
.swatches { display: grid; grid-template-columns: 1fr 1fr; gap: 1.6mm 3mm; font-size: 8.8pt; }
.sw { display: flex; gap: 2mm; align-items: center; line-height: 1.2; }
img.big { width: 8.5mm; height: 8.5mm; }
.flowrow { display: flex; align-items: stretch; gap: 1.5mm; }
.flowrow .flow { flex: 1; }
.arr { display: flex; align-items: center; font-size: 18pt; color: var(--forest); }
.endturn { margin-top: 3mm; border: 1.2pt dashed var(--forest); border-radius: 3mm; padding: 2.5mm 3.5mm; }
.cards { display: grid; grid-template-columns: 1fr 1fr; gap: 3.5mm; }
.card { display: flex; gap: 3mm; align-items: flex-start; }
.cardimg { width: 21mm; flex: none; }
.card ol { padding-left: 4.5mm; margin-bottom: 1.5mm; }
.animal { display: grid; grid-template-columns: 74mm 1fr; gap: 5mm; margin-bottom: 4.5mm; align-items: start; }
.animal ul li { font-size: 9.8pt; }
.five { display: grid; grid-template-columns: repeat(5, 1fr); gap: 2.5mm; }
.sp { border: 0.8pt solid var(--rule); border-radius: 2.5mm; padding: 2mm; text-align: center; background: #fbfaf6; }
.spn { font-weight: 800; color: var(--forest); font-size: 10.5pt; }
.sps { margin: 1mm 0; }
.sps .st { width: 5.5mm; height: 5.5mm; }
.rule { font-weight: 700; color: var(--blue); margin-bottom: 1.5mm; font-size: 10pt; }
.clock { display: flex; gap: 4mm; align-items: center; margin-top: 2mm; }
.clk { display: flex; gap: .5mm; flex: none; }
.spirit { padding: 3mm 3.5mm 1.5mm; }
.sname { font-family: "Inter Display", sans-serif; font-weight: 900; font-size: 15pt; color: var(--blue);
         letter-spacing: .04em; text-transform: uppercase; line-height: 1; }
.stag { font-size: 8.4pt; color: var(--muted); font-weight: 600; margin: .8mm 0 2mm; }
.spirit .steps li { margin-bottom: 1.4mm; }
.spirit .num { width: 5mm; height: 5mm; font-size: 8pt; }
.faq { column-count: 2; column-gap: 6mm; font-size: 8.9pt; }
.qa { break-inside: avoid; margin-bottom: 2.6mm; }
.q { font-weight: 800; color: var(--blue); }
table.sheet { width: 100%; font-size: 9pt; margin-bottom: 4.5mm; }
table.sheet th, table.sheet td { border: 0.9pt solid #6f788c; padding: 0 2mm; height: 7.6mm; }
table.sheet th { text-align: left; background: #f1f3f7; font-weight: 700; }
table.sheet tr.g th { background: var(--forest-t); height: 9.5mm; font-size: 8.6pt; }
table.sheet tr.g th:first-child { color: var(--forest); font-size: 10.5pt; }
table.sheet tr.sub th { height: 5.5mm; font-size: 7.4pt; color: var(--muted); font-weight: 600;
                        text-align: center; }
table.sheet td.x { width: 9mm; text-align: center; }
table.sheet tr.tot th, table.sheet tr.tot td { height: 9mm; border-top: 2pt solid #1d2433; }
table.sheet tr.tie td, table.sheet tr.tie th { font-size: 7.2pt; height: 7mm; }
.cb { display: inline-block; width: 3.6mm; height: 3.6mm; border: 0.9pt solid #1d2433; border-radius: .6mm;
      vertical-align: middle; }
.line { display: inline-block; width: 19mm; border-bottom: 0.8pt solid #6f788c; height: 3mm; }
.sheets { gap: 0 5mm; }
.qr .box { font-size: 9pt; }
.quick h2 { margin: 3mm 0 1.5mm; }
.quick table.data td, .quick table.data th { padding: .8mm 2mm; }
.qr .steps li { margin-bottom: 1.2mm; }
"""

PAGES = [page_cover, page_goal, page_setup, page_turn, page_cards, page_animals1, page_animals2,
         page_spirit_coyote, page_spirits, page_end, page_scoresheet, page_quickref]


def build_html(I):
    out = []
    for n, fn in enumerate(PAGES, 1):
        side = "odd" if n % 2 else "even"
        foot = "" if n == 1 else (f'<footer><span class="pn">{n}</span>'
                                  f'<span>Spirits of the Wild · Rules manual</span></footer>')
        out.append(f'<section class="page {side}" id="p{n}"><div class="content">{fn(I)}</div>'
                   f'{foot}</section>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<title>Spirits of the Wild · Rules manual</title>'
            f'<style>{CSS}</style></head><body>{"".join(out)}</body></html>')


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
    I = build_images()
    with tempfile.TemporaryDirectory() as tmp:
        hp = Path(tmp) / "manual-color.html"
        hp.write_text(build_html(I), encoding="utf-8")
        if "--html" in sys.argv:
            (ASSETS / "_preview.html").write_text(hp.read_text(), encoding="utf-8")
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


if __name__ == "__main__":
    main()
