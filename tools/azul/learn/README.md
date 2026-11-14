# Azul learning page source

`docs/azul/learn.html` is assembled from these pieces. Edit the parts here, then run `bash tools/azul/learn/build.sh`; don't edit the HTML directly.

- `parts/`: `head.html` (styles), `body.html`, `engine.js` (JS port of `tools/azul/engine.py`), `core.js`, `lessons.js`, `play.js`
- `puzzles.json`: Chapter 2 puzzle positions
- Checks:
  - `gen_cases.py` + `verify.js`: the JS engine port against the Python engine
  - `design.py`: the puzzle optimums
  - `test.js`: Playwright play-through
  - These may need path tweaks before running.
