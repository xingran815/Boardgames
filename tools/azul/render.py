"""Pillow renderer for the Azul explainer videos.

Everything is laid out in a 1920x1080 logical space but drawn at S x that
resolution (SDraw scales every call), so the video can zoom into any region and
stay sharp. Original flat tile designs only (docs/azul/STYLE.md); no publisher
artwork, logo or board art.

The Azul modules load each other under `azul_*` names (see _load) so they never
clash with the Spirits of the Wild `engine` / `render` / `anim` modules.
"""
from __future__ import annotations

import importlib.util
import math
import random
import sys
from pathlib import Path

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
BG = (14, 22, 48)
PANEL = (26, 38, 78)
INK = (234, 240, 255)
MUTED = (150, 165, 205)
ACCENT = (110, 200, 255)
GOLD = (255, 205, 90)
HL = (255, 120, 60)
BAD = (235, 70, 70)
SLOT = (80, 96, 140)
MINUS = (255, 150, 130)

# docs/azul/STYLE.md
FILL = {"blue": (0x2F, 0x6F, 0xB5), "yellow": (0xE8, 0xB7, 0x30), "red": (0xC8, 0x42, 0x3A),
        "black": (0x2A, 0x2D, 0x34), "white": (0xEE, 0xF1, 0xF4)}
EDGE = {"blue": (20, 50, 90), "yellow": (140, 100, 20), "red": (110, 30, 25),
        "black": (120, 130, 150), "white": (0x9A, 0xA4, 0xB1)}
MARK_INK = {"blue": (255, 255, 255), "yellow": (90, 58, 0), "red": (255, 255, 255),
            "black": (255, 255, 255), "white": (0x5B, 0x6B, 0x80)}
MARKER_FILL = (246, 231, 200)
FACTORY = (0xD9, 0xB3, 0x8C)
FACTORY_RIM = (0x9C, 0x76, 0x50)
GREY_SPACE = (64, 74, 104)

FONT_DIR = "/usr/share/fonts/opentype/inter/"


def font(size, weight="Regular"):
    try:
        return ImageFont.truetype(FONT_DIR + f"Inter-{weight}.otf", size)
    except OSError:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)


F = {k: font(s, w) for k, (s, w) in {
    "h0": (104, "Bold"), "h1": (64, "Bold"), "h2": (44, "Bold"), "h3": (32, "Bold"),
    "b": (34, "Regular"), "s": (26, "Regular"), "sb": (26, "SemiBold"),
    "xs": (21, "Regular"), "xsb": (21, "SemiBold"), "cap": (34, "SemiBold"),
    "big": (84, "Bold"), "mid": (46, "SemiBold"), "rc": (54, "SemiBold"),
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

    def veil(self, box, color=(6, 10, 26), alpha=150, radius=16):
        x0, y0, x1, y1 = [int(v * self.s) for v in box]
        layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), radius * self.s,
                                                fill=color + (alpha,))
        self.im.paste(layer, (x0, y0), layer)


def new_canvas():
    im = Image.new("RGB", (W * S, H * S), BG)
    d = SDraw(im)
    r = random.Random(7)
    for _ in range(160):
        c = r.randrange(60, 130)
        d.point((r.randrange(W), r.randrange(H)), fill=(c, c, c + 40))
    return im, d


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


# ------------------------------------------------------------------ tiles
def _mark(d, cx, cy, s, colour, ink):
    if colour == "blue":
        r = s * 0.17
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ink)
    elif colour == "yellow":
        ro, ri = s * 0.27, s * 0.09
        pts = []
        for i in range(8):
            a = -math.pi / 2 + i * math.pi / 4
            rr = ro if i % 2 == 0 else ri
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        d.polygon(pts, fill=ink)
    elif colour == "red":
        r = s * 0.21
        d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=ink)
    elif colour == "black":
        a, t = s * 0.21, s * 0.055
        d.rectangle((cx - a, cy - t, cx + a, cy + t), fill=ink)
        d.rectangle((cx - t, cy - a, cx + t, cy + a), fill=ink)
    elif colour == "white":
        a = s * 0.17
        d.rectangle((cx - a, cy - a, cx + a, cy + a), outline=ink, width=max(1.5, s * 0.06))


