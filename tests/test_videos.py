"""Video-script helper and clip tests (no TTS, no ffmpeg)."""
import copy

import pytest

import engine as E
import render as R
import videos as V
from conftest import SWEEP_SEEDS


# ============================================================ wording helpers
class TestWords:
    def test_list_words(self):
        assert V.list_words([]) == "nothing"
        assert V.list_words(["a"]) == "a"
        assert V.list_words(["a", "b"]) == "a and b"
        assert V.list_words(["a", "b", "c"]) == "a, b and c"
        assert V.list_words(["a", "b", "c", "d"]) == "a, b, c and d"

    def test_list_words_accepts_any_iterable(self):
        assert V.list_words(iter(["x", "y"])) == "x and y"
        assert V.list_words(("x",)) == "x"
        assert V.list_words(x for x in ()) == "nothing"

    def test_colors_words_example(self):
        assert V.colors_words(["red", "red", "clear"]) == "two red and a Spirit Stone"

    def test_colors_words_variants(self):
        assert V.colors_words([]) == "nothing"
        assert V.colors_words(["red"]) == "a red"
        assert V.colors_words(["clear"]) == "a Spirit Stone"
        assert V.colors_words(["clear", "clear"]) == "two Spirit Stones"
        assert V.colors_words(["blue", "green", "blue", "blue"]) == "three blue and a green"
        assert V.colors_words(["red", "blue", "white"]) == "a red, a blue and a white"

    def test_stone_word(self):
        assert V.stone_word(E.CLEAR) == "a Spirit Stone"
        assert V.stone_word("red") == "a red stone"

    def test_where_and_place_words(self):
        assert V.where_word(("owl", None)) == "to the Owl"
        assert V.where_word(("turtle", "bonus")) == "on the Turtle's times-two space"
        assert V.place_words([("red", ("rabbit", None))]) == "a red stone to the Rabbit"
        assert V.place_words([("red", None)]) == "a red stone, which fits nowhere"
        assert V.place_words([("red", ("rabbit", None)), (E.CLEAR, ("owl", "bonus"))]) == \
            "a red stone to the Rabbit and a Spirit Stone on the Owl's times-two space"
        assert V.place_words([]) == "nothing"

    def test_turn_label(self):
        ev = {"player": 0, "action": E.TAKE2}
        assert V.turn_label(3, ev) == "Turn 3 · Ana · Take Two Stones"
        ev = {"player": 1, "action": E.SPIRIT, "spirit": "wolf"}
        assert V.turn_label(8, ev) == "Turn 8 · Ben · Spirit Power: Wolf"

    def test_num_table_covers_small_counts(self):
        assert [V.NUM[i] for i in range(10)][:4] == ["zero", "one", "two", "three"]
        assert V.NUM[E.OWL_POINTS] == "four"


# ================================================================== camera
class TestCamera:
    @pytest.mark.parametrize("x", [-500, -1, 0, 100, 1500, 1920, 5000])
    @pytest.mark.parametrize("y", [-500, 0, 400, 1080, 9999])
    @pytest.mark.parametrize("w", [300, 760, 1000, 1540, 1920])
    def test_clamp_cam_inside_frame(self, x, y, w):
        cx, cy, cw = V.clamp_cam(x, y, w)
        assert cw == w
        assert 0 <= cx and cx + cw <= 1920
        assert 0 <= cy and cy + cw * 9 / 16 <= 1080 + 1e-9

    def test_clamp_cam_leaves_valid_rect_untouched(self):
        assert V.clamp_cam(100, 50, 800) == (100, 50, 800)

    def test_clamp_cam_full(self):
        assert V.clamp_cam(0, 0, 1920) == (0, 0, 1920)
        assert V.clamp_cam(50, 50, 1920) == (0, 0, 1920)

    @pytest.mark.parametrize("p", [0, 1])
    def test_cam_player_in_bounds(self, p):
        x, y, w = V.cam_player(p)
        assert x >= 0 and x + w <= 1920 and y >= 0 and y + w * 9 / 16 <= 1080

    @pytest.mark.parametrize("p", [0, 1])
    @pytest.mark.parametrize("animal", E.ANIMALS)
    @pytest.mark.parametrize("w", [500, 760, 1000])
    def test_cam_section_in_bounds_and_covers_section(self, p, animal, w):
        x, y, cw = V.cam_section(p, animal, w)
        assert cw == w
        assert 0 <= x and x + w <= 1920 and 0 <= y and y + w * 9 / 16 <= 1080 + 1e-9

    @pytest.mark.parametrize("p", [0, 1])
    @pytest.mark.parametrize("animal", E.ANIMALS)
    def test_cam_section_contains_the_rendered_section(self, p, animal, base_state):
        R.table(base_state)
        sx, sy, sw, sh = R.CTX["sec"][(p, animal)]
        x, y, w = V.cam_section(p, animal)
        h = w * 9 / 16
        assert x <= sx and sx + sw <= x + w, "section horizontally visible"
        assert y <= sy + 56 and sy + sh >= y, "section vertically overlaps view"
        assert y <= sy + 100 <= y + h  # the stone row is in view

    def test_named_cams_in_bounds(self):
        for x, y, w in (V.CAM_CARDS, V.CAM_CARDS_BEN, V.CAM_MID, V.CAM_BAG, V.FULL):
            assert x >= 0 and x + w <= 1920 and y >= 0 and y + w * 9 / 16 <= 1080


