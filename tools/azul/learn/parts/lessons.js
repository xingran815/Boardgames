/* Chapter 1: Learn the game. Each lesson is a short script: say, let the player act, check, explain, Remember card. */
(function () {
  "use strict";
  var E = window.AzulEngine, AZ = window.AZ, $ = AZ.$, w = AZ.w, Snd = AZ.Snd, LET = E.LETTERS;
  var F = E.FACTORIES, PER = E.TILES_PER_FACTORY, TOTAL = E.TILES_PER_COLOUR * E.COLOURS.length;

  function shuffled(n) {
    var a = []; for (var i = 0; i < n; i++) a.push(E.COLOURS[i % 5]);
    for (i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }

  /* Phase B for one line, without revealing the points yet (the player predicts them first). */
  AZ.Table.prototype.tileLineQuiet = function (row) {
    var st = this.st, b = this.board(), pl = b.lines[row], colour = pl.colour, n = pl.count;
    var col = E.wallColumn(row, colour), keys = [];
    for (var s = 0; s < n; s++) keys.push("l" + row + "-" + s);
    var rects = this.rects(keys);
    b.wall[row][col] = colour;
    var d = E.scoreDetail(b.wall, row, col);
    for (s = 0; s < n - 1; s++) st.lid.push(colour);
    pl.colour = null; pl.count = 0;
    if (this.opt.supply && this.opt.supply.lid !== undefined) this.opt.supply.lid = st.lid.length;
    this.extraMarks = { ring: [row, col] };
    this.render();
    var moves = [{ from: "l" + row + "-0", to: "w" + row + "-" + col, html: AZ.tileHTML(colour, { label: false }) }];
    for (s = 1; s < n; s++) moves.push({ from: "l" + row + "-" + s, to: "lid", html: AZ.tileHTML(colour, { label: false }) });
    return this.fly(moves, rects).then(function () { return { row: row, col: col, colour: colour, detail: d, points: d.points, to_lid: n - 1 }; });
  };
  AZ.Table.prototype.reveal = function (res) {
    var d = res.detail;
    this.board().score += d.points;
    this.extraMarks = { h: d.h > 1 ? d.across : [], v: d.v > 1 ? d.down : [], pick: d.lone ? [[res.row, res.col]] : [] };
    this.render();
    this.pop("w" + res.row + "-" + res.col, "+" + d.points); Snd.play("score", d.points);
  };
  /* Draw up to `n` tiles from bag (array) onto factory i, with flights from the bag. */
  AZ.Table.prototype.fillFactory = function (i, bag) {
    var f = this.st.factories[i], need = PER - f.length, moves = [], rects = this.rects(["bag"]);
    var start = f.length;
    for (var q = 0; q < need && bag.length; q++) f.push(bag.pop());
    if (this.opt.supply) this.opt.supply.bag = bag.length;
    this.render();
    for (q = start; q < f.length; q++) moves.push({ from: "bag", to: "f" + i + "-" + q, html: AZ.tileHTML(f[q], { label: false }) });
    if (moves.length) Snd.play("clack");
    return this.fly(moves, rects);
  };

  /* ---------------- the lesson runner ---------------- */
  function Runner(idx) {
    this.idx = idx; this.dead = false; this.pending = null; this.nextResolve = null; this.choice = null;
    this.root = $("#lesson");
    var L = LESSONS[idx];
    this.root.innerHTML =
      '<div class="shead"><div class="eyebrow">Learn the game · Lesson ' + (idx + 1) + " of " + LESSONS.length + "</div><h2>" + L.title + '</h2><div class="dots" aria-hidden="true">' +
      LESSONS.map(function (l, i) { return '<i class="' + (i === idx ? "on" : AZ.Save.data.lessons[l.id] ? "done" : "") + '"></i>'; }).join("") + "</div></div>" +
      '<div class="coach" id="coach"><div class="say" id="cSay"></div><div class="msg" id="cMsg" role="status" hidden></div><div class="choices" id="cChoices" hidden></div><div class="row-btns" id="cBtns"></div></div>' +
      '<div class="stage" id="lStage"></div><div id="lEnd"></div>';
    this.table = new AZ.Table($("#lStage"), E.makeState({}), {});
  }
  Runner.prototype.check = function () { if (this.dead) throw AZ.ABORT; };
  Runner.prototype.scene = function (stateOpts, opt) {
    this.table.st = E.makeState(stateOpts);
    this.table.opt = opt; this.table.hand = null; this.table.extraMarks = null; this.table.goal = null;
    this.table.render();
  };
  Runner.prototype.render = function () { this.table.render(); };
  Runner.prototype.say = function (html) {
    this.check();
    $("#cSay").innerHTML = html; this.msg(null);
    $("#cChoices").hidden = true; $("#cChoices").innerHTML = ""; $("#cBtns").innerHTML = "";
    AZ.say(html);
  };
  Runner.prototype.msg = function (text, ok) {
    var m = $("#cMsg"); if (!m) return;
    if (!text) { m.hidden = true; m.textContent = ""; return; }
    m.hidden = false; m.className = "msg" + (ok ? " ok" : ""); m.innerHTML = text;
  };
  Runner.prototype.next = function (label) {
    this.check();
    var self = this;
    $("#cBtns").innerHTML = '<button class="btn primary" type="button" id="cNext">' + (label || "Next") + " &#8594;</button>";
    return new Promise(function (res, rej) { self.nextResolve = res; self.nextReject = rej; }).then(function () { self.check(); });
  };
  /* Wait for a stage action that `validate` accepts (true). A string rejects it with that reason. */
  Runner.prototype.act = function (validate, goal) {
    this.check();
    var self = this;
    this.table.goal = goal || null; this.table.applyGoal();
    return new Promise(function (res, rej) { self.pending = { validate: validate, resolve: res, reject: rej }; }).then(function (a) {
      self.check(); self.table.goal = null; self.table.applyGoal(); return a;
    });
  };
  Runner.prototype.onAction = function (a) {
    if (!this.pending) return;
    var r = this.pending.validate(a);
    if (r === true) { var p = this.pending; this.pending = null; this.msg(null); Snd.play("tap"); p.resolve(a); }
    else if (typeof r === "string") {
      this.msg(r); Snd.play("wrong");
      if (a.el && !AZ.reduced) { a.el.classList.remove("shake"); void a.el.offsetWidth; a.el.classList.add("shake"); }
    }
  };
  /* Multiple choice in the coach panel. options: [{label, ok, why, value}] */
  Runner.prototype.choose = function (options) {
    this.check();
    var self = this, box = $("#cChoices");
    box.hidden = false;
    box.innerHTML = options.map(function (o, i) { return '<button class="btn" type="button" data-choice="' + i + '">' + o.label + "</button>"; }).join("");
    return new Promise(function (res, rej) { self.choice = { options: options, resolve: res, reject: rej }; }).then(function (v) { self.check(); return v; });
  };
  Runner.prototype.onChoice = function (i, el) {
    if (!this.choice) return;
    var o = this.choice.options[i];
    if (o.ok) {
      el.classList.add("right"); Snd.play("ok");
      $$all("#cChoices .btn").forEach(function (b) { b.disabled = true; });
      if (o.why) this.msg(o.why, true);
      var c = this.choice; this.choice = null;
      setTimeout(function () { c.resolve(o.value !== undefined ? o.value : o.label); }, AZ.reduced ? 50 : 450);
    } else {
      el.classList.add("wrong"); Snd.play("wrong"); this.msg(o.why || "Not quite. Try again.");
    }
  };
  function $$all(s) { return AZ.$$(s); }
  Runner.prototype.abort = function () {
    this.dead = true;
    if (this.pending) this.pending.reject(AZ.ABORT);
    if (this.nextReject) this.nextReject(AZ.ABORT);
    if (this.choice) this.choice.reject(AZ.ABORT);
  };
  Runner.prototype.remember = function (lines) {
    this.check();
    var idx = this.idx, L = LESSONS[idx], last = idx === LESSONS.length - 1;
    AZ.Save.data.lessons[L.id] = true; AZ.Save.save();
    $("#coach").hidden = true; $("#lStage").hidden = true;
    $("#lEnd").innerHTML = '<div class="card remember fadein"><h3><span class="tag">Lesson ' + (idx + 1) + " done</span> Remember</h3><ul>" +
      lines.map(function (l) { return "<li>" + l + "</li>"; }).join("") + '</ul><div class="row-btns">' +
      (last ? '<button class="btn primary" type="button" id="lnCh2">Next: Score better &#8594;</button>'
        : '<button class="btn primary" type="button" id="lnNext">Next: ' + LESSONS[idx + 1].title + " &#8594;</button>") +
      '<button class="btn" type="button" id="lnAgain">Play this lesson again</button><button class="btn ghost" type="button" id="lnMap">Back to the map</button></div></div>';
    Snd.play("win");
    var f = $("#lnCh2") || $("#lnNext"); if (f) f.focus();
  };

  function areaWrong(a) {
    return { lines: "That's the pattern lines: the staircase of rows on the left.", wall: "That's the wall: the 5 by 5 grid.",
      floor: "That's the floor line, along the bottom.", score: "That's your score." }[a.area];
  }
  function wantArea(name) { return function (a) { return a.kind === "area" ? (a.area === name || areaWrong(a)) : false; }; }
  function lineAct(T, target, extra) {
    return function (a) {
      if (a.kind === "floor") return extra && extra.floor ? extra.floor : "That's allowed, but those tiles would cost points. Use pattern line " + (target + 1) + ".";
      if (a.kind !== "line") return false;
      var b = T.table.board(), h = T.table.hand, why = AZ.placeMsg(b, a.line, h.colour);
      if (why) return why;
      if (a.line === target) return true;
      if (extra && extra[a.line]) return extra[a.line];
      var room = a.line + 1 - b.lines[a.line].count, spill = h.n - room;
      if (spill > 0) return "That's allowed, but pattern line " + (a.line + 1) + " has room for only " + AZ.plural(room, "tile") + ". " + AZ.cap(AZ.plural(spill, "tile")) + " would spill onto the floor line. Use pattern line " + (target + 1) + ".";
      return "That's allowed too, but for this lesson use pattern line " + (target + 1) + ".";
    };
  }
  function floorChoice(n) {
    var lost = -E.floorPenalty(n);
    var cands = [n, -E.floorPenalty(n + 1), -E.floorPenalty(Math.max(1, n - 1)), lost + 1];
    return AZ.numOptions(lost, cands).map(function (v) {
      return { label: String(v), ok: v === lost, why: v === lost ? "Yes: " + AZ.floorText(n) + "." : "Add the numbers under the filled spaces, from the left." };
    });
  }
  function scoreChoice(d, wrongWhy) {
    var cands = [d.h + d.v - 1, d.h > 1 ? d.h : 0, d.v > 1 ? d.v : 0, d.points + 1, d.points - 1];
    return AZ.numOptions(d.points, cands).map(function (v) {
      var why;
      if (v === d.points) why = "Yes: " + AZ.detailText(d) + ".";
      else if (d.h > 1 && d.v > 1 && v === d.h + d.v - 1) why = "Close. The new tile counts in both lines, so it is counted twice.";
      else if (d.h > 1 && d.v > 1 && (v === d.h || v === d.v)) why = "It touches tiles across and down. Count both lines and add them.";
      else why = wrongWhy;
      return { label: String(v), ok: v === d.points, why: why };
    });
  }
  function wallSpaceAct(T, row, colour) {
    var col = E.wallColumn(row, colour);
    return function (a) {
      if (a.kind !== "wall") return false;
      if (a.r !== row) return "The tile from pattern line " + (row + 1) + " goes into row " + (row + 1) + " of the wall, the row right beside it.";
      if (T.table.board().wall[a.r][a.c]) return "That space already has a tile.";
      if (a.c !== col) return "That space is for " + E.wallColour(a.r, a.c) + ". The " + colour + " tile goes on the " + colour + " space.";
      return true;
    };
  }

  /* ---------------- the eight lessons ---------------- */
  var LESSONS = AZ.LESSONS = [
    { id: "l1", title: "What's in the box", blurb: "Tiles, factory displays and your player board.",
      run: async function (T) {
        T.scene({ factories: [[]], board: E.newBoard() }, { palette: true, factories: true, centre: false, supply: { bag: TOTAL } });
        T.say("<p>Azul is a game about decorating a palace wall with " + w("tiles") + ". A tile is a small square piece.</p><p>There are " + TOTAL + " tiles: " + E.TILES_PER_COLOUR + " in each of 5 colours.</p>");
        await T.next();
        T.table.opt.paletteActive = true; T.render();
        T.say("Each colour has a letter and a mark, so you never need to tell colours apart by colour alone. Tap the <b>red</b> tile. Its letter is R and its mark is a diamond.");
        var a = await T.act(function (a) { return a.kind === "pal" ? (a.colour === "red" || "That is the " + a.colour + " tile, letter " + LET[a.colour] + ". Red has the letter R and a diamond.") : false; }, '[data-act="pal"][data-colour="red"]');
        T.msg("Right: red, letter R.", true);
        T.say("Now tap the <b>black</b> tile. Its letter is K, because B already means blue.");
        await T.act(function (a) { return a.kind === "pal" ? (a.colour === "black" || "That is the " + a.colour + " tile, letter " + LET[a.colour] + ". Black has the letter K and a plus sign.") : false; }, '[data-act="pal"][data-colour="black"]');
        T.table.opt.paletteActive = false; T.render();
        T.say("<p>All tiles start in the " + w("bag") + ". To " + w("draw") + " means to reach into the bag without looking and take tiles out.</p><p>Tiles are offered on round cardboard discs called " + w("factory displays") + ".</p>");
        await T.next();
        T.table.opt.areas = true; T.render();
        T.say("This is your " + w("player board") + ". Every player has the same board. Tap the " + w("pattern lines") + ": the five rows on the left, shaped like a staircase. Tiles you collect wait here.");
        await T.act(wantArea("lines"), '[data-area="lines"]');
        T.say("Tap the " + w("wall") + ": the 5 by 5 grid on the right. Each space shows the colour of the tile that belongs there. Tiles on the wall score points.");
        await T.act(wantArea("wall"), '[data-area="wall"]');
        T.say("Tap the " + w("floor line") + ": the seven spaces along the bottom. Tiles you can't use land here, and each space costs the points printed under it.");
        await T.act(wantArea("floor"), '[data-area="floor"]');
        T.say("Tap your " + w("score") + ". On the real board this is the " + w("score track") + " around the edge, where a marker counts your points.");
        await T.act(wantArea("score"), '[data-area="score"]');
        T.table.opt.areas = false; T.render();
        T.say("<p><b>The goal:</b> collect tiles, fill your pattern lines, and move tiles onto your wall for points. The player with the most points at the end wins.</p>");
        await T.next("Finish lesson");
        T.remember([TOTAL + " tiles in 5 colours, each with a letter: B blue, Y yellow, R red, K black, W white.",
          "Your board: pattern lines on the left, the wall on the right, the floor line at the bottom.",
          "Tiles on the wall score points. Most points wins."]);
      } },

    { id: "l2", title: "Set up the table", blurb: "Count the factory displays and fill them.",
      run: async function (T) {
        T.scene({ factories: [], board: E.newBoard() }, { supply: { bag: TOTAL } });
        T.say("Let's set up a game. First: how many players?");
        var n = await T.choose([2, 3, 4].map(function (k) { return { label: k + " players", ok: true, value: k }; }));
        var bag = shuffled(TOTAL);
        T.table.st.factories = []; for (var i = 0; i < F[n]; i++) T.table.st.factories.push([]);
        T.table.opt = { factories: true, centre: false, supply: { bag: bag.length, marker: true }, who: "Your board" };
        T.render();
        T.say("With " + n + " players you use " + w(F[n] + " factory displays") + ". (2 players: " + F[2] + ", 3 players: " + F[3] + ", 4 players: " + F[4] + ".) Put them in a ring in the middle of the table.");
        await T.next();
        T.say("<p>Every player takes a player board. <b>Everyone uses the same side</b>: the coloured side. Every board is identical.</p><p>Each player's score starts at 0.</p>");
        await T.next();
        T.table.opt.factoryBtn = true; T.render();
        T.say("All " + TOTAL + " tiles go in the bag. Now fill the factory displays: tap each one to draw " + PER + " tiles from the bag onto it.");
        var filled = 0;
        while (filled < F[n]) {
          var a = await T.act(function (a) { return a.kind === "fac" ? (T.table.st.factories[a.i].length >= PER ? "That display already has " + PER + " tiles. Each factory display gets exactly " + PER + "." : true) : false; }, '[data-act="fac"].need');
          await T.table.fillFactory(a.i, bag); T.check();
          filled++;
          T.msg(filled < F[n] ? filled + " of " + F[n] + " filled." : "All " + F[n] + " displays have " + PER + " tiles each.", true);
        }
        T.table.opt.factoryBtn = false; T.table.opt.supply.markerBtn = true; T.render();
        T.say("Last step: choose who starts. That player is the " + w("starting player") + " and takes the " + w("starting player marker") + ", the token with a 1. Let's say it's you: tap the marker.");
        await T.act(function (a) { return a.kind === "marker" || (a.kind === "fac" ? "The displays are ready. Now tap the starting player marker." : false); }, '[data-act="marker"]');
        var r = T.table.rects(["ma"]);
        T.table.opt.supply.marker = false; T.table.opt.markerMine = true; T.render();
        await T.table.fly([{ from: "ma", to: "pbm", html: AZ.markerHTML({ label: false }) }], r);
        T.say("You are the starting player. The table is ready to play.");
        await T.next("Finish lesson");
        T.remember(["2, 3 or 4 players use " + F[2] + ", " + F[3] + " or " + F[4] + " factory displays.",
          "Draw " + PER + " tiles from the bag onto each factory display.",
          "Everyone uses the same board side and starts on 0. The starting player takes the marker."]);
      } },

    { id: "l3", title: "Take tiles", blurb: "Take one colour; the rest slides to the centre.",
      run: async function (T) {
        T.scene({ factories: [["red", "red", "blue", "yellow"], ["black", "black", "black", "white"], ["blue", "blue", "red", "red"], ["yellow", "white", "white", "black"], ["red", "yellow", "yellow", "yellow"]], centre: [], centre_marker: true },
          { factories: true, hand: true, board: false });
        T.say("<p>Players take " + w("turns") + ": a turn is one player's go. Turns go " + w("clockwise") + ", to the player on your left.</p><p>The starting player first puts the marker in the " + w("centre of the table") + ": the space inside the ring of displays.</p>");
        await T.next();
        T.table.opt.takeable = true; T.render();
        T.say("On your turn you <b>must</b> take tiles. Pick one colour on one factory display, and you take <b>every</b> tile of that colour there. Try it: tap the red tiles on display 1.");
        var a = await T.act(function (a) {
          if (a.kind === "marker") return "The marker isn't a tile. You only take it together with tiles from the centre.";
          if (a.kind === "emptyfac") return "That display is empty. Pick one with tiles.";
          return a.kind === "take" && a.src !== E.CENTRE ? true : false;
        }, '[data-act="take"][data-src="0"][data-colour="red"]');
        var info = await T.table.take(a.src, a.colour); T.check();
        T.say("You took " + AZ.plural(info.taken, a.colour + " tile") + ". The other " + AZ.plural(info.pushed, "tile") + " on display " + (a.src + 1) + " slid into the centre. That display is now empty.");
        await T.next();
        T.table.hand = null; T.render();
        T.say("Your tiles go on your board; the next lesson shows how. On a later turn, you may take from the <b>centre</b> instead. Tap a colour in the centre.");
        a = await T.act(function (a) {
          if (a.kind === "marker") return "The marker isn't a tile. Tap a tile in the centre; the marker comes along by itself.";
          if (a.kind === "emptyfac") return "That display is empty. This time, take from the centre.";
          if (a.kind === "take" && a.src !== E.CENTRE) return "This time, take from the centre of the table.";
          return a.kind === "take";
        }, '.centre [data-act="take"]');
        info = await T.table.take(a.src, a.colour); T.check();
        T.say("You took " + AZ.plural(info.taken, a.colour + " tile") + " from the centre. You were the first to take from the centre this round, so you also took the " + w("starting player marker") + ". It costs a point or two, but you go first next round.");
        await T.next();
        T.table.hand = null; T.render();
        T.say("Quick check. A display shows 2 blue tiles and 2 red tiles. What may you take?");
        await T.choose([
          { label: "One blue tile", ok: false, why: "You must take <b>all</b> tiles of the colour you pick." },
          { label: "One blue and one red", ok: false, why: "Only <b>one</b> colour per turn." },
          { label: "Both blue tiles", ok: true, why: "Yes. All tiles of one colour. The 2 red slide to the centre." }]);
        T.say("When you take from a factory display, where do its other tiles go?");
        await T.choose([
          { label: "Back in the bag", ok: false, why: "No. They stay in play for this round." },
          { label: "Into the centre", ok: true, why: "Yes. Anyone can take them from the centre later." },
          { label: "They stay on the display", ok: false, why: "No. A display is always emptied when someone takes from it." }]);
        await T.next("Finish lesson");
        T.remember(["Take <b>all</b> tiles of <b>one</b> colour, from one factory display or from the centre.",
          "The rest of that display slides into the centre.",
          "The first player to take from the centre also takes the starting player marker."]);
      } },

    { id: "l4", title: "Pattern lines", blurb: "Choose a line; see which lines are not allowed.",
      run: async function (T) {
        var b = E.makeBoard({ lines: [null, ["blue", 1], null, null, ["yellow", 2]] });
        b.wall[3][E.wallColumn(3, "red")] = "red";
        T.scene({ board: b }, { hand: true });
        T.table.hand = { colour: "red", n: 3 }; T.render();
        T.say("<p>Right after you take tiles, you put <b>all</b> of them into <b>one</b> " + w("pattern line") + ". Line 1 has 1 space, line 5 has 5.</p><p>Tiles fill a line from right to left, starting next to the wall.</p>");
        await T.next();
        T.table.opt.linesActive = true; T.table.opt.floorActive = true; T.render();
        T.say("You hold 3 red tiles. Put them in pattern line 3. (Try another line first if you like: you'll see why it doesn't work.)");
        await T.act(lineAct(T, 2), '[data-act="line"][data-line="2"]');
        await T.table.place(2); T.check();
        T.say("Pattern line 3 is full. A full line is called " + w("complete") + ". At the end of the round, each complete line moves one tile to the wall.");
        await T.next();
        T.table.hand = { colour: "blue", n: 2 }; T.render();
        T.say("Now you hold 2 blue tiles. Put them in a line where both fit, so nothing spills.");
        await T.act(lineAct(T, 3, { 1: "Pattern line 2 already has 1 blue, so it has room for only 1 more. The other tile would spill onto the floor line.", 0: "Pattern line 1 has room for only 1 tile. The other would spill onto the floor line." }), '[data-act="line"][data-line="3"]');
        await T.table.place(3); T.check();
        T.table.opt.linesActive = false; T.table.opt.floorActive = false; T.render();
        T.say("Pattern line 4 is not complete yet. That's fine: an unfinished line keeps its tiles, and you can add more blue on a later turn.");
        await T.next("Finish lesson");
        T.remember(["Put all the tiles you take into one pattern line, filling it from the right.",
          "One colour per line, and never a colour that is already in that row of your wall.",
          "Line 1 holds 1 tile, line 5 holds 5. A full line is complete."]);
      } },

    { id: "l5", title: "The floor line", blurb: "Extra tiles fall to the floor and cost points.",
      run: async function (T) {
        var b = E.makeBoard({ score: 12, lines: [["black", 1], null, ["blue", 3], ["red", 1], ["white", 2]] });
        T.scene({ board: b, factories: [], centre: ["red", "red", "red", "blue"], centre_marker: true }, { hand: true, factories: true });
        T.table.hand = { colour: "yellow", n: 4 }; T.render();
        T.say("<p>Sometimes you take more tiles than your line can hold. The extra tiles fall to the " + w("floor line") + ", filling it from the left.</p><p>Each floor space costs the points printed under it: " + E.FLOOR_VALUES.map(AZ.minus).join(" ") + ".</p>");
        await T.next();
        T.table.opt.linesActive = true; T.table.opt.floorActive = true; T.render();
        T.say("You hold 4 yellow tiles. Put them in pattern line 2.");
        await T.act(lineAct(T, 1, { floor: "That's allowed, but let's fill pattern line 2 first." }), '[data-act="line"][data-line="1"]');
        var pi = await T.table.place(1); T.check();
        T.table.opt.linesActive = false; T.table.opt.floorActive = false; T.render();
        T.say("Pattern line 2 took " + pi.placed + ". The other " + pi.to_floor + " fell to the floor line. How many points will the floor line cost you so far?");
        await T.choose(floorChoice(T.table.board().floor.length));
        T.table.opt.takeable = true; T.render();
        T.say("On a later turn, you take tiles from the centre. Tap the red tiles in the centre.");
        var a = await T.act(function (a) {
          if (a.kind === "marker") return "The marker isn't a tile. Tap the red tiles; the marker comes along by itself.";
          return a.kind === "take" ? (a.colour === "red" || "Take the red tiles this time.") : false;
        }, '[data-act="take"][data-colour="red"]');
        await T.table.take(a.src, a.colour); T.check();
        T.table.opt.takeable = false; T.table.opt.linesActive = true; T.table.opt.floorActive = true; T.render();
        T.say("You were first to take from the centre, so the " + w("starting player marker") + " went onto your floor line first. It counts like a tile there. Now put the 3 red tiles in pattern line 4.");
        await T.act(lineAct(T, 3), '[data-act="line"][data-line="3"]');
        await T.table.place(3); T.check();
        T.table.opt.linesActive = false; T.table.opt.floorActive = false; T.render();
        var n = T.table.board().floor.length;
        T.say("Your floor line now holds " + AZ.plural(n, "item") + ". How many points do you lose?");
        await T.choose(floorChoice(n));
        T.say("<p>You may also put the tiles you take straight onto the floor line. If all " + E.FLOOR_SPACES + " spaces are full, extra tiles go to the " + w("box lid") + " and cost nothing more.</p><p>Your score can never drop below 0.</p>");
        await T.next("Finish lesson");
        T.remember(["Tiles that don't fit fall to the floor line, from left to right.",
          "Floor spaces cost " + E.FLOOR_VALUES.map(AZ.minus).join(" ") + ": the first items are cheap, later ones hurt.",
          "The starting player marker counts as an item on the floor line."]);
      } },

    { id: "l6", title: "Tiles to the wall", blurb: "Move a tile to the wall and count its points.",
      run: async function (T) {
        var b = E.makeBoard({ score: 4, wall: [".....", "..X.X", "X....", ".X...", ".X..."], lines: [["blue", 1], ["red", 2], ["white", 3], null, null] });
        T.scene({ board: b }, { supply: { lid: 0 }, hlLines: [0, 1, 2] });
        T.say("<p>When every factory display and the centre are empty, collecting stops. Now comes " + w("wall-tiling") + ".</p><p>Each complete pattern line moves its <b>rightmost</b> tile onto the wall, to the space of the same colour in the row beside it.</p>");
        await T.next();
        T.table.opt.wallActive = true; T.render();
        T.say("Pattern line 1 is complete. Tap the wall space where its blue tile goes: row 1, the blue space.");
        await T.act(wallSpaceAct(T, 0, "blue"), '[data-act="wall"][data-r="0"][data-c="' + E.wallColumn(0, "blue") + '"]');
        T.table.opt.hlLines = [1, 2];
        var r = await T.table.tileLine(0); T.check();
        T.say("The blue tile touches no other tile across or down. A tile with no neighbours scores " + w(r.points + " point") + ".");
        await T.next();
        T.say("Pattern line 2 is complete too. Tap the space for its red tile.");
        await T.act(wallSpaceAct(T, 1, "red"), '[data-act="wall"][data-r="1"][data-c="' + E.wallColumn(1, "red") + '"]');
        T.table.opt.hlLines = [2];
        r = await T.table.tileLineQuiet(1); T.check();
        T.say("The other red tile from that line went into the " + w("box lid") + ". Now count: how many tiles are in the unbroken line across that includes the new tile? That's its points.");
        await T.choose(scoreChoice(r.detail, "Count the tiles side by side in row 2, including the new one. Stop at a gap."));
        T.table.reveal(r);
        T.say("Across: " + AZ.detailText(r.detail) + ". An empty space stops the count.");
        await T.next();
        T.say("Last one: pattern line 3. Tap the space for its white tile.");
        await T.act(wallSpaceAct(T, 2, "white"), '[data-act="wall"][data-r="2"][data-c="' + E.wallColumn(2, "white") + '"]');
        T.table.opt.hlLines = [];
        r = await T.table.tileLineQuiet(2); T.check();
        T.say("This tile touches tiles across <b>and</b> down. Count the unbroken line across, then the unbroken line down, and add them. How many points?");
        await T.choose(scoreChoice(r.detail, "Count both lines. Across: tiles side by side. Down: tiles above and below."));
        T.table.reveal(r);
        T.say("Across and down: " + AZ.detailText(r.detail) + ". The new tile counts in both lines.");
        T.table.opt.wallActive = false;
        await T.next("Finish lesson");
        T.remember(["A complete line moves its rightmost tile to the wall space of the same colour. The rest go to the box lid.",
          "A tile with no neighbours scores 1.",
          "Otherwise count the unbroken line across and the unbroken line down, and add them."]);
      } },

    { id: "l7", title: "End of a round", blurb: "Top to bottom, pay the floor, refill from the bag.",
      run: async function (T) {
        var b = E.makeBoard({ score: 9, wall: ["X....", "....X", ".X...", ".....", "....."], lines: [["yellow", 1], ["white", 1], ["red", 3], ["blue", 2], null], floor: [E.MARKER, "white"] });
        var bag = shuffled(6), lidStart = shuffled(14);
        T.scene({ board: b, factories: [[], [], [], [], []], centre: [], centre_marker: false, lid: lidStart }, { factories: true, centre: false, supply: { bag: bag.length, lid: lidStart.length } });
        T.say("<p>Every factory display and the centre are empty, so collecting is over for this round. Now: " + w("wall-tiling") + ".</p><p>Go through your pattern lines <b>from top to bottom</b>. Only complete lines move a tile.</p>");
        await T.next();
        T.table.opt.linesActive = true; T.render();
        var todo = [0, 2];
        while (todo.length) {
          T.say(todo.length === 2 ? "Tap the first complete pattern line, starting from the top." : "Tap the next complete pattern line.");
          var want = todo[0];
          await T.act(function (a) {
            if (a.kind !== "line") return false;
            var pl = T.table.board().lines[a.line], cap = a.line + 1;
            if (pl.count < cap) return "Pattern line " + (a.line + 1) + " isn't complete (" + pl.count + " of " + cap + "). Its tiles stay for the next round.";
            if (a.line !== want) return "Go from top to bottom: pattern line " + (want + 1) + " comes first.";
            return true;
          }, '[data-act="line"][data-line="' + want + '"]');
          var r = await T.table.tileLine(want); T.check();
          T.msg("Pattern line " + (want + 1) + ": " + r.colour + " to the wall, " + AZ.detailText(r.detail) + (r.to_lid ? ". " + AZ.cap(AZ.plural(r.to_lid, "leftover tile")) + " to the box lid." : "."), true);
          todo.shift();
        }
        T.table.opt.linesActive = false; T.render();
        T.say("Pattern lines 2 and 4 were not complete. Their tiles stay where they are, ready for the next round.");
        await T.next();
        T.table.opt.floorActive = true; T.render();
        T.say("Now pay for your floor line. Tap it.");
        await T.act(function (a) { return a.kind === "floor"; }, '[data-act="floor"]');
        var fr = await T.table.payFloor(); T.check();
        T.table.opt.floorActive = false; T.render();
        T.say("You lost " + AZ.floorText(fr.items) + " points. The floor tiles went to the box lid. The starting player marker stays with you: you start the next round.");
        await T.next();
        T.table.opt.factoryBtn = true; T.table.opt.supply.bag = bag.length; T.render();
        T.say("Nobody has a complete row across, so the game goes on: " + w("prepare the next round") + ". You hold the marker, so you fill every factory display with " + PER + " tiles again. Tap each display.");
        var lid = T.table.st.lid, poured = false;
        while (T.table.st.factories.some(function (f) { return f.length < PER; })) {
          var a = await T.act(function (a) {
            if (a.kind === "lid") return "Fill the displays first. You only use the box lid when the bag runs empty.";
            return a.kind === "fac" ? (T.table.st.factories[a.i].length >= PER ? "That display already has " + PER + " tiles." : true) : false;
          }, '[data-act="fac"].need');
          await T.table.fillFactory(a.i, bag); T.check();
          if (!bag.length && T.table.st.factories.some(function (f) { return f.length < PER; }) && !poured) {
            T.table.opt.supply.lidBtn = true; T.table.opt.factoryBtn = false; T.render();
            T.say("The bag is empty, but a display still needs tiles! Tap the " + w("box lid") + " to pour all its tiles into the bag. Then keep filling.");
            await T.act(function (a) { return a.kind === "lid" || (a.kind === "fac" ? "The bag is empty. Pour in the box lid first." : false); }, '[data-act="lid"]');
            var rr = T.table.rects(["lid"]);
            while (lid.length) bag.push(lid.pop());
            T.table.opt.supply = { bag: bag.length, lid: 0 }; T.table.opt.factoryBtn = true; T.render();
            Snd.play("slide");
            await T.table.fly([{ from: "lid", to: "bag", html: '<svg class="ico" style="width:34px;height:34px"><use href="#ico-lid"/></svg>' }], rr);
            poured = true;
            T.say("Mixed into the bag. Now finish filling the displays.");
          }
        }
        T.table.opt.factoryBtn = false; T.render();
        T.say("Every display has " + PER + " tiles. The new round begins: you put the marker in the centre and take the first turn.");
        await T.next("Finish lesson");
        T.remember(["Wall-tiling goes from top to bottom. Unfinished lines keep their tiles.",
          "Pay the floor line. Floor tiles and leftovers go to the box lid; the marker holder starts next round.",
          "If the bag runs empty while filling, pour the box lid into the bag."]);
      } },

    { id: "l8", title: "End of the game", blurb: "A full row ends it. Then bonuses.",
      run: async function (T) {
        var b = E.makeBoard({ score: 52, wall: ["X.X..", "XXX.X", "X.X.X", "X..X.", "X..XX"], lines: [null, ["red", 2], null, null, null] });
        T.scene({ board: b }, { hlLines: [1] });
        T.say("The game ends after the round in which any player completes a " + w("row") + ": 5 tiles side by side across the wall. Here it is the last wall-tiling of the game.");
        await T.next();
        T.table.opt.linesActive = true; T.render();
        T.say("Tap pattern line 2 to move its red tile to the wall.");
        await T.act(function (a) { return a.kind === "line" ? (a.line === 1 || "Pattern line " + (a.line + 1) + " isn't complete. Tap pattern line 2.") : false; }, '[data-act="line"][data-line="1"]');
        T.table.opt.linesActive = false; T.table.opt.hlLines = [];
        var r = await T.table.tileLine(1); T.check();
        T.say("Row 2 is complete! The tile scored " + AZ.detailText(r.detail) + ". Everyone finishes this wall-tiling and the floor line. Then the game ends: no new round.");
        await T.next();
        T.say("Does a full " + w("column") + " (5 tiles straight down) end the game?");
        await T.choose([{ label: "Yes", ok: false, why: "No. Only a complete row <b>across</b> ends the game." }, { label: "No", ok: true, why: "Right. Only a complete row across ends it." }]);
        T.table.extraMarks = null; T.table.opt.wallActive = true; T.render();
        var wall = T.table.board().wall, parts = E.bonusParts(wall), picked = [], bonus = 0;
        function cellsOf(kind, x) {
          var out = [], i;
          for (i = 0; i < 5; i++) {
            if (kind === "rows") out.push([x, i]);
            else if (kind === "columns") out.push([i, x]);
            else out.push([i, E.wallColumn(i, x)]);
          }
          return out;
        }
        var steps = [
          { kind: "rows", ask: "Now the " + w("end bonuses") + ". Each complete row is worth +" + E.ROW_BONUS + ". Tap a tile in each complete row.", value: E.ROW_BONUS,
            key: function (a) { return a.r; }, name: function (x) { return "row " + (x + 1); }, miss: function (a) { return "Row " + (a.r + 1) + " has only " + wall[a.r].filter(Boolean).length + " tiles."; } },
          { kind: "columns", ask: "Each complete column (5 down) is worth +" + E.COLUMN_BONUS + ". Tap a tile in each complete column.", value: E.COLUMN_BONUS,
            key: function (a) { return a.c; }, name: function (x) { return "column " + (x + 1); }, miss: function (a) { var n = 0; for (var i = 0; i < 5; i++) if (wall[i][a.c]) n++; return "Column " + (a.c + 1) + " has only " + n + " tiles."; } },
          { kind: "colours", ask: "Each colour with all 5 of its tiles on your wall is worth +" + E.COLOUR_BONUS + ". Tap a tile of each such colour.", value: E.COLOUR_BONUS,
            key: function (a) { return wall[a.r][a.c]; }, name: function (x) { return "all 5 " + x; }, miss: function (a) { var c = wall[a.r][a.c], n = 0; for (var i = 0; i < 5; i++) if (wall[i][E.wallColumn(i, c)]) n++; return "Only " + n + " of the 5 " + c + " tiles are on your wall."; } }];
        for (var s = 0; s < steps.length; s++) {
          var st = steps[s], found = [];
          T.say(st.ask);
          while (found.length < parts[st.kind].length) {
            var a = await T.act(function (a) {
              if (a.kind !== "wall") return false;
              if (!wall[a.r][a.c]) return "That space is empty. Tap a tile.";
              var k = st.key(a);
              if (parts[st.kind].indexOf(k) < 0) return st.miss(a);
              if (found.indexOf(k) >= 0) return "Already counted. " + (found.length < parts[st.kind].length ? "Find another." : "");
              return true;
            }, null);
            var k = st.key(a); found.push(k); bonus += st.value;
            picked = picked.concat(cellsOf(st.kind, k));
            T.table.extraMarks = { pick: picked }; T.render();
            T.table.pop("w" + a.r + "-" + a.c, "+" + st.value); Snd.play("score", 3);
            T.msg(AZ.cap(st.name(k)) + ": +" + st.value + ".", true);
          }
          if (!parts[st.kind].length) { T.msg("None this time.", true); await T.next(); }
        }
        T.table.opt.wallActive = false;
        var bd = E.bonusBreakdown(wall);
        T.table.board().score += bd.total; T.render();
        T.table.pop("score", "+" + bd.total); Snd.play("win");
        T.say("Bonus: " + AZ.plural(bd.rows, "row") + " × " + E.ROW_BONUS + " + " + AZ.plural(bd.columns, "column") + " × " + E.COLUMN_BONUS + " + " + AZ.plural(bd.colours, "colour") + " × " + E.COLOUR_BONUS + " = <b>" + bd.total + "</b>. Final score: <b>" + T.table.board().score + "</b>.");
        await T.next();
        T.say("<p>The player with the most points wins.</p><p>If players tie, the tied player with more complete rows wins. Still tied? You share the victory.</p>");
        await T.next("Finish lesson");
        T.remember(["The game ends after the round in which someone completes a row across.",
          "Bonuses: +" + E.ROW_BONUS + " per complete row, +" + E.COLUMN_BONUS + " per complete column, +" + E.COLOUR_BONUS + " per colour with all 5 tiles.",
          "Most points wins. Tie: more complete rows wins."]);
      } }
  ];

  /* ---------------- open / close ---------------- */
  var cur = null;
  AZ.openLesson = function (idx) {
    if (cur) cur.abort();
    AZ.show("lesson", "Lesson " + (idx + 1));
    var T = cur = new Runner(idx);
    LESSONS[idx].run(T).catch(function (e) { if (e !== AZ.ABORT) console.error(e); });
  };
  AZ.leaveHooks.push(function (to) { if (to !== "lesson" && cur) { cur.abort(); cur = null; } });

  $("#lesson").addEventListener("click", function (ev) {
    var t = ev.target;
    if (!cur) return;
    if (t.closest("#cNext")) { var r = cur.nextResolve; cur.nextResolve = null; $("#cBtns").innerHTML = ""; Snd.play("tap"); if (r) r(); return; }
    var ch = t.closest("[data-choice]");
    if (ch) { cur.onChoice(+ch.dataset.choice, ch); return; }
    if (t.closest("#lnNext")) { AZ.openLesson(cur.idx + 1); return; }
    if (t.closest("#lnAgain")) { AZ.openLesson(cur.idx); return; }
    if (t.closest("#lnCh2")) { AZ.openBridge(); return; }
    if (t.closest("#lnMap")) { AZ.goHome(); return; }
    var el = t.closest("[data-act]");
    if (el && $("#lStage").contains(el)) cur.onAction(AZ.parseAct(el));
  });
  AZ.lessonKey = function (ev) {
    if (!cur) return false;
    var k = ev.key;
    if (/^[1-5]$/.test(k)) { var el = $('#lStage [data-act="line"][data-line="' + (+k - 1) + '"]'); if (el) { cur.onAction(AZ.parseAct(el)); return true; } }
    if (k === "f" || k === "F" || k === "0") { var fl = $('#lStage [data-act="floor"]'); if (fl) { cur.onAction(AZ.parseAct(fl)); return true; } }
    return false;
  };
})();
