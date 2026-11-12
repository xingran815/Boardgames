"""Animated transitions between two table snapshots, plus clip assembly
(Kokoro TTS narration, optional ambient music, ffmpeg encode)."""
from __future__ import annotations

import hashlib
import math
import os
import subprocess
import wave
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

import render as R

FPS = 30
ANIM_FRAMES = 18          # 0.6 s per moving stone
STAGGER = 6               # frames between successive stones
COY_FRAMES = 30
CAM_FRAMES = 18
FULL = (0, 0, 1920)       # camera rect: x, y, width (height = width * 9/16)
VOICE_DIR = Path(__file__).resolve().parents[1] / "voices"
VOICE = os.environ.get("SOTW_VOICE", "af_heart")
SPEED = float(os.environ.get("SOTW_SPEED", "1.0"))
SR = 24000


# ================================================================ diffing
def _layout(st, tk):
    R.table(st, **{k: v for k, v in tk.items() if k in ("names",)})
    return dict(R.CTX["reg"]), R.CTX["coyote"]


def plan(pre, post, tk):
    """Return (movers, hide, coyote_move) to animate pre -> post.
    movers: (color, (x,y,r) from, (x,y,r) to, order, dest_kind)"""
    rpre, cpre = _layout(pre, tk)
    rpost, cpost = _layout(post, tk)
    is_bowl = lambda k: k[0] == "bowl"
    movers, hide = [], set()
    app_b = [k for k in rpost if not is_bowl(k) and (k not in rpre or rpre[k][3] != rpost[k][3])]
    dis_b = [k for k in rpre if not is_bowl(k) and (k not in rpost or rpost[k][3] != rpre[k][3])]
    pb = sorted((k for k in rpre if is_bowl(k)), key=lambda k: k[1])
    qb = sorted((k for k in rpost if is_bowl(k)), key=lambda k: k[1])
    pool = {}
    for k in pb:
        pool.setdefault(rpre[k][3], []).append(k)
    app_w, matched = [], set()
    for k in qb:
        c = rpost[k][3]
        if pool.get(c):
            src = pool[c].pop(0)
            matched.add(src)
            if rpre[src][:2] != rpost[k][:2]:
                movers.append((c, rpre[src][:3], rpost[k][:3], 0, "shift"))
                hide.add(k)
        else:
            app_w.append(k)
    dis_w = [k for k in pb if k not in matched]
    bag = (*R.BAG_XY, 18)
    order = 1
    for k in app_b:
        c = rpost[k][3]
        src = next((s for s in dis_w if rpre[s][3] == c), None)
        if src:
            dis_w.remove(src)
        movers.append((c, rpre[src][:3] if src else bag, rpost[k][:3], order,
                       "bonus" if k[3] == "bonus" else "board"))
        hide.add(k)
        order += 1
    for k in app_w:
        c = rpost[k][3]
        src = next((s for s in dis_b if rpre[s][3] == c), None)
        if src:
            dis_b.remove(src)
        movers.append((c, rpre[src][:3] if src else bag, rpost[k][:3], order, "bowl"))
        hide.add(k)
        order += 1
    for k in dis_w + dis_b:
        movers.append((rpre[k][3], rpre[k][:3], bag, order, "bag"))
        order += 1
    coy = None
    if pre.get("coyote") != post.get("coyote") and cpre and cpost:
        coy = (cpre, cpost)
        hide.add("coyote")
    return movers, hide, coy


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