# ==================================================================== Demo
class TestDemo:
    def test_draw_take_direct(self, base_state):
        D = V.Demo(base_state)
        D.draw(["green", E.CLEAR])
        assert D.st["bag"] == 50 and D.st["bowl"][-2:] == ["green", E.CLEAR]
        assert D.st["clear_out"] == base_state["clear_out"] + 1
        D.take(0, "red", ("rabbit", None))
        assert "red" not in D.st["bowl"] and D.st["boards"][0]["rabbit"] == ["red"]
        D.direct(1, "blue", ("turtle", None))
        assert D.st["bag"] == 49 and D.st["boards"][1]["turtle"] == ["blue"]
        D.direct(1, E.CLEAR, ("turtle", "bonus"))
        assert D.st["boards"][1]["bonus"]["turtle"] and D.st["clear_out"] == base_state["clear_out"] + 2

    def test_does_not_alias_input(self, base_state):
        before = copy.deepcopy(base_state)
        V.Demo(base_state).draw(["red"]).take(0, "red", ("rabbit", None))
        assert base_state == before

    def test_snap_updates_scores_and_is_a_copy(self, base_state):
        D = V.Demo(base_state)
        D.direct(0, "red", ("turtle", None)).direct(0, "red", ("turtle", None))
        s = D.snap()
        assert s["scores"] == [3, 0]
        D.direct(0, "red", ("turtle", None))
        assert s["scores"] == [3, 0] and s["boards"][0]["turtle"] == ["red", "red"]

    def test_card_all_up_coyote(self, base_state):
        D = V.Demo(base_state)
        D.card(0, E.TAKE1A, False)
        assert D.st["cards"][0][E.TAKE1A] is False
        D.all_up(0)
        assert all(D.st["cards"][0].values())
        D.coyote(1, "owl")
        assert D.st["coyote"] == (1, "owl")
        D.coyote(None, None)
        assert D.st["coyote"] is None


def test_deltas(base_state):
    pre = V.Demo(base_state).snap()
    D = V.Demo(pre)
    for _ in range(3):
        D.direct(0, "red", ("turtle", None))
    D.direct(1, "red", ("rabbit", None))
    post = D.snap()
    assert V.deltas(pre, post) == {(0, "turtle"): 6}
    assert V.deltas(post, pre) == {(0, "turtle"): -6}
    assert V.deltas(pre, pre) == {}


def test_deltas_bonus_doubling(base_state):
    D = V.Demo(base_state)
    for _ in range(4):
        D.direct(0, "red", ("turtle", None))
    pre = D.snap()
    post = D.direct(0, E.CLEAR, ("turtle", "bonus")).snap()
    assert V.deltas(pre, post) == {(0, "turtle"): 9}


def test_seg_builder(base_state):
    pre = V.Demo(base_state).snap()
    post = V.Demo(pre).direct(0, "red", ("turtle", None)).snap()
    s = V.seg("hello", post, pre, cam=V.CAM_MID, bar="b", hl={"mid": "bowl"})
    assert set(s) == {"text", "post", "pre", "tk", "cam", "hold", "sfx"}
    assert s["tk"]["deltas"] == {(0, "turtle"): 1}
    assert s["tk"]["names"] == V.NAMES and s["tk"]["bar"] == "b"
    assert "deltas" not in V.seg("x", post, pre, pops=False)["tk"]
    assert "deltas" not in V.seg("x", post)["tk"]


