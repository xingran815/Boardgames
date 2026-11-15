"""Pillow renderer for the Azul explainer videos.

Everything is laid out in a 1920x1080 logical space but drawn at S x that
resolution (SDraw scales every call), so the video can zoom into any region and
stay sharp. The look follows docs/azul/STYLE.md: a warm parchment table, cream
panels in deep azulejo-blue frames with ochre-gold lines, dark-red headings and
original geometric tile motifs. No publisher artwork, logo or board art.

The Azul modules load each other under `azul_*` names (see _load) so they never
clash with the Spirits of the Wild `engine` / `render` / `anim` modules.
"""
from __future__ import annotations

import importlib.util
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent


def _load(name):
    """Import tools/azul/<name>.py as module 'azul_<name>' (shared, cached)."""
    full = f"azul_{name}"
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(full, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


E = _load("engine")

W, H = 1920, 1080
S = 2  # supersampling factor

# ---------------------------------------------------------------- palette
# docs/azul/STYLE.md: a light, warm table like the game's own board and rulebook.
BG = (0xEF, 0xE4, 0xCF)          # parchment table
PAPER = (0xFA, 0xF5, 0xEA)       # cream panels and cards
PANEL = PAPER                    # (alias) default base for faint wall spaces
SAND = (0xEA, 0xDA, 0xBE)        # stone-beige slots and trays
INK = (0x1B, 0x2A, 0x4E)         # deep blue-black text
MUTED = (0x68, 0x54, 0x3C)       # warm brown labels
NAVY = (0x1E, 0x3A, 0x72)        # deep azulejo-blue frames
COBALT = (0x2C, 0x5A, 0xA8)      # cobalt tile blue
SKY = (0x9C, 0xC0, 0xE3)         # light azulejo blue
GOLD = (0xC0, 0x8A, 0x2E)        # ochre-gold accent lines
GOLD_LIGHT = (0xF4, 0xCD, 0x78)  # gold text on deep blue
RED = (0x9E, 0x2A, 0x22)         # dark red headings
ACCENT = COBALT
HL = (0xB3, 0x2A, 0x1E)          # highlight frames (rulebook red)
BAD = (0xB0, 0x1E, 0x24)         # crosses
MINUS = RED                      # floor-line penalties
SLOT = (0xBE, 0x9C, 0x68)        # empty-slot edge (gold-tan)
SHADOW = (0xBF, 0xA8, 0x84)      # soft tile shadow on parchment
WALL_BG = (0xE6, 0xD6, 0xB8)     # tray under the wall

# tiles (docs/azul/STYLE.md)
FILL = {"blue": (0x2F, 0x62, 0xAC), "yellow": (0xE9, 0xA2, 0x38), "red": (0xD2, 0x49, 0x2F),
        "black": (0x24, 0x27, 0x2F), "white": (0xF4, 0xEF, 0xE2)}
EDGE = {"blue": (0x1A, 0x3A, 0x6E), "yellow": (0x9C, 0x62, 0x14), "red": (0x82, 0x28, 0x19),
        "black": (0x0C, 0x0E, 0x12), "white": (0x8F, 0xA8, 0xC4)}
MARK_INK = {"blue": (0xB4, 0xD4, 0xF2), "yellow": (0xC2, 0x3E, 0x1E), "red": (0xF8, 0xDC, 0xC4),
            "black": (0x6C, 0xAC, 0xCC), "white": (0x5E, 0x9A, 0xCE)}
LETTER_INK = {"blue": (255, 255, 255), "yellow": (0x5A, 0x2C, 0x00), "red": (255, 255, 255),
              "black": (0xE8, 0xEE, 0xF4), "white": (0x1E, 0x3A, 0x72)}
MARKER_FILL = (0xFB, 0xF8, 0xEF)
FACTORY = (0xF2, 0xE6, 0xD0)     # cream ring of a factory display
FACTORY_RIM = (0xB0, 0x5E, 0x34)  # terracotta rim
GREY_SPACE = (0xC4, 0xBE, 0xB4)

# ------------------------------------------------------------------ fonts
FONT_DIR = HERE / "fonts"        # OFL fonts, see fonts/OFL.txt
_FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"


def font(size, weight="Regular"):
    """Body text: Caladea (a classic book serif). weight: Regular | Bold (SemiBold = Bold)."""
    name = "Caladea-Regular.ttf" if weight == "Regular" else "Caladea-Bold.ttf"
    try:
        return ImageFont.truetype(str(FONT_DIR / name), size)
    except OSError:
        return ImageFont.truetype(_FALLBACK, size)


def display(size):
    """Titles and key words: Cinzel Bold (classic inscription capitals)."""
    try:
        return ImageFont.truetype(str(FONT_DIR / "Cinzel-Bold.ttf"), size)
    except OSError:
        return ImageFont.truetype(_FALLBACK, size)


F = {k: (display(s) if w == "Display" else font(s, w)) for k, (s, w) in {
    "h0": (100, "Display"), "h1": (66, "Display"), "h2": (46, "Bold"), "h3": (32, "Display"),
    "b": (36, "Regular"), "s": (28, "Regular"), "sb": (28, "Bold"),
    "xs": (23, "Regular"), "xsb": (23, "Bold"), "cap": (36, "Bold"),
    "big": (72, "Display"), "mid": (48, "Bold"), "rc": (56, "Bold"),
    "lab": (24, "Display"),
}.items()}
_LETTER_FONTS = {}


def letter_font(size):
    size = max(8, int(round(size)))
    if size not in _LETTER_FONTS:
        _LETTER_FONTS[size] = font(size, "Bold")
    return _LETTER_FONTS[size]


class SDraw:
    """ImageDraw wrapper: logical coordinates, physical = logical * s."""

    def __init__(self, im, s=S):
        self.im, self.s, self.d = im, s, ImageDraw.Draw(im)
        self._fonts = {}

    def _f(self, f):
        key = (f.path, f.size)
        if key not in self._fonts:
            self._fonts[key] = ImageFont.truetype(f.path, int(f.size * self.s))
        return self._fonts[key]

    def _xy(self, xy):
        s = self.s
        if len(xy) and isinstance(xy[0], (tuple, list)):
            return [(x * s, y * s) for x, y in xy]
        return [v * s for v in xy]

    def ellipse(self, xy, fill=None, outline=None, width=1):
        self.d.ellipse(self._xy(xy), fill=fill, outline=outline, width=max(1, int(width * self.s)))

    def rounded_rectangle(self, xy, radius, fill=None, outline=None, width=1):
        self.d.rounded_rectangle(self._xy(xy), radius * self.s, fill=fill, outline=outline,
                                 width=max(1, int(width * self.s)))

    def rectangle(self, xy, fill=None, outline=None, width=1):
        self.d.rectangle(self._xy(xy), fill=fill, outline=outline, width=max(1, int(width * self.s)))

    def polygon(self, pts, fill=None, outline=None):
        self.d.polygon(self._xy(pts), fill=fill, outline=outline)

    def line(self, xy, fill=None, width=1):
        self.d.line(self._xy(xy), fill=fill, width=max(1, int(width * self.s)))

    def point(self, xy, fill=None):
        x, y = xy
        self.d.rectangle((x * self.s, y * self.s, x * self.s + self.s - 1, y * self.s + self.s - 1),
                         fill=fill)

    def text(self, xy, s, font, fill=None):
        self.d.text((xy[0] * self.s, xy[1] * self.s), s, font=self._f(font), fill=fill)

    def textlength(self, s, font):
        return self.d.textlength(s, font=self._f(font)) / self.s

    def veil(self, box, color=(0x3A, 0x2A, 0x18), alpha=110, radius=16):
        x0, y0, x1, y1 = [int(v * self.s) for v in box]
        layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), radius * self.s,
                                                fill=color + (alpha,))
        self.im.paste(layer, (x0, y0), layer)



