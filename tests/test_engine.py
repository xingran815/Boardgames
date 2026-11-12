"""Rules-engine tests: hand-built boards first, then simulation sweeps."""
import copy
import itertools
from collections import Counter

import pytest

import engine as E
from conftest import SWEEP_SEEDS, all_states, mk, total_stones

C = E.COLORS  # green yellow blue purple white red


# ============================================================== scoring
class TestScoring:
    def test_empty_board_is_zero(self):
        assert E.total_score(E.new_board()) == 0

    @pytest.mark.parametrize("stones,pts", [
        ([], 0), (["red"], 0), (["red", "blue"], 0),
        (["red", "blue", "white"], 6),
    ])
    def test_rabbit(self, stones, pts):
        assert E.animal_score(mk(rabbit=stones), "rabbit") == pts

    @pytest.mark.parametrize("n,pts", [(0, 0), (1, 1), (2, 3), (3, 6), (4, 9), (5, 14)])
    def test_turtle(self, n, pts):
        assert E.animal_score(mk(turtle=["green"] * n), "turtle") == pts

    @pytest.mark.parametrize("n,pts", [(0, 0), (1, 1), (2, 2), (3, 4), (4, 6), (5, 9), (6, 13)])
    def test_salmon(self, n, pts):
        assert E.animal_score(mk(salmon=C[:n]), "salmon") == pts

    def test_owl_points_constants(self):
        assert E.OWL_POINTS == 4
        assert E.OWL_PAIRS >= 1

    @pytest.mark.parametrize("owl,pairs", [
        ([], 0),
        ([["red"]], 0),
        ([["red", "red"]], 1),
        ([["red", "red"], ["blue"]], 1),
        ([["red", "red"], ["blue", "blue"]], 2),
        ([["red", "red"], ["blue", "blue"], ["green", "green"]], 3),
    ])
    def test_owl(self, owl, pairs):
        assert E.animal_score(mk(owl=owl), "owl") == pairs * E.OWL_POINTS

    def test_owl_full_board_is_max_pairs(self):
        owl = [[c, c] for c in C[:E.OWL_PAIRS]]
        assert E.animal_score(mk(owl=owl), "owl") == E.OWL_POINTS * E.OWL_PAIRS

    @pytest.mark.parametrize("triple,pair,pts", [
        ([], [], 0),
        (["red"] * 2, [], 0),            # incomplete triple scores nothing
        ([], ["blue"], 0),               # incomplete pair scores nothing
        (["red"] * 3, [], 5),
        ([], ["blue"] * 2, 2),
        (["red"] * 3, ["blue"], 5),
        (["red"] * 2, ["blue"] * 2, 2),
        (["red"] * 3, ["blue"] * 2, 14),  # 5 + 2 + 7 bonus
    ])
    def test_beaver(self, triple, pair, pts):
        assert E.animal_score(mk(triple=triple, pair=pair), "beaver") == pts

    @pytest.mark.parametrize("animal,kw,base", [
        ("rabbit", dict(rabbit=["red", "blue", "white"]), 6),
        ("turtle", dict(turtle=["red"] * 4), 9),
        ("salmon", dict(salmon=C[:4]), 6),
        ("owl", dict(owl=[["red", "red"], ["blue", "blue"]]), 8),
        ("beaver", dict(triple=["red"] * 3, pair=["blue"] * 2), 14),
    ])
    def test_spirit_stone_doubles(self, animal, kw, base):
        b = mk(**kw)
        assert E.animal_score(b, animal) == base
        E.place(b, E.CLEAR, (animal, "bonus"))
        assert b["bonus"][animal] is True
        assert E.animal_score(b, animal) == 2 * base
        # doubling only affects that animal
        others = sum(E.animal_score(b, a) for a in E.ANIMALS if a != animal)
        assert E.total_score(b) == 2 * base + others

    def test_bonus_on_empty_animal_scores_zero(self):
        b = mk(bonus=["turtle"])
        assert E.total_score(b) == 0

    def test_total_is_sum_of_animals(self):
        b = mk(rabbit=C[:3], turtle=["red"] * 3, salmon=C[:2], owl=[["blue", "blue"]],
               triple=["white"] * 3, pair=["green"] * 2)
        assert E.total_score(b) == 6 + 6 + 2 + 4 + 14

    @pytest.mark.parametrize("animal,kw", [
        ("rabbit", dict(rabbit=["red", "red", "blue"])),
        ("salmon", dict(salmon=["red", "red", "blue"])),
        ("turtle", dict(turtle=["red", "blue"])),
        ("owl", dict(owl=[["red", "blue"]])),
        ("beaver", dict(triple=["red", "blue", "red"], pair=["blue", "red"])),
    ])
    def test_colour_rule_violations_score_zero(self, animal, kw):
        # Rabbit/Salmon/Turtle/Owl/Beaver each break their colour rule here.
        # Salmon [red, red, blue] is expected to be worth 0 (not 4); etc.
        assert E.animal_score(mk(**kw), animal) == 0


