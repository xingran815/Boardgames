# Playbook: making explainers for a board game

How this repo turns a rulebook (often a photo of a non-English rulesheet) into:

- English manuals: Markdown, plain PDF and a printable colour PDF
- an HTML practice page and an HTML arcade trainer
- a series of narrated videos for beginners

*Spirits of the Wild* (`docs/spirits-of-the-wild/`, `tools/sotw/`) is the reference implementation.
Copy its structure for each new game.

---

## 1. Folder layout for a new game

Use a short slug for each game, e.g. `spirits-of-the-wild` → code prefix `sotw`.

```
docs/<game>/
  manual.md  manual.pdf            # full rules in plain English
  manual-color.pdf                 # illustrated, print-ready (A4, double-sided)
  manual-assets/                   # PNGs used by the colour manual
  quick-reference.md               # one-page cheat sheet
  scenarios.html                   # practice puzzles with hidden answers
  arcade.html                      # playable trainer (stages + quick-fire mode)
  videos/NN-<topic>.mp4 + .srt     # beginner episode series
tools/<prefix>/
  engine.py   # rules engine + simple AI (the single source of truth for scoring)
  render.py   # draws the table/components with Pillow at 2× resolution
  anim.py     # animation, camera, captions, TTS, SFX, music, ffmpeg assembly
  videos.py   # the episode scripts
tools/build_color_manual.py, tools/build_manual_pdf.js, tools/setup_env.sh
tests/        # pytest, one file per module
```

Add a section for the game to `README.md` listing every output, plus rebuild commands.

## 2. Order of work

1. **Get the rules right first.**
   - Transcribe and translate the source rules.
   - Find the official English rulebook if one exists and cross-check it.
   - Note every edition difference (e.g. Owl 4 vs 3 points) and every gap the rules leave open.
2. **Write `manual.md`.**
   - Sections: overview, components, setup, turn, each card/action, scoring per element, special pieces, end of game, tie-break, FAQ, beginner strategy (labelled "not rules").
   - Mark house rules as **house rule**, and edition notes as **edition note**.
3. **Write `engine.py` and its tests.**
   - Encode setup, legal moves, scoring and end conditions.
   - Add a deterministic AI (seeded) so a sample game can be replayed exactly.
   - Every number that appears anywhere (manual, puzzles, videos) must be checkable against the engine.
4. Write **`quick-reference.md`**, then build **`manual.pdf`** (pandoc → Chromium).
5. Build the **colour manual** (`build_color_manual.py`): HTML/CSS per A4 page → PDF with Playwright. Pictures come from the game's renderer.
6. Write **scenarios** and the **arcade** trainer (HTML). Their positions and best moves are generated and verified with the engine.
7. Make the **videos** last, once the rules wording is settled.

Rebuild everything that quotes a rule whenever a rule's wording changes. That means the manual, both PDFs, the quick reference, the HTML pages and the videos.

## 3. Writing rules for humans (all formats)

These come from real feedback from people learning the game. Follow them.

- **Say what is the same, not only what differs.** If both players get identical card sets, say so explicitly in setup and show it. Players lost time not knowing this.
- **One name per thing, everywhere.** Don't add descriptive adjectives that can be misread as a rule.
  - "five clear Spirit Stones" was read as a special subset. Write "five Spirit Stones".
  - Describe the look of a component once, in the components list, and nowhere else.
- **Define every game word on first use**, e.g. turn, face-up/face-down, draw, bowl, section, closed, blocked, opponent.
- **Count and condition precisely.** When does the end check happen: during the turn or at the end of it? Is "five out" counting stones from the bag or stones on boards?
- Rules that aren't printed but follow from the text are fine. Rules that need a choice are house rules: label them.
- Keep colour from being the only cue. Give stones letters (G Y B P W R, S) and name colours in the text.

## 4. Video rules (beginner series)

The audience is someone who has **never played a board game**. A dense, single "learn to play" clip was rejected as hard to follow. Short, slow, visual episodes were accepted.

**Structure**
- A series of episodes, **1–2½ minutes each, one idea per episode.** Number them `01-…`, `02-…`. The sample game is the last episode.
- Teach in dependency order, so every episode only uses words and ideas already taught. E.g. teach the Coyote before the tie-break that mentions it.
- Each episode opens with a numbered title card. It ends with a **"Remember"** card of 2–3 lines and a **"Next: …"** teaser.

