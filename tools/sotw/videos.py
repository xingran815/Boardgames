"""Build the Spirits of the Wild explainer videos.

    python3 videos.py [01-what-is-this-game] ... [11-sample-game]   (default: all)

A short episode series: each teaching episode covers one idea, with big on-screen
captions, a "Remember" recap and a "Next" teaser.

Needs ffmpeg, Pillow, numpy, kokoro-onnx and the Kokoro model files in
tools/voices/ (see tools/setup_env.sh). Output: docs/spirits-of-the-wild/videos/.
"""
from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

import anim as A
import engine as E
import render as R

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "spirits-of-the-wild" / "videos"
WORK = Path(os.environ.get("SOTW_WORK", "/tmp/sotw-build"))
GAME_SEED = 1538
NAMES = ("Ana", "Ben")
PRON = ({"s": "she", "o": "her", "p": "her"}, {"s": "he", "o": "him", "p": "his"})
ANAME = {a: a.capitalize() for a in E.ANIMALS}
NUM = {0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
       7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}

# ------------------------------------------------------------------ camera
FULL = A.FULL


def clamp_cam(x, y, w):
    h = w * 9 / 16
    return (max(0, min(1920 - w, x)), max(0, min(1080 - h, y)), w)


def cam_player(p):
    return clamp_cam(380, 0 if p == 1 else 300, 1540)


def cam_section(p, animal, w=760):
    sw = (1480 - 36 - 48) / 5
    i = E.ANIMALS.index(animal)
    sx = 426 + 18 + i * (sw + 12)
    sy = (552 if p == 0 else 14) + 56
    return clamp_cam(sx + sw / 2 - w / 2, sy + 100 - w * 9 / 32, w)


CAM_CARDS = (0, 300, 1000)
CAM_CARDS_BEN = (0, 0, 1000)
CAM_MID = (0, 90, 1200)
CAM_BAG = (0, 260, 760)
CAM_ANA_CARDS = clamp_cam(0, 420, 720)        # Ana's six cards, room for a caption on top
CAM_BEN_CARDS = clamp_cam(0, 0, 720)         # Ben's six cards (caption goes at the bottom)
CAM_BOWL = clamp_cam(240, 170, 1000)
CAM_PILES = clamp_cam(1000, 170, 900)
CAM_COYOTE = clamp_cam(1240, 200, 760)
CAM_BOARDS = clamp_cam(400, 0, 1520)         # both boards; the empty middle band holds a caption

# ---------------------------------------------------------------- geometry
# Table-space boxes (x0, y0, x1, y1) of things the narration points at.
BAG_BOX = (60, 330, 360, 530)
METER_BOX = (100, 464, 320, 512)
BOWL_BOX = (430, 340, 1050, 530)
PILES_BOX = (1110, 296, 1606, 536)
COYOTE_BOX = (1630, 370, 1740, 490)
SEC_W = (1480 - 36 - 48) / 5


def board_y(p):
    return 552 if p == 0 else 14


def sec_box(p, a):
    x = 426 + 18 + E.ANIMALS.index(a) * (SEC_W + 12)
    y = board_y(p) + 56
    return (x, y, x + SEC_W, y + 200)


def board_box(p):
    return (426, board_y(p), 1906, board_y(p) + 270)


def cards_box(p):
    y = board_y(p) + 12
    return (14, y, 14 + 3 * R.CW + 2 * R.CG, y + 2 * R.CH + R.CG)


def card_box(p, c):
    return R.card_rect(14, board_y(p) + 12, E.CARD_ORDER.index(c))


def bonus_xy(p, a):
    x0, y0, x1, y1 = sec_box(p, a)
    return (x1 - 34, y0 + 30)


def arrow(xy, label, side="down"):
    return (xy[0], xy[1], label, side)


def mid_of(box, side="top"):
    x0, y0, x1, y1 = box
    return {"top": ((x0 + x1) / 2, y0), "bottom": ((x0 + x1) / 2, y1),
            "left": (x0, (y0 + y1) / 2), "right": (x1, (y0 + y1) / 2)}[side]


def grow(box, m=10):
    return (box[0] - m, box[1] - m, box[2] + m, box[3] + m)


# ------------------------------------------------------------------ states
class Demo:
    def __init__(self, st):
        self.st = copy.deepcopy(st)

    def snap(self):
        self.st["scores"] = [E.total_score(b) for b in self.st["boards"]]
        return copy.deepcopy(self.st)

    def draw(self, colors):
        self.st["bag"] -= len(colors)
        self.st["bowl"] += list(colors)
        self.st["clear_out"] += colors.count(E.CLEAR)
        return self

    def back(self, color):  # from the bowl back into the bag
        self.st["bowl"].remove(color)
        self.st["bag"] += 1
        self.st["clear_out"] -= color == E.CLEAR
        return self

    def take(self, p, color, where):
        self.st["bowl"].remove(color)
        E.place(self.st["boards"][p], color, where)
        return self

    def direct(self, p, color, where):  # from the bag straight to the board
        self.st["bag"] -= 1
        self.st["clear_out"] += color == E.CLEAR
        E.place(self.st["boards"][p], color, where)
        return self

    def card(self, p, c, up):
        self.st["cards"][p][c] = up
        return self

    def all_up(self, p):
        for c in E.CARD_ORDER:
            self.st["cards"][p][c] = True
        return self

    def coyote(self, p, a):
        self.st["coyote"] = (p, a) if p is not None else None
        return self

    def turn(self, p):
        self.st["current"] = p
        return self


def fresh(bowl, seed=2, piles=None):
    """A clean table: given bowl, empty boards, all cards face-up, Coyote at the side."""
    g = E.Game(seed=seed)
    g.setup()
    st = g.snapshot()
    st["bowl"], st["bag"], st["clear_out"] = list(bowl), 56 - len(bowl), 0
    st["cards"] = [{c: True for c in E.CARD_ORDER} for _ in (0, 1)]
    st["coyote"], st["current"] = None, 0
    if piles:
        st["piles"] = [list(x) for x in piles]
    return Demo(st)


def deltas(pre, post):
    out = {}
    for p in (0, 1):
        for a in E.ANIMALS:
            n = E.animal_score(post["boards"][p], a) - E.animal_score(pre["boards"][p], a)
            if n:
                out[(p, a)] = n
    return out


TEACH_PAUSE = 0.9   # silence after each new idea in the teaching episodes