# ============================================================ placements
class TestPlacements:
    def test_empty_board_non_clear_options(self):
        opts = E.placements(mk(), "red")
        assert set(opts) == {("rabbit", None), ("turtle", None), ("salmon", None),
                             ("owl", None), ("beaver", "triple"), ("beaver", "pair")}

    def test_clear_only_on_bonus_spaces(self):
        opts = E.placements(mk(), E.CLEAR)
        assert set(opts) == {(a, "bonus") for a in E.ANIMALS}

    def test_non_clear_never_goes_to_bonus_space(self):
        assert all(slot != "bonus" for _, slot in E.placements(mk(), "green"))

    def test_clear_skips_closed_animals(self):
        opts = E.placements(mk(bonus=["rabbit", "owl"]), E.CLEAR)
        assert {a for a, _ in opts} == {"turtle", "salmon", "beaver"}

    def test_all_closed_means_no_placements(self):
        b = mk(bonus=E.ANIMALS)
        assert E.placements(b, E.CLEAR) == []
        assert E.placements(b, "red") == []

    def test_closed_section_accepts_no_stones(self):
        b = mk(bonus=["turtle"])
        assert "turtle" not in {a for a, _ in E.placements(b, "red")}

    def test_rabbit_rules(self):
        has = lambda b, c: ("rabbit", None) in E.placements(b, c)
        assert has(mk(rabbit=["red"]), "blue")
        assert not has(mk(rabbit=["red"]), "red")
        assert not has(mk(rabbit=["red", "blue", "white"]), "green")  # capacity 3

    def test_turtle_rules(self):
        has = lambda b, c: ("turtle", None) in E.placements(b, c)
        assert has(mk(turtle=["red"]), "red")
        assert not has(mk(turtle=["red"]), "blue")
        assert has(mk(turtle=["red"] * 4), "red")
        assert not has(mk(turtle=["red"] * 5), "red")  # capacity 5

    def test_salmon_rules(self):
        has = lambda b, c: ("salmon", None) in E.placements(b, c)
        assert has(mk(salmon=["red"]), "blue")
        assert not has(mk(salmon=["red"]), "red")
        assert has(mk(salmon=C[:5]), C[5])
        assert not has(mk(salmon=C), "red")  # capacity 6 (and all colours used)

    def test_owl_rules(self):
        has = lambda b, c: ("owl", None) in E.placements(b, c)
        assert has(mk(owl=[["red"]]), "red")      # completes the pair
        assert has(mk(owl=[["red"]]), "blue")     # starts a new pair
        # board with E.OWL_PAIRS pair slots used, one open pair waiting for red
        full = [["green", "green"]] * (E.OWL_PAIRS - 2) + [["white", "white"], ["red"]]
        assert has(mk(owl=full), "red")
        assert not has(mk(owl=full), "blue")      # no free pair slot
        assert not has(mk(owl=full), "white")     # white pair already complete
        complete = [[c, c] for c in C[:E.OWL_PAIRS]]
        assert not has(mk(owl=complete), "red")   # every pair complete

    def test_beaver_rules(self):
        slots = lambda b, c: {s for a, s in E.placements(b, c) if a == "beaver"}
        assert slots(mk(), "red") == {"triple", "pair"}
        assert slots(mk(triple=["red"]), "red") == {"triple", "pair"}
        assert slots(mk(triple=["red"]), "blue") == {"pair"}
        assert slots(mk(triple=["red"] * 3, pair=["red"]), "red") == {"pair"}
        assert slots(mk(triple=["red"] * 3, pair=["red"]), "blue") == set()
        assert slots(mk(triple=["red"] * 3, pair=["blue"] * 2), "red") == set()
        assert slots(mk(pair=["blue"]), "red") == {"triple"}

    @pytest.mark.parametrize("animal", E.ANIMALS)
    def test_coyote_blocks_animal_for_stones_and_spirit_stones(self, animal):
        b = mk()
        for color in C + [E.CLEAR]:
            assert animal not in {a for a, _ in E.placements(b, color, blocked=animal)}
            # other animals are still available
            assert {a for a, _ in E.placements(b, color, blocked=animal)} == \
                   set(E.ANIMALS) - {animal}

    def test_place_updates_board(self):
        b = mk()
        E.place(b, "red", ("rabbit", None))
        E.place(b, "red", ("turtle", None))
        E.place(b, "red", ("salmon", None))
        E.place(b, "red", ("beaver", "triple"))
        E.place(b, "blue", ("beaver", "pair"))
        assert b["rabbit"] == ["red"] and b["turtle"] == ["red"] and b["salmon"] == ["red"]
        assert b["beaver"] == {"triple": ["red"], "pair": ["blue"]}

    def test_place_owl_completes_pair_before_starting_new(self):
        b = mk(owl=[["blue"], ["red"]])
        E.place(b, "red", ("owl", None))
        assert b["owl"] == [["blue"], ["red", "red"]]
        E.place(b, "green", ("owl", None))
        assert b["owl"][-1] == ["green"]

    def test_every_placement_is_legal_after_place(self):
        """Fuzz: placing any option never produces an illegal board."""
        import random
        rng = random.Random(0)
        for _ in range(300):
            b = E.new_board()
            for _ in range(rng.randrange(0, 25)):
                c = rng.choice(C + [E.CLEAR])
                opts = E.placements(b, c)
                if opts:
                    E.place(b, c, rng.choice(opts))
            assert_board_legal(b)


