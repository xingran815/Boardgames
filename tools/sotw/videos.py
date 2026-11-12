"""Build the Spirits of the Wild explainer videos.

    python3 videos.py [learn-to-play] [sample-game] [spirit-powers]   (default: all)

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


def deltas(pre, post):
    out = {}
    for p in (0, 1):
        for a in E.ANIMALS:
            n = E.animal_score(post["boards"][p], a) - E.animal_score(pre["boards"][p], a)
            if n:
                out[(p, a)] = n
    return out


def seg(text, post, pre=None, cam=None, bar=None, hl=None, pops=True, ticker=False,
        ban=None, hold=0.6, sfx=()):
    tk = dict(names=NAMES, hl=hl or {}, bar=bar, ticker=ticker, ban=ban)
    if pre is not None and pops:
        tk["deltas"] = deltas(pre, post)
    return dict(text=text, post=post, pre=pre, tk=tk, cam=cam, hold=hold, sfx=list(sfx))


def card_seg(text, image, hold=0.8, sfx=()):
    return dict(text=text, image=image, hold=hold, sfx=list(sfx))


# ============================================================ learn to play
def learn_to_play():
    S = []
    S.append(card_seg("Spirits of the Wild is a quick game for two players. Collect colorful "
                      "stones, give them to five forest animals, and score the most points. "
                      "Here's everything you need, in about four minutes.",
                      R.title_card("Spirits of the Wild", "Learn to play in 4 minutes",
                                   kicker="How to play")))
    g = E.Game(seed=2)
    g.setup()
    base = g.snapshot()
    base["bowl"], base["bag"], base["clear_out"] = [], 56, 0
    base["cards"][0][E.TAKE2] = True
    base["current"] = 0
    D = Demo(base)
    s0 = D.snap()
    s1 = D.draw(["red", "white", "white", "blue"]).snap()
    S.append(seg("To set up, put all fifty six stones in the bag, and draw four into the bowl. "
                 "If you draw a clear Spirit Stone, put it back.",
                 s1, s0, cam=CAM_MID, bar="Setup: four stones into the bowl", hl={"mid": "bowl"}))
    s2 = D.card(0, E.TAKE2, False).snap()
    S.append(seg("Each player gets a board with five animals, and six action cards. Shuffle "
                 "the Spirit cards into two piles, and the first player turns their Take Two "
                 "Stones card face down.", s2, cam=FULL, bar="Setup: boards, cards, Spirit piles",
                 hl={"card": (0, E.TAKE2)}, sfx=["card"]))

    # ---- the turn
    S.append(seg("On your turn, play one face-up action card, then turn it face down. "
                 "Let's follow Ana.", s2, cam=CAM_CARDS, bar="Your turn: play one card, flip it down",
                 hl={"card": (0, E.TAKE1A)}))
    pre = D.snap()
    s = D.take(0, "red", ("rabbit", None)).card(0, E.TAKE1A, False).snap()
    S.append(seg("Take One Stone. She takes the red stone from the bowl, and gives it to her Rabbit.",
                 s, pre, cam=cam_player(0), bar="Take One Stone", hl={"card": (0, E.TAKE1A)},
                 sfx=["card"]))
    pre = D.snap()
    D.st["current"] = 1
    D.st["current"] = 0
    D.card(0, E.TAKE2, True)
    pre = D.snap()
    s = D.take(0, "white", ("turtle", None)).take(0, "white", ("turtle", None)).card(0, E.TAKE2, False).snap()
    S.append(seg("Take Two Stones takes two at once. Two whites for her Turtle: three points.",
                 s, pre, cam=cam_player(0), bar="Take Two Stones", hl={"card": (0, E.TAKE2)},
                 sfx=["card"]))
    pre = D.snap()
    s = D.draw(["green", "yellow"]).snap()
    S.append(seg("Add Two Stones and Take One. First, two new stones go from the bag into the bowl.",
                 s, pre, cam=CAM_MID, bar="Add Two Stones & Take One", hl={"card": (0, E.ADD2)},
                 sfx=["card"]))
    pre = D.snap()
    s = D.take(0, "yellow", ("rabbit", None)).card(0, E.ADD2, False).snap()
    S.append(seg("Then she takes one. Yellow, for the Rabbit.", s, pre, cam=cam_player(0),
                 bar="Add Two Stones & Take One"))
    pre = D.snap()
    s = D.draw(["purple", "clear", "red"]).snap()
    S.append(seg("Add Three Stones and Move Coyote. Three stones go into the bowl, but she takes none.",
                 s, pre, cam=CAM_MID, bar="Add Three Stones & Move Coyote", hl={"card": (0, E.ADD3)},
                 sfx=["card"]))
    pre = D.snap()
    s = D.coyote(1, "turtle").card(0, E.ADD3, False).snap()
    S.append(seg("Instead, she sends the Coyote to one of Ben's animals. While it sits there, "
                 "Ben can't add stones to his Turtle.", s, pre, cam=FULL,
                 bar="The Coyote blocks one animal", hl={"sections": (1, ["turtle"])}))
    S.append(seg("Four of Ana's cards are now face down. Once at least three are, she may play "
                 "her last card: Spirit Power.", s, cam=CAM_CARDS, bar="Spirit Power: needs 3 cards face down",
                 hl={"card": (0, E.SPIRIT)}))
    top = [p[0] for p in s["piles"]]
    pick = "wolf" if "wolf" in top else top[0]
    S.append(seg(f"She chooses one of the two Spirit cards on top. The {pick.capitalize()}.", s,
                 cam=(900, 180, 1000), bar="Choose one of the two Spirit cards", hl={"mid": pick}))
    pre = D.snap()
    if pick == "wolf":
        s = D.draw(["blue", "green", "white", "purple"]).snap()
        S.append(seg("The Wolf adds four stones to the bowl...", s, pre, cam=CAM_MID,
                     bar="Wolf: add four, take one", hl={"mid": "bowl"}))
        pre = D.snap()
        s = D.take(0, "blue", ("salmon", None)).snap()
        S.append(seg("...and she takes one.", s, pre, cam=cam_player(0), bar="Wolf: add four, take one"))
    else:
        s = D.take(0, "blue", ("salmon", None)).snap()
        S.append(seg("She takes a stone.", s, pre, cam=cam_player(0)))
    pre = D.snap()
    i = [p[0] for p in D.st["piles"]].index(pick)
    D.st["piles"][i].append(D.st["piles"][i].pop(0))
    s = D.all_up(0).snap()
    S.append(seg("Then the Spirit card goes under its pile, and all her action cards flip face up "
                 "again. That's the rhythm of the game: spend your cards, then recover.",
                 s, pre, cam=FULL, bar="Recover: all cards face up again", hl={"card": (0, E.SPIRIT)},
                 sfx=["card"]))

    # ---- the animals
    g2 = E.Game(seed=5)
    g2.setup()
    st = g2.snapshot()
    st["current"] = 0
    D2 = Demo(st)
    animals = [
        ("rabbit", [("red", None), ("blue", None), ("yellow", None)],
         "The Rabbit wants three different colors. A full set is worth six points. "
         "Anything less scores nothing.", "Rabbit: 3 different colors = 6"),
        ("turtle", [("green", None)] * 5,
         "The Turtle wants one color only. More stones, more points: up to fourteen for five.",
         "Turtle: one color, 1 · 3 · 6 · 9 · 14"),
        ("salmon", [(c, None) for c in ("green", "yellow", "blue", "purple", "white", "red")],
         "The Salmon is the opposite: every stone a different color. All six colors earn thirteen.",
         "Salmon: all different, up to 13"),
        ("owl", [("white", None), ("white", None), ("red", None), ("red", None)],
         f"The Owl loves pairs. Each pair of the same color is worth {NUM[E.OWL_POINTS]}.",
         f"Owl: same-color pairs, {E.OWL_POINTS} each"),
        ("beaver", [("blue", "triple")] * 3 + [("yellow", "pair")] * 2,
         "The Beaver wants three of a kind and a pair. Five, plus two, plus a seven point bonus "
         "for finishing both. Fourteen in total.", "Beaver: 3 same + 2 same = 5 + 2 + 7"),
    ]
    S.append(seg("Now, the five animals. Each one wants a different pattern of colors.",
                 D2.snap(), cam=cam_player(0), bar="The five animals"))
    for a, stones, text, bar in animals:
        pre = D2.snap()
        for c, slot in stones:
            D2.direct(0, c, (a, slot))
        s = D2.snap()
        S.append(seg(text, s, pre, cam=cam_section(0, a), bar=bar, hl={"sections": (0, [a])}))
    S.append(seg("A stone must fit the animal you give it to. If it fits nowhere on your board, "
                 "it goes back to the bowl.", D2.snap(), cam=cam_player(0), bar="No fit? Back to the bowl"))
    # spirit stone doubling (on a fresh Turtle with four red)
    D3 = Demo(st)
    for _ in range(4):
        D3.direct(0, "red", ("turtle", None))
    pre = D3.snap()
    S.append(seg("The clear Spirit Stones are special. They only go on an animal's times-two space.",
                 pre, cam=cam_section(0, "turtle"), bar="Spirit Stones: only on the ×2 space",
                 hl={"sections": (0, ["turtle"])}))
    s = D3.direct(0, "clear", ("turtle", "bonus")).snap()
    S.append(seg("They double that animal. This Turtle jumps from nine to eighteen points. "
                 "But the animal is now closed: no more stones.", s, pre, cam=cam_section(0, "turtle"),
                 bar="×2 points, and the animal is closed", hl={"sections": (0, ["turtle"])}))

    # ---- coyote second way
    D4 = Demo(D.snap())
    D4.card(1, E.TAKE1A, False)
    pre = D4.snap()
    S.append(seg("One more Coyote trick. Each Take One Stone card has half a Coyote on its back.",
                 pre, cam=CAM_CARDS_BEN, bar="Half a Coyote on each Take One card",
                 hl={"card": (1, E.TAKE1A)}))
    s = D4.card(1, E.TAKE1B, False).snap()
    s_pre = copy.deepcopy(s)
    S.append(seg("When Ben turns both face down, the Coyote is complete...", s, pre, cam=CAM_CARDS_BEN,
                 bar="Both face down: the Coyote is complete", hl={"card": (1, E.TAKE1B)}, sfx=["card"]))
    s = D4.coyote(0, "rabbit").snap()
    S.append(seg("...and he may move it to any animal on Ana's board.", s, s_pre, cam=FULL,
                 bar="Move the Coyote to your opponent", hl={"sections": (0, ["rabbit"])}))

    # ---- spirit cards overview
    S.append(card_seg("There are six Spirit cards in all, each a different boost: more stones to "
                      "choose from, stones straight from the bag, a swap, or even an extra turn. "
                      "The reference video covers each one.",
                      R.spirit_grid(SPIRIT_GRID, bar="Six Spirit cards: see the reference video")))

    # ---- the end
    D5 = Demo(D4.snap())
    D5.st["clear_out"] = 4
    pre = D5.snap()
    s = D5.draw(["clear", "green"]).snap()
    S.append(seg("The clear stones are also the clock. When five Spirit Stones are out of the bag "
                 "at the end of a turn, the game ends right away.", s, pre, cam=CAM_BAG,
                 bar="Game end: 5 Spirit Stones out of the bag", hl={"mid": "meter"}))
    S.append(seg("Add up your animals. The most points wins. And in a tie, whoever has the Coyote "
                 "on their board wins. The trickster pays you back!", s, cam=FULL, ticker=False,
                 bar="Most points wins · tie: Coyote's board wins",
                 ban=("Most points wins", "Tie? The Coyote's board wins."), sfx=["win"]))
    S.append(card_seg("That's it: play a card, feed your animals, recover with a Spirit power, and "
                      "watch out for the Coyote. Now, let's watch a real game.",
                      R.title_card("You're ready!", "Play a card · feed your animals · recover · "
                                   "watch the Coyote")))
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
    "bear": "The Bear clears the bowl. Put all of its stones back in the bag, draw the same number "
            "of new ones, and take one. Perfect when the bowl is full of colors you don't need.",
    "wolf": "The Wolf adds four stones to the bowl, then you take one. Lots of choice.",
    "ram": "The Ram draws two stones from the bag and puts them straight on your board. You must "
           "place both if you can. Whatever doesn't fit goes into the bowl. It's a gamble!",
    "eagle": "The Eagle lets you take one stone, and after you recover your cards, you play "
             "another whole turn.",
    "deer": "The Deer moves one of your own stones back to the bowl, then you take two. "
            "Great for fixing a mistake.",
    "bison": "The Bison adds three stones and you take one. Then you return any stone from the "
             "bowl to the bag. Even a Spirit Stone, to keep the game going a little longer.",
}


def spirit_powers():
    S = [card_seg("Here are the six Spirit cards. You use one each time you play your Spirit Power "
                  "card, choosing between the two on top of the piles.",
                  R.title_card("The six Spirit powers", "Quick reference", kicker="Spirits of the Wild"))]
    for i, k in enumerate(SPIRIT_GRID):
        x = 90 + (i % 3) * 590
        y = 60 + (i // 3) * 450
        cam = clamp_cam(x + 280 - 450, y + 210 - 253, 900)
        S.append(dict(text=SPIRIT_SAY[k], image=R.spirit_grid(SPIRIT_GRID, hl=k), cam=cam, hold=0.6))
    S.append(dict(text="Do the steps in the order written, then slide the card under its pile.",
                  image=R.spirit_grid(SPIRIT_GRID, bar="Do the steps in order, then card goes under its pile"),
                  hold=1.0))
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
    S = [card_seg("Let's watch Ana and Ben play a whole game. We'll slow down for the big moments "
                  "and fast-forward the rest.",
                  R.title_card("Sample game", "Ana vs Ben · highlights", kicker="Spirits of the Wild"))]
    setup = log[0]["state"]
    S.append(seg(f"Ana is at the bottom, Ben at the top. The bowl starts with "
                 f"{colors_words(setup['bowl'])}, and Ana's Take Two Stones card starts face down.",
                 setup, cam=FULL, ticker=True, bar="Setup", hl={"card": (0, E.TAKE2), "mid": "bowl"}))
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
                         hl={"card": (p, act)}, hold=0.7, sfx=["card"]))
            continue
        in_skip = False
        if act == E.SPIRIT:
            intro = f"Turn {n}. {who} plays Spirit Power, and picks the {ev['spirit'].capitalize()}."
            S.append(seg(intro, ev["pre"], cam=FULL, ticker=True, bar=label,
                         hl={"card": (p, act), "mid": ev["spirit"]}, sfx=["card"]))
        else:
            S.append(seg(f"Turn {n}. {who}: {E.CARD_NAMES[act].replace('&', 'and')}.", ev["pre"],
                         cam=FULL, ticker=True, bar=label, hl={"card": (p, act)}, sfx=["card"]))
        prev = ev["pre"]
        for step, snap in zip(ev["steps"], ev["snaps"]):
            kind = step[0]
            hl, cam = {}, FULL
            if kind == "draw":
                if not step[1]:
                    continue
                text = f"Into the bowl: {colors_words(step[1])}."
                hl, cam = {"mid": "bowl"}, CAM_MID
            elif kind == "take":
                if not step[1]:
                    continue
                verb = "puts" if all(w and w[1] == "bonus" for c, w in step[1]) else "gives"
                text = f"{pr['s'].capitalize()} {verb} {place_words(step[1])}."
                secs = [w[0] for c, w in step[1] if w]
                hl, cam = {"sections": (p, secs)}, cam_player(p)
                if any(w and w[1] == "bonus" for c, w in step[1]):
                    text += " Double points, and that animal is closed."
            elif kind == "ram":
                text = (f"The Ram puts {colors_words([c for c, _ in step[1]])} straight from the bag: "
                        f"{place_words(step[1])}.")
                hl, cam = {"sections": (p, [w[0] for c, w in step[1] if w])}, cam_player(p)
            elif kind in ("coyote", "coyote_half"):
                opp, tgt, was = NAMES[step[1]], step[2], step[3]
                frm = f" off {pr['p']} own {ANAME[was[1]]}" if was and was[0] == p else ""
                if kind == "coyote_half":
                    text = (f"Both Take One cards are face down: the Coyote is complete! {who} moves "
                            f"it{frm} onto {opp}'s {ANAME[tgt]}.")
                else:
                    text = f"And the Coyote jumps{frm} onto {opp}'s {ANAME[tgt]}."
                hl = {"sections": (step[1], [tgt])}
            elif kind == "bear_return":
                text = "The Bear sends the whole bowl back into the bag..."
                hl, cam = {"mid": "bowl"}, CAM_MID
            elif kind == "deer_remove":
                text = f"The Deer moves {stone_word(step[1])} from {pr['p']} {ANAME[step[2]]} back to the bowl."
                hl, cam = {"sections": (p, [step[2]]), "mid": "bowl"}, CAM_MID
            elif kind == "bison_return":
                text = f"Then the Bison sends {stone_word(step[1])} back into the bag."
                if step[1] == E.CLEAR:
                    text += " That keeps the game going longer."
                hl, cam = {"mid": "bowl"}, CAM_MID
            elif kind == "recover":
                text = ""
                hl = {"card": (p, E.SPIRIT)}
            elif kind == "extra":
                text = f"And thanks to the Eagle, {who} plays again!"
            else:
                continue
            S.append(seg(text, snap, prev, cam=cam, ticker=True, bar=label, hl=hl,
                         hold=0.6 if text else 0.4))
            prev = snap
        post = ev["post"]
        extra = []
        if post["clear_out"] != prev_out and post["clear_out"] >= 3:
            extra.append(f"That's {NUM[post['clear_out']]} Spirit Stones out of the bag.")
        sc = post["scores"]
        if n in feat and len(turns) - n > 1:
            pass
        prev_out = post["clear_out"]
        if extra:
            S.append(seg(" ".join(extra), post, cam=CAM_BAG, ticker=True, bar=label, hl={"mid": "meter"}))
    end = log[-1]["state"]
    sc = end["scores"]
    co = end["clear_out"]
    S.append(seg(f"{NUM[co].capitalize()} Spirit Stones are out at the end of the turn. Game over!",
                 end, cam=CAM_BAG, ticker=True, bar="Game over", hl={"mid": "meter"}))
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
    "learn-to-play": learn_to_play,
    "sample-game": sample_game,
    "spirit-powers": spirit_powers,
}


if __name__ == "__main__":
    names = sys.argv[1:] or list(CLIPS)
    for n in names:
        A.build(n, CLIPS[n](), OUT, WORK)
