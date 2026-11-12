"""Pillow renderer: draws the table (boards, bowl, bag, cards, coyote) and
text slides for the Spirits of the Wild explainer videos. Original simple
graphics only; no publisher artwork is used."""
from __future__ import annotations

import textwrap

from PIL import Image, ImageDraw, ImageFont

import engine as E

W, H = 1920, 1080
BG = (14, 22, 48)
PANEL = (26, 38, 78)
PANEL2 = (34, 50, 98)
INK = (234, 240, 255)
MUTED = (150, 165, 205)
ACCENT = (110, 200, 255)
GOLD = (255, 205, 90)
HL = (255, 120, 60)
COYOTE = (214, 110, 40)

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
    "h0": (96, "Bold"), "h1": (64, "Bold"), "h2": (44, "Bold"), "h3": (32, "Bold"),
    "b": (34, "Regular"), "s": (26, "Regular"), "sb": (26, "SemiBold"),
    "xs": (21, "Regular"), "xsb": (21, "SemiBold"), "cap": (36, "Medium"),
}.items()}

ANIMAL_LABEL = {
    "rabbit": ("RABBIT", "3 different colors", "6 pts for the set"),
    "turtle": ("TURTLE", "all one color", "1·3·6·9·14"),
    "salmon": ("SALMON", "all different colors", "1·2·4·6·9·13"),
    "owl": ("OWL", "same-color pairs", f"{E.OWL_POINTS} pts per pair"),
    "beaver": ("BEAVER", "triple + pair", "5 + 2, +7 bonus"),
}


def new_canvas():
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    # subtle star field
    import random
    r = random.Random(7)
    for _ in range(140):
        x, y = r.randrange(W), r.randrange(H)
        c = r.randrange(60, 130)
        d.point((x, y), fill=(c, c, c + 40))
    return im, d


# Layout registry: every stone drawn on a board or in the bowl is recorded
# with a stable key so animations can move stones between frames.
CTX = {"reg": {}, "hide": set(), "player": None, "coyote": None}
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
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill,
              outline=outline or (20, 20, 30), width=3 if not outline else 5)
    # highlight
    d.ellipse((cx - r * 0.55, cy - r * 0.6, cx - r * 0.05, cy - r * 0.15),
              fill=tuple(min(255, v + 45) for v in fill))
    if color == "clear":
        d.ellipse((cx - r * 0.35, cy - r * 0.35, cx + r * 0.35, cy + r * 0.35),
                  outline=(255, 255, 255), width=2)


def text_center(d, xy, s, f, fill=INK):
    x, y = xy
    w = d.textlength(s, font=f)
    d.text((x - w / 2, y), s, font=f, fill=fill)


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


# ------------------------------------------------------------------ board
def draw_section(d, x, y, w, h, board, animal, blocked=False, hl=False,
                 small=False):
    d.rounded_rectangle((x, y, x + w, y + h), 16, fill=PANEL,
                        outline=HL if hl else (60, 80, 140), width=5 if hl else 2)
    name, req, pts = ANIMAL_LABEL[animal]
    d.text((x + 14, y + 8), name, font=F["sb"], fill=ACCENT)
    d.text((x + 14, y + 40), req, font=F["xs"], fill=MUTED)
    d.text((x + 14, y + h - 32), pts, font=F["xsb"], fill=GOLD)
    sc = E.animal_score(board, animal)
    scs = f"{sc}"
    d.text((x + w - 14 - d.textlength(scs, font=F["h3"]), y + h - 42), scs,
           font=F["h3"], fill=INK)
    # bonus space
    bx, by, br = x + w - 34, y + 30, 20
    if board["bonus"][animal]:
        bstone(d, (animal, "bonus", 0), bx, by, br, "clear")
    else:
        d.ellipse((bx - br, by - br, bx + br, by + br), outline=(160, 200, 230), width=2)
        text_center(d, (bx, by - 12), "x2", F["xsb"], fill=(160, 200, 230))
    r = 19
    cy0 = y + 98
    s = board[animal]
    if animal in ("rabbit", "turtle"):
        n = 3 if animal == "rabbit" else 5
        for i in range(n):
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
        d.text((x + 34 + 3 * 48 - 10, cy0 - 12), "×3", font=F["xs"], fill=MUTED)
        d.text((x + 34 + 2 * 48 - 10, cy0 + 34), "×2", font=F["xs"], fill=MUTED)
    if blocked:
        d.rounded_rectangle((x, y, x + w, y + h), 16, outline=COYOTE, width=6)
        CTX["coyote"] = (x + w - 98, y + 6, 0.8)
        if "coyote" not in CTX["hide"]:
            draw_coyote(d, x + w - 98, y + 6, 0.8)
        text_center(d, (x + w / 2 + 40, y + h - 70), "BLOCKED", F["xsb"], fill=COYOTE)


