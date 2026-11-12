"""Pillow renderer for the Spirits of the Wild explainer videos.

Everything is laid out in a 1920x1080 logical space but drawn at S x that
resolution (SDraw scales every call), so the video can zoom into any region
and stay sharp. Original simple graphics only; no publisher artwork."""
from __future__ import annotations

import random

from PIL import Image, ImageDraw, ImageFont

import engine as E

W, H = 1920, 1080
S = 2  # supersampling factor
BG = (14, 22, 48)
PANEL = (26, 38, 78)
INK = (234, 240, 255)
MUTED = (150, 165, 205)
ACCENT = (110, 200, 255)
GOLD = (255, 205, 90)
HL = (255, 120, 60)
COYOTE = (214, 110, 40)
CARD_UP = (120, 70, 50)
CARD_DOWN = (40, 30, 40)

STONE = {
    "green": (60, 185, 90), "yellow": (245, 210, 60), "blue": (60, 120, 230),
    "purple": (150, 80, 200), "white": (240, 240, 240), "red": (220, 60, 60),
    "clear": (200, 230, 245),
}

FONT_DIR = "/usr/share/fonts/opentype/inter/"


def font(size, weight="Regular"):
    try:
        return ImageFont.truetype(FONT_DIR + f"Inter-{weight}.otf", size)
    except OSError:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)


F = {k: font(s, w) for k, (s, w) in {
    "h0": (104, "Bold"), "h1": (64, "Bold"), "h2": (44, "Bold"), "h3": (32, "Bold"),
    "b": (34, "Regular"), "s": (26, "Regular"), "sb": (26, "SemiBold"),
    "xs": (21, "Regular"), "xsb": (21, "SemiBold"), "cap": (34, "SemiBold"),
}.items()}


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


def finish(im):
    """Downscale a full supersampled frame to 1920x1080."""
    return im.resize((W, H), Image.LANCZOS)


# ------------------------------------------------------------- primitives
# Layout registry: every stone drawn on a board or in the bowl is recorded
# with a stable key so animations can move stones between frames.
CTX = {"reg": {}, "hide": set(), "player": None, "coyote": None, "sec": {}}
BAG_XY = (210, 470)


def bstone(d, key, cx, cy, r, color, outline=None, empty_ring=True):
    full = (("b", CTX["player"]) + tuple(key)) if key[0] != "bowl" else tuple(key)
    if color is not None:
        CTX["reg"][full] = (cx, cy, r, color)
    if color is not None and full in CTX["hide"]:
        if empty_ring:
            stone(d, cx, cy, r, None)
        return
    stone(d, cx, cy, r, color, outline=outline)


def stone(d, cx, cy, r, color, outline=None):
    if color is None:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(80, 96, 140), width=3)
        return
    fill = STONE[color]
    d.ellipse((cx - r + 2, cy - r + 4, cx + r + 2, cy + r + 4), fill=(8, 12, 28))  # shadow
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill,
              outline=outline or (20, 20, 30), width=3 if not outline else 5)
    d.ellipse((cx - r * 0.55, cy - r * 0.6, cx - r * 0.05, cy - r * 0.15),
              fill=tuple(min(255, v + 45) for v in fill))
    if color == "clear":
        d.ellipse((cx - r * 0.35, cy - r * 0.35, cx + r * 0.35, cy + r * 0.35),
                  outline=(255, 255, 255), width=2)


def text_center(d, xy, s, f, fill=INK):
    d.text((xy[0] - d.textlength(s, font=f) / 2, xy[1]), s, font=f, fill=fill)