def assert_board_legal(b):
    assert len(set(b["rabbit"])) == len(b["rabbit"]) <= 3
    assert len(set(b["turtle"])) <= 1 and len(b["turtle"]) <= 5
    assert len(set(b["salmon"])) == len(b["salmon"]) <= 6
    assert len(b["owl"]) <= E.OWL_PAIRS
    for p in b["owl"]:
        assert 1 <= len(p) <= 2 and len(set(p)) == 1
    t, p = b["beaver"]["triple"], b["beaver"]["pair"]
    assert len(t) <= 3 and len(set(t)) <= 1 and len(p) <= 2 and len(set(p)) <= 1
    for a in E.ANIMALS:
        assert E.CLEAR not in E.stones_in(b, a)


# ================================================================ remove
class TestRemove:
    def test_owl_removes_exactly_one_stone(self):
        b = mk(owl=[["red", "red"], ["blue", "blue"]])
        E.remove(b, "owl", "red")
        assert len(E.stones_in(b, "owl")) == 3
        assert Counter(E.stones_in(b, "owl")) == Counter(["red", "blue", "blue"])

    def test_owl_prefers_incomplete_pair(self):
        b = mk(owl=[["red", "red"], ["red"]])
        E.remove(b, "owl", "red")
        assert b["owl"] == [["red", "red"]]
        b = mk(owl=[["red"], ["red", "red"]])
        E.remove(b, "owl", "red")
        assert b["owl"] == [["red", "red"]]

    def test_owl_breaks_complete_pair_when_no_incomplete(self):
        b = mk(owl=[["red", "red"], ["blue"]])
        E.remove(b, "owl", "red")
        assert b["owl"] == [["red"], ["blue"]]
        assert E.animal_score(b, "owl") == 0

    def test_owl_last_stone_drops_empty_pair(self):
        b = mk(owl=[["red"], ["blue", "blue"]])
        E.remove(b, "owl", "red")
        assert b["owl"] == [["blue", "blue"]]

    @pytest.mark.parametrize("animal,kw", [
        ("rabbit", dict(rabbit=["red", "blue"])),
        ("turtle", dict(turtle=["red", "red"])),
        ("salmon", dict(salmon=["red", "blue"])),
    ])
    def test_simple_animals_remove_one(self, animal, kw):
        b = mk(**kw)
        n = len(b[animal])
        E.remove(b, animal, "red")
        assert len(b[animal]) == n - 1 and (b[animal].count("red") == kw[animal].count("red") - 1)

    def test_beaver_removes_one_stone(self):
        b = mk(triple=["red"] * 3, pair=["blue"] * 2)
        E.remove(b, "beaver", "red")
        assert b["beaver"] == {"triple": ["red"] * 2, "pair": ["blue"] * 2}
        E.remove(b, "beaver", "blue")
        assert len(E.stones_in(b, "beaver")) == 3