def draw_coyote(d, x, y, s=1.0):
    """Tiny stylised coyote head (original drawing)."""
    pts = [(x, y + 40 * s), (x + 8 * s, y), (x + 20 * s, y + 22 * s),
           (x + 34 * s, y + 22 * s), (x + 46 * s, y), (x + 54 * s, y + 40 * s),
           (x + 27 * s, y + 66 * s)]
    d.polygon(pts, fill=COYOTE, outline=(40, 20, 10))
    d.ellipse((x + 14 * s, y + 30 * s, x + 21 * s, y + 37 * s), fill=(20, 10, 0))
    d.ellipse((x + 33 * s, y + 30 * s, x + 40 * s, y + 37 * s), fill=(20, 10, 0))
    d.polygon([(x + 23 * s, y + 52 * s), (x + 31 * s, y + 52 * s), (x + 27 * s, y + 58 * s)],
              fill=(20, 10, 0))


def draw_board(d, x, y, board, title, score, coyote_animal=None, hl=None,
               active=False):
    w = 1480
    d.rounded_rectangle((x, y, x + w, y + 270), 20, fill=(20, 30, 64),
                        outline=GOLD if active else (50, 66, 120), width=4 if active else 2)
    d.text((x + 18, y + 10), title, font=F["h3"], fill=GOLD if active else INK)
    sc = f"{score} pts"
    d.text((x + w - 18 - d.textlength(sc, font=F["h3"]), y + 10), sc,
           font=F["h3"], fill=INK)
    sw = (w - 36 - 4 * 12) / 5
    for i, a in enumerate(E.ANIMALS):
        draw_section(d, x + 18 + i * (sw + 12), y + 56, sw, 200, board, a,
                     blocked=(coyote_animal == a), hl=(hl and a in hl))