def wrap_text(d, s, f, maxw):
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_coyote(d, x, y, s=1.0):
    """Stylised coyote head (original drawing); (x, y) = top-left, 54s x 66s."""
    P = lambda a, b: (x + a * s, y + b * s)
    d.polygon([P(0, 40), P(8, 0), P(20, 22), P(34, 22), P(46, 0), P(54, 40), P(27, 66)],
              fill=COYOTE, outline=(40, 20, 10))
    d.polygon([P(10, 8), P(17, 22), P(12, 26)], fill=(120, 50, 20))
    d.polygon([P(44, 8), P(37, 22), P(42, 26)], fill=(120, 50, 20))
    d.polygon([P(18, 46), P(36, 46), P(27, 66)], fill=(245, 225, 200))
    d.ellipse((x + 14 * s, y + 30 * s, x + 21 * s, y + 37 * s), fill=(20, 10, 0))
    d.ellipse((x + 33 * s, y + 30 * s, x + 40 * s, y + 37 * s), fill=(20, 10, 0))
    d.polygon([P(23, 56), P(31, 56), P(27, 62)], fill=(20, 10, 0))


# ------------------------------------------------------------------ board
ANIMAL_LABEL = {
    "rabbit": ("RABBIT", "3 different colors", "set of 3 = 6"),
    "turtle": ("TURTLE", "all one color", "1·3·6·9·14"),
    "salmon": ("SALMON", "all different colors", "1·2·4·6·9·13"),
    "owl": ("OWL", "same-color pairs", f"{E.OWL_POINTS} per pair"),
    "beaver": ("BEAVER", "3 same + 2 same", "5 + 2, +7 bonus"),
}


