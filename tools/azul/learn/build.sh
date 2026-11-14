#!/bin/bash
# Assemble docs/azul/learn.html from parts.
set -e
D=$(dirname "$0")
OUT="$D/../../../docs/azul/learn.html"
{
  cat "$D/parts/head.html"
  cat "$D/parts/body.html"
  echo '<script id="azul-engine">'; cat "$D/parts/engine.js"; echo '</script>'
  echo '<script id="azul-puzzles" type="application/json">'; python3 -c "import json,sys; print(json.dumps(json.load(open('$D/puzzles.json')), ensure_ascii=False))"; echo '</script>'
  echo '<script>'; cat "$D/parts/core.js"; echo '</script>'
  echo '<script>'; cat "$D/parts/lessons.js"; echo '</script>'
  echo '<script>'; cat "$D/parts/play.js"; echo '</script>'
} > "$OUT"
wc -c "$OUT"
