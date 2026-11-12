"""Rules engine + simple AI for Spirits of the Wild (2 players).

Used only to generate an accurate, rules-legal sample game for the
explainer videos. Rules follow the 2019 German rulesheet (Owl pair = 4 pts)
cross-checked with the 2017 English rulebook (where Owl pair = 3 pts).
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

COLORS = ["green", "yellow", "blue", "purple", "white", "red"]
CLEAR = "clear"
ANIMALS = ["rabbit", "turtle", "salmon", "owl", "beaver"]

# Board capacities. Rabbit/Turtle/Salmon/Beaver follow from the scoring
# tracks; the number of Owl pairs is not stated in the rules text, so we
# assume three pairs here (only matters for the simulated demo game).
OWL_PAIRS = 3
OWL_POINTS = 4  # German 2019 edition; English 2017 printing says 3
TURTLE_PTS = [0, 1, 3, 6, 9, 14]
SALMON_PTS = [0, 1, 2, 4, 6, 9, 13]

TAKE1A, TAKE1B, TAKE2, ADD2, ADD3, SPIRIT = (
    "take1a", "take1b", "take2", "add2", "add3", "spirit")
CARD_ORDER = [TAKE1A, TAKE1B, TAKE2, ADD2, ADD3, SPIRIT]
CARD_NAMES = {
    TAKE1A: "Take One Stone",
    TAKE1B: "Take One Stone",
    TAKE2: "Take Two Stones",
    ADD2: "Add Two Stones & Take One",
    ADD3: "Add Three Stones & Move Coyote",
    SPIRIT: "Use Spirit Power & Recover Cards",
}
SPIRITS = ["bear", "wolf", "ram", "eagle", "deer", "bison"]


def new_board():
    return {
        "rabbit": [], "turtle": [], "salmon": [],
        "owl": [],  # list of pairs, each a list of 1-2 colors
        "beaver": {"triple": [], "pair": []},
        "bonus": {a: False for a in ANIMALS},
    }


def stones_in(board, animal):
    s = board[animal]
    if animal == "owl":
        return [c for p in s for c in p]
    if animal == "beaver":
        return s["triple"] + s["pair"]
    return list(s)


def animal_score(board, animal):
    s = board[animal]
    same = lambda xs: len(set(xs)) <= 1
    if animal == "rabbit":
        pts = 6 if len(s) == 3 and len(set(s)) == 3 else 0
    elif animal == "turtle":
        pts = TURTLE_PTS[len(s)] if same(s) else 0
    elif animal == "salmon":
        pts = SALMON_PTS[len(s)] if len(set(s)) == len(s) else 0
    elif animal == "owl":
        pts = OWL_POINTS * sum(1 for p in s if len(p) == 2 and same(p))
    else:
        t = len(s["triple"]) == 3 and same(s["triple"])
        p = len(s["pair"]) == 2 and same(s["pair"])
        pts = (5 if t else 0) + (2 if p else 0) + (7 if t and p else 0)
    return pts * (2 if board["bonus"][animal] else 1)


def total_score(board):
    return sum(animal_score(board, a) for a in ANIMALS)


def placements(board, color, blocked=None):
    """All legal placements for one stone: list of (animal, slot) tuples.
    slot is None, 'bonus', 'triple' or 'pair'."""
    out = []
    for a in ANIMALS:
        if a == blocked or board["bonus"][a]:
            continue
        if color == CLEAR:
            out.append((a, "bonus"))
            continue
        s = board[a]
        if a == "rabbit" and len(s) < 3 and color not in s:
            out.append((a, None))
        elif a == "turtle" and len(s) < 5 and (not s or s[0] == color):
            out.append((a, None))
        elif a == "salmon" and len(s) < 6 and color not in s:
            out.append((a, None))
        elif a == "owl":
            if any(len(p) == 1 and p[0] == color for p in s) or len(s) < OWL_PAIRS:
                out.append((a, None))
        elif a == "beaver":
            t, p = s["triple"], s["pair"]
            if len(t) < 3 and (not t or t[0] == color):
                out.append((a, "triple"))
            if len(p) < 2 and (not p or p[0] == color):
                out.append((a, "pair"))
    return out


def place(board, color, where):
    a, slot = where
    if slot == "bonus":
        board["bonus"][a] = True
    elif a == "owl":
        for p in board["owl"]:
            if len(p) == 1 and p[0] == color:
                p.append(color)
                return
        board["owl"].append([color])
    elif a == "beaver":
        board["beaver"][slot].append(color)
    else:
        board[a].append(color)


def remove(board, animal, color):
    if animal == "owl":
        # take from an unfinished pair first, otherwise break a finished one
        pairs = sorted((p for p in board["owl"] if color in p), key=len)
        pairs[0].remove(color)
        board["owl"] = [p for p in board["owl"] if p]
    elif animal == "beaver":
        for k in ("pair", "triple"):
            if color in board["beaver"][k]:
                board["beaver"][k].remove(color)
                return
    else:
        board[animal].remove(color)


# ---------------------------------------------------------------- heuristics
def potential(board):
    """Score plus partial credit for unfinished sets (AI evaluation only)."""
    v = total_score(board)
    for a in ANIMALS:
        s = board[a]
        if board["bonus"][a]:
            continue
        if a == "rabbit" and len(s) < 3:
            v += 1.6 * len(s)
        elif a == "owl":
            v += 1.5 * sum(1 for p in s if len(p) == 1)
        elif a == "beaver":
            t, p = len(s["triple"]), len(s["pair"])
            if t < 3:
                v += 1.3 * t
            if p < 2:
                v += 0.7 * p
        elif a == "turtle" and 0 < len(s) < 5:
            v += 0.8  # room to grow
    return v


def clear_value(board, animal):
    """Value of capping an animal with a Spirit Stone now."""
    cur = animal_score(board, animal)
    room = {
        "rabbit": 3 - len(board["rabbit"]),
        "turtle": 5 - len(board["turtle"]),
        "salmon": 6 - len(board["salmon"]),
        "owl": OWL_PAIRS * 2 - len(stones_in(board, "owl")),
        "beaver": 5 - len(stones_in(board, "beaver")),
    }[animal]
    return cur - 1.8 * room


def best_placement(board, color, blocked, pref=None):
    opts = placements(board, color, blocked)
    if not opts:
        return None, -99
    best, bv = None, -1e9
    base = potential(board)
    for w in opts:
        if w[1] == "bonus":
            v = clear_value(board, w[0])
        else:
            b2 = copy.deepcopy(board)
            place(b2, color, w)
            v = potential(b2) - base + (pref or {}).get(w[0], 0)
        if v > bv:
            best, bv = w, v
    return best, bv


# ---------------------------------------------------------------- game state
@dataclass
class Game:
    seed: int = 1
    rng: random.Random = field(init=False)
    bag: list = field(default_factory=list)
    bowl: list = field(default_factory=list)
    boards: list = field(default_factory=lambda: [new_board(), new_board()])
    cards: list = field(default_factory=lambda: [
        {c: True for c in CARD_ORDER}, {c: True for c in CARD_ORDER}])
    piles: list = field(default_factory=list)
    coyote: tuple | None = None  # (player, animal)
    current: int = 0
    turn_no: int = 0
    log: list = field(default_factory=list)
    names: tuple = ("Ana", "Ben")
    # mild per-player taste so the demo game uses every animal
    prefs: tuple = ({"salmon": 1.4, "beaver": 0.6}, {"beaver": 1.4, "salmon": 0.4})

    def __post_init__(self):
        self.rng = random.Random(self.seed)

    # -------------------------------------------------------------- helpers
    def snapshot(self):
        return {
            "bag": len(self.bag),
            "bag_clear": self.bag.count(CLEAR),
            "bowl": list(self.bowl),
            "boards": copy.deepcopy(self.boards),
            "cards": copy.deepcopy(self.cards),
            "piles": [list(p) for p in self.piles],
            "coyote": self.coyote,
            "current": self.current,
            "scores": [total_score(b) for b in self.boards],
            "clear_out": 8 - self.bag.count(CLEAR),
        }

    def draw(self, n):
        n = min(n, len(self.bag))
        got = [self.bag.pop(self.rng.randrange(len(self.bag))) for _ in range(n)]
        return got

    def step(self, ev, t):
        ev["steps"].append(t)
        ev.setdefault("snaps", []).append(self.snapshot())

    def blocked(self, p):
        return self.coyote[1] if self.coyote and self.coyote[0] == p else None

    def setup(self):
        self.bag = [c for c in COLORS + [CLEAR] for _ in range(8)]
        self.rng.shuffle(self.bag)
        while len(self.bowl) < 4:
            s = self.draw(1)[0]
            if s == CLEAR:
                self.bag.append(s)
            else:
                self.bowl.append(s)
        sp = SPIRITS[:]
        self.rng.shuffle(sp)
        self.piles = [sp[:3], sp[3:]]
        self.cards[0][TAKE2] = False
        self.log.append({"type": "setup", "state": self.snapshot()})

    def clear_out(self):
        return 8 - self.bag.count(CLEAR)

    # ------------------------------------------------------- stone choices
    def place_both(self, board, stones, blocked):
        """Ram: place as many of the drawn stones as possible (both if at all
        possible), preferring the best-valued combination."""
        best, key = None, None
        orders = [stones, stones[::-1]] if len(stones) == 2 else [stones]
        for order in orders:
            def rec(b, rest, acc):
                nonlocal best, key
                if not rest:
                    k = (sum(1 for _, w in acc if w), potential(b))
                    if key is None or k > key:
                        best, key = list(acc), k
                    return
                c = rest[0]
                opts = placements(b, c, blocked) or [None]
                for w in opts:
                    b2 = copy.deepcopy(b)
                    if w:
                        place(b2, c, w)
                    rec(b2, rest[1:], acc + [(c, w)])
            rec(copy.deepcopy(board), order, [])
        return best

    def pick_from_bowl(self, p, k=1, exclude_clear=False):
        """Pick up to k stones from the bowl and place them. Returns list of
        (color, placement or None)."""
        res = []
        for _ in range(k):
            if not self.bowl:
                break
            best, bv, bi = None, -1e9, None
            for i, c in enumerate(self.bowl):
                if exclude_clear and c == CLEAR:
                    continue
                w, v = best_placement(self.boards[p], c, self.blocked(p), self.prefs[p])
                if w is not None and v > bv:
                    best, bv, bi = w, v, i
            if bi is None:
                # nothing placeable: the taken stone goes straight back to the bowl
                c = self.bowl[len(res) % len(self.bowl)]
                res.append((c, None))
                continue
            c = self.bowl.pop(bi)
            place(self.boards[p], c, best)
            res.append((c, best))
        return res

    def bowl_value(self, p):
        vals = sorted((best_placement(self.boards[p], c, self.blocked(p), self.prefs[p])[1]
                       for c in self.bowl), reverse=True)
        return vals

    def coyote_target(self, p):
        opp = 1 - p
        b = self.boards[opp]
        best, bv = None, -1e9
        for a in ANIMALS:
            if b["bonus"][a] or self.coyote == (opp, a):
                continue
            # block the section where the opponent can gain the most
            n = len(stones_in(b, a))
            v = n + (3 if a in ("turtle", "salmon") else 0) + self.rng.random()
            if v > bv:
                best, bv = a, v
        return best

    # --------------------------------------------------------------- actions
    def available(self, p):
        cs = self.cards[p]
        out = []
        for c in CARD_ORDER:
            if not cs[c]:
                continue
            if c in (TAKE1A, TAKE1B) and not self.bowl:
                continue
            if c == TAKE2 and len(self.bowl) < 2:
                continue
            if c == SPIRIT and sum(1 for k in CARD_ORDER if k != SPIRIT and not cs[k]) < 3:
                continue
            out.append(c)
        return out

    def choose_action(self, p):
        av = self.available(p)
        vals = self.bowl_value(p)
        top = [v for v in vals if v > 0]
        score = {}
        for c in av:
            if c in (TAKE1A, TAKE1B):
                s = (vals[0] if vals else -5)
            elif c == TAKE2:
                s = sum(vals[:2]) + 0.5 if len(vals) >= 2 else -5
            elif c == ADD2:
                s = (vals[0] if vals else 0) * 0.7 + 1.6
            elif c == ADD3:
                s = 1.0 + (1.5 if self.coyote is None or self.coyote[0] == p else 0.5)
            elif c == SPIRIT:
                s = 3.5
            score[c] = s + self.rng.random() * 0.6
        if not score:
            return None
        return max(score, key=score.get)

    def do_turn(self):
        p = self.current
        pre = self.snapshot()
        act = self.choose_action(p)
        ev = {"type": "turn", "player": p, "turn": self.turn_no, "action": act,
              "pre": pre, "steps": []}
        if act is None:
            self.step(ev, ("pass",))
        elif act in (TAKE1A, TAKE1B):
            self.step(ev, ("take", self.pick_from_bowl(p, 1)))
        elif act == TAKE2:
            self.step(ev, ("take", self.pick_from_bowl(p, 2)))
        elif act == ADD2:
            d = self.draw(2)
            self.bowl += d
            self.step(ev, ("draw", d))
            self.step(ev, ("take", self.pick_from_bowl(p, 1)))
        elif act == ADD3:
            d = self.draw(3)
            self.bowl += d
            self.step(ev, ("draw", d))
            tgt = self.coyote_target(p)
            if tgt:
                was = self.coyote
                self.coyote = (1 - p, tgt)
                self.step(ev, ("coyote", 1 - p, tgt, was))
        extra = False
        if act is not None and act != SPIRIT:
            self.cards[p][act] = False
            if act in (TAKE1A, TAKE1B) and not self.cards[p][TAKE1A] and not self.cards[p][TAKE1B]:
                tgt = self.coyote_target(p)
                if tgt:
                    was = self.coyote
                    self.coyote = (1 - p, tgt)
                    self.step(ev, ("coyote_half", 1 - p, tgt, was))
        if act == SPIRIT:
            extra = self.do_spirit(p, ev)
            for c in CARD_ORDER:
                self.cards[p][c] = True
            self.step(ev, ("recover",))
        ev["post"] = self.snapshot()
        self.log.append(ev)
        self.turn_no += 1
        if self.clear_out() >= 5:
            self.log.append({"type": "end", "state": self.snapshot()})
            return False
        if not extra:
            self.current = 1 - p
        else:
            self.step(ev, ("extra",))
        return True

    def do_spirit(self, p, ev):
        # choose the better of the two face-up spirit cards (simple heuristic)
        tops = [(i, pile[0]) for i, pile in enumerate(self.piles) if pile]
        pref = {"eagle": 3, "deer": 2.5, "wolf": 2.4, "ram": 2.2, "bison": 2.0, "bear": 1.5}
        if len(self.bowl) <= 1:
            pref["bear"] = 0.5
        i, card = max(tops, key=lambda t: pref[t[1]] + self.rng.random() * 0.8)
        self.piles[i].pop(0)
        self.piles[i].append(card)
        ev["spirit"] = card
        extra = False
        b = self.boards[p]
        if card == "bear":
            n = len(self.bowl)
            self.bag += self.bowl
            self.bowl = []
            self.step(ev, ("bear_return", n))
            d = self.draw(n)
            self.bowl += d
            self.step(ev, ("draw", d))
            self.step(ev, ("take", self.pick_from_bowl(p, 1)))
        elif card == "wolf":
            d = self.draw(4)
            self.bowl += d
            self.step(ev, ("draw", d))
            self.step(ev, ("take", self.pick_from_bowl(p, 1)))
        elif card == "ram":
            d = self.draw(2)
            res = self.place_both(b, d, self.blocked(p))
            for c, w in res:
                if w is None:
                    self.bowl.append(c)
                else:
                    place(b, c, w)
            self.step(ev, ("ram", res))
        elif card == "eagle":
            self.step(ev, ("take", self.pick_from_bowl(p, 1)))
            extra = True
        elif card == "deer":
            # remove the least useful stone from own board
            best = None
            base = potential(b)
            for a in ANIMALS:
                if b["bonus"][a] or a == self.blocked(p):
                    continue
                for c in sorted(set(stones_in(b, a))):
                    b2 = copy.deepcopy(b)
                    remove(b2, a, c)
                    loss = base - potential(b2)
                    if best is None or loss < best[0]:
                        best = (loss, a, c)
            if best:
                remove(b, best[1], best[2])
                self.bowl.append(best[2])
                self.step(ev, ("deer_remove", best[2], best[1]))
            self.step(ev, ("take", self.pick_from_bowl(p, 2)))
        elif card == "bison":
            d = self.draw(3)
            self.bowl += d
            self.step(ev, ("draw", d))
            self.step(ev, ("take", self.pick_from_bowl(p, 1)))
            if self.bowl:
                # prefer returning a Spirit Stone (delays the end), else a random one
                c = CLEAR if CLEAR in self.bowl else self.rng.choice(self.bowl)
                self.bowl.remove(c)
                self.bag.append(c)
                self.step(ev, ("bison_return", c))
        return extra

    def play(self, max_turns=200):
        self.setup()
        while self.turn_no < max_turns and self.do_turn():
            pass
        return self.log


if __name__ == "__main__":
    import sys
    for seed in range(int(sys.argv[1]) if len(sys.argv) > 1 else 20):
        g = Game(seed=seed)
        log = g.play()
        end = log[-1]
        sp = [e.get("spirit") for e in log if e.get("spirit")]
        coy = sum(1 for e in log if e["type"] == "turn" for s in e["steps"] if s[0].startswith("coyote"))
        print(seed, "turns", g.turn_no, "scores", end["state"]["scores"], "spirits", sp, "coyote", coy)
