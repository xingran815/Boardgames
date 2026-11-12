# Boardgames

English rules, cheat sheets and narrated how-to-play videos for board games.

## Spirits of the Wild (2 players, ~30 min)

| What | File |
|---|---|
| Full English manual | [docs/spirits-of-the-wild/manual.md](docs/spirits-of-the-wild/manual.md) · [PDF](docs/spirits-of-the-wild/manual.pdf) |
| Illustrated full-colour manual (A4, print double-sided; score sheet + quick reference) | [manual-color.pdf](docs/spirits-of-the-wild/manual-color.pdf) · rebuild: `python3 tools/build_color_manual.py` |
| One-page cheat sheet | [docs/spirits-of-the-wild/quick-reference.md](docs/spirits-of-the-wild/quick-reference.md) |
| Videos (with .srt subtitles) | [docs/spirits-of-the-wild/videos/](docs/spirits-of-the-wild/videos/) |

Videos (narrated, animated, with .srt subtitles):

1. `learn-to-play.mp4` – everything you need to start playing, on one animated board
2. `sample-game.mp4` – a complete game between Ana and Ben: big moments explained, routine turns fast-forwarded
3. `spirit-powers.mp4` – quick reference for the six Spirit Power cards

Owl pairs score **4** in the 2019 German edition (used here) and **3** in the 2017 English printing.

### Rebuilding

```bash
bash tools/setup_env.sh                 # from the parent dir of the checkout: Kokoro TTS + voice model
cd tools/sotw && python3 videos.py      # all videos; or name some, e.g. python3 videos.py sample-game
node tools/build_manual_pdf.js          # manual.md -> manual.pdf
```

- `engine.py` – rules engine and simple AI that plays the sample game (seed in `videos.py`)
- `render.py` – draws the table at 2× resolution so the camera can zoom without blur
- `anim.py` – stone/Coyote animations, camera moves, sound effects, music, narration (Kokoro `af_heart`;
  change with `SOTW_VOICE=bm_george` etc.) and ffmpeg assembly
- `videos.py` – the scripts for each video
