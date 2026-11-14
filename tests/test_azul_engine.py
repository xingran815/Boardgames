"""Azul rules-engine tests.

Worked examples are taken from the photographed German rulebook (pages 3-6);
the page is named in each test. Then edge cases and whole-game sweeps.
"""
import copy
import importlib.util
from collections import Counter
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "tools" / "azul" / "engine.py"
_spec = importlib.util.spec_from_file_location("azul_engine", _PATH)
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)

B, Y, R, K, W = A.COLOURS  # blue yellow red black white
SWEEP = [(n, s, v) for v in (A.COLOURED, A.GREY) for n in (2, 3, 4) for s in range(25)]


def W_(*rows):
    """Wall from 5 strings ('.' empty, any letter = tile at that printed space)."""
    return A.wall_from_rows(list(rows) + ["....."] * (5 - len(rows)))


def put(wall, row, colour):
    """Place a tile on the coloured wall and return its points."""
    col = A.wall_column(row, colour)
    wall[row][col] = colour
    return A.score_placement(wall, row, col)


def state_with(n=2, variant=A.COLOURED, factories=None, centre=(), marker=True, current=0):
    """A hand-made offer-phase state; leftover tiles go in the bag."""
    st = A.new_state(n, seed=0, variant=variant)
    st["round"], st["phase"], st["current"], st["start_player"] = 1, "offer", current, 0
    st["marker_holder"] = None
    st["centre_marker"] = marker
    fs = factories or []
    st["factories"] = [list(f) for f in fs] + [[] for _ in range(A.FACTORIES[n] - len(fs))]
    st["centre"] = list(centre)
    pool = Counter({c: 20 for c in A.COLOURS})
    pool.subtract(Counter([t for f in fs for t in f] + list(centre)))
    st["bag"] = [c for c in A.COLOURS for _ in range(pool[c])]
    return st


@pytest.fixture(scope="module")
def games():
    out = {}
    for n, s, v in SWEEP:
        g = A.Game(n, s, v)
        out[(n, s, v)] = (g, g.play())
    return out


# ============================================================ components
class TestComponents:
    def test_counts(self):
        assert A.TOTAL_TILES == 100 and A.TILES_PER_COLOUR == 20 and len(A.COLOURS) == 5
        assert A.FACTORIES == {2: 5, 3: 7, 4: 9}
        assert A.TILES_PER_FACTORY == 4
        assert A.FLOOR_VALUES == (-1, -1, -2, -2, -2, -3, -3)
        assert (A.ROW_BONUS, A.COLUMN_BONUS, A.COLOUR_BONUS) == (2, 7, 10)

    def test_letters_unique(self):
        assert sorted(A.LETTERS.values()) == sorted("BYRKW")

    def test_wall_pattern_matches_board_photo(self):
        # Read off the coloured board (rulebook p.2 and the board photo).
        assert A.wall_to_rows([[A.wall_colour(r, c) for c in range(5)] for r in range(5)]) == [
            "BYRKW", "WBYRK", "KWBYR", "RKWBY", "YRKWB"]

    def test_wall_is_latin_square(self):
        for i in range(5):
            assert {A.wall_colour(i, c) for c in range(5)} == set(A.COLOURS)
            assert {A.wall_colour(r, i) for r in range(5)} == set(A.COLOURS)

    @pytest.mark.parametrize("row", range(5))
    def test_wall_column_inverse(self, row):
        for c in A.COLOURS:
            assert A.wall_colour(row, A.wall_column(row, c)) == c


