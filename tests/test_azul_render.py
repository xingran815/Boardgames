"""Azul video renderer: tile designs, table layout, registry and cards."""
import copy
import importlib.util
import sys
from itertools import combinations
from pathlib import Path

import pytest
from PIL import Image

AZUL = Path(__file__).resolve().parents[1] / "tools" / "azul"


def load(name):
    """Load tools/azul/<name>.py as 'azul_<name>' (the name the modules use themselves),
    so it never clashes with the Spirits of the Wild modules on sys.path."""
    full = f"azul_{name}"
    if full not in sys.modules:
        spec = importlib.util.spec_from_file_location(full, AZUL / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[full] = mod
        spec.loader.exec_module(mod)
    return sys.modules[full]


R = load("render")
E = R.E


def game_state(seed=4, turns=6):
    """A real mid-round state from the engine (offer phase, some tiles taken)."""
    g = E.Game(2, seed)
    log = g.play()
    t = [e for e in log if e["type"] == "turn"]
    return copy.deepcopy(t[turns]["post"])


def late_state(seed=4):
    g = E.Game(2, seed)
    log = g.play()
    return copy.deepcopy([e for e in log if e["type"] == "tiling"][-2]["state"])


def boxes_overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def inside(box, outer=(0, 0, R.W, R.H)):
    return outer[0] <= box[0] and outer[1] <= box[1] and box[2] <= outer[2] and box[3] <= outer[3]


# ================================================================ style
class TestTileStyle:
    def test_fill_colours_follow_style_md(self):
        style = (Path(__file__).resolve().parents[1] / "docs" / "azul" / "STYLE.md").read_text()
        for c, rgb in R.FILL.items():
            hexs = "#%02X%02X%02X" % rgb
            assert hexs in style, (c, hexs)

    def test_every_engine_colour_has_a_design(self):
        assert set(R.FILL) == set(E.COLOURS) == set(R.EDGE) == set(R.MARK_INK)

    def _tile_image(self, colour, **kw):
        im = Image.new("RGB", (240, 240), R.BG)
        R.tile(R.SDraw(im, 1), 120, 120, 160, colour, **kw)
        return im

    def test_marks_differ_even_in_greyscale(self):
        """Colour is never the only cue: each tile differs from every other in black and white."""
        grey = {c: self._tile_image(c).convert("L") for c in E.COLOURS}
        for a, b in combinations(E.COLOURS, 2):
            diff = sum(1 for p, q in zip(grey[a].getdata(), grey[b].getdata()) if abs(p - q) > 40)
            assert diff > 500, (a, b, diff)

    def test_faint_wall_space_is_paler_than_the_tile(self):
        for c in ("blue", "red", "black"):
            full = self._tile_image(c).getpixel((185, 120))
            faint = self._tile_image(c, faint=True).getpixel((185, 120))
            assert sum(abs(x - y) for x, y in zip(full, R.FILL[c])) < 40
            assert faint != full

    def test_marker_tile_is_not_a_colour_tile(self):
        im = self._tile_image(E.MARKER)
        for c in E.COLOURS:
            assert list(im.getdata()) != list(self._tile_image(c).getdata())


# =============================================================== layout
class TestLayout:
    def test_board_boxes_are_inside_and_apart(self):
        a, b = R.board_box(0), R.board_box(1)
        assert inside(a) and inside(b) and not boxes_overlap(a, b)

    def test_factories_do_not_overlap_anything(self):
        n = E.FACTORIES[2]
        fs = [R.factory_box(i) for i in range(n)]
        for i, j in combinations(range(n), 2):      # discs: compare centre distances
            (x1, y1), (x2, y2) = R.factory_xy(i), R.factory_xy(j)
            assert ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5 > 2 * R.FACT_R + 4, (i, j)
        for f in fs:
            assert inside(f)
            for other in (R.CENTRE_BOX, R.BAG_BOX, R.LID_BOX, R.board_box(0), R.board_box(1)):
                assert not boxes_overlap(f, other), (f, other)

    def test_centre_holds_every_tile_a_two_player_round_can_push(self):
        # 5 displays x 3 pushed tiles + the starting player marker
        need = E.FACTORIES[2] * (E.TILES_PER_FACTORY - 1) + 1
        for j in range(need):
            x, y = R.centre_slot(j)
            box = (x - R.FT / 2, y - R.FT / 2, x + R.FT / 2, y + R.FT / 2)
            assert inside(box, R.CENTRE_BOX), j

    def test_lid_slots_inside_the_lid(self):
        for j in range(R.LID_SLOTS):
            x, y = R.lid_slot(j)
            assert inside((x - R.LT / 2, y - R.LT / 2, x + R.LT / 2, y + R.LT / 2), R.LID_BOX)

    @pytest.mark.parametrize("p", [0, 1])
    def test_board_parts_inside_their_board(self, p):
        bb = R.board_box(p)
        for box in (R.lines_box(p), R.wall_box(p), R.floor_box(p), R.score_box(p)):
            assert inside(box, bb), box
        assert not boxes_overlap(R.lines_box(p), R.wall_box(p))
        assert not boxes_overlap(R.wall_box(p), R.floor_box(p))

    @pytest.mark.parametrize("p", [0, 1])
    def test_pattern_lines_fill_right_to_left_next_to_the_wall(self, p):
        for r in range(5):
            xs = [R.line_xy(p, r, k)[0] for k in range(r + 1)]
            assert xs == sorted(xs, reverse=True)       # slot 0 is the rightmost
            assert R.line_xy(p, r, 0)[1] == R.wall_xy(p, r, 0)[1]   # same height as its wall row
        assert R.line_xy(p, 0, 0)[0] == R.line_xy(p, 4, 0)[0]       # staircase aligned right

    def test_row_and_column_boxes_cover_their_cells(self):
        for r in range(5):
            for c in range(5):
                cb = R.cell_box(0, r, c, 0)
                assert inside(cb, R.wall_row_box(0, r)) and inside(cb, R.wall_col_box(0, c))


# ============================================================ drawing
class TestTable:
    def test_size_is_supersampled(self):
        im = R.table(game_state())
        assert im.size == (R.W * R.S, R.H * R.S)

    def test_registry_lists_every_tile(self):
        st = late_state()
        R.table(st)
        reg = R.CTX["reg"]
        expect = sum(len(f) for f in st["factories"]) + len(st["centre"])
        expect += min(len(st["lid"]), R.LID_SLOTS)
        for b in st["boards"]:
            expect += sum(pl["count"] for pl in b["lines"])
            expect += sum(1 for row in b["wall"] for t in row if t)
            expect += sum(1 for t in b["floor"] if t != E.MARKER)
        tiles = [k for k in reg if k != ("m",)]
        assert len(tiles) == expect
        assert ("m",) in reg   # held by the next starting player

    def test_registry_colours_match_the_state(self):
        st = game_state()
        R.table(st)
        reg = R.CTX["reg"]
        for p, b in enumerate(st["boards"]):
            for r in range(5):
                for c in range(5):
                    if b["wall"][r][c]:
                        assert reg[("p", p, "wall", r, c)][3] == b["wall"][r][c]
                for k in range(b["lines"][r]["count"]):
                    assert reg[("p", p, "line", r, k)][3] == b["lines"][r]["colour"]
        for i, f in enumerate(st["factories"]):
            assert [reg[("f", i, j)][3] for j in range(len(f))] == f
        centre = sorted(st["centre"], key=E.COLOURS.index)
        assert [reg[("c", i)][3] for i in range(len(centre))] == centre

    def test_marker_position_follows_the_rules(self):
        st = E.new_game(2, 3)
        R.table(st)
        assert R.CTX["reg"][("m",)][:2] == R.centre_slot(0)
        st2 = copy.deepcopy(st)
        st2["centre_marker"], st2["marker_holder"] = False, 1
        R.table(st2)
        assert R.CTX["reg"][("m",)][:2] == R.marker_home(1)
        st3 = copy.deepcopy(st2)
        st3["boards"][0]["floor"] = [E.MARKER]
        R.table(st3)
        assert R.CTX["reg"][("m",)][:2] == R.floor_xy(0, 0)

    def test_hidden_tiles_are_not_drawn(self):
        st = game_state()
        a = R.table(st)
        key = next(k for k in R.CTX["reg"] if k[0] == "f")
        b = R.table(st, hide={key})
        assert a.tobytes() != b.tobytes()
        assert key in R.CTX["reg"]       # still registered, so it can be animated in

    def test_show_subset_draws_less(self):
        st = game_state()
        R.table(st, show=["board0"])
        assert all(k[0] == "p" and k[1] == 0 for k in R.CTX["reg"] if k != ("m",))

    def test_grey_wall_spaces_have_no_colour(self):
        st = E.new_game(2, 1, E.GREY)
        im = R.table(st).resize((R.W, R.H))
        for c in range(5):
            x, y = R.wall_xy(0, 2, c)
            px = im.getpixel((int(x - R.T * 0.35), int(y - R.T * 0.35)))
            assert sum(abs(a - b) for a, b in zip(px, R.GREY_SPACE)) < 30, (c, px)

    def test_highlights_and_crosses_change_the_picture(self):
        st = game_state()
        plain = R.table(st).tobytes()
        for hl in ({"lines": {0: [2]}}, {"cells": {1: [(0, 0)]}}, {"floor": 0},
                   {"factories": [1]}, {"centre": True}, {"mid": "bag"}, {"score": 1},
                   {"xs": [("line", 0, 1)]}, {"xs": [("cell", 1, 2, 2)]}):
            assert R.table(st, hl=hl).tobytes() != plain, hl

    def test_table_ignores_animation_hints(self):
        st = game_state()
        assert R.table(st, src_xy=(1, 2)).size == (R.W * R.S, R.H * R.S)


# ================================================================ cards
class TestCards:
    def test_cards_render(self):
        for im in (R.title_card("Taking tiles", "One colour", kicker="Azul · Episode 3"),
                   R.recap_card(["a", "b", "c"], "Next one"), R.tiles_card(), R.tiles_card(True),
                   R.factories_card(), R.factories_card(hl=3), R.marker_card()):
            assert im.size == (R.W * R.S, R.H * R.S)

    def test_factories_card_counts_come_from_the_engine(self, monkeypatch):
        a = R.factories_card().tobytes()
        monkeypatch.setitem(E.FACTORIES, 4, 8)
        assert R.factories_card().tobytes() != a

    def test_wrap_text(self):
        d = R.SDraw(R.new_canvas()[0], 1)
        lines = R.wrap_text(d, "one two three four five six seven", R.F["h2"], 200)
        assert len(lines) > 1 and " ".join(lines) == "one two three four five six seven"
        assert R.wrap_text(d, "", R.F["h2"], 200) == []
