/* Chapter 2 (bridge + Score better puzzles), Chapter 3 (Quick-fire), home map and start-up. */
(function () {
  "use strict";
  var E = window.AzulEngine, AZ = window.AZ, $ = AZ.$, $$ = AZ.$$, Snd = AZ.Snd, Save = AZ.Save;
  var PUZZLES = AZ.PUZZLES = JSON.parse(document.getElementById("azul-puzzles").textContent);
  var CONST = { ROW_BONUS: E.ROW_BONUS, COLUMN_BONUS: E.COLUMN_BONUS, COLOUR_BONUS: E.COLOUR_BONUS };
  function fill(t) { return t.replace(/\{(\w+)\}/g, function (m, k) { return CONST[k] !== undefined ? CONST[k] : m; }); }
  function starStr(n, of) { var s = ""; for (var i = 0; i < (of || 3); i++) s += i < n ? "★" : '<span class="off">★</span>'; return '<span class="stars" aria-label="' + n + ' of 3 stars">' + s + "</span>"; }
  AZ.starStr = starStr;

  function lessonsDone() { return AZ.LESSONS.every(function (l) { return Save.data.lessons[l.id]; }); }
  function unlocked() { return Save.data.skipped || lessonsDone(); }

  /* ---------------- bridge ---------------- */
  AZ.openBridge = function () {
    AZ.show("bridge", "Score better");
    Save.data.bridgeSeen = true; Save.save();
    $("#bridge").innerHTML = '<div class="bridge fadein"><div class="shead"><div class="eyebrow">Chapter 2 · Before you start</div><h2>Score better: what’s new</h2></div>' +
      '<div class="card"><p>You know the rules. Now each puzzle shows one moment of a game, and <b>you choose the move</b>.</p><ol>' +
      "<li><b>Points this round</b> means: points from tiles that reach your wall in this round's wall-tiling, minus your floor line. Lines you don't finish score nothing yet.</li>" +
      "<li>The page tries <b>every legal move</b> and finds the best one. The best move earns 3 stars, the second-best result 2 stars, anything else 1 star.</li>" +
      "<li>Stuck? Press <b>Hint</b>. After your move you see the point maths, step by step, for your move and for the best one.</li>" +
      "<li>You can always open <b>Rules</b> at the top, or press <b>Start over</b> to try again.</li></ol>" +
      '<div class="row-btns"><button class="btn primary" type="button" data-go="puzzle:0">Start puzzle 1 &#8594;</button><button class="btn ghost" type="button" data-go="home">Back to the map</button></div></div></div>';
    $("#bridge [data-go]").focus();
  };

  /* ---------------- puzzles ---------------- */
  var P = null;
  function puzzleState(def) {
    return E.makeState({ board: E.makeBoard(def.board), factories: def.factories || [], centre: def.centre || [], centre_marker: def.centre_marker !== false });
  }
  function moveText(m, take) {
    var src = m.source === E.CENTRE ? "the centre" : "factory display " + (m.source + 1);
    var dst = m.line === E.FLOOR ? "the floor line" : "pattern line " + (m.line + 1);
    return "Take " + AZ.plural(take.taken, m.colour + " tile") + " from " + src + " → " + dst;
  }
  function mathsHTML(ev) {
    var L = [], t = ev.take, pl = ev.tiling;
    L.push([moveText(ev.move, t), ""]);
    if (t.took_marker) L.push(["Also take the starting player marker (to the floor line)", ""]);
    if (t.to_floor) L.push([AZ.cap(AZ.plural(t.to_floor, "tile")) + (t.to_floor === 1 ? " spills" : " spill") + " onto the floor line", ""]);
    if (!pl.placements.length) L.push(["No pattern line is complete: no wall tiles this round", "0"]);
    pl.placements.forEach(function (p) {
      L.push(["Pattern line " + (p.row + 1) + ": " + p.colour + " to the wall, " + AZ.detailText(p.detail).replace(/ = \d+$/, ""), "+" + p.points]);
    });
    if (pl.floor_items) L.push(["Floor line: " + AZ.plural(pl.floor_items, "item") + " (" + AZ.floorText(pl.floor_items).replace(/ = \d+$/, "") + ")", AZ.minus(pl.floor_penalty)]);
    else L.push(["Floor line: empty", "0"]);
    if (ev.bonus) {
      var b = ev.bonus;
      L.push(["End bonus: " + AZ.plural(b.rows, "row") + " × " + E.ROW_BONUS + ", " + AZ.plural(b.columns, "column") + " × " + E.COLUMN_BONUS + ", " + AZ.plural(b.colours, "colour") + " × " + E.COLOUR_BONUS, "+" + b.total]);
    }
    return '<div class="maths">' + L.map(function (x) { return '<div class="ln"><span>' + x[0] + "</span><span>" + x[1] + "</span></div>"; }).join("") +
      '<div class="ln tot"><span>' + (ev.bonus ? "Points this round, bonuses included" : "Points this round") + "</span><span>" + AZ.sign(ev.value) + "</span></div></div>";
  }

  AZ.openPuzzle = function (i) {
    if (!unlocked()) { AZ.goHome(); return; }
    var def = PUZZLES[i];
    AZ.show("puzzle", "Puzzle " + (i + 1));
    P = { i: i, def: def, phase: "pick", tries: 0, busy: false };
    var best = Save.data.stars[def.id] || 0;
    $("#puzzle").innerHTML = '<div class="shead"><div class="eyebrow">Score better · Puzzle ' + (i + 1) + " of " + PUZZLES.length + " · " + def.level + "</div><h2>" + def.title + "</h2>" + starStr(best) + "</div>" +
      '<div class="coach" id="pCoach"><div class="say" id="pAsk">' + def.ask + '</div><div class="msg" id="pMsg" role="status" hidden></div><div class="choices" id="pChoices" hidden></div>' +
      '<div class="row-btns"><button class="btn small" type="button" id="pHint">Hint</button><button class="btn small" type="button" id="pReset">Start over</button></div></div>' +
      '<div class="stage" id="pStage"></div><div id="pResult"></div>';
    P.table = new AZ.Table($("#pStage"), null, {});
    if (def.kind === "score") setupScore(); else setupMove();
  };
  function pmsg(t, ok) { var m = $("#pMsg"); if (!t) { m.hidden = true; return; } m.hidden = false; m.className = "msg" + (ok ? " ok" : ""); m.innerHTML = t; }

  function setupMove() {
    var def = P.def;
    P.st0 = puzzleState(def);
    P.solved = E.solve(P.st0, !!def.final);
    P.table.st = E.clone(P.st0); P.table.hand = null; P.table.extraMarks = null;
    P.table.opt = { factories: true, takeable: true, hand: true, who: "Your board" };
    P.phase = "pick"; P.busy = false;
    P.table.render();
    $("#pResult").innerHTML = ""; pmsg(null);
    $("#pAsk").innerHTML = P.def.ask + " <span class=\"why\">Tap a tile to take that colour.</span>";
  }
  async function onMoveAction(a) {
    if (P.busy || P.phase === "done") return;
    var T = P.table;
    if (P.phase === "pick") {
      if (a.kind === "marker") { pmsg("The marker isn't a tile. Tap a tile; the marker comes along when you are first to take from the centre."); Snd.play("wrong"); return; }
      if (a.kind === "emptyfac") { pmsg("That display is empty."); Snd.play("wrong"); return; }
      if (a.kind !== "take") return;
      P.busy = true; pmsg(null);
      P.move = { source: a.src, colour: a.colour };
      T.opt.takeable = false;
      await T.take(a.src, a.colour);
      T.opt.linesActive = true; T.opt.floorActive = true; T.render();
      P.phase = "place"; P.busy = false;
      $("#pAsk").innerHTML = "You hold " + AZ.plural(T.hand.n, a.colour + " tile") + ". Choose a pattern line, or the floor line. <span class=\"why\">(Keys 1–5, F for floor.)</span>";
      return;
    }
    if (P.phase === "place") {
      var line;
      if (a.kind === "floor") line = E.FLOOR;
      else if (a.kind === "line") {
        var why = AZ.placeMsg(T.board(), a.line, T.hand.colour);
        if (why) { pmsg(why); Snd.play("wrong"); if (a.el && !AZ.reduced) { a.el.classList.remove("shake"); void a.el.offsetWidth; a.el.classList.add("shake"); } return; }
        line = a.line;
      } else return;
      P.busy = true; pmsg(null);
      P.move.line = line;
      T.opt.linesActive = false; T.opt.floorActive = false;
      await T.place(line);
      await playTiling(T);
      finishMove(P.move);
    }
  }
  async function playTiling(T) {
    var b = T.board();
    $("#pAsk").innerHTML = "Wall-tiling: complete lines move to the wall, top to bottom.";
    await AZ.sleep(300);
    for (var row = 0; row < 5; row++) {
      if (b.lines[row].count === row + 1) { await T.tileLine(row); await AZ.sleep(350); }
    }
    if (b.floor.length) { await T.payFloor(); await AZ.sleep(300); }
    if (P.def.final) {
      var bd = E.bonusBreakdown(b.wall);
      T.extraMarks = null;
      b.score += bd.total; T.render();
      if (bd.total) { T.pop("score", "+" + bd.total); Snd.play("score", 6); }
      await AZ.sleep(300);
    }
  }
  function finishMove(move) {
    var def = P.def, ev = E.evaluate(P.st0, move, !!def.final), S = P.solved;
    var shown = P.table.board().score - P.st0.boards[0].score;
    if (shown !== ev.value) console.error("animated score differs from engine evaluate", shown, ev.value);
    var rank = S.values.indexOf(ev.value), stars = rank === 0 ? 3 : rank === 1 ? 2 : 1;
    var prev = Save.data.stars[def.id] || 0;
    if (stars > prev) { Save.data.stars[def.id] = stars; Save.save(); }
    P.phase = "done"; P.busy = false; P.lastStars = stars;
    var bestEv = S.bestMoves[0], isBest = ev.value === S.best;
    var diff = S.best - ev.value;
    var verdict = isBest ? "Best possible move!" : AZ.plural(diff, "point") + " short of the best.";
    var others = S.bestMoves.length > 1 ? '<p class="why">' + AZ.plural(S.bestMoves.length, "move") + " share the best result.</p>" : "";
    renderResult(stars, verdict,
      '<div class="cols2"><div><h4>Your move</h4>' + mathsHTML(ev) + "</div>" +
      (isBest ? '<div><h4>Why it works</h4><p>' + def.why + "</p>" + others + "</div>" :
        "<div><h4>Best move</h4>" + mathsHTML(bestEv) + '<p class="why" style="margin-top:8px">' + def.why + "</p></div>") + "</div>", true);
  }
  function renderResult(stars, verdict, body, canWatch) {
    var last = P.i === PUZZLES.length - 1;
    $("#pAsk").innerHTML = P.def.ask;
    $("#pResult").innerHTML = '<div class="card fadein" style="margin-top:14px" id="pCard"><div class="row-btns" style="justify-content:space-between"><span class="verdict">' + verdict + "</span>" + (stars ? starStr(stars) : "") + "</div>" + body +
      '<div class="row-btns">' + (last ? '<button class="btn primary" type="button" data-go="rush">Next: Quick-fire &#8594;</button>' : '<button class="btn primary" type="button" id="pNext">Next puzzle &#8594;</button>') +
      '<button class="btn" type="button" id="pAgain">Try again</button>' + (canWatch ? '<button class="btn" type="button" id="pWatch">Show the best move</button>' : "") +
      '<button class="btn ghost" type="button" data-go="home">Map</button></div></div>';
    $$(".shead .stars", $("#puzzle")).forEach(function (s) { s.outerHTML = starStr(Math.max(stars || 0, Save.data.stars[P.def.id] || 0)); });
    for (var k = 0; k < stars; k++) Snd.play("star", 0.15 * k);
    AZ.say(verdict + (stars ? " " + stars + " stars." : ""));
    var card = $("#pCard");
    if (card && card.scrollIntoView) card.scrollIntoView({ block: "nearest", behavior: AZ.reduced ? "auto" : "smooth" });
    var nb = $("#pNext") || $('#pCard [data-go="rush"]'); if (nb) nb.focus({ preventScroll: true });
  }
  async function watchBest() {
    var S = P.solved, m = S.bestMoves[0].move;
    setupMove();
    P.busy = true; P.phase = "watch";
    $("#pResult").innerHTML = "";
    $("#pAsk").innerHTML = "Watch the best move.";
    await AZ.sleep(500);
    await P.table.take(m.source, m.colour);
    P.table.render(); await AZ.sleep(500);
    await P.table.place(m.line);
    await playTiling(P.table);
    var ev = S.bestMoves[0];
    P.phase = "done"; P.busy = false;
    renderResult(0, "The best move", '<div class="cols2"><div><h4>Best move</h4>' + mathsHTML(ev) + '</div><div><h4>Why it works</h4><p>' + P.def.why + "</p></div></div>", false);
  }

  /* "What does this tile score?" puzzles */
  function setupScore() {
    var def = P.def, b = E.newBoard();
    b.wall = E.wallFromMask(def.wall);
    var r = def.tile[0], c = def.tile[1];
    b.wall[r][c] = E.wallColour(r, c);
    P.detail = E.scoreDetail(b.wall, r, c);
    P.table.st = E.makeState({ board: b }); P.table.opt = { only: "wall", who: "Your wall" }; P.table.extraMarks = { ring: [r, c] };
    P.table.render(); P.tries = 0; P.phase = "pick";
    $("#pResult").innerHTML = ""; pmsg(null);
    var d = P.detail, opts = AZ.numOptions(d.points, [d.h + d.v - 1, d.h, d.v, d.points + 2]);
    var box = $("#pChoices"); box.hidden = false;
    box.innerHTML = opts.map(function (v) { return '<button class="btn" type="button" data-ans="' + v + '">' + v + "</button>"; }).join("");
  }
  function onScoreAnswer(v, el) {
    if (P.phase === "done") return;
    var d = P.detail;
    P.tries++;
    if (v !== d.points) {
      el.classList.add("wrong"); el.disabled = true; Snd.play("wrong");
      pmsg(d.h > 1 && d.v > 1 && v === d.h + d.v - 1 ? "Close. The new tile counts in both lines, so it is counted twice." :
        d.h > 1 && d.v > 1 && (v === d.h || v === d.v) ? "It touches tiles across and down. Count both lines and add them." : "Not quite. Count the unbroken line across, then the unbroken line down.");
      return;
    }
    el.classList.add("right"); Snd.play("ok"); pmsg(null);
    $$("#pChoices .btn").forEach(function (b) { b.disabled = true; });
    P.table.extraMarks = { ring: P.def.tile, h: d.h > 1 ? d.across : [], v: d.v > 1 ? d.down : [] }; P.table.render();
    var stars = P.tries === 1 ? 3 : P.tries === 2 ? 2 : 1;
    if (stars > (Save.data.stars[P.def.id] || 0)) { Save.data.stars[P.def.id] = stars; Save.save(); }
    P.phase = "done"; P.lastStars = stars;
    var body = '<div class="cols2"><div><h4>The maths</h4><div class="maths">' +
      (d.h > 1 ? '<div class="ln"><span>Across: the unbroken line has ' + d.h + " tiles</span><span>+" + d.h + "</span></div>" : '<div class="ln"><span>Across: no neighbour</span><span>0</span></div>') +
      (d.v > 1 ? '<div class="ln"><span>Down: the unbroken line has ' + d.v + " tiles</span><span>+" + d.v + "</span></div>" : '<div class="ln"><span>Down: no neighbour</span><span>0</span></div>') +
      '<div class="ln tot"><span>Points</span><span>' + d.points + '</span></div></div></div><div><h4>Why</h4><p>' + P.def.why + "</p></div></div>";
    renderResult(stars, P.tries === 1 ? "Right first time!" : "Right, on try " + P.tries + ".", body, false);
  }

  $("#puzzle").addEventListener("click", function (ev) {
    if (!P) return;
    var t = ev.target;
    if (t.closest("#pHint")) { pmsg("Hint: " + fill(P.def.hint), true); Snd.play("tap"); return; }
    if (t.closest("#pReset")) { if (P.busy) return; Snd.play("tap"); if (P.def.kind === "score") setupScore(); else setupMove(); return; }
    if (t.closest("#pAgain")) { Snd.play("tap"); if (P.def.kind === "score") setupScore(); else setupMove(); return; }
    if (t.closest("#pNext")) { AZ.openPuzzle(P.i + 1); return; }
    if (t.closest("#pWatch")) { watchBest(); return; }
    var ans = t.closest("[data-ans]");
    if (ans) { onScoreAnswer(+ans.dataset.ans, ans); return; }
    var el = t.closest("[data-act]");
    if (el && $("#pStage").contains(el) && P.def.kind === "move") onMoveAction(AZ.parseAct(el));
  });
  AZ.puzzleKey = function (ev) {
    if ($("#puzzle").hidden || !P || P.def.kind !== "move") return false;
    var k = ev.key, el = null;
    if (/^[1-5]$/.test(k)) el = $('#pStage [data-act="line"][data-line="' + (+k - 1) + '"]');
    else if (k === "f" || k === "F" || k === "0") el = $('#pStage [data-act="floor"]');
    if (el) { onMoveAction(AZ.parseAct(el)); return true; }
    return false;
  };

  /* ---------------- quick-fire ---------------- */
  var R = null, raf = 0;
  var MODES = {
    tile: { name: "Score the tile", blurb: "A tile lands on a wall. How many points does it score?" },
    floor: { name: "Floor penalty", blurb: "Count what a floor line costs, fast." }
  };
  function randInt(n) { return Math.floor(Math.random() * n); }
  function genTile(level) {
    var dens = 0.22 + Math.min(0.4, level * 0.07);
    for (var tries = 0; tries < 200; tries++) {
      var wall = E.emptyWall(), r, c, empties = [];
      for (r = 0; r < 5; r++) for (c = 0; c < 5; c++) if (Math.random() < dens) wall[r][c] = E.wallColour(r, c); else empties.push([r, c]);
      if (!empties.length) continue;
      var near = empties.filter(function (p) { return [[0, 1], [1, 0], [0, -1], [-1, 0]].some(function (d) { var y = p[0] + d[0], x = p[1] + d[1]; return y >= 0 && y < 5 && x >= 0 && x < 5 && wall[y][x]; }); });
      var pool = near.length && Math.random() < 0.85 ? near : empties, pick = pool[randInt(pool.length)];
      var d = E.scoreDetail(wall, pick[0], pick[1]);
      wall[pick[0]][pick[1]] = E.wallColour(pick[0], pick[1]);
      return { kind: "tile", wall: wall, at: pick, detail: d, answer: d.points,
        options: AZ.numOptions(d.points, [d.h + d.v - 1, d.h, d.v, d.points + 1, d.points + 2]) };
    }
  }
  function genFloor(level) {
    var n = 1 + randInt(7), extra = level >= 2 && n === 7 && Math.random() < 0.5 ? 1 + randInt(2) : 0;
    var items = []; for (var i = 0; i < n; i++) items.push(E.COLOURS[randInt(5)]);
    if (Math.random() < 0.35) items[0] = E.MARKER;
    var lost = -E.floorPenalty(n + extra);
    return { kind: "floor", items: items, extra: extra, answer: lost,
      options: AZ.numOptions(lost, [n + extra, -E.floorPenalty(n + 1), -E.floorPenalty(Math.max(1, n - 1)), lost + 1]) };
  }
  function rushMenu() {
    AZ.show("rush", "Quick-fire");
    stopTimer(); R = null;
    $("#rush").innerHTML = '<div class="shead"><div class="eyebrow">Chapter 3 · Quick-fire practice</div><h2>Quick-fire</h2></div>' +
      '<p style="margin-bottom:14px;max-width:62ch">Answer before the bar runs out. You have 3 lives. Every 3 right answers in a row raise your multiplier. Keys 1–4 pick an answer.</p><div class="modes">' +
      Object.keys(MODES).map(function (k) {
        return '<div class="card"><h3>' + MODES[k].name + "</h3><p>" + MODES[k].blurb + '</p><p class="why">Best score: <b>' + (Save.data.rush[k] || 0) + '</b></p><div class="row-btns"><button class="btn primary" type="button" data-rush="' + k + '">Play ' + MODES[k].name + "</button></div></div>";
      }).join("") + "</div>";
  }
  AZ.openRush = function (mode) {
    if (!mode) { rushMenu(); return; }
    AZ.show("rush", MODES[mode].name);
    R = { mode: mode, score: 0, lives: 3, streak: 0, bestStreak: 0, right: 0, q: null, locked: false };
    nextQ();
  };
  function mult() { return 1 + Math.min(3, Math.floor(R.streak / 3)); }
  function nextQ() {
    var level = Math.floor(R.right / 5);
    R.q = R.mode === "tile" ? genTile(level) : genFloor(level);
    R.dur = Math.max(6, 15 - level) * 1000; R.locked = false;
    renderRush();
    startTimer();
  }
  function hud() {
    var hearts = ""; for (var i = 0; i < 3; i++) hearts += i < R.lives ? "♥" : "♡";
    return '<div class="hud"><span class="chip">Score <span id="rScore">' + R.score + '</span></span><span class="chip">Streak ' + R.streak + " · ×" + mult() + '</span><span class="chip lives" aria-label="' + R.lives + ' lives">' + hearts + '</span><span class="chip">Best ' + (Save.data.rush[R.mode] || 0) + "</span></div>";
  }
  function qVisual(q, marks) {
    if (q.kind === "tile") {
      var b = E.newBoard(); b.wall = q.wall;
      return AZ.boardHTML(b, { only: "wall", noTop: true, marks: marks || { ring: q.at } });
    }
    var b2 = E.newBoard(); b2.floor = q.items;
    return AZ.boardHTML(b2, { only: "floor" }) + (q.extra ? '<p class="why">…and ' + AZ.plural(q.extra, "more tile") + " that didn’t fit on the floor line.</p>" : "");
  }
  function renderRush(feedback) {
    var q = R.q;
    $("#rush").innerHTML = '<div class="shead"><div class="eyebrow">Quick-fire · ' + MODES[R.mode].name + '</div></div>' + hud() +
      '<div class="timer" aria-hidden="true"><i id="rBar"></i></div><div class="qbox" id="rBox"><div class="q">' +
      (q.kind === "tile" ? "How many points does the ringed tile score?" : "How many points does this floor line lose?") + '</div><div id="rVis">' + qVisual(q) + '</div>' +
      '<div class="answers">' + q.options.map(function (v, i) { return '<button class="btn" type="button" data-rans="' + v + '"><kbd>' + (i + 1) + "</kbd> " + v + "</button>"; }).join("") + '</div><div id="rFb" role="status"></div></div>';
  }
  function startTimer() {
    stopTimer();
    var t0 = performance.now(), bar = $("#rBar"), lastTick = 0;
    function step(now) {
      if (!R || R.locked) return;
      var f = Math.max(0, 1 - (now - t0) / R.dur);
      if (bar) bar.style.transform = "scaleX(" + f + ")";
      var secs = Math.ceil((R.dur - (now - t0)) / 1000);
      if (secs <= 3 && secs !== lastTick && secs > 0) { lastTick = secs; Snd.play("tick"); }
      if (f <= 0) { answer(null, null); return; }
      raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);
  }
  function stopTimer() { if (raf) cancelAnimationFrame(raf); raf = 0; }
  function explain(q) {
    if (q.kind === "tile") return "It scores " + AZ.detailText(q.detail) + ".";
    var n = Math.min(q.items.length + q.extra, E.FLOOR_SPACES);
    return "Lose " + AZ.floorText(n) + "." + (q.extra ? " Tiles beyond the seventh space cost nothing." : "");
  }
  function answer(v, el) {
    if (!R || R.locked) return;
    R.locked = true; stopTimer();
    var q = R.q, ok = v === q.answer, fb = $("#rFb");
    $$("#rBox [data-rans]").forEach(function (b) { b.disabled = true; if (+b.dataset.rans === q.answer) b.classList.add("right"); });
    if (q.kind === "tile") { var d = q.detail; $("#rVis").innerHTML = qVisual(q, { ring: q.at, h: d.h > 1 ? d.across : [], v: d.v > 1 ? d.down : [] }); }
    if (ok) {
      var gain = 10 * mult();
      R.score += gain; R.streak++; R.right++; R.bestStreak = Math.max(R.bestStreak, R.streak);
      fb.innerHTML = '<p class="msg ok">Right! +' + gain + ". " + explain(q) + "</p>";
      Snd.play("ok");
      if (el) { var r = el.getBoundingClientRect(), p = document.createElement("div"); p.className = "pop"; p.textContent = "+" + gain; p.style.left = (r.left + r.width / 2) + "px"; p.style.top = r.top + "px"; document.body.appendChild(p); setTimeout(function () { p.remove(); }, 1250); }
    } else {
      R.lives--; R.streak = 0;
      if (el) el.classList.add("wrong");
      fb.innerHTML = '<p class="msg">' + (v === null ? "Time's up. " : "Not quite. ") + "The answer is " + q.answer + ". " + explain(q) + "</p>";
      Snd.play("wrong");
    }
    var chips = $(".hud", $("#rush")); if (chips) chips.outerHTML = hud();
    var wait = ok ? 900 : 2200;
    R.timeout = setTimeout(function () { if (!R) return; if (R.lives <= 0) gameOver(); else nextQ(); }, AZ.reduced ? Math.min(wait, 1200) : wait);
  }
  function gameOver() {
    var best = Save.data.rush[R.mode] || 0, isNew = R.score > best;
    if (isNew) { Save.data.rush[R.mode] = R.score; Save.save(); }
    Snd.play(isNew ? "win" : "over");
    var other = R.mode === "tile" ? "floor" : "tile";
    $("#rush").innerHTML = '<div class="shead"><div class="eyebrow">Quick-fire · ' + MODES[R.mode].name + '</div><h2>Game over</h2></div><div class="card fadein" style="max-width:560px"><div class="verdict">' +
      (isNew ? "New best score!" : "Well played.") + '</div><div class="maths"><div class="ln"><span>Score</span><span>' + R.score + '</span></div><div class="ln"><span>Right answers</span><span>' + R.right +
      '</span></div><div class="ln"><span>Longest streak</span><span>' + R.bestStreak + '</span></div><div class="ln"><span>Best score</span><span>' + Math.max(best, R.score) + "</span></div></div>" +
      '<div class="row-btns"><button class="btn primary" type="button" data-rush="' + R.mode + '" id="rAgain">Play again</button><button class="btn" type="button" data-rush="' + other + '">Try ' + MODES[other].name + '</button><button class="btn ghost" type="button" data-go="home">Map</button></div></div>';
    $("#rAgain").focus();
    R = null;
  }
  $("#rush").addEventListener("click", function (ev) {
    var t = ev.target, m = t.closest("[data-rush]");
    if (m) { Snd.ensure(); AZ.openRush(m.dataset.rush); return; }
    var a = t.closest("[data-rans]");
    if (a && R) answer(+a.dataset.rans, a);
  });
  AZ.rushKey = function (ev) {
    if ($("#rush").hidden || !R || R.locked) return false;
    if (/^[1-4]$/.test(ev.key)) { var b = $$("#rBox [data-rans]")[+ev.key - 1]; if (b) { answer(+b.dataset.rans, b); return true; } }
    return false;
  };
  AZ.rushState = function () { return R; };
  AZ.leaveHooks.push(function (to) { if (to !== "rush") { stopTimer(); if (R && R.timeout) clearTimeout(R.timeout); R = null; } });

  /* ---------------- home / map ---------------- */
  function heroWall() {
    var h = "", filled = ["XX.X.", ".XXXX", "X.XX.", "XX..X", ".X.XX"];
    for (var r = 0; r < 5; r++) for (var c = 0; c < 5; c++) {
      var col = E.wallColour(r, c);
      h += AZ.tileHTML(col, { cls: filled[r][c] === "X" ? "" : "ghost", label: false }).replace('class="tile', 'style="animation-delay:' + ((r + c) * 50) + 'ms" class="tile');
    }
    return '<div class="hero-tiles" role="img" aria-label="A player wall: 25 spaces in five colours, some tiled">' + h + "</div>";
  }
  AZ.goHome = function () {
    AZ.show("home", "");
    var L = AZ.LESSONS, done = L.filter(function (l) { return Save.data.lessons[l.id]; }).length;
    var nextL = L.findIndex(function (l) { return !Save.data.lessons[l.id]; });
    var stars = PUZZLES.reduce(function (n, p) { return n + (Save.data.stars[p.id] || 0); }, 0);
    var open = unlocked();
    var nextP = PUZZLES.findIndex(function (p) { return !Save.data.stars[p.id]; });
    var primary = nextL >= 0 ? '<button class="btn primary" type="button" data-go="lesson:' + nextL + '">' + (done ? "Continue: lesson " + (nextL + 1) : "Start learning") + " &#8594;</button>"
      : '<button class="btn primary" type="button" data-go="' + (nextP >= 0 ? "puzzle:" + nextP : "rush") + '">' + (nextP >= 0 ? "Continue: puzzle " + (nextP + 1) : "Play Quick-fire") + " &#8594;</button>";
    $("#home").innerHTML = '<div class="hero"><div><h1>Azul <span>Tile School</span></h1><p class="lede">Learn the tile-laying game Azul from zero. Short lessons where you move the tiles yourself, then puzzles that make you score better.</p><div class="row-btns">' +
      primary + (open && nextL >= 0 || Save.data.skipped ? "" : '<button class="btn" type="button" data-go="skip">Skip, I know the rules</button>') + '<button class="btn ghost" type="button" data-go="rules">Read the rules</button></div></div>' + heroWall() + "</div>" +
      '<div class="map">' +
      '<div class="chapter"><div class="chhead"><span class="eyebrow">Chapter 1</span><h2>Learn the game</h2><p>' + L.length + " short lessons. One idea each, and you do it.</p>" +
      '<div class="meter" aria-label="' + done + " of " + L.length + ' lessons done"><i style="width:' + (100 * done / L.length) + '%"></i></div></div><div class="nodes">' +
      L.map(function (l, i) {
        var d = Save.data.lessons[l.id];
        return '<button class="node' + (d ? " done" : i === nextL ? " next" : "") + '" type="button" data-go="lesson:' + i + '"><span class="n">' + (d ? "✓" : i + 1) + '</span><span class="nm">' + l.title + '</span><span class="ds">' + l.blurb + "</span></button>";
      }).join("") + "</div></div>" +
      '<div class="chapter' + (open ? "" : " locked") + '"><div class="chhead"><span class="eyebrow">Chapter 2</span><h2>Score better</h2><p>' + PUZZLES.length + " puzzles, easy to hard. Stars: " + stars + " of " + PUZZLES.length * 3 + ".</p></div>" +
      (open ? "" : '<div class="locknote">Finish the lessons first, or skip them if you already know how to play.<button class="btn small" type="button" data-go="skip">Skip, I know the rules</button></div>') +
      '<div class="nodes"><button class="node" type="button" data-go="bridge"' + (open ? "" : " disabled") + '><span class="n">?</span><span class="nm">What’s new</span><span class="ds">How puzzles, hints and stars work.</span></button>' +
      PUZZLES.map(function (p, i) {
        var s = Save.data.stars[p.id] || 0;
        return '<button class="node' + (s ? " done" : "") + '" type="button" data-go="puzzle:' + i + '"' + (open ? "" : " disabled") + '><span class="n">' + (i + 1) + '</span><span class="nm">' + p.title + '</span><span class="ds">' + p.level + '</span><span class="st">' + (s ? starStr(s).replace('class="stars"', 'class="stars" style="font-size:15px"') : "") + "</span></button>";
      }).join("") + "</div></div>" +
      '<div class="chapter' + (open ? "" : " locked") + '"><div class="chhead"><span class="eyebrow">Chapter 3</span><h2>Quick-fire</h2><p>Speed rounds with a timer, 3 lives and streaks.</p></div><div class="nodes">' +
      Object.keys(MODES).map(function (k, i) {
        return '<button class="node" type="button" data-go="rush:' + k + '"' + (open ? "" : " disabled") + '><span class="n">' + ["⌖", "↓"][i] + '</span><span class="nm">' + MODES[k].name + '</span><span class="ds">' + MODES[k].blurb + '</span><span class="st" style="color:var(--ink-2)">Best ' + (Save.data.rush[k] || 0) + "</span></button>";
      }).join("") + "</div></div></div>" +
      '<div class="foot"><p>An unofficial learning page for Azul (Michael Kiesling, Plan B Games / Next Move). The tile designs here are our own. Every point value on this page is computed by a rules engine that matches the repo’s Python engine.</p>' +
      '<div class="row-btns" id="resetRow"><button class="btn small ghost" type="button" id="resetBtn">Reset my progress</button></div></div>';
  };
  function resetAsk() {
    $("#resetRow").innerHTML = '<span>Clear lessons, stars and best scores on this device?</span><button class="btn small" type="button" id="resetYes">Yes, reset</button><button class="btn small ghost" type="button" id="resetNo">Keep them</button>';
    $("#resetNo").focus();
  }

  function go(target) {
    Snd.ensure();
    var p = target.split(":");
    if (p[0] === "home") AZ.goHome();
    else if (p[0] === "lesson") AZ.openLesson(+p[1]);
    else if (p[0] === "puzzle") AZ.openPuzzle(+p[1]);
    else if (p[0] === "bridge") AZ.openBridge();
    else if (p[0] === "rush") AZ.openRush(p[1]);
    else if (p[0] === "rules") AZ.openRules();
    else if (p[0] === "skip") { Save.data.skipped = true; Save.save(); AZ.openBridge(); }
  }
  document.addEventListener("click", function (ev) {
    var t = ev.target;
    var g = t.closest("[data-go]");
    if (g && !g.disabled) { Snd.play("tap"); go(g.dataset.go); return; }
    if (t.closest("#resetBtn")) { resetAsk(); return; }
    if (t.closest("#resetYes")) { Save.reset(); AZ.goHome(); return; }
    if (t.closest("#resetNo")) { AZ.goHome(); return; }
  });

  /* ---------------- start-up ---------------- */
  $("#homeBtn").addEventListener("click", function () { Snd.play("tap"); AZ.goHome(); });
  $("#rulesBtn").addEventListener("click", function () { AZ.openRules(); });
  $("#muteBtn").addEventListener("click", function () { Save.data.muted = !Save.data.muted; Save.save(); AZ.syncMute(); if (!Save.data.muted) { Snd.ensure(); Snd.play("ok"); } });
  $("#rules").addEventListener("click", function (ev) { if (ev.target.id === "rules" || ev.target.closest("[data-close]")) AZ.closeRules(); });
  document.addEventListener("pointerdown", function () { Snd.ensure(); }, { once: true });
  document.addEventListener("keydown", function (ev) {
    if (!$("#rules").hidden) { if (ev.key === "Escape") { AZ.closeRules(); ev.preventDefault(); } return; }
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
    var tag = (ev.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea") return;
    if (ev.key === "Enter" && tag !== "button") { var n = $("#cNext"); if (n && !$("#lesson").hidden) { n.click(); ev.preventDefault(); return; } }
    if (!$("#lesson").hidden && AZ.lessonKey(ev)) { ev.preventDefault(); return; }
    if (AZ.puzzleKey(ev)) { ev.preventDefault(); return; }
    if (AZ.rushKey(ev)) { ev.preventDefault(); return; }
  });
  AZ.syncMute();
  AZ.goHome();
})();