def seg(text, post, pre=None, cam=None, bar=None, hl=None, pops=True, ticker=False,
        ban=None, hold=0.6, sfx=(), cap=None, cap_pos="top", arrows=None, focus=None,
        show=None, fade_from=None, xfade=False, say_after=False, pause=None):
    """One narrated shot of the table. Screen overlays (cap, arrows, focus, bar, ticker)
    go in 'ov' so they stay readable at any camera zoom."""
    tk = dict(names=NAMES, hl=hl or {}, ticker=False, ban=ban)
    if show is not None:
        tk["show"] = list(show)
    if pre is not None and pops:
        tk["deltas"] = deltas(pre, post)
    ov = {}
    if cap:
        ov["cap"] = cap
        if cap_pos != "top":
            ov["cap_pos"] = cap_pos
    if arrows:
        ov["arrows"] = list(arrows)
    if focus:
        ov["focus"] = [grow(b) for b in focus]
    if bar:
        ov["bar"] = bar
    if ticker:
        ov["score"] = f"{NAMES[0]} {post['scores'][0]}  ·  {NAMES[1]} {post['scores'][1]}"
    out = dict(text=text, post=post, pre=pre, tk=tk, cam=cam, hold=hold, sfx=list(sfx), ov=ov)
    if fade_from is not None:
        out["fade_from"] = {"show": list(fade_from)}
    if xfade:
        out["xfade"] = True
    if say_after:
        out["say_after"] = True
    if pause is not None:
        out["pause"] = pause
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
    ("03-your-turn", "Your turn"),
    ("04-placing-stones", "Placing stones"),
    ("05-rabbit-turtle-salmon", "Rabbit, Turtle, Salmon"),
    ("06-owl-and-beaver", "Owl and Beaver"),
    ("07-getting-cards-back", "Getting your cards back"),
    ("08-the-coyote", "The Coyote"),
    ("09-spirit-stones-and-the-end", "Spirit Stones and the end"),
    ("10-spirit-powers", "The six Spirit Powers"),
    ("11-sample-game", "Watch a whole game"),
]


def title(n, sub, text):
    name = EPISODES[n - 1][1]
    return card_seg(text, R.title_card(name, sub, kicker=f"Spirits of the Wild · Episode {n}"),
                    fade=True, pause=0.8, sfx=["card"])


def recap(n, lines, text):
    nxt = EPISODES[n][1] if n < len(EPISODES) else None
    return card_seg(text, R.recap_card(lines, nxt), fade=True, hold=1.5, pause=1.6)


ALL = list(R.PARTS)
BOARDS = ["board0", "board1"]


# ============================================================ 1 what is it
def ep_what_is_this_game():
    D = fresh(["green", "red", "green", "blue", "yellow"])
    s0 = D.snap()
    S = [title(1, "Two players · stones · points",
               "Welcome to Spirits of the Wild! This first short video shows what the game is about.")]
    S.append(T("This is a game for two players. Let's call them Ana and Ben.", s0, cam=CAM_BOARDS,
               show=BOARDS, fade_from=[], cap="A game for 2 players", cap_pos="mid"))
    S.append(T("They take turns. First, Ana plays.", s0, cam=CAM_BOARDS, show=BOARDS,
               cap="Take turns", cap_pos="mid", focus=[board_box(0)]))
    s1 = D.turn(1).snap()
    S.append(T("Then Ben plays.", s1, cam=CAM_BOARDS, show=BOARDS, cap="Take turns", cap_pos="mid",
               focus=[board_box(1)], pause=0.5))
    s2 = D.turn(0).snap()
    S.append(T("Then Ana again, and so on. Each go is called a turn.", s2, cam=CAM_BOARDS,
               show=BOARDS, cap=("A turn", "= one player's go"), cap_pos="mid", focus=[board_box(0)]))
    shown = BOARDS + ["bowl"]
    S.append(T("In the middle of the table is a bowl. It holds colorful stones.", s2, cam=CAM_BOWL,
               show=shown, fade_from=BOARDS, cap="The bowl",
               arrows=[arrow(mid_of(BOWL_BOX, "left"), "Stones", "left")]))
    S.append(T("Look at Ana's board, at the bottom. It shows five forest animals.", s2,
               cam=cam_player(0), show=shown, cap="Five animals", focus=[board_box(0)]))
    pre = D.snap()
    s3 = D.take(0, "green", ("turtle", None)).snap()
    S.append(T("On her turn, Ana takes a stone from the bowl. She gives it to one of her animals.",
               s3, pre, cam=cam_player(0), show=shown, say_after=True,
               cap=("Take a stone", "give it to an animal")))
    pre = D.snap()
    s4 = D.take(0, "green", ("turtle", None)).snap()
    x0, y0, x1, y1 = sec_box(0, "turtle")
    S.append(T("Animals give you points. Look at the number in the corner. It just went up.",
               s4, pre, cam=cam_section(0, "turtle"), show=shown, say_after=True,
               cap="Points", arrows=[arrow((x1 - 28, y1 - 8), "Points", "down")]))
    D.direct(1, "red", ("owl", None)).direct(1, "red", ("owl", None))
    s5 = D.snap()
    S.append(T("At the end of the game, each player adds up their points. "
               "The player with the most points wins. That player is the winner.",
               s5, cam=CAM_BOARDS, show=shown, cap="Most points wins!", cap_pos="mid", sfx=["win"],
               focus=[(1740, board_y(0) + 4, 1900, board_y(0) + 52),
                      (1740, board_y(1) + 4, 1900, board_y(1) + 52)]))
    S.append(T("There's a little more on the table. A bag, some cards, and a sneaky Coyote. "
               "You'll meet each of them in the next videos.", s5, cam=FULL, show=ALL,
               fade_from=shown, cap="More to meet, one at a time",
               arrows=[arrow(mid_of(BAG_BOX, "top"), "Bag", "up"),
                       arrow(mid_of(cards_box(0), "bottom"), "Cards", "down"),
                       arrow(mid_of(COYOTE_BOX, "bottom"), "Coyote", "down")]))
    S.append(recap(1, ["Two players take turns.", "Give stones to your animals to score points.",
                       "Most points at the end wins."],
                   "Remember. Two players take turns. You give stones to your animals to score points. "
                   "And the most points at the end wins. Next up: getting the game ready."))
    return S


