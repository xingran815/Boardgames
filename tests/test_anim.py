"""Animation planning, easing, audio/SFX helpers and (mocked) ffmpeg assembly."""
import copy
import math
from pathlib import Path

import numpy as np
import pytest

import anim as A
import engine as E
import render as R
from conftest import rescore


def moved(st, fn):
    st = copy.deepcopy(st)
    fn(st)
    return rescore(st)


def regs(pre, post):
    rpre, cpre = A._layout(pre, {})
    rpost, cpost = A._layout(post, {})
    return rpre, rpost, cpre, cpost


# ================================================================== ease
def test_ease_endpoints():
    assert A.ease(0) == 0
    assert A.ease(1) == 1
    assert A.ease(0.5) == pytest.approx(0.5)


def test_ease_monotonic():
    ts = [i / 200 for i in range(201)]
    vals = [A.ease(t) for t in ts]
    assert all(b >= a for a, b in zip(vals, vals[1:]))
    assert all(0 <= v <= 1 for v in vals)


def test_ease_clamps_outside_unit_interval():
    assert A.ease(-3) == 0
    assert A.ease(7) == 1


# ================================================================== plan
def test_no_change_means_no_movement(base_state):
    movers, hide, coy = A.plan(base_state, copy.deepcopy(base_state), {})
    assert movers == [] and hide == set() and coy is None


def test_bowl_to_board_mover(base_state):
    def go(st):
        st["bowl"].remove("red")
        E.place(st["boards"][0], "red", ("rabbit", None))
    post = moved(base_state, go)
    movers, hide, coy = A.plan(base_state, post, {})
    rpre, rpost, _, _ = regs(base_state, post)
    board_moves = [m for m in movers if m[4] == "board"]
    assert len(board_moves) == 1
    color, src, dst, order, kind = board_moves[0]
    assert color == "red"
    assert src == rpre[("bowl", 0)][:3]                 # red sat at bowl slot 0
    assert dst == rpost[("b", 0, "rabbit", "s", 0)][:3]
    assert ("b", 0, "rabbit", "s", 0) in hide
    assert coy is None
    # the three remaining bowl stones just slide over (no lift, order 0)
    shifts = [m for m in movers if m[4] == "shift"]
    assert len(shifts) == 3 and all(m[3] == 0 for m in shifts)


def test_bowl_to_board_for_player_one(base_state):
    def go(st):
        st["bowl"].remove("blue")
        E.place(st["boards"][1], "blue", ("turtle", None))
    post = moved(base_state, go)
    movers, hide, _ = A.plan(base_state, post, {})
    rpre, rpost, _, _ = regs(base_state, post)
    (m,) = [m for m in movers if m[4] == "board"]
    assert m[0] == "blue"
    assert m[1] == rpre[("bowl", 1)][:3]
    assert m[2] == rpost[("b", 1, "turtle", "s", 0)][:3]


def test_two_stones_taken_are_ordered(base_state):
    def go(st):
        for c in ("red", "blue"):
            st["bowl"].remove(c)
        E.place(st["boards"][0], "red", ("rabbit", None))
        E.place(st["boards"][0], "blue", ("rabbit", None))
    movers, hide, _ = A.plan(base_state, moved(base_state, go), {})
    b = sorted((m for m in movers if m[4] == "board"), key=lambda m: m[3])
    assert [m[0] for m in b] == ["red", "blue"]
    assert b[0][3] < b[1][3]


def test_spirit_stone_to_bonus_space(base_state):
    def go(st):
        st["bowl"].remove(E.CLEAR)
        E.place(st["boards"][0], E.CLEAR, ("turtle", "bonus"))
    post = moved(base_state, go)
    movers, hide, _ = A.plan(base_state, post, {})
    rpre, rpost, _, _ = regs(base_state, post)
    (m,) = [m for m in movers if m[4] == "bonus"]
    assert m[0] == E.CLEAR
    assert m[1] == rpre[("bowl", 3)][:3]
    assert m[2] == rpost[("b", 0, "turtle", "bonus", 0)][:3]


def test_bag_to_bowl_draws_originate_at_bag(base_state):
    def go(st):
        st["bag"] -= 2
        st["bowl"] += ["yellow", "purple"]
    post = moved(base_state, go)
    movers, hide, _ = A.plan(base_state, post, {})
    rpre, rpost, _, _ = regs(base_state, post)
    draws = [m for m in movers if m[4] == "bowl"]
    assert sorted(m[0] for m in draws) == ["purple", "yellow"]
    for color, src, dst, order, kind in draws:
        assert src == (*R.BAG_XY, 18)
        assert dst in [rpost[("bowl", i)][:3] for i in (4, 5)]
    assert {("bowl", 4), ("bowl", 5)} <= hide
    assert not [m for m in movers if m[4] in ("board", "bonus", "bag")]


