/* Azul rules engine: a JS port of tools/azul/engine.py (coloured wall only).
   State keys use the Python names so the two can be compared directly.
   Checked against the Python engine by tools in the build scratchpad (verify.js). */
(function (root) {
  "use strict";
  var COLOURS = ["blue", "yellow", "red", "black", "white"];
  var LETTERS = { blue: "B", yellow: "Y", red: "R", black: "K", white: "W" };
  var SIZE = 5, TILES_PER_FACTORY = 4, TILES_PER_COLOUR = 20;
  var FACTORIES = { 2: 5, 3: 7, 4: 9 };
  var FLOOR_VALUES = [-1, -1, -2, -2, -2, -3, -3];
  var FLOOR_SPACES = FLOOR_VALUES.length;
  var ROW_BONUS = 2, COLUMN_BONUS = 7, COLOUR_BONUS = 10;
  var MARKER = "marker", CENTRE = "centre", FLOOR = "floor";

  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function wallColour(r, c) { return COLOURS[(((c - r) % SIZE) + SIZE) % SIZE]; }
  function wallColumn(r, colour) { return (COLOURS.indexOf(colour) + r) % SIZE; }
  function emptyWall() { var w = []; for (var r = 0; r < SIZE; r++) w.push([null, null, null, null, null]); return w; }
  function filled(wall, r, c, here) {
    if (r === here[0] && c === here[1]) return true;
    return r >= 0 && r < SIZE && c >= 0 && c < SIZE && wall[r][c] !== null && wall[r][c] !== undefined;
  }

  /* Points for a tile at (row, col), with the runs it makes.
     across / down: the cells of the unbroken line through the tile (length 1 = no neighbour that way). */
  function scoreDetail(wall, row, col) {
    var here = [row, col], across = [[row, col]], down = [[row, col]], c, r;
    for (c = col - 1; filled(wall, row, c, here); c--) across.unshift([row, c]);
    for (c = col + 1; filled(wall, row, c, here); c++) across.push([row, c]);
    for (r = row - 1; filled(wall, r, col, here); r--) down.unshift([r, col]);
    for (r = row + 1; filled(wall, r, col, here); r++) down.push([r, col]);
    var h = across.length, v = down.length;
    var pts = (h === 1 && v === 1) ? 1 : (h > 1 ? h : 0) + (v > 1 ? v : 0);
    return { points: pts, h: h, v: v, across: across, down: down, lone: h === 1 && v === 1 };
  }
  function scorePlacement(wall, row, col) { return scoreDetail(wall, row, col).points; }

  function floorPenalty(n) {
    var k = Math.max(0, Math.min(n, FLOOR_SPACES)), s = 0;
    for (var i = 0; i < k; i++) s += FLOOR_VALUES[i];
    return s;
  }
  function completeRows(wall) {
    var n = 0; for (var r = 0; r < SIZE; r++) if (wall[r].every(function (t) { return t !== null; })) n++; return n;
  }
  function completeColumns(wall) {
    var n = 0; for (var c = 0; c < SIZE; c++) { var ok = true; for (var r = 0; r < SIZE; r++) if (wall[r][c] === null) ok = false; if (ok) n++; } return n;
  }
  function completeColours(wall) {
    var cnt = {}; wall.forEach(function (row) { row.forEach(function (t) { if (t !== null) cnt[t] = (cnt[t] || 0) + 1; }); });
    return COLOURS.filter(function (c) { return cnt[c] === SIZE; }).length;
  }
  function bonusBreakdown(wall) {
    var rows = completeRows(wall), cols = completeColumns(wall), colours = completeColours(wall);
    return { rows: rows, columns: cols, colours: colours, row_points: rows * ROW_BONUS,
      column_points: cols * COLUMN_BONUS, colour_points: colours * COLOUR_BONUS,
      total: rows * ROW_BONUS + cols * COLUMN_BONUS + colours * COLOUR_BONUS };
  }
  function endBonus(wall) { return bonusBreakdown(wall).total; }
  /* Which rows, columns and colours are complete (for pointing at them). */
  function bonusParts(wall) {
    var out = { rows: [], columns: [], colours: [] }, r, c;
    for (r = 0; r < SIZE; r++) if (wall[r].every(function (t) { return t !== null; })) out.rows.push(r);
    for (c = 0; c < SIZE; c++) { var ok = true; for (r = 0; r < SIZE; r++) if (wall[r][c] === null) ok = false; if (ok) out.columns.push(c); }
    COLOURS.forEach(function (col) { var n = 0; for (r = 0; r < SIZE; r++) if (wall[r][wallColumn(r, col)] === col) n++; if (n === SIZE) out.colours.push(col); });
    return out;
  }
  function wallFromRows(rows) {
    var w = emptyWall(), rev = {};
    COLOURS.forEach(function (c) { rev[LETTERS[c]] = c; });
    rows.forEach(function (s, r) { for (var c = 0; c < s.length; c++) if (s[c] !== ".") w[r][c] = rev[s[c]] || wallColour(r, c); });
    return w;
  }
  /* Rows like "..X.." : any non-dot puts the printed colour there. */
  function wallFromMask(rows) {
    var w = emptyWall();
    rows.forEach(function (s, r) { for (var c = 0; c < s.length; c++) if (s[c] !== ".") w[r][c] = wallColour(r, c); });
    return w;
  }
  function wallToRows(wall) { return wall.map(function (row) { return row.map(function (t) { return t ? LETTERS[t] : "."; }).join(""); }); }

  function newBoard() {
    var lines = []; for (var i = 0; i < SIZE; i++) lines.push({ colour: null, count: 0 });
    return { score: 0, lines: lines, wall: emptyWall(), floor: [] };
  }
  function lineCapacity(line) { return line + 1; }
  function canPlace(board, line, colour) { return placeReason(board, line, colour) === null; }
  /* null when allowed, otherwise a code the page turns into words. */
  function placeReason(board, line, colour) {
    var pl = board.lines[line];
    if (pl.count >= lineCapacity(line)) return "full";
    if (pl.colour !== null && pl.colour !== colour) return "other";
    if (board.wall[line].indexOf(colour) >= 0) return "wall";
    return null;
  }

  function offerOver(state) {
    return !state.centre.length && !state.factories.some(function (f) { return f.length; });
  }
  function legalMoves(state) {
    var board = state.boards[state.current], sources = [], moves = [];
    state.factories.forEach(function (f, i) { if (f.length) sources.push([i, f]); });
    if (state.centre.length) sources.push([CENTRE, state.centre]);
    sources.forEach(function (s) {
      COLOURS.forEach(function (colour) {
        if (s[1].indexOf(colour) < 0) return;
        for (var line = 0; line < SIZE; line++) if (canPlace(board, line, colour)) moves.push({ source: s[0], colour: colour, line: line });
        moves.push({ source: s[0], colour: colour, line: FLOOR });
      });
    });
    return moves;
  }
  function sameMove(a, b) { return a.source === b.source && a.colour === b.colour && a.line === b.line; }

  function toFloor(state, board, item) {
    if (board.floor.length < FLOOR_SPACES) { board.floor.push(item); return "floor"; }
    if (item !== MARKER) state.lid.push(item);
    return "lid";
  }
  /* First half of a turn: take every tile of one colour from one source.
     Factory leftovers go to the centre; the first take from the centre also takes the marker (onto the floor line). */
  function takeTiles(state, source, colour) {
    var p = state.current, board = state.boards[p], taken, pushed = [];
    var info = { player: p, took_marker: false, marker_beside_board: false };
    if (source === CENTRE) {
      taken = state.centre.filter(function (t) { return t === colour; });
      state.centre = state.centre.filter(function (t) { return t !== colour; });
      if (state.centre_marker) {
        state.centre_marker = false;
        state.marker_holder = p;
        info.took_marker = true;
        if (toFloor(state, board, MARKER) === "lid") info.marker_beside_board = true;
      }
    } else {
      var f = state.factories[source];
      taken = f.filter(function (t) { return t === colour; });
      pushed = f.filter(function (t) { return t !== colour; });
      state.centre = state.centre.concat(pushed);
      state.factories[source] = [];
    }
    info.taken = taken.length; info.pushed = pushed.length; info.pushed_colours = pushed;
    return info;
  }
  /* Second half: n tiles of colour into pattern line `line` (0-4) or FLOOR. */
  function placeTiles(state, colour, n, line) {
    var board = state.boards[state.current], placed = 0, toF = 0, toL = 0;
    if (line !== FLOOR) {
      var pl = board.lines[line];
      placed = Math.min(n, lineCapacity(line) - pl.count);
      pl.colour = colour;
      pl.count += placed;
    }
    for (var i = placed; i < n; i++) { if (toFloor(state, board, colour) === "floor") toF++; else toL++; }
    return { placed: placed, to_floor: toF, to_lid: toL };
  }
  function endTurn(state) {
    if (offerOver(state)) state.phase = "tiling";
    else state.current = (state.current + 1) % state.n;
  }
  function applyMove(state, move) {
    if (state.phase !== "offer") throw new Error("not in the factory offer phase");
    if (!legalMoves(state).some(function (m) { return sameMove(m, move); })) throw new Error("illegal move");
    var info = takeTiles(state, move.source, move.colour);
    var pl = placeTiles(state, move.colour, info.taken, move.line);
    info.placed = pl.placed; info.to_floor = pl.to_floor; info.to_lid = pl.to_lid; info.move = move;
    endTurn(state);
    return info;
  }

  /* Phase B for one player (coloured wall). Placements carry their scoreDetail. */
  function tileWall(state, p) {
    var board = state.boards[p], wall = board.wall, before = board.score, placements = [];
    for (var row = 0; row < SIZE; row++) {
      var pl = board.lines[row];
      if (pl.count !== lineCapacity(row)) continue;
      var colour = pl.colour, col = wallColumn(row, colour);
      if (wall[row][col] !== null) throw new Error("wall space taken");
      wall[row][col] = colour;
      var d = scoreDetail(wall, row, col);
      board.score += d.points;
      for (var i = 0; i < pl.count - 1; i++) state.lid.push(colour);
      placements.push({ row: row, colour: colour, col: col, points: d.points, detail: d, to_lid: pl.count - 1 });
      pl.colour = null; pl.count = 0;
    }
    var items = board.floor.slice(), pen = floorPenalty(items.length), afterWall = board.score;
    board.score = Math.max(0, board.score + pen);
    items.forEach(function (t) { if (t !== MARKER) state.lid.push(t); });
    board.floor = [];
    return { player: p, placements: placements, floor_items: items.length, floor_marker: items.indexOf(MARKER) >= 0,
      floor_penalty: pen, score_before: before, score_after_wall: afterWall, score: board.score };
  }
  function tileWalls(state) {
    if (state.phase !== "tiling") throw new Error("not in the wall-tiling phase");
    var res = []; for (var p = 0; p < state.n; p++) res.push(tileWall(state, p));
    if (state.marker_holder === null) { state.centre_marker = false; state.marker_holder = state.start_player; }
    if (state.boards.some(function (b) { return completeRows(b.wall) > 0; })) finishGame(state);
    else state.phase = "prepare";
    return res;
  }
  function finishGame(state) {
    state.bonuses = [];
    state.boards.forEach(function (b) { var bd = bonusBreakdown(b.wall); b.score += bd.total; state.bonuses.push(bd); });
    state.phase = "over"; state.game_over = true;
  }

  /* A small table for lessons and puzzles: one player (or more), given sources. */
  function makeState(o) {
    o = o || {};
    var boards = o.boards || [o.board || newBoard()];
    return { n: boards.length, factories: clone(o.factories || []), centre: clone(o.centre || []),
      centre_marker: o.centre_marker !== undefined ? o.centre_marker : true, marker_holder: null,
      start_player: 0, current: 0, boards: clone(boards), lid: clone(o.lid || []), bag: clone(o.bag || []),
      phase: "offer", game_over: false, round: 1 };
  }
  function makeBoard(o) {
    var b = newBoard();
    if (o.score) b.score = o.score;
    if (o.wall) b.wall = wallFromMask(o.wall);
    (o.lines || []).forEach(function (l, i) { if (l) { b.lines[i].colour = l[0]; b.lines[i].count = l[1]; } });
    if (o.floor) b.floor = o.floor.slice();
    return b;
  }

  /* Points this round for one move: apply it, finish the offer, tile the wall (+ end bonuses if final). */
  function evaluate(state0, move, final) {
    var s = clone(state0), p = state0.current;
    var take = applyMove(s, move);
    var before = state0.boards[p].score;
    var board = s.boards[p];
    s.phase = "tiling";
    var res = tileWall(s, p);
    var bonus = null;
    if (final) { bonus = bonusBreakdown(board.wall); board.score += bonus.total; }
    return { move: move, value: board.score - before, take: take, tiling: res, bonus: bonus, after: s };
  }
  function solve(state0, final) {
    var all = legalMoves(state0).map(function (m) { return evaluate(state0, m, final); });
    var best = Math.max.apply(null, all.map(function (e) { return e.value; }));
    var values = all.map(function (e) { return e.value; }).filter(function (v, i, a) { return a.indexOf(v) === i; }).sort(function (a, b) { return b - a; });
    return { all: all, best: best, values: values, bestMoves: all.filter(function (e) { return e.value === best; }) };
  }

  root.AzulEngine = {
    COLOURS: COLOURS, LETTERS: LETTERS, SIZE: SIZE, TILES_PER_FACTORY: TILES_PER_FACTORY, TILES_PER_COLOUR: TILES_PER_COLOUR,
    FACTORIES: FACTORIES, FLOOR_VALUES: FLOOR_VALUES, FLOOR_SPACES: FLOOR_SPACES, ROW_BONUS: ROW_BONUS,
    COLUMN_BONUS: COLUMN_BONUS, COLOUR_BONUS: COLOUR_BONUS, MARKER: MARKER, CENTRE: CENTRE, FLOOR: FLOOR,
    clone: clone, wallColour: wallColour, wallColumn: wallColumn, emptyWall: emptyWall, scoreDetail: scoreDetail,
    scorePlacement: scorePlacement, floorPenalty: floorPenalty, completeRows: completeRows, completeColumns: completeColumns,
    completeColours: completeColours, bonusBreakdown: bonusBreakdown, bonusParts: bonusParts, endBonus: endBonus,
    wallFromRows: wallFromRows, wallFromMask: wallFromMask, wallToRows: wallToRows, newBoard: newBoard,
    lineCapacity: lineCapacity, canPlace: canPlace, placeReason: placeReason, offerOver: offerOver, legalMoves: legalMoves,
    sameMove: sameMove, takeTiles: takeTiles, placeTiles: placeTiles, endTurn: endTurn, applyMove: applyMove,
    tileWall: tileWall, tileWalls: tileWalls, finishGame: finishGame, makeState: makeState, makeBoard: makeBoard,
    evaluate: evaluate, solve: solve
  };
})(typeof window !== "undefined" ? window : globalThis);