_PARCHMENT = {}


def _parchment(w, h, base=BG, seed=7):
    """Warm parchment: soft low-frequency mottling, fine grain and a gentle vignette."""
    key = (w, h, base, seed)
    if key not in _PARCHMENT:
        rng = np.random.default_rng(seed)
        low = Image.fromarray(rng.integers(0, 255, (9, 16), dtype=np.uint8)).resize(
            (w, h), Image.BICUBIC)
        mid = Image.fromarray(rng.integers(0, 255, (36, 64), dtype=np.uint8)).resize(
            (w, h), Image.BICUBIC)
        m = (np.asarray(low, np.float32) - 128) / 128 * 5 + (np.asarray(mid, np.float32) - 128) / 128 * 2.5
        m += rng.normal(0, 1.6, (h, w)).astype(np.float32)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
        m -= np.clip(r - 0.75, 0, None) * 26
        tint = np.array([1.0, 0.92, 0.78], np.float32)       # darker = browner, like old paper
        arr = np.asarray(base, np.float32)[None, None, :] + m[..., None] * tint
        _PARCHMENT[key] = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    return _PARCHMENT[key].copy()


def new_canvas():
    im = _parchment(W * S, H * S)
    return im, SDraw(im)


def text_center(d, xy, s, f, fill=INK):
    d.text((xy[0] - d.textlength(s, font=f) / 2, xy[1]), s, font=f, fill=fill)


def wrap_text(d, s, f, maxw):
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def mix(a, b, t):
    """Blend colour a towards b by t (0 = a, 1 = b)."""
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


# -------------------------------------------------------------- ornaments
def star8(d, cx, cy, ro, ri, fill, rot=0.0):
    """Eight-point star (two overlapping squares' outline as one polygon)."""
    pts = []
    for i in range(16):
        a = rot - math.pi / 2 + i * math.pi / 8
        rr = ro if i % 2 == 0 else ri
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def diamond(d, cx, cy, r, fill):
    d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=fill)


def frame(d, box, radius=26, fill=PAPER, edge=NAVY, line=GOLD, width=8, corners=True):
    """Cream panel in a deep-blue frame with an inner ochre-gold line and small corner
    diamonds: the house style for cards, captions and boards."""
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius, fill=fill, outline=edge, width=width)
    g = width + 6
    d.rounded_rectangle((x0 + g, y0 + g, x1 - g, y1 - g), max(4, radius - g), outline=line, width=2)
    if corners:
        k = width / 2 + 0.5
        for x, y in ((x0 + k + 14, y0 + k + 14), (x1 - k - 14, y0 + k + 14),
                     (x0 + k + 14, y1 - k - 14), (x1 - k - 14, y1 - k - 14)):
            diamond(d, x, y, 9, edge)
            diamond(d, x, y, 4, line)