def test_bag_to_board_direct_placement(base_state):
    """Ram: stone goes straight from the bag to a board slot."""
    def go(st):
        st["bag"] -= 1
        E.place(st["boards"][0], "green", ("salmon", None))
    post = moved(base_state, go)
    movers, _, _ = A.plan(base_state, post, {})
    (m,) = [m for m in movers if m[4] == "board"]
    assert m[1] == (*R.BAG_XY, 18) and m[0] == "green"


def test_board_to_bowl_deer_move_starts_on_board(base_state):
    pre = moved(base_state, lambda st: E.place(st["boards"][0], "red", ("rabbit", None)))

    def go(st):
        E.remove(st["boards"][0], "rabbit", "red")
        st["bowl"].append("red")
    post = moved(pre, go)
    movers, _, _ = A.plan(pre, post, {})
    rpre, rpost, _, _ = regs(pre, post)
    (m,) = [m for m in movers if m[4] == "bowl"]
    assert m[1] == rpre[("b", 0, "rabbit", "s", 0)][:3]
    assert m[2] == rpost[("bowl", 4)][:3]


def test_bowl_to_bag_bear_return(base_state):
    def go(st):
        st["bowl"] = []
        st["bag"] += 4
        st["clear_out"] -= 1
    post = moved(base_state, go)
    movers, _, _ = A.plan(base_state, post, {})
    rpre, _, _, _ = regs(base_state, post)
    bag_moves = [m for m in movers if m[4] == "bag"]
    assert len(bag_moves) == 4
    for color, src, dst, order, kind in bag_moves:
        assert dst == (*R.BAG_XY, 18)
    assert {m[1][:2] for m in bag_moves} == {rpre[("bowl", i)][:2] for i in range(4)}


def test_coyote_change_yields_coyote_move(base_state):
    post = moved(base_state, lambda st: st.__setitem__("coyote", (1, "turtle")))
    movers, hide, coy = A.plan(base_state, post, {})
    assert coy is not None and "coyote" in hide
    (ax, ay, as_), (bx, by, bs) = coy
    rpre, rpost, cpre, cpost = regs(base_state, post)
    assert (ax, ay, as_) == cpre and (bx, by, bs) == cpost
    sx, sy, sw, sh = R.CTX["sec"][(1, "turtle")]
    assert sx <= bx <= sx + sw and sy <= by <= sy + sh
    assert movers == []


def test_coyote_moves_between_boards(base_state):
    pre = moved(base_state, lambda st: st.__setitem__("coyote", (1, "turtle")))
    post = moved(base_state, lambda st: st.__setitem__("coyote", (0, "rabbit")))
    _, hide, coy = A.plan(pre, post, {})
    assert coy is not None and coy[0] != coy[1] and "coyote" in hide


def test_unchanged_coyote_not_animated(base_state):
    pre = moved(base_state, lambda st: st.__setitem__("coyote", (1, "turtle")))
    _, hide, coy = A.plan(pre, copy.deepcopy(pre), {})
    assert coy is None and "coyote" not in hide


def test_plan_over_real_game_turns_is_consistent():
    g = E.Game(seed=4)
    log = g.play()
    for e in [x for x in log if x["type"] == "turn"][:12]:
        movers, hide, coy = A.plan(e["pre"], e["post"], {})
        for color, src, dst, order, kind in movers:
            assert color in R.STONE
            assert kind in ("shift", "board", "bonus", "bowl", "bag")
            assert len(src) == 3 and len(dst) == 3


def test_anim_frames_static_and_animated(base_state):
    final_only, sfx = A.anim_frames(base_state, copy.deepcopy(base_state), {})
    assert len(final_only) == 1 and final_only[0][1] == 1 and sfx == []

    def go(st):
        st["bowl"].remove("red")
        E.place(st["boards"][0], "red", ("rabbit", None))
    post = moved(base_state, go)
    frames, sfx = A.anim_frames(base_state, post, {})
    assert frames[-1][1] == 1 and all(n == 2 for _, n in frames[:-1])
    assert len(frames) > 5
    assert all(im.size == (R.W * R.S, R.H * R.S) for im, _ in frames)
    assert [k for _, k in sfx] == ["click"]   # one board stone; bowl shifts are silent