# ============================================================ 2 getting ready
def ep_getting_ready():
    D = fresh([])
    s0 = D.snap()
    S = [title(2, "Setting up the table, step by step",
               "Let's set up the game together, one step at a time.")]
    S.append(T("First, the bag. Put all fifty six stones inside it.", s0, cam=CAM_BAG, show=["bag"],
               fade_from=[], cap="1. All stones in the bag",
               arrows=[arrow(mid_of(BAG_BOX, "right"), "Bag", "right")]))
    S.append(card_seg("Most stones have a color. There are six colors: green, yellow, blue, purple, "
                      "white and red.", R.stones_card(False), fade=True, pause=TEACH_PAUSE))
    S.append(card_seg("A few stones are special and shiny. They are called Spirit Stones. "
                      "A Spirit Stone is not a color. You'll learn what it does later.",
                      R.stones_card(True), fade=R.stones_card(False), pause=TEACH_PAUSE))
    shown = ["bag", "bowl"]
    pre = D.snap()
    s1 = D.draw(["red", "white", "blue"]).snap()
    S.append(T("Now reach into the bag without looking, and pull out stones. That's called drawing. "
               "Put them in the bowl.",
               s1, pre, cam=CAM_MID, show=shown, fade_from=["bag"], say_after=True,
               cap="2. Draw stones into the bowl"))
    pre = D.snap()
    s2 = D.draw([E.CLEAR]).snap()
    S.append(T("Oops, a Spirit Stone! At the start, Spirit Stones go back into the bag.", s2, pre,
               cam=CAM_MID, show=shown, say_after=True, cap="Spirit Stone? Put it back",
               hl={"drawn": 1}))
    pre = D.snap()
    s3 = D.back(E.CLEAR).draw(["green"]).snap()
    S.append(T("Draw again, until the bowl has four colored stones.", s3, pre, cam=CAM_MID,
               show=shown, say_after=True, cap="2. Four stones in the bowl"))
    shown = shown + BOARDS
    S.append(T("Each player takes a board with five animals. Ana sits at the bottom. Ben sits at the top.",
               s3, cam=FULL, show=shown, fade_from=["bag", "bowl"], cap="3. One board each"))
    shown = shown + ["cards0", "cards1"]
    S.append(T("Each player also takes six action cards. An action card tells you what you can do "
               "on your turn.", s3, cam=FULL, show=shown, fade_from=shown[:-2],
               cap="4. Six action cards each", focus=[cards_box(0), cards_box(1)]))
    S.append(card_seg("Both players get the exact same six cards. Look: Ana's row and Ben's row match.",
                      R.card_rows(note="The same six cards for each player"), fade=True,
                      pause=TEACH_PAUSE, cap="Same cards for both"))
    S.append(card_seg("Two of the cards are the same, too. Each player has two Take One Stone cards.",
                      R.card_rows(hl=[E.TAKE1A, E.TAKE1B], note="Two Take One Stone cards each"),
                      fade=R.card_rows(note="The same six cards for each player"), pause=TEACH_PAUSE))
    S.append(T("Lay your cards face-up. Face-up means you can read the words.", s3,
               cam=CAM_ANA_CARDS, show=shown, cap="Face-up = you can read it",
               focus=[card_box(0, E.TAKE2)]))
    shown = shown + ["piles"]
    S.append(T("Next, the six Spirit Power cards. Mix them up, and make two piles of three, face-up.",
               s3, cam=CAM_PILES, show=shown, fade_from=shown[:-1], cap="5. Two Spirit piles"))
    S.append(T("Put the Coyote to the side. He waits there for now.", s3, cam=CAM_COYOTE, show=ALL,
               fade_from=shown, cap="6. Coyote to the side",
               arrows=[arrow(mid_of(COYOTE_BOX, "bottom"), "Coyote", "down")]))
    pre = D.snap()
    s4 = D.card(0, E.TAKE2, False).snap()
    S.append(T("Choose who goes first. Here it's Ana. She turns her Take Two Stones card face-down.",
               s4, pre, cam=CAM_ANA_CARDS, xfade=True, say_after=True, sfx=["card"],
               cap="7. First player: Take Two face-down", hl={"card": (0, E.TAKE2)}))
    S.append(T("Face-down means the words are hidden. You can't use a face-down card. "
               "This keeps the game fair for Ben, who goes second.", s4, cam=CAM_ANA_CARDS,
               cap="Face-down = can't use it", focus=[card_box(0, E.TAKE2)]))
    S.append(T("And that's it. You're ready to play!", s4, cam=FULL, cap="Ready!", sfx=["win"]))
    S.append(recap(2, ["Four colored stones go in the bowl.",
                       "Each player: a board and the same six cards, face-up.",
                       "First player turns Take Two Stones face-down."],
                   "Remember. Four colored stones go in the bowl. Each player gets a board and the "
                   "same six cards, face-up. The first player turns Take Two Stones face-down. "
                   "Next: what you do on your turn."))
    return S


# ============================================================ 3 your turn
def ep_your_turn():
    D = fresh(["red", "white", "blue", "white", "green"])
    D.card(0, E.TAKE2, False)
    s0 = D.snap()
    S = [title(3, "Pick a card · do it · turn it face-down",
               "What do you do on your turn? Just three simple steps.")]
    S.append(T("Step one. Pick one of your face-up cards.", s0, cam=CAM_ANA_CARDS,
               cap="1. Pick a card", focus=[cards_box(0)]))
    S.append(T("Step two. Do what the card says.", s0, cam=CAM_ANA_CARDS, cap="2. Do what it says",
               focus=[cards_box(0)]))
    S.append(T("Step three. Turn that card face-down. Then the other player has a turn.", s0,
               cam=CAM_ANA_CARDS, cap="3. Turn it face-down", focus=[cards_box(0)]))
    S.append(T("Let's watch Ana. She picks Take One Stone.", s0, cam=CAM_ANA_CARDS,
               cap="Take One Stone", hl={"card": (0, E.TAKE1A)}, sfx=["card"],
               focus=[card_box(0, E.TAKE1A)]))
    pre = D.snap()
    s1 = D.take(0, "red", ("rabbit", None)).snap()
    S.append(T("She takes one stone from the bowl, the red one. She puts it on her Rabbit.", s1, pre,
               cam=cam_player(0), say_after=True, cap="Take One Stone",
               hl={"card": (0, E.TAKE1A), "sections": (0, ["rabbit"])}))
    pre = D.snap()
    s2 = D.card(0, E.TAKE1A, False).snap()
    S.append(T("Then she turns the card face-down. Her turn is over. The picture on the back is for "
               "later.", s2, pre, cam=CAM_ANA_CARDS,
               xfade=True, sfx=["card"], cap="Turn it face-down", hl={"card": (0, E.TAKE1A)}))
    s3 = D.turn(1).snap()
    S.append(T("Now it's Ben's turn. He picks Take Two Stones.", s3, cam=CAM_BEN_CARDS,
               cap=("Ben's turn", "Take Two Stones"), cap_pos="bottom", hl={"card": (1, E.TAKE2)},
               sfx=["card"], focus=[card_box(1, E.TAKE2)]))
    pre = D.snap()
    s4 = D.take(1, "white", ("turtle", None)).take(1, "white", ("turtle", None)).card(1, E.TAKE2, False).snap()
    S.append(T("He takes two stones from the bowl, both white. He gives them to his Turtle. "
               "Then he turns the card face-down.", s4, pre, cam=cam_player(1), say_after=True,
               cap="Take Two Stones", cap_pos="bottom", hl={"card": (1, E.TAKE2)}))
    S.append(T("You can only pick a card that you can really do. Take Two Stones needs two stones "
               "in the bowl.", s4, cam=CAM_BOWL, cap="Only cards you can do",
               focus=[BOWL_BOX]))
    s5 = D.turn(0).snap()
    S.append(T("Ana's turn again. This time she picks Add Two Stones and Take One.", s5,
               cam=CAM_ANA_CARDS, cap="Add Two & Take One", hl={"card": (0, E.ADD2)},
               sfx=["card"], focus=[card_box(0, E.ADD2)]))
    pre = D.snap()
    s6 = D.draw(["yellow", "purple"]).snap()
    S.append(T("First, she draws two stones from the bag, without looking. They go into the bowl.",
               s6, pre, cam=CAM_MID, say_after=True, cap="Add two to the bowl", hl={"drawn": 2}))
    pre = D.snap()
    s7 = D.take(0, "yellow", ("rabbit", None)).card(0, E.ADD2, False).snap()
    S.append(T("Then she takes one, the yellow, for her Rabbit. And the card goes face-down.",
               s7, pre, cam=cam_player(0), say_after=True, cap="...and take one",
               hl={"card": (0, E.ADD2)}))
    S.append(T("Look at Ana's cards now. Three are face-down. She can't use them for a while. "
               "Episode seven shows how to get them back.", s7, cam=CAM_ANA_CARDS,
               cap="Face-down cards wait",
               focus=[card_box(0, E.TAKE1A), card_box(0, E.TAKE2), card_box(0, E.ADD2)]))
    pre = D.turn(1).snap()
    s9 = D.take(1, "green", ("salmon", None)).card(1, E.TAKE1A, False).snap()
    S.append(T("One more time, with Ben. He picks a card, does it, and turns it face-down.",
               s9, pre, cam=cam_player(1), say_after=True,
               cap=("Pick · Do · Face-down", "that's a turn"), cap_pos="bottom",
               hl={"card": (1, E.TAKE1A)}, sfx=["card"]))
    S.append(recap(3, ["Pick one face-up card.", "Do what it says.", "Turn it face-down."],
                   "Remember. On your turn, pick one face-up card. Do what it says. "
                   "Then turn it face-down. Next: where your stones can go."))
    return S


