// Verify the JS engine (from learn.html or engine.js) against cases made by the Python engine.
// usage: node verify.js <learn.html|engine.js> <cases.json>
const fs = require("fs");
const src = fs.readFileSync(process.argv[2], "utf8");
let code = src;
if (process.argv[2].endsWith(".html")) {
  const m = src.match(/<script id="azul-engine">([\s\S]*?)<\/script>/);
  if (!m) throw new Error("engine script not found");
  code = m[1];
}
new Function(code)();
const E = globalThis.AzulEngine;
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const canon = (x) => JSON.stringify(x, (k, v) => (v && typeof v === "object" && !Array.isArray(v) ? Object.keys(v).sort().reduce((o, kk) => ((o[kk] = v[kk]), o), {}) : v));
const mv = (a) => ({ source: a[0], colour: a[1], line: a[2] });
const counts = {};
let fail = 0;
function check(kind, ok, msg) {
  counts[kind] = (counts[kind] || 0) + 1;
  if (!ok) { fail++; if (fail < 15) console.log("FAIL", kind, msg); }
}
cases.score.forEach((c) => check("score_placement", E.scorePlacement(c.wall, c.r, c.c) === c.pts, canon(c)));
cases.floor.forEach((c) => check("floor_penalty", E.floorPenalty(c.n) === c.pen, canon(c)));
cases.bonus.forEach((c) => {
  const bd = E.bonusBreakdown(c.wall);
  check("bonus_breakdown", canon(bd) === canon(c.bd), canon(c));
  const parts = E.bonusParts(c.wall);
  check("bonus_parts", parts.rows.length === c.bd.rows && parts.columns.length === c.bd.columns && parts.colours.length === c.bd.colours, canon(c));
});
cases.reason.forEach((c) => {
  const ok = c.can.every((row, l) => row.every((v, i) => E.canPlace(c.board, l, E.COLOURS[i]) === v));
  check("can_place", ok, canon(c.board));
});
cases.moves.forEach((c) => {
  const legal = E.legalMoves(c.state).map((m) => JSON.stringify([m.source, m.colour, m.line])).sort();
  check("legal_moves", canon(legal) === canon(c.legal.map((x) => JSON.stringify(JSON.parse(x))).sort()), "legal " + legal.length + " vs " + c.legal.length);
  const s = E.clone(c.state);
  const info = E.applyMove(s, mv(c.move));
  const sub = { taken: info.taken, pushed: info.pushed, placed: info.placed, to_floor: info.to_floor, to_lid: info.to_lid, took_marker: info.took_marker };
  check("apply_move_info", canon(sub) === canon(c.info), canon(sub) + " vs " + canon(c.info));
  check("apply_move_state", canon(s) === canon(c.after), "state differs");
});
cases.tiling.forEach((c) => {
  const s = E.clone(c.state);
  const res = E.tileWalls(s);
  const slim = res.map((r) => Object.assign({}, r, { placements: r.placements.map((p) => ({ row: p.row, colour: p.colour, col: p.col, points: p.points })) }));
  check("tile_walls_results", canon(slim) === canon(c.results), canon(slim).slice(0, 300) + "\n vs " + canon(c.results).slice(0, 300));
  check("tile_walls_state", canon(s) === canon(c.after), "state differs");
});
cases.evaluate.forEach((c) => {
  const e = E.evaluate(c.state, mv(c.move), c.final);
  check("evaluate (puzzle value)", e.value === c.value, e.value + " vs " + c.value);
});
console.log(counts);
const total = Object.values(counts).reduce((a, b) => a + b, 0);
console.log(fail ? `${fail} FAILURES of ${total}` : `ALL ${total} CHECKS PASS`);
process.exit(fail ? 1 : 0);
