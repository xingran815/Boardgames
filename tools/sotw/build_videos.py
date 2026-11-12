"""Build the English explainer videos for Spirits of the Wild.

Usage:  python3 build_videos.py [clip ...]     (default: all)
Needs:  ffmpeg, piper-tts, Pillow, and the voice model in tools/voices/
        (see tools/setup_env.sh).
Output: docs/spirits-of-the-wild/videos/*.mp4 (+ .srt subtitles)
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import wave
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import engine as E
import render as R

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "spirits-of-the-wild" / "videos"
WORK = Path(os.environ.get("SOTW_WORK", "/tmp/sotw-build"))
VOICE = Path(os.environ.get(
    "SOTW_VOICE", ROOT / "tools" / "voices" / "en_US-lessac-medium.onnx"))
SEED = 1300
NAMES = ("Ana", "Ben")
PRON = ({"s": "she", "o": "her", "p": "her"}, {"s": "he", "o": "him", "p": "his"})
FPS = 30
PAD = 0.45  # silence after each line


# ===================================================================== TTS
_voice = None


def tts(text, path):
    global _voice
    if path.exists():
        return
    from piper import PiperVoice
    if _voice is None:
        _voice = PiperVoice.load(str(VOICE))
    tmp = path.with_suffix(".tmp.wav")
    with wave.open(str(tmp), "wb") as wf:
        _voice.synthesize_wav(text, wf)
    tmp.rename(path)


def wav_len(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def make_segment(args):
    idx, img_path, text, seg_dir = args
    h = hashlib.sha1(text.encode()).hexdigest()[:12]
    wav = WORK / "tts" / f"{h}.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    tts(text, wav)
    dur = wav_len(wav) + PAD
    out = Path(seg_dir) / f"{idx:04d}.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-framerate", str(FPS), "-i", str(img_path),
        "-i", str(wav),
        "-filter_complex",
        f"[0:v]fade=t=in:st=0:d=0.18,format=yuv420p[v];[1:a]apad,atrim=0:{dur:.3f},"
        "aresample=44100[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
        "-crf", "22", "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ac", "1",
        str(out)], check=True)
    return idx, dur


def build_clip(name, segments):
    """segments: list of (PIL image, narration text)."""
    seg_dir = WORK / name
    seg_dir.mkdir(parents=True, exist_ok=True)
    jobs = []
    for i, (im, text) in enumerate(segments):
        p = seg_dir / f"{i:04d}.png"
        im.save(p)
        jobs.append((i, str(p), text, str(seg_dir)))
    with ProcessPoolExecutor(max_workers=os.cpu_count() or 2) as ex:
        durs = dict(ex.map(make_segment, jobs))
    lst = seg_dir / "list.txt"
    lst.write_text("".join(f"file '{seg_dir}/{i:04d}.mp4'\n" for i in range(len(jobs))))
    OUT.mkdir(parents=True, exist_ok=True)
    mp4 = OUT / f"{name}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(mp4)],
                   check=True)
    # subtitles
    t, srt = 0.0, []
    for i, (_, text) in enumerate(segments):
        a, b = t, t + durs[i] - PAD / 2
        srt.append(f"{i + 1}\n{_ts(a)} --> {_ts(b)}\n{text}\n")
        t += durs[i]
    (OUT / f"{name}.srt").write_text("\n".join(srt))
    print(f"{mp4.name}: {len(segments)} segments, {t / 60:.1f} min")
    return mp4


def _ts(t):
    h, m = divmod(int(t), 3600)
    m, s = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{int((t % 1) * 1000):03d}"


# ============================================================ state helpers
def base_state():
    g = E.Game(seed=11)
    g.setup()
    st = g.snapshot()
    return st


def with_board(st, p, **kw):
    st = copy.deepcopy(st)
    b = st["boards"][p]
    for k, v in kw.items():
        if k == "bonus":
            for a in v:
                b["bonus"][a] = True
        else:
            b[k] = v
    st["scores"] = [E.total_score(x) for x in st["boards"]]
    return st


def demo_board(**kw):
    b = E.new_board()
    for k, v in kw.items():
        if k == "bonus":
            for a in v:
                b["bonus"][a] = True
        else:
            b[k] = v
    return b


def T(st, cap, **hl):
    return R.table(st, NAMES, cap=cap, hl=hl)


def S(title, cap, bullets=None, sub=None, art=None):
    return R.slide(title, bullets=bullets, sub=sub, cap=cap, art=art)


# ======================================================== clip 1: overview
def clip_overview():
    segs = []
    allc = E.COLORS + [E.CLEAR]
    segs.append((S("Spirits of the Wild", "Welcome! This video teaches you Spirits of the Wild, "
                   "a quick two player game of collecting colorful stones.",
                   sub="How to play  ·  Part 1: Overview and Setup"),
                 "Welcome! This video teaches you Spirits of the Wild, a quick two player game "
                 "of collecting colorful stones."))
    segs.append((S("The story", "Long ago, five forest animals rose to the stars and came back as spirits.",
                   bullets=["Five forest animals rose to the stars and returned as spirits.",
                            "Bring them beautiful stones and they will reward you.",
                            "But watch out for the jealous Coyote, who loves to get in the way."]),
                 "Legend says that five forest animals rose to the stars and came back as spirits. "
                 "Bring them beautiful stones and they will reward you. But watch out for the "
                 "jealous Coyote, who loves to get in the way."))
    segs.append((S("Goal of the game", "Collect stones, give them to your animals, score the most points.",
                   bullets=["Use your action cards to get stones from the bowl.",
                            "Give each stone to one of the five animals on your board.",
                            "Each animal wants a different pattern of colors.",
                            "Most points at the end wins."]),
                 "Your goal is simple. Use your action cards to get stones, give them to the five "
                 "animals on your board, and score the most points. Each animal wants a different "
                 "pattern of colors."))
    segs.append((S("What's in the box", "There are fifty six stones: eight in each of seven colors.",
                   bullets=["1 bowl, 1 cloth bag, 1 Coyote pawn",
                            "2 player boards, 12 action cards (6 each)",
                            "6 Spirit Power cards",
                            "56 stones: 8 each of green, yellow, blue, purple, white, red and clear"],
                   art=R.stones_row(allc, 170, 820, r=38, gap=100)),
                 "In the box you will find a bowl, a cloth bag, the Coyote pawn, two player boards, "
                 "twelve action cards, six Spirit Power cards, and fifty six stones: eight in each "
                 "of seven colors."))
    segs.append((S("Spirit Stones", "The eight clear stones are special Spirit Stones.",
                   bullets=["The 8 clear stones are Spirit Stones.",
                            "They only go on an animal's x2 bonus space and double that animal.",
                            "When the fifth Spirit Stone leaves the bag, the game ends."],
                   art=R.stones_row([E.CLEAR] * 5, 170, 760, r=40, gap=110)),
                 "The eight clear stones are Spirit Stones. They can only go on an animal's bonus "
                 "space, where they double that animal's points. And they are the game clock: when "
                 "the fifth Spirit Stone has left the bag, the game ends."))
    st = base_state()
    st0 = copy.deepcopy(st)
    st0["bowl"] = []
    st0["cards"][0][E.TAKE2] = True
    st0["bag"] = 56
    st0["clear_out"] = 0
    segs.append((T(st0, "Setup step 1: put the bowl between the players, and set the Coyote aside.",
                   mid="bowl"),
                 "Setup. Put the bowl between the two players, and set the Coyote to the side."))
    segs.append((T(st, "Step 2: all stones go in the bag. Draw four into the bowl.", mid="bowl", drawn=4),
                 "Put all the stones into the bag and shake it. Then draw four stones into the bowl. "
                 "If you draw a clear Spirit Stone, put it back and draw a new one, so the bowl starts "
                 "with four colored stones."))
    segs.append((T(st0 | {"bowl": st["bowl"], "bag": st["bag"]},
                   "Step 3: each player takes a board and six action cards, face up."),
                 "Each player takes a player board and a set of six action cards, laid out face up "
                 "in front of the board."))
    segs.append((T(st, "Step 4: shuffle the six Spirit Power cards into two face-up piles of three."),
                 "Shuffle the six Spirit Power cards and make two face-up piles of three cards. "
                 "Only the top card of each pile can be chosen."))
    segs.append((T(st, "Step 5: the start player turns their Take Two Stones card face down.",
                   card=(0, E.TAKE2)),
                 "Finally, choose a start player. To balance the first move, the start player turns "
                 "their Take Two Stones card face down. They can't use it until they recover their "
                 "cards. Now you are ready to play!"))
    return segs


# ===================================================== clip 2: turn + cards
def clip_actions():
    segs = []
    st = base_state()
    st["cards"][0][E.TAKE2] = True
    segs.append((S("Your turn", "On your turn, choose one face-up action card and do what it says.",
                   sub="Part 2: Taking a turn and the action cards"),
                 "Part two: taking a turn. On your turn, choose one of your face-up action cards, "
                 "do what it says, and then turn that card face down."))
    segs.append((S("Taking a turn", "Face-down cards can't be used until you recover them.",
                   bullets=["Pick one face-up action card.",
                            "Do the action.",
                            "Turn the card face down: it's used up for now.",
                            "If a card says take stones, they must be in the bowl."]),
                 "Face-down cards can't be used again until you recover them with your Spirit Power "
                 "card. And if a card tells you to take stones, those stones must actually be "
                 "available in the bowl."))
    # Take one stone
    s1 = copy.deepcopy(st)
    s1["bowl"] = ["red", "blue", "green", "yellow"]
    segs.append((T(s1, "Take One Stone: take one stone from the bowl and place it on your board.",
                   card=(0, E.TAKE1A), mid="bowl"),
                 "Take One Stone. Take one stone from the bowl and place it on your board. "
                 "You have two of these cards. If the bowl is empty, you can't use it."))
    s2 = with_board(s1, 0, rabbit=["red"])
    s2["bowl"] = ["blue", "green", "yellow"]
    s2["cards"][0][E.TAKE1A] = False
    segs.append((T(s2, "Ana takes the red stone and gives it to her Rabbit. The card turns face down.",
                   sections=(0, ["rabbit"]), card=(0, E.TAKE1A)),
                 "For example, Ana takes the red stone and gives it to her Rabbit. Then the card "
                 "is turned face down."))
    segs.append((T(s2, "Take Two Stones: take two stones from the bowl. Needs at least two in the bowl.",
                   card=(0, E.TAKE2), mid="bowl"),
                 "Take Two Stones. Take two stones from the bowl and place them on your board. "
                 "You can only use it if there are at least two stones in the bowl."))
    s3 = copy.deepcopy(s2)
    s3["bowl"] = s2["bowl"] + ["white", "purple"]
    s3["bag"] -= 2
    segs.append((T(s3, "Add Two Stones & Take One: draw two from the bag into the bowl, then take one.",
                   card=(0, E.ADD2), mid="bowl", drawn=2),
                 "Add Two Stones and Take One. First draw two stones from the bag and add them to "
                 "the bowl. Then take any one stone from the bowl. More choice, but only one stone."))
    s4 = copy.deepcopy(s3)
    s4["bowl"] = s3["bowl"] + ["red", "red", "clear"]
    s4["bag"] -= 3
    s4["clear_out"] += 1
    segs.append((T(s4, "Add Three Stones & Move Coyote: draw three into the bowl…",
                   card=(0, E.ADD3), mid="bowl", drawn=3),
                 "Add Three Stones and Move Coyote. Draw three stones from the bag into the bowl. "
                 "You don't take any stones with this card."))
    s5 = copy.deepcopy(s4)
    s5["coyote"] = (1, "turtle")
    segs.append((T(s5, "…then you may put the Coyote on one animal on your opponent's board.",
                   sections=(1, ["turtle"])),
                 "Then you may put the Coyote on one animal on your opponent's board. While the "
                 "Coyote sits there, your opponent can't add any stones to that animal. Moving "
                 "the Coyote is optional."))
    s6 = copy.deepcopy(s5)
    for c in (E.TAKE1A, E.TAKE1B, E.ADD2):
        s6["cards"][0][c] = False
    segs.append((T(s6, "Spirit Power & Recover Cards: only when three or more other cards are face down.",
                   card=(0, E.SPIRIT)),
                 "The last card is Use Spirit Power and Recover Cards. You may only play it when at "
                 "least three of your other action cards are face down."))
    segs.append((T(s6, "Choose one top Spirit card, do its power, put it under its pile…",
                   mid=s6["piles"][0][0]),
                 "When you play it, choose one of the two face-up Spirit Power cards, do its action "
                 "in the order written, and slide that card under the bottom of its pile."))
    s7 = copy.deepcopy(s6)
    for c in E.CARD_ORDER:
        s7["cards"][0][c] = True
    segs.append((T(s7, "…and turn ALL your action cards face up again.", card=(0, E.SPIRIT)),
                 "Then turn all six of your action cards face up again. Timing this well is the "
                 "heart of the game: you can't recover too early, but waiting too long wastes "
                 "turns."))
    segs.append((S("Can't place a stone?", "If you take a stone you can't place, return it to the bowl.",
                   bullets=["Every stone must follow the rules of the animal you give it to.",
                            "If you take a stone that fits nowhere, it goes back into the bowl.",
                            "So check your board before you take!"]),
                 "One more rule. Every stone must follow the requirement of the animal you give it "
                 "to. If you take a stone that you can't place anywhere, it goes back into the bowl."))
    return segs


# =================================================== clip 3: animals & score
def clip_animals():
    segs = []
    segs.append((S("The five animals", "Each animal wants stones in a different pattern.",
                   sub="Part 3: The animals and scoring"),
                 "Part three: the five animals. Each section of your board shows an animal and "
                 "the pattern of stones it wants."))

    def ex(animal, board, title, cap, bullets, say):
        segs.append((S(title, cap, bullets=bullets,
                       art=R.section_art(board, animal)), say))

    ex("rabbit", demo_board(rabbit=["red", "blue", "yellow"]), "Rabbit – three different colors",
       "Rabbit: three stones, all different colors, worth 6 points.",
       ["Every stone must be a different color.", "3 stones = 6 points.",
        "An incomplete Rabbit scores nothing!"],
       "The Rabbit wants three different colors. A complete set of three is worth six points, "
       "but an incomplete Rabbit scores nothing.")
    ex("turtle", demo_board(turtle=["green"] * 4), "Turtle – all one color",
       "Turtle: all the same color. 1, 3, 6, 9 or 14 points.",
       ["Every stone must be the same color.", "1 / 2 / 3 / 4 / 5 stones",
        "= 1 / 3 / 6 / 9 / 14 points"],
       "The Turtle wants stones that are all the same color. The more you give, the more it pays: "
       "one, three, six, nine, and fourteen points for five stones.")
    ex("salmon", demo_board(salmon=["green", "yellow", "blue", "purple"]), "Salmon – one of each color",
       "Salmon: every stone a different color. Up to 13 points for six.",
       ["Every stone must be a different color.", "1 / 2 / 3 / 4 / 5 / 6 stones",
        "= 1 / 2 / 4 / 6 / 9 / 13 points"],
       "The Salmon wants one of each color, so every stone must be different. One stone is worth "
       "one point, then two, four, six, nine, and thirteen points for all six colors.")
    ex("owl", demo_board(owl=[["white", "white"], ["red"]]), "Owl – same-colored pairs",
       f"Owl: pairs of the same color, {E.OWL_POINTS} points per complete pair.",
       [f"{E.OWL_POINTS} points for each complete pair (English 2017 printing: 3).",
        "You may start a new pair before finishing another.",
        "Only complete pairs score."],
       "The Owl wants pairs of the same color. Each complete pair is worth four points in your "
       "edition. Some English printings say three. You may start a new pair before finishing "
       "another, but only complete pairs score.")
    ex("beaver", demo_board(beaver={"triple": ["blue"] * 3, "pair": ["yellow"] * 2}),
       "Beaver – a triple and a pair", "Beaver: triple = 5, pair = 2, both = 7 bonus. Total 14.",
       ["Three of one color: 5 points.", "A pair of one color: 2 points.",
        "Complete both: +7 bonus (14 total)."],
       "The Beaver wants three of a kind and a same-colored pair. The triple is worth five, the "
       "pair is worth two, and completing both earns a seven point bonus, for fourteen in total.")
    b = demo_board(turtle=["red"] * 4, bonus=["turtle"])
    segs.append((S("Spirit Stones double", "A Spirit Stone on a bonus space doubles that animal…",
                   bullets=["Clear Spirit Stones go only on the x2 bonus space.",
                            "That animal's points are doubled.",
                            "But the section is now CLOSED: no more stones there."],
                   art=R.section_art(b, "turtle")),
                 "Clear Spirit Stones can only go on an animal's bonus space. They double that "
                 "animal's points. Here, four red stones on the Turtle are worth nine, doubled to "
                 "eighteen. But placing a Spirit Stone closes the section: no more stones can go there."))
    segs.append((S("When to use a Spirit Stone", "Tip: cap an animal that is already big.",
                   bullets=["Best on an animal that is full or nearly full.",
                            "On an empty animal it doubles zero!",
                            "Every Spirit Stone taken out of the bag also brings the end closer."]),
                 "A tip: a Spirit Stone is best on an animal that is already full or almost full. "
                 "Doubling zero is still zero. And remember, every Spirit Stone out of the bag "
                 "brings the end of the game closer."))
    st = base_state()
    st = with_board(st, 0, rabbit=["red", "blue", "yellow"], turtle=["white"] * 3,
                    salmon=["green", "purple"], owl=[["red", "red"], ["blue"]],
                    beaver={"triple": ["green"] * 3, "pair": []}, bonus=["rabbit"])
    segs.append((T(st, "Scoring example: Rabbit 12, Turtle 6, Salmon 2, Owl 4, Beaver 5 = 29.",
                   sections=(0, list(E.ANIMALS))),
                 f"At the end, add up every animal. Here Ana has a doubled Rabbit for twelve, six for "
                 f"the Turtle, two for the Salmon, four for one Owl pair, and five for the Beaver's "
                 f"triple. That's {st['scores'][0]} points."))
    return segs


# ================================================= clip 4: spirits & coyote
SPIRIT_TEXT = {
    "bear": ("Bear", ["Put all stones from the bowl back in the bag.",
                      "Draw the same number from the bag into the bowl.",
                      "Take one stone from the bowl."],
             "Bear. Count the stones in the bowl and put them back in the bag. Draw the same "
             "number of new stones into the bowl, then take one. Great when the bowl is full "
             "of colors you don't need."),
    "wolf": ("Wolf", ["Draw four stones from the bag into the bowl.", "Take one stone from the bowl."],
             "Wolf. Draw four stones from the bag into the bowl, then take one. Lots of choice."),
    "ram": ("Ram", ["Draw two stones from the bag straight onto your board.",
                    "You must place both if you can.",
                    "Stones you can't place go into the bowl."],
            "Ram. Draw two stones from the bag and place them directly on your board. You must "
            "place both if you can. Any you can't place go into the bowl. It's a gamble!"),
    "eagle": ("Eagle", ["Take one stone from the bowl.",
                        "After recovering your cards, take another turn!"],
              "Eagle. Take one stone from the bowl, and after you recover your cards, you get "
              "another whole turn."),
    "deer": ("Deer", ["Move one stone from your board to the bowl.",
                      "Then take two stones from the bowl."],
             "Deer. Take one stone off your own board and put it in the bowl. Then take two "
             "stones from the bowl. Use it to fix a mistake or swap a stone."),
    "bison": ("Bison", ["Draw three stones into the bowl.", "Take one stone from the bowl.",
                        "Then return one stone from the bowl to the bag."],
              "Bison. Draw three stones into the bowl and take one. Then pick another stone from "
              "the bowl and put it back in the bag. It doesn't have to be one you just drew. "
              "You can even put a Spirit Stone back to delay the end of the game."),
}


def clip_spirits():
    segs = []
    segs.append((S("Spirit Powers & the Coyote", "The six Spirit Power cards, the Coyote, and the end.",
                   sub="Part 4: Spirit Powers, the Coyote and the end of the game"),
                 "Part four: the Spirit Power cards, the Coyote, and how the game ends."))
    segs.append((S("Spirit Power cards", "When you recover, you also use one of the two face-up Spirit cards.",
                   bullets=["Only the top card of each pile is available.",
                            "Do its actions in the order written.",
                            "Then put it under its pile: the next card is revealed."]),
                 "Whenever you play your Spirit Power card, you choose one of the two face-up "
                 "Spirit cards, do its actions in order, and put it under its pile. Here are all six."))
    for k in E.SPIRITS:
        name, bullets, say = SPIRIT_TEXT[k]

        def art(im, d, k=k):
            d.rounded_rectangle((1350, 260, 1750, 640), 22, fill=(40, 60, 120),
                                outline=(120, 160, 230), width=3)
            R.text_center(d, (1550, 300), name.upper(), R.F["h1"])
            for j, ln in enumerate(R.SPIRIT_SHORT[k]):
                R.text_center(d, (1550, 420 + j * 44), ln, R.F["s"], fill=R.MUTED)
        segs.append((S(f"{name}", say.split(". ")[0] + ".", bullets=bullets, art=art), say))
    st = base_state()
    st["coyote"] = (1, "salmon")
    st = with_board(st, 1, salmon=["red", "blue", "green"])
    segs.append((T(st, "The Coyote blocks one animal: no stones (not even Spirit Stones) can go there.",
                   sections=(1, ["salmon"])),
                 "The Coyote. While the Coyote stands on one of your animals, you can't add any "
                 "stones to it, not even a Spirit Stone, until the Coyote moves away."))
    s2 = copy.deepcopy(st)
    s2["cards"][0][E.TAKE1A] = False
    s2["cards"][0][E.TAKE1B] = False
    segs.append((T(s2, "Each Take One Stone card has half a Coyote on its back.",
                   card=(0, E.TAKE1B)),
                 "There are two ways to move the Coyote. One is the Add Three Stones and Move "
                 "Coyote card. The other is hidden on the back of your two Take One Stone cards: "
                 "each shows half of the Coyote."))
    s3 = copy.deepcopy(s2)
    s3["coyote"] = (1, "turtle")
    s3 = with_board(s3, 1, turtle=["white", "white"])
    segs.append((T(s3, "Both halves face down = complete Coyote: move it to your opponent's board.",
                   sections=(1, ["turtle"])),
                 "When both Take One Stone cards are face down, the Coyote picture is complete, "
                 "and you may move the Coyote onto any animal on your opponent's board."))
    s4 = copy.deepcopy(st)
    s4["clear_out"] = 5
    segs.append((T(s4, "Game end: five Spirit Stones out of the bag at the end of a turn.", mid="bowl"),
                 "The end of the game. If at the end of any turn five Spirit Stones are out of the "
                 "bag, in the bowl or on the boards, the game ends immediately. With the Bison you "
                 "can return one to the bag before your turn ends to keep the game going."))
    segs.append((S("Who wins?", "Most points wins. Tie: the player with the Coyote on their board wins.",
                   bullets=["Add up all five animals (Spirit Stones double).",
                            "The most points wins.",
                            "Tie? The player who has the Coyote on their board wins."]),
                 "Add up your points. The player with the most points wins. If it's a tie, the "
                 "player who currently has the Coyote on their board wins. The trickster pays you "
                 "back after all! Now watch a full sample game in part five."))
    return segs


# ================================================= clip 5: full sample game
ANAME = {"rabbit": "Rabbit", "turtle": "Turtle", "salmon": "Salmon", "owl": "Owl", "beaver": "Beaver"}


def stone_word(c):
    return "a Spirit Stone" if c == E.CLEAR else f"a {c} stone"


def where_word(w):
    a, slot = w
    if slot == "bonus":
        return f"on the {ANAME[a]}'s bonus space, doubling it and closing that section"
    if slot == "triple":
        return "to the Beaver's triple"
    if slot == "pair":
        return "to the Beaver's pair"
    return f"to the {ANAME[a]}"


def list_words(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


NUM = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}


def colors_words(cs):
    from collections import Counter
    cnt = Counter(cs)
    parts = []
    for c, n in cnt.items():
        if c == E.CLEAR:
            parts.append("a Spirit Stone" if n == 1 else f"{NUM[n]} Spirit Stones")
        else:
            parts.append(f"{'a' if n == 1 else NUM[n]} {c}")
    return list_words(parts)


def placements_words(res, who):
    out = []
    for c, w in res:
        if w is None:
            out.append(f"{stone_word(c)} that fits nowhere, so it goes back to the bowl")
        elif w[1] == "bonus":
            out.append(f"{stone_word(c)} {where_word(w)}")
        else:
            out.append(f"{stone_word(c)} {where_word(w)}")
    return list_words(out)


def take_sentence(pr, res):
    if all(w and w[1] == "bonus" for c, w in res):
        return f"{pr['s'].capitalize()} places {placements_words(res, None)}."
    return f"{pr['s'].capitalize()} gives {placements_words(res, None)}."


def clip_game():
    g = E.Game(seed=SEED, names=NAMES)
    log = g.play()
    segs = []
    setup = log[0]["state"]
    segs.append((S("A full sample game", "Ana and Ben play a complete game, turn by turn.",
                   sub="Part 5: A complete sample game, Ana versus Ben"),
                 "Part five. Let's watch Ana and Ben play a complete game, turn by turn. "
                 "Ana is at the bottom, Ben at the top."))
    segs.append((T(setup, f"Setup: the bowl starts with {colors_words(setup['bowl'])}. "
                   "Ana starts, so her Take Two Stones card is face down.", card=(0, E.TAKE2), mid="bowl"),
                 f"The bowl starts with {colors_words(setup['bowl'])}. The Spirit cards on top are "
                 f"the {setup['piles'][0][0].capitalize()} and the {setup['piles'][1][0].capitalize()}. Ana goes first, so her Take Two "
                 f"Stones card starts face down."))
    prev_out = 0
    n = 0
    for ev in log:
        if ev["type"] != "turn":
            continue
        n += 1
        p = ev["player"]
        who = NAMES[p]
        pr = PRON[p]
        act = ev["action"]
        pre = ev["pre"]
        if act == E.SPIRIT:
            sp = ev["spirit"]
            say = (f"Turn {n}. {who} has at least three cards face down, so {pr['s']} plays Spirit Power "
                   f"and chooses the {sp.capitalize()}.")
            segs.append((T(pre, say, card=(p, act), mid=sp), say))
        elif act is None:
            say = f"Turn {n}. {who} has no usable card and passes."
            segs.append((T(pre, say), say))
        else:
            say = f"Turn {n}. {who} plays {E.CARD_NAMES[act].replace('&', 'and')}."
            segs.append((T(pre, say, card=(p, act)), say))
        for (step, snap) in zip(ev["steps"], ev["snaps"]):
            kind = step[0]
            hl = {}
            if kind == "draw":
                if not step[1]:
                    continue
                say = f"{pr['s'].capitalize()} draws {colors_words(step[1])} into the bowl."
                hl = {"mid": "bowl", "drawn": len(step[1])}
            elif kind == "take":
                res = step[1]
                if not res:
                    continue
                say = take_sentence(pr, res)
                secs = [w[0] for c, w in res if w]
                hl = {"sections": (p, secs)}
            elif kind == "ram":
                say = (f"The Ram draws {colors_words([c for c, _ in step[1]])} straight from the bag. "
                       f"{pr['s'].capitalize()} gives {placements_words(step[1], who)}.")
                hl = {"sections": (p, [w[0] for c, w in step[1] if w])}
            elif kind == "coyote":
                opp = NAMES[step[1]]
                was = pre["coyote"]
                frm = (f" off {pr['p']} own {ANAME[was[1]]}" if was and was[0] == p else "")
                say = f"Then {pr['s']} moves the Coyote{frm} onto {opp}'s {ANAME[step[2]]}."
                hl = {"sections": (step[1], [step[2]])}
            elif kind == "coyote_half":
                opp = NAMES[step[1]]
                say = (f"Both of {pr['p']} Take One Stone cards are now face down. The Coyote picture is "
                       f"complete, so {pr['s']} moves the Coyote to {opp}'s {ANAME[step[2]]}.")
                hl = {"sections": (step[1], [step[2]])}
            elif kind == "bear_return":
                say = f"The Bear sends all {step[1]} stones in the bowl back into the bag."
                hl = {"mid": "bowl"}
            elif kind == "deer_remove":
                say = (f"The Deer lets {pr['o']} move {stone_word(step[1])} from {pr['p']} "
                       f"{ANAME[step[2]]} back to the bowl.")
                hl = {"sections": (p, [step[2]]), "mid": "bowl"}
            elif kind == "bison_return":
                say = f"The Bison returns {stone_word(step[1])} from the bowl to the bag."
                hl = {"mid": "bowl"}
            elif kind == "recover":
                say = f"{who} turns all six action cards face up again."
                hl = {"card": (p, E.SPIRIT)}
            elif kind == "extra":
                say = f"Thanks to the Eagle, {who} takes another turn."
            else:
                continue
            segs.append((T(snap, say, **hl), say))
        post = ev["post"]
        extra = []
        if post["clear_out"] != prev_out:
            k = post["clear_out"]
            extra.append(f"That makes {NUM[k]} Spirit Stone{'s' if k != 1 else ''} out of the bag.")
            prev_out = k
        sc = post["scores"]
        extra.append(f"Score: Ana {sc[0]}, Ben {sc[1]}.")
        say = " ".join(extra)
        # fold the score into the turn's last step to keep the pace up
        last_im, last_say = segs[-1]
        if not last_say.startswith("Turn ") and len(last_say) + len(say) < 150:
            segs[-1] = (T(post, last_say + " " + say), last_say + " " + say)
        else:
            segs.append((T(post, say), say))
    end = log[-1]["state"]
    sc = end["scores"]
    segs.append((T(end, "Five Spirit Stones are out of the bag at the end of the turn. Game over!",
                   mid="bowl"),
                 "Five Spirit Stones are now out of the bag at the end of a turn, so the game ends "
                 "immediately."))
    for p in (0, 1):
        b = end["boards"][p]
        parts = [f"{ANAME[a]} {E.animal_score(b, a)}" for a in E.ANIMALS]
        say = f"{NAMES[p]} scores: {list_words(parts)}. Total {sc[p]}."
        segs.append((T(end, say, sections=(p, list(E.ANIMALS))), say))
    if sc[0] == sc[1]:
        cp = end["coyote"][0] if end["coyote"] else None
        if cp is None:
            say = "It's a tie, and nobody has the Coyote, so the players share the win."
        else:
            say = (f"It's a tie, {sc[0]} to {sc[1]}! The Coyote is on {NAMES[cp]}'s board, so "
                   f"{NAMES[cp]} wins the tie-break. Thanks for watching!")
    else:
        w = 0 if sc[0] > sc[1] else 1
        say = f"{NAMES[w]} wins, {max(sc)} to {min(sc)}! Thanks for watching!"
    segs.append((S("Game over", say, sub=say), say))
    return segs


CLIPS = {
    "01-overview-and-setup": clip_overview,
    "02-turn-and-action-cards": clip_actions,
    "03-animals-and-scoring": clip_animals,
    "04-spirit-powers-coyote-and-end": clip_spirits,
    "05-full-sample-game": clip_game,
}


def main(names):
    names = names or list(CLIPS)
    for n in names:
        build_clip(n, CLIPS[n]())
    if not sys.argv[1:] or "complete" in names:
        lst = WORK / "complete.txt"
        parts = [OUT / f"{k}.mp4" for k in list(CLIPS)[:4]]
        lst.write_text("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c", "copy", "-movflags", "+faststart",
                        str(OUT / "00-complete-rules-tutorial.mp4")], check=True)
        print("00-complete-rules-tutorial.mp4 written")


if __name__ == "__main__":
    main([a for a in sys.argv[1:] if a != "complete"])