# ========================================================== game targets
def fresh(seed=1):
    g = E.Game(seed=seed)
    g.setup()
    return g


class TestSetup:
    @pytest.mark.parametrize("seed", range(10))
    def test_setup(self, seed):
        g = fresh(seed)
        assert len(g.bowl) == 4 and E.CLEAR not in g.bowl
        assert len(g.bag) == 52
        assert g.bag.count(E.CLEAR) == 8
        pool = Counter(g.bag) + Counter(g.bowl)
        assert all(pool[c] == 8 for c in C + [E.CLEAR])
        assert [len(p) for p in g.piles] == [3, 3]
        assert sorted(g.piles[0] + g.piles[1]) == sorted(E.SPIRITS)
        assert g.cards[0][E.TAKE2] is False
        assert all(v for k, v in g.cards[0].items() if k != E.TAKE2)
        assert all(g.cards[1].values())
        assert g.current == 0 and g.turn_no == 0 and g.coyote is None
        assert total_stones(g.snapshot()) == 56
        assert g.log[0]["type"] == "setup"

    def test_deterministic_per_seed(self):
        a, b = E.Game(seed=9), E.Game(seed=9)
        a.play()
        b.play()
        assert a.log[-1]["state"]["scores"] == b.log[-1]["state"]["scores"]
        assert a.turn_no == b.turn_no

    def test_draw_caps_at_bag_size(self):
        g = fresh()
        g.bag = ["red", "blue"]
        assert len(g.draw(5)) == 2 and g.bag == []

    def test_snapshot_is_a_deep_copy(self):
        g = fresh()
        s = g.snapshot()
        g.boards[0]["rabbit"].append("red")
        g.bowl.append("red")
        assert s["boards"][0]["rabbit"] == [] and len(s["bowl"]) == 4


