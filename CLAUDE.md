# Boardgames repo

English manuals (Markdown, PDF, colour PDF), HTML practice pages and beginner video series for board games.

Before adding or changing anything for a game, read **docs/PLAYBOOK.md** and follow it. It covers folder layout, order of work, wording rules, video style and the verification checklist. Spirits of the Wild (`docs/spirits-of-the-wild/`, `tools/sotw/`) is the reference implementation.

- Tests: `python3 -m pytest`
- Never hand-type point values; derive and check them with the game's `engine.py`.
- When a rules wording changes, rebuild every output that quotes it.