# ============================================================ setup
class TestSetup:
    @pytest.mark.parametrize("n,f", [(2, 5), (3, 7), (4, 9)])
    def test_factories_filled(self, n, f):
        st = A.new_game(n, seed=3)
        assert len(st["factories"]) == f
        assert all(len(x) == 4 for x in st["factories"])
        assert len(st["bag"]) == 100 - 4 * f
        assert st["centre"] == [] and st["centre_marker"] is True
        assert A.count_tiles(st) == 100

    @pytest.mark.parametrize("n", [2, 3, 4])
    def test_everyone_same_empty_board(self, n):
        st = A.new_game(n, seed=1)
        for b in st["boards"]:
            assert b == st["boards"][0]
            assert b["score"] == 0 and b["floor"] == []

    @pytest.mark.parametrize("n", [1, 5])
    def test_bad_player_count(self, n):
        with pytest.raises(ValueError):
            A.new_game(n)

    def test_same_seed_same_setup(self):
        assert A.new_game(3, seed=9)["factories"] == A.new_game(3, seed=9)["factories"]
        assert A.new_game(3, seed=9)["factories"] != A.new_game(3, seed=10)["factories"]

    def test_first_player_starts(self):
        st = A.new_game(4, seed=0, first_player=2)
        assert st["current"] == 2 and st["start_player"] == 2


# ============================================================ scoring maths
class TestScorePlacement:
    def test_p5_lone_tile_1_point(self):
        # p.5: the red tile has no neighbours -> 1 point.
        w = A.empty_wall()
        assert put(w, 1, R) == 1

    def test_p5_horizontal_group_3(self):
        # p.5: yellow joins red + black on its right in row 2 -> 3 points.
        w = W_(".Y...", "W..RK", ".....", ".K...", "...WB")
        assert put(w, 1, Y) == 3

    def test_p5_vertical_group_2(self):
        # p.5: blue lands under the yellow in column 3 -> 2 points.
        w = W_(".Y.KW", "W.YRK", ".....", ".K...", "...WB")
        assert put(w, 2, B) == 2

    def test_p5_cross_7(self):
        # p.5: yellow in row 3 makes a row group of 4 and a column group of 3
        # -> 4 + 3 = 7 points.
        w = W_(".Y.KW", "W.YRK", ".WB.R", ".....", ".....")
        assert put(w, 2, Y) == 7

    def test_p4_peter_two_lone_tiles(self):
        # p.4: Peter's red (row 2) and blue (row 4) each score 1.
        w = A.empty_wall()
        assert put(w, 1, R) == 1
        assert put(w, 3, B) == 1

    def test_gap_breaks_group(self):
        w = W_("BY.KW")
        assert put(w, 0, R) == 5
        w = W_("B..KW")
        assert put(w, 0, Y) == 2  # Y joins B only; the gap stops the count

    def test_full_cross(self):
        w = W_("..X..", "..X..", "XXXXX", "..X..", "..X..")
        w[2][2] = None
        assert A.score_placement(w, 2, 2) == 10

    def test_wall_with_or_without_new_tile(self):
        w = W_("BY...")
        a = A.score_placement(w, 0, 2)
        w[0][2] = R
        assert a == A.score_placement(w, 0, 2) == 3

    @pytest.mark.parametrize("n,pen", [(0, 0), (1, -1), (2, -2), (3, -4), (4, -6),
                                       (5, -8), (6, -11), (7, -14), (8, -14), (12, -14)])
    def test_floor_penalty(self, n, pen):
        assert A.floor_penalty(n) == pen

    def test_p5_peter_floor_minus_8(self):
        # p.5: 4 tiles + the starting player marker on the floor -> -8.
        assert A.floor_penalty(5) == -8


class TestEndBonus:
    def test_empty(self):
        assert A.end_bonus(A.empty_wall()) == 0

    def test_row(self):
        assert A.bonus_breakdown(W_("BYRKW"))["row_points"] == 2
        assert A.end_bonus(W_("BYRKW")) == 2

    def test_column(self):
        w = W_("X....", "X....", "X....", "X....", "X....")
        assert A.bonus_breakdown(w) == {"rows": 0, "columns": 1, "colours": 0,
                                        "row_points": 0, "column_points": 7,
                                        "colour_points": 0, "total": 7}

    def test_colour(self):
        # All 5 blue tiles sit on the diagonal of the coloured wall.
        w = W_("B....", ".B...", "..B..", "...B.", "....B")
        assert A.end_bonus(w) == 10

    def test_full_wall(self):
        w = W_(*["XXXXX"] * 5)
        assert A.end_bonus(w) == 5 * 2 + 5 * 7 + 5 * 10 == 95

    def test_complete_rows_counts_only_full_rows(self):
        w = W_("BYRKW", "WBYR.", "KWBYR")
        assert A.complete_rows(w) == 2


