"""Video-script helper and clip tests (no TTS, no ffmpeg)."""
import copy

import pytest

import engine as E
import render as R
import anim as A
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
    assert set(s) == {"text", "post", "pre", "tk", "cam", "hold", "sfx", "ov"}
    assert s["tk"]["deltas"] == {(0, "turtle"): 1}
    assert s["tk"]["names"] == V.NAMES and s["ov"]["bar"] == "b"
    assert s["tk"]["ticker"] is False          # scores are drawn in screen space instead
    t = V.seg("x", post, ticker=True, cap=("A", "b"), cap_pos="mid", focus=[(0, 0, 10, 10)],
              arrows=[V.arrow((5, 5), "L")], show=["bowl"], fade_from=[], xfade=True,
              say_after=True, pause=1.0)
    assert t["ov"]["score"] == f"Ana {post['scores'][0]}  ·  Ben {post['scores'][1]}"
    assert t["ov"]["cap"] == ("A", "b") and t["ov"]["cap_pos"] == "mid"
    assert t["ov"]["focus"] == [(-10, -10, 20, 20)] and t["ov"]["arrows"] == [(5, 5, "L", "down")]
    assert t["tk"]["show"] == ["bowl"] and t["fade_from"] == {"show": []}
    assert t["xfade"] and t["say_after"] and t["pause"] == 1.0
    assert V.T("x", post)["pause"] == V.TEACH_PAUSE
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
def episodes():
    return {k: f() for k, f in V.CLIPS.items()}


@pytest.fixture(scope="module")
def spirits(episodes):
    return episodes["10-spirit-powers"]


@pytest.fixture(scope="module")
def sample(episodes):
    return episodes["11-sample-game"]


TEACHING = [k for k, _ in V.EPISODES[:9]]


def by_text(S, sub):
    hits = [s for s in S if sub in s["text"]]
    assert len(hits) == 1, (sub, len(hits))
    return hits[0]


def cap_title(s):
    c = s.get("ov", {}).get("cap")
    return c if isinstance(c, str) or c is None else c[0]


def test_clips_registry():
    assert list(V.CLIPS) == [k for k, _ in V.EPISODES]
    assert len(V.CLIPS) == 11
    assert all(callable(f) for f in V.CLIPS.values())
    for i, k in enumerate(V.CLIPS, 1):
        assert k.startswith(f"{i:02d}-")