# ============================================================ 4 placing stones
def ep_placing_stones():
    D = fresh(["red", "blue", "green", "yellow"])
    s0 = D.snap()
    tx0, ty0, tx1, ty1 = sec_box(0, "turtle")
    S = [title(4, "Where can a stone go?",
               "Every stone you take goes on your board. But where? Let's find out.")]
    S.append(T("Look at Ana's board. It has five parts, one for each animal. Each part is called "
               "a section.", s0, cam=cam_player(0), cap=("Section", "= one animal's part"),
               focus=[sec_box(0, a) for a in E.ANIMALS]))
    S.append(T("Let's zoom in on the Turtle's section. The empty circles are where stones go.", s0,
               cam=cam_section(0, "turtle"), cap="Stones go in the circles",
               focus=[(tx0 + 8, ty0 + 72, tx0 + 262, ty0 + 124)]))
    S.append(T("Each animal is picky. It only takes stones that match its rule. The rule is written "
               "under its name.", s0, cam=cam_section(0, "turtle"), cap="Each animal has a rule",
               focus=[(tx0 + 6, ty0 + 36, tx0 + 160, ty0 + 66)]))
    S.append(T("The Turtle's rule is: all one color.", s0, cam=cam_section(0, "turtle"),
               cap="Turtle: all one color", pause=0.6))
    pre = D.snap()
    s1 = D.take(0, "red", ("turtle", None)).snap()
    S.append(T("Ana gives it a red stone. That fits!", s1, pre, cam=cam_player(0), say_after=True,
               cap="Red fits", hl={"sections": (0, ["turtle"])}))
    S.append(T("Next, she takes the blue stone. Blue is not red. So blue can't go on this Turtle.",
               s1, cam=cam_player(0), cap="Blue doesn't fit the Turtle",
               hl={"sections": (0, ["turtle"])}, focus=[sec_box(0, "turtle"), BOWL_BOX]))
    pre = D.snap()
    s2 = D.take(0, "blue", ("salmon", None)).snap()
    S.append(T("But blue fits the Salmon. The Salmon wants all different colors.", s2, pre,
               cam=cam_player(0), say_after=True, cap="Blue fits the Salmon",
               hl={"sections": (0, ["salmon"])}))
    S.append(T("What if a stone fits nowhere on your board? Then it goes back into the bowl.", s2,
               cam=CAM_BOWL, cap="Fits nowhere? Back to the bowl", focus=[BOWL_BOX]))
    sx0, sy0, sx1, sy1 = sec_box(0, "salmon")
    S.append(T("Now, points. The gold numbers at the bottom show what the animal can score.", s2,
               cam=cam_section(0, "salmon"), cap="What it can score",
               arrows=[arrow((sx0 + 90, sy1 - 14), "Points list", "down")]))
    S.append(T("The big number in the corner shows its points right now.", s2,
               cam=cam_section(0, "salmon"), cap="Points right now",
               arrows=[arrow((sx1 - 26, sy1 - 10), "Now: 2", "down")]))
    S.append(T("All five animals add up to your total. It's at the top right of the board.", s2,
               cam=cam_player(0), cap="Your total",
               focus=[(1740, board_y(0) + 4, 1900, board_y(0) + 52)]))
    S.append(recap(4, ["Each animal has its own section.", "A stone must match the animal's rule.",
                       "Fits nowhere? It goes back to the bowl."],
                   "Remember. Each animal has its own section. A stone must match that animal's rule. "
                   "If it fits nowhere, it goes back to the bowl. Next: meet the first three animals."))
    return S


# ============================================================ 5 rabbit turtle salmon
def animal_steps(D, p, a, steps, cap, cam=None):
    """[(text, [(color, slot)], extra kw)] -> teaching shots that add stones one batch at a time."""
    out = []
    for text, stones, kw in steps:
        pre = D.snap()
        for c, slot in stones:
            D.direct(p, c, (a, slot))
        post = D.snap()
        kw = dict(kw)
        kw.setdefault("cap", cap)
        kw.setdefault("cam", cam or cam_section(p, a))
        kw.setdefault("hl", {"sections": (p, [a])})
        if stones:
            kw.setdefault("say_after", True)
            out.append(T(text, post, pre, **kw))
        else:
            out.append(T(text, post, **kw))
    return out


def ep_rabbit_turtle_salmon():
    D = fresh(["red", "blue", "green", "yellow"])
    S = [title(5, "Meet the animals, part 1",
               "Each animal wants different stones. Let's meet the first three: Rabbit, Turtle and Salmon.")]
    S += animal_steps(D, 0, "rabbit", [
        ("This is the Rabbit. The Rabbit wants three stones, each a different color.", [], {}),
        ("Red, then blue. No points yet.", [("red", None), ("blue", None)], {}),
        ("Then yellow. Three different colors! That's six points.", [("yellow", None)],
         {"sfx": ["chime"]}),
        ("The Rabbit only scores when all three are there.", [],
         {"cap": ("Rabbit", "full = 6 points, not full = 0")}),
    ], ("Rabbit", "3 different colors"))
    S += animal_steps(D, 0, "turtle", [
        ("Next, the Turtle. The Turtle wants stones that are all the same color.", [], {}),
        ("One green stone. One point.", [("green", None)], {}),
        ("Three green stones. Six points.", [("green", None)] * 2, {}),
        ("Five green stones. Fourteen points! More stones, more points.", [("green", None)] * 2,
         {"sfx": ["chime"]}),
    ], ("Turtle", "all one color"))
    S += animal_steps(D, 0, "salmon", [
        ("Now the Salmon. The Salmon is the opposite of the Turtle. Every stone must be a "
         "different color.", [], {}),
        ("Three different colors. Four points.", [(c, None) for c in ("purple", "white", "red")], {}),
        ("All six colors. Thirteen points!", [(c, None) for c in ("yellow", "blue", "green")],
         {"sfx": ["chime"]}),
    ], ("Salmon", "all different colors"))
    S.append(T("A tip: the last stones are worth the most. So try to fill your animals up.",
               D.snap(), cam=cam_player(0), cap="Tip: fill them up",
               focus=[sec_box(0, a) for a in ("rabbit", "turtle", "salmon")]))
    S.append(recap(5, ["Rabbit: three different colors, six points.",
                       "Turtle: all one color.", "Salmon: all different colors."],
                   "Remember. The Rabbit wants three different colors, for six points. "
                   "The Turtle wants all one color. The Salmon wants all different colors. "
                   "Next: the Owl and the Beaver."))
    return S