# ============================================================ drafting
class TestFactoryOffer:
    def test_take_from_factory_pushes_rest_to_centre(self):
        # p.3 example 1: Peter takes 2 black, the rest goes to the centre.
        st = state_with(factories=[[K, K, Y, W]])
        info = A.apply_move(st, A.Move(0, K, 1))
        assert info["taken"] == 2 and info["pushed"] == 2
        assert sorted(st["centre"]) == sorted([Y, W])
        assert st["factories"][0] == []
        assert st["boards"][0]["lines"][1] == {"colour": K, "count": 2}
        assert st["centre_marker"] and st["current"] == 1

    def test_first_from_centre_takes_marker(self):
        # p.3 example 3: Andrea takes 3 red from the centre and, being first
        # to take from the centre, the marker goes to her floor's left space.
        st = state_with(n=3, factories=[[B, B, B, B]], centre=[R, R, R, Y, W], current=2)
        info = A.apply_move(st, A.Move(A.CENTRE, R, 4))
        assert info["took_marker"] and info["taken"] == 3
        b = st["boards"][2]
        assert b["floor"] == [A.MARKER]
        assert b["lines"][4] == {"colour": R, "count": 3}
        assert sorted(st["centre"]) == sorted([Y, W])
        assert not st["centre_marker"] and st["marker_holder"] == 2

    def test_second_from_centre_no_marker(self):
        st = state_with(factories=[[B, B, B, B]], centre=[R, Y, Y])
        A.apply_move(st, A.Move(A.CENTRE, R, 0))
        A.apply_move(st, A.Move(A.CENTRE, Y, 1))
        assert st["boards"][1]["floor"] == []
        assert st["marker_holder"] == 0

    def test_p4_andrea_legal_targets(self):
        # p.4: yellow already on wall rows 2 and 3; line 4 holds a blue.
        st = state_with(factories=[[Y, Y, B, R]])
        b = st["boards"][0]
        b["wall"] = W_(".....", "..Y..", "...Y.")
        b["lines"][3] = {"colour": B, "count": 1}
        lines = {m.line for m in A.legal_moves(st) if m.source == 0 and m.colour == Y}
        assert lines == {0, 4, A.FLOOR}

    def test_p4_andrea_option_a_overflow(self):
        st = state_with(factories=[[Y, Y, B, R]])
        info = A.apply_move(st, A.Move(0, Y, 0))
        assert info["placed"] == 1 and info["to_floor"] == 1
        assert st["boards"][0]["floor"] == [Y]

    def test_p4_andrea_option_c_all_to_floor(self):
        st = state_with(factories=[[Y, Y, B, R]])
        A.apply_move(st, A.Move(0, Y, A.FLOOR))
        assert st["boards"][0]["floor"] == [Y, Y]

    def test_cannot_mix_colours_in_a_line(self):
        st = state_with(factories=[[R, R, B, B]])
        st["boards"][0]["lines"][2] = {"colour": B, "count": 1}
        assert A.Move(0, R, 2) not in A.legal_moves(st)
        assert A.Move(0, B, 2) in A.legal_moves(st)

    def test_full_line_is_not_a_target(self):
        st = state_with(factories=[[R, R, B, B]])
        st["boards"][0]["lines"][1] = {"colour": R, "count": 2}
        assert A.Move(0, R, 1) not in A.legal_moves(st)

    def test_illegal_move_rejected(self):
        st = state_with(factories=[[R, R, B, B]])
        with pytest.raises(ValueError):
            A.apply_move(st, A.Move(0, Y, 0))   # no yellow there
        with pytest.raises(ValueError):
            A.apply_move(st, A.Move(A.CENTRE, R, 0))  # centre empty

    def test_marker_alone_is_not_a_source(self):
        st = state_with(factories=[[R, R, B, B]], centre=[])
        assert all(m.source != A.CENTRE for m in A.legal_moves(st))

    def test_floor_overflow_goes_to_lid(self):
        st = state_with(factories=[[R, R, R, R]], centre=[B, B, B, B, B])
        st["boards"][0]["floor"] = [K, K, K, K]
        info = A.apply_move(st, A.Move(A.CENTRE, B, A.FLOOR))
        b = st["boards"][0]
        # marker first (5th space), then 2 blue fill spaces 6-7, 3 blue to lid
        assert b["floor"] == [K, K, K, K, A.MARKER, B, B]
        assert info["to_floor"] == 2 and info["to_lid"] == 3
        assert st["lid"] == [B, B, B]

    def test_full_floor_marker_kept_beside_board(self):
        st = state_with(factories=[[R, R, R, R]], centre=[B])
        st["boards"][0]["floor"] = [K] * 7
        info = A.apply_move(st, A.Move(A.CENTRE, B, 0))
        assert info.get("marker_beside_board")
        assert st["boards"][0]["floor"] == [K] * 7
        assert st["marker_holder"] == 0

    def test_phase_ends_when_all_empty(self):
        st = state_with(factories=[[R, R, B, B]])
        A.apply_move(st, A.Move(0, R, 1))
        assert st["phase"] == "offer"
        A.apply_move(st, A.Move(A.CENTRE, B, 1))
        assert st["phase"] == "tiling"