def azulejo(d, cx, cy, s, kind, bg=COBALT, ink=PAPER):
    """One small decorative wall tile (original geometric patterns) for borders."""
    x0, y0 = cx - s / 2, cy - s / 2
    d.rectangle((x0, y0, x0 + s, y0 + s), fill=bg)
    if kind == 0:     # eight-point star with a dot
        star8(d, cx, cy, s * 0.42, s * 0.2, ink)
        d.ellipse((cx - s * 0.08, cy - s * 0.08, cx + s * 0.08, cy + s * 0.08), fill=bg)
    elif kind == 1:   # corner triangles and a centre diamond
        q = s * 0.32
        x1, y1 = x0 + s, y0 + s
        for (x, y), (sx, sy) in (((x0, y0), (1, 1)), ((x1, y0), (-1, 1)), ((x0, y1), (1, -1)),
                                 ((x1, y1), (-1, -1))):
            d.polygon([(x, y), (x + sx * q, y), (x, y + sy * q)], fill=ink)
        diamond(d, cx, cy, s * 0.22, ink)
    else:             # four petals
        r = s * 0.13
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            px, py = cx + dx * s * 0.2, cy + dy * s * 0.2
            d.ellipse((px - r, py - r, px + r, py + r), fill=ink)
        d.ellipse((cx - r * 0.6, cy - r * 0.6, cx + r * 0.6, cy + r * 0.6), fill=bg)


def azulejo_band(d, x0, x1, y, s, light=False):
    """A strip of small azulejo tiles from x0 to x1, centred on height y."""
    n = max(1, int((x1 - x0) // s))
    left = x0 + ((x1 - x0) - n * s) / 2
    for i in range(n):
        cx = left + i * s + s / 2
        if light:
            bg, ink = (PAPER, COBALT) if i % 2 else (SKY, NAVY)
        else:
            bg, ink = (COBALT, PAPER) if i % 2 == 0 else (NAVY, SKY)
        azulejo(d, cx, y, s - 2, i % 3, bg=bg, ink=ink)
    d.line((left, y - s / 2 - 2, left + n * s, y - s / 2 - 2), fill=GOLD, width=3)
    d.line((left, y + s / 2 + 1, left + n * s, y + s / 2 + 1), fill=GOLD, width=3)


# ------------------------------------------------------------------ tiles
def _mark(d, cx, cy, s, colour, ink, bg):
    """Original geometric motif of each colour (kept inside about 0.3 s of the centre)."""
    if colour == "blue":        # ring with a dot
        r, w = s * 0.19, s * 0.065
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ink, width=max(1.5, w))
        r = s * 0.065
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ink)
    elif colour == "yellow":    # four-petal rosette (quatrefoil) with dots between petals
        r, o = s * 0.105, s * 0.13
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            d.ellipse((cx + dx * o - r, cy + dy * o - r, cx + dx * o + r, cy + dy * o + r), fill=ink)
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            q, rr = s * 0.17, s * 0.035
            d.ellipse((cx + dx * q - rr, cy + dy * q - rr, cx + dx * q + rr, cy + dy * q + rr), fill=ink)
        r = s * 0.055
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=bg)
    elif colour == "red":       # diamond with a diamond window
        diamond(d, cx, cy, s * 0.23, ink)
        diamond(d, cx, cy, s * 0.09, bg)
    elif colour == "black":     # lattice: plus sign and four small diamonds
        a, t = s * 0.22, s * 0.05
        d.rectangle((cx - a, cy - t, cx + a, cy + t), fill=ink)
        d.rectangle((cx - t, cy - a, cx + t, cy + a), fill=ink)
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            diamond(d, cx + dx * s * 0.17, cy + dy * s * 0.17, s * 0.055, ink)
    elif colour == "white":     # eight-ray star of slim rhombi (a snowflake-like flower)
        ro, hw = s * 0.31, s * 0.06
        for i in range(8):
            a = i * math.pi / 4
            ux, uy = math.cos(a), math.sin(a)
            px, py = -uy, ux
            mx, my = cx + ux * ro * 0.5, cy + uy * ro * 0.5
            d.polygon([(cx + ux * s * 0.05, cy + uy * s * 0.05), (mx + px * hw, my + py * hw),
                       (cx + ux * ro, cy + uy * ro), (mx - px * hw, my - py * hw)], fill=ink)
        r = s * 0.05
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ink)


def tile(d, cx, cy, s, colour, faint=False, outline=None, letter=True, base=PANEL):
    """One tile centred at (cx, cy), side s. colour 'marker' = starting player marker.
    faint=True: the pale wall-space version (about 35% strength) without shadow."""
    x0, y0, x1, y1 = cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2
    rad = s * 0.12
    if colour == E.MARKER:
        d.rounded_rectangle((x0 + 3, y0 + 4, x1 + 3, y1 + 4), rad, fill=SHADOW)
        d.rounded_rectangle((x0, y0, x1, y1), rad, fill=MARKER_FILL,
                            outline=outline or NAVY, width=max(2, s * 0.07))
        d.rounded_rectangle((x0 + s * 0.15, y0 + s * 0.15, x1 - s * 0.15, y1 - s * 0.15), s * 0.08,
                            outline=COBALT, width=max(1.5, s * 0.03))
        f = display(max(8, int(round(s * 0.5))))
        tw = d.textlength("1", f)
        d.text((cx - tw / 2, cy - s * 0.36), "1", font=f, fill=NAVY)
        return
    fill, edge, ink = FILL[colour], EDGE[colour], MARK_INK[colour]
    if faint:
        fill = mix(base, fill, 0.36)
        ink = mix(base, ink if colour != "white" else NAVY, 0.36)
        edge = mix(base, edge, 0.45)
        d.rounded_rectangle((x0, y0, x1, y1), rad, fill=fill, outline=edge, width=2)
        _mark(d, cx, cy, s, colour, ink, fill)
        return
    d.rounded_rectangle((x0 + 3, y0 + 4, x1 + 3, y1 + 4), rad, fill=SHADOW)
    d.rounded_rectangle((x0, y0, x1, y1), rad, fill=fill, outline=outline or edge,
                        width=max(2, s * (0.08 if outline else 0.045)))
    d.rounded_rectangle((x0 + s * 0.1, y0 + s * 0.07, x1 - s * 0.1, y0 + s * 0.15), s * 0.04,
                        fill=mix(fill, (255, 255, 255), 0.22))
    if s >= 30:   # thin inset frame, like a glazed tile's border
        a = s * 0.36
        d.rounded_rectangle((cx - a, cy - a, cx + a, cy + a), s * 0.05,
                            outline=mix(fill, ink, 0.45), width=max(1, s * 0.022))
    _mark(d, cx, cy, s, colour, ink, fill)
    if letter and s >= 30:
        f = letter_font(s * 0.24)
        d.text((x0 + s * 0.09, y1 - s * 0.34), E.LETTERS[colour], font=f, fill=LETTER_INK[colour])