def tile(d, cx, cy, s, colour, faint=False, outline=None, letter=True, base=PANEL):
    """One tile centred at (cx, cy), side s. colour 'marker' = starting player marker.
    faint=True: the pale wall-space version (about 25% strength) without shadow."""
    x0, y0, x1, y1 = cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2
    rad = s * 0.14
    if colour == E.MARKER:
        d.rounded_rectangle((x0 + 3, y0 + 4, x1 + 3, y1 + 4), rad, fill=(8, 12, 28))
        d.rounded_rectangle((x0, y0, x1, y1), rad, fill=MARKER_FILL,
                            outline=outline or GOLD, width=max(2, s * 0.06))
        f = letter_font(s * 0.62)
        tw = d.textlength("1", f)
        d.text((cx - tw / 2, cy - s * 0.42), "1", font=f, fill=(60, 40, 10))
        return
    fill, edge, ink = FILL[colour], EDGE[colour], MARK_INK[colour]
    if faint:
        fill = mix(base, fill, 0.27)
        ink = mix(base, ink if colour != "white" else (40, 50, 70), 0.30)
        edge = mix(base, edge, 0.35)
        d.rounded_rectangle((x0, y0, x1, y1), rad, fill=fill, outline=edge, width=2)
        _mark(d, cx, cy, s, colour, ink)
        return
    d.rounded_rectangle((x0 + 3, y0 + 4, x1 + 3, y1 + 4), rad, fill=(8, 12, 28))
    d.rounded_rectangle((x0, y0, x1, y1), rad, fill=fill, outline=outline or edge,
                        width=max(2, s * (0.08 if outline else 0.045)))
    d.rounded_rectangle((x0 + s * 0.1, y0 + s * 0.08, x1 - s * 0.1, y0 + s * 0.2), s * 0.06,
                        fill=mix(fill, (255, 255, 255), 0.22))
    _mark(d, cx, cy + s * 0.04, s, colour, ink)
    if letter and s >= 30:
        f = letter_font(s * 0.24)
        d.text((x0 + s * 0.09, y1 - s * 0.33), E.LETTERS[colour], font=f, fill=ink)


def empty_slot(d, cx, cy, s, colour=SLOT, width=3):
    d.rounded_rectangle((cx - s / 2, cy - s / 2, cx + s / 2, cy + s / 2), s * 0.14, outline=colour,
                        width=width)