def anim_frames(pre, post, tk):
    """([(supersampled image, n_frames)], [(frame, sfx)]). Last image = settled."""
    movers, hide, coy = plan(pre, post, tk)
    final = R.table(post, **tk)
    if not movers and not coy:
        return [(final, 1)], []
    base = R.table(post, **{**tk, "hide": hide, "deltas": None})
    nsteps = max([m[3] for m in movers] + [0]) * STAGGER + ANIM_FRAMES
    if coy:
        nsteps = max(nsteps, COY_FRAMES)
    sfx = []
    for c, _, _, o, kind in movers:
        if kind != "shift":
            sfx.append((o * STAGGER + ANIM_FRAMES - 1,
                        "chime" if (kind == "bonus" or (c == "clear" and kind == "bowl")) else "click"))
    if coy:
        sfx.append((2, "yip"))
    out = []
    for f in range(0, nsteps, 2):
        im = base.copy()
        d = R.SDraw(im)
        for c, (x0, y0, r0), (x1, y1, r1), o, kind in movers:
            t = ease((f - o * STAGGER) / ANIM_FRAMES)
            lift = math.sin(math.pi * t) * (0 if kind == "shift" else 70)
            R.stone(d, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t - lift,
                    r0 + (r1 - r0) * t + math.sin(math.pi * t) * (0 if kind == "shift" else 8), c)
        if coy:
            (ax, ay, as_), (bx, by, bs) = coy
            t = ease(f / COY_FRAMES)
            R.draw_coyote(d, ax + (bx - ax) * t, ay + (by - ay) * t - math.sin(math.pi * t) * 120,
                          as_ + (bs - as_) * t)
        out.append((im, 2))
    out.append((final, 1))
    return out, sfx


# ==================================================================== TTS
_k = None


def tts(text, cache_dir):
    """Return mono float32 numpy audio at SR."""
    global _k
    h = hashlib.sha1(f"{VOICE}|{SPEED}|{text}".encode()).hexdigest()[:16]
    p = Path(cache_dir) / f"{h}.npy"
    if p.exists():
        return np.load(p)
    if _k is None:
        from kokoro_onnx import Kokoro
        _k = Kokoro(str(VOICE_DIR / "kokoro-v1.0.int8.onnx"), str(VOICE_DIR / "voices-v1.0.bin"))
    lang = "en-gb" if VOICE.startswith("b") else "en-us"
    a, sr = _k.create(text, voice=VOICE, speed=SPEED, lang=lang)
    assert sr == SR
    a = a.astype(np.float32)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.save(p, a)
    return a