# ============================================================ featured_turns
def fake_turn(steps=(), spirit=None, scores=(0, 0)):
    ev = {"steps": list(steps), "post": {"scores": list(scores)}}
    if spirit:
        ev["spirit"] = spirit
    return ev


class TestFeaturedTurns:
    def test_first_and_last_two_are_featured(self):
        ts = [fake_turn() for _ in range(12)]
        assert V.featured_turns(ts) == {1, 11, 12}

    def test_empty(self):
        assert V.featured_turns([]) == set()

    def test_short_game_all_featured(self):
        assert V.featured_turns([fake_turn() for _ in range(2)]) == {1, 2}

    def test_first_use_of_each_spirit_only(self):
        ts = [fake_turn() for _ in range(15)]
        ts[3] = fake_turn(spirit="wolf")
        ts[5] = fake_turn(spirit="wolf")
        ts[7] = fake_turn(spirit="bear")
        assert V.featured_turns(ts) == {1, 4, 8, 14, 15}

    def test_first_coyote_of_each_kind(self):
        ts = [fake_turn() for _ in range(15)]
        ts[2] = fake_turn(steps=[("coyote", 1, "owl", None)])
        ts[4] = fake_turn(steps=[("coyote", 1, "owl", None)])
        ts[6] = fake_turn(steps=[("coyote_half", 1, "owl", None)])
        assert V.featured_turns(ts) == {1, 3, 7, 14, 15}

    def test_first_bonus_placement(self):
        ts = [fake_turn() for _ in range(15)]
        ts[4] = fake_turn(steps=[("take", [("clear", ("turtle", "bonus"))])])
        ts[6] = fake_turn(steps=[("take", [("clear", ("owl", "bonus"))])])
        ts[8] = fake_turn(steps=[("ram", [("clear", ("owl", "bonus")), ("red", None)])])
        assert V.featured_turns(ts) == {1, 5, 14, 15}

    def test_non_bonus_and_unplaced_stones_are_ignored(self):
        ts = [fake_turn() for _ in range(15)]
        ts[4] = fake_turn(steps=[("take", [("red", None), ("blue", ("owl", None))])])
        assert V.featured_turns(ts) == {1, 14, 15}

    def test_lead_change_after_turn_six(self):
        ts = [fake_turn(scores=(1, 0)) for _ in range(15)]
        ts[8] = fake_turn(scores=(1, 3))     # lead flips on turn 9
        ts[9] = fake_turn(scores=(1, 3))
        feat = V.featured_turns(ts)
        assert 9 in feat and 10 not in feat and 5 not in feat

    def test_early_lead_change_not_featured(self):
        ts = [fake_turn(scores=(1, 0)) for _ in range(15)]
        ts[3] = fake_turn(scores=(0, 1))
        assert 4 not in V.featured_turns(ts)

    def test_ties_do_not_count_as_lead_change(self):
        ts = [fake_turn(scores=(2, 1)) for _ in range(15)]
        ts[8] = fake_turn(scores=(2, 2))
        ts[9] = fake_turn(scores=(2, 1))
        feat = V.featured_turns(ts)
        assert 9 not in feat and 10 not in feat

    def test_real_games(self, games):
        for s, (g, log) in games.items():
            turns = [e for e in log if e["type"] == "turn"]
            feat = V.featured_turns(turns)
            n = len(turns)
            assert {1, n - 1, n} & set(range(1, n + 1)) <= feat
            assert feat <= set(range(1, n + 1))
            assert len(feat) < n or n < 12


# ============================================================ clip scripts
SEG_COMMON = {"text", "hold"}


def check_segment(s):
    assert isinstance(s, dict)
    assert SEG_COMMON <= set(s), s.keys()
    assert isinstance(s["text"], str)
    assert s["hold"] > 0
    assert isinstance(s.get("sfx", []), list)
    if "image" in s:
        assert s["image"].size == (R.W * R.S, R.H * R.S)
    else:
        assert {"post", "pre", "tk", "cam"} <= set(s)
        st = s["post"]
        assert {"bag", "bowl", "boards", "cards", "piles", "coyote", "scores"} <= set(st)
        assert st["scores"] == [E.total_score(b) for b in st["boards"]]
        assert s["tk"]["names"] == V.NAMES
    cam = s.get("cam")
    if cam is not None:
        x, y, w = cam
        assert x >= 0 and y >= 0 and x + w <= 1920 + 1e-9 and y + w * 9 / 16 <= 1080 + 1e-9, cam