def empty_slot(d, cx, cy, s, colour=SLOT, width=3, fill=SAND):
    d.rounded_rectangle((cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2), s * 0.12, fill=fill,
                        outline=colour, width=width)


def cross(d, cx, cy, s, colour=BAD, width=9):
    a = s / 2
    for c, w in ((PAPER, width + 6), (colour, width)):
        d.line((cx - a, cy - a, cx + a, cy + a), fill=c, width=w)
        d.line((cx - a, cy + a, cx + a, cy - a), fill=c, width=w)


# ------------------------------------------------------------- geometry
T, G = 60, 8                  # board tile side, gap
P = T + G                     # pitch
BOARD_W, BOARD_H = 800, 560
BOARD_Y = 440
BOARD_X = (60, 1060)
LINES_DY = 88                 # top of pattern line 1 inside the board
WALL_DX = 428                 # left of wall column 1 inside the board
FLOOR_DY = LINES_DY + 5 * P + 12
FACT_R = 80
FT = 50                       # factory / centre tile side
FACT_OFF = ((-29, -29), (29, -29), (-29, 29), (29, 29))
CENTRE_BOX = (800, 168, 1120, 424)
BAG_BOX = (60, 40, 320, 300)
LID_BOX = (1600, 40, 1860, 330)
LT = 48                       # box lid tile side
BAG_XY = (190, 190)
LID_XY = (1730, 200)


def factory_xy(i, n=5):
    """Centre of factory display i (2 players: 5 displays on an ellipse)."""
    a = math.radians(-90 + 360 / n * i)
    return 960 + 420 * math.cos(a), 225 + 140 * math.sin(a)


def factory_box(i, m=0):
    x, y = factory_xy(i)
    r = FACT_R + m
    return (x - r, y - r, x + r, y + r)


def centre_slot(j):
    row, col = divmod(j, 5)
    return 960 + (col - 2) * 60, 225 + row * 56


def lid_slot(j):
    row, col = divmod(j, 4)
    return LID_BOX[0] + 49 + col * 54, LID_BOX[1] + 140 + row * 52


LID_SLOTS = 12


def board_box(p):
    return (BOARD_X[p], BOARD_Y, BOARD_X[p] + BOARD_W, BOARD_Y + BOARD_H)


def line_xy(p, row, k):
    """Centre of slot k (0 = rightmost, next to the wall) of pattern line `row`."""
    bx = BOARD_X[p]
    return bx + 24 + (4 - k) * P + T / 2, BOARD_Y + LINES_DY + row * P + T / 2


def wall_xy(p, row, col):
    return BOARD_X[p] + WALL_DX + col * P + T / 2, BOARD_Y + LINES_DY + row * P + T / 2


def floor_xy(p, k):
    return BOARD_X[p] + 24 + k * P + T / 2, BOARD_Y + FLOOR_DY + T / 2


def lines_box(p, rows=range(5)):
    rows = list(rows)
    bx = BOARD_X[p]
    x0 = bx + 24 + (4 - max(rows)) * P
    return (x0 - 6, BOARD_Y + LINES_DY + min(rows) * P - 6, bx + 24 + 5 * P - G + 6,
            BOARD_Y + LINES_DY + max(rows) * P + T + 6)


def line_box(p, row):
    return lines_box(p, [row])


def wall_box(p):
    bx = BOARD_X[p]
    return (bx + WALL_DX - 6, BOARD_Y + LINES_DY - 6, bx + WALL_DX + 5 * P - G + 6,
            BOARD_Y + LINES_DY + 5 * P - G + 6)


def cell_box(p, row, col, m=4):
    x, y = wall_xy(p, row, col)
    return (x - T / 2 - m, y - T / 2 - m, x + T / 2 + m, y + T / 2 + m)


def wall_row_box(p, row):
    x0, _, x1, _ = wall_box(p)
    _, y, _, _ = cell_box(p, row, 0, 6)
    return (x0, y, x1, y + T + 12)


def wall_col_box(p, col):
    x, _, _, _ = cell_box(p, 0, col, 6)
    _, y0, _, y1 = wall_box(p)
    return (x, y0, x + T + 12, y1)


def floor_box(p):
    bx = BOARD_X[p]
    return (bx + 18, BOARD_Y + FLOOR_DY - 6, bx + 24 + 7 * P - G + 6, BOARD_Y + FLOOR_DY + T + 38)


def score_box(p):
    bx = BOARD_X[p]
    return (bx + 236, BOARD_Y + 6, bx + BOARD_W - 12, BOARD_Y + 56)


def marker_home(p):
    return BOARD_X[p] + 180, BOARD_Y + 30


# ------------------------------------------------------------------ registry
# Every tile drawn is recorded with a stable key so animations can move it.
CTX = {"reg": {}, "hide": set()}
PARTS = ("bag", "lid", "factories", "centre", "board0", "board1")


