"""Animated transitions between two Azul table snapshots, plus clip assembly
(Kokoro TTS narration, ambient music, SFX, ffmpeg encode, SRT).

Same techniques as tools/sotw/anim.py: frames are drawn at 2x, cropped by a moving
camera, then captions / arrows / spotlights / pop-ups are drawn in screen space so
they stay large at any zoom. Narration is voiced one sentence at a time and every
segment's video and audio are cut to the same whole number of frames."""
from __future__ import annotations

import hashlib
import math
import multiprocessing as mp
import os
import re
import subprocess
import wave
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import importlib.util
import sys

_HERE = Path(__file__).resolve().parent


def _load(name):
    full = f"azul_{name}"
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(full, _HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


R = _load("render")
E = R.E

FPS = 30
ANIM_FRAMES = 18          # 0.6 s per moving tile
STAGGER = 5               # frames between successive tiles
FAST_ANIM, FAST_STAGGER = 10, 2   # fast-forwarded turns in the sample game
CAM_FRAMES = 18
FULL = (0, 0, 1920)       # camera rect: x, y, width (height = width * 9/16)
VOICE_DIR = _HERE.parent / "voices"
VOICE = os.environ.get("AZUL_VOICE", "af_heart")
SPEED = float(os.environ.get("AZUL_SPEED", "0.9"))
SR = 24000
GAP = 0.32                # silence between sentences (each sentence is voiced separately)
FADE_FRAMES = 14          # crossfade for reveals and cards
OV_FRAMES = 10            # fade-in of captions, arrows, spotlights and pop-ups


# ================================================================ diffing
def _layout(st, tk):
    R.table(st, **{k: v for k, v in tk.items() if k in ("names", "show")})
    return dict(R.CTX["reg"])


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


DEST_ORDER = {"line": 0, "floor": 1, "m": 1, "wall": 2, "c": 3, "lid": 4, "f": 5}


def _kind(key):
    if key[0] == "p":
        return key[2]
    return key[0]


def plan(pre, post, tk):
    """Return (movers, hide) to animate pre -> post.

    movers: (colour, (x, y, size) from, (x, y, size) to, order, kind). Tiles are
    matched by colour: each new tile flies from the nearest vanished tile of the same
    colour; new tiles with no source come from the bag (or tk['src_xy']); vanished
    tiles with no destination go to the box lid (or, from the lid, into the bag).
    The centre of the table and the box lid are pools: their remaining tiles slide."""
    rpre, rpost = _layout(pre, tk), _layout(post, tk)
    movers, hide = [], set()
    pooled = lambda k: k[0] in ("c", "lid")
    gone = [k for k in rpre if not pooled(k) and k != ("m",)
            and (k not in rpost or rpost[k][3] != rpre[k][3])]
    new = [k for k in rpost if not pooled(k) and k != ("m",)
           and (k not in rpre or rpre[k][3] != rpost[k][3])]
    for pool in ("c", "lid"):
        pk = sorted((k for k in rpre if k[0] == pool), key=lambda k: k[1])
        qk = sorted((k for k in rpost if k[0] == pool), key=lambda k: k[1])
        avail = {}
        for k in pk:
            avail.setdefault(rpre[k][3], []).append(k)
        # keep the first tiles of each colour; extra pre tiles vanish, extra post tiles arrive
        for k in qk:
            c = rpost[k][3]
            if avail.get(c):
                src = avail[c].pop(0)
                if _dist(rpre[src], rpost[k]) > 0.5:
                    movers.append((c, rpre[src][:3], rpost[k][:3], 0, "shift"))
                    hide.add(k)
            else:
                new.append(k)
        for ks in avail.values():
            gone += ks
    if ("m",) in rpre and ("m",) in rpost and _dist(rpre[("m",)], rpost[("m",)]) > 0.5:
        movers.append((E.MARKER, rpre[("m",)][:3], rpost[("m",)][:3], 1, "marker"))
        hide.add(("m",))
    elif ("m",) in rpost and ("m",) not in rpre:
        hide.add(("m",))
        x, y, s, _ = rpost[("m",)]
        movers.append((E.MARKER, (x, y - 60, s), (x, y, s), 1, "marker"))
    src_xy = tk.get("src_xy")
    order = 1 + bool(movers and movers[-1][4] == "marker")
    for k in sorted(new, key=lambda k: (DEST_ORDER.get(_kind(k), 9), k[1:] if k[0] != "p" else k)):
        c = rpost[k][3]
        cands = [g for g in gone if rpre[g][3] == c]
        if cands:
            src = min(cands, key=lambda g: _dist(rpre[g], rpost[k]))
            gone.remove(src)
            frm = rpre[src][:3]
        elif src_xy:
            frm = (src_xy[0], src_xy[1], rpost[k][2])
        else:
            frm = (*R.BAG_XY, rpost[k][2])
        movers.append((c, frm, rpost[k][:3], order, _kind(k)))
        hide.add(k)
        order += 1
    for g in sorted(gone, key=lambda g: (DEST_ORDER.get(_kind(g), 9), g[1:] if g[0] != "p" else g)):
        x, y, s, c = rpre[g]
        if g[0] == "lid":
            movers.append((c, (x, y, s), (*R.BAG_XY, s), order, "bag"))
        else:
            movers.append((c, (x, y, s), (*R.LID_XY, R.LT), order, "tolid"))
        order += 1
    return movers, hide


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


SFX_FOR = {"wall": "chime", "floor": "thud", "line": "click", "c": "click", "f": "click",
           "marker": "click", "tolid": "click", "bag": None, "lid": "click", "shift": None}


def anim_frames(pre, post, tk, fast=False):
    """([(supersampled image, n_frames)], [(frame, sfx)]). Last image = settled."""
    movers, hide = plan(pre, post, tk)
    final = R.table(post, **tk)
    if not movers:
        return [(final, 1)], []
    base = R.table(post, **{**tk, "hide": hide})
    af, sg = (FAST_ANIM, FAST_STAGGER) if fast else (ANIM_FRAMES, STAGGER)
    # tiles going to the same kind of place within one step move together in a wave
    nsteps = max(m[3] for m in movers) * sg + af
    sfx, seen = [], set()
    for c, _, _, o, kind in movers:
        s = SFX_FOR.get(kind)
        fr = o * sg + af - 1
        if s and (fr // 4, s) not in seen:
            seen.add((fr // 4, s))
            sfx.append((fr, s))
    out = []
    for f in range(0, nsteps, 2):
        im = base.copy()
        d = R.SDraw(im)
        for c, (x0, y0, s0), (x1, y1, s1), o, kind in movers:
            t = ease((f - o * sg) / af)
            if kind in ("tolid", "bag") and t >= 1:
                continue
            lift = math.sin(math.pi * t) * (0 if kind == "shift" else 60)
            grow = math.sin(math.pi * t) * (0 if kind == "shift" else 8)
            R.tile(d, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t - lift, s0 + (s1 - s0) * t + grow, c)
        out.append((im, 2))
    out.append((final, 1))
    return out, sfx


# ==================================================================== TTS
_k = None


def tts(text, cache_dir):
    """Return mono float32 numpy audio at SR (cached by voice, speed and text)."""
    global _k
    h = hashlib.sha1(f"{VOICE}|{SPEED}|{text}".encode()).hexdigest()[:16]
    p = Path(cache_dir) / f"{h}.npy"
    if p.exists():
        return np.load(p)
    if _k is None:
        from kokoro_onnx import Kokoro
        _k = Kokoro(str(VOICE_DIR / "kokoro-v1.0.int8.onnx"), str(VOICE_DIR / "voices-v1.0.bin"))
    lang = "en-gb" if VOICE.startswith("b") else "en-us"
    a, sr = _k.create(spoken(text), voice=VOICE, speed=SPEED, lang=lang)
    assert sr == SR
    a = a.astype(np.float32)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.save(p, a)
    return a


def spoken(text):
    """Small pronunciation fixes for the TTS only (captions keep the written form)."""
    return text.replace("Azul", "Ah-zool")


# ================================================================== music
def ambient(seconds, seed=3):
    """Soft synthesized pad (original), Dm-Bb-F-C, very low in the mix."""
    n = int(round(seconds * SR))
    t = np.arange(n) / SR
    chords = [[146.83, 174.61, 220.0], [116.54, 146.83, 174.61],
              [174.61, 220.0, 261.63], [130.81, 164.81, 196.0]]
    seg = 6.0
    out = np.zeros(n, np.float32)
    for i in range(int(seconds // seg) + 2):
        a, b = int(i * seg * SR), int((i + 1) * seg * SR + 1.5 * SR)
        a, b = max(0, a), min(n, b)
        if a >= b:
            continue
        tt = t[a:b] - i * seg
        env = np.minimum(1, tt / 1.5) * np.clip((seg + 1.5 - tt) / 1.5, 0, 1)
        sig = np.zeros(b - a)
        for f in chords[i % 4]:
            sig += np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.003 * tt + 1)
        sig += 0.5 * np.sin(2 * np.pi * chords[i % 4][0] / 2 * tt)
        out[a:b] += (sig * env).astype(np.float32)
    out /= max(1e-6, np.abs(out).max())
    fade = np.minimum(1, np.minimum(t / 2, (seconds - t) / 3))
    return (out * fade).astype(np.float32)


# ==================================================================== SFX
def _sfx_bank():
    t = lambda d: np.arange(int(d * SR)) / SR
    rng = np.random.default_rng(1)
    bank = {}
    tt = t(0.08)
    n = rng.standard_normal(len(tt))
    # a ceramic "tock": short high partials + a little noise
    bank["click"] = ((0.45 * np.sin(2 * np.pi * 1850 * tt) + 0.3 * np.sin(2 * np.pi * 3100 * tt)
                      + 0.25 * np.diff(n, prepend=0)) * np.exp(-tt * 70) * 0.35)
    tt = t(1.2)
    bank["chime"] = sum(np.sin(2 * np.pi * f * tt) * np.exp(-tt * k)
                        for f, k in ((1046.5, 3), (1568.0, 4), (2093.0, 5))) * 0.12
    tt = t(0.35)
    f = 220 - 90 * tt / 0.35
    bank["thud"] = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 12) * 0.35
    tt = t(0.22)
    n = rng.standard_normal(len(tt))
    bank["card"] = np.convolve(n, np.ones(12) / 12, mode="same") * np.sin(np.pi * tt / 0.22) * 0.25
    notes, out = (523.25, 659.25, 783.99, 1046.5), []
    for i, fr in enumerate(notes):
        tt = t(0.5 if i == 3 else 0.14)
        out.append(np.sin(2 * np.pi * fr * tt) * np.exp(-tt * (3 if i == 3 else 8)) * 0.22)
    bank["win"] = np.concatenate(out)
    tt = t(0.45)
    bank["minus"] = (np.sin(2 * np.pi * 330 * tt) * (tt < 0.18) * np.exp(-tt * 8)
                     + np.sin(2 * np.pi * 247 * tt) * (tt >= 0.18) * np.exp(-(tt - 0.18) * 8)) * 0.18
    return {k: v.astype(np.float32) for k, v in bank.items()}


SFX_NAMES = ("click", "chime", "thud", "card", "win", "minus")


# =============================================================== overlays
def _crop(im, rect):
    x, y, w = rect
    h = w * 9 / 16
    s = R.S
    return im.resize((R.W, R.H), Image.LANCZOS, box=(x * s, y * s, (x + w) * s, (y + h) * s))


def _screen(rect, x, y):
    cx, cy, cw = rect
    k = R.W / cw
    return (x - cx) * k, (y - cy) * k


def _pill(d, box, fill, outline=None, width=0, r=None):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, r if r is not None else (y1 - y0) / 2, fill=fill, outline=outline,
                        width=width)


def _alpha(layer, a):
    if a < 1:
        al = layer.getchannel("A").point(lambda v: int(v * a))
        layer.putalpha(al)
    return layer


def _cap_fonts(ov):
    """Caption fonts: the key word in the display serif, the sub-line in the body serif;
    both shrink a little if a long caption would not fit the screen."""
    cap = ov["cap"]
    title, sub = (cap, None) if isinstance(cap, str) else cap
    d = R.SDraw(Image.new("RGBA", (8, 8)), 1)
    maxw = R.W - 200
    ft = R.fit_font(d, title, R.display, R.F["big"].size, maxw, 48)
    fs = R.fit_font(d, sub, lambda z: R.font(z, "Bold"), R.F["mid"].size, maxw, 30) if sub else None
    return title, sub, ft, fs


def caption_box(ov):
    """Screen-space box (x0, y0, x1, y1) of the key-word caption."""
    title, sub, ft, fs = _cap_fonts(ov)
    d = R.SDraw(Image.new("RGBA", (8, 8)), 1)
    w = max(d.textlength(title, ft), d.textlength(sub, fs) if sub else 0) + 120
    h = 120 + (64 if sub else 0)
    pos = ov.get("cap_pos", "top")
    y0 = 28 if pos == "top" else (R.H - h) / 2 - 20 if pos == "mid" else R.H - h - 34
    if ov.get("bar") or ov.get("score"):
        y0 = min(y0, R.H - 78 - h - 16)
    x0 = (R.W - w) / 2
    return (x0, y0, x0 + w, y0 + h)


def _draw_caption(ov):
    """A cream plaque in a deep-blue frame with a gold inner line (the cards' style)."""
    title, sub, ft, fs = _cap_fonts(ov)
    layer = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
    d = R.SDraw(layer, 1)
    x0, y0, x1, y1 = caption_box(ov)
    d.rounded_rectangle((x0 + 4, y0 + 6, x1 + 4, y1 + 6), 30, fill=(60, 40, 20, 70))
    R.frame(d, (x0, y0, x1, y1), 30, fill=R.PAPER + (246,), edge=R.NAVY + (255,),
            line=R.GOLD + (255,), width=6)
    R.text_mid(d, R.W / 2, y0 + 62, title, ft, fill=R.NAVY, anchor="m")
    if sub:
        R.text_mid(d, R.W / 2, y0 + 140, sub, fs, fill=R.RED, anchor="m")
    return layer


ARROW = R.HL                  # rulebook-style dark red arrows


def _draw_arrows(arrows, rect):
    layer = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
    d = R.SDraw(layer, 1)
    f = R.F["mid"]
    halo, ink = R.PAPER + (255,), ARROW + (255,)
    for x, y, label, side in arrows:
        tx, ty = _screen(rect, x, y)
        dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[side]
        dist = 150
        lx, ly = tx + dx * dist, ty + dy * dist
        tw = d.textlength(label, f)
        bw, bh = tw + 56, 76
        bx0, by0 = lx - bw / 2 + dx * bw / 2, ly - bh / 2 + dy * bh / 2
        bx0 = max(16, min(R.W - bw - 16, bx0))
        by0 = max(16, min(R.H - bh - 16, by0))
        sx = bx0 + bw / 2 if dx == 0 else (bx0 if dx > 0 else bx0 + bw)
        sy = by0 + bh / 2 if dy == 0 else (by0 if dy > 0 else by0 + bh)
        ex, ey = tx + dx * 26, ty + dy * 26
        ang = math.atan2(ey - sy, ex - sx)
        hx, hy = tx + dx * 8, ty + dy * 8
        pts = [(hx, hy)] + [(hx - 40 * math.cos(ang + s), hy - 40 * math.sin(ang + s)) for s in (0.5, -0.5)]
        # a cream halo first, so the arrow reads on tiles and on parchment alike
        d.line((sx, sy, ex, ey), fill=halo, width=17)
        hp = [(hx + 7 * math.cos(ang), hy + 7 * math.sin(ang))] + [
            (hx - 50 * math.cos(ang + s), hy - 50 * math.sin(ang + s)) for s in (0.56, -0.56)]
        d.polygon(hp, fill=halo)
        d.line((sx, sy, ex, ey), fill=ink, width=9)
        d.polygon(pts, fill=ink)
        _pill(d, (bx0, by0, bx0 + bw, by0 + bh), ink, outline=halo, width=4)
        R.text_mid(d, bx0 + bw / 2, by0 + bh / 2, label, f, fill=R.PAPER, anchor="m")
    return layer


def _draw_focus(rects, rect):
    """Spotlight: wash everything else with pale parchment; frame the focus in dark red."""
    layer = Image.new("RGBA", (R.W, R.H), R.PAPER + (178,))
    d = ImageDraw.Draw(layer)
    boxes = []
    for x0, y0, x1, y1 in rects:
        a, b = _screen(rect, x0, y0)
        c, e = _screen(rect, x1, y1)
        boxes.append((a, b, c, e))
        d.rounded_rectangle((a, b, c, e), 18, fill=(0, 0, 0, 0))
    for box in boxes:
        d.rounded_rectangle(box, 18, outline=R.HL + (255,), width=6)
    return layer


def _pop_font(n):
    """Big pop-ups; a little smaller when several share the screen."""
    return (_POP_BIG, 86) if n <= 2 else (_POP_SMALL, 62)


_POP_BIG, _POP_SMALL = R.font(68, "Bold"), R.font(48, "Bold")


def pop_box(pop, rect, avoid=None, n=1):
    """Screen box of a point pop-up. pop = (x, y, text, mode): mode 'tile' = (x, y) is a
    tile centre, the pill sits above the tile, or below it if `avoid` (a caption box)
    is in the way; mode 'at' = the pill is centred on (x, y)."""
    x, y, s, mode = pop
    sx, sy = _screen(rect, x, y)
    d = R.SDraw(Image.new("RGBA", (8, 8)), 1)
    f, bh = _pop_font(n)
    bw = d.textlength(s, f) + (48 if bh > 70 else 32)
    half = R.T / 2 * R.W / rect[2]
    bx0 = max(12, min(R.W - bw - 12, sx - bw / 2))
    if mode == "at":
        by0 = sy - bh / 2
    else:
        by0 = sy - half - 10 - bh
        if by0 < 12 or (avoid and by0 < avoid[3] and by0 + bh > avoid[1]
                        and bx0 < avoid[2] and bx0 + bw > avoid[0]):
            by0 = sy + half + 10
    by0 = max(12, min(R.H - bh - 12, by0))
    return (bx0, by0, bx0 + bw, by0 + bh)


POP_PLUS = (0xF1, 0xB8, 0x52)  # ochre, like the score track's number plaques
POP_INK = (0x3A, 0x22, 0x08)


def _draw_pops(pops, rect, avoid=None):
    """Point pop-ups ('+3', '−2'), big at any zoom."""
    layer = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
    d = R.SDraw(layer, 1)
    f, bh = _pop_font(len(pops))
    for pop in pops:
        s = pop[2]
        bx0, by0, bx1, by1 = pop_box(pop, rect, avoid, len(pops))
        neg = s.startswith("−") or s.startswith("-")
        d.rounded_rectangle((bx0 + 3, by0 + 5, bx1 + 3, by1 + 5), bh / 2, fill=(60, 40, 20, 80))
        _pill(d, (bx0, by0, bx1, by1), (R.HL if neg else POP_PLUS) + (255,),
              outline=(R.PAPER if neg else R.NAVY) + (255,), width=4)
        R.text_mid(d, (bx0 + bx1) / 2, (by0 + by1) / 2, s, f,
                   fill=R.PAPER if neg else POP_INK, anchor="m")
    return layer


def _draw_badges(badges, rect):
    """Small numbered circles on tiles (counting across / down)."""
    layer = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
    d = R.SDraw(layer, 1)
    k = R.W / rect[2]
    rad = max(22, 17 * k)
    f = R.font(int(rad * 1.25), "Bold")
    for x, y, s, kind in badges:
        sx, sy = _screen(rect, x, y)
        fill = POP_PLUS + (255,) if kind == "across" else R.SKY + (255,)
        d.ellipse((sx - rad, sy - rad, sx + rad, sy + rad), fill=fill, outline=R.NAVY + (255,), width=3)
        R.text_mid(d, sx, sy, s, f, fill=R.INK, anchor="m")
    return layer


def _draw_bar(ov):
    """Bottom bar in deep azulejo blue with a gold edge."""
    layer = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
    d = R.SDraw(layer, 1)
    y = R.H - 78
    d.rectangle((0, y, R.W, R.H), fill=R.NAVY + (240,))
    d.line((0, y + 2, R.W, y + 2), fill=R.GOLD + (255,), width=4)
    f = R.F["cap"]
    if ov.get("bar"):
        R.text_mid(d, 48, y + 41, ov["bar"], f, fill=R.GOLD_LIGHT)
    if ov.get("score"):
        R.text_mid(d, R.W - 48, y + 41, ov["score"], f, fill=R.PAPER, anchor="r")
    return layer


def overlay(im, ov, rect, fade=None):
    """Draw screen-space overlays on a 1920x1080 frame. fade: {element: alpha} for
    elements that are fading in (others are fully visible)."""
    if not ov:
        return im
    fade = fade or {}
    out = im.convert("RGBA")
    parts = []
    if ov.get("focus"):
        parts.append(("focus", _draw_focus(ov["focus"], rect)))
    if ov.get("badges"):
        parts.append(("badges", _draw_badges(ov["badges"], rect)))
    if ov.get("bar") or ov.get("score"):
        parts.append(("bar", _draw_bar(ov)))
    if ov.get("arrows"):
        parts.append(("arrows", _draw_arrows(ov["arrows"], rect)))
    if ov.get("pops"):
        parts.append(("pops", _draw_pops(ov["pops"], rect, caption_box(ov) if ov.get("cap") else None)))
    if ov.get("cap"):
        parts.append(("cap", _draw_caption(ov)))
    for k, layer in parts:
        out.alpha_composite(_alpha(layer, fade.get(k, 1.0)))
    return out.convert("RGB")


OV_KEYS = {"focus": ("focus",), "badges": ("badges",), "bar": ("bar", "score"),
           "arrows": ("arrows",), "pops": ("pops",), "cap": ("cap", "cap_pos")}


def _new_parts(ov, ov_prev):
    ov_prev = ov_prev or {}
    return [k for k, keys in OV_KEYS.items()
            if any(ov.get(x) for x in keys) and any(ov.get(x) != ov_prev.get(x) for x in keys)]


# =============================================================== assembly
def _start_frames(seg):
    """Supersampled frames for the segment: [(image, n)] (last = settled) and sfx."""
    if "image" in seg:
        frames, sfx = [(seg["image"], 1)], []
        f = seg.get("fade")
        start = f if isinstance(f, Image.Image) else R.new_canvas()[0] if f else None
    elif seg.get("pre") is not None and seg.get("xfade"):
        tk = seg.get("tk", {})
        frames, sfx = [(R.table(seg["post"], **tk), 1)], []
        start = R.table(seg["pre"], **tk)
    elif seg.get("pre") is not None:
        return anim_frames(seg["pre"], seg["post"], seg.get("tk", {}), fast=seg.get("fast", False))
    else:
        tk = seg.get("tk", {})
        frames, sfx = [(R.table(seg["post"], **tk), 1)], []
        start = R.table(seg["post"], **{**tk, **seg["fade_from"]}) if seg.get("fade_from") else None
    if start is not None:
        end = frames[0][0]
        frames = [(Image.blend(start, end, ease(f / FADE_FRAMES)), 2)
                  for f in range(0, FADE_FRAMES, 2)] + frames
    return frames, sfx


def _render_seg(args):
    idx, seg, cam_prev, ov_prev, seg_dir = args
    cam = seg.get("cam") or FULL
    ov = seg.get("ov") or {}
    frames, sfx = _start_frames(seg)
    moving = cam_prev != cam
    nanim = sum(n for _, n in frames[:-1])
    new = _new_parts(ov, ov_prev)
    # pop-ups and count badges appear once the tiles have landed
    late = {k for k in new if k in ("pops", "badges")} if nanim else set()
    total = max(nanim + (OV_FRAMES if late else 0), CAM_FRAMES if moving else 0,
                OV_FRAMES if new else 0)
    out, f = [], 0
    timeline = []
    for im, n in frames[:-1]:
        timeline += [im] * n
    while f < total:
        im = timeline[f] if f < len(timeline) else frames[-1][0]
        t = ease(f / CAM_FRAMES) if moving else 1
        rect = tuple(a + (b - a) * t for a, b in zip(cam_prev, cam))
        a = ease(f / OV_FRAMES)
        al = {k: a for k in new if k not in late}
        al.update({k: ease((f - nanim) / OV_FRAMES) for k in late})
        out.append((overlay(_crop(im, rect), ov, rect, al), 2))
        f += 2
    out.append((overlay(_crop(frames[-1][0], cam), ov, cam), 1))
    paths = []
    for j, (im, n) in enumerate(out):
        p = Path(seg_dir) / f"{idx:04d}_{j:03d}.png"
        im.save(p, compress_level=1)
        paths.append((str(p), n))
    return idx, (paths, sfx + [(0, s) for s in seg.get("sfx", [])])


def sentences(text):
    """Split narration into sentences; each is voiced separately, with a pause between."""
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def narrate(text, cache_dir):
    """(audio, [(sentence, start, end)]) with GAP seconds of silence between sentences."""
    parts, cues, t = [], [], 0.0
    for i, s in enumerate(sentences(text)):
        if i:
            parts.append(np.zeros(int(GAP * SR), np.float32))
            t += GAP
        a = tts(s, cache_dir)
        parts.append(a)
        cues.append((s, t, t + len(a) / SR))
        t += len(a) / SR
    return (np.concatenate(parts) if parts else np.zeros(0, np.float32)), cues


def timing(seg, anim_n, speech):
    """(lead, total_frames) for a segment: when the voice starts, and its length."""
    has = bool(seg.get("text"))
    lead = (anim_n / FPS + 0.15 if seg.get("say_after") else 0.2) if has else 0
    after = seg.get("pause", PAD) if has else 0
    need = max(lead + speech + after, anim_n / FPS + seg.get("hold", 0.6))
    return lead, max(anim_n + 4, int(math.ceil(need * FPS)))


PAD = 0.45


def build(name, segments, out_dir, work_dir, music=True):
    """segments: dicts with text, and image | post (+pre for animation), tk (table
    kwargs), cam (x, y, w), hold (min seconds after the animation), sfx [names],
    ov (screen overlays: cap, cap_pos, arrows, focus, pops, badges, bar, score),
    pause (silence after the narration), say_after (narration waits for the
    animation), fast (quick tile moves), fade / fade_from / xfade (crossfades)."""
    seg_dir = Path(work_dir) / name
    seg_dir.mkdir(parents=True, exist_ok=True)
    for f in seg_dir.glob("*.png"):
        f.unlink()
    voiced = [narrate(s["text"], Path(work_dir) / "tts") if s.get("text") else
              (np.zeros(0, np.float32), []) for s in segments]
    cams, ovs, prev, prev_ov = [], [], FULL, None
    for s in segments:
        cams.append(prev)
        ovs.append(prev_ov)
        prev, prev_ov = s.get("cam") or FULL, s.get("ov")
    jobs = [(i, s, cams[i], ovs[i], str(seg_dir)) for i, s in enumerate(segments)]
    ctx = mp.get_context("fork")
    with ProcessPoolExecutor(max_workers=os.cpu_count() or 2, mp_context=ctx) as ex:
        res = dict(ex.map(_render_seg, jobs))
    bank = _sfx_bank()
    lines, tracks, fx, srt, t = [], [], [], [], 0.0
    for i, s in enumerate(segments):
        frames, sfx = res[i]
        anim_n = sum(n for _, n in frames[:-1])
        audio, cues = voiced[i]
        lead, total_n = timing(s, anim_n, len(audio) / SR)
        for p, n in frames[:-1]:
            lines.append(f"file '{p}'\nduration {n / FPS:.6f}\n")
        lines.append(f"file '{frames[-1][0]}'\nduration {(total_n - anim_n) / FPS:.6f}\n")
        n_samp = int(round(total_n / FPS * SR))
        a = np.zeros(n_samp, np.float32)
        st = int(lead * SR)
        a[st:st + len(audio)] = audio[:max(0, n_samp - st)]
        b = np.zeros(n_samp, np.float32)
        for fr, kind in sfx:
            o = int(fr / FPS * SR)
            clip = bank[kind][:max(0, n_samp - o)]
            b[o:o + len(clip)] += clip
        tracks.append(a)
        fx.append(b)
        for text, c0, c1 in cues:
            srt.append(f"{len(srt) + 1}\n{_ts(t + lead + c0)} --> {_ts(t + lead + c1)}\n{text}\n")
        t += total_n / FPS
    lines.append(f"file '{res[len(segments) - 1][0][-1][0]}'\n")
    voice = np.concatenate(tracks)
    mix = voice + np.concatenate(fx)
    if music:
        env = np.convolve(np.abs(voice), np.ones(SR // 4) / (SR // 4), mode="same")
        duck = 1 - 0.7 * np.clip(env / 0.02, 0, 1)
        amb = ambient(len(voice) / SR)
        amb = np.pad(amb, (0, max(0, len(voice) - len(amb))))[:len(voice)]
        mix = mix + amb * 0.09 * duck
    mix = mix / max(1.0, np.abs(mix).max() / 0.95)
    wav = seg_dir / "audio.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    lst = seg_dir / "frames.txt"
    lst.write_text("".join(lines))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4 = out_dir / f"{name}.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
        "-i", str(wav), "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264",
        "-preset", "medium", "-crf", "20", "-tune", "animation", "-c:a", "aac", "-b:a", "160k",
        "-ar", "44100", "-shortest", "-movflags", "+faststart", str(mp4)], check=True)
    (out_dir / f"{name}.srt").write_text("\n".join(srt))
    print(f"{mp4.name}: {len(segments)} segments, {t / 60:.2f} min", flush=True)
    return mp4


def _ts(t):
    h, m = divmod(int(t), 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{int((t % 1) * 1000):03d}"