def test_anim_frames_sfx_for_coyote_and_spirit_stone(base_state):
    def go(st):
        st["bowl"].remove(E.CLEAR)
        E.place(st["boards"][0], E.CLEAR, ("turtle", "bonus"))
        st["coyote"] = (1, "owl")
    _, sfx = A.anim_frames(base_state, moved(base_state, go), {})
    kinds = sorted(k for _, k in sfx)
    assert kinds == ["chime", "yip"]


# =================================================================== audio
def test_ambient_length_range_and_fades():
    a = A.ambient(4.0)
    assert len(a) == int(4.0 * A.SR)
    assert np.isfinite(a).all() and np.abs(a).max() <= 1.0 + 1e-6
    assert abs(a[0]) < 0.01 and abs(a[-1]) < 0.01      # faded in / out
    assert np.abs(a).max() > 0.1


def test_ambient_long_clip_stays_normalised():
    a = A.ambient(20)
    assert len(a) == 20 * A.SR and np.abs(a).max() <= 1.0 + 1e-6


def test_sfx_bank():
    bank = A._sfx_bank()
    assert {"click", "chime", "yip", "card", "win"} <= set(bank)
    for k, v in bank.items():
        assert v.dtype == np.float32 and len(v) > 0, k
        assert np.isfinite(v).all() and np.abs(v).max() < 1.0, k
        assert np.abs(v).max() > 0.001, k


def test_every_sfx_used_by_videos_exists():
    import videos
    bank = A._sfx_bank()
    used = set()
    for fn in (videos.learn_to_play, videos.spirit_powers, videos.sample_game):
        for s in fn():
            used.update(s.get("sfx", []))
    assert used and used <= set(bank)


@pytest.mark.parametrize("t,s", [(0, "00:00:00,000"), (1.5, "00:00:01,500"),
                                 (61.25, "00:01:01,250"), (3661.5, "01:01:01,500")])
def test_srt_timestamp(t, s):
    assert A._ts(t) == s


def test_tts_uses_cache_without_kokoro(tmp_path, monkeypatch):
    import hashlib
    text = "hello board gamers"
    h = hashlib.sha1(f"{A.VOICE}|{A.SPEED}|{text}".encode()).hexdigest()[:16]
    audio = np.linspace(-1, 1, 100).astype(np.float32)
    np.save(tmp_path / f"{h}.npy", audio)
    monkeypatch.setattr(A, "_k", None)
    out = A.tts(text, tmp_path)           # must not try to import kokoro_onnx
    assert np.array_equal(out, audio)


def test_crop_output_size_and_zoom():
    im = R.title_card("x")
    assert A._crop(im, A.FULL).size == (R.W, R.H)
    assert A._crop(im, (100, 50, 800)).size == (R.W, R.H)


# ================================================================== build
class _SerialExecutor:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def map(self, fn, it):
        return map(fn, it)


def test_build_with_mocked_tts_and_ffmpeg(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(A, "tts", lambda text, d: np.full(A.SR // 2, 0.1, np.float32))
    monkeypatch.setattr(A.subprocess, "run", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(A, "ProcessPoolExecutor", _SerialExecutor)
    segs = [
        dict(text="First line.", image=R.title_card("A"), hold=0.2, sfx=["card"]),
        dict(text="", image=R.title_card("B"), hold=0.2),
        dict(text="Third.", image=R.title_card("C"), hold=0.2, cam=(100, 50, 800)),
    ]
    mp4 = A.build("demo", segs, tmp_path / "out", tmp_path / "work", music=False)
    assert mp4 == tmp_path / "out" / "demo.mp4"
    assert len(calls) == 1 and calls[0][0] == "ffmpeg" and str(mp4) in calls[0]
    srt = (tmp_path / "out" / "demo.srt").read_text()
    assert "First line." in srt and "Third." in srt
    assert srt.count("-->") == 2             # silent segment has no subtitle
    wav = tmp_path / "work" / "demo" / "audio.wav"
    assert wav.exists() and wav.stat().st_size > 1000
    lst = (tmp_path / "work" / "demo" / "frames.txt").read_text()
    assert lst.count("file '") >= 4 and "duration" in lst
    for line in lst.splitlines():
        if line.startswith("file '"):
            assert Path(line[6:-1]).exists()