# ============================================================ wall-tiling
class TestWallTiling:
    def test_p4_peter_example(self):
        # p.4: lines 2 (2 red) and 4 (4 blue) complete; 3 and 5 not.
        st = state_with()
        st["phase"] = "tiling"
        b = st["boards"][0]
        b["lines"] = [{"colour": None, "count": 0}, {"colour": R, "count": 2},
                      {"colour": B, "count": 2}, {"colour": B, "count": 4},
                      {"colour": Y, "count": 3}]
        res = A.tile_walls(st)[0]
        assert [(p["row"], p["colour"], p["points"]) for p in res["placements"]] == [
            (1, R, 1), (3, B, 1)]
        assert b["score"] == 2
        assert b["wall"][1][3] == R and b["wall"][3][3] == B
        # leftover tiles of the completed lines went to the lid (1 red + 3 blue)
        assert sorted(st["lid"]) == sorted([R, B, B, B])
        # incomplete lines stay for next round
        assert b["lines"][2] == {"colour": B, "count": 2}
        assert b["lines"][4] == {"colour": Y, "count": 3}
        assert b["lines"][1]["count"] == 0 and b["lines"][3]["count"] == 0

    def test_top_to_bottom_order_matters(self):
        # Rows are tiled from the top: row 1's tile is already there when
        # row 2's tile is scored.
        st = state_with()
        st["phase"] = "tiling"
        b = st["boards"][0]
        b["lines"][0] = {"colour": Y, "count": 1}  # row 1, column 2
        b["lines"][1] = {"colour": B, "count": 2}  # row 2, column 2
        res = A.tile_walls(st)[0]
        assert [p["points"] for p in res["placements"]] == [1, 2]

    def test_floor_penalty_and_clamp_at_zero(self):
        st = state_with()
        st["phase"] = "tiling"
        b = st["boards"][0]
        b["score"] = 3
        b["floor"] = [R, R, R, A.MARKER, R]
        res = A.tile_walls(st)[0]
        assert res["floor_penalty"] == -8
        assert b["score"] == 0  # never below 0
        assert b["floor"] == [] and st["lid"].count(R) == 4  # marker not in lid

    def test_p5_peter_floor(self):
        st = state_with()
        st["phase"] = "tiling"
        b = st["boards"][0]
        b["score"] = 20
        b["floor"] = [B, A.MARKER, W, W, Y]
        A.tile_walls(st)
        assert b["score"] == 12

    def test_marker_holder_starts_next_round(self):
        st = state_with(factories=[[R, B, B, B]], current=0)
        A.apply_move(st, A.Move(0, B, 2))         # P0, red -> centre
        A.apply_move(st, A.Move(A.CENTRE, R, 0))  # P1 takes marker
        A.tile_walls(st)
        assert st["marker_holder"] == 1
        A.start_round(st)
        assert st["start_player"] == 1 and st["current"] == 1 and st["centre_marker"]

    def test_nobody_took_marker_same_start_player(self):
        st = state_with(factories=[[R] * 4, [B] * 4], current=0)
        A.apply_move(st, A.Move(0, R, 3))
        A.apply_move(st, A.Move(1, B, 3))
        A.tile_walls(st)
        assert st["marker_holder"] == 0

    def test_lid_refill_when_bag_empty(self):
        # p.5: when the bag runs out while filling, refill it from the lid
        # and keep filling.
        st = state_with(factories=[])
        st["bag"] = [R, R, R, R, R, R]           # enough for 1.5 factories
        st["lid"] = [B] * 60 + [Y] * 34
        A.fill_factories(st)
        assert all(len(f) == 4 for f in st["factories"])
        assert st["lid"] == [] and st["refills"] == 1
        assert Counter(t for f in st["factories"] for t in f)[R] == 6
        assert A.count_tiles(st) == 100

    def test_bag_and_lid_empty_partial_factories(self):
        # p.5: rare case - start the round with some factories short.
        st = state_with(factories=[])
        st["bag"] = [R] * 6
        st["lid"] = []
        A.fill_factories(st)
        assert [len(f) for f in st["factories"]] == [4, 2, 0, 0, 0]

    def test_no_refill_when_bag_not_empty(self):
        st = state_with(factories=[])
        st["bag"] = [R] * 30
        st["lid"] = [B] * 5
        A.fill_factories(st)
        assert st["lid"] == [B] * 5 and len(st["bag"]) == 10