# ================================================================== music
def ambient(seconds, seed=3):
    """Soft synthesized pad (original), Am-F-C-G, very low in the mix."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63],
              [130.81, 196.0, 261.63], [196.0, 246.94, 293.66]]
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
            sig += np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 1.003 * tt + 1)
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
    tt = t(0.09)
    n = rng.standard_normal(len(tt))
    bank["click"] = (0.5 * np.sin(2 * np.pi * 2300 * tt) + 0.5 * np.diff(n, prepend=0) * 0.5) \
        * np.exp(-tt * 60) * 0.35
    tt = t(1.2)
    bank["chime"] = sum(np.sin(2 * np.pi * f * tt) * np.exp(-tt * k)
                        for f, k in ((1318.5, 3), (1975.5, 4), (2637, 5))) * 0.12
    tt = t(0.32)
    f = 650 + 700 * np.sin(np.pi * tt / 0.32)
    bank["yip"] = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / 0.32) * 0.18
    tt = t(0.22)
    n = rng.standard_normal(len(tt))
    bank["card"] = np.convolve(n, np.ones(12) / 12, mode="same") * np.sin(np.pi * tt / 0.22) * 0.25
    notes, out = (523.25, 659.25, 783.99, 1046.5), []
    for i, fr in enumerate(notes):
        tt = t(0.5 if i == 3 else 0.14)
        out.append(np.sin(2 * np.pi * fr * tt) * np.exp(-tt * (3 if i == 3 else 8)) * 0.22)
    bank["win"] = np.concatenate(out)
    return {k: v.astype(np.float32) for k, v in bank.items()}


# =============================================================== assembly
def _crop(im, rect):
    x, y, w = rect
    h = w * 9 / 16
    s = R.S
    return im.resize((R.W, R.H), Image.LANCZOS, box=(x * s, y * s, (x + w) * s, (y + h) * s))


def _render_seg(args):
    idx, seg, cam_prev, seg_dir = args
    cam = seg.get("cam") or FULL
    if "image" in seg:
        frames, sfx = [(seg["image"], 1)], []
    elif seg.get("pre") is not None:
        frames, sfx = anim_frames(seg["pre"], seg["post"], seg.get("tk", {}))
    else:
        frames, sfx = [(R.table(seg["post"], **seg.get("tk", {})), 1)], []
    moving = cam_prev != cam
    nanim = sum(n for _, n in frames[:-1])
    total = max(nanim, CAM_FRAMES if moving else 0)
    out, f = [], 0
    timeline = []
    for im, n in frames[:-1]:
        timeline += [im] * n
    while f < total:
        im = timeline[f] if f < len(timeline) else frames[-1][0]
        t = ease(f / CAM_FRAMES) if moving else 1
        rect = tuple(a + (b - a) * t for a, b in zip(cam_prev, cam))
        out.append((_crop(im, rect), 2))
        f += 2
    out.append((_crop(frames[-1][0], cam), 1))
    paths = []
    for j, (im, n) in enumerate(out):
        p = Path(seg_dir) / f"{idx:04d}_{j:03d}.png"
        im.save(p, compress_level=1)
        paths.append((str(p), n))
    return idx, (paths, sfx + [(0, s) for s in seg.get("sfx", [])])


def build(name, segments, out_dir, work_dir, music=True, pad=0.45):
    """segments: dicts with text, and image | post (+pre for animation), tk (table
    kwargs), cam (x, y, w), hold (min seconds after the animation), sfx [names]."""
    seg_dir = Path(work_dir) / name
    seg_dir.mkdir(parents=True, exist_ok=True)
    for f in seg_dir.glob("*.png"):
        f.unlink()
    audio = [tts(s["text"], Path(work_dir) / "tts") if s.get("text") else np.zeros(0, np.float32)
             for s in segments]
    cams, prev = [], FULL
    for s in segments:
        cams.append(prev)
        prev = s.get("cam") or FULL
    jobs = [(i, s, cams[i], str(seg_dir)) for i, s in enumerate(segments)]
    with ProcessPoolExecutor(max_workers=os.cpu_count() or 2) as ex:
        res = dict(ex.map(_render_seg, jobs))
    bank = _sfx_bank()
    lines, tracks, fx, srt, t = [], [], [], [], 0.0
    for i, s in enumerate(segments):
        frames, sfx = res[i]
        anim_n = sum(n for _, n in frames[:-1])
        speech = len(audio[i]) / SR
        lead = 0.2 if s.get("text") else 0
        need = max(lead + speech + (pad if s.get("text") else 0), anim_n / FPS + s.get("hold", 0.6))
        total_n = max(anim_n + 6, int(math.ceil(need * FPS)))
        for p, n in frames[:-1]:
            lines.append(f"file '{p}'\nduration {n / FPS:.6f}\n")
        lines.append(f"file '{frames[-1][0]}'\nduration {(total_n - anim_n) / FPS:.6f}\n")
        n_samp = int(round(total_n / FPS * SR))
        a = np.zeros(n_samp, np.float32)
        st = int(lead * SR)
        a[st:st + len(audio[i])] = audio[i][:max(0, n_samp - st)]
        b = np.zeros(n_samp, np.float32)
        for fr, kind in sfx:
            o = int(fr / FPS * SR)
            clip = bank[kind][:max(0, n_samp - o)]
            b[o:o + len(clip)] += clip
        tracks.append(a)
        fx.append(b)
        if s.get("text"):
            srt.append(f"{len(srt) + 1}\n{_ts(t + lead)} --> {_ts(t + lead + speech)}\n{s['text']}\n")
        t += total_n / FPS
    lines.append(f"file '{res[len(segments) - 1][0][-1][0]}'\n")
    voice = np.concatenate(tracks)
    mix = voice + np.concatenate(fx)
    if music:
        env = np.convolve(np.abs(voice), np.ones(SR // 4) / (SR // 4), mode="same")
        duck = 1 - 0.7 * np.clip(env / 0.02, 0, 1)
        mix = mix + ambient(len(voice) / SR)[:len(voice)] * 0.09 * duck
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
    print(f"{mp4.name}: {len(segments)} segments, {t / 60:.2f} min")
    return mp4


def _ts(t):
    h, m = divmod(int(t), 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{int((t % 1) * 1000):03d}"
