"""Azul video scripts: structure, beginner wording, glossary order, and every spoken or
shown number checked against tools/azul/engine.py (no TTS, no ffmpeg)."""
import copy
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

AZUL = Path(__file__).resolve().parents[1] / "tools" / "azul"
VIDEOS = Path(__file__).resolve().parents[1] / "docs" / "azul" / "videos"


def load(name):
    full = f"azul_{name}"
    if full not in sys.modules:
        spec = importlib.util.spec_from_file_location(full, AZUL / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[full] = mod
        spec.loader.exec_module(mod)
    return sys.modules[full]


V = load("videos")
A, R, E = V.A, V.R, V.E

TEACHING = [k for k, _ in V.EPISODES[:-1]]
SAMPLE = V.EPISODES[-1][0]


@pytest.fixture(scope="module")
def episodes():
    return {k: f() for k, f in V.CLIPS.items()}


def by_text(S, sub):
    hits = [s for s in S if sub in s["text"]]
    assert len(hits) == 1, (sub, len(hits))
    return hits[0]


def cap_words(s):
    c = s.get("ov", {}).get("cap")
    return "" if not c else (c if isinstance(c, str) else " ".join(c))


def table_states(S):
    for s in S:
        if "post" in s:
            yield s["post"]
            if s.get("pre") is not None:
                yield s["pre"]


# ================================================================ helpers
class TestWords:
    def test_num(self):
        assert [V.num(n) for n in (0, 1, 13, 20, 26, 52, 100, 101)] == [
            "zero", "one", "thirteen", "twenty", "twenty six", "fifty two", "one hundred",
            "one hundred and one"]
        assert V.num(-4) == "minus four"

    def test_points_and_tiles(self):
        assert V.points(1) == "one point" and V.points(7) == "seven points"
        assert V.tiles_word(1, "red") == "one red tile" and V.tiles_word(3) == "three tiles"

    def test_list_words(self):
        assert V.list_words([]) == "nothing"
        assert V.list_words(["a", "b", "c"]) == "a, b and c"

    def test_floor_values_words_follow_the_engine(self):
        said = V.floor_values_words()
        words = said.replace(".", "").split()
        # rebuild the seven values from "The first two say minus one." etc.
        values = []
        for m in re.finditer(r"The \w+ (\w+) say minus (\w+)", said):
            n = [V.num(i) for i in range(10)].index(m.group(1))
            v = [V.num(i) for i in range(10)].index(m.group(2))
            values += [-v] * n
        assert tuple(values) == E.FLOOR_VALUES and words


# ================================================================== Demo
class TestDemo:
    def test_always_100_tiles(self, episodes):
        for name, S in episodes.items():
            for st in table_states(S):
                assert E.count_tiles(st) == E.TOTAL_TILES, name

    def test_board_states_are_legal(self, episodes):
        for name, S in episodes.items():
            for st in table_states(S):
                for b in st["boards"]:
                    for r, pl in enumerate(b["lines"]):
                        assert 0 <= pl["count"] <= r + 1
                        if pl["count"]:
                            assert pl["colour"] not in b["wall"][r], (name, r)
                    assert len(b["floor"]) <= E.FLOOR_SPACES
                    assert b["score"] >= 0
                    if st["variant"] == E.COLOURED:
                        for r in range(5):
                            for c in range(5):
                                t = b["wall"][r][c]
                                assert t is None or t == E.wall_colour(r, c)
                    else:
                        for c in range(5):
                            col = [b["wall"][r][c] for r in range(5) if b["wall"][r][c]]
                            assert len(col) == len(set(col)), name

    @pytest.mark.parametrize("seed", range(12))
    def test_tile_line_and_score_floor_match_the_engine(self, seed):
        """The one-line-at-a-time helper used in the episodes equals engine.tile_wall."""
        g = E.Game(2, seed)
        log = g.play()
        for e_pre, e in zip(log, log[1:]):
            if e["type"] != "tiling":
                continue
            pre = e_pre.get("post") or e_pre.get("state")
            for p in range(2):
                a = V.Demo()
                a.st = copy.deepcopy(pre)
                b = copy.deepcopy(pre)
                expect = E.tile_wall(b, p)
                got = []
                for r in range(5):
                    pl = a.st["boards"][p]["lines"][r]
                    if pl["count"] == r + 1:
                        got.append(a.tile_line(p, r)[0])
                pen = a.score_floor(p)
                assert got == [x["points"] for x in expect["placements"]]
                assert pen == expect["floor_penalty"]
                assert a.st["boards"][p] == b["boards"][p]
                assert sorted(a.st["lid"]) == sorted(b["lid"])

    def test_take_split_middle_state(self):
        D = V.demo_factories(V.Demo()).marker_to_centre()
        pre = D.snap()
        info, mid = D.take(0, 0, E.COLOURS[0], 2, split=True)
        assert mid["factories"][0] == [t for t in pre["factories"][0] if t != "blue"]
        assert mid["centre"] == pre["centre"] and D.st["factories"][0] == []
        assert E.count_tiles(mid) == E.TOTAL_TILES

    def test_wall_strings_must_match_the_printed_wall(self):
        with pytest.raises(AssertionError):
            V.Demo().wall(0, "Y....")


# ============================================================== structure
def test_registry():
    assert list(V.CLIPS) == [k for k, _ in V.EPISODES]
    for i, k in enumerate(V.CLIPS, 1):
        assert k.startswith(f"{i:02d}-")
    assert SAMPLE == "11-sample-game"          # the sample game is the last episode


class TestEpisodes:
    @pytest.mark.parametrize("name", list(V.CLIPS))
    def test_starts_with_numbered_title_card(self, episodes, name):
        first = episodes[name][0]
        assert "image" in first and first.get("fade") and first["text"].strip()

    @pytest.mark.parametrize("name", TEACHING)
    def test_ends_with_remember_and_next(self, episodes, name):
        last = episodes[name][-1]
        assert "image" in last and last["text"].startswith("Remember.")
        assert "Next" in last["text"]

    @pytest.mark.parametrize("name", TEACHING)
    def test_every_teaching_segment_is_narrated(self, episodes, name):
        for s in episodes[name]:
            assert s["text"].strip()

    @pytest.mark.parametrize("name", list(V.CLIPS))
    def test_sentences_have_at_most_16_words(self, episodes, name):
        for s in episodes[name]:
            for sent in A.sentences(s["text"]):
                assert len(sent.split()) <= 16, sent

    @pytest.mark.parametrize("name", TEACHING)
    def test_episode_length(self, episodes, name):
        """1-2.5 minutes: about 120-320 narrated words with the pauses."""
        words = sum(len(s["text"].split()) for s in episodes[name])
        assert 120 <= words <= 320, words

    def test_sample_game_length(self, episodes):
        words = sum(len(s["text"].split()) for s in episodes[SAMPLE])
        assert words <= 520, words

    @pytest.mark.parametrize("name", TEACHING)
    def test_teaching_shots_pause_after_each_idea(self, episodes, name):
        for s in episodes[name][1:-1]:
            if "post" in s:
                assert s.get("pause", A.PAD) >= 0.4

    @pytest.mark.parametrize("name", TEACHING)
    def test_table_shots_carry_a_caption(self, episodes, name):
        for s in episodes[name]:
            if "post" in s:
                assert s["ov"].get("cap"), s["text"]

    @pytest.mark.parametrize("name", list(V.CLIPS))
    def test_captions_fit_on_screen(self, episodes, name):
        for s in episodes[name]:
            if s.get("ov", {}).get("cap"):
                x0, y0, x1, y1 = A.caption_box(s["ov"])
                assert 20 <= x0 and x1 <= R.W - 20 and 0 <= y0 and y1 <= R.H, cap_words(s)

    @pytest.mark.parametrize("name", list(V.CLIPS))
    def test_cameras_and_overlays_inside_the_view(self, episodes, name):
        for s in episodes[name]:
            x, y, w = s.get("cam") or A.FULL
            h = w * 9 / 16
            assert x >= 0 and y >= -1e-9 and x + w <= 1920 + 1e-9 and y + h <= 1080 + 1e-9
            ov = s.get("ov", {})
            for ax, ay, label, side in ov.get("arrows", []):
                assert x <= ax <= x + w and y <= ay <= y + h, (label, s["text"])
            for x0, y0, x1, y1 in ov.get("focus", []):
                assert x0 < x1 and y0 < y1
                assert x1 > x and x0 < x + w and y1 > y and y0 < y + h, s["text"]
            for px, py, *_ in ov.get("pops", []) + ov.get("badges", []):
                assert x <= px <= x + w and y <= py <= y + h, s["text"]
            cap = A.caption_box(ov) if ov.get("cap") else None
            for pop in ov.get("pops", []):
                b = A.pop_box(pop, (x, y, w), cap, len(ov["pops"]))
                assert 0 <= b[0] and b[2] <= R.W and 0 <= b[1] and b[3] <= R.H
                if cap:
                    assert not (b[0] < cap[2] and cap[0] < b[2] and b[1] < cap[3] and cap[1] < b[3]), \
                        (pop, s["text"])

    @pytest.mark.parametrize("name", list(V.CLIPS))
    def test_british_spelling_and_manual_names(self, episodes, name):
        for s in episodes[name]:
            words = s["text"] + " " + cap_words(s)
            assert not re.search(r"\bcolor|\bcenter\b", words, re.I), words
            assert not re.search(r"\bstones?\b|\bbowl\b", words, re.I), words   # no SotW words

    def test_manual_names_are_used(self, episodes):
        text = " ".join(s["text"] for S in episodes.values() for s in S).lower()
        for name in ("factory display", "centre of the table", "pattern line", "wall",
                     "floor line", "box lid", "starting player marker", "score track",
                     "score marker", "player board"):
            assert name in text, name

    def test_game_words_are_explained_on_first_use(self, episodes):
        """Each game word is explained the first time the series says it. 'Next: ...'
        teasers at the end of an episode don't count as a use."""
        parts = []
        for k in V.CLIPS:
            for s in episodes[k]:
                t = s["text"]
                if t.startswith("Remember."):
                    t = t.split(" Next")[0]
                parts.append(t)
        text = " ".join(parts)
        for word, explain in [
                (r"\bturns?\b", "Each go is called a turn"),
                (r"\btiles?\b", "They are called tiles"),
                (r"\bplayer board", "Each player has their own player board"),
                (r"\bwall\b", "The grid on the right is her wall"),
                (r"\bpoints?\b", "Tiles on the wall score points"),
                (r"\brounds?\b", "That cycle is called a round"),
                (r"\bwinner\b", "That player is the winner"),
                (r"\bscore track\b", "Along the top is the score track"),
                (r"\bscore marker\b", "The score marker is a small black cube"),
                (r"\bfactory displays?\b", "These cardboard discs hold the tiles"),
                (r"\bcentre\b", "The space inside the circle is the centre of the table"),
                (r"\bstarting player\b", "That player is the starting player"),
                (r"\bdraw", "That's called drawing"),
                (r"\bbox lid\b", "It is the lid of the game box"),
                (r"\bclockwise\b", "Clockwise means"),
                (r"\bpattern lines?\b", "are her pattern lines"),
                (r"\brows?\b", "A row goes across"),
                (r"\bcomplete\b", "Now the line is complete"),
                (r"\bfloor line\b", "The floor line is the seven spaces"),
                (r"\bcolumns?\b", "A column goes down"),
                (r"\bneighbours?\b", "A neighbour is a tile right beside it"),
                (r"\bunbroken\b", "Unbroken means"),
                (r"\bbonus", "A bonus is extra points"),
                (r"\btie\b", "A tie means"),
                (r"\bvariant\b", "A variant is a different way to play")]:
            m = re.search(word, text, re.I)
            assert m, word
            at = text.find(explain)
            assert at >= 0, explain
            assert at <= m.start() + 200, (word, text[max(0, m.start() - 80):m.start() + 80])


# ================================================================ numbers
def _delta_source(S, i):
    """The animated segment that produced segment i's state (itself, or an earlier one
    showing the very same state)."""
    for j in range(i, -1, -1):
        if S[j].get("pre") is not None and S[j]["post"] is S[i]["post"]:
            return S[j]
    return None


class TestNumbers:
    @pytest.mark.parametrize("name", list(V.CLIPS))
    def test_claimed_numbers_are_spoken(self, episodes, name):
        for s in episodes[name]:
            for k, v in s.get("claim", {}).items():
                assert V.num(abs(v)) in s["text"].lower(), (k, v, s["text"])

    @pytest.mark.parametrize("name", list(V.CLIPS))
    def test_claimed_points_match_the_score_change(self, episodes, name):
        """A claim {player: n} is the wall/bonus points the engine just added for that player
        (with the claimed floor penalty applied, never below 0)."""
        S = episodes[name]
        checked = 0
        for i, s in enumerate(S):
            for p, n in s.get("claim", {}).items():
                if not isinstance(p, int):
                    continue
                src = _delta_source(S, i)
                assert src is not None, s["text"]
                before = src["pre"]["boards"][p]["score"]
                after = src["post"]["boards"][p]["score"]
                floor = s["claim"].get("floor", 0)
                assert after == max(0, before + n + floor), (s["text"], before, n, after)
                checked += 1
        if name not in ("02-getting-ready", "03-taking-tiles", "04-pattern-lines",
                        "08-the-next-round"):
            assert checked, name

    @pytest.mark.parametrize("name", list(V.CLIPS))
    def test_floor_claims_match_floor_penalty(self, episodes, name):
        S = episodes[name]
        for i, s in enumerate(S):
            if "floor" not in s.get("claim", {}):
                continue
            src = _delta_source(S, i) or s
            counts = {len(st["boards"][p]["floor"]) for st in (src.get("pre"), src["post"]) if st
                      for p in range(2)}
            assert s["claim"]["floor"] in {E.floor_penalty(n) for n in counts}, s["text"]

    @pytest.mark.parametrize("name", list(V.CLIPS))
    def test_pops_show_engine_points(self, episodes, name):
        """Every '+N' pop on a wall tile equals engine.score_placement for that tile."""
        for s in episodes[name]:
            for x, y, label, mode in s.get("ov", {}).get("pops", []):
                if not label.startswith("+") or "post" not in s:
                    continue
                for p in range(2):
                    for r in range(5):
                        for c in range(5):
                            if R.wall_xy(p, r, c) == (x, y):
                                w = s["post"]["boards"][p]["wall"]
                                assert w[r][c]
                                pre = (s.get("pre") or s["post"])["boards"][p]["wall"]
                                if pre[r][c] is None:
                                    assert E.score_placement(w, r, c) == int(label[1:])

    def test_setup_numbers(self, episodes):
        S = episodes["02-getting-ready"]
        s = by_text(S, "Two players use")
        for n, k in E.FACTORIES.items():
            assert f"{V.num(n)} players use {V.num(k)}" in s["text"].lower()
        s = by_text(S, "tiles in the bag")
        assert V.num(E.TOTAL_TILES) in s["text"] and V.num(E.TILES_PER_COLOUR) in s["text"]
        s = by_text(S, "She puts exactly")
        assert all(len(f) == E.TILES_PER_FACTORY for f in s["post"]["factories"])

    def test_taking_tiles(self, episodes):
        S = episodes["03-taking-tiles"]
        s = by_text(S, "Ana takes both blue tiles")
        assert s["post"]["boards"][0]["lines"][2] == {"colour": "blue", "count": 2}
        s = by_text(S, "slide into the centre of the table")
        assert V.num(len(s["post"]["centre"])) in s["text"]
        s = by_text(S, "So she also takes the")
        assert E.MARKER in s["post"]["boards"][0]["floor"] and s["pre"]["centre_marker"]
        s = by_text(S, "The marker is already gone")
        assert E.MARKER not in s["post"]["boards"][1]["floor"]

    def test_pattern_line_rules(self, episodes):
        S = episodes["04-pattern-lines"]
        s = by_text(S, "So yellow can't go in pattern line two")
        assert not E.can_place(s["post"]["boards"][0], 1, "yellow")
        s = by_text(S, "red tiles. She picks line two")
        b0, b1 = s["pre"]["boards"][0], s["post"]["boards"][0]
        assert b1["lines"][1] == {"colour": "red", "count": 2}
        assert len(b1["floor"]) - len(b0["floor"]) == 1

    def test_floor_line_examples(self, episodes):
        S = episodes["05-the-floor-line"]
        s = by_text(S, "That's four points")
        assert len(s["post"]["boards"][0]["floor"]) == 3 and E.floor_penalty(3) == -4
        s = by_text(S, "Three tiles and the marker cost")
        assert V.points(-E.floor_penalty(4)) in s["text"]
        s = by_text(S, "All seven spaces cost")
        assert V.points(-E.floor_penalty(7)) in s["text"]
        s = by_text(S, "but stops at zero")
        assert s["post"]["boards"][0]["score"] == 0 and s["pre"]["boards"][0]["score"] > 0

    def test_scoring_examples_match_the_engine(self, episodes):
        S = episodes["07-scoring-a-wall-tile"]
        for key, sub in [("alone", "No neighbours? It scores"), ("corner", "Corners don't count"),
                         ("across", "Unbroken means"), ("down", "right below a tile"),
                         ("gap", "An empty space stops the count"), ("cross", "Add them: ")]:
            rows, (r, c) = V.SCORING[key]
            w = E.wall_from_rows(list(rows) + ["....."] * (5 - len(rows)))
            assert w[r][c] is None
            w[r][c] = E.wall_colour(r, c)
            pts = E.score_placement(w, r, c)
            assert V.points(pts) in by_text(S, sub)["text"].lower(), key
        assert E.score_placement(*[E.wall_from_rows(["...K.", "...R.", ".WBYR", ".....", "....."]),
                                   2, 3]) == 7      # the manual's 4 + 3 example

    def test_end_bonus_example(self, episodes):
        S = episodes["09-end-of-the-game"]
        s = by_text(S, "Ana's bonus:")
        bb = E.bonus_breakdown(s["post"]["boards"][0]["wall"])
        assert V.points(bb["total"]) in s["text"]
        assert bb == {**bb, "rows": 1, "columns": 2, "colours": 1}
        assert by_text(S, "Each complete row: plus")["text"].count(V.num(E.ROW_BONUS))
        assert V.num(E.COLUMN_BONUS) in by_text(S, "Each complete column")["text"]
        assert V.num(E.COLOUR_BONUS) in by_text(S, "Each colour with all five")["text"]
        s = by_text(S, "fills the last space in row two")
        assert E.complete_rows(s["post"]["boards"][0]["wall"]) == 1

    def test_grey_wall(self, episodes):
        S = episodes["10-grey-wall-variant"]
        s = by_text(S, "may go in")
        w = s["post"]["boards"][0]["wall"]
        assert V.num(len(E.grey_columns(w, 0, "blue"))) in s["text"]
        s = by_text(S, "So all tiles of that line fall")
        assert s["post"]["boards"][0]["floor"] == ["red", "red"]
        assert s["post"]["variant"] == E.GREY


# ================================================================ sample
class TestSampleGame:
    def test_matches_the_engine_game(self, episodes):
        S = episodes[SAMPLE]
        g, log = V.sample_log()
        end = log[-1]
        sc, win = end["scores"], end["winners"]
        assert S[-1]["post"]["boards"][0]["score"] == sc[0]
        assert S[-1]["post"]["boards"][1]["score"] == sc[1]
        if len(win) == 1:
            assert f"{V.NAMES[win[0]]} wins, {V.num(max(sc))} to {V.num(min(sc))}" in S[-1]["text"]
        for p in (0, 1):
            s = by_text(S, f"{V.NAMES[p]}'s bonus")
            assert V.points(end["bonuses"][p]["total"]) in s["text"]

    def test_every_turn_is_shown_in_order(self, episodes):
        S = episodes[SAMPLE]
        g, log = V.sample_log()
        turns = [e for e in log if e["type"] == "turn"]
        shown = [s for s in S if s.get("ov", {}).get("bar", "").count("· Turn")]
        assert len(shown) == len(turns)
        for s, e in zip(shown, turns):
            assert s["post"] == e["post"]

    def test_featured_turns_are_narrated_and_others_fast(self, episodes):
        S = episodes[SAMPLE]
        g, log = V.sample_log()
        turns = [e for e in log if e["type"] == "turn"]
        feat = V.featured(turns)
        shown = [s for s in S if s.get("ov", {}).get("bar", "").count("· Turn")]
        for i, s in enumerate(shown):
            if i in feat:
                assert s["text"].startswith(V.NAMES[turns[i]["player"]] + " takes")
                assert not s.get("fast")
            else:
                assert s.get("fast") and (not s["text"] or s["text"] in V.SKIP_LINES)

    def test_featured_turns_cover_the_key_moments(self):
        g, log = V.sample_log()
        turns = [e for e in log if e["type"] == "turn"]
        feat = V.featured(turns)
        assert {0, 1} <= feat
        assert any(turns[i]["took_marker"] for i in feat)
        assert any(turns[i]["to_floor"] for i in feat)

    def test_turn_words(self):
        ev = {"player": 1, "move": E.Move(2, "red", 1), "taken": 3, "placed": 2, "to_floor": 1,
              "took_marker": False, "pushed": 1}
        t = V.turn_words(ev, None)
        assert t == ("Ben takes three red tiles from a factory display. Two go in line two. "
                     "One extra tile falls to the floor line. One tile slides into the centre.")
        ev = {"player": 0, "move": E.Move(E.CENTRE, "blue", E.FLOOR), "taken": 2, "placed": 0,
              "to_floor": 2, "took_marker": True, "pushed": 0}
        assert V.turn_words(ev, None) == ("Ana takes two blue tiles from the centre. She puts them "
                                          "straight on her floor line. First from the centre, so the "
                                          "marker comes too.")

    def test_tiling_sentences_say_engine_points(self, episodes):
        g, log = V.sample_log()
        for e in log:
            if e["type"] != "tiling":
                continue
            for res in e["results"]:
                t = V.tiling_words(res, detail=False)
                tot = sum(x["points"] for x in res["placements"])
                if res["placements"]:
                    assert V.points(tot) in t
                if res["floor_items"]:
                    assert V.points(-res["floor_penalty"]) in t
                d = V.tiling_words(res, detail=True)
                for x in res["placements"]:
                    assert f"{x['colour']} to the wall, {V.points(x['points'])}" in d

    def test_bonuses_are_not_shown_before_the_end(self, episodes):
        S = episodes[SAMPLE]
        over = by_text(S, "complete row. So the game ends")
        g, log = V.sample_log()
        end = log[-1]
        for p in (0, 1):
            assert over["post"]["boards"][p]["score"] == end["scores"][p] - end["bonuses"][p]["total"]

    @pytest.mark.parametrize("seed", [0, 1, 5, 9])
    def test_other_seeds_build(self, seed, monkeypatch):
        monkeypatch.setattr(V, "GAME_SEED", seed)
        S = V.sample_game()
        for s in S:
            for sent in A.sentences(s["text"]):
                assert len(sent.split()) <= 16, sent
        sc = E.Game(2, seed).play()[-1]["scores"]
        assert S[-1]["post"]["boards"][0]["score"] == sc[0]


# ======================================================= built outputs
def _probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                          "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@pytest.mark.skipif(not shutil.which("ffprobe"), reason="ffprobe not installed")
@pytest.mark.parametrize("name", list(V.CLIPS))
def test_built_video_matches_its_script(episodes, name):
    """If the episode is built: it has video + audio, the right length, and its SRT holds
    exactly the script's sentences (so a wording change forces a rebuild)."""
    mp4, srt = VIDEOS / f"{name}.mp4", VIDEOS / f"{name}.srt"
    if not mp4.exists():
        pytest.skip("not built")
    info = _probe(mp4)
    assert {s["codec_type"] for s in info["streams"]} == {"video", "audio"}
    dur = float(info["format"]["duration"])
    if name == SAMPLE:
        assert 60 <= dur <= 225, dur
    else:
        assert 60 <= dur <= 150, dur
    cues = [c.splitlines()[2:] for c in srt.read_text().strip().split("\n\n")]
    said = [" ".join(c) for c in cues]
    script = [x for s in episodes[name] for x in A.sentences(s["text"])]
    assert said == script