# ============================================================ end of game
class TestEndOfGame:
    def _tiling_state(self, n=2):
        st = state_with(n=n)
        st["phase"] = "tiling"
        return st

    def test_full_row_ends_at_end_of_round(self):
        st = self._tiling_state()
        b = st["boards"][0]
        b["wall"] = W_("BYRK.")
        b["lines"][0] = {"colour": W, "count": 1}
        A.tile_walls(st)
        assert st["game_over"] and st["phase"] == "over"
        # row 0 placed W: run of 5 -> 5 points, then +2 row bonus
        assert b["score"] == 5 + 2
        assert st["bonuses"][0]["rows"] == 1

    def test_no_full_row_continues(self):
        st = self._tiling_state()
        st["boards"][0]["wall"] = W_("BYR..")
        A.tile_walls(st)
        assert not st["game_over"] and st["phase"] == "prepare"

    def test_full_column_alone_does_not_end(self):
        st = self._tiling_state()
        st["boards"][0]["wall"] = W_("B....", "W....", "K....", "R....", "Y....")
        A.tile_walls(st)
        assert not st["game_over"]

    def test_floor_applied_before_bonus(self):
        st = self._tiling_state()
        b = st["boards"][0]
        b["wall"] = W_("BYRKW")
        b["score"] = 1
        b["floor"] = [R, R, R]
        A.tile_walls(st)
        assert b["score"] == 0 + 2  # clamp to 0 first, then +2

    def test_tie_break_most_rows(self):
        st = self._tiling_state(3)
        st["phase"] = "over"
        bs = st["boards"]
        bs[0]["score"], bs[0]["wall"] = 40, W_("BYRKW")
        bs[1]["score"], bs[1]["wall"] = 40, W_("BYRKW", "WBYRK")
        bs[2]["score"], bs[2]["wall"] = 39, W_("BYRKW", "WBYRK", "KWBYR")
        assert A.winners(st) == [1]

    def test_tie_still_tied_shared(self):
        st = self._tiling_state()
        bs = st["boards"]
        bs[0]["score"] = bs[1]["score"] = 50
        bs[0]["wall"] = W_("BYRKW")
        bs[1]["wall"] = W_(".....", "WBYRK")
        assert A.winners(st) == [0, 1]

    def test_clear_winner(self):
        st = self._tiling_state()
        st["boards"][1]["score"] = 1
        assert A.winners(st) == [1]