def rtile(d, key, cx, cy, s, colour, slot=False, **kw):
    """Registered tile. If its key is hidden (it is being animated in), draw only the
    empty slot (slot=True) or nothing."""
    CTX["reg"][key] = (cx, cy, s, colour)
    if key in CTX["hide"]:
        if slot:
            empty_slot(d, cx, cy, s)
        return
    tile(d, cx, cy, s, colour, **kw)



# ------------------------------------------------------------------- board
def text_mid(d, x, cy, s, f, fill=INK, anchor="l"):
    """Draw text so its ink is vertically centred on cy (anchor l / m / r on x)."""
    pf = d._f(f)
    l, t, r, b = pf.getbbox(s)
    w = (r - l) / d.s
    x = x - w / 2 if anchor == "m" else x - w if anchor == "r" else x
    d.text((x - l / d.s, cy - (t + b) / 2 / d.s), s, font=f, fill=fill)


def fit_font(d, s, maker, size, maxw, smallest=24):
    """Largest font from maker(size) (stepping down) whose width of s fits maxw."""
    while size > smallest and d.textlength(s, maker(size)) > maxw:
        size -= 2
    return maker(size)


def draw_board(d, st, p, name, hl, active=False):
    b = st["boards"][p]
    bx, by = BOARD_X[p], BOARD_Y
    grey = st.get("variant") == E.GREY
    if active:
        d.rounded_rectangle((bx - 9, by - 9, bx + BOARD_W + 9, by + BOARD_H + 9), 30, outline=GOLD,
                            width=7)
    frame(d, (bx, by, bx + BOARD_W, by + BOARD_H), 22, fill=PAPER, edge=NAVY, line=GOLD, width=7,
          corners=False)
    # header band in deep blue, like the board's own blue scoring area
    d.rounded_rectangle((bx + 7, by + 7, bx + BOARD_W - 7, by + 52), 16, fill=NAVY)
    d.rectangle((bx + 7, by + 30, bx + BOARD_W - 7, by + 52), fill=NAVY)
    d.line((bx + 7, by + 53, bx + BOARD_W - 7, by + 53), fill=GOLD, width=2)
    text_mid(d, bx + 24, by + 30, name, F["h3"], fill=GOLD_LIGHT if active else PAPER)
    # score track: a 0-100 strip with the score marker (a small black cube)
    x0, x1, ty = bx + 290, bx + 620, by + 24
    d.rounded_rectangle((x0, ty, x1, ty + 12), 6, fill=(0x3A, 0x5C, 0x96), outline=SKY, width=2)
    for v in range(0, 101, 10):
        tx = x0 + (x1 - x0) * v / 100
        d.line((tx, ty + 2, tx, ty + 10), fill=SKY, width=2)
    text_mid(d, x0 - 12, ty + 6, "0", F["xsb"], fill=SKY, anchor="r")
    text_mid(d, x1 + 12, ty + 6, "100", F["xsb"], fill=SKY)
    sc = b["score"]
    mx = x0 + (x1 - x0) * min(sc, 100) / 100
    d.rectangle((mx - 11, ty - 5, mx + 11, ty + 17), fill=(18, 18, 22), outline=PAPER, width=2)
    # score number on an ochre plaque, like the numbers printed on the score track
    s = str(sc)
    on = hl.get("score") == p
    tw = d.textlength(s, F["h2"])
    px1 = bx + BOARD_W - 16
    px0 = px1 - max(64, tw + 28)
    d.rounded_rectangle((px0, by + 4, px1, by + 56), 10, fill=HL if on else (0xF1, 0xB8, 0x52),
                        outline=GOLD_LIGHT if on else NAVY, width=3)
    text_mid(d, (px0 + px1) / 2, by + 30, s, F["h2"], fill=(255, 255, 255) if on else INK, anchor="m")
    # labels
    lx = bx + 24 + 5 * P - G
    d.text((lx - d.textlength("PATTERN LINES", F["xsb"]), by + 57), "PATTERN LINES", font=F["xsb"],
           fill=MUTED)
    text_center(d, (bx + WALL_DX + (5 * P - G) / 2, by + 57), "WALL", F["xsb"], fill=MUTED)
    # pattern lines
    hl_lines = hl.get("lines", {}).get(p, ())
    for r in range(5):
        pl = b["lines"][r]
        for k in range(r + 1):
            x, y = line_xy(p, r, k)
            if k < pl["count"]:
                rtile(d, ("p", p, "line", r, k), x, y, T, pl["colour"], slot=True)
            else:
                empty_slot(d, x, y, T)
        ay = by + LINES_DY + r * P + T / 2
        ax = bx + 24 + 5 * P - G + 14
        d.polygon([(ax, ay - 12), (ax + 22, ay), (ax, ay + 12)], fill=NAVY)
        d.ellipse((ax + 3, ay - 3, ax + 9, ay + 3), fill=GOLD_LIGHT)
        if r in hl_lines:
            x0_, y0_, x1_, y1_ = line_box(p, r)
            d.rounded_rectangle((x0_, y0_, x1_, y1_), 12, outline=HL, width=5)
    # wall, on a stone tray with a gold edge
    wx0, wy0, wx1, wy1 = wall_box(p)
    d.rounded_rectangle((wx0 - 4, wy0 - 4, wx1 + 4, wy1 + 4), 14, fill=WALL_BG, outline=GOLD, width=2)
    hl_cells = set(hl.get("cells", {}).get(p, ()))
    for r in range(5):
        for c in range(5):
            x, y = wall_xy(p, r, c)
            t = b["wall"][r][c]
            if grey:
                d.rounded_rectangle((x - T / 2, y - T / 2, x + T / 2, y + T / 2), T * 0.12,
                                    fill=GREY_SPACE, outline=(0x9E, 0x96, 0x8A), width=2)
            else:
                tile(d, x, y, T, E.wall_colour(r, c), faint=True, base=WALL_BG)
            if t:
                CTX["reg"][("p", p, "wall", r, c)] = (x, y, T, t)
                if ("p", p, "wall", r, c) not in CTX["hide"]:
                    tile(d, x, y, T, t)
            if (r, c) in hl_cells:
                d.rounded_rectangle((x - T / 2 - 5, y - T / 2 - 5, x + T / 2 + 5, y + T / 2 + 5), 12,
                                    outline=HL, width=5)
    # floor line
    fy = by + FLOOR_DY
    for k, v in enumerate(E.FLOOR_VALUES):
        x, y = floor_xy(p, k)
        empty_slot(d, x, y, T, colour=COBALT, fill=(0xEE, 0xE6, 0xD6))
        text_center(d, (x, fy + T + 2), f"−{-v}", F["sb"], fill=MINUS)
        if k < len(b["floor"]):
            item = b["floor"][k]
            if item == E.MARKER:
                CTX["reg"][("m",)] = (x, y, T, E.MARKER)
                if ("m",) not in CTX["hide"]:
                    tile(d, x, y, T, E.MARKER)
            else:
                rtile(d, ("p", p, "floor", k), x, y, T, item, slot=True)
    d.text((bx + 24 + 7 * P + 8, fy + 16), "FLOOR LINE", font=F["xsb"], fill=MUTED)
    if hl.get("floor") == p:
        d.rounded_rectangle(floor_box(p), 12, outline=HL, width=5)
    for kind, *where in hl.get("xs", ()):
        if where[0] != p:
            continue
        if kind == "line":
            x0_, y0_, x1_, y1_ = line_box(p, where[1])
            cross(d, (x0_ + x1_) / 2, (y0_ + y1_) / 2, min(56, y1_ - y0_ - 10))
        elif kind == "cell":
            x, y = wall_xy(p, where[1], where[2])
            cross(d, x, y, 40)


