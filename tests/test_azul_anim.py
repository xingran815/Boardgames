"""Azul animation planning, overlays, audio helpers and (mocked) clip assembly."""
import copy
import importlib.util
import math
import sys
import wave
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

AZUL = Path(__file__).resolve().parents[1] / "tools" / "azul"


def load(name):
    full = f"azul_{name}"
    if full not in sys.modules:
        spec = importlib.util.spec_from_file_location(full, AZUL / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[full] = mod
        spec.loader.exec_module(mod)
    return sys.modules[full]


A = load("anim")
R, E = A.R, A.R.E


def offer_state(seed=2):
    st = E.new_game(2, seed)
    return st


def apply(st, move):
    st = copy.deepcopy(st)
    E.apply_move(st, move)
    return st


def first_factory_move(st, line=1):
    f = st["factories"][0]
    return E.Move(0, f[0], line), f.count(f[0]), len(f) - f.count(f[0])


# ================================================================== basics
def test_ease():
    assert A.ease(0) == 0 and A.ease(1) == 1 and A.ease(0.5) == pytest.approx(0.5)
    assert A.ease(-2) == 0 and A.ease(9) == 1
    vals = [A.ease(i / 100) for i in range(101)]
    assert all(b >= a for a, b in zip(vals, vals[1:]))


def test_sentences():
    assert A.sentences("One. Two! Three? Four") == ["One.", "Two!", "Three?", "Four"]
    assert A.sentences("  ") == []
    assert A.sentences("Line one: black to the wall, one point.") == \
        ["Line one: black to the wall, one point."]


def test_srt_timestamps():
    assert A._ts(0) == "00:00:00,000"
    assert A._ts(61.25) == "00:01:01,250"
    assert A._ts(3725.5) == "01:02:05,500"


def test_spoken_keeps_captions_unchanged():
    assert A.spoken("Welcome to Azul!") != "Welcome to Azul!"
    assert A.spoken("A red tile.") == "A red tile."


def test_voice_settings_follow_the_playbook():
    assert A.VOICE == "af_heart" and A.SPEED == pytest.approx(0.9)
    assert A.GAP == pytest.approx(0.32)


def test_timing():
    lead, n = A.timing({"text": "x", "hold": 0.6}, 0, 2.0)
    assert lead == pytest.approx(0.2) and n == math.ceil((0.2 + 2.0 + A.PAD) * A.FPS)
    lead, n = A.timing({"text": "x", "say_after": True, "pause": 0.9}, 30, 1.0)
    assert lead == pytest.approx(1.15) and n == math.ceil((1.15 + 1.0 + 0.9) * A.FPS)
    lead, n = A.timing({"text": "", "hold": 0.25}, 20, 0.0)
    assert lead == 0 and n == max(24, math.ceil((20 / A.FPS + 0.25) * A.FPS))


# ==================================================================== plan
class TestPlan:
    def test_no_change_no_movers(self):
        st = offer_state()
        movers, hide = A.plan(st, copy.deepcopy(st), {})
        assert movers == [] and hide == set()

    def test_take_from_a_factory(self):
        pre = offer_state()
        mv, n_taken, n_pushed = first_factory_move(pre)
        post = apply(pre, mv)
        movers, hide = A.plan(pre, post, {})
        to_line = [m for m in movers if m[4] == "line"]
        to_floor = [m for m in movers if m[4] == "floor"]
        to_centre = [m for m in movers if m[4] == "c"]
        placed = min(n_taken, 2)
        assert len(to_line) == placed and len(to_floor) == n_taken - placed
        assert len(to_centre) == n_pushed
        assert all(m[0] == mv.colour for m in to_line + to_floor)
        assert all(m[0] != mv.colour for m in to_centre)
        R.table(pre)
        fac = {v[:2] for k, v in R.CTX["reg"].items() if k[0] == "f" and k[1] == 0}
        assert all(m[1][:2] in fac for m in to_line + to_centre)      # all start on display 0
        assert {("p", 0, "line", 1, k) for k in range(placed)} <= hide
        orders = [m[3] for m in to_line]
        assert orders == sorted(orders) and min(m[3] for m in to_centre) > max(orders)

    def test_take_from_the_centre_moves_the_marker_to_the_floor(self):
        st = offer_state()
        mv, _, _ = first_factory_move(st)
        st = apply(st, mv)
        colour = st["centre"][0]
        st["current"] = 1
        post = apply(st, E.Move(E.CENTRE, colour, E.FLOOR))
        movers, hide = A.plan(st, post, {})
        mk = [m for m in movers if m[4] == "marker"]
        assert len(mk) == 1 and mk[0][2][:2] == R.floor_xy(1, 0)
        assert ("m",) in hide
        floor = [m for m in movers if m[4] == "floor"]
        assert len(floor) == st["centre"].count(colour)
        assert any(m[4] == "shift" for m in movers) or len(post["centre"]) == 0

    def test_new_tiles_come_from_the_bag_or_src_xy(self):
        st = E.new_state(2, 5)
        post = copy.deepcopy(st)
        E.fill_factories(post)
        movers, _ = A.plan(st, post, {})
        assert len(movers) == sum(len(f) for f in post["factories"])
        assert all(m[1][:2] == R.BAG_XY and m[4] == "f" for m in movers)
        movers, _ = A.plan(st, post, {"src_xy": (5, 6)})
        assert all(m[1][:2] == (5, 6) for m in movers)

    def test_wall_tiling_rightmost_tile_to_wall_rest_to_lid(self):
        st = E.new_state(2, 1)
        b = st["boards"][0]
        b["lines"][2] = {"colour": "red", "count": 3}
        for _ in range(3):
            st["bag"].remove("red")
        post = copy.deepcopy(st)
        info = E.tile_wall(post, 0)
        assert info["placements"][0]["points"] == 1
        movers, hide = A.plan(st, post, {})
        wall = [m for m in movers if m[4] == "wall"]
        assert len(wall) == 1
        assert wall[0][1][:2] == R.line_xy(0, 2, 0)                   # the rightmost tile
        assert wall[0][2][:2] == R.wall_xy(0, 2, E.wall_column(2, "red"))
        lid = [m for m in movers if m[4] == "lid"]
        assert len(lid) == 2 and {m[1][:2] for m in lid} == {R.line_xy(0, 2, 1), R.line_xy(0, 2, 2)}

    def test_lid_into_the_bag(self):
        st = E.new_state(2, 1)
        st["lid"], st["bag"] = st["bag"][:30], st["bag"][30:]
        post = copy.deepcopy(st)
        post["bag"] += post["lid"]
        post["lid"] = []
        movers, _ = A.plan(st, post, {})
        assert len(movers) == R.LID_SLOTS
        assert all(m[4] == "bag" and m[2][:2] == R.BAG_XY for m in movers)

    def test_marker_appears(self):
        st = E.new_state(2, 1)
        st["marker_holder"] = None
        post = copy.deepcopy(st)
        post["marker_holder"] = 0
        movers, hide = A.plan(st, post, {})
        assert [m[4] for m in movers] == ["marker"] and ("m",) in hide

    def test_matches_whole_game_transitions(self):
        """Every turn of a real game plans cleanly: one mover per tile that moved."""
        g = E.Game(2, 7)
        log = g.play()
        prev = None
        for e in log:
            st = e.get("post") or e.get("state")
            if prev is not None and e["type"] == "turn":
                movers, hide = A.plan(prev, st, {})
                mv = e["move"]
                assert len([m for m in movers if m[0] == mv.colour and m[4] in ("line", "floor")]) \
                    == e["placed"] + e["to_floor"]
                assert len([m for m in movers if m[4] == "c"]) == e["pushed"]
            prev = st


class TestFrames:
    def test_anim_frames_end_settled(self):
        pre = offer_state()
        mv, _, _ = first_factory_move(pre)
        post = apply(pre, mv)
        frames, sfx = A.anim_frames(pre, post, {})
        assert frames[-1][1] == 1 and len(frames) > 3
        assert frames[-1][0].tobytes() == R.table(post).tobytes()
        assert sfx and all(k in A._sfx_bank() for _, k in sfx)
        fast, _ = A.anim_frames(pre, post, {}, fast=True)
        assert len(fast) < len(frames)

    def test_no_movement_single_frame(self):
        st = offer_state()
        frames, sfx = A.anim_frames(st, copy.deepcopy(st), {})
        assert len(frames) == 1 and sfx == []


# ================================================================== audio
def test_sfx_bank_complete():
    bank = A._sfx_bank()
    assert set(A.SFX_NAMES) <= set(bank)
    assert {v for v in A.SFX_FOR.values() if v} <= set(bank)
    for k, v in bank.items():
        assert v.dtype == np.float32 and np.abs(v).max() < 1.0, k


def test_ambient_is_quiet_and_faded():
    a = A.ambient(10)
    assert len(a) == 10 * A.SR and np.abs(a).max() <= 1.0 + 1e-6
    assert abs(a[0]) < 1e-3 and abs(a[-1]) < 1e-2


# ================================================================ overlays
class TestOverlays:
    def test_caption_positions(self):
        for pos in ("top", "mid", "bottom"):
            x0, y0, x1, y1 = A.caption_box({"cap": ("Title", "sub"), "cap_pos": pos})
            assert 0 < x0 < x1 < R.W and 0 < y0 < y1 < R.H
        top = A.caption_box({"cap": "T"})
        bot = A.caption_box({"cap": "T", "cap_pos": "bottom"})
        assert top[1] < 100 and bot[3] > R.H - 100
        barred = A.caption_box({"cap": "T", "cap_pos": "bottom", "bar": "x"})
        assert barred[3] <= R.H - 78

    def test_pop_boxes_stay_on_screen_and_dodge_captions(self):
        rect = (0, 0, 1920)
        x, y = R.wall_xy(0, 0, 0)
        cap = A.caption_box({"cap": "A very long caption across the top"})
        free = A.pop_box((x, y, "+3", "tile"), rect)
        assert free[3] <= y - R.T / 2                 # above the tile
        cam = (0, y - 40, 900)
        dodge = A.pop_box((x, y, "+3", "tile"), cam, avoid=cap)
        assert dodge[1] >= cap[3] or dodge[3] <= cap[1] or dodge[0] >= cap[2] or dodge[2] <= cap[0]
        for p in (free, dodge, A.pop_box((5000, -40, "−14", "at"), rect)):
            assert 0 <= p[0] < p[2] <= R.W and 0 <= p[1] < p[3] <= R.H

    def test_overlay_draws_each_part(self):
        im = Image.new("RGB", (R.W, R.H), R.BG)
        rect = A.FULL
        base = im.tobytes()
        for ov in ({"cap": "Hi"}, {"cap": ("Hi", "there"), "cap_pos": "mid"},
                   {"arrows": [(900, 500, "Here", "down")]}, {"focus": [(100, 100, 300, 300)]},
                   {"pops": [(500, 500, "+2", "tile")]}, {"badges": [(600, 600, "1", "across")]},
                   {"bar": "Round 1", "score": "Ana 0 · Ben 0"}):
            out = A.overlay(im, ov, rect)
            assert out.size == (R.W, R.H) and out.tobytes() != base, ov
        assert A.overlay(im, {}, rect) is im

    def test_new_parts(self):
        assert A._new_parts({"cap": "a"}, None) == ["cap"]
        assert A._new_parts({"cap": "a"}, {"cap": "a"}) == []
        assert set(A._new_parts({"cap": "a", "pops": [1]}, {"cap": "b"})) == {"cap", "pops"}


# ================================================================ assembly
def test_build_keeps_audio_video_and_srt_in_sync(tmp_path, monkeypatch):
    """Mocked TTS and ffmpeg: frame durations, audio length and SRT cues line up."""
    monkeypatch.setattr(A, "tts", lambda text, cache: np.full(int(0.05 * len(text) * A.SR),
                                                               0.01, np.float32))
    calls = []
    monkeypatch.setattr(A.subprocess, "run", lambda cmd, check: calls.append(cmd))

    class SerialPool:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def map(self, f, jobs):
            return map(f, jobs)

    monkeypatch.setattr(A, "ProcessPoolExecutor", SerialPool)
    st = offer_state()
    mv, _, _ = first_factory_move(st)
    post = apply(st, mv)
    segs = [dict(text="Hello there. Second one.", image=R.title_card("T"), hold=0.5, fade=True),
            dict(text="Ana takes tiles.", post=post, pre=st, tk={}, cam=(0, 0, 960), hold=0.6,
                 say_after=True, ov={"cap": "Take", "pops": [(*R.wall_xy(0, 0, 0), "+1", "tile")]}),
            dict(text="", post=post, tk={}, cam=None, hold=0.3, ov={})]
    A.build("t", segs, tmp_path / "out", tmp_path / "work", music=True)
    assert calls and calls[0][0] == "ffmpeg"
    lst = (tmp_path / "work" / "t" / "frames.txt").read_text()
    total = sum(float(l.split()[1]) for l in lst.splitlines() if l.startswith("duration"))
    with wave.open(str(tmp_path / "work" / "t" / "audio.wav")) as w:
        audio = w.getnframes() / w.getframerate()
    assert total == pytest.approx(audio, abs=1 / A.SR * 3)
    assert abs(total * A.FPS - round(total * A.FPS)) < 1e-3          # whole frames
    srt = (tmp_path / "out" / "t.srt").read_text().strip().split("\n\n")
    assert len(srt) == 3                                              # one cue per sentence
    assert [c.splitlines()[2] for c in srt] == ["Hello there.", "Second one.", "Ana takes tiles."]
    starts = [c.splitlines()[1].split(" --> ")[0] for c in srt]
    assert starts == sorted(starts)