# ============================================================ grey variant
class TestGreyVariant:
    def test_any_free_column(self):
        w = A.empty_wall()
        assert A.grey_columns(w, 0, R) == [0, 1, 2, 3, 4]

    def test_colour_once_per_column_and_row(self):
        w = A.empty_wall()
        w[0][2] = R
        assert A.grey_columns(w, 1, R) == [0, 1, 3, 4]
        assert A.grey_columns(w, 0, R) == []

    def test_draft_still_blocks_colour_in_row(self):
        st = state_with(variant=A.GREY, factories=[[R, R, B, B]])
        st["boards"][0]["wall"][2][0] = R
        assert A.Move(0, R, 2) not in A.legal_moves(st)

    def test_special_case_whole_line_to_floor(self):
        # p.6: if the rightmost tile can't legally go on the wall, all tiles
        # of that line go to the floor.
        st = state_with(variant=A.GREY)
        st["phase"] = "tiling"
        b = st["boards"][0]
        # row 2 (index 1): free spaces only in columns that already hold red
        b["wall"] = [[None] * 5 for _ in range(5)]
        b["wall"][0] = [R, None, None, None, None]
        b["wall"][2] = [None, R, None, None, None]
        b["wall"][1] = [None, None, B, Y, K]
        b["lines"][1] = {"colour": R, "count": 2}
        res = A.tile_walls(st)[0]
        assert res["placements"] == [{"row": 1, "colour": R, "col": None,
                                      "points": 0, "to_floor": 2}]
        assert res["floor_items"] == 2 and res["floor_penalty"] == -2
        assert st["lid"].count(R) == 2

    def test_chooser_used(self):
        st = state_with(variant=A.GREY)
        st["phase"] = "tiling"
        st["boards"][0]["lines"][0] = {"colour": R, "count": 1}
        A.tile_walls(st, choose_column=lambda s, p, r, c, opts: opts[-1])
        assert st["boards"][0]["wall"][0][4] == R

    def test_default_chooser_takes_most_points(self):
        w = A.empty_wall()
        w[0][3] = B
        assert A.best_grey_column(w, 0, R) in (2, 4)
        assert A.score_placement(w, 0, A.best_grey_column(w, 0, R)) == 2

    def test_illegal_chooser_rejected(self):
        st = state_with(variant=A.GREY)
        st["phase"] = "tiling"
        st["boards"][0]["wall"][1][0] = R
        st["boards"][0]["lines"][0] = {"colour": R, "count": 1}
        with pytest.raises(ValueError):
            A.tile_walls(st, choose_column=lambda *a: 0)


# ============================================================ whole games
def _states(log):
    for e in log:
        if e["type"] == "turn":
            yield e["post"]
        else:
            yield e["state"]


