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
from PIL import ImageDraw

import render as R

FPS = 30
ANIM_FRAMES = 18          # 0.6 s per moving stone
STAGGER = 5               # frames between successive stones
VOICE_DIR = Path(__file__).resolve().parents[1] / "voices"
VOICE = os.environ.get("SOTW_VOICE", "af_heart")
SPEED = float(os.environ.get("SOTW_SPEED", "1.08"))
SR = 24000


# ================================================================ diffing
def _layout(st, **kw):
    im = R.table(st, **kw)
    return im, dict(R.CTX["reg"]), R.CTX["coyote"]


def plan(pre, post, names, cap, hl):
    """Return (movers, hide, coyote_move) to animate pre -> post."""
    _, rpre, cpre = _layout(pre, names=names)
    _, rpost, cpost = _layout(post, names=names)
    is_bowl = lambda k: k[0] == "bowl"
    movers, hide = [], set()
    # board slots
    app_b = [k for k in rpost if not is_bowl(k) and (k not in rpre or rpre[k][3] != rpost[k][3])]
    dis_b = [k for k in rpre if not is_bowl(k) and (k not in rpost or rpost[k][3] != rpre[k][3])]
    # bowl: match by color, in order
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
                movers.append((c, rpre[src][:3], rpost[k][:3], 0))
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
            frm = rpre[src][:3]
        else:
            frm = bag
        movers.append((c, frm, rpost[k][:3], order))
        hide.add(k)
        order += 1
    for k in app_w:
        c = rpost[k][3]
        src = next((s for s in dis_b if rpre[s][3] == c), None)
        if src:
            dis_b.remove(src)
            frm = rpre[src][:3]
        else:
            frm = bag
        movers.append((c, frm, rpost[k][:3], order))
        hide.add(k)
        order += 1
    for k in dis_w + dis_b:  # leftovers go back into the bag
        movers.append((rpre[k][3], rpre[k][:3], bag, order))
        order += 1
    coy = None
    if pre.get("coyote") != post.get("coyote") and cpre and cpost:
        coy = (cpre, cpost)
        hide.add("coyote")
    return movers, hide, coy


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


def anim_frames(pre, post, names, cap, hl):
    """List of (image, n_frames). Last entry is the settled post frame."""
    movers, hide, coy = plan(pre, post, names, cap, hl)
    final = R.table(post, names, cap=cap, hl=hl)
    if not movers and not coy:
        return [(final, 1)]
    base = R.table(post, names, cap=cap, hl=hl, hide=hide)
    if coy:
        hide2 = set(hide)
    nsteps = max([m[3] for m in movers] + [0]) * STAGGER + ANIM_FRAMES
    out = []
    for f in range(0, nsteps, 2):  # render every 2nd frame, hold for 2
        im = base.copy()
        d = ImageDraw.Draw(im)
        for c, (x0, y0, r0), (x1, y1, r1), o in movers:
            t = ease((f - o * STAGGER) / ANIM_FRAMES)
            lift = math.sin(math.pi * t) * 60
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t - lift
            r = r0 + (r1 - r0) * t + math.sin(math.pi * t) * 6
            if t <= 0:
                x, y, r = x0, y0, r0
            R.stone(d, x, y, r, c)
        if coy:
            (ax, ay, as_), (bx, by, bs) = coy
            t = ease(f / ANIM_FRAMES)
            R.draw_coyote(d, ax + (bx - ax) * t, ay + (by - ay) * t - math.sin(math.pi * t) * 80,
                          as_ + (bs - as_) * t)
        out.append((im, 2))
    out.append((final, 1))
    return out


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
    return out * fade


# =============================================================== assembly
def _render_seg(args):
    idx, kind, payload, seg_dir = args
    if kind == "static":
        frames = [(payload, 1)]
    else:
        pre, post, names, cap, hl = payload
        frames = anim_frames(pre, post, names, cap, hl)
    paths = []
    for j, (im, n) in enumerate(frames):
        p = Path(seg_dir) / f"{idx:04d}_{j:03d}.png"
        im.save(p, compress_level=1)
        paths.append((str(p), n))
    return idx, paths


def build(name, segments, out_dir, work_dir, music=True, pad=0.25):
    """segments: list of dicts {text, kind: 'static'|'anim', payload}."""
    seg_dir = Path(work_dir) / name
    seg_dir.mkdir(parents=True, exist_ok=True)
    for f in seg_dir.glob("*.png"):
        f.unlink()
    audio = [tts(s["text"], Path(work_dir) / "tts") for s in segments]
    jobs = [(i, s["kind"], s["payload"], str(seg_dir)) for i, s in enumerate(segments)]
    with ProcessPoolExecutor(max_workers=os.cpu_count() or 2) as ex:
        frames = dict(ex.map(_render_seg, jobs))
    lines, tracks, srt, t = [], [], [], 0.0
    for i, s in enumerate(segments):
        anim_n = sum(n for _, n in frames[i][:-1])
        speech = len(audio[i]) / SR
        lead = 0.15
        total_n = max(anim_n + int(FPS * 0.4), int(math.ceil((lead + speech + pad) * FPS)))
        hold = total_n - anim_n
        for p, n in frames[i][:-1]:
            lines.append(f"file '{p}'\nduration {n / FPS:.6f}\n")
        lines.append(f"file '{frames[i][-1][0]}'\nduration {hold / FPS:.6f}\n")
        seg_samples = int(round(total_n / FPS * SR))
        a = np.zeros(seg_samples, np.float32)
        st = int(lead * SR)
        a[st:st + len(audio[i])] = audio[i][:seg_samples - st]
        tracks.append(a)
        dur = total_n / FPS
        srt.append(f"{i + 1}\n{_ts(t + lead)} --> {_ts(t + min(dur, lead + speech + 0.1))}\n{s['text']}\n")
        t += dur
    lines.append(f"file '{frames[len(segments) - 1][-1][0]}'\n")
    voice = np.concatenate(tracks)
    if music:
        env = np.convolve(np.abs(voice), np.ones(SR // 4) / (SR // 4), mode="same")
        duck = 1 - 0.6 * np.clip(env / 0.02, 0, 1)
        mix = voice + ambient(len(voice) / SR)[:len(voice)] * 0.07 * duck
    else:
        mix = voice
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
        "-preset", "medium", "-crf", "21", "-tune", "animation", "-c:a", "aac", "-b:a", "128k",
        "-ar", "44100", "-shortest", "-movflags", "+faststart", str(mp4)], check=True)
    (out_dir / f"{name}.srt").write_text("\n".join(srt))
    print(f"{mp4.name}: {len(segments)} segments, {t / 60:.2f} min")
    return mp4


def _ts(t):
    h, m = divmod(int(t), 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{int((t % 1) * 1000):03d}"