@pytest.fixture(scope="module")
def learn():
    return V.learn_to_play()


@pytest.fixture(scope="module")
def spirits():
    return V.spirit_powers()


@pytest.fixture(scope="module")
def sample():
    return V.sample_game()


def test_clips_registry():
    assert set(V.CLIPS) == {"learn-to-play", "sample-game", "spirit-powers"}
    assert all(callable(f) for f in V.CLIPS.values())


class TestLearnToPlay:
    def test_segments_well_formed(self, learn):
        assert len(learn) > 20
        for s in learn:
            check_segment(s)

    def test_every_segment_is_narrated(self, learn):
        for s in learn:
            assert s["text"].strip(), s

    def test_starts_and_ends_with_cards(self, learn):
        assert "image" in learn[0] and "image" in learn[-1]
        assert "Spirits of the Wild" in learn[0]["text"]

    def test_state_snapshots_are_conserved_where_stones_move(self, learn):
        """Scripted demos place stones from the bag directly (animals demo), so only the
        board legality is checked here."""
        from test_engine import assert_board_legal
        for s in learn:
            if "post" in s:
                for b in s["post"]["boards"]:
                    assert_board_legal(b)

    def test_scripted_scores_match_the_narration(self, learn):
        by_text = {s["text"][:30]: s for s in learn if "post" in s}
        turtle = next(s for s in learn if "Two whites for her Turtle" in s["text"])
        assert turtle["post"]["scores"][0] == E.animal_score(turtle["post"]["boards"][0], "turtle") \
            + E.animal_score(turtle["post"]["boards"][0], "rabbit")
        assert E.animal_score(turtle["post"]["boards"][0], "turtle") == 3  # "three points"
        dbl = next(s for s in learn if "jumps from nine to eighteen" in s["text"])
        assert E.animal_score(dbl["pre"]["boards"][0], "turtle") == 9
        assert E.animal_score(dbl["post"]["boards"][0], "turtle") == 18
        assert dbl["post"]["boards"][0]["bonus"]["turtle"]
        assert by_text

    def test_animal_demos_match_stated_points(self, learn):
        claims = {"Rabbit": ("rabbit", 6), "Turtle": ("turtle", 14), "Salmon": ("salmon", 13),
                  "Owl": ("owl", 2 * E.OWL_POINTS), "Beaver": ("beaver", 14)}
        for s in learn:
            if "post" not in s or not s["tk"].get("hl", {}).get("sections"):
                continue
            p, animals = s["tk"]["hl"]["sections"]
            bar = s["tk"]["bar"] or ""
            for key, (a, pts) in claims.items():
                if bar.startswith(key + ":") and len(animals) == 1 and animals[0] == a.lower():
                    assert E.animal_score(s["post"]["boards"][p], a) == pts, bar

    def test_owl_text_matches_engine_points(self, learn):
        owl = next(s for s in learn if s["text"].startswith("The Owl loves pairs"))
        assert V.NUM[E.OWL_POINTS] in owl["text"]


class TestSpiritPowers:
    def test_segments_well_formed(self, spirits):
        assert len(spirits) == 1 + len(V.SPIRIT_GRID) + 1
        for s in spirits:
            check_segment(s)
            assert s["text"].strip()

    def test_grid_covers_every_engine_spirit(self):
        assert set(V.SPIRIT_GRID) == set(E.SPIRITS) == set(V.SPIRIT_SAY)

    def test_each_spirit_is_mentioned_by_name(self, spirits):
        for seg, k in zip(spirits[1:-1], V.SPIRIT_GRID):
            assert k.capitalize() in seg["text"] or k.capitalize() in V.SPIRIT_GRID[k][0]
            assert V.SPIRIT_GRID[k][0] == k.capitalize()

    def test_spirit_cameras_zoom_on_their_card(self, spirits):
        for seg in spirits[1:-1]:
            x, y, w = seg["cam"]
            assert w == 900