class TestTargetedRules:
    def force(self, g, action):
        g.choose_action = lambda p: action

    def test_spirit_unavailable_with_fewer_than_three_down(self):
        g = fresh()
        for n_down in range(0, 3):
            cs = {c: True for c in E.CARD_ORDER}
            for c in E.CARD_ORDER[:n_down]:
                cs[c] = False
            g.cards[1] = cs
            assert E.SPIRIT not in g.available(1)
        for c in E.CARD_ORDER[:3]:
            g.cards[1][c] = False
        assert E.SPIRIT in g.available(1)

    def test_spirit_own_card_down_does_not_count(self):
        g = fresh()
        g.cards[1] = {c: True for c in E.CARD_ORDER}
        g.cards[1][E.SPIRIT] = False
        g.cards[1][E.TAKE1A] = g.cards[1][E.TAKE1B] = False
        assert E.SPIRIT not in g.available(1)

    def test_spirit_recovers_all_cards(self):
        g = fresh()
        for c in (E.TAKE1A, E.TAKE1B, E.TAKE2):
            g.cards[0][c] = False
        g.cards[0][E.SPIRIT] = True
        self.force(g, E.SPIRIT)
        g.piles = [["wolf"], ["wolf"]]
        g.do_turn()
        assert all(g.cards[0].values())
        assert g.log[-1]["post"]["cards"][0] == {c: True for c in E.CARD_ORDER}

    def test_eagle_gives_extra_turn_same_player(self):
        g = fresh()
        for c in (E.TAKE1A, E.TAKE1B, E.TAKE2):
            g.cards[0][c] = False
        g.piles = [["eagle"], ["eagle"]]
        self.force(g, E.SPIRIT)
        assert g.do_turn() is True
        assert g.current == 0
        assert g.log[-1]["spirit"] == "eagle"
        assert g.log[-1]["steps"][-1] == ("extra",)

    def test_non_eagle_passes_turn(self):
        g = fresh()
        self.force(g, E.TAKE1A)
        g.do_turn()
        assert g.current == 1

    def test_game_ends_with_five_spirit_stones_out(self):
        g = fresh()
        g.bag = [c for c in g.bag if c != E.CLEAR] + [E.CLEAR] * 4  # 4 left -> 4 out
        assert g.clear_out() == 4
        self.force(g, E.TAKE1A)
        assert g.do_turn() is True
        g.bag.remove(E.CLEAR)  # now 5 are out
        assert g.clear_out() == 5
        self.force(g, E.TAKE1B)
        g.current = 0
        assert g.do_turn() is False
        assert g.log[-1]["type"] == "end"

    def test_game_continues_with_four_out(self):
        g = fresh()
        g.bag = [c for c in g.bag if c != E.CLEAR] + [E.CLEAR] * 4
        self.force(g, E.TAKE1A)
        assert g.do_turn() is True

    def test_end_checked_at_end_of_turn_even_for_eagle(self):
        g = fresh()
        g.bag = [c for c in g.bag if c != E.CLEAR] + [E.CLEAR] * 3
        for c in (E.TAKE1A, E.TAKE1B, E.TAKE2):
            g.cards[0][c] = False
        g.piles = [["eagle"], ["eagle"]]
        self.force(g, E.SPIRIT)
        assert g.do_turn() is False

    @pytest.mark.parametrize("seed", range(40))
    def test_coyote_target_never_current_spot(self, seed):
        g = fresh(seed)
        for opp_animal in E.ANIMALS:
            g.coyote = (1, opp_animal)
            for _ in range(15):
                assert g.coyote_target(0) != opp_animal

    def test_coyote_target_none_when_nothing_eligible(self):
        g = fresh()
        g.boards[1] = mk(bonus=E.ANIMALS)
        assert g.coyote_target(0) is None
        g.boards[1] = mk(bonus=E.ANIMALS[1:])
        g.coyote = (1, E.ANIMALS[0])
        assert g.coyote_target(0) is None

    def test_coyote_target_skips_closed_animals(self):
        g = fresh()
        g.boards[1] = mk(bonus=["rabbit", "turtle", "salmon", "owl"])
        for _ in range(20):
            assert g.coyote_target(0) == "beaver"

    def test_add3_moves_coyote_to_opponent(self):
        g = fresh()
        self.force(g, E.ADD3)
        g.do_turn()
        steps = [s for s in g.log[-1]["steps"] if s[0] == "coyote"]
        assert len(steps) == 1 and g.coyote[0] == 1
        assert len(g.bowl) == 7

    def test_half_coyote_only_when_both_take_one_face_down(self):
        g = fresh()
        self.force(g, E.TAKE1A)
        g.do_turn()
        assert not any(s[0].startswith("coyote") for s in g.log[-1]["steps"])
        assert g.coyote is None
        # now same player plays the other Take One: coyote completes
        g.current = 0
        self.force(g, E.TAKE1B)
        g.do_turn()
        kinds = [s[0] for s in g.log[-1]["steps"]]
        assert "coyote_half" in kinds and g.coyote[0] == 1

    def test_half_coyote_not_for_other_cards(self):
        g = fresh()
        g.cards[0][E.TAKE1A] = False
        g.cards[0][E.TAKE1B] = False   # both already down, but a different card is played
        self.force(g, E.ADD2)
        g.do_turn()
        assert not any(s[0] == "coyote_half" for s in g.log[-1]["steps"])

    def test_blocked_animal_never_receives_stone(self):
        g = fresh()
        g.coyote = (0, "turtle")
        g.bowl = ["red", "red", "red", "red"]
        g.boards[0] = mk(bonus=["rabbit", "salmon", "owl", "beaver"])
        # only the blocked turtle would accept red: nothing placeable
        assert E.placements(g.boards[0], "red", g.blocked(0)) == []
        res = g.pick_from_bowl(0, 1)
        assert res[0][1] is None
        assert g.boards[0]["turtle"] == []

    def test_blocked_helper(self):
        g = fresh()
        g.coyote = (1, "owl")
        assert g.blocked(1) == "owl" and g.blocked(0) is None

    def test_pick_from_bowl_places_and_removes(self):
        g = fresh()
        g.bowl = ["red", "blue", "white", "green"]
        res = g.pick_from_bowl(0, 2)
        assert len(res) == 2 and len(g.bowl) == 2
        for c, w in res:
            assert w is not None

    # ---- Ram / place_both
    def test_place_both_order_matters(self):
        b = mk(rabbit=["green"], bonus=["turtle", "salmon", "owl", "beaver"])
        g = fresh()
        # [clear, red]: clear on rabbit first would close it; place_both must try red first
        res = g.place_both(b, [E.CLEAR, "red"], None)
        assert len(res) == 2 and all(w is not None for _, w in res)
        assert {c for c, _ in res} == {E.CLEAR, "red"}

    def test_place_both_places_what_it_can_when_impossible(self):
        b = mk(rabbit=["green"], bonus=["turtle", "salmon", "owl", "beaver"])
        g = fresh()
        res = g.place_both(b, ["red", "red"], None)  # second red cannot go anywhere
        assert sum(1 for _, w in res if w) == 1

    def test_place_both_respects_blocked(self):
        g = fresh()
        b = mk(bonus=["turtle", "salmon", "owl", "beaver"])
        res = g.place_both(b, ["red", "blue"], "rabbit")
        assert all(w is None for _, w in res)

    def test_place_both_does_not_mutate_board(self):
        g = fresh()
        b = mk()
        before = copy.deepcopy(b)
        g.place_both(b, ["red", "blue"], None)
        assert b == before

    def test_place_both_result_is_legal_sequence(self):
        g = fresh()
        b = mk(rabbit=["red"], turtle=["blue"])
        res = g.place_both(b, ["red", "blue"], None)
        b2 = copy.deepcopy(b)
        for c, w in res:
            if w:
                assert w in E.placements(b2, c)
                E.place(b2, c, w)


