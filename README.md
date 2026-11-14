# Boardgames

English rules, cheat sheets and narrated how-to-play videos for board games.

How everything here is made, and how to add a new game: [docs/PLAYBOOK.md](docs/PLAYBOOK.md).

## Spirits of the Wild (2 players, ~30 min)

| What | File |
|---|---|
| Full English manual | [docs/spirits-of-the-wild/manual.md](docs/spirits-of-the-wild/manual.md) · [PDF](docs/spirits-of-the-wild/manual.pdf) |
| Illustrated full-colour manual (A4, print double-sided; score sheet + quick reference) | [manual-color.pdf](docs/spirits-of-the-wild/manual-color.pdf) · rebuild: `python3 tools/build_color_manual.py` |
| One-page cheat sheet | [docs/spirits-of-the-wild/quick-reference.md](docs/spirits-of-the-wild/quick-reference.md) |
| Practice scenarios (7 puzzles with answers) | [docs/spirits-of-the-wild/scenarios.html](docs/spirits-of-the-wild/scenarios.html) |
| Arcade trainer (7 playable stages + Score Rush quick-fire mode) | [docs/spirits-of-the-wild/arcade.html](docs/spirits-of-the-wild/arcade.html) |
| Videos (with .srt subtitles) | [docs/spirits-of-the-wild/videos/](docs/spirits-of-the-wild/videos/) |

Videos (narrated, animated, with .srt subtitles). A short series for complete beginners: each
episode teaches one idea in 1–2½ minutes and ends with a "Remember" recap and a "Next" teaser.
Watch them in order:

1. `01-what-is-this-game.mp4` – two players, taking turns, stones, animals, points, the winner
2. `02-getting-ready.mp4` – setting up the table step by step (both players get the same six cards)
3. `03-your-turn.mp4` – pick a card, do it, turn it face-down
4. `04-placing-stones.mp4` – sections, each animal's rule, stones that fit nowhere, reading the points
5. `05-rabbit-turtle-salmon.mp4` – meet the animals, part 1
6. `06-owl-and-beaver.mp4` – meet the animals, part 2
7. `07-getting-cards-back.mp4` – the Spirit Power card: turn all your cards face-up again
8. `08-the-coyote.mp4` – blocking an animal, and the two ways to move the Coyote
9. `09-spirit-stones-and-the-end.mp4` – double points with Spirit Stones, the end of the game, ties
10. `10-spirit-powers.mp4` – the six Spirit Power cards, one at a time
11. `11-sample-game.mp4` – a complete game between Ana and Ben: big moments explained, routine turns fast-forwarded

Owl pairs score **4** in the 2019 German edition (used here) and **3** in the 2017 English printing.

### Rebuilding

```bash
bash tools/setup_env.sh                 # from the parent dir of the checkout: Kokoro TTS + voice model
cd tools/sotw && python3 videos.py      # all 11 episodes (~25 min of building)
python3 videos.py 03-your-turn          # or just some episodes, by file name without .mp4
SOTW_WORK=/tmp/sotw python3 videos.py   # scratch dir for frames and the TTS cache (default /tmp/sotw-build)
node tools/build_manual_pdf.js          # manual.md -> manual.pdf
```

- `engine.py` – rules engine and simple AI that plays the sample game (seed in `videos.py`)
- `render.py` – draws the table at 2× resolution so the camera can zoom without blur
- `anim.py` – stone/Coyote animations, crossfades, camera moves, on-screen captions/arrows/spotlights
  (drawn after the camera crop, so they stay large at any zoom), sound effects, music, narration and
  ffmpeg assembly. Narration is Kokoro `af_heart` at speed 0.9, voiced one sentence at a time with a
  short pause between sentences (one subtitle cue per sentence); change with `SOTW_VOICE=bm_george`,
  `SOTW_SPEED=1.0`
- `videos.py` – the scripts for each episode (`EPISODES` / `CLIPS`); one short sentence per idea

## Azul (2–4 players, ~30–45 min)

Rules follow the photographed German rulebook (2018), which matches the published English rules on every number.

| What | File |
|---|---|
| Full English manual (with German → English glossary) | [docs/azul/manual.md](docs/azul/manual.md) · [PDF](docs/azul/manual.pdf) |
| Illustrated full-colour manual (A4, print double-sided; score sheet + quick reference) | [manual-color.pdf](docs/azul/manual-color.pdf) |
| One-page cheat sheet | [docs/azul/quick-reference.md](docs/azul/quick-reference.md) |
| Learning page: 8 hands-on lessons, 7 scoring puzzles, quick-fire practice | [docs/azul/learn.html](docs/azul/learn.html) |
| Beginner video series (11 episodes, with .srt subtitles) | [docs/azul/videos/](docs/azul/videos/) |
| Rules engine + seeded AI (source of truth for every point value) | [tools/azul/engine.py](tools/azul/engine.py) · tests: `tests/test_azul_engine.py` |

### Rebuilding

```bash
node tools/build_manual_pdf.js azul          # docs/azul/manual.md -> docs/azul/manual.pdf
python3 tools/azul/engine.py 1 2             # print a seeded AI game: seed 1, 2 players
python3 tools/build_azul_color_manual.py     # docs/azul/manual-color.pdf
bash tools/azul/learn/build.sh               # docs/azul/learn.html from tools/azul/learn/parts
AZUL_WORK=/tmp/azul-build python3 tools/azul/videos.py [episode ...]   # videos (~30 min for all 11)
python3 -m pytest tests/ -k azul
```