# ============================================================ 6 owl beaver
def ep_owl_and_beaver():
    D = fresh(["red", "blue", "green", "yellow"])
    P = NUM[E.OWL_POINTS]
    S = [title(6, "Meet the animals, part 2", "Two more animals to meet: the Owl and the Beaver.")]
    S += animal_steps(D, 0, "owl", [
        ("This is the Owl. The Owl loves pairs. A pair is two stones of the same color.", [], {}),
        ("One white stone. Not a pair yet, so no points.", [("white", None)], {}),
        (f"A second white stone. That's a pair! {P.capitalize()} points.", [("white", None)],
         {"sfx": ["chime"]}),
        (f"Another pair, red this time. {P.capitalize()} more points.", [("red", None)] * 2, {}),
    ], ("Owl", f"pairs, {E.OWL_POINTS} points each"))
    S += animal_steps(D, 0, "beaver", [
        ("This is the Beaver. The Beaver wants two groups.", [], {}),
        ("On top: three stones of one color. Three blues make five points.",
         [("blue", "triple")] * 3, {"cap": ("Beaver", "3 the same: 5 points")}),
        ("Below: two stones of one color. Two yellows make two points.",
         [("yellow", "pair")] * 2, {"cap": ("Beaver", "2 the same: 2 points"), "pops": False}),
        ("Both groups done? Bonus! Seven more points. That's fourteen in all.", [],
         {"cap": ("Beaver bonus!", "5 + 2 + 7 = 14"), "sfx": ["chime"]}),
    ], ("Beaver", "3 the same + 2 the same"))
    D.direct(0, "red", ("rabbit", None)).direct(0, "blue", ("rabbit", None)).direct(0, "yellow", ("rabbit", None))
    for c in ("green",) * 3:
        D.direct(0, c, ("turtle", None))
    for c in ("purple", "white", "red", "green"):
        D.direct(0, c, ("salmon", None))
    S.append(T("Here are all five animals together. Each one has its own rule.", D.snap(),
               cam=cam_player(0), cap="All five animals", focus=[board_box(0)]))
    S.append(recap(6, [f"Owl: pairs of the same color, {E.OWL_POINTS} points each.",
                       "Beaver: three the same, plus two the same.",
                       "Both Beaver groups: 7 bonus points."],
                   f"Remember. The Owl wants pairs of the same color, {P} points each. "
                   "The Beaver wants three the same, plus two the same. Finish both, and get a "
                   "bonus. Next: how to get your cards back."))
    return S


# ============================================================ 7 cards back
def ep_getting_cards_back():
    D = fresh(["red", "white", "green"], piles=[["wolf", "bear", "eagle"], ["deer", "ram", "bison"]])
    for c in (E.TAKE1A, E.TAKE2, E.ADD2):
        D.card(0, c, False)
    D.direct(0, "red", ("rabbit", None)).direct(0, "white", ("turtle", None))
    s0 = D.snap()
    S = [title(7, "The Spirit Power card",
               "Every turn, one of your cards goes face-down. So what happens when you run out?")]
    S.append(T("Look at Ana's cards. Three of them are face-down.", s0, cam=CAM_ANA_CARDS,
               cap="3 cards face-down",
               focus=[card_box(0, E.TAKE1A), card_box(0, E.TAKE2), card_box(0, E.ADD2)]))
    S.append(T("Her last card is called Spirit Power. She may use it only when at least three "
               "other cards are face-down.", s0, cam=CAM_ANA_CARDS,
               cap=("Spirit Power", "needs 3 cards face-down"),
               focus=[card_box(0, E.SPIRIT)]))
    S.append(T("Now she can. She picks Spirit Power.", s0, cam=CAM_ANA_CARDS, sfx=["card"],
               cap="Spirit Power", hl={"card": (0, E.SPIRIT)}))
    S.append(T("Look at the two Spirit cards in the middle. She chooses one of the two top cards.",
               s0, cam=CAM_PILES, cap="Choose one Spirit card", focus=[PILES_BOX]))
    S.append(T("She picks the Wolf. The Wolf says: add four stones to the bowl, then take one.",
               s0, cam=CAM_PILES, cap="The Wolf", hl={"mid": "wolf"}))
    pre = D.snap()
    s1 = D.draw(["blue", "purple", "white", "yellow"]).snap()
    S.append(T("Four new stones go into the bowl.", s1, pre, cam=CAM_MID, say_after=True,
               cap="Add four", hl={"mid": "bowl", "drawn": 4}, pause=0.5))
    pre = D.snap()
    s2 = D.take(0, "white", ("turtle", None)).snap()
    S.append(T("And she takes one. Another white for her Turtle.", s2, pre, cam=cam_player(0),
               say_after=True, cap="Take one"))
    pre = D.snap()
    D.st["piles"][0].append(D.st["piles"][0].pop(0))
    s3 = D.snap()
    S.append(T("The Wolf goes to the bottom of its pile. A new Spirit card is now on top.", s3, pre,
               cam=CAM_PILES, xfade=True, sfx=["card"], cap="Under its pile"))
    pre = D.snap()
    s4 = D.all_up(0).snap()
    S.append(T("And now the best part. All of Ana's cards turn face-up again! She can use them all "
               "again.", s4, pre, cam=CAM_ANA_CARDS, xfade=True, say_after=True, sfx=["card", "win"],
               cap="All cards face-up again!"))
    S.append(T("So the game has a rhythm. Use your cards, one each turn. Then use Spirit Power to "
               "get them all back.", s4, cam=FULL, cap=("The rhythm", "use your cards · get them back")))
    S.append(T("There are six different Spirit cards. Episode ten shows each one.", s4,
               cam=CAM_PILES, cap="Six Spirit cards", focus=[PILES_BOX]))
    S.append(recap(7, ["Spirit Power needs three face-down cards.",
                       "Choose one of the two top Spirit cards, and do it.",
                       "Then all your cards turn face-up."],
                   "Remember. Spirit Power needs three face-down cards. Choose one of the two top "
                   "Spirit cards, and do what it says. Then all your cards turn face-up. "
                   "Next: the Coyote."))
    return S