**Narration**
- Use one idea per sentence, at most **16 words per sentence** (a test enforces this), in everyday words.
- Define each game word the first time it appears ("Reach into the bag without looking… that's called drawing.").
- Tell the viewer where to look ("Look at Ana's cards at the bottom.").
- **Show → say → show again.** Start the narration after the key animation, then hold the result on screen.
- Pause about 0.9 s after each new idea, with a short gap (0.32 s) between sentences.
- Voice: Kokoro TTS, `af_heart`, speed **0.9**, one sentence voiced at a time. Older robotic TTS (Piper) was rejected.
- Speak numbers that come from the engine. Never hand-type point values.

**Visuals**
- Introduce one thing at a time. Build the table piece by piece with fades instead of showing everything at once.
- Zoom the camera on the part being explained. Draw at 2× so zooms stay sharp.
- Captions, arrows, spotlights and the score bar are drawn **after** the camera crop, so they stay large at any zoom.
  - Put each new idea on screen as a big key-word caption.
  - Place it at the top, middle or bottom so it doesn't cover what's being explained.
- Keep it lively: animate pieces moving, add point pop-ups ("+6"), small sound effects, quiet ambient music ducked under the voice, and a friendly tone without talking down.
- Every episode gets an `.srt` with one cue per sentence.

**Sample game**
- A seeded AI game. Explain the big moments; fast-forward routine turns.
- One stone per sentence. Say what happens to stones that fit nowhere.

## 5. Printable colour manual rules

- A4 with mirrored margins for double-sided printing (inner ≥ 19 mm, outer ≥ 14 mm), and an even page count.
- White pages with light tinted panels. It must still read in black and white.
- Page order:
  1. cover
  2. goal/components/glossary
  3. setup with a numbered table picture
  4. turn flow
  5. cards
  6. scoring elements with example boards and tables
  7. special pieces
  8. end/tie/FAQ
  9. score sheet
  10. quick-reference back page
- Include one worked scoring example whose total matches the engine.
- The build script warns when content overflows a page. Ship with no warnings.

## 6. HTML pages rules

- One self-contained file: inline CSS/JS, no external assets except Google Fonts.
- Use colour tokens on `:root` with dark-mode variants. Works at 390 px wide with no sideways scroll, and prints cleanly.
- **Scenarios page:** puzzles from easy to hard. Each has:
  - a diagram
  - "Your question" with A–D choices
  - a `<details>` answer with the point maths for every option, the rule it teaches, and a manual section reference
- **Arcade trainer:**
  - Real interaction: tap or drag pieces, with illegal moves rejected and a one-line reason.
  - Stages with 1–3 stars against the brute-force optimum, plus a "Rule learned" card and a replay of the best line.
  - A quick-fire mode with timer, lives and streaks.
  - Web Audio sounds with mute, `prefers-reduced-motion`, and `localStorage` wrapped in try/catch.
  - The JS port of the scoring must match `engine.py` on hundreds of random boards.

## 7. Verification checklist (before every commit)

- [ ] `python3 -m pytest` passes.
- [ ] Every point total in the docs, HTML and narration is checked against the engine.
- [ ] Videos:
  - [ ] Look at frames from each episode for overlapping or cut-off text.
  - [ ] Read each `.srt` start to finish as a beginner.
- [ ] PDFs: render each page (`pdftoppm -r 60`) and look at every page.
- [ ] HTML:
  - [ ] Take Playwright screenshots at 1280 px and 390 px, in light and dark.
  - [ ] Check there are no console errors.
  - [ ] Print once to PDF.
- [ ] Grep for retired wording after a rules correction (e.g. `grep -ri "clear spirit"`).

## 8. Environment and tooling

- `tools/setup_env.sh` installs `kokoro-onnx==0.6.1` and downloads the voice model into `tools/voices/`. The model files are git-ignored.
- Network hosts needed: `github.com` and `release-assets.githubusercontent.com`.
- Also needed: ffmpeg, pandoc, Chromium/Playwright (Node `playwright`), Pillow and numpy.
- Building the full video series takes about 25 minutes. Run it in the background. TTS clips are cached in the work dir (`SOTW_WORK`).
- Work on a feature branch and commit generated outputs (PDF, MP4, SRT, HTML) together with the scripts that make them.

## 9. Working with AI agents on this repo

- Delegate big independent pieces to subagents in parallel: colour manual, scenarios, arcade, video rewrite, code review, unit tests.
  - Use a fast model for routine work, and the strongest model where rules accuracy or design quality matters.
- Give each agent:
  - the source-of-truth files
  - the files it must not touch
  - "don't commit"
  - a requirement to verify its numbers with the engine and look at its own renders before reporting
- Review agents' output visually and spot-check the maths before committing.