class TestEpisodes:
    @pytest.mark.parametrize("name", list(V.CLIPS))
    def test_segments_well_formed(self, episodes, name):
        for s in episodes[name]:
            check_segment(s)

    @pytest.mark.parametrize("name", TEACHING + ["10-spirit-powers"])
    def test_every_segment_is_narrated(self, episodes, name):
        for s in episodes[name]:
            assert s["text"].strip(), s.get("ov")

    @pytest.mark.parametrize("name", list(V.CLIPS))
    def test_starts_with_numbered_title_card(self, episodes, name):
        first = episodes[name][0]
        assert "image" in first and first.get("fade")
        assert first["text"].strip()

    @pytest.mark.parametrize("name", TEACHING + ["10-spirit-powers"])
    def test_ends_with_recap_and_next(self, episodes, name):
        last = episodes[name][-1]
        assert "image" in last and last["text"].startswith("Remember.")
        n = list(V.CLIPS).index(name)
        nxt = V.EPISODES[n + 1][1]
        assert "Next" in last["text"]

    @pytest.mark.parametrize("name", TEACHING)
    def test_one_idea_per_sentence(self, episodes, name):
        """Beginner narration: short sentences, at most 16 words each."""
        for s in episodes[name]:
            for sent in A.sentences(s["text"]):
                assert len(sent.split()) <= 16, sent

    @pytest.mark.parametrize("name", TEACHING + ["10-spirit-powers"])
    def test_episode_is_short(self, episodes, name):
        """One idea per episode: roughly 1-2.5 minutes of narration (~120-150 words/min)."""
        words = sum(len(s["text"].split()) for s in episodes[name])
        assert 120 <= words <= 320, words

    @pytest.mark.parametrize("name", TEACHING)
    def test_table_shots_carry_a_caption(self, episodes, name):
        for s in episodes[name]:
            if "post" in s:
                assert s["ov"].get("cap"), s["text"]

    @pytest.mark.parametrize("name", list(V.CLIPS))
    def test_never_says_clear_stones(self, episodes, name):
        """Spirit Stones are always called Spirit Stones, never 'clear' stones."""
        import re
        for s in episodes[name]:
            cap = s.get("ov", {}).get("cap")
            words = s["text"] + " " + (" ".join(cap) if isinstance(cap, tuple) else (cap or ""))
            assert not re.search(r"\bclear\b", words, re.I), words

    @pytest.mark.parametrize("name", list(V.CLIPS))
    def test_captions_fit_on_screen(self, episodes, name):
        d = R.SDraw(R.new_canvas()[0], 1)
        for s in episodes[name]:
            cap = s.get("ov", {}).get("cap")
            if cap:
                t, sub = (cap, None) if isinstance(cap, str) else cap
                assert d.textlength(t, R.F["big"]) + 110 < R.W - 40, t
                if sub:
                    assert d.textlength(sub, R.F["mid"]) + 110 < R.W - 40, sub

    @pytest.mark.parametrize("name", list(V.CLIPS))
    def test_arrows_and_focus_are_in_view(self, episodes, name):
        for s in episodes[name]:
            x, y, w = s.get("cam") or V.FULL
            h = w * 9 / 16
            for ax, ay, label, side in s.get("ov", {}).get("arrows", []):
                assert x <= ax <= x + w and y <= ay <= y + h, (label, s["text"])
                assert side in ("up", "down", "left", "right")
            for x0, y0, x1, y1 in s.get("ov", {}).get("focus", []):
                assert x0 < x1 and y0 < y1
                assert x1 > x and x0 < x + w and y1 > y and y0 < y + h, s["text"]

    def test_game_words_are_explained_on_first_use(self, episodes):
        """Each game word is explained the first time the series uses it."""
        text = " ".join(s["text"] for k in V.CLIPS for s in episodes[k])
        for word, explain in [("turn", "Each go is called a turn"),
                              ("face-up", "Face-up means"),
                              ("face-down", "Face-down means"),
                              ("without looking", "without looking"),
                              ("section", "Each part is called a section"),
                              ("points", "Animals give you points"),
                              ("winner", "That player is the winner"),
                              ("opponent", "Your opponent is the other player"),
                              ("blocked", "Blocked means"),
                              ("closed", "Closed means")]:
            first = text.lower().find(word)
            assert first >= 0, word
            assert text.find(explain) >= 0, explain
            assert text.find(explain) <= first + 200, (word, text[first - 80:first + 80])

    def test_setup_says_both_players_have_the_same_cards(self, episodes):
        S = episodes["02-getting-ready"]
        same = by_text(S, "exact same six cards")
        assert "image" in same
        assert by_text(S, "two Take One Stone cards")

    def test_spirit_stone_is_not_a_color(self, episodes):
        s = by_text(episodes["02-getting-ready"], "A Spirit Stone is not a color")
        assert isinstance(s["fade"], R.Image.Image)   # crossfades in from the six-colors card

    def test_numbers_in_the_animal_episodes_match_the_engine(self, episodes):
        S = episodes["05-rabbit-turtle-salmon"] + episodes["06-owl-and-beaver"]
        claims = [("That's six points", "rabbit", 6), ("One green stone. One point", "turtle", 1),
                  ("Three green stones. Six points", "turtle", 6),
                  ("Fourteen points", "turtle", 14), ("Three different colors. Four points", "salmon", 4),
                  ("Thirteen points", "salmon", 13),
                  ("That's a pair", "owl", E.OWL_POINTS), ("Another pair", "owl", 2 * E.OWL_POINTS),
                  ("make five points", "beaver", 5), ("fourteen in all", "beaver", 14)]
        for sub, a, pts in claims:
            s = by_text(S, sub)
            assert E.animal_score(s["post"]["boards"][0], a) == pts, sub
        owl = by_text(S, "That's a pair")
        assert V.NUM[E.OWL_POINTS].capitalize() in owl["text"]

    def test_turn_episode_and_points_shots(self, episodes):
        S = episodes["01-what-is-this-game"]
        s = by_text(S, "It just went up")
        assert E.animal_score(s["post"]["boards"][0], "turtle") == 3
        assert s["tk"]["deltas"] == {(0, "turtle"): 2}
        S = episodes["03-your-turn"]
        flip = by_text(S, "Then she turns the card face-down")
        assert flip["post"]["cards"][0][E.TAKE1A] is False and flip["pre"]["cards"][0][E.TAKE1A]
        s = by_text(S, "Three are face-down")
        assert sum(not v for v in s["post"]["cards"][0].values()) == 3

    def test_spirit_stone_doubling(self, episodes):
        S = episodes["09-spirit-stones-and-the-end"]
        dbl = by_text(S, "Nine becomes eighteen")
        assert E.animal_score(dbl["pre"]["boards"][0], "turtle") == 9
        assert E.animal_score(dbl["post"]["boards"][0], "turtle") == 18
        assert dbl["post"]["boards"][0]["bonus"]["turtle"]
        end = by_text(S, "the fifth one comes out")
        assert end["pre"]["clear_out"] == 4 and end["post"]["clear_out"] == 5

    def test_cards_back_episode_recovers_all_cards(self, episodes):
        S = episodes["07-getting-cards-back"]
        need = by_text(S, "Three of them are face-down")
        assert sum(not v for c, v in need["post"]["cards"][0].items() if c != E.SPIRIT) >= 3
        up = by_text(S, "turn face-up again")
        assert all(up["post"]["cards"][0].values())
        wolf = by_text(S, "She picks the Wolf")
        assert wolf["post"]["piles"][0][0] == "wolf"

    def test_coyote_episode(self, episodes):
        S = episodes["08-the-coyote"]
        assert by_text(S, "moves the Coyote onto Ben's Turtle")["post"]["coyote"] == (1, "turtle")
        whole = by_text(S, "whole Coyote")
        c = whole["post"]["cards"][1]
        assert not c[E.TAKE1A] and not c[E.TAKE1B]
        assert by_text(S, "He puts it on Ana's Rabbit")["post"]["coyote"] == (0, "rabbit")

    @pytest.mark.parametrize("name", TEACHING)
    def test_board_states_are_legal(self, episodes, name):
        from test_engine import assert_board_legal
        for s in episodes[name]:
            if "post" in s:
                for b in s["post"]["boards"]:
                    assert_board_legal(b)


