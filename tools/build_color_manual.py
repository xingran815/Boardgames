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
    W, H = 2030, 1130
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
    bx, bw = player(0, 830, "Ana's board  (start player)")
    my = 360
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
    badge(d, bx + bw - 30, 830 + 30, 4)
    badge(d, bx + bw - 30, 16 + 30, 4)
    badge(d, px - 30, my + 60, 5)
    x0, y0, x1, y1 = R.card_rect(20, 850, 2)
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