# ------------------------------------------------------------------ middle
BAG_BLUE = (0x4F, 0x7C, 0xBE)      # washed cotton blue
BAG_PRINT = (0xE4, 0xEA, 0xF0)     # cream-white print


def draw_bag(d, st, hl=None):
    x0, y0, x1, y1 = BAG_BOX
    cx = (x0 + x1) / 2
    on = hl == "bag"
    ex0, ey0, ex1, ey1 = x0 + 10, y0 + 60, x1 - 10, y1
    d.ellipse((ex0 + 4, ey0 + 6, ex1 + 4, ey1 + 6), fill=SHADOW)
    # gathered neck with a ruffled top
    d.polygon([(cx - 64, y0 + 82), (cx - 40, y0 + 44), (cx + 40, y0 + 44), (cx + 64, y0 + 82)],
              fill=BAG_BLUE)
    for k in range(-4, 5):
        x = cx + k * 10
        d.ellipse((x - 8, y0 + 34, x + 8, y0 + 50), fill=BAG_BLUE)
    d.ellipse((ex0, ey0, ex1, ey1), fill=BAG_BLUE)
    # printed pattern: small stars and diamonds on a grid, kept inside the bag outline
    ecx, ecy, rx, ry = (ex0 + ex1) / 2, (ey0 + ey1) / 2, (ex1 - ex0) / 2, (ey1 - ey0) / 2
    for j in range(-4, 5):
        for i in range(-5, 6):
            x, y = ecx + i * 28 + (14 if j % 2 else 0), ecy + j * 26
            if ((x - ecx) / (rx - 14)) ** 2 + ((y - ecy) / (ry - 14)) ** 2 > 1:
                continue
            if (i + j) % 2:
                star8(d, x, y, 8, 3.5, BAG_PRINT)
            else:
                diamond(d, x, y, 4, BAG_PRINT)
    # folds and a cream drawstring tied in a bow
    for k in (-2, -1, 1, 2):
        d.line((cx + k * 12, y0 + 50, cx + k * 20, y0 + 84), fill=mix(BAG_BLUE, NAVY, 0.45), width=2)
    d.rounded_rectangle((cx - 48, y0 + 58, cx + 48, y0 + 67), 4, fill=BAG_PRINT)
    for sx in (-1, 1):
        d.ellipse((cx + sx * 22 - 13, y0 + 52, cx + sx * 22 + 13, y0 + 73), outline=BAG_PRINT, width=4)
    d.line((cx - 4, y0 + 66, cx - 16, y0 + 92), fill=BAG_PRINT, width=4)
    d.line((cx + 4, y0 + 66, cx + 18, y0 + 90), fill=BAG_PRINT, width=4)
    if on:
        d.ellipse((ex0 - 4, ey0 - 4, ex1 + 4, ey1 + 4), outline=HL, width=6)
    # label plaque
    frame(d, (cx - 74, y0 + 104, cx + 74, y0 + 196), 14, fill=PAPER, edge=NAVY, line=GOLD, width=4,
          corners=False)
    text_center(d, (cx, y0 + 116), "BAG", F["h3"], fill=NAVY)
    n = len(st["bag"])
    text_center(d, (cx, y0 + 152), f"{n} tile" + ("" if n == 1 else "s"), F["sb"], fill=INK)