class TestSpiritPowers:
    def test_segments_well_formed(self, spirits):
        assert len(spirits) == 1 + 1 + len(V.SPIRIT_GRID) + 1 + 1
        for s in spirits:
            check_segment(s)
            assert s["text"].strip()

    def test_grid_covers_every_engine_spirit(self):
        assert set(V.SPIRIT_GRID) == set(E.SPIRITS) == set(V.SPIRIT_SAY)

    def test_each_spirit_is_mentioned_by_name(self, spirits):
        for seg, k in zip(spirits[2:-2], V.SPIRIT_GRID):
            assert seg["text"].startswith(f"The {k.capitalize()}.")
            assert V.SPIRIT_GRID[k][0] == k.capitalize()

    def test_spirit_cameras_zoom_on_their_card(self, spirits):
        for seg in spirits[2:-2]:
            x, y, w = seg["cam"]
            assert w == 900


class TestSampleGame:
    def test_segments_well_formed(self, sample):
        assert len(sample) > 20
        for s in sample:
            check_segment(s)

    def test_intro_and_setup_narrated(self, sample):
        assert sample[0]["text"] and "image" in sample[0] and sample[0].get("fade")
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
            assert s["ov"]["bar"] and (s["ov"]["bar"].startswith("Turn "))
            assert s["ov"]["score"].startswith("Ana ")
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