def draw_section(d, x, y, w, h, board, animal, blocked=False, hl=False):
    CTX["sec"][(CTX["player"], animal)] = (x, y, w, h)
    d.rounded_rectangle((x, y, x + w, y + h), 16, fill=PANEL,
                        outline=HL if hl else (60, 80, 140), width=5 if hl else 2)
    name, req, pts = ANIMAL_LABEL[animal]
    d.text((x + 14, y + 8), name, font=F["sb"], fill=ACCENT)
    d.text((x + 14, y + 40), req, font=F["xs"], fill=MUTED)
    d.text((x + 14, y + h - 32), pts, font=F["xsb"], fill=GOLD)
    scs = str(E.animal_score(board, animal))
    d.text((x + w - 14 - d.textlength(scs, font=F["h3"]), y + h - 42), scs, font=F["h3"], fill=INK)
    bx, by, br = x + w - 34, y + 30, 20
    if board["bonus"][animal]:
        bstone(d, (animal, "bonus", 0), bx, by, br, "clear")
    else:
        d.ellipse((bx - br, by - br, bx + br, by + br), outline=(160, 200, 230), width=2)
        text_center(d, (bx, by - 12), "x2", F["xsb"], fill=(160, 200, 230))
    r, cy0, s = 19, y + 98, board[animal]
    if animal in ("rabbit", "turtle"):
        for i in range(3 if animal == "rabbit" else 5):
            bstone(d, (animal, "s", i), x + 34 + i * 48, cy0, r, s[i] if i < len(s) else None)
    elif animal == "salmon":
        for i in range(6):
            bstone(d, (animal, "s", i), x + 34 + (i % 3) * 48, cy0 + (i // 3) * 46, r,
                   s[i] if i < len(s) else None)
    elif animal == "owl":
        for i in range(E.OWL_PAIRS):
            px = x + 32 + i * 88
            pr = s[i] if i < len(s) else []
            d.rounded_rectangle((px - 22, cy0 - 22, px + 62, cy0 + 22), 22,
                                outline=(70, 90, 150), width=2)
            bstone(d, (animal, f"p{i}", 0), px, cy0, 17, pr[0] if len(pr) > 0 else None)
            bstone(d, (animal, f"p{i}", 1), px + 40, cy0, 17, pr[1] if len(pr) > 1 else None)
    elif animal == "beaver":
        t, p = s["triple"], s["pair"]
        for i in range(3):
            bstone(d, (animal, "triple", i), x + 34 + i * 48, cy0, r, t[i] if i < len(t) else None)
        for i in range(2):
            bstone(d, (animal, "pair", i), x + 34 + i * 48, cy0 + 46, r, p[i] if i < len(p) else None)
    if blocked:
        d.veil((x + 3, y + 62, x + w - 3, y + h - 3), alpha=165)
        cx, cy = x + w / 2 - 40, y + 66
        CTX["coyote"] = (cx, cy, 1.45)
        if "coyote" not in CTX["hide"]:
            draw_coyote(d, cx, cy, 1.45)
        d.rounded_rectangle((x + 3, y + 3, x + w - 3, y + h - 3), 14, outline=COYOTE, width=5)


def draw_board(d, x, y, board, title, score, coyote_animal=None, hl=None, active=False):
    w = 1480
    d.rounded_rectangle((x, y, x + w, y + 270), 20, fill=(20, 30, 64),
                        outline=GOLD if active else (50, 66, 120), width=4 if active else 2)
    d.text((x + 18, y + 10), title, font=F["h3"], fill=GOLD if active else INK)
    sc = f"{score} pts"
    d.text((x + w - 18 - d.textlength(sc, font=F["h3"]), y + 10), sc, font=F["h3"], fill=INK)
    sw = (w - 36 - 4 * 12) / 5
    for i, a in enumerate(E.ANIMALS):
        draw_section(d, x + 18 + i * (sw + 12), y + 56, sw, 200, board, a,
                     blocked=(coyote_animal == a), hl=bool(hl and a in hl))


CARD_SHORT = {
    E.TAKE1A: ["TAKE", "ONE", "STONE"], E.TAKE1B: ["TAKE", "ONE", "STONE"],
    E.TAKE2: ["TAKE", "TWO", "STONES"], E.ADD2: ["ADD 2", "& TAKE 1"],
    E.ADD3: ["ADD 3", "& MOVE", "COYOTE"], E.SPIRIT: ["SPIRIT", "POWER &", "RECOVER"],
}
CW, CH, CG = 118, 120, 10


def card_rect(x, y, i):
    cx, cy = x + (i % 3) * (CW + CG), y + (i // 3) * (CH + CG)
    return cx, cy, cx + CW, cy + CH


def draw_cards(d, x, y, cards, hl=None):
    # face-down backs first, then the coyote across the two Take One backs,
    # then face-up cards on top, so each back shows "its" half of the coyote
    order = sorted(range(6), key=lambda i: cards[E.CARD_ORDER[i]])
    drew_coy = False
    for i in order:
        c = E.CARD_ORDER[i]
        x0, y0, x1, y1 = card_rect(x, y, i)
        if cards[c]:
            if not drew_coy:
                _coyote_backs(d, x, y, cards)
                drew_coy = True
            d.rounded_rectangle((x0, y0, x1, y1), 10, fill=CARD_UP,
                                outline=HL if hl == c else (230, 200, 160), width=6 if hl == c else 2)
            for j, ln in enumerate(CARD_SHORT[c]):
                text_center(d, ((x0 + x1) / 2, y0 + 22 + j * 26), ln, F["xsb"], fill=(255, 240, 220))
        else:
            d.rounded_rectangle((x0, y0, x1, y1), 10, fill=CARD_DOWN,
                                outline=HL if hl == c else (90, 80, 100), width=6 if hl == c else 2)
            if c not in (E.TAKE1A, E.TAKE1B):
                text_center(d, ((x0 + x1) / 2, y0 + CH / 2 - 14), "used", F["s"], fill=MUTED)
    if not drew_coy:
        _coyote_backs(d, x, y, cards)


def _coyote_backs(d, x, y, cards):
    if cards[E.TAKE1A] and cards[E.TAKE1B]:
        return
    s = 1.6
    cx = x + CW + CG / 2 - 27 * s
    draw_coyote(d, cx, y + 8, s)
    # the gap between the cards stays background-coloured
    d.rectangle((x + CW + 1, y, x + CW + CG - 1, y + CH), fill=BG)


SPIRIT_SHORT = {
    "bear": ["Bowl → bag, refill", "same number,", "take 1"],
    "wolf": ["Add 4 to bowl,", "take 1"],
    "ram": ["Draw 2 from bag", "straight onto", "your board"],
    "eagle": ["Take 1,", "then take", "another turn"],
    "deer": ["Move 1 of yours", "to bowl,", "take 2"],
    "bison": ["Add 3, take 1,", "return 1 from", "bowl to bag"],
}


def draw_middle(d, y, st, hl=None, drawn=None):
    d.rounded_rectangle((60, y, 360, y + 200), 30, fill=(70, 50, 40), outline=(150, 120, 90), width=3)
    text_center(d, (210, y + 16), "BAG", F["h3"], fill=(240, 220, 200))
    text_center(d, (210, y + 64), f"{st['bag']} stones", F["s"], fill=INK)
    co = st["clear_out"]
    text_center(d, (210, y + 104), "Spirit Stones out:" if co <= 5 else f"Spirit Stones out: {co}",
                F["xs"], fill=HL if hl == "meter" else MUTED)
    for i in range(5):
        stone(d, 130 + i * 40, y + 158, 15, "clear" if i < co else None)
    if hl == "meter":
        d.rounded_rectangle((100, y + 134, 320, y + 182), 20, outline=HL, width=4)
    bx = 430
    d.ellipse((bx, y + 10, bx + 620, y + 200), fill=(205, 180, 140),
              outline=HL if hl == "bowl" else (120, 90, 60), width=6 if hl == "bowl" else 3)
    d.ellipse((bx + 25, y + 30, bx + 595, y + 180), fill=(230, 210, 175))
    text_center(d, (bx + 310, y - 30), "BOWL", F["sb"], fill=MUTED)
    bowl, n = st["bowl"], len(st["bowl"])
    for i, c in enumerate(bowl):
        row, col = divmod(i, 9)
        rowsz = min(9, n - row * 9)
        cx = bx + 310 + (col - (rowsz - 1) / 2) * 56
        cy = y + 105 + (row - ((n - 1) // 9) / 2) * 52
        bstone(d, ("bowl", i), cx, cy, 23, c, outline=HL if drawn and i >= n - drawn else None,
               empty_ring=False)
    sx = 1110
    d.text((sx, y - 34), "SPIRIT POWER CARDS", font=F["xsb"], fill=MUTED)
    for i, pile in enumerate(st["piles"]):
        px = sx + i * 250
        for k in range(min(3, len(pile)) - 1, -1, -1):
            off = k * 8
            on = hl == pile[0] and k == 0
            d.rounded_rectangle((px + off, y + off, px + 220 + off, y + 190 + off), 14,
                                fill=(40, 60, 120) if k == 0 else (30, 44, 90),
                                outline=HL if on else (120, 160, 230), width=6 if on else 2)
        if pile:
            text_center(d, (px + 110, y + 20), pile[0].upper(), F["h3"], fill=INK)
            for j, ln in enumerate(SPIRIT_SHORT[pile[0]]):
                text_center(d, (px + 110, y + 70 + j * 28), ln, F["xs"], fill=MUTED)
    if st["coyote"] is None:
        CTX["coyote"] = (1650, y + 50, 1.3)
        if "coyote" not in CTX["hide"]:
            draw_coyote(d, 1650, y + 50, 1.3)
        text_center(d, (1685, y + 150), "Coyote", F["xs"], fill=MUTED)


def info_bar(d, left=None, right=None):
    y = H - 104
    d.rectangle((0, y, W, H), fill=(6, 10, 26))
    d.line((0, y, W, y), fill=(40, 56, 100), width=2)
    if left:
        lines = wrap_text(d, left, F["cap"], 1300 if right else 1780)[:2]
        for i, ln in enumerate(lines):
            d.text((60, y + (30 if len(lines) == 1 else 10) + i * 44), ln, font=F["cap"], fill=GOLD)
    if right:
        d.text((W - 60 - d.textlength(right, font=F["cap"]), y + 30), right, font=F["cap"], fill=INK)


def pops(d, deltas):
    for (p, a), n in deltas.items():
        if not n or (p, a) not in CTX["sec"]:
            continue
        x, y, w, h = CTX["sec"][(p, a)]
        s = f"+{n}" if n > 0 else str(n)
        tw = d.textlength(s, font=F["h2"])
        bx, by = x + w / 2 - tw / 2 - 18, y - 30
        d.rounded_rectangle((bx, by, bx + tw + 36, by + 62), 31, fill=GOLD if n > 0 else HL,
                            outline=(60, 40, 0), width=3)
        d.text((bx + 18, by + 4), s, font=F["h2"], fill=(30, 20, 0))


def banner(d, text, sub=None):
    d.veil((0, 380, W, 700), alpha=215, radius=0)
    text_center(d, (W / 2, 420), text, F["h0"], fill=GOLD)
    if sub:
        text_center(d, (W / 2, 560), sub, F["h2"], fill=INK)


def table(st, names=("Ana", "Ben"), hl=None, hide=None, bar=None, deltas=None, ban=None,
          ticker=True):
    """Full table view (supersampled). hl keys: card=(p, card), sections=(p, [animals]),
    mid='bowl'|'meter'|<spirit>, drawn=n."""
    hl = hl or {}
    CTX.update(reg={}, hide=set(hide or ()), coyote=None, sec={})
    im, d = new_canvas()
    coy = st["coyote"]
    for p, y in ((1, 14), (0, 552)):
        CTX["player"] = p
        card = hl.get("card")
        draw_cards(d, 14, y + 12, st["cards"][p], hl=card[1] if card and card[0] == p else None)
        secs = hl.get("sections")
        draw_board(d, 426, y, st["boards"][p], names[p], st["scores"][p],
                   coyote_animal=coy[1] if coy and coy[0] == p else None,
                   hl=secs[1] if secs and secs[0] == p else None, active=(st["current"] == p))
    draw_middle(d, 330, st, hl=hl.get("mid"), drawn=hl.get("drawn"))
    if deltas:
        pops(d, deltas)
    right = f"{names[0]} {st['scores'][0]}  ·  {names[1]} {st['scores'][1]}" if ticker else None
    info_bar(d, bar, right)
    if ban:
        banner(d, *ban)
    return im


# ------------------------------------------------------------------ cards
def title_card(title, sub=None, kicker=None):
    im, d = new_canvas()
    if kicker:
        text_center(d, (W / 2, 300), kicker.upper(), F["sb"], fill=ACCENT)
    text_center(d, (W / 2, 360), title, F["h0"], fill=INK)
    if sub:
        for i, ln in enumerate(wrap_text(d, sub, F["h2"], 1400)):
            text_center(d, (W / 2, 520 + i * 60), ln, F["h2"], fill=GOLD)
    # five stones as a motif
    for i, c in enumerate(["green", "yellow", "blue", "purple", "red"]):
        stone(d, W / 2 + (i - 2) * 90, 760, 30, c)
    return im


def spirit_card(name, lines, x, y, w=420, h=520, hl=False):
    def _draw(d):
        d.rounded_rectangle((x, y, x + w, y + h), 26, fill=(40, 60, 120),
                            outline=HL if hl else (120, 160, 230), width=6 if hl else 3)
        text_center(d, (x + w / 2, y + 40), name.upper(), F["h1"])
        yy = y + 160
        for ln in lines:
            for sub in wrap_text(d, ln, F["b"], w - 60):
                text_center(d, (x + w / 2, yy), sub, F["b"], fill=INK)
                yy += 46
            yy += 18
    return _draw


def spirit_grid(names_lines, hl=None, bar=None):
    im, d = new_canvas()
    for i, (k, (nm, lines)) in enumerate(names_lines.items()):
        x = 90 + (i % 3) * 590
        y = 60 + (i // 3) * 450
        spirit_card(nm, lines, x, y, w=560, h=420, hl=(hl == k))(d)
    info_bar(d, bar)
    return im
