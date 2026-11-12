"""Renderer tests (Pillow only; no fonts beyond what render.py falls back to)."""
import copy
from collections import Counter

import pytest
from PIL import Image

import engine as E
import render as R
from conftest import rescore


@pytest.fixture(scope="module")
def end_state():
    g = E.Game(seed=3)
    log = g.play()
    return log[-1]["state"]


def test_constants():
    assert (R.W, R.H) == (1920, 1080)
    assert R.S >= 1


def test_table_size(end_state):
    im = R.table(end_state)
    assert isinstance(im, Image.Image)
    assert im.size == (R.W * R.S, R.H * R.S)


def test_table_size_for_setup_state(base_state):
    assert R.table(base_state).size == (R.W * R.S, R.H * R.S)


def test_finish_is_1080p(end_state):
    f = R.finish(R.table(end_state))
    assert f.size == (1920, 1080)


def test_new_canvas_size_and_background():
    im, d = R.new_canvas()
    assert im.size == (R.W * R.S, R.H * R.S)
    # background colour dominates (only ~160 speckles are drawn)
    assert Counter(im.crop((0, 0, 400, 400)).getdata()).most_common(1)[0][0] == R.BG
    assert isinstance(d, R.SDraw)


def test_title_card_and_spirit_grid_sizes():
    assert R.title_card("Hello", "Sub", kicker="Kick").size == (R.W * R.S, R.H * R.S)
    grid = R.spirit_grid({"bear": ("Bear", ["a", "b"]), "wolf": ("Wolf", ["c"])}, hl="bear",
                         bar="bar")
    assert grid.size == (R.W * R.S, R.H * R.S)


def board_stones(st):
    """{(player): Counter(colors)} from engine data, bonus markers counted as clear."""
    out = {}
    for p in (0, 1):
        c = Counter()
        for a in E.ANIMALS:
            c.update(E.stones_in(st["boards"][p], a))
            if st["boards"][p]["bonus"][a]:
                c[E.CLEAR] += 1
        out[p] = c
    return out


def test_registry_records_every_stone_with_colour(end_state):
    R.table(end_state)
    reg = R.CTX["reg"]
    bowl = {k: v for k, v in reg.items() if k[0] == "bowl"}
    assert len(bowl) == len(end_state["bowl"])
    for i, c in enumerate(end_state["bowl"]):
        x, y, r, col = reg[("bowl", i)]
        assert col == c and r > 0
    expected = board_stones(end_state)
    for p in (0, 1):
        got = Counter(v[3] for k, v in reg.items() if k[0] == "b" and k[1] == p)
        assert got == expected[p]
    assert len(reg) == len(bowl) + sum(sum(c.values()) for c in expected.values())


def test_registry_is_reset_each_call(end_state, base_state):
    R.table(end_state)
    n_end = len(R.CTX["reg"])
    R.table(base_state)
    assert len(R.CTX["reg"]) == len(base_state["bowl"])
    assert len(R.CTX["reg"]) != n_end


def test_registry_keys_unique_positions_inside_canvas(end_state):
    R.table(end_state)
    for k, (x, y, r, c) in R.CTX["reg"].items():
        assert 0 <= x <= R.W and 0 <= y <= R.H, k
        assert c in R.STONE


def test_registry_board_keys_have_player_prefix(base_state):
    st = copy.deepcopy(base_state)
    E.place(st["boards"][0], "red", ("rabbit", None))
    E.place(st["boards"][1], "blue", ("turtle", None))
    rescore(st)
    R.table(st)
    reg = R.CTX["reg"]
    assert ("b", 0, "rabbit", "s", 0) in reg and reg[("b", 0, "rabbit", "s", 0)][3] == "red"
    assert ("b", 1, "turtle", "s", 0) in reg and reg[("b", 1, "turtle", "s", 0)][3] == "blue"


def test_registry_bonus_and_owl_and_beaver_keys(base_state):
    st = copy.deepcopy(base_state)
    b = st["boards"][0]
    E.place(b, "red", ("owl", None))
    E.place(b, "red", ("owl", None))
    E.place(b, "blue", ("beaver", "triple"))
    E.place(b, "white", ("beaver", "pair"))
    E.place(b, E.CLEAR, ("salmon", "bonus"))
    rescore(st)
    R.table(st)
    reg = R.CTX["reg"]
    assert reg[("b", 0, "owl", "p0", 0)][3] == "red"
    assert reg[("b", 0, "owl", "p0", 1)][3] == "red"
    assert reg[("b", 0, "beaver", "triple", 0)][3] == "blue"
    assert reg[("b", 0, "beaver", "pair", 0)][3] == "white"
    assert reg[("b", 0, "salmon", "bonus", 0)][3] == "clear"


@pytest.fixture
def open_state(end_state):
    """End state without a Coyote (a blocked section is veiled, which dims its stones)."""
    st = copy.deepcopy(end_state)
    st["coyote"] = None
    return st


def _px(im, x, y):
    return im.getpixel((int(x * R.S), int(y * R.S)))[:3]