class TestGames:
    def test_deterministic(self):
        a = A.Game(3, 42).play()
        b = A.Game(3, 42).play()
        assert [e.get("move") for e in a] == [e.get("move") for e in b]
        assert a[-1]["scores"] == b[-1]["scores"]

    def test_different_seeds_differ(self):
        assert A.Game(2, 1).play()[-1]["state"] != A.Game(2, 2).play()[-1]["state"]

    def test_tile_conservation(self, games):
        for (n, s, v), (g, log) in games.items():
            for st in _states(log):
                assert A.count_tiles(st) == 100, (n, s, v)

    def test_every_logged_move_was_legal(self):
        g = A.Game(4, 7)
        st = g.state
        A.start_round(st)
        while st["phase"] == "offer":
            m = A.choose_move(st, g.ai_rng)
            assert m in A.legal_moves(st)
            A.apply_move(st, m)

    def test_board_invariants(self, games):
        for (n, s, v), (g, log) in games.items():
            for st in _states(log):
                for b in st["boards"]:
                    assert len(b["floor"]) <= 7
                    assert b["score"] >= 0
                    assert b["floor"].count(A.MARKER) <= 1
                    for r, pl in enumerate(b["lines"]):
                        assert 0 <= pl["count"] <= r + 1
                        if pl["count"]:
                            assert pl["colour"] not in b["wall"][r]
                    for r in range(5):
                        row = [t for t in b["wall"][r] if t]
                        assert len(row) == len(set(row))
                        col = [b["wall"][x][r] for x in range(5) if b["wall"][x][r]]
                        assert len(col) == len(set(col))
                        if v == A.COLOURED:
                            for c in range(5):
                                t = b["wall"][r][c]
                                assert t is None or t == A.wall_colour(r, c)

    def test_one_marker_in_play(self, games):
        for (n, s, v), (g, log) in games.items():
            for e in log:
                if e["type"] == "turn":
                    st = e["post"]
                    on_floors = sum(b["floor"].count(A.MARKER) for b in st["boards"])
                    held = st["marker_holder"] is not None
                    assert st["centre_marker"] + held == 1
                    assert on_floors <= 1

    def test_games_end_on_full_row(self, games):
        for (n, s, v), (g, log) in games.items():
            st = g.state
            assert st["game_over"]
            assert any(A.complete_rows(b["wall"]) for b in st["boards"])
            # The round before had no full row anywhere
            prev = [e for e in log if e["type"] == "tiling"][:-1]
            for e in prev:
                assert not any(A.complete_rows(b["wall"]) for b in e["state"]["boards"])

    def test_score_ledger(self, games):
        """Replaying the logged tiling results reproduces each final score."""
        for (n, s, v), (g, log) in games.items():
            totals = [0] * n
            for e in log:
                if e["type"] == "tiling":
                    for r in e["results"]:
                        p = r["player"]
                        assert r["score_before"] == totals[p]
                        gained = sum(x["points"] for x in r["placements"])
                        assert r["score_after_wall"] == totals[p] + gained
                        totals[p] = max(0, totals[p] + gained + r["floor_penalty"])
                        assert r["score"] == totals[p]
            end = log[-1]
            for p in range(n):
                assert end["scores"][p] == totals[p] + A.end_bonus(g.state["boards"][p]["wall"])

    def test_placement_points_recomputed(self, games):
        """Every logged placement equals score_placement on the wall at that moment."""
        for (n, s, v), (g, log) in list(games.items())[:30]:
            walls = [A.empty_wall() for _ in range(n)]
            for e in log:
                if e["type"] != "tiling":
                    continue
                for r in e["results"]:
                    w = walls[r["player"]]
                    for x in r["placements"]:
                        if x["col"] is None:
                            continue
                        w[x["row"]][x["col"]] = x["colour"]
                        assert A.score_placement(w, x["row"], x["col"]) == x["points"]
                    assert w == e["state"]["boards"][r["player"]]["wall"]

    def test_winners_valid(self, games):
        for (n, s, v), (g, log) in games.items():
            ws = log[-1]["winners"]
            assert ws and all(0 <= w < n for w in ws)

    def test_refill_happens_in_bigger_games(self, games):
        assert any(g.state.get("refills") for (n, s, v), (g, _) in games.items() if n >= 3)

    def test_snapshot_has_no_rng(self):
        g = A.Game(2, 0)
        g.play()
        assert "rng_state" not in g.snapshot()
        assert g.state["boards"] == g.snapshot()["boards"]