def cross(d, cx, cy, s, colour=BAD, width=9):
    a = s / 2
    d.line((cx - a, cy - a, cx + a, cy + a), fill=colour, width=width)
    d.line((cx - a, cy + a, cx + a, cy - a), fill=colour, width=width)


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
def draw_board(d, st, p, name, hl, active=False):
    b = st["boards"][p]
    bx, by = BOARD_X[p], BOARD_Y
    grey = st.get("variant") == E.GREY
    d.rounded_rectangle((bx, by, bx + BOARD_W, by + BOARD_H), 22, fill=(20, 30, 64),
                        outline=GOLD if active else (50, 66, 120), width=4 if active else 2)
    d.text((bx + 24, by + 12), name, font=F["h3"], fill=GOLD if active else INK)
    # score track: a 0-100 strip with the score marker (a small black cube)
    x0, x1, ty = bx + 290, bx + 620, by + 24
    d.rounded_rectangle((x0, ty, x1, ty + 12), 6, fill=(40, 52, 96), outline=(70, 86, 140), width=2)
    for v in range(0, 101, 10):
        tx = x0 + (x1 - x0) * v / 100
        d.line((tx, ty + 2, tx, ty + 10), fill=(90, 106, 160), width=2)
    d.text((x0 - 14 - d.textlength("0", F["xs"]), ty - 6), "0", font=F["xs"], fill=MUTED)
    d.text((x1 + 12, ty - 6), "100", font=F["xs"], fill=MUTED)
    sc = b["score"]
    mx = x0 + (x1 - x0) * min(sc, 100) / 100
    d.rectangle((mx - 11, ty - 5, mx + 11, ty + 17), fill=(18, 18, 22), outline=(220, 225, 240), width=2)
    s = str(sc)
    on = hl.get("score") == p
    d.text((bx + BOARD_W - 24 - d.textlength(s, F["h2"]), by + 4), s, font=F["h2"],
           fill=HL if on else INK)
    # labels
    lx = bx + 24 + 5 * P - G
    d.text((lx - d.textlength("PATTERN LINES", F["xsb"]), by + 58), "PATTERN LINES", font=F["xsb"],
           fill=MUTED)
    text_center(d, (bx + WALL_DX + (5 * P - G) / 2, by + 58), "WALL", F["xsb"], fill=MUTED)
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
        d.polygon([(ax, ay - 11), (ax + 22, ay), (ax, ay + 11)], fill=(90, 106, 160))
        if r in hl_lines:
            x0_, y0_, x1_, y1_ = line_box(p, r)
            d.rounded_rectangle((x0_, y0_, x1_, y1_), 12, outline=HL, width=5)
    # wall
    hl_cells = set(hl.get("cells", {}).get(p, ()))
    for r in range(5):
        for c in range(5):
            x, y = wall_xy(p, r, c)
            t = b["wall"][r][c]
            if grey:
                d.rounded_rectangle((x - T / 2, y - T / 2, x + T / 2, y + T / 2), T * 0.14,
                                    fill=GREY_SPACE, outline=(90, 100, 130), width=2)
            else:
                tile(d, x, y, T, E.wall_colour(r, c), faint=True, base=(20, 30, 64))
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
        empty_slot(d, x, y, T, colour=(120, 80, 90))
        text_center(d, (x, fy + T + 4), f"−{-v}", F["sb"], fill=MINUS)
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
def draw_bag(d, st, hl=None):
    x0, y0, x1, y1 = BAG_BOX
    cx = (x0 + x1) / 2
    on = hl == "bag"
    d.ellipse((x0 + 10, y0 + 60, x1 - 10, y1), fill=(112, 74, 56),
              outline=HL if on else (170, 130, 100), width=5 if on else 3)
    d.polygon([(cx - 50, y0 + 70), (cx - 34, y0 + 30), (cx + 34, y0 + 30), (cx + 50, y0 + 70)],
              fill=(112, 74, 56))
    d.rounded_rectangle((cx - 44, y0 + 50, cx + 44, y0 + 64), 7, fill=(70, 46, 34))
    text_center(d, (cx, y0 + 110), "BAG", F["h3"], fill=(245, 225, 205))
    n = len(st["bag"])
    text_center(d, (cx, y0 + 160), f"{n} tile" + ("" if n == 1 else "s"), F["sb"], fill=INK)


def draw_lid(d, st, hl=None):
    x0, y0, x1, y1 = LID_BOX
    on = hl == "lid"
    d.rounded_rectangle((x0, y0, x1, y1), 18, fill=(52, 44, 40),
                        outline=HL if on else (150, 125, 100), width=5 if on else 3)
    d.rounded_rectangle((x0 + 12, y0 + 92, x1 - 12, y1 - 12), 12, fill=(38, 32, 30))
    text_center(d, ((x0 + x1) / 2, y0 + 12), "BOX LID", F["h3"], fill=(245, 225, 205))
    n = len(st["lid"])
    text_center(d, ((x0 + x1) / 2, y0 + 54), f"{n} tile" + ("" if n == 1 else "s"), F["xsb"], fill=INK)
    for j, c in enumerate(st["lid"][:LID_SLOTS]):
        x, y = lid_slot(j)
        rtile(d, ("lid", j), x, y, LT, c, letter=False)


def draw_factories(d, st, hl=None):
    hl = hl or ()
    for i, f in enumerate(st["factories"]):
        x, y = factory_xy(i, len(st["factories"]))
        on = i in hl
        d.ellipse((x - FACT_R + 3, y - FACT_R + 5, x + FACT_R + 3, y + FACT_R + 5), fill=(8, 12, 28))
        d.ellipse((x - FACT_R, y - FACT_R, x + FACT_R, y + FACT_R), fill=FACTORY,
                  outline=HL if on else FACTORY_RIM, width=7 if on else 5)
        d.ellipse((x - FACT_R + 12, y - FACT_R + 12, x + FACT_R - 12, y + FACT_R - 12),
                  outline=mix(FACTORY, FACTORY_RIM, 0.45), width=2)
        for j, c in enumerate(f):
            dx, dy = FACT_OFF[j]
            rtile(d, ("f", i, j), x + dx, y + dy, FT, c)


def draw_centre(d, st, hl=False):
    x0, y0, x1, y1 = CENTRE_BOX
    d.rounded_rectangle((x0, y0, x1, y1), 24, fill=(22, 34, 70),
                        outline=HL if hl else (60, 80, 140), width=5 if hl else 2)
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