def draw_cards(d, x, y, cards, hl=None):
    cw, ch = 118, 120
    for i, c in enumerate(E.CARD_ORDER):
        cx = x + (i % 3) * (cw + 10)
        cy = y + (i // 3) * (ch + 10)
        up = cards[c]
        if up:
            d.rounded_rectangle((cx, cy, cx + cw, cy + ch), 10, fill=(120, 70, 50),
                                outline=HL if hl == c else (230, 200, 160),
                                width=6 if hl == c else 2)
            lines = CARD_SHORT[c]
            for j, ln in enumerate(lines[:5]):
                text_center(d, (cx + cw / 2, cy + 8 + j * 23), ln, F["xsb"], fill=(255, 240, 220))
        else:
            d.rounded_rectangle((cx, cy, cx + cw, cy + ch), 10, fill=(40, 30, 40),
                                outline=HL if hl == c else (90, 80, 100),
                                width=6 if hl == c else 2)
            if c in (E.TAKE1A, E.TAKE1B):
                # half a coyote on the back
                draw_coyote(d, cx + cw / 2 - 27, cy + 28, 1.0)
                d.rectangle((cx + (cw / 2 if c == E.TAKE1A else 0) + (0 if c == E.TAKE1A else 0),
                             cy + 20, cx + (cw if c == E.TAKE1A else cw / 2), cy + 100),
                            fill=(40, 30, 40))
                text_center(d, (cx + cw / 2, cy + ch - 26), "½ coyote", F["xs"], fill=MUTED)
            else:
                text_center(d, (cx + cw / 2, cy + ch / 2 - 12), "used", F["s"], fill=MUTED)


def draw_middle(d, y, st, hl=None, drawn=None):
    # bag
    d.rounded_rectangle((60, y, 360, y + 200), 30, fill=(70, 50, 40), outline=(150, 120, 90), width=3)
    text_center(d, (210, y + 16), "BAG", F["h3"], fill=(240, 220, 200))
    text_center(d, (210, y + 64), f"{st['bag']} stones", F["s"], fill=INK)
    co = st["clear_out"]
    text_center(d, (210, y + 104), "Spirit Stones out:", F["xs"], fill=MUTED)
    for i in range(5):
        stone(d, 130 + i * 40, y + 158, 15, "clear" if i < co else None)
    # bowl
    bx, by = 430, y
    d.ellipse((bx, by + 10, bx + 620, by + 200), fill=(205, 180, 140),
              outline=HL if hl == "bowl" else (120, 90, 60), width=6 if hl == "bowl" else 3)
    d.ellipse((bx + 25, by + 30, bx + 595, by + 180), fill=(230, 210, 175))
    text_center(d, (bx + 310, by - 30), "BOWL", F["sb"], fill=MUTED)
    bowl = st["bowl"]
    n = len(bowl)
    per_row = max(1, min(9, n))
    for i, c in enumerate(bowl):
        row, col = divmod(i, 9)
        rowsz = min(9, n - row * 9)
        cx = bx + 310 + (col - (rowsz - 1) / 2) * 56
        cy = by + 105 + (row - ((n - 1) // 9) / 2) * 52
        bstone(d, ("bowl", i), cx, cy, 23, c, outline=HL if drawn and i >= n - drawn else None,
               empty_ring=False)
    # spirit piles
    sx = 1110
    d.text((sx, y - 34), "SPIRIT POWER CARDS (top = available)", font=F["xsb"], fill=MUTED)
    for i, pile in enumerate(st["piles"]):
        px = sx + i * 250
        for k in range(min(3, len(pile)) - 1, -1, -1):
            off = k * 8
            d.rounded_rectangle((px + off, y + off, px + 220 + off, y + 190 + off), 14,
                                fill=(40, 60, 120) if k == 0 else (30, 44, 90),
                                outline=HL if (hl == pile[0] and k == 0) else (120, 160, 230),
                                width=6 if (hl == pile[0] and k == 0) else 2)
        if pile:
            text_center(d, (px + 110, y + 20), pile[0].upper(), F["h3"], fill=INK)
            for j, ln in enumerate(SPIRIT_SHORT[pile[0]]):
                text_center(d, (px + 110, y + 70 + j * 28), ln, F["xs"], fill=MUTED)
    # coyote parking
    if st["coyote"] is None:
        CTX["coyote"] = (1650, y + 60, 1.3)
        if "coyote" not in CTX["hide"]:
            draw_coyote(d, 1650, y + 60, 1.3)
        text_center(d, (1685, y + 160), "Coyote (aside)", F["xs"], fill=MUTED)


CARD_SHORT = {
    E.TAKE1A: ["TAKE", "ONE", "STONE"], E.TAKE1B: ["TAKE", "ONE", "STONE"],
    E.TAKE2: ["TAKE", "TWO", "STONES"], E.ADD2: ["ADD 2", "& TAKE 1"],
    E.ADD3: ["ADD 3", "& MOVE", "COYOTE"], E.SPIRIT: ["SPIRIT", "POWER &", "RECOVER"],
}

SPIRIT_SHORT = {
    "bear": ["Bowl → bag, refill", "same number,", "take 1"],
    "wolf": ["Add 4 to bowl,", "take 1"],
    "ram": ["Draw 2 from bag", "straight onto", "your board"],
    "eagle": ["Take 1,", "then take", "another turn"],
    "deer": ["Move 1 of yours", "to bowl,", "take 2"],
    "bison": ["Add 3, take 1,", "return 1 from", "bowl to bag"],
}


def caption(d, text, y=H - 128):
    d.rectangle((0, y, W, H), fill=(6, 10, 26))
    lines = wrap_text(d, text, F["cap"], W - 160)
    if len(lines) > 2:
        lines = lines[:2]
        lines[-1] = lines[-1].rstrip(".,;") + " …"
    for i, ln in enumerate(lines):
        text_center(d, (W / 2, y + 18 + i * 48 + (24 if len(lines) == 1 else 0)), ln, F["cap"])


def table(st, names=("Ana", "Ben"), cap=None, hl=None, label=None, hide=None):
    """Full table view from a snapshot. hl: dict with optional keys
    card=(player, card), sections=(player, [animals]), mid=..., drawn=n"""
    hl = hl or {}
    CTX["reg"], CTX["hide"], CTX["coyote"] = {}, set(hide or ()), None
    im, d = new_canvas()
    cur = st["current"]
    coy = st["coyote"]
    # Player 1 (top), Player 0 (bottom)
    for p, y in ((1, 14), (0, 552)):
        draw_cards(d, 14, y + 12, st["cards"][p],
                   hl=hl.get("card", (None, None))[1] if hl.get("card", (None,))[0] == p else None)
        secs = hl.get("sections")
        CTX["player"] = p
        draw_board(d, 426, y, st["boards"][p], names[p], st["scores"][p],
                   coyote_animal=coy[1] if coy and coy[0] == p else None,
                   hl=secs[1] if secs and secs[0] == p else None,
                   active=(cur == p))
    draw_middle(d, 330, st, hl=hl.get("mid"), drawn=hl.get("drawn"))
    if label:
        d.rounded_rectangle((14, 300, 400, 340), 10, fill=(6, 10, 26))
        d.text((26, 306), label, font=F["xsb"], fill=GOLD)
    if cap:
        caption(d, cap, y=H - 132 + 0)
    return im


# ------------------------------------------------------------------ slides
def slide(title, bullets=None, sub=None, cap=None, art=None):
    im, d = new_canvas()
    if bullets is None and sub is not None and art is None:
        text_center(d, (W / 2, 330), title, F["h0"], fill=INK)
        for i, ln in enumerate(wrap_text(d, sub, F["h2"], 1400)):
            text_center(d, (W / 2, 470 + i * 60), ln, F["h2"], fill=ACCENT)
    else:
        d.text((110, 80), title, font=F["h1"], fill=INK)
        d.line((110, 170, 520, 170), fill=ACCENT, width=6)
        y = 220
        if sub:
            for ln in wrap_text(d, sub, F["b"], 1700 if not art else 1000):
                d.text((110, y), ln, font=F["b"], fill=MUTED)
                y += 46
            y += 20
        maxw = 1700 if not art else 1000
        for b in bullets or []:
            lines = wrap_text(d, b, F["b"], maxw - 50)
            d.ellipse((112, y + 14, 128, y + 30), fill=GOLD)
            for ln in lines:
                d.text((150, y), ln, font=F["b"], fill=INK)
                y += 46
            y += 18
        if art:
            art(im, d)
    if cap:
        caption(d, cap)
    return im


def stones_row(colors, x, y, r=34, gap=84):
    def _art(im, d):
        for i, c in enumerate(colors):
            stone(d, x + i * gap, y, r, c)
    return _art


def section_art(board, animal, x=1180, y=250, scale_w=300, blocked=False, zoom=2.0):
    def _art(im, d):
        tile = Image.new("RGB", (scale_w + 4, 204), BG)
        draw_section(ImageDraw.Draw(tile), 2, 2, scale_w, 200, board, animal, blocked=blocked)
        tile = tile.resize((int(tile.width * zoom), int(tile.height * zoom)), Image.LANCZOS)
        im.paste(tile, (x, y))
    return _art


def compose(*arts):
    def _art(im, d):
        for a in arts:
            a(im, d)
    return _art
