# Boardgames

English rules, cheat sheets and narrated how-to-play videos for board games.

## Spirits of the Wild (2 players, ~30 min)

| What | File |
|---|---|
| Full English manual | [docs/spirits-of-the-wild/manual.md](docs/spirits-of-the-wild/manual.md) · [PDF](docs/spirits-of-the-wild/manual.pdf) |
| One-page cheat sheet | [docs/spirits-of-the-wild/quick-reference.md](docs/spirits-of-the-wild/quick-reference.md) |
| Videos (with .srt subtitles) | [docs/spirits-of-the-wild/videos/](docs/spirits-of-the-wild/videos/) |

Videos:

1. `01-overview-and-setup.mp4` – story, goal, components, setup (1.5 min)
2. `02-turn-and-action-cards.mp4` – how a turn works, the six action cards (1.7 min)
3. `03-animals-and-scoring.mp4` – the five animals, Spirit Stones, scoring (1.6 min)
4. `04-spirit-powers-coyote-and-end.mp4` – the six Spirit cards, the Coyote, game end (2 min)
5. `05-full-sample-game.mp4` – a complete simulated game, turn by turn, ending in a tie-break (6.3 min)
0. `00-complete-rules-tutorial.mp4` – parts 1–4 joined into one video

Owl pairs score **4** in the 2019 German edition (used here) and **3** in the 2017 English printing.

### Rebuilding

```bash
bash tools/setup_env.sh                # from the parent dir of the checkout: piper TTS + voice
cd tools/sotw && python3 build_videos.py   # all clips; or name clips, e.g. 05-full-sample-game
node tools/build_manual_pdf.js         # manual.md -> manual.pdf
```

`tools/sotw/engine.py` is a rules engine with a simple AI that plays the sample game
(seed set in `build_videos.py`); `render.py` draws the frames; narration uses the offline
Piper voice `en_US-lessac-medium`; ffmpeg assembles the clips.
