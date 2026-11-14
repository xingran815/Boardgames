"""Build the Azul beginner video series.

    AZUL_WORK=/tmp/azul-build python3 tools/azul/videos.py [01-what-is-this-game ...]
    (default: every episode)

A short episode series: each teaching episode covers one idea, with big on-screen
captions, a "Remember" recap and a "Next" teaser. Every point value that is
spoken or shown comes from tools/azul/engine.py.

Needs ffmpeg, Pillow, numpy, kokoro-onnx and the Kokoro model files in
tools/voices/ (see tools/setup_env.sh). Output: docs/azul/videos/.
"""
from __future__ import annotations

import copy
import importlib.util
import os
import random
import sys
from collections import Counter
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name):
    full = f"azul_{name}"
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(full, _HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod


A = _load("anim")
R = A.R
E = R.E

ROOT = _HERE.parents[1]
OUT = ROOT / "docs" / "azul" / "videos"
WORK = Path(os.environ.get("AZUL_WORK", "/tmp/azul-build"))
GAME_SEED = 13
NAMES = ("Ana", "Ben")
PRON = ({"s": "she", "o": "her", "p": "her"}, {"s": "he", "o": "him", "p": "his"})
B, Y, RD, K, WH = E.COLOURS      # blue yellow red black white
FLOOR = E.FLOOR
CENTRE = E.CENTRE

_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
         "fourteen fifteen sixteen seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def num(n):
    """Number in words, 0-199 (TTS-friendly)."""
    n = int(n)
    if n < 0:
        return "minus " + num(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return _TENS[t] + ("" if o == 0 else " " + _ONES[o])
    if n < 200:
        return "one hundred" + ("" if n == 100 else " and " + num(n - 100))
    raise ValueError(n)


def ordinal_line(r):
    """0-based pattern line / wall row -> spoken 1-based number."""
    return num(r + 1)


def points(n):
    return f"{num(n)} point" + ("" if abs(n) == 1 else "s")


def tiles_word(n, colour=None):
    c = f" {colour}" if colour else ""
    if n == 1:
        return f"one{c} tile"
    return f"{num(n)}{c} tiles"


def list_words(xs):
    xs = list(xs)
    if not xs:
        return "nothing"
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def cap1(s):
    return s[:1].upper() + s[1:]


# ------------------------------------------------------------------ camera
FULL = A.FULL


def clamp_cam(x, y, w):
    h = w * 9 / 16
    return (max(0, min(1920 - w, x)), max(0, min(1080 - h, y)), w)


def cam_on(box, w):
    x0, y0, x1, y1 = box
    return clamp_cam((x0 + x1) / 2 - w / 2, (y0 + y1) / 2 - w * 9 / 32, w)


def cam_board(p):
    """One whole board; a one-line caption fits at the bottom, under the floor line."""
    return cam_on(R.board_box(p), 1300)


def cam_wall(p):
    """Pattern lines and wall of player p; the top band is free for a caption."""
    bx = R.BOARD_X[p]
    return clamp_cam(bx + 395 - 480, R.BOARD_Y + R.LINES_DY + 170 - 274, 960)


def cam_lines(p):
    bx = R.BOARD_X[p]
    return clamp_cam(bx + 250 - 450, 1080 - 506.25, 900)


def cam_floor(p):
    return cam_lines(p)


CAM_FACTORIES = clamp_cam(440, 0, 1040)
CAM_CENTRE = cam_on(R.CENTRE_BOX, 800)
CAM_BAG = clamp_cam(0, 0, 800)
CAM_LID = clamp_cam(1120, 0, 800)
CAM_BOARDS = FULL                              # both boards need the full width


def arrow(xy, label, side="down"):
    return (xy[0], xy[1], label, side)


def mid_of(box, side="top"):
    x0, y0, x1, y1 = box
    return {"top": ((x0 + x1) / 2, y0), "bottom": ((x0 + x1) / 2, y1),
            "left": (x0, (y0 + y1) / 2), "right": (x1, (y0 + y1) / 2)}[side]


def grow(box, m=8):
    return (box[0] - m, box[1] - m, box[2] + m, box[3] + m)


def score_xy(p):
    return R.BOARD_X[p] + R.BOARD_W - 48, R.BOARD_Y + 8


def floor_mid(p):
    x0, y0, x1, y1 = R.floor_box(p)
    return (x0 + x1) / 2, y0


# ------------------------------------------------------------------ states
class Demo:
    """A hand-made table built with engine primitives. Tiles always come out of the
    bag, so the table holds exactly 100 tiles at every step."""

    def __init__(self, seed=3, variant=E.COLOURED, holder=0):
        st = E.new_state(2, seed=seed, variant=variant, first_player=0)
        st["round"], st["phase"], st["marker_holder"] = 1, "offer", holder
        self.st = st

    def snap(self):
        return copy.deepcopy(self.st)

    def _pull(self, colour):
        self.st["bag"].remove(colour)
        return colour

    def factories(self, *fs):
        for i, f in enumerate(fs):
            assert not self.st["factories"][i]
            self.st["factories"][i] = [self._pull(c) for c in f]
        return self

    def fill(self, indices=None, limit=None):
        """Fill factory displays from the bag with the engine's own draw (seeded).
        limit: stop after that many tiles (to show the bag running out)."""
        rng = E._rng(self.st)
        n = 0
        for i in (range(len(self.st["factories"])) if indices is None else indices):
            f = self.st["factories"][i]
            while len(f) < E.TILES_PER_FACTORY:
                if limit is not None and n >= limit:
                    break
                if not self.st["bag"] and limit is not None:
                    break
                t = E.draw_tile(self.st, rng)
                if t is None:
                    break
                f.append(t)
                n += 1
        self.st["rng_state"] = rng.getstate()
        return self

    def refill_bag(self):
        """Bag ran empty: every tile from the box lid goes into the bag (engine rule)."""
        assert not self.st["bag"]
        rng = E._rng(self.st)
        self.st["bag"], self.st["lid"] = self.st["lid"], []
        rng.shuffle(self.st["bag"])
        self.st["rng_state"] = rng.getstate()
        return self

    def centre(self, *tiles):
        self.st["centre"] += [self._pull(c) for c in tiles]
        return self

    def marker_to_centre(self):
        self.st["centre_marker"], self.st["marker_holder"] = True, None
        return self

    def line(self, p, row, colour, count):
        pl = self.st["boards"][p]["lines"][row]
        assert colour not in self.st["boards"][p]["wall"][row], "colour already in that wall row"
        assert pl["count"] + count <= E.line_capacity(row)
        for _ in range(count):
            self._pull(colour)
        pl["colour"], pl["count"] = colour, pl["count"] + count
        return self

    def wall(self, p, *rows):
        """Put tiles on a wall from strings ('.' empty, any letter = tile there)."""
        w = self.st["boards"][p]["wall"]
        rev = {v: k for k, v in E.LETTERS.items()}
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch == "." or w[r][c]:
                    continue
                colour = rev[ch]
                if self.st["variant"] == E.COLOURED:
                    assert colour == E.wall_colour(r, c), (r, c, ch)
                w[r][c] = self._pull(colour)
        return self

    def put_wall(self, p, row, col, colour=None):
        colour = colour or E.wall_colour(row, col)
        self.st["boards"][p]["wall"][row][col] = self._pull(colour)
        return self

    def floor_add(self, p, *items):
        for t in items:
            self.st["boards"][p]["floor"].append(t if t == E.MARKER else self._pull(t))
        return self

    def to_lid(self, *tiles):
        self.st["lid"] += [self._pull(c) for c in tiles]
        return self

    def score(self, p, n):
        self.st["boards"][p]["score"] = n
        return self

    def take(self, p, src, colour, line, split=False):
        """One turn with the engine's apply_move. split=True also returns the middle
        state: tiles taken (and marker still in the centre), the rest not yet pushed."""
        st = self.st
        st["current"], st["phase"] = p, "offer"
        pre = self.snap()
        info = E.apply_move(st, E.Move(src, colour, line))
        st["phase"] = "offer"
        if not split:
            return info
        mid = copy.deepcopy(st)
        if src != CENTRE:
            mid["factories"][src] = [t for t in pre["factories"][src] if t != colour]
            for t in mid["factories"][src]:
                mid["centre"].remove(t)
        if info["took_marker"]:
            fl = mid["boards"][p]["floor"]
            if E.MARKER in fl:
                fl.remove(E.MARKER)
            mid["centre_marker"], mid["marker_holder"] = True, None
        mid.pop("rng_state", None)
        return info, mid

    def tile_line(self, p, row, col=None):
        """Phase B for one complete pattern line, as engine.tile_wall does it.
        Returns (points, column); column None = grey-wall special case (to floor)."""
        b = self.st["boards"][p]
        pl = b["lines"][row]
        assert pl["count"] == E.line_capacity(row)
        colour = pl["colour"]
        if self.st["variant"] == E.COLOURED:
            col = E.wall_column(row, colour)
        else:
            options = E.grey_columns(b["wall"], row, colour)
            if not options:
                for _ in range(pl["count"]):
                    E._to_floor(self.st, b, colour)
                pl["colour"], pl["count"] = None, 0
                return 0, None
            col = E.best_grey_column(b["wall"], row, colour) if col is None else col
            assert col in options
        b["wall"][row][col] = colour
        pts = E.score_placement(b["wall"], row, col)
        b["score"] += pts
        self.st["lid"].extend([colour] * (pl["count"] - 1))
        pl["colour"], pl["count"] = None, 0
        return pts, col

    def score_floor(self, p):
        """Floor line at the end of phase B. Returns the (negative) penalty."""
        b = self.st["boards"][p]
        items = list(b["floor"])
        pen = E.floor_penalty(len(items))
        b["score"] = max(0, b["score"] + pen)
        self.st["lid"].extend(t for t in items if t != E.MARKER)
        b["floor"] = []
        if E.MARKER in items:
            self.st["marker_holder"] = p
        return pen

    def tile_all(self, p):
        return E.tile_wall(self.st, p)

    def finish(self):
        """End-of-game bonuses (engine)."""
        for b in self.st["boards"]:
            b["score"] += E.end_bonus(b["wall"])
        return self


# ------------------------------------------------------------------ segments
TEACH_PAUSE = 0.9   # silence after each new idea in the teaching episodes


def seg(text, post, pre=None, cam=None, hl=None, show=None, active=None, src_xy=None,
        bar=None, ticker=False, hold=0.6, sfx=(), cap=None, cap_pos="top", arrows=None,
        focus=None, pops=None, badges=None, fade_from=None, xfade=False, say_after=False,
        pause=None, fast=False, claim=None):
    """One narrated shot of the table. Screen overlays (cap, arrows, focus, pops,
    badges, bar, ticker) go in 'ov' so they stay readable at any camera zoom.
    claim: {player: points} that the narration states, checked by the tests."""
    tk = dict(names=NAMES, hl=hl or {})
    if show is not None:
        tk["show"] = list(show)
    if active is not None:
        tk["active"] = active
    if src_xy is not None:
        tk["src_xy"] = tuple(src_xy)
    ov = {}
    if cap:
        ov["cap"] = cap
        if cap_pos != "top":
            ov["cap_pos"] = cap_pos
    if arrows:
        ov["arrows"] = list(arrows)
    if focus:
        ov["focus"] = [grow(b) for b in focus]
    if pops:
        ov["pops"] = list(pops)
    if badges:
        ov["badges"] = list(badges)
    if bar:
        ov["bar"] = bar
    if ticker:
        sc = [b["score"] for b in post["boards"]]
        ov["score"] = f"{NAMES[0]} {sc[0]}  ·  {NAMES[1]} {sc[1]}"
    out = dict(text=text, post=post, pre=pre, tk=tk, cam=cam, hold=hold, sfx=list(sfx), ov=ov)
    if fade_from is not None:
        out["fade_from"] = {"show": list(fade_from)}
    if xfade:
        out["xfade"] = True
    if say_after:
        out["say_after"] = True
    if pause is not None:
        out["pause"] = pause
    if fast:
        out["fast"] = True
    if claim:
        out["claim"] = dict(claim)
    return out


def T(text, post, pre=None, **kw):
    """A teaching shot: like seg(), with a pause after the idea."""
    kw.setdefault("pause", TEACH_PAUSE)
    return seg(text, post, pre, **kw)


def card_seg(text, image, hold=0.8, sfx=(), fade=False, pause=None, cap=None):
    out = dict(text=text, image=image, hold=hold, sfx=list(sfx), ov={"cap": cap} if cap else {})
    if fade is not False and fade is not None:
        out["fade"] = fade        # True: from a blank canvas; an image: crossfade from it
    if pause is not None:
        out["pause"] = pause
    return out


EPISODES = [
    ("01-what-is-this-game", "What is this game?"),
    ("02-getting-ready", "Getting ready"),
    ("03-taking-tiles", "Taking tiles"),
    ("04-pattern-lines", "Pattern lines"),
    ("05-the-floor-line", "The floor line"),
    ("06-moving-tiles-to-the-wall", "Moving tiles to the wall"),
    ("07-scoring-a-wall-tile", "Scoring a wall tile"),
    ("08-the-next-round", "The next round"),
    ("09-end-of-the-game", "End of the game and bonuses"),
    ("10-grey-wall-variant", "The grey wall variant"),
    ("11-sample-game", "Watch a whole game"),
]


def title(n, sub, text):
    name = EPISODES[n - 1][1]
    return card_seg(text, R.title_card(name, sub, kicker=f"Azul · Episode {n}"),
                    fade=True, pause=0.8, sfx=["card"])


def recap(n, lines, text):
    nxt = EPISODES[n][1] if n < len(EPISODES) else None
    return card_seg(text, R.recap_card(lines, nxt), fade=True, hold=1.5, pause=1.6)


ALL = list(R.PARTS)
BOARDS = ["board0", "board1"]
MIDDLE = ["factories", "centre"]


def wall_pop(p, row, col, n):
    x, y = R.wall_xy(p, row, col)
    return (x, y, f"+{n}", "tile")


def row_pop(p, row, n):
    """'+N' just right of a wall row (keeps the counted tiles visible)."""
    x0, y0, x1, y1 = R.wall_row_box(p, row)
    return (x1 + 62, (y0 + y1) / 2, f"+{n}", "at")


def minus(n):
    return f"−{abs(n)}"


def floor_pop(p, pen):
    """'−N' (pen from engine.floor_penalty) just right of the floor line."""
    x, y = R.floor_xy(p, E.FLOOR_SPACES - 1)
    return (x + 150, y, minus(pen), "at")


def demo_factories(D):
    """The same friendly starting offer used by several teaching episodes."""
    return D.factories([B, B, RD, Y], [RD, RD, RD, WH], [K, K, Y, WH], [Y, Y, B, K],
                       [WH, WH, RD, K])


# ============================================================ 1 what is it
def ep_what_is_this_game():
    D = demo_factories(Demo(holder=None))      # the marker is introduced in episode 2
    s0 = D.snap()
    S = [title(1, "2 to 4 players · tiles · a wall · points",
               "Welcome to Azul! This first short video shows what the game is about.")]
    S.append(T("Azul is a game for two to four players. In these videos, two friends play: Ana and Ben.",
               s0, cam=CAM_BOARDS, show=BOARDS, fade_from=[], cap="A game for 2 to 4 players",
               cap_pos="top"))
    S.append(T("They take turns. First, Ana plays.", s0, cam=CAM_BOARDS, show=BOARDS,
               cap="Take turns", focus=[R.board_box(0)], active=0))
    S.append(T("Then Ben plays. Then Ana again, and so on. Each go is called a turn.", s0,
               cam=CAM_BOARDS, show=BOARDS, cap=("A turn", "= one player's go"),
               focus=[R.board_box(1)], active=1))
    S.append(card_seg("The game uses small square pieces. They are called tiles. "
                      "There are five colours: blue, yellow, red, black and white.",
                      R.tiles_card(), fade=True, pause=TEACH_PAUSE))
    S.append(card_seg("Each colour also has its own mark and letter. So you never need colour alone.",
                      R.tiles_card(hl_marks=True), fade=R.tiles_card(), pause=TEACH_PAUSE))
    S.append(T("Each player has their own player board. Look at Ana's board, on the left.", s0,
               cam=cam_board(0), show=BOARDS, fade_from=[], cap="Player board",
               cap_pos="bottom", focus=[R.board_box(0)]))
    S.append(T("The grid on the right is her wall. Her goal is to decorate it with tiles.", s0,
               cam=cam_wall(0), show=BOARDS, cap="The wall", focus=[R.wall_box(0)]))
    S.append(T("In the middle of the table, tiles wait on small discs. The next video gives them a name.",
               s0, cam=CAM_FACTORIES, show=ALL, fade_from=BOARDS, cap="Tiles to collect",
               cap_pos="bottom"))
    pre = D.snap()
    D.take(0, 0, B, 1)
    s1 = D.snap()
    S.append(T("On her turn, Ana takes some tiles. They wait on the left side of her board.", s1, pre,
               cam=FULL, say_after=True, cap="Collect tiles", active=0,
               hl={"lines": {0: [1]}}))
    pre = D.snap()
    pts, col = D.tile_line(0, 1)
    s2 = D.snap()
    S.append(T(f"Later, one tile moves onto her wall. Tiles on the wall score points. "
               f"This one scores {points(pts)}.", s2, pre, cam=cam_wall(0), say_after=True,
               cap="Wall tiles score points", pops=[wall_pop(0, 1, col, pts)], sfx=["chime"],
               claim={0: pts}))
    S.append(T("Her points are shown at the top of her board.", s2, cam=cam_board(0),
               cap="Points", cap_pos="bottom", hl={"score": 0},
               arrows=[arrow(score_xy(0), "Score", "down")]))
    S.append(T("Players collect tiles, then move them to their walls. That cycle is called a round. "
               "A game has several rounds.", s2, cam=FULL,
               cap=("A round", "collect tiles, then move them to the wall"), cap_pos="mid"))
    S.append(T("When the game ends, the player with the most points wins. That player is the winner.",
               s2, cam=CAM_BOARDS, show=ALL, cap="Most points wins!", sfx=["win"],
               focus=[R.score_box(0), R.score_box(1)]))
    S.append(recap(1, ["Players take turns collecting tiles.", "Tiles on your wall score points.",
                       "Most points at the end wins."],
                   "Remember. Players take turns collecting tiles. Tiles on your wall score points. "
                   "And the most points at the end wins. Next up: getting the game ready."))
    return S


# ============================================================ 2 getting ready
def ep_getting_ready():
    D = Demo(holder=None)
    s0 = D.snap()
    nf = E.FACTORIES
    S = [title(2, "Setting up the table, step by step",
               "Let's set up the game together, one step at a time.")]
    S.append(T("Each player takes a player board. Everyone uses the same side: the coloured side.",
               s0, cam=CAM_BOARDS, show=BOARDS, fade_from=[], cap="1. A board each, coloured side"))
    S.append(T("All player boards are the same. Every board has the same wall pattern.", s0,
               cam=CAM_BOARDS, show=BOARDS, cap="All boards are the same",
               focus=[R.wall_box(0), R.wall_box(1)]))
    x0, y0 = R.BOARD_X[0] + 290, R.BOARD_Y + 30
    S.append(T("Along the top is the score track. It counts your points, from zero to one hundred.",
               s0, cam=cam_board(0), show=BOARDS, cap="Score track", cap_pos="bottom",
               focus=[R.score_box(0)]))
    S.append(T("Put your score marker on zero. The score marker is a small black cube.", s0,
               cam=cam_board(0), show=BOARDS, cap="2. Score marker on 0", cap_pos="bottom",
               arrows=[arrow((x0, y0 + 8), "Score marker", "down")]))
    S.append(card_seg("Next, the factory displays. These cardboard discs hold the tiles that players take.",
                      R.factories_card(), fade=True, pause=TEACH_PAUSE))
    S.append(card_seg(f"Two players use {num(nf[2])}. Three players use {num(nf[3])}. "
                      f"Four players use {num(nf[4])}.", R.factories_card(hl=2),
                      fade=R.factories_card(), pause=TEACH_PAUSE))
    shown = BOARDS + ["factories"]
    S.append(T("Put them in a circle, in the middle of the table.", s0, cam=CAM_FACTORIES,
               show=shown, fade_from=BOARDS, cap="3. Factory displays in a circle", cap_pos="bottom"))
    shown = shown + ["centre"]
    S.append(T("The space inside the circle is the centre of the table.", s0, cam=CAM_FACTORIES,
               show=shown, fade_from=shown[:-1], cap="The centre of the table", cap_pos="bottom",
               focus=[R.CENTRE_BOX]))
    shown = shown + ["bag"]
    S.append(T(f"Put all {num(E.TOTAL_TILES)} tiles in the bag. "
               f"That's {num(E.TILES_PER_COLOUR)} of each colour.", s0, cam=CAM_BAG, show=shown,
               fade_from=shown[:-1], cap=f"4. All {E.TOTAL_TILES} tiles in the bag"))
    pre = D.snap()
    D.st["marker_holder"] = 0
    s1 = D.snap()
    S.append(T("Choose who goes first. That player is the starting player. "
               "Here it's Ana. She takes the starting player marker.", s1, pre, cam=cam_board(0),
               show=shown, say_after=True, cap="5. Starting player marker", cap_pos="bottom",
               arrows=[arrow((R.marker_home(0)[0], R.marker_home(0)[1] + 22), "Marker", "down")]))
    S.append(card_seg("The marker is not a tile. It never goes on a wall.", R.marker_card(),
                      fade=True, pause=TEACH_PAUSE))
    pre = D.snap()
    D.fill([0])
    s2 = D.snap()
    S.append(T("Ana reaches into the bag without looking, and takes out tiles. That's called drawing.",
               s2, pre, cam=clamp_cam(0, 0, 1300), show=shown, say_after=True,
               cap="6. Draw tiles from the bag", cap_pos="bottom"))
    pre = D.snap()
    D.fill()
    s3 = D.snap()
    S.append(T(f"She puts exactly {num(E.TILES_PER_FACTORY)} tiles on each factory display.", s3, pre,
               cam=CAM_FACTORIES, show=shown, say_after=True,
               cap=f"{E.TILES_PER_FACTORY} tiles on each display", cap_pos="bottom"))
    S.append(T("Keep the box lid nearby, empty. It is the lid of the game box. Spare tiles wait in it later.",
               s3, cam=CAM_LID, show=ALL, fade_from=shown, cap="7. Empty box lid nearby",
               cap_pos="bottom"))
    S.append(T("And that's it. You're ready to play!", s3, cam=FULL, cap="Ready!", cap_pos="mid",
               sfx=["win"]))
    S.append(recap(2, ["Everyone: same side, score marker on 0.",
                       f"{nf[2]}, {nf[3]} or {nf[4]} factory displays for 2, 3 or 4 players.",
                       f"The starting player puts {E.TILES_PER_FACTORY} tiles on each display."],
                   "Remember. Everyone uses the same board side, with score markers on zero. "
                   f"Use {num(nf[2])}, {num(nf[3])} or {num(nf[4])} factory displays, for two, three "
                   f"or four players. The starting player puts {num(E.TILES_PER_FACTORY)} tiles on "
                   "each one. Next: taking tiles."))
    return S


# ============================================================ 3 taking tiles
def ep_taking_tiles():
    D = demo_factories(Demo())
    s0 = D.snap()
    S = [title(3, "One colour, all of it",
               "What do you do on your turn? You take tiles. Here's how.")]
    pre = s0
    s1 = D.marker_to_centre().snap()
    S.append(T("At the start of a round, the starting player puts the marker in the centre.", s1, pre,
               cam=FULL, say_after=True, cap="Marker to the centre", active=0))
    S.append(T("Then the starting player takes the first turn. Here, that's Ana.", s1, cam=FULL,
               cap="Ana goes first", active=0, focus=[R.board_box(0)]))
    S.append(T("Turns go clockwise. Clockwise means the next player is the one on your left. "
               "With two players, they simply swap.", s1, cam=FULL,
               cap=("Clockwise", "the next player is on your left"), cap_pos="mid"))
    S.append(T("On your turn, you must take tiles. You have two choices.", s1, cam=CAM_FACTORIES,
               cap="Two choices", cap_pos="bottom"))
    S.append(T("Choice one: pick a factory display. Then pick one colour on it.", s1,
               cam=CAM_FACTORIES, cap=("Choice 1", "one colour from a factory display"),
               cap_pos="bottom", focus=[R.factory_box(0, 6)]))
    pre = D.snap()
    info, mid = D.take(0, 0, B, 2, split=True)
    s2 = D.snap()
    S.append(T(f"Ana takes both blue tiles. You always take every tile of that colour.", mid, pre,
               cam=FULL, say_after=True, cap="All tiles of one colour", active=0))
    S.append(T(f"The other {num(info['pushed'])} tiles on that display slide into the centre of the table. "
               "Now that display is empty.", s2, mid, cam=CAM_FACTORIES, say_after=True,
               cap="The rest go to the centre", cap_pos="bottom",
               focus=[R.CENTRE_BOX, R.factory_box(0, 6)]))
    S.append(T("You can't take only some tiles of a colour. And you can't take two colours.", s2,
               cam=CAM_FACTORIES, cap=("Never some", "never two colours"), cap_pos="bottom"))
    pre = D.snap()
    info, mid = D.take(1, 1, RD, 2, split=True)
    s3 = D.snap()
    S.append(T(f"Now it's Ben's turn. He takes all {num(info['taken'])} red tiles from a display.",
               mid, pre, cam=FULL, say_after=True, cap="Ben's turn", active=1))
    S.append(T("The white one slides into the centre.", s3, mid, cam=FULL, say_after=True,
               cap="The rest go to the centre", active=1, pause=0.6))
    S.append(T("Choice two: take one colour from the centre of the table.", s3, cam=CAM_CENTRE,
               cap=("Choice 2", "one colour from the centre"), cap_pos="bottom",
               focus=[R.CENTRE_BOX]))
    pre = D.snap()
    info, mid = D.take(0, CENTRE, Y, 0, split=True)
    s4 = D.snap()
    S.append(T("Ana takes the yellow tile from the centre. The other tiles stay there.", mid, pre,
               cam=FULL, say_after=True, cap="Take one colour from the centre", active=0))
    S.append(T("She is the first to take from the centre this round. So she also takes the "
               "starting player marker.", s4, mid, cam=FULL, say_after=True,
               cap=("First from the centre?", "take the marker too"), active=0))
    pen = E.floor_penalty(1)
    S.append(T(f"It goes at the bottom of her board. It costs her {points(-pen)}. "
               "But she will go first next round.", s4, cam=cam_floor(0),
               cap=("The marker", f"costs {abs(pen)}, but you start next round"),
               pops=[floor_pop(0, pen)], claim={"floor": pen}))
    pre = D.snap()
    D.take(1, CENTRE, WH, 3)
    s5 = D.snap()
    S.append(T("Later, Ben takes from the centre too. The marker is already gone, so he takes only tiles.",
               s5, pre, cam=FULL, say_after=True, cap="Only the first takes the marker", active=1))
    S.append(T("Players keep taking turns, until every display and the centre are empty.", s5,
               cam=CAM_FACTORIES, cap="Until all tiles are taken", cap_pos="bottom"))
    S.append(recap(3, ["Take all the tiles of one colour.",
                       "From a display: the rest go to the centre.",
                       "First from the centre: take the marker too."],
                   "Remember. Take all the tiles of one colour. From a factory display, the rest go "
                   "to the centre. The first player to take from the centre also takes the marker. "
                   "Next: pattern lines."))
    return S


# ============================================================ 4 pattern lines
def ep_pattern_lines():
    D = Demo()
    D.factories([B, B, RD, K], [B, WH, WH, K], [RD, RD, RD, Y], [Y, Y, K, WH])
    D.marker_to_centre()
    D.put_wall(0, 1, E.wall_column(1, Y))
    s0 = D.snap()
    S = [title(4, "Where your tiles wait",
               "You took some tiles. Where do they go? Onto your pattern lines.")]
    S.append(T("Look at the left side of Ana's board. These five lines of spaces are her pattern lines.",
               s0, cam=cam_wall(0), cap="Pattern lines", focus=[R.lines_box(0)]))
    S.append(T("Line one has one space. Line two has two spaces. And line five has five.", s0,
               cam=cam_wall(0), cap="1 to 5 spaces",
               focus=[R.line_box(0, 0), R.line_box(0, 1), R.line_box(0, 4)]))
    S.append(T("Each line belongs to the wall row beside it. A row goes across.", s0, cam=cam_wall(0),
               cap="Each line → its wall row", focus=[R.line_box(0, 2), R.wall_row_box(0, 2)]))
    pre = D.snap()
    D.take(0, 0, B, 2)
    s1 = D.snap()
    S.append(T("Ana takes two blue tiles. She puts them all in one pattern line: line three.", s1, pre,
               cam=FULL, say_after=True, cap="All in one line", hl={"lines": {0: [2]}}))
    lx, ly = R.line_xy(0, 2, 0)
    S.append(T("Tiles fill a line from right to left. The first tile goes next to the wall.", s1,
               cam=cam_wall(0), cap="Right to left",
               arrows=[arrow((lx, ly + R.T / 2), "First tile", "down")]))
    S.append(T("A pattern line holds one colour only. Line three is now a blue line.", s1,
               cam=cam_wall(0), cap="One colour per line", focus=[R.line_box(0, 2)]))
    pre = D.snap()
    D.take(0, 1, B, 2)
    s2 = D.snap()
    S.append(T("Later, she takes one more blue tile. It fills the last space.", s2, pre, cam=FULL,
               say_after=True, cap="One more blue", hl={"lines": {0: [2]}}, pause=0.5))
    S.append(T("Every space is filled. Now the line is complete.", s2, cam=cam_wall(0),
               cap=("Complete", "every space is filled"), focus=[R.line_box(0, 2)]))
    yc = E.wall_column(1, Y)
    S.append(T("Now look at row two of her wall. It already has a yellow tile.", s2, cam=cam_wall(0),
               cap="Row 2 has yellow", focus=[R.cell_box(0, 1, yc)]))
    S.append(T("So yellow can't go in pattern line two. A colour can't go where its wall row has it.",
               s2, cam=cam_wall(0), cap=("Not allowed", "that colour is already in the wall row"),
               hl={"xs": [("line", 0, 1)]}, focus=[R.line_box(0, 1), R.cell_box(0, 1, yc)]))
    pre = D.snap()
    D.take(0, 3, Y, 4)
    s3 = D.snap()
    S.append(T("Ana puts her two yellow tiles in line five instead.", s3, pre, cam=FULL,
               say_after=True, cap="Yellow to line 5", hl={"lines": {0: [4]}}, pause=0.6))
    pre = D.snap()
    info = D.take(0, 2, RD, 1)
    s4 = D.snap()
    assert info["placed"] == 2 and info["to_floor"] == 1
    S.append(T(f"Next, Ana takes {num(info['taken'])} red tiles. She picks line two, which has two spaces.",
               s4, pre, cam=FULL, say_after=True, cap="3 red, but only 2 spaces",
               hl={"lines": {0: [1]}}))
    S.append(T("Two tiles fill the line. The extra one falls to the floor line. "
               "The floor line is the seven spaces at the bottom.", s4, cam=cam_floor(0),
               cap=("Too many?", "extras fall to the floor line"), focus=[R.floor_box(0)]))
    S.append(T("You may also put all your tiles straight on the floor line.", s4, cam=cam_floor(0),
               cap="Or all on the floor line", focus=[R.floor_box(0)]))
    S.append(recap(4, ["Fill a pattern line from right to left.",
                       "One colour per line, not one in its wall row.",
                       "Extra tiles fall to the floor line."],
                   "Remember. Fill a pattern line from right to left. Each line holds one colour, "
                   "and never a colour already in its wall row. Extra tiles fall to the floor line. "
                   "Next: the floor line."))
    return S


# ============================================================ 5 floor line
def floor_values_words():
    groups = []
    for v in E.FLOOR_VALUES:
        if groups and groups[-1][0] == v:
            groups[-1][1] += 1
        else:
            groups.append([v, 1])
    words = ["first", "next", "last"]
    out = []
    for i, (v, n) in enumerate(groups):
        out.append(f"The {words[min(i, 2)]} {num(n)} say minus {num(-v)}.")
    return " ".join(out)


def ep_the_floor_line():
    D = Demo()
    D.factories([K, K, K, Y], [RD, WH, WH, B], [B, B, B, B], [Y, RD, K, WH], [WH, Y, Y, K])
    D.marker_to_centre()
    # every line is full or holds another colour, so black and blue fit nowhere
    D.line(0, 0, RD, 1).line(0, 1, Y, 1).line(0, 2, WH, 1).line(0, 3, RD, 1).line(0, 4, WH, 1)
    D.score(0, 5)
    s0 = D.snap()
    S = [title(5, "Tiles you can't use cost points",
               "Tiles you can't use don't just disappear. They fall to your floor line, and cost points.")]
    S.append(T(f"This is Ana's floor line. It has {num(E.FLOOR_SPACES)} spaces.", s0, cam=cam_floor(0),
               cap=f"Floor line: {E.FLOOR_SPACES} spaces", focus=[R.floor_box(0)]))
    fx, fy = R.floor_xy(0, 2)
    S.append(T("Under each space is a minus number. Minus means points you lose.", s0, cam=cam_floor(0),
               cap="Minus = points you lose",
               arrows=[arrow((fx, fy + R.T / 2 + 34), "Points lost", "down")]))
    S.append(T(floor_values_words(), s0, cam=cam_floor(0), cap="  ".join(minus(v) for v in E.FLOOR_VALUES),
               focus=[R.floor_box(0)]))
    pre = D.snap()
    D.take(0, 0, K, E.FLOOR)
    s1 = D.snap()
    assert not any(E.can_place(D.st["boards"][0], r, c) for r in range(5) for c in (K, B))
    S.append(T("Ana takes three black tiles. None of her lines can take black. So they go to the floor line.",
               s1, pre, cam=FULL, say_after=True, cap="No room? To the floor line"))
    S.append(T("Tiles fill the floor line from left to right.", s1, cam=cam_floor(0),
               cap="Left to right", focus=[R.floor_box(0)]))
    pen = E.floor_penalty(3)
    S.append(T("When the round ends, add up the numbers under your tiles. You lose that many points.",
               s1, cam=cam_floor(0), cap="Add up the minus numbers", focus=[R.floor_box(0)]))
    S.append(T(f"So these three tiles cost one, plus one, plus two. That's {points(-pen)}.", s1,
               cam=cam_floor(0), cap=f"3 tiles: {minus(pen)}", pops=[floor_pop(0, pen)],
               sfx=["minus"], claim={"floor": pen}))
    pre = D.snap()
    D.take(0, CENTRE, Y, 1)  # the starting player marker comes along
    s2 = D.snap()
    pen4 = E.floor_penalty(len(D.st["boards"][0]["floor"]))
    assert E.MARKER in D.st["boards"][0]["floor"] and len(D.st["boards"][0]["floor"]) == 4
    S.append(T("Later, Ana is the first to take from the centre. The starting player marker joins her floor line.",
               s2, pre, cam=FULL, say_after=True, cap="The marker counts too"))
    S.append(T(f"The marker takes a space, just like a tile. Three tiles and the marker cost {points(-pen4)}.",
               s2, cam=cam_floor(0), cap=f"4 on the floor: {minus(pen4)}", pops=[floor_pop(0, pen4)],
               sfx=["minus"], claim={"floor": pen4}))
    pre = D.snap()
    D.take(0, 2, B, E.FLOOR)
    s3 = D.snap()
    fl = D.st["boards"][0]["floor"]
    pen7 = E.floor_penalty(len(fl))
    assert len(fl) == E.FLOOR_SPACES and D.st["lid"]
    S.append(T("Then she takes four blue tiles. Again, no line can take them.", s3, pre, cam=FULL,
               say_after=True, cap="Four more!", pause=0.5))
    S.append(T(f"The floor line is full. All seven spaces cost {points(-pen7)}. Ouch!", s3,
               cam=cam_floor(0), cap=f"Full floor line: {minus(pen7)}", pops=[floor_pop(0, pen7)],
               sfx=["minus"], claim={"floor": pen7}))
    S.append(T("The last tile didn't fit. Extra tiles go in the box lid. They cost nothing more.", s3,
               cam=CAM_LID, cap="Extras: box lid, no cost", cap_pos="bottom", focus=[R.LID_BOX]))
    before = D.st["boards"][0]["score"]
    pre = D.snap()
    D.score_floor(0)
    s4 = D.snap()
    after = D.st["boards"][0]["score"]
    assert after == 0 and before + pen7 < 0
    S.append(T(f"Ana had {points(before)}. She loses {num(-pen7)}, but stops at zero. "
               "Your score never goes below zero.", s4, pre, cam=FULL, say_after=True,
               cap="Never below 0", pops=[floor_pop(0, pen7)], hl={"score": 0},
               claim={0: after - before}))
    S.append(T("After scoring, floor tiles go in the box lid. Ana keeps the marker. She starts the next round.",
               s4, cam=cam_board(0), cap="Marker: you start next round", cap_pos="bottom",
               arrows=[arrow((R.marker_home(0)[0], R.marker_home(0)[1] + 22), "Marker", "down")]))
    S.append(recap(5, ["Floor line: " + " ".join(minus(v) for v in E.FLOOR_VALUES) + ".",
                       "The starting player marker counts too.",
                       "Your score never goes below 0."],
                   "Remember. Each floor space costs the number under it. The starting player marker "
                   "counts too. And your score never goes below zero. Next: moving tiles to the wall."))
    return S


# ============================================================ 6 moving to the wall
def wall_demo():
    D = Demo(holder=None)
    D.line(0, 0, Y, 1).line(0, 1, RD, 2).line(0, 2, K, 2).line(0, 3, B, 4)
    D.floor_add(0, WH)
    D.line(1, 0, RD, 1).line(1, 2, WH, 3).line(1, 4, Y, 2).floor_add(1, E.MARKER, K)
    D.score(0, 0).score(1, 0)
    return D


def ep_moving_tiles_to_the_wall():
    D = wall_demo()
    s0 = D.snap()
    S = [title(6, "The end of a round",
               "When all the tiles are taken, collecting is over. Now tiles move to your wall.")]
    S.append(T("Every factory display and the centre are empty. Collecting is over.", s0,
               cam=CAM_FACTORIES, cap="No tiles left", cap_pos="bottom"))
    S.append(T("Now everyone moves tiles to their wall, all at the same time.", s0, cam=FULL,
               cap="Move tiles to the wall", cap_pos="mid"))
    S.append(T("Go through your pattern lines from top to bottom.", s0, cam=cam_wall(0),
               cap="Top to bottom", focus=[R.lines_box(0)]))
    pre = D.snap()
    pts, col = D.tile_line(0, 0)
    s1 = D.snap()
    S.append(T("Line one is complete. Its tile moves to the yellow space in the row beside it.", s1, pre,
               cam=cam_wall(0), say_after=True, cap=("Complete line", "one tile moves to the wall"),
               pops=[wall_pop(0, 0, col, pts)]))
    S.append(T(f"It scores {points(pts)}. The next video shows how to count points.", s1,
               cam=cam_wall(0), cap="Score it right away", pops=[wall_pop(0, 0, col, pts)],
               claim={0: pts}))
    pre = D.snap()
    pts2, col2 = D.tile_line(0, 1)
    s2 = D.snap()
    S.append(T(f"Line two is complete too. Its rightmost tile moves to the red space, for "
               f"{points(pts2)}. The other red tile goes in the box lid.", s2, pre, cam=FULL, say_after=True,
               cap=("One tile to the wall", "the rest to the box lid"),
               pops=[wall_pop(0, 1, col2, pts2)], focus=[R.board_box(0), R.LID_BOX],
               claim={0: pts2}))
    S.append(T("Line three is not complete. Its tiles stay where they are, for the next round.", s2,
               cam=cam_wall(0), cap="Not complete? Tiles stay", focus=[R.line_box(0, 2)]))
    pre = D.snap()
    pts3, col3 = D.tile_line(0, 3)
    s3 = D.snap()
    S.append(T(f"Line four is complete. One blue tile moves over, for {points(pts3)}. "
               "The other three go in the box lid.",
               s3, pre, cam=FULL, say_after=True, cap=("One tile to the wall", "the rest to the box lid"),
               pops=[wall_pop(0, 3, col3, pts3)], focus=[R.board_box(0), R.LID_BOX], claim={0: pts3}))
    S.append(T("Line five is empty, so nothing happens there.", s3, cam=cam_wall(0),
               cap="Empty line: nothing", focus=[R.line_box(0, 4)], pause=0.6))
    pre = D.snap()
    pen = D.score_floor(0)
    s4 = D.snap()
    S.append(T(f"Last, the floor line. Ana loses {points(-pen)}, and the tile goes in the box lid.", s4,
               pre, cam=FULL, say_after=True, cap="Then the floor line", pops=[floor_pop(0, pen)],
               sfx=["minus"], claim={"floor": pen}))
    pre = D.snap()
    res = D.tile_all(1)
    D.st["marker_holder"] = 1          # the marker was on his floor line: he keeps it
    s5 = D.snap()
    pops = [wall_pop(1, p["row"], p["col"], p["points"]) for p in res["placements"]]
    pops.append(floor_pop(1, res["floor_penalty"]))
    S.append(T("Ben does the same on his board. He had the marker on his floor line, so he keeps it.",
               s5, pre, cam=FULL, say_after=True, cap="Ben does the same", pops=pops))
    S.append(T("Tiles on the wall stay there until the end of the game.", s5, cam=CAM_BOARDS,
               cap="Wall tiles stay", focus=[R.wall_box(0), R.wall_box(1)]))
    S.append(recap(6, ["Complete lines move one tile to the wall.",
                       "The rest of that line goes in the box lid.",
                       "Lines that aren't complete wait."],
                   "Remember. Each complete line moves one tile to the wall, and scores. The rest of "
                   "that line goes in the box lid. Lines that aren't complete wait for the next round. "
                   "Next: scoring a wall tile."))
    return S


# ============================================================ 7 scoring
def badges_for(p, row, col, wall):
    """Count badges for a new tile at (row, col): across in gold, down in blue."""
    run = lambda cells: cells if len(cells) > 1 else []
    across, down = [], []
    c = col
    while c - 1 >= 0 and wall[row][c - 1]:
        c -= 1
    while c < 5 and wall[row][c]:
        across.append((row, c))
        c += 1
    r = row
    while r - 1 >= 0 and wall[r - 1][col]:
        r -= 1
    while r < 5 and wall[r][col]:
        down.append((r, col))
        r += 1
    out = []
    for i, (r, c) in enumerate(run(across), 1):
        x, y = R.wall_xy(p, r, c)
        out.append((x - 14, y - 16, str(i), "across"))
    for i, (r, c) in enumerate(run(down), 1):
        x, y = R.wall_xy(p, r, c)
        out.append((x + 14, y + 16, str(i), "down"))
    return out, len(run(across)), len(run(down))


def scoring_example(rows, new, holder=None):
    """(pre, post, points, (across, down)) for a new tile at `new` on a wall built
    from `rows`; points straight from the engine."""
    D = Demo(holder=holder)
    D.wall(0, *rows)
    pre = D.snap()
    r, c = new
    D.put_wall(0, r, c)
    w = D.st["boards"][0]["wall"]
    pts = E.score_placement(w, r, c)
    D.st["boards"][0]["score"] += pts
    post = D.snap()
    b, na, nd = badges_for(0, r, c, w)
    return pre, post, pts, b, na, nd


SCORING = {
    "alone": ([".....", "....."], (1, 2)),
    "corner": ([".....", "..Y.."], (2, 3)),
    "across": ([".....", "...RK"], (1, 2)),
    "down": ([".....", "..Y.."], (2, 2)),
    "gap": ([".Y.K."], (0, 0)),
    "cross": (["...K.", "...R.", ".WB.R"], (2, 3)),
}


def ep_scoring_a_wall_tile():
    cam = cam_wall(0)
    S = [title(7, "Count across, count down",
               "Every new wall tile scores points right away. Let's learn to count them.")]
    pre, post, pts, b, na, nd = scoring_example(*SCORING["cross"])
    S.append(T("Here is Ana's wall. A row goes across.", pre, cam=cam, cap="A row goes across",
               focus=[R.wall_row_box(0, 2)]))
    S.append(T("A column goes down.", pre, cam=cam, cap="A column goes down",
               focus=[R.wall_col_box(0, 3)], pause=0.6))
    # 1. no neighbours
    pre, post, pts, b, na, nd = scoring_example(*SCORING["alone"])
    r, c = SCORING["alone"][1]
    src = R.line_xy(0, r, 0)
    S.append(T("Let's start with an empty wall.", pre, cam=cam, cap="An empty wall", xfade=True,
               pre=S[-1]["post"], pause=0.4))
    S.append(T("A new tile lands in row two. It has no neighbours.", post, pre, cam=cam,
               src_xy=src, say_after=True, cap="No neighbours"))
    S.append(T(f"A neighbour is a tile right beside it: left, right, above or below. "
               f"No neighbours? It scores {points(pts)}.", post, cam=cam,
               cap=f"No neighbours: {pts} point", pops=[row_pop(0, r, pts)], claim={0: pts}))
    # 2. corner only
    pre2, post2, pts2, b, na, nd = scoring_example(*SCORING["corner"])
    r2, c2 = SCORING["corner"][1]
    S.append(T(f"This tile touches the first one only at a corner. Corners don't count. "
               f"So it scores {points(pts2)} again.", post2, pre2, cam=cam, src_xy=R.line_xy(0, r2, 0),
               say_after=True, cap="Corners don't count", pops=[row_pop(0, r2, pts2)],
               claim={0: pts2}))
    # 3. across
    pre3, post3, pts3, b3, na, nd = scoring_example(*SCORING["across"])
    r3, c3 = SCORING["across"][1]
    S.append(T("New wall. Two tiles sit side by side in row two.", pre3, post2, cam=cam, xfade=True,
               cap="Side by side", focus=[R.cell_box(0, 1, 3), R.cell_box(0, 1, 4)], pause=0.5))
    S.append(T(f"The new tile lands right beside them. Count the unbroken line across: "
               f"{tiles_word(na)}.", post3, pre3, cam=cam, src_xy=R.line_xy(0, r3, 0), say_after=True,
               cap="Count across", badges=b3))
    S.append(T(f"So it scores {points(pts3)}. Unbroken means no empty space in between.", post3,
               cam=cam, cap=f"{na} across: {pts3} points", badges=b3, pops=[row_pop(0, r3, pts3)],
               claim={0: pts3}))
    # 4. down
    pre4, post4, pts4, b4, na, nd = scoring_example(*SCORING["down"])
    r4, c4 = SCORING["down"][1]
    S.append(T(f"New wall. This time, the new tile lands right below a tile. Count down: "
               f"{tiles_word(nd)}. {cap1(points(pts4))}.", post4, pre4, cam=cam,
               src_xy=R.line_xy(0, r4, 0), say_after=True, cap=f"{nd} down: {pts4} points",
               badges=b4, pops=[row_pop(0, r4, pts4)], claim={0: pts4}))
    # 5. a gap stops the count
    pre5, post5, pts5, b5, na, nd = scoring_example(*SCORING["gap"])
    r5, c5 = SCORING["gap"][1]
    S.append(T("New wall. Look at row one. There is an empty space between these tiles.", pre5,
               post4, cam=cam, xfade=True, cap="A gap", focus=[R.cell_box(0, 0, 2)], pause=0.5))
    S.append(T(f"The new tile lands at the left end. An empty space stops the count. "
               f"Only {num(na)} tiles count: {points(pts5)}.", post5, pre5, cam=cam,
               src_xy=R.line_xy(0, r5, 0), say_after=True, cap="A gap stops the count", badges=b5,
               pops=[row_pop(0, r5, pts5)], claim={0: pts5}))
    # 6. across and down
    pre6, post6, pts6, b6, na, nd = scoring_example(*SCORING["cross"])
    r6, c6 = SCORING["cross"][1]
    S.append(T("The big one. This new tile will have neighbours across and down.", pre6, post5,
               cam=cam, xfade=True, cap="Across and down", focus=[R.cell_box(0, r6, c6)], pause=0.5))
    S.append(T(f"Count across: {tiles_word(na)}. Count down: {tiles_word(nd)}.", post6, pre6, cam=cam,
               src_xy=R.line_xy(0, r6, 0), say_after=True, cap=f"{na} across + {nd} down", badges=b6))
    S.append(T(f"Add them: {num(na)} plus {num(nd)}. {cap1(points(pts6))}! "
               "The new tile counts in both lines.", post6, cam=cam,
               cap=f"{na} + {nd} = {pts6} points", badges=b6, pops=[row_pop(0, r6, pts6)],
               sfx=["chime"], claim={0: pts6}))
    S.append(T("Tip: tiles next to other tiles score more. So build your wall in groups.", post6,
               cam=cam, cap="Tip: build in groups", focus=[R.wall_box(0)]))
    S.append(recap(7, ["No neighbours: 1 point.",
                       "Otherwise: count across, and count down.",
                       "Add both counts together."],
                   "Remember. A tile with no neighbours scores one point. Otherwise, count the "
                   "unbroken line across, and the unbroken line down. Add them together. "
                   "Next: the next round."))
    return S


# ============================================================ 8 next round
def next_round_demo():
    D = Demo(holder=0)
    D.wall(0, "B....", ".B...", "....R")
    D.wall(1, "..R..", "...R.", "....R")
    D.line(0, 2, K, 2).line(1, 3, Y, 1)
    D.score(0, 7).score(1, 9)
    # all but 6 tiles have been used and are now in the box lid
    rng = random.Random(8)
    bag = list(D.st["bag"])
    rng.shuffle(bag)
    keep = bag[:6]
    D.st["lid"] = bag[6:]
    D.st["bag"] = keep
    return D


def ep_the_next_round():
    D = next_round_demo()
    s0 = D.snap()
    S = [title(8, "Refill, and play again",
               "After the walls are done, a new round begins. Here's how to get it ready.")]
    S.append(T("Nobody has filled a whole row of their wall yet. So we play another round.", s0,
               cam=CAM_BOARDS, cap="No full row? Another round", focus=[R.wall_box(0), R.wall_box(1)]))
    S.append(T("Ana has the starting player marker. So she fills the factory displays.", s0,
               cam=cam_board(0), cap="The marker holder fills them", cap_pos="bottom",
               arrows=[arrow((R.marker_home(0)[0], R.marker_home(0)[1] + 22), "Marker", "down")]))
    pre = D.snap()
    D.fill([0])
    s1 = D.snap()
    S.append(T(f"She draws {num(E.TILES_PER_FACTORY)} tiles for each display, just like at the start.",
               s1, pre, cam=FULL, say_after=True, cap=f"{E.TILES_PER_FACTORY} tiles on each display"))
    pre = D.snap()
    D.fill([1], limit=len(D.st["bag"]))
    s2 = D.snap()
    assert not D.st["bag"] and len(D.st["factories"][1]) < E.TILES_PER_FACTORY
    S.append(T("Oh! The bag runs empty halfway.", s2, pre, cam=FULL, say_after=True,
               cap="The bag is empty!", hl={"mid": "bag"}, pause=0.6))
    pre = D.snap()
    n_lid = len(D.st["lid"])
    D.refill_bag()
    s3 = D.snap()
    S.append(T("So pour every tile from the box lid into the bag. Mix them up.", s3, pre, cam=FULL,
               say_after=True, cap="Box lid → bag", hl={"mid": "bag"}))
    pre = D.snap()
    D.fill()
    s4 = D.snap()
    assert all(len(f) == E.TILES_PER_FACTORY for f in D.st["factories"])
    S.append(T("Then keep filling, until each display has four tiles.", s4, pre, cam=FULL,
               say_after=True, cap="Keep filling", pause=0.6))
    S.append(T("The box lid is only emptied when the bag runs out. Never at any other time.", s4,
               cam=CAM_LID, cap="Only when the bag is empty", cap_pos="bottom", focus=[R.LID_BOX]))
    S.append(T("Very rarely, the bag and the box lid are both empty. Then start the round anyway.", s4,
               cam=FULL, cap=("Both empty?", "start the round anyway"), cap_pos="mid"))
    S.append(T("Look at Ana's line three. Its tiles stayed from last round. She can still finish it.",
               s4, cam=cam_wall(0), cap="Unfinished lines carry on", focus=[R.line_box(0, 2)]))
    pre = D.snap()
    D.marker_to_centre()
    s5 = D.snap()
    S.append(T("Now the round starts. Ana puts the marker in the centre, and goes first.", s5, pre,
               cam=FULL, say_after=True, cap="Ana goes first", active=0))
    S.append(recap(8, [f"The marker holder puts {E.TILES_PER_FACTORY} tiles on each display.",
                       "Bag empty? Pour in the box lid, then keep going.",
                       "The marker holder goes first."],
                   f"Remember. The marker holder puts {num(E.TILES_PER_FACTORY)} tiles on each "
                   "display. If the bag runs empty, pour in the box lid and keep going. Then the "
                   "marker holder goes first. Next: the end of the game."))
    return S


# ============================================================ 9 end + bonuses
BONUS_WALL = ["B...W", "WBYRK", "K.B.R", "R..BY", "Y...B"]


def ep_end_of_the_game():
    D = Demo(holder=None)
    D.wall(0, "B....", "WB.RK", "K.B..", "R..B.", "....B")
    D.line(0, 1, Y, 2)
    D.wall(1, "BY...", "WB...", "K.B..", "R..B.", "Y...B")      # a full column, no full row
    D.score(0, 41).score(1, 47)
    pre = D.snap()
    pts, col = D.tile_line(0, 1)
    s1 = D.snap()
    assert E.complete_rows(D.st["boards"][0]["wall"]) == 1
    assert E.complete_columns(D.st["boards"][1]["wall"]) == 1 and not E.complete_rows(D.st["boards"][1]["wall"])
    S = [title(9, "Full rows, bonuses and the winner",
               "How does the game end? And who wins? Let's find out.")]
    S.append(T(f"Ana's yellow tile fills the last space in row two. It scores {points(pts)}.", s1, pre,
               cam=cam_wall(0), say_after=True, cap="Row 2 is full!",
               pops=[wall_pop(0, 1, col, pts)], claim={0: pts}))
    S.append(T("That's five tiles across. It's called a complete row.", s1, cam=cam_wall(0),
               cap=("Complete row", "5 tiles across"), focus=[R.wall_row_box(0, 1)]))
    S.append(T("A complete row ends the game. But first, everyone finishes moving tiles to their wall.",
               s1, cam=FULL, cap="Finish this round's wall moves", cap_pos="mid"))
    S.append(T("Then the game is over. No new round starts.", s1, cam=FULL,
               cap="Then the game is over", cap_pos="mid"))
    S.append(T("A full column does not end the game. Only a full row does.", s1, cam=cam_wall(1),
               cap="Columns don't end the game", focus=[R.wall_col_box(1, 0)]))
    # bonus example: engine breakdown
    Bd = Demo(holder=None)
    Bd.wall(0, *BONUS_WALL)
    Bd.wall(1, "BY...", ".BY..", "..BY.", "...BY", "Y...B")
    Bd.score(0, 38).score(1, 40)
    bb = E.bonus_breakdown(Bd.st["boards"][0]["wall"])
    pre_b = Bd.snap()
    cols = [c for c in range(5) if all(Bd.st["boards"][0]["wall"][r][c] for r in range(5))]
    rows = [r for r in range(5) if all(Bd.st["boards"][0]["wall"][r])]
    S.append(T("Now everyone adds bonus points. A bonus is extra points. Let's look at Ana's final wall.",
               pre_b, s1, cam=cam_wall(0), xfade=True, cap="End bonuses"))
    S.append(T(f"Each complete row: plus {num(E.ROW_BONUS)} points. Ana has {num(bb['rows'])}.", pre_b,
               cam=cam_wall(0), cap=f"Complete row: +{E.ROW_BONUS}",
               focus=[R.wall_row_box(0, r) for r in rows],
               pops=[(R.wall_box(0)[2] + 70, (R.wall_row_box(0, rows[0])[1] + R.wall_row_box(0, rows[0])[3]) / 2,
                      f"+{bb['row_points']}", "at")],
               claim={"bonus_rows": bb["row_points"]}))
    S.append(T(f"Each complete column: plus {num(E.COLUMN_BONUS)} points. Ana has {num(bb['columns'])}. "
               f"That's {num(bb['column_points'])}.", pre_b, cam=cam_wall(0),
               cap=f"Complete column: +{E.COLUMN_BONUS}", focus=[R.wall_col_box(0, c) for c in cols],
               pops=[(R.wall_xy(0, 4, c)[0], R.wall_box(0)[3] + 44, f"+{E.COLUMN_BONUS}", "at") for c in cols],
               claim={"bonus_columns": bb["column_points"]}))
    S.append(T(f"Each colour with all five tiles on your wall: plus {num(E.COLOUR_BONUS)} points. "
               "Ana has all five blue tiles.", pre_b, cam=cam_wall(0),
               cap=f"All 5 of a colour: +{E.COLOUR_BONUS}",
               focus=[R.cell_box(0, r, E.wall_column(r, B)) for r in range(5)],
               claim={"bonus_colours": bb["colour_points"]}))
    Bd.finish()
    post_b = Bd.snap()
    parts = ([num(E.ROW_BONUS)] * bb["rows"] + [num(E.COLUMN_BONUS)] * bb["columns"]
             + [num(E.COLOUR_BONUS)] * bb["colours"])
    S.append(T(f"Ana's bonus: {' plus '.join(parts)}. That's {points(bb['total'])}!", post_b, pre_b,
               cam=cam_board(0), xfade=True, cap=f"Bonus: +{bb['total']}", cap_pos="bottom",
               hl={"score": 0}, pops=[(score_xy(0)[0] - 60, score_xy(0)[1] + 100, f"+{bb['total']}", "at")],
               sfx=["chime"], claim={0: bb["total"]}))
    S.append(T("The player with the most points wins.", post_b, cam=CAM_BOARDS, cap="Most points wins!",
               sfx=["win"], focus=[R.score_box(0), R.score_box(1)], pause=0.6))
    S.append(T("A tie means two players have the same points. Then the one with more complete rows wins.",
               post_b, cam=CAM_BOARDS, cap=("A tie?", "more complete rows wins")))
    S.append(T("Still tied? Then they share the win.", post_b, cam=CAM_BOARDS,
               cap="Still tied? Share the win"))
    S.append(recap(9, ["A full row ends the game, after that round.",
                       f"Bonus: row +{E.ROW_BONUS}, column +{E.COLUMN_BONUS}, colour +{E.COLOUR_BONUS}.",
                       "A tie? More complete rows wins."],
                   "Remember. A complete row ends the game, after that round's wall moves. Then add "
                   f"bonuses: {num(E.ROW_BONUS)} per row, {num(E.COLUMN_BONUS)} per column, and "
                   f"{num(E.COLOUR_BONUS)} per full colour. A tie goes to more complete rows. "
                   "Next: the grey wall variant."))
    return S


# ============================================================ 10 grey wall
def ep_grey_wall_variant():
    D = Demo(variant=E.GREY, holder=None)
    D.wall(0, ".....", "YWK..", "..B..", ".....", "...R.")
    D.put_wall(0, 3, 4, RD)
    D.line(0, 0, B, 1).line(0, 1, RD, 2)
    s0 = D.snap()
    S = [title(10, "A different way to play",
               "Once you know the game, try this. It's called a variant. A variant is a different way to play.")]
    S.append(T("Turn every player board to its grey side. Everyone must use the same side.", s0,
               cam=CAM_BOARDS, show=ALL, cap="Everyone: grey side", focus=[R.wall_box(0), R.wall_box(1)]))
    S.append(T("On the grey side, the wall spaces have no colours.", s0, cam=cam_wall(0),
               cap="No colours on the wall", focus=[R.wall_box(0)]))
    S.append(T("When a line is complete, you choose where its tile goes. Any empty space in that row.",
               s0, cam=cam_wall(0), cap="You choose the space", focus=[R.line_box(0, 0), R.wall_row_box(0, 0)]))
    w = D.st["boards"][0]["wall"]
    ok = E.grey_columns(w, 0, B)
    bad = [c for c in range(5) if c not in ok]
    S.append(T("But each colour may appear only once in each column. Blue is already in column three.",
               s0, cam=cam_wall(0), cap=("Once per column", "each colour, each column"),
               focus=[R.wall_col_box(0, c) for c in bad], hl={"xs": [("cell", 0, 0, c) for c in bad]}))
    S.append(T(f"So Ana's blue tile may go in {num(len(ok))} spaces of row one.", s0, cam=cam_wall(0),
               cap=f"{len(ok)} allowed spaces", focus=[R.cell_box(0, 0, c) for c in ok], pause=0.6))
    pre = D.snap()
    pts, col = D.tile_line(0, 0, col=ok[0])
    s1 = D.snap()
    S.append(T(f"She picks the left one. It scores like normal: {points(pts)}.", s1, pre, cam=cam_wall(0),
               say_after=True, cap="Scoring is the same", pops=[row_pop(0, 0, pts)], claim={0: pts}))
    S.append(T("Each row still holds each colour only once, too.", s1, cam=cam_wall(0),
               cap="Once per row, too", focus=[R.wall_row_box(0, 1)], pause=0.6))
    S.append(T("Now look at line two. It's complete, with red. But red is already in both free columns.",
               s1, cam=cam_wall(0), cap="No allowed space?",
               focus=[R.line_box(0, 1), R.wall_col_box(0, 3), R.wall_col_box(0, 4)]))
    pre = D.snap()
    pts2, col2 = D.tile_line(0, 1)
    s2 = D.snap()
    assert col2 is None
    S.append(T("So all tiles of that line fall to the floor line.", s2, pre, cam=cam_wall(0),
               say_after=True, cap="Then all go to the floor line"))
    S.append(T("Everything else is the same: scoring, the floor line, the end and the bonuses.", s2,
               cam=FULL, cap="Everything else: the same", cap_pos="mid"))
    S.append(recap(10, ["Grey side: choose any empty space in the row.",
                        "Each colour once per row and once per column.",
                        "No allowed space? The line goes to the floor."],
                   "Remember. On the grey side, you choose any empty space in the row. Each colour "
                   "appears once per row and once per column. If no space is allowed, the whole line "
                   "goes to the floor line. Next: watch a whole game."))
    return S


# ============================================================ sample game
def source_words(src):
    return "the centre" if src == CENTRE else "a factory display"


def turn_words(ev, pre, with_push=True):
    """Narration for one featured turn (one idea per sentence)."""
    p, mv = ev["player"], ev["move"]
    who, pr = NAMES[p], PRON[p]
    out = [f"{who} takes {tiles_word(ev['taken'], mv.colour)} from {source_words(mv.source)}."]
    if mv.line == FLOOR:
        out.append(f"{cap1(pr['s'])} puts {'it' if ev['taken'] == 1 else 'them'} straight on "
                   f"{pr['p']} floor line.")
    else:
        if ev["to_floor"]:
            out.append(f"{cap1(num(ev['placed']))} {'goes' if ev['placed'] == 1 else 'go'} in "
                       f"line {ordinal_line(mv.line)}.")
        else:
            it = "it" if ev["placed"] == 1 else "them"
            out.append(f"{cap1(pr['s'])} puts {it} in line {ordinal_line(mv.line)}.")
        if ev["to_floor"]:
            out.append(f"{cap1(tiles_word(ev['to_floor'], 'extra'))} "
                       f"{'falls' if ev['to_floor'] == 1 else 'fall'} to the floor line.")
    if ev["took_marker"]:
        out.append("First from the centre, so the marker comes too.")
    if ev["pushed"] and with_push:
        out.append(f"{cap1(num(ev['pushed']))} {'tile slides' if ev['pushed'] == 1 else 'tiles slide'} "
                   "into the centre.")
    return " ".join(out)


def featured(turns):
    """Which turns (index in `turns`) get narration: the first two of the game, the first
    take from the centre, the first tiles to the floor, and the first move straight to
    the floor line."""
    feat, seen = set(), set()
    for i, ev in enumerate(turns):
        why = []
        if i < 2:
            why.append("start")
        if ev["took_marker"] and "marker" not in seen:
            seen.add("marker")
            why.append("marker")
        if ev["move"].line != FLOOR and ev["to_floor"] and "overflow" not in seen:
            seen.add("overflow")
            why.append("overflow")
        if ev["move"].line == FLOOR and "floor" not in seen:
            seen.add("floor")
            why.append("floor")
        if why:
            feat.add(i)
    return feat


SKIP_LINES = ["A few quick turns.", "Let's skip ahead.", "Fast forward.", "Quick turns now."]


def tiling_words(res, detail):
    """Narration for one player's wall moves. detail=True: one tile per sentence."""
    p = res["player"]
    who, pr = NAMES[p], PRON[p]
    out = []
    pl = res["placements"]
    if detail:
        if not pl:
            out.append(f"{who} has no complete lines.")
        for i, x in enumerate(pl):
            lead = f"{who}'s line" if i == 0 else "Line"
            out.append(f"{lead} {ordinal_line(x['row'])}: {x['colour']} to the wall, {points(x['points'])}.")
    else:
        tot = sum(x["points"] for x in pl)
        if pl:
            out.append(f"{who} moves {tiles_word(len(pl))} to {pr['p']} wall, for {points(tot)}.")
        else:
            out.append(f"{who} has no complete lines this round.")
        best = max(pl, key=lambda x: x["points"], default=None)
        if best and best["points"] >= 6 and len(pl) > 1:
            out.append(f"The {best['colour']} tile scores {num(best['points'])} by itself, "
                       "across and down.")
    if res["floor_items"]:
        out.append(f"{cap1(pr['p'])} floor line costs {points(-res['floor_penalty'])}.")
    return " ".join(out)


def sample_log(seed=None):
    g = E.Game(2, GAME_SEED if seed is None else seed)
    log = g.play()
    rnd = 0
    for e in log:
        if e["type"] == "round":
            rnd = e["round"]
        e.setdefault("round", rnd)
    return g, log


def score_text(st):
    sc = [b["score"] for b in st["boards"]]
    return f"{NAMES[0]} {sc[0]}  ·  {NAMES[1]} {sc[1]}"


def sample_game():
    g, log = sample_log()
    turns = [e for e in log if e["type"] == "turn"]
    feat = featured(turns)
    S = [title(11, "Ana vs Ben · the highlights",
               "Now let's watch Ana and Ben play a whole game. We'll slow down for the big "
               "moments, and skip through the rest.")]
    prev = None
    ti, skip_i, in_skip, n_turn = 0, 0, False, 0
    for e in log:
        if e["type"] == "round":
            st = e["state"]
            sp = NAMES[e["start_player"]]
            label = f"Round {e['round']}"
            if prev is None:
                S.append(seg(f"Ana is on the left. Ben is on the right. Ana is the starting player. "
                             f"The marker is in the centre, and Ana goes first.", st, cam=FULL,
                             ticker=True, bar="Round 1 · setup", active=0, pause=0.6))
            else:
                S.append(seg(f"Round {num(e['round'])}. {sp} has the marker, so {PRON[e['start_player']]['s']} "
                             "starts.", st, prev, cam=FULL, ticker=True,
                             bar=label, fast=True, active=e["start_player"], pause=0.5))
            prev, n_turn, in_skip = st, 0, False
        elif e["type"] == "turn":
            n_turn += 1
            p = e["player"]
            label = f"Round {e['round']} · Turn {n_turn} · {NAMES[p]}"
            if ti in feat:
                in_skip = False
                S.append(seg(turn_words(e, prev, with_push=ti < 2), e["post"], prev, cam=FULL, ticker=True, bar=label,
                             active=p, say_after=True, hold=0.4, pause=0.45))
            else:
                text = ""
                if not in_skip:
                    text = SKIP_LINES[skip_i % len(SKIP_LINES)]
                    skip_i += 1
                in_skip = True
                S.append(seg(text, e["post"], prev, cam=FULL, ticker=True, bar=label, active=p,
                             fast=True, hold=0.25, pause=0.1))
            prev = e["post"]
            ti += 1
        elif e["type"] == "tiling":
            st = e["state"]
            if st["game_over"]:      # the engine adds the end bonuses inside the last tiling
                st = copy.deepcopy(st)
                for b, bb in zip(st["boards"], st["bonuses"]):
                    b["score"] -= bb["total"]
            rnd = e["round"]
            label = f"Round {rnd} · wall-tiling"
            pops, close = [], {}
            for res in e["results"]:
                p = res["player"]
                tot = sum(x["points"] for x in res["placements"])
                if tot:
                    pops.append((score_xy(p)[0] - 60, score_xy(p)[1] + 100, f"+{tot}", "at"))
                close[p] = [(*R.wall_xy(p, x["row"], x["col"]), f"+{x['points']}", "at")
                            for x in res["placements"]]
                if res["floor_items"]:
                    pops.append(floor_pop(p, res["floor_penalty"]))
                    close[p].append(floor_pop(p, res["floor_penalty"]))
            ended = any(E.complete_rows(b["wall"]) for b in st["boards"])
            intro = "All tiles are taken. Time to move tiles to the walls." if rnd == 1 else \
                "Wall-tiling time."
            S.append(seg(intro, st, prev, cam=FULL, ticker=True, bar=label, pops=pops, fast=rnd > 1,
                         hold=0.8, say_after=False, pause=0.3))
            for res in e["results"]:
                p = res["player"]
                S.append(seg(tiling_words(res, detail=(rnd == 1 and p == 0)), st, cam=cam_board(p), ticker=True,
                             bar=label, pops=close[p],
                             claim={p: sum(x["points"] for x in res["placements"]),
                                    **({"floor": res["floor_penalty"]} if res["floor_items"] else {})},
                             pause=0.4))
            if ended:
                who = [NAMES[i] for i, b in enumerate(st["boards"]) if E.complete_rows(b["wall"])]
                S.append(seg(("Both players" if len(who) == 2 else who[0]) +
                             f" now {'have' if len(who) == 2 else 'has'} a complete row. "
                             "So the game ends after this round.", st, cam=CAM_BOARDS, ticker=True,
                             bar="Game over", cap="Game over!",
                             focus=[R.wall_row_box(i, r) for i, b in enumerate(st["boards"])
                                    for r in range(5) if all(b["wall"][r])]))
            prev = st
        elif e["type"] == "end":
            end = e["state"]
            for p in (0, 1):
                bb = e["bonuses"][p]
                bits = []
                if bb["rows"]:
                    bits.append(f"{num(bb['rows'])} row{'s' if bb['rows'] > 1 else ''}")
                if bb["columns"]:
                    bits.append(f"{num(bb['columns'])} column{'s' if bb['columns'] > 1 else ''}")
                if bb["colours"]:
                    bits.append(f"{num(bb['colours'])} full colour{'s' if bb['colours'] > 1 else ''}")
                say = (f"{NAMES[p]}'s bonus: {list_words(bits)}. Plus {points(bb['total'])}." if bits
                       else f"{NAMES[p]} gets no bonus.")
                cur = copy.deepcopy(prev)
                cur["boards"][p]["score"] = end["boards"][p]["score"]
                S.append(seg(say, cur, prev, cam=cam_board(p), ticker=True, bar="End bonuses",
                             xfade=True, pops=[(score_xy(p)[0] - 60, score_xy(p)[1] + 100, f"+{bb['total']}", "at")]
                             if bb["total"] else None, claim={p: bb["total"]}, hl={"score": p}))
                prev = cur
            sc = e["scores"]
            win = e["winners"]
            if len(win) == 1:
                w = win[0]
                say = f"Final score: {NAMES[w]} wins, {num(max(sc))} to {num(min(sc))}! Thanks for watching."
                cap = f"{NAMES[w]} wins!"
            else:
                say = f"Final score: a tie at {num(sc[0])}, with the same rows. They share the win!"
                cap = "A shared win!"
            S.append(seg(say, end, cam=FULL, ticker=True, bar="Final score", cap=(cap, f"{max(sc)} – {min(sc)}"),
                         cap_pos="mid", hold=2.0, sfx=["win"]))
    return S


CLIPS = {
    "01-what-is-this-game": ep_what_is_this_game,
    "02-getting-ready": ep_getting_ready,
    "03-taking-tiles": ep_taking_tiles,
    "04-pattern-lines": ep_pattern_lines,
    "05-the-floor-line": ep_the_floor_line,
    "06-moving-tiles-to-the-wall": ep_moving_tiles_to_the_wall,
    "07-scoring-a-wall-tile": ep_scoring_a_wall_tile,
    "08-the-next-round": ep_the_next_round,
    "09-end-of-the-game": ep_end_of_the_game,
    "10-grey-wall-variant": ep_grey_wall_variant,
    "11-sample-game": sample_game,
}
assert list(CLIPS) == [k for k, _ in EPISODES]


if __name__ == "__main__":
    names = sys.argv[1:] or list(CLIPS)
    for n in names:
        A.build(n, CLIPS[n](), OUT, WORK)