# ============================================================ 8 coyote
def ep_the_coyote():
    D = fresh(["red", "green"])
    for c in ("blue",) * 3:
        D.direct(1, c, ("turtle", None))
    D.direct(0, "red", ("rabbit", None))
    s0 = D.snap()
    S = [title(8, "The trickster", "Meet the Coyote. He's a troublemaker, and he gets in the way.")]
    S.append(T("Here he is, waiting at the side of the table.", s0, cam=CAM_COYOTE,
               cap="The Coyote", arrows=[arrow(mid_of(COYOTE_BOX, "bottom"), "Coyote", "down")]))
    S.append(T("You can put the Coyote on one of your opponent's animals. Your opponent is the "
               "other player.", s0, cam=FULL, cap=("Opponent", "= the other player"), cap_pos="mid",
               focus=[board_box(1)]))
    S.append(T("Way one: the card Add Three Stones and Move Coyote. Ana picks it.", s0,
               cam=CAM_ANA_CARDS, cap="Way 1: Add Three & Move Coyote", sfx=["card"],
               hl={"card": (0, E.ADD3)}, focus=[card_box(0, E.ADD3)]))
    pre = D.snap()
    s1 = D.draw(["yellow", "white", "purple"]).snap()
    S.append(T("She draws three stones into the bowl. This card doesn't let her take one.", s1, pre,
               cam=CAM_MID, say_after=True, cap="Add three", hl={"drawn": 3}))
    pre = D.snap()
    s2 = D.coyote(1, "turtle").card(0, E.ADD3, False).snap()
    S.append(T("Then she moves the Coyote onto Ben's Turtle.", s2, pre, cam=FULL, say_after=True,
               cap="Move the Coyote", hl={"sections": (1, ["turtle"])}))
    S.append(T("Now Ben's Turtle is blocked. Blocked means Ben can't add any stones to it.", s2,
               cam=cam_section(1, "turtle"), cap=("Blocked", "no new stones"), cap_pos="bottom"))
    S.append(T("The stones already there stay. They still count for points.", s2,
               cam=cam_section(1, "turtle"), cap="Old stones still count", cap_pos="bottom"))
    S.append(T("Way two is a secret on the back of the Take One Stone cards. Look at Ben's cards.",
               s2, cam=CAM_BEN_CARDS, cap="Way 2: the card backs", cap_pos="bottom",
               focus=[card_box(1, E.TAKE1A), card_box(1, E.TAKE1B)]))
    pre = D.snap()
    s3 = D.turn(1).card(1, E.TAKE1A, False).snap()
    S.append(T("Ben plays one Take One Stone card, and turns it face-down. On its back is half a "
               "Coyote!", s3, pre, cam=CAM_BEN_CARDS, xfade=True, say_after=True, sfx=["card"],
               cap="Half a Coyote", cap_pos="bottom", hl={"card": (1, E.TAKE1A)}))
    pre = D.snap()
    s4 = D.card(1, E.TAKE1B, False).snap()
    S.append(T("On a later turn, he plays the other one. Both are face-down. The two halves make a "
               "whole Coyote!", s4, pre, cam=CAM_BEN_CARDS, xfade=True, say_after=True,
               sfx=["card", "yip"], cap="Both face-down = whole Coyote", cap_pos="bottom",
               hl={"card": (1, E.TAKE1B)}))
    pre = D.snap()
    s5 = D.coyote(0, "rabbit").snap()
    S.append(T("So Ben may move the Coyote. He puts it on Ana's Rabbit.", s5, pre, cam=FULL,
               say_after=True, cap="Move the Coyote", hl={"sections": (0, ["rabbit"])}))
    S.append(T("The Coyote is only ever on one animal. Ben's Turtle is free again.", s5, cam=FULL,
               cap="Only one animal at a time", focus=[sec_box(1, "turtle"), sec_box(0, "rabbit")]))
    S.append(recap(8, ["The Coyote blocks one animal: no new stones.",
                       "Way 1: Add Three Stones & Move Coyote.",
                       "Way 2: both Take One Stone cards face-down."],
                   "Remember. The Coyote blocks one animal: no new stones there. Move him with Add "
                   "Three Stones and Move Coyote. Or move him when both your Take One Stone cards are "
                   "face-down. Next: Spirit Stones, and how the game ends."))
    return S


# ============================================================ 9 spirit stones + end
def ep_spirit_stones_and_end():
    D = fresh(["red", E.CLEAR, "green"])
    D.st["clear_out"] = 1
    for _ in range(4):
        D.direct(0, "red", ("turtle", None))
    s0 = D.snap()
    bx, by = bonus_xy(0, "turtle")
    S = [title(9, "Double points, and the end of the game",
               "Remember the special, shiny stones? They're called Spirit Stones. "
               "They're powerful, and they also end the game.")]
    S.append(T("Here is a Spirit Stone, in the bowl.", s0, cam=CAM_BOWL, cap="Spirit Stone",
               arrows=[arrow((740, 412), "Spirit Stone", "up")]))
    S.append(T("A Spirit Stone can't go in the normal circles. It only goes on the space marked "
               "times two, next to the animal's name.", s0, cam=cam_section(0, "turtle"),
               cap="Only on the ×2 space", arrows=[arrow((bx, by + 22), "×2 space", "down")]))
    S.append(T("Ana's Turtle has four red stones. That's nine points.", s0, cam=cam_section(0, "turtle"),
               cap="Turtle: 9 points", hl={"sections": (0, ["turtle"])}, pause=0.6))
    pre = D.snap()
    s1 = D.take(0, E.CLEAR, ("turtle", "bonus")).snap()
    S.append(T("She adds a Spirit Stone. Times two means double. Nine becomes eighteen!", s1, pre,
               cam=cam_section(0, "turtle"), say_after=True, cap="×2 = double points!",
               hl={"sections": (0, ["turtle"])}))
    S.append(T("But now this animal is closed. Closed means no more stones can go on it.", s1,
               cam=cam_section(0, "turtle"), cap=("Closed", "no more stones here"),
               hl={"sections": (0, ["turtle"])}))
    S.append(T("So wait until the animal is full, or nearly full.", s1, cam=cam_section(0, "turtle"),
               cap="Tip: fill it first"))
    S.append(T("Spirit Stones also tell you when the game ends. Look at the bag. These five circles "
               "count the Spirit Stones that are out of the bag.", s1, cam=CAM_BAG,
               cap="Spirit Stones out of the bag", hl={"mid": "meter"},
               arrows=[arrow(mid_of(METER_BOX, "bottom"), "Counter", "down")]))
    S.append(T("Out of the bag means in the bowl, or on a board.", s1, cam=CAM_MID,
               cap="Out = in the bowl or on a board", hl={"mid": "meter"}))
    D.st["clear_out"] = 4
    pre = D.snap()
    s2 = D.draw([E.CLEAR, "blue"]).snap()
    S.append(T("When the fifth one comes out, all five circles are full. At the end of that turn, "
               "the game is over.", s2, pre, cam=CAM_BAG, say_after=True,
               cap="5 Spirit Stones out = game over", hl={"mid": "meter"}))
    for c in ("yellow", "blue", "purple"):
        D.direct(1, c, ("salmon", None))
    D.direct(1, "white", ("owl", None)).direct(1, "white", ("owl", None))
    D.coyote(0, "rabbit")
    s3 = D.snap()
    S.append(T("Now everyone adds up their points. The player with the most points wins!", s3,
               cam=FULL, cap="Most points wins!", sfx=["win"],
               focus=[(1740, board_y(0) + 4, 1900, board_y(0) + 52),
                      (1740, board_y(1) + 4, 1900, board_y(1) + 52)]))
    rx0, ry0, rx1, ry1 = sec_box(0, "rabbit")
    S.append(T("What if both players have the same points? That's a tie. Then the player with the "
               "Coyote on their board wins.", s3, cam=FULL, cap=("A tie?", "the Coyote's board wins"),
               arrows=[arrow(((rx0 + rx1) / 2, ry0 + 60), "Coyote", "up")]))
    S.append(recap(9, ["A Spirit Stone goes on a ×2 space and doubles that animal.",
                       "Then that animal is closed.",
                       "5 Spirit Stones out of the bag: game over. Most points wins."],
                   "Remember. A Spirit Stone goes on a times two space, and doubles that animal. "
                   "Then that animal is closed. When five Spirit Stones are out of the bag, the game "
                   "ends. The most points wins. Next: the six Spirit Powers."))
    return S