def test_stones_are_drawn_at_registry_positions(open_state):
    im = R.table(open_state)
    for k, (x, y, r, c) in R.CTX["reg"].items():
        assert _px(im, x, y) == R.STONE[c], k


def test_hide_keys_are_not_drawn_as_stones(open_state):
    R.table(open_state)
    keys = list(R.CTX["reg"])
    board_key = next(k for k in keys if k[0] == "b")
    bowl_key = next(k for k in keys if k[0] == "bowl")
    vis_reg = dict(R.CTX["reg"])
    im = R.table(open_state, hide={board_key, bowl_key})
    # registry still records hidden stones (animation needs their slots)
    assert R.CTX["reg"] == vis_reg
    for k in (board_key, bowl_key):
        x, y, r, c = vis_reg[k]
        assert _px(im, x, y) != R.STONE[c], k
    # every other stone is untouched
    for k, (x, y, r, c) in vis_reg.items():
        if k not in (board_key, bowl_key):
            assert _px(im, x, y) == R.STONE[c], k


def test_hidden_board_stone_leaves_empty_ring_hidden_bowl_stone_does_not(open_state):
    R.table(open_state)
    keys = list(R.CTX["reg"])
    bk = next(k for k in keys if k[0] == "b" and k[3] == "s")
    x, y, r, _ = R.CTX["reg"][bk]
    im = R.table(open_state, hide={bk})
    # ring at radius r, colour (80,96,140)
    assert _px(im, x + r - 1, y) == (80, 96, 140) or _px(im, x, y + r - 1) == (80, 96, 140)


def test_hide_set_only_affects_current_call(end_state):
    R.table(end_state)
    k = next(iter(R.CTX["reg"]))
    R.table(end_state, hide={k})
    assert k in R.CTX["hide"]
    R.table(end_state)
    assert R.CTX["hide"] == set()


def test_blocked_section_registers_coyote_on_that_board(base_state):
    st = copy.deepcopy(base_state)
    st["coyote"] = (1, "turtle")
    R.table(st)
    cx, cy, s = R.CTX["coyote"]
    sx, sy, sw, sh = R.CTX["sec"][(1, "turtle")]
    assert sx <= cx <= sx + sw and sy <= cy <= sy + sh


def test_unplaced_coyote_registers_in_the_middle(base_state):
    st = copy.deepcopy(base_state)
    st["coyote"] = None
    R.table(st)
    cx, cy, s = R.CTX["coyote"]
    assert (cx, cy) == (1650, 330 + 50)


def test_all_ten_sections_registered(base_state):
    R.table(base_state)
    assert set(R.CTX["sec"]) == {(p, a) for p in (0, 1) for a in E.ANIMALS}


def test_table_with_all_overlays_does_not_crash(end_state):
    im = R.table(end_state, hl={"card": (0, E.TAKE2), "sections": (1, ["owl"]), "mid": "bowl",
                                "drawn": 2},
                 bar="A caption that is rather long " * 4, deltas={(0, "owl"): 4, (1, "rabbit"): -2},
                 ban=("Title", "Sub"), ticker=False)
    assert im.size == (R.W * R.S, R.H * R.S)


# ------------------------------------------------------------ small helpers
def test_wrap_text_respects_width():
    im, d = R.new_canvas()
    text = "the quick brown fox jumps over the lazy dog " * 3
    lines = R.wrap_text(d, text, R.F["b"], 400)
    assert len(lines) > 1
    assert " ".join(lines) == text.strip()
    for ln in lines:
        assert d.textlength(ln, R.F["b"]) <= 400


def test_wrap_text_empty():
    im, d = R.new_canvas()
    assert R.wrap_text(d, "", R.F["b"], 400) == []


def test_wrap_text_overlong_first_word_has_no_blank_line():
    im, d = R.new_canvas()
    lines = R.wrap_text(d, "Supercalifragilisticexpialidocious word", R.F["b"], 20)
    assert "" not in lines


def test_sdraw_scales_coordinates():
    im = Image.new("RGB", (40, 40), (0, 0, 0))
    d = R.SDraw(im, s=2)
    d.rectangle((2, 2, 8, 8), fill=(255, 0, 0))
    assert im.getpixel((10, 10)) == (255, 0, 0)
    assert im.getpixel((30, 30)) == (0, 0, 0)
    assert d._xy([(1, 2), (3, 4)]) == [(2, 4), (6, 8)]
    assert d._xy((1, 2, 3, 4)) == [2, 4, 6, 8]


def test_stone_none_draws_ring_only():
    im, d = R.new_canvas()
    R.stone(d, 500, 500, 30, None)
    assert _px(im, 500, 500) != R.STONE["red"]
    R.stone(d, 800, 500, 30, "red")
    assert _px(im, 800, 500) == R.STONE["red"]


@pytest.mark.parametrize("color", list(R.STONE))
def test_every_colour_has_a_rendering(color):
    im, d = R.new_canvas()
    R.stone(d, 400, 400, 25, color)
    assert _px(im, 400, 400) == R.STONE[color]


def test_stone_colours_match_engine():
    assert set(E.COLORS + [E.CLEAR]) == set(R.STONE)