def draw_lid(d, st, hl=None):
    x0, y0, x1, y1 = LID_BOX
    on = hl == "lid"
    d.rounded_rectangle((x0 + 4, y0 + 6, x1 + 4, y1 + 6), 18, fill=SHADOW)
    d.rounded_rectangle((x0, y0, x1, y1), 18, fill=NAVY, outline=HL if on else NAVY,
                        width=6 if on else 3)
    d.rounded_rectangle((x0 + 6, y0 + 6, x1 - 6, y1 - 6), 14, outline=SKY, width=2)
    text_center(d, ((x0 + x1) / 2, y0 + 14), "BOX LID", F["h3"], fill=PAPER)
    n = len(st["lid"])
    text_center(d, ((x0 + x1) / 2, y0 + 54), f"{n} tile" + ("" if n == 1 else "s"), F["xsb"],
                fill=GOLD_LIGHT)
    d.rounded_rectangle((x0 + 12, y0 + 92, x1 - 12, y1 - 12), 12, fill=SAND, outline=GOLD, width=2)
    for j, c in enumerate(st["lid"][:LID_SLOTS]):
        x, y = lid_slot(j)
        rtile(d, ("lid", j), x, y, LT, c, letter=False)


def factory_disc(d, x, y, r, on=False):
    """A factory display: terracotta rim, cream ring with blue beads, a gold ring and a
    blue centre with rays (an original simple design)."""
    d.ellipse((x - r + 3, y - r + 5, x + r + 3, y + r + 5), fill=SHADOW)
    d.ellipse((x - r, y - r, x + r, y + r), fill=FACTORY_RIM,
              outline=HL if on else mix(FACTORY_RIM, (60, 20, 10), 0.35), width=7 if on else 3)
    rc = r * 0.88
    d.ellipse((x - rc, y - rc, x + rc, y + rc), fill=FACTORY)
    rb, n = r * 0.72, 16
    for i in range(n):
        a = i * 2 * math.pi / n
        bx_, by_ = x + rb * math.cos(a), y + rb * math.sin(a)
        if i % 2:
            q = r * 0.055
            d.ellipse((bx_ - q, by_ - q, bx_ + q, by_ + q), fill=NAVY)
        else:
            q = r * 0.075
            d.ellipse((bx_ - q, by_ - q, bx_ + q, by_ + q), outline=NAVY, width=max(1.5, r * 0.025))
    rg = r * 0.56
    d.ellipse((x - rg, y - rg, x + rg, y + rg), fill=GOLD)
    rd = r * 0.5
    d.ellipse((x - rd, y - rd, x + rd, y + rd), fill=NAVY)
    ri = r * 0.44
    d.ellipse((x - ri, y - ri, x + ri, y + ri), fill=COBALT)
    for i in range(24):
        a = i * math.pi / 12
        d.line((x + r * 0.1 * math.cos(a), y + r * 0.1 * math.sin(a),
                x + ri * 0.95 * math.cos(a), y + ri * 0.95 * math.sin(a)), fill=SKY,
               width=max(1, r * 0.018))
    q = r * 0.09
    d.ellipse((x - q, y - q, x + q, y + q), fill=FACTORY, outline=GOLD, width=max(1, r * 0.02))


def draw_factories(d, st, hl=None):
    hl = hl or ()
    for i, f in enumerate(st["factories"]):
        x, y = factory_xy(i, len(st["factories"]))
        factory_disc(d, x, y, FACT_R, i in hl)
        for j, c in enumerate(f):
            dx, dy = FACT_OFF[j]
            rtile(d, ("f", i, j), x + dx, y + dy, FT, c)


def draw_centre(d, st, hl=False):
    x0, y0, x1, y1 = CENTRE_BOX
    d.rounded_rectangle((x0, y0, x1, y1), 24, fill=mix(BG, PAPER, 0.7),
                        outline=HL if hl else SLOT, width=5 if hl else 2)
    text_center(d, ((x0 + x1) / 2, y0 + 4), "CENTRE OF THE TABLE", F["xsb"], fill=MUTED)
    j = 0
    if st.get("centre_marker"):
        x, y = centre_slot(0)
        CTX["reg"][("m",)] = (x, y, FT, E.MARKER)
        if ("m",) not in CTX["hide"]:
            tile(d, x, y, FT, E.MARKER)
        j = 1
    for i, c in enumerate(sorted(st["centre"], key=E.COLOURS.index)):
        x, y = centre_slot(j + i)
        rtile(d, ("c", i), x, y, FT, c)


def draw_held_marker(d, st):
    p = st.get("marker_holder")
    if p is None or st.get("centre_marker") or any(E.MARKER in b["floor"] for b in st["boards"]):
        return
    x, y = marker_home(p)
    CTX["reg"][("m",)] = (x, y, 44, E.MARKER)
    if ("m",) not in CTX["hide"]:
        tile(d, x, y, 44, E.MARKER)


def table(st, names=("Ana", "Ben"), hl=None, hide=None, show=None, active=None, **_anim):
    """Full table view (supersampled). show: subset of PARTS (default all), used to
    introduce the table piece by piece. hl keys: lines={p: [rows]}, cells={p: [(r, c)]},
    floor=p, factories=[i], centre=True, mid='bag'|'lid', score=p,
    xs=[('line', p, r) | ('cell', p, r, c)]. active: player whose board is outlined.
    Other keyword arguments (e.g. src_xy) are animation hints and are ignored here."""
    hl = hl or {}
    show = set(PARTS if show is None else show)
    CTX.update(reg={}, hide=set(hide or ()))
    im, d = new_canvas()
    if "bag" in show:
        draw_bag(d, st, hl.get("mid"))
    if "lid" in show:
        draw_lid(d, st, hl.get("mid"))
    if "factories" in show:
        draw_factories(d, st, hl.get("factories"))
    if "centre" in show:
        draw_centre(d, st, bool(hl.get("centre")))
    for p in range(min(2, len(st["boards"]))):
        if f"board{p}" in show:
            draw_board(d, st, p, names[p], hl, active=(active == p))
    if any(f"board{p}" in show for p in (0, 1)) or "centre" in show:
        draw_held_marker(d, st)
    return im