SPIRIT_GRID = {
    "bear": ("Bear", ["Bowl back into the bag", "Refill with the same number", "Take 1"]),
    "wolf": ("Wolf", ["Add 4 stones to the bowl", "Take 1"]),
    "ram": ("Ram", ["Draw 2 from the bag", "straight onto your board"]),
    "eagle": ("Eagle", ["Take 1", "Then take another turn"]),
    "deer": ("Deer", ["Move 1 of your stones to the bowl", "Take 2"]),
    "bison": ("Bison", ["Add 3, take 1", "Return 1 from bowl to bag"]),
}

SPIRIT_SAY = {
    "bear": "The Bear. Put every stone from the bowl back in the bag. Then draw the same number of "
            "new ones. Then take one. Use it when the bowl has nothing you need.",
    "wolf": "The Wolf. Draw four stones into the bowl. Then take one. Lots of choice!",
    "ram": "The Ram. Draw two stones from the bag, without looking. Put them straight on your "
           "board, if they fit. A stone that doesn't fit goes in the bowl. It's a surprise!",
    "eagle": "The Eagle. Take one stone. Your cards turn face-up as usual. Then you play another "
             "whole turn!",
    "deer": "The Deer. Move one of your own stones back to the bowl. Then take two. "
            "Good for fixing a mistake.",
    "bison": "The Bison. Draw three stones into the bowl, and take one. Then put one stone from the "
             "bowl back in the bag. It can even be a Spirit Stone. That makes the game last longer.",
}