# =============================================================== sweeps
def can_place_both(board, stones, blocked):
    for order in itertools.permutations(stones):
        def rec(b, rest):
            if not rest:
                return True
            for w in E.placements(b, rest[0], blocked):
                b2 = copy.deepcopy(b)
                E.place(b2, rest[0], w)
                if rec(b2, rest[1:]):
                    return True
            return False
        if rec(board, list(order)):
            return True
    return False


def turns(log):
    return [e for e in log if e["type"] == "turn"]


class TestSimulationSweep:
    def test_games_terminate_properly(self, games):
        for s, (g, log) in games.items():
            assert log[-1]["type"] == "end", s
            assert g.turn_no < 200, s
            assert log[-1]["state"]["clear_out"] >= 5, s
            for e in turns(log)[:-1]:
                assert e["post"]["clear_out"] < 5, (s, e["turn"])

    def test_stones_always_conserved(self, games):
        for s, (g, log) in games.items():
            for st in all_states(log):
                assert total_stones(st) == 56, s

    def test_clear_stones_conserved_and_only_on_bonus(self, games):
        for s, (g, log) in games.items():
            for st in all_states(log):
                n = st["bag_clear"] + st["bowl"].count(E.CLEAR) + sum(
                    sum(b["bonus"].values()) for b in st["boards"])
                assert n == 8, s

    def test_boards_always_legal(self, games):
        for s, (g, log) in games.items():
            for st in all_states(log):
                for b in st["boards"]:
                    assert_board_legal(b)

    def test_scores_match_boards(self, games):
        for s, (g, log) in games.items():
            for st in all_states(log):
                assert st["scores"] == [E.total_score(b) for b in st["boards"]]
                assert st["clear_out"] == 8 - st["bag_clear"]

    def test_card_discipline(self, games):
        for s, (g, log) in games.items():
            for e in turns(log):
                p, act = e["player"], e["action"]
                cs = e["pre"]["cards"][p]
                if act is None:
                    continue
                assert cs[act], (s, e["turn"])               # only face-up cards played
                if act == E.SPIRIT:
                    down = sum(1 for k in E.CARD_ORDER if k != E.SPIRIT and not cs[k])
                    assert down >= 3, (s, e["turn"])
                    assert all(e["post"]["cards"][p].values())
                else:
                    assert not e["post"]["cards"][p][act]
                # opponent's cards untouched
                assert e["post"]["cards"][1 - p] == e["pre"]["cards"][1 - p]

    def test_turn_order_and_eagle(self, games):
        seen_eagle = 0
        for s, (g, log) in games.items():
            ts = turns(log)
            for a, b in zip(ts, ts[1:]):
                if a.get("spirit") == "eagle":
                    seen_eagle += 1
                    assert b["player"] == a["player"], (s, a["turn"])
                else:
                    assert b["player"] == 1 - a["player"], (s, a["turn"])
            assert ts[0]["player"] == 0
        assert seen_eagle > 0  # the sweep really exercises the Eagle

    def test_coyote_never_targets_its_own_spot(self, games):
        n = 0
        for s, (g, log) in games.items():
            for e in turns(log):
                for st in e["steps"]:
                    if st[0] in ("coyote", "coyote_half"):
                        n += 1
                        _, opp, tgt, was = st
                        assert (opp, tgt) != was, (s, e["turn"])
                        assert opp == 1 - e["player"]
        assert n > 50

    def test_coyote_step_only_from_add3_or_half(self, games):
        for s, (g, log) in games.items():
            for e in turns(log):
                for st in e["steps"]:
                    if st[0] == "coyote":
                        assert e["action"] == E.ADD3
                    if st[0] == "coyote_half":
                        assert e["action"] in (E.TAKE1A, E.TAKE1B)

    def test_half_coyote_iff_both_take_one_down(self, games):
        hits = 0
        for s, (g, log) in games.items():
            for e in turns(log):
                if e["action"] not in (E.TAKE1A, E.TAKE1B):
                    assert not any(st[0] == "coyote_half" for st in e["steps"])
                    continue
                p = e["player"]
                other = E.TAKE1B if e["action"] == E.TAKE1A else E.TAKE1A
                both = not e["pre"]["cards"][p][other]
                opp_board = e["pre"]["boards"][1 - p]
                elig = any(not opp_board["bonus"][a] and e["pre"]["coyote"] != (1 - p, a)
                           for a in E.ANIMALS)
                has = any(st[0] == "coyote_half" for st in e["steps"])
                assert has == (both and elig), (s, e["turn"])
                hits += has
        assert hits > 10

    def test_coyote_state_matches_steps(self, games):
        for s, (g, log) in games.items():
            for e in turns(log):
                last = None
                for st in e["steps"]:
                    if st[0] in ("coyote", "coyote_half"):
                        last = (st[1], st[2])
                assert e["post"]["coyote"] == (last or e["pre"]["coyote"])

    def test_blocked_animal_never_gets_stones(self, games):
        for s, (g, log) in games.items():
            for e in turns(log):
                p = e["player"]
                co = e["pre"]["coyote"]
                blocked = co[1] if co and co[0] == p else None
                if blocked is None:
                    continue
                pre_b, post_b = e["pre"]["boards"][p], e["post"]["boards"][p]
                assert E.stones_in(post_b, blocked) == E.stones_in(pre_b, blocked) \
                    or e.get("spirit") == "deer"
                assert post_b["bonus"][blocked] == pre_b["bonus"][blocked]

    def test_ram_places_both_when_possible(self, games):
        n_ram = n_both = 0
        for s, (g, log) in games.items():
            for e in turns(log):
                for st in e["steps"]:
                    if st[0] != "ram":
                        continue
                    n_ram += 1
                    p = e["player"]
                    co = e["pre"]["coyote"]
                    blocked = co[1] if co and co[0] == p else None
                    res = st[1]
                    stones = [c for c, _ in res]
                    possible = can_place_both(e["pre"]["boards"][p], stones, blocked)
                    placed = [w for _, w in res if w is not None]
                    if possible:
                        n_both += 1
                        assert len(placed) == 2, (s, e["turn"], res)
                    # unplaced stones return to the bowl, placed ones never to blocked animal
                    assert all(w[0] != blocked for w in placed)
        assert n_ram > 5 and n_both > 0

    def test_every_spirit_power_is_exercised(self, games):
        used = {e["spirit"] for _, (g, log) in games.items() for e in turns(log) if e.get("spirit")}
        assert used == set(E.SPIRITS)

    def test_spirit_piles_rotate_not_lose_cards(self, games):
        for s, (g, log) in games.items():
            for st in all_states(log):
                assert sorted(st["piles"][0] + st["piles"][1]) == sorted(E.SPIRITS)
                assert [len(p) for p in st["piles"]] == [3, 3]

    def test_spirit_turn_records_card_from_top_of_a_pile(self, games):
        for s, (g, log) in games.items():
            for e in turns(log):
                if e["action"] == E.SPIRIT:
                    tops = [p[0] for p in e["pre"]["piles"]]
                    assert e["spirit"] in tops
                    assert e["steps"][-1][0] in ("recover", "extra")


def test_same_seed_same_game_across_hash_seeds():
    import subprocess
    import sys
    code = ("import engine as E; "
            "print([(g.turn_no, g.play()[-1]['state']['scores']) "
            "for g in [E.Game(seed=s) for s in range(120)]])")
    import os
    sotw = os.path.dirname(E.__file__)
    outs = {subprocess.run([sys.executable, "-c", code], cwd=sotw, capture_output=True, text=True,
                           env={**os.environ, "PYTHONHASHSEED": h}).stdout for h in ("1", "3")}
    assert len(outs) == 1