# ------------------------------------------------------------------ cards
MOTIF = ("blue", "yellow", "red", "black", "white")


def _rule(d, cx, y, half):
    """Ornamental rule: gold line with a centre diamond."""
    d.line((cx - half, y, cx - 18, y), fill=GOLD, width=3)
    d.line((cx + 18, y, cx + half, y), fill=GOLD, width=3)
    diamond(d, cx, y, 11, NAVY)
    diamond(d, cx, y, 5, GOLD_LIGHT)


def _bands(d):
    azulejo_band(d, 0, W, 44, 64)
    azulejo_band(d, 0, W, H - 44, 64)


def title_card(title, sub=None, kicker=None):
    im, d = new_canvas()
    _bands(d)
    frame(d, (250, 206, W - 250, H - 206), 34, width=9)
    if kicker:
        text_center(d, (W / 2, 292), kicker.upper(), F["sb"], fill=RED)
    _rule(d, W / 2, 350, 300)
    f = fit_font(d, title, display, F["h0"].size, W - 640)
    text_mid(d, W / 2, 440, title, f, fill=NAVY, anchor="m")
    subs = wrap_text(d, sub, F["h2"], 1240) if sub else []
    for i, ln in enumerate(subs):
        text_center(d, (W / 2, 516 + i * 60), ln, F["h2"], fill=RED)
    ty = 676 + 60 * max(0, len(subs) - 1)
    for i, c in enumerate(MOTIF):
        tile(d, W / 2 + (i - 2) * 112, ty, 80, c)
    return im


def recap_card(lines, nxt=None, title="Remember"):
    """End-of-episode recap: 2-3 short lines, plus a 'Next:' teaser."""
    im, d = new_canvas()
    wrapped = [wrap_text(d, ln, F["rc"], W - 660) for ln in lines]
    body = sum(70 * len(w) + 44 for w in wrapped) - 44
    h = 200 + body + 76
    top = (850 - h) / 2 + 20
    frame(d, (200, top, W - 200, top + h), 40, width=9)
    text_center(d, (W / 2, top + 46), title, F["h1"], fill=RED)
    _rule(d, W / 2, top + 150, 260)
    y = top + 196
    for i, sub in enumerate(wrapped):
        tile(d, 330, y + 36, 50, MOTIF[i % len(MOTIF)], letter=False)
        for j, s in enumerate(sub):
            d.text((390, y + j * 70), s, font=F["rc"], fill=INK)
        y += 70 * len(sub) + 44
    if nxt:
        s = f"Next: {nxt}"
        f = fit_font(d, s, lambda z: font(z, "Bold"), F["mid"].size, W - 360)
        tw = d.textlength(s, font=f)
        d.rounded_rectangle((W / 2 - tw / 2 - 44, 900, W / 2 + tw / 2 + 44, 990), 45, fill=NAVY,
                            outline=GOLD, width=4)
        text_mid(d, W / 2, 945, s, f, fill=PAPER, anchor="m")
    return im


def tiles_card(hl_marks=False, count=None):
    """The five tile colours with name, letter and mark."""
    im, d = new_canvas()
    text_center(d, (W / 2, 100), "Five colours", F["h1"], fill=RED)
    _rule(d, W / 2, 200, 260)
    for i, c in enumerate(E.COLOURS):
        x = W / 2 + (i - 2) * 320
        tile(d, x, 400, 190, c, outline=HL if hl_marks else None)
        text_center(d, (x, 528), c, F["h2"], fill=INK)
        text_center(d, (x, 590), f"letter {E.LETTERS[c]}", F["b"], fill=HL if hl_marks else MUTED)
    if count:
        text_center(d, (W / 2, 780), count, F["h2"], fill=INK)
    return im


def factories_card(hl=None):
    """How many factory displays for 2, 3 and 4 players (numbers from the engine)."""
    im, d = new_canvas()
    text_center(d, (W / 2, 52), "Factory displays", F["h1"], fill=RED)
    for k, n in enumerate(sorted(E.FACTORIES)):
        y = 290 + k * 250
        on = hl == n
        frame(d, (120, y - 105, W - 120, y + 105), 30, edge=HL if on else NAVY,
              width=9 if on else 6, corners=False)
        text_mid(d, 170, y, f"{n} players", F["h1"], fill=INK)
        cnt = E.FACTORIES[n]
        for i in range(cnt):
            factory_disc(d, 610 + i * 112, y, 46)
        s = str(cnt)
        text_mid(d, W - 190, y, s, F["h0"], fill=RED, anchor="r")
    return im


def marker_card():
    """The starting player marker beside a tile, to show it is not a tile."""
    im, d = new_canvas()
    text_center(d, (W / 2, 100), "Starting player marker", F["h1"], fill=RED)
    _rule(d, W / 2, 200, 300)
    tile(d, W / 2 - 220, 470, 220, E.MARKER)
    tile(d, W / 2 + 220, 470, 220, "blue")
    text_center(d, (W / 2 - 220, 610), "marker", F["h2"], fill=INK)
    text_center(d, (W / 2 + 220, 610), "a tile", F["h2"], fill=INK)
    text_center(d, (W / 2, 780), "The marker is not a tile.", F["h2"], fill=INK)
    return im