def spirit_powers():
    S = [title(10, "A quick look at all six",
               "Remember Spirit Power? You choose one of the two top Spirit cards, and do what it "
               "says. Here are all six.")]
    S.append(card_seg("Here they are. Let's look at them one at a time.",
                      R.spirit_grid(SPIRIT_GRID), fade=True, pause=0.6))
    for i, k in enumerate(SPIRIT_GRID):
        x = 90 + (i % 3) * 590
        y = 60 + (i // 3) * 450
        cam = clamp_cam(x + 280 - 450, y + 210 - 253, 900)
        S.append(dict(text=SPIRIT_SAY[k], image=R.spirit_grid(SPIRIT_GRID, hl=k), cam=cam, hold=0.6,
                      pause=TEACH_PAUSE, ov={}))
    S.append(dict(text="Always do the steps in the order they are written. Then put the Spirit "
                       "card at the bottom of its pile.", image=R.spirit_grid(SPIRIT_GRID), hold=1.0,
                  pause=TEACH_PAUSE, ov={"cap": "Steps in order, then under the pile", "cap_pos": "bottom"}))
    S.append(recap(10, ["Choose one of the two top Spirit cards.", "Do its steps in order.",
                        "Card under its pile; your cards turn face-up."],
                   "Remember. Choose one of the two top Spirit cards. Do its steps in order. "
                   "Then the card goes under its pile, and your cards turn face-up. "
                   "Next: watch a whole game."))
    return S


# ============================================================ sample game
def stone_word(c):
    return "a Spirit Stone" if c == E.CLEAR else f"a {c} stone"


def list_words(xs):
    xs = list(xs)
    if not xs:
        return "nothing"
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def colors_words(cs):
    from collections import Counter
    parts = []
    for c, n in Counter(cs).items():
        if c == E.CLEAR:
            parts.append("a Spirit Stone" if n == 1 else f"{NUM[n]} Spirit Stones")
        else:
            parts.append(f"{'a' if n == 1 else NUM[n]} {c}")
    return list_words(parts)


def where_word(w):
    a, slot = w
    if slot == "bonus":
        return f"on the {ANAME[a]}'s times-two space"
    return f"to the {ANAME[a]}"


def place_words(res):
    out = []
    for c, w in res:
        out.append(f"{stone_word(c)}, which fits nowhere" if w is None else f"{stone_word(c)} {where_word(w)}")
    return list_words(out)


def placed_words(res, pr):
    """'She gives a red stone to the Rabbit.' plus a sentence for each stone that fits nowhere."""
    placed = [(c, w) for c, w in res if w is not None]
    out = []
    for c, w in placed:  # one stone per sentence
        verb = "puts" if w[1] == "bonus" else "gives"
        out.append(f"{pr['s'].capitalize()} {verb} {place_words([(c, w)])}.")
    for c, w in res:
        if w is None:
            out.append(f"{stone_word(c).capitalize()} fits nowhere, so it goes back to the bowl.")
    if any(w and w[1] == "bonus" for c, w in res):
        out.append("Double points! That animal is now closed.")
    return " ".join(out)


def bonus_cap(res):
    return "Spirit Stone: ×2!" if any(w and w[1] == "bonus" for c, w in res) else None


def turn_label(n, ev):
    who = NAMES[ev["player"]]
    if ev["action"] == E.SPIRIT:
        return f"Turn {n} · {who} · Spirit Power: {ev['spirit'].capitalize()}"
    return f"Turn {n} · {who} · {E.CARD_NAMES[ev['action']]}"


def featured_turns(turns):
    feat, seen = set(), set()
    lead_prev = 0
    for n, ev in enumerate(turns, 1):
        kinds = [s[0] for s in ev["steps"]]
        why = []
        if n == 1:
            why.append("start")
        if ev.get("spirit") and ev["spirit"] not in seen:
            seen.add(ev["spirit"])
            why.append("spirit")
        for k in ("coyote", "coyote_half"):
            if k in kinds and k not in seen:
                seen.add(k)
                why.append(k)
        bonus = any(w and w[1] == "bonus" for s in ev["steps"] if s[0] in ("take", "ram") for c, w in s[1])
        if bonus and "bonus" not in seen:
            seen.add("bonus")
            why.append("bonus")
        sc = ev["post"]["scores"]
        lead = (sc[0] > sc[1]) - (sc[0] < sc[1])
        if lead and lead_prev and lead != lead_prev and n > 6:
            why.append("lead")
        if lead:
            lead_prev = lead
        if n >= len(turns) - 1:
            why.append("end")
        if why:
            feat.add(n)
    return feat


SKIP_LINES = ["Let's skip ahead a few turns.", "A few quick turns.", "Fast forward.",
              "Skipping ahead.", "Quick turns now."]


def sample_game():
    g = E.Game(seed=GAME_SEED, names=NAMES)
    log = g.play()
    turns = [e for e in log if e["type"] == "turn"]
    feat = featured_turns(turns)
    S = [title(11, "Ana vs Ben · the highlights",
               "Now let's watch Ana and Ben play a whole game, using everything you learned. "
               "We'll slow down for the big moments, and skip quickly through the rest.")]
    setup = log[0]["state"]
    S.append(seg(f"Ana is at the bottom. Ben is at the top. The bowl starts with "
                 f"{colors_words(setup['bowl'])}. Ana goes first, so her Take Two Stones card "
                 f"starts face-down.",
                 setup, cam=FULL, ticker=True, bar="Setup", hl={"card": (0, E.TAKE2), "mid": "bowl"},
                 pause=0.7))
    prev_out, skip_i, in_skip = 0, 0, False
    for n, ev in enumerate(turns, 1):
        p, act = ev["player"], ev["action"]
        who, pr = NAMES[p], PRON[p]
        label = turn_label(n, ev)
        if n not in feat:
            text = ""
            if not in_skip:
                text = SKIP_LINES[skip_i % len(SKIP_LINES)]
                skip_i += 1
            in_skip = True
            S.append(seg(text, ev["post"], ev["pre"], cam=FULL, ticker=True, bar=label,
                         hl={"card": (p, act)}, hold=0.5, sfx=["card"]))
            continue
        in_skip = False
        if act == E.SPIRIT:
            intro = (f"Turn {n}. {who} plays Spirit Power. {pr['s'].capitalize()} picks the "
                     f"{ev['spirit'].capitalize()}.")
            S.append(seg(intro, ev["pre"], cam=FULL, ticker=True, bar=label,
                         hl={"card": (p, act), "mid": ev["spirit"]}, sfx=["card"],
                         cap=("Spirit Power", f"the {ev['spirit'].capitalize()}")))
        else:
            S.append(seg(f"Turn {n}. {who} plays {E.CARD_NAMES[act].replace('&', 'and')}.", ev["pre"],
                         cam=FULL, ticker=True, bar=label, hl={"card": (p, act)}, sfx=["card"]))
        prev = ev["pre"]
        for step, snap in zip(ev["steps"], ev["snaps"]):
            kind = step[0]
            hl, cam, cap = {}, FULL, None
            if kind == "draw":
                if not step[1]:
                    continue
                text = f"Into the bowl: {colors_words(step[1])}."
                hl, cam = {"mid": "bowl"}, CAM_MID
            elif kind == "take":
                if not step[1]:
                    continue
                text, cap = placed_words(step[1], pr), bonus_cap(step[1])
                secs = [w[0] for c, w in step[1] if w]
                hl, cam = {"sections": (p, secs)}, cam_player(p)
            elif kind == "ram":
                text = (f"The Ram draws {colors_words([c for c, _ in step[1]])} straight from the bag. "
                        + placed_words(step[1], pr))
                cap = bonus_cap(step[1])
                hl, cam = {"sections": (p, [w[0] for c, w in step[1] if w])}, cam_player(p)
            elif kind in ("coyote", "coyote_half"):
                opp, tgt, was = NAMES[step[1]], step[2], step[3]
                if kind == "coyote_half":
                    text = (f"Both of {pr['p']} Take One Stone cards are face-down. That makes a whole "
                            f"Coyote! {who} moves it onto {opp}'s {ANAME[tgt]}.")
                else:
                    text = f"{who} moves the Coyote onto {opp}'s {ANAME[tgt]}."
                if was and was[0] == p:
                    text += f" {pr['p'].capitalize()} own {ANAME[was[1]]} is free again."
                hl, cap = {"sections": (step[1], [tgt])}, ("Coyote!", f"{opp}'s {ANAME[tgt]} is blocked")
            elif kind == "bear_return":
                text = "The Bear sends the whole bowl back into the bag."
                hl, cam = {"mid": "bowl"}, CAM_MID
            elif kind == "deer_remove":
                text = f"The Deer moves {stone_word(step[1])} from {pr['p']} {ANAME[step[2]]} back to the bowl."
                hl, cam = {"sections": (p, [step[2]]), "mid": "bowl"}, CAM_MID
            elif kind == "bison_return":
                text = f"Then the Bison sends {stone_word(step[1])} back into the bag."
                if step[1] == E.CLEAR:
                    text += " That makes the game last longer."
                hl, cam = {"mid": "bowl"}, CAM_MID
            elif kind == "recover":
                text = ""
                hl = {"card": (p, E.SPIRIT)}
            elif kind == "extra":
                text = f"The Eagle gives {who} another turn!"
            else:
                continue
            S.append(seg(text, snap, prev, cam=cam, ticker=True, bar=label, hl=hl, cap=cap,
                         hold=0.6 if text else 0.4))
            prev = snap
        post = ev["post"]
        extra = []
        if post["clear_out"] != prev_out and 3 <= post["clear_out"] < 5:  # 5 = the game-over line
            extra.append(f"That's {NUM[post['clear_out']]} Spirit Stones out of the bag.")
            if post["clear_out"] == 4:
                extra.append("One more, and the game ends.")
        prev_out = post["clear_out"]
        if extra:
            S.append(seg(" ".join(extra), post, cam=CAM_BAG, ticker=True, bar=label, hl={"mid": "meter"},
                         cap=f"{post['clear_out']} of 5 Spirit Stones out"))
    end = log[-1]["state"]
    sc = end["scores"]
    co = end["clear_out"]
    S.append(seg(f"{NUM[co].capitalize()} Spirit Stones are out at the end of the turn. Game over!",
                 end, cam=CAM_BAG, ticker=True, bar="Game over", hl={"mid": "meter"}, cap="Game over!"))
    for p in (0, 1):
        b = end["boards"][p]
        parts = [f"{ANAME[a]} {E.animal_score(b, a)}" for a in E.ANIMALS if E.animal_score(b, a)]
        S.append(seg(f"{NAMES[p]}: {list_words(parts)}. {sc[p]} points.", end, cam=cam_player(p),
                     ticker=True, bar=f"{NAMES[p]}: {sc[p]} points",
                     hl={"sections": (p, list(E.ANIMALS))}))
    if sc[0] == sc[1]:
        cp = end["coyote"][0] if end["coyote"] else None
        w = cp
        say = (f"A tie! The Coyote is on {NAMES[cp]}'s board, so {NAMES[cp]} wins."
               if cp is not None else "A tie, and nobody has the Coyote. Share the win!")
    else:
        w = 0 if sc[0] > sc[1] else 1
        say = f"{NAMES[w]} wins, {max(sc)} to {min(sc)}! Thanks for watching."
    ban = (f"{NAMES[w]} wins!" if w is not None else "Tie!", f"{max(sc)} – {min(sc)}")
    S.append(seg(say, end, cam=FULL, ticker=True, bar="Final score", ban=ban, hold=2.0, sfx=["win"]))
    return S


CLIPS = {
    "01-what-is-this-game": ep_what_is_this_game,
    "02-getting-ready": ep_getting_ready,
    "03-your-turn": ep_your_turn,
    "04-placing-stones": ep_placing_stones,
    "05-rabbit-turtle-salmon": ep_rabbit_turtle_salmon,
    "06-owl-and-beaver": ep_owl_and_beaver,
    "07-getting-cards-back": ep_getting_cards_back,
    "08-the-coyote": ep_the_coyote,
    "09-spirit-stones-and-the-end": ep_spirit_stones_and_end,
    "10-spirit-powers": spirit_powers,
    "11-sample-game": sample_game,
}
assert list(CLIPS) == [k for k, _ in EPISODES]


if __name__ == "__main__":
    names = sys.argv[1:] or list(CLIPS)
    for n in names:
        A.build(n, CLIPS[n](), OUT, WORK)