class TestSampleGame:
    def test_segments_well_formed(self, sample):
        assert len(sample) > 20
        for s in sample:
            check_segment(s)

    def test_intro_and_setup_narrated(self, sample):
        assert sample[0]["text"] and "image" in sample[0]
        g = E.Game(seed=V.GAME_SEED, names=V.NAMES)
        log = g.play()
        setup = log[0]["state"]
        assert sample[1]["text"].startswith("Ana is at the bottom")
        assert V.colors_words(setup["bowl"]) in sample[1]["text"]
        assert "Take Two Stones" in sample[1]["text"]

    def test_narration_non_empty_except_silent_transitions(self, sample):
        empty = [s for s in sample[1:] if not s["text"].strip()]
        # silent segments are only the fast-forwarded turns / recover steps
        for s in empty:
            assert s["tk"]["bar"] and (s["tk"]["bar"].startswith("Turn "))
        assert sample[-1]["text"].strip() and sample[-2]["text"].strip()

    def test_final_script_matches_engine_result(self, sample):
        g = E.Game(seed=V.GAME_SEED, names=V.NAMES)
        log = g.play()
        sc = log[-1]["state"]["scores"]
        assert sample[-1]["post"]["scores"] == sc
        final = sample[-1]
        if sc[0] != sc[1]:
            w = 0 if sc[0] > sc[1] else 1
            assert f"{V.NAMES[w]} wins, {max(sc)} to {min(sc)}" in final["text"]
            assert final["tk"]["ban"] == (f"{V.NAMES[w]} wins!", f"{max(sc)} – {min(sc)}")
        # the per-player breakdown lines state the engine totals
        co = sample[-4:-1]
        for p, seg in zip((0, 1), sample[-3:-1]):
            assert f"{V.NAMES[p]}:" in seg["text"] and f"{sc[p]} points." in seg["text"]
            b = log[-1]["state"]["boards"][p]
            for a in E.ANIMALS:
                pts = E.animal_score(b, a)
                if pts:
                    assert f"{V.ANAME[a]} {pts}" in seg["text"]
                else:
                    assert f"{V.ANAME[a]} 0" not in seg["text"]
        assert co

    def test_game_over_line_states_spirit_stones_out(self, sample):
        g = E.Game(seed=V.GAME_SEED, names=V.NAMES)
        end = g.play()[-1]["state"]
        over = sample[-4]
        assert over["text"].startswith(V.NUM[end["clear_out"]].capitalize() + " Spirit Stones")
        assert "Game over" in over["text"]

    def test_turn_announcements_follow_featured_turns(self, sample):
        g = E.Game(seed=V.GAME_SEED, names=V.NAMES)
        turns = [e for e in g.play() if e["type"] == "turn"]
        feat = V.featured_turns(turns)
        announced = {int(s["text"].split(".")[0].split()[1]) for s in sample
                     if s["text"].startswith("Turn ") and s["text"].split(".")[0].split()[1].isdigit()}
        assert announced == feat

    def test_script_is_deterministic(self):
        a, b = V.sample_game(), V.sample_game()
        assert [s["text"] for s in a] == [s["text"] for s in b]

    def test_tie_games_award_the_coyote_board(self, games, monkeypatch):
        ties = [s for s, (g, log) in games.items()
                if log[-1]["state"]["scores"][0] == log[-1]["state"]["scores"][1]]
        if not ties:
            pytest.skip("no tied game in the sweep")
        for seed in ties:
            end = games[seed][1][-1]["state"]
            monkeypatch.setattr(V, "GAME_SEED", seed)
            final = V.sample_game()[-1]
            cp = end["coyote"][0] if end["coyote"] else None
            if cp is None:
                assert "nobody has the Coyote" in final["text"]
            else:
                assert f"{V.NAMES[cp]} wins" in final["text"]
                assert final["tk"]["ban"][0] == f"{V.NAMES[cp]} wins!"

    @pytest.mark.parametrize("seed", [0, 1, 2, 3, 7, 11])
    def test_other_seeds_build_and_name_the_winner(self, seed, monkeypatch):
        monkeypatch.setattr(V, "GAME_SEED", seed)
        S = V.sample_game()
        for s in S:
            check_segment(s)
        sc = E.Game(seed=seed).play()[-1]["state"]["scores"]
        if sc[0] != sc[1]:
            w = 0 if sc[0] > sc[1] else 1
            assert f"{V.NAMES[w]} wins, {max(sc)} to {min(sc)}" in S[-1]["text"]