def title_card(title, sub=None, kicker=None):
    im, d = new_canvas()
    if kicker:
        text_center(d, (W / 2, 300), kicker.upper(), F["sb"], fill=ACCENT)
    text_center(d, (W / 2, 360), title, F["h0"], fill=INK)
    if sub:
        for i, ln in enumerate(wrap_text(d, sub, F["h2"], 1400)):
            text_center(d, (W / 2, 520 + i * 60), ln, F["h2"], fill=GOLD)
    for i, c in enumerate(MOTIF):
        tile(d, W / 2 + (i - 2) * 100, 780, 70, c)
    return im


def recap_card(lines, nxt=None, title="Remember"):
    """End-of-episode recap: 2-3 short lines, plus a 'Next:' teaser."""
    im, d = new_canvas()
    wrapped = [wrap_text(d, ln, F["rc"], W - 640) for ln in lines]
    body = sum(68 * len(w) + 46 for w in wrapped) - 46
    h = 190 + body + 80
    top = (850 - h) / 2 + 20
    d.rounded_rectangle((200, top, W - 200, top + h), 40, fill=PANEL, outline=GOLD, width=4)
    text_center(d, (W / 2, top + 50), title, F["h1"], fill=GOLD)
    y = top + 190
    for i, sub in enumerate(wrapped):
        tile(d, 330, y + 34, 50, MOTIF[i % len(MOTIF)], letter=False)
        for j, s in enumerate(sub):
            d.text((390, y + j * 68), s, font=F["rc"], fill=INK)
        y += 68 * len(sub) + 46
    if nxt:
        s = f"Next: {nxt}"
        tw = d.textlength(s, font=F["mid"])
        d.rounded_rectangle((W / 2 - tw / 2 - 40, 900, W / 2 + tw / 2 + 40, 990), 45, fill=ACCENT)
        d.text((W / 2 - tw / 2, 916), s, font=F["mid"], fill=(10, 20, 40))
    return im


def tiles_card(hl_marks=False, count=None):
    """The five tile colours with name, letter and mark."""
    im, d = new_canvas()
    text_center(d, (W / 2, 110), "Five colours", F["h1"], fill=GOLD)
    for i, c in enumerate(E.COLOURS):
        x = W / 2 + (i - 2) * 320
        tile(d, x, 400, 190, c, outline=HL if hl_marks else None)
        text_center(d, (x, 540), c, F["h2"], fill=INK)
        text_center(d, (x, 600), f"letter {E.LETTERS[c]}", F["b"], fill=GOLD if hl_marks else MUTED)
    if count:
        text_center(d, (W / 2, 780), count, F["h2"], fill=INK)
    return im


def factories_card(hl=None):
    """How many factory displays for 2, 3 and 4 players (numbers from the engine)."""
    im, d = new_canvas()
    text_center(d, (W / 2, 70), "Factory displays", F["h1"], fill=GOLD)
    for k, n in enumerate(sorted(E.FACTORIES)):
        y = 270 + k * 260
        on = hl == n
        d.rounded_rectangle((120, y - 110, W - 120, y + 110), 30, fill=PANEL,
                            outline=HL if on else (60, 80, 140), width=6 if on else 2)
        d.text((170, y - 60), f"{n} players", font=F["h1"], fill=INK)
        cnt = E.FACTORIES[n]
        for i in range(cnt):
            x = 640 + i * 132
            d.ellipse((x - 54, y - 54, x + 54, y + 54), fill=FACTORY, outline=FACTORY_RIM, width=4)
        text_center(d, (640 + cnt * 132 + 10, y - 34), f"= {cnt}", F["h2"], fill=GOLD)
    return im


def marker_card():
    """The starting player marker beside a tile, to show it is not a tile."""
    im, d = new_canvas()
    text_center(d, (W / 2, 110), "Starting player marker", F["h1"], fill=GOLD)
    tile(d, W / 2 - 220, 470, 220, E.MARKER)
    tile(d, W / 2 + 220, 470, 220, "blue")
    text_center(d, (W / 2 - 220, 620), "marker", F["h2"], fill=INK)
    text_center(d, (W / 2 + 220, 620), "a tile", F["h2"], fill=INK)
    text_center(d, (W / 2, 780), "The marker is not a tile.", F["h2"], fill=INK)
    return im
