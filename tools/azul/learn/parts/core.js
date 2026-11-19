/* Core: save, sound, rendering of tiles / table / board, animated table actions, rules overlay, navigation. */
(function () {
  "use strict";
  var E = window.AzulEngine;
  var AZ = window.AZ = {};
  var LET = E.LETTERS;
  var $ = AZ.$ = function (s, el) { return (el || document).querySelector(s); };
  var $$ = AZ.$$ = function (s, el) { return Array.prototype.slice.call((el || document).querySelectorAll(s)); };
  var reduced = AZ.reduced = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  AZ.ABORT = { abort: true };

  function w(t) { return '<b class="w">' + t + "</b>"; }
  AZ.w = w;
  AZ.sign = function (n) { return n > 0 ? "+" + n : n < 0 ? "−" + Math.abs(n) : "0"; };
  AZ.minus = function (n) { return "−" + Math.abs(n); };
  AZ.cap = function (s) { return s.charAt(0).toUpperCase() + s.slice(1); };
  AZ.plural = function (n, one, many) { return n + " " + (n === 1 ? one : (many || one + "s")); };
  AZ.colourName = function (c) { return c + " (" + LET[c] + ")"; };
  AZ.sleep = function (ms) { return new Promise(function (r) { setTimeout(r, reduced ? Math.min(ms, 60) : ms); }); };

  /* ---------------- save (per-viewer convenience only) ---------------- */
  var Save = AZ.Save = {
    key: "azul-tile-school-v1",
    data: { lessons: {}, stars: {}, rush: { tile: 0, floor: 0 }, muted: false, skipped: false, bridgeSeen: false },
    load: function () {
      try { var r = localStorage.getItem(this.key); if (r) { var d = JSON.parse(r); if (d && typeof d === "object") { Object.assign(this.data, d); this.data.rush = Object.assign({ tile: 0, floor: 0 }, d.rush || {}); } } } catch (e) { /* storage unavailable */ }
    },
    save: function () { try { localStorage.setItem(this.key, JSON.stringify(this.data)); } catch (e) { /* storage unavailable */ } },
    reset: function () { this.data = { lessons: {}, stars: {}, rush: { tile: 0, floor: 0 }, muted: this.data.muted, skipped: false, bridgeSeen: false }; this.save(); }
  };
  Save.load();

  /* ---------------- sound (Web Audio, starts after a tap) ---------------- */
  var Snd = AZ.Snd = {
    ctx: null,
    ensure: function () {
      if (this.ctx || Save.data.muted) return;
      try { var C = window.AudioContext || window.webkitAudioContext; if (C) this.ctx = new C(); } catch (e) { this.ctx = null; }
    },
    tone: function (f, dur, type, vol, delay, f2) {
      var c = this.ctx; if (!c || Save.data.muted) return;
      try {
        if (c.state === "suspended") c.resume();
        var t = c.currentTime + (delay || 0), o = c.createOscillator(), g = c.createGain();
        o.type = type || "sine"; o.frequency.setValueAtTime(f, t);
        if (f2) o.frequency.exponentialRampToValueAtTime(f2, t + dur);
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol || 0.06, t + 0.012);
        g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        o.connect(g); g.connect(c.destination); o.start(t); o.stop(t + dur + 0.02);
      } catch (e) { /* ignore */ }
    },
    play: function (n, x) {
      var T = this.tone.bind(this);
      switch (n) {
        case "tap": T(660, 0.06, "triangle", 0.05); break;
        case "clack": T(1400, 0.035, "square", 0.025); T(900, 0.05, "triangle", 0.04, 0.03); break;
        case "slide": T(300, 0.18, "sine", 0.04, 0, 520); break;
        case "place": T(520, 0.07, "triangle", 0.06); T(780, 0.08, "triangle", 0.05, 0.05); break;
        case "score": var k = Math.min(x || 1, 8); for (var i = 0; i < k; i++) T(523 * Math.pow(1.122, i), 0.09, "triangle", 0.05, i * 0.055); break;
        case "lose": T(392, 0.16, "sawtooth", 0.025); T(294, 0.22, "sawtooth", 0.025, 0.12); break;
        case "wrong": T(180, 0.16, "square", 0.03); T(150, 0.18, "square", 0.03, 0.08); break;
        case "ok": T(784, 0.08, "triangle", 0.05); T(1047, 0.12, "triangle", 0.05, 0.07); break;
        case "star": T(1047, 0.1, "triangle", 0.05, x || 0); T(1568, 0.14, "triangle", 0.04, (x || 0) + 0.06); break;
        case "win": [523, 659, 784, 1047, 784, 1047].forEach(function (f, i) { T(f, 0.14, "triangle", 0.05, i * 0.08); }); break;
        case "tick": T(1200, 0.03, "square", 0.015); break;
        case "over": [392, 349, 311, 262].forEach(function (f, i) { T(f, 0.2, "triangle", 0.05, i * 0.14); }); break;
      }
    }
  };
  function syncMute() {
    var b = $("#muteBtn"), m = Save.data.muted;
    b.setAttribute("aria-pressed", m ? "true" : "false");
    b.setAttribute("aria-label", m ? "Sound off. Press to turn sound on." : "Sound on. Press to mute.");
    b.innerHTML = m ? '<span aria-hidden="true" style="text-decoration:line-through">&#9835;</span>' : '<span aria-hidden="true">&#9835;</span>';
  }
  AZ.syncMute = syncMute;

  AZ.say = function (t) { var l = $("#live"); l.textContent = ""; setTimeout(function () { l.textContent = t.replace(/<[^>]+>/g, ""); }, 30); };

  /* ---------------- tile HTML ---------------- */
  function tileHTML(c, o) {
    o = o || {};
    var cls = "tile c-" + c + (o.cls ? " " + o.cls : "");
    var lab = o.label === false ? ' aria-hidden="true"' : ' role="img" aria-label="' + (o.ghost ? "empty space for " : "") + c + ' tile"';
    return '<span class="' + cls + '" data-l="' + LET[c] + '"' + (o.k ? ' data-k="' + o.k + '"' : "") + lab +
      '><svg aria-hidden="true" focusable="false"><use href="#mk-' + c + '"/></svg></span>';
  }
  function markerHTML(o) {
    o = o || {};
    return '<span class="tile marker' + (o.cls ? " " + o.cls : "") + '"' + (o.k ? ' data-k="' + o.k + '"' : "") +
      (o.label === false ? ' aria-hidden="true"' : ' role="img" aria-label="starting player marker"') + ">1</span>";
  }
  function itemHTML(x, o) { return x === E.MARKER ? markerHTML(o) : tileHTML(x, o); }
  AZ.tileHTML = tileHTML; AZ.markerHTML = markerHTML; AZ.itemHTML = itemHTML;

  /* ---------------- table + board HTML ---------------- */
  function factoriesHTML(st, o) {
    return '<div class="factories">' + st.factories.map(function (f, i) {
      var inner = f.map(function (c, j) {
        var k = "f" + i + "-" + j;
        if (o.takeable) return '<button type="button" class="tilebtn" data-act="take" data-src="' + i + '" data-colour="' + c + '" aria-label="Take ' + c + ' from factory display ' + (i + 1) + '">' + tileHTML(c, { cls: "sm", k: k, label: false }) + "</button>";
        return tileHTML(c, { cls: "sm", k: k });
      }).join("");
      var open = "div", attrs = "";
      if (o.factoryBtn) { open = "button"; attrs = ' type="button" data-act="fac" data-i="' + i + '" aria-label="Factory display ' + (i + 1) + ", " + AZ.plural(f.length, "tile") + '"'; }
      else if (o.takeable && !f.length) { open = "button"; attrs = ' type="button" data-act="emptyfac" data-i="' + i + '" aria-label="Factory display ' + (i + 1) + ', empty"'; }
      var need = o.factoryBtn && f.length < E.TILES_PER_FACTORY ? " need" : "";
      return "<" + open + attrs + ' class="factory' + (f.length ? "" : " empty") + (o.factoryBtn ? need : "") + '" data-k="fd' + i + '">' + inner + '<span class="fno" aria-hidden="true">' + (i + 1) + "</span></" + open + ">";
    }).join("") + "</div>";
  }
  function centreHTML(st, o) {
    var h = "";
    if (st.centre_marker) h += o.takeable ? '<button type="button" class="tilebtn" data-act="marker" aria-label="Starting player marker">' + markerHTML({ cls: "sm", k: "cm", label: false }) + "</button>" : markerHTML({ cls: "sm", k: "cm" });
    st.centre.forEach(function (c, j) {
      var k = "c" + j;
      h += o.takeable ? '<button type="button" class="tilebtn" data-act="take" data-src="centre" data-colour="' + c + '" aria-label="Take ' + c + ' from the centre">' + tileHTML(c, { cls: "sm", k: k, label: false }) + "</button>" : tileHTML(c, { cls: "sm", k: k });
    });
    if (!h) h = '<span class="none">empty</span>';
    return '<div class="centre" data-k="centre" aria-label="Centre of the table">' + h + "</div>";
  }
  function handHTML(hand) {
    var h = '<div class="hand" aria-label="In your hand"><span class="lbl">In your hand:</span><span class="tiles">';
    if (hand && hand.n) {
      for (var q = 0; q < hand.n; q++) h += tileHTML(hand.colour, { cls: "sm", k: "h" + q });
      if (hand.marker) h += markerHTML({ cls: "sm", k: "hm" });
      h += '</span><span class="lbl"><b>' + hand.n + " " + hand.colour + "</b>" + (hand.marker ? " and the starting player marker" : "") + "</span>";
    } else h += '</span><span class="lbl">nothing</span>';
    return h + "</div>";
  }
  function supplyHTML(o) {
    var s = o.supply, h = '<div class="supply">';
    if (s.bag !== undefined) {
      var tb = s.bagBtn ? 'button type="button" data-act="bag"' : "div";
      h += "<" + tb + ' class="pile" data-k="bag"><svg class="ico" aria-hidden="true"><use href="#ico-bag"/></svg><span>Bag <span class="num">' + s.bag + "</span></span></" + tb.split(" ")[0] + ">";
    }
    if (s.lid !== undefined) {
      var tl = s.lidBtn ? 'button type="button" data-act="lid"' : "div";
      h += "<" + tl + ' class="pile" data-k="lid"><svg class="ico" aria-hidden="true"><use href="#ico-lid"/></svg><span>Box lid <span class="num">' + s.lid + "</span></span></" + tl.split(" ")[0] + ">";
    }
    if (s.marker) {
      h += s.markerBtn ? '<button type="button" class="pile" data-act="marker" aria-label="Starting player marker">' + markerHTML({ k: "ma", label: false }) + "<span>Starting player marker</span></button>"
        : '<div class="pile">' + markerHTML({ k: "ma" }) + "<span>Starting player marker</span></div>";
    }
    return h + "</div>";
  }

  function lineLabel(b, i) {
    var pl = b.lines[i], cap = i + 1;
    return "Pattern line " + (i + 1) + ": " + (pl.count ? pl.count + " " + pl.colour + " of " + cap : "empty, " + AZ.plural(cap, "space"));
  }
  function boardHTML(b, o) {
    o = o || {};
    var marks = o.marks || {}, i, r, c;
    var key = function (r, c) { return r + "," + c; };
    var ring = marks.ring ? key(marks.ring[0], marks.ring[1]) : null, runH = {}, runV = {}, pick = {};
    (marks.h || []).forEach(function (p) { runH[key(p[0], p[1])] = 1; });
    (marks.v || []).forEach(function (p) { runV[key(p[0], p[1])] = 1; });
    (marks.pick || []).forEach(function (p) { pick[key(p[0], p[1])] = 1; });
    var linesH = "", numsH = "";
    for (i = 0; i < 5; i++) {
      var pl = b.lines[i], cap = i + 1, cells = "";
      for (var pos = 0; pos < cap; pos++) {
        var slot = cap - 1 - pos, k = "l" + i + "-" + slot;
        cells += slot < pl.count ? tileHTML(pl.colour, { k: k, label: false }) : '<span class="hole" data-k="' + k + '" aria-hidden="true"></span>';
      }
      var hl = o.hlLines && o.hlLines.indexOf(i) >= 0 ? " hl" : "";
      if (o.linesActive) linesH += '<button type="button" class="pline' + hl + '" data-act="line" data-line="' + i + '" aria-label="' + lineLabel(b, i) + '">' + cells + "</button>";
      else linesH += '<div class="pline' + hl + '" role="img" aria-label="' + lineLabel(b, i) + '">' + cells + "</div>";
      numsH += '<span class="lno" style="height:var(--cell);display:flex;align-items:center;font:700 13px/1 var(--font-body);color:var(--ink-2)" aria-hidden="true">' + (i + 1) + "</span>";
    }
    var wallH = "";
    for (r = 0; r < 5; r++) for (c = 0; c < 5; c++) {
      var t = b.wall[r][c], wc = E.wallColour(r, c), kk = key(r, c);
      var cls = "wcell" + (ring === kk ? " ring" : "") + (runH[kk] ? " run-h" : "") + (runV[kk] ? " run-v" : "") + (pick[kk] ? " pick" : "");
      var inner = t ? tileHTML(t, { label: false }) : tileHTML(wc, { cls: "ghost", label: false });
      var lab = "Wall row " + (r + 1) + ", column " + (c + 1) + ": " + wc + (t ? ", tiled" : ", empty");
      if (o.wallActive) wallH += '<button type="button" class="' + cls + '" data-act="wall" data-r="' + r + '" data-c="' + c + '" data-k="w' + r + "-" + c + '" aria-label="' + lab + '">' + inner + "</button>";
      else wallH += '<span class="' + cls + '" data-k="w' + r + "-" + c + '" data-r="' + r + '" data-c="' + c + '"' + (t ? ' data-t="1"' : "") + ' role="img" aria-label="' + lab + '">' + inner + "</span>";
    }
    var floorH = "";
    for (i = 0; i < E.FLOOR_SPACES; i++) {
      var it = b.floor[i];
      floorH += '<span class="fspace">' + (it ? itemHTML(it, { k: "fl" + i, label: false }) : '<span class="hole" data-k="fl' + i + '"></span>') + '<span class="pen">' + AZ.minus(E.FLOOR_VALUES[i]) + "</span></span>";
    }
    var floorLab = "Floor line: " + AZ.plural(b.floor.length, "item") + " of " + E.FLOOR_SPACES;
    var floorBox = o.floorActive ? '<button type="button" class="floor" data-act="floor" aria-label="' + floorLab + '">' + floorH + "</button>" : '<div class="floor" role="img" aria-label="' + floorLab + '">' + floorH + "</div>";
    var A = function (name, inner, label) { return o.areas ? '<button type="button" class="area" data-act="area" data-area="' + name + '" aria-label="' + label + '">' + inner + "</button>" : inner; };
    var scoreH = '<span class="scorebox" data-k="score"><span class="k">Score</span><span class="v">' + b.score + "</span></span>";
    var top = '<div class="pb-top"><span class="who">' + (o.who || "Your board") + (o.markerMine ? " " + markerHTML({ cls: "xs", k: "pbm" }) : "") + "</span>" + A("score", scoreH, "Score track") + "</div>";
    var wallBox = '<div class="wall" data-k="wall">' + wallH + "</div>";
    if (o.only === "wall") return '<div class="pboard">' + (o.noTop ? "" : top) + wallBox + "</div>";
    if (o.only === "floor") return '<div class="pboard"><div class="floorwrap"><span class="flabel">Floor<br>line</span>' + floorBox + "</div></div>";
    return '<div class="pboard" data-k="board">' + top +
      '<div class="pb-main"><div style="display:grid;gap:3px">' + numsH + "</div>" + A("lines", '<div class="lines">' + linesH + "</div>", "Pattern lines") + A("wall", wallBox, "Wall") + "</div>" +
      A("floor", '<div class="floorwrap"><span class="flabel">Floor<br>line</span>' + floorBox + "</div>", "Floor line") + "</div>";
  }
  AZ.boardHTML = boardHTML;
  AZ.factoriesHTML = factoriesHTML;

  function paletteHTML(o) {
    return '<div class="palette">' + E.COLOURS.map(function (c) {
      var t = tileHTML(c, { k: "pal-" + c, label: false });
      return "<figure>" + (o.paletteActive ? '<button type="button" class="tilebtn" data-act="pal" data-colour="' + c + '" aria-label="' + c + ' tile, letter ' + LET[c] + '">' + t + "</button>" : t) +
        "<figcaption>" + c + " " + LET[c] + "</figcaption></figure>";
    }).join("") + "</div>";
  }

  /* ---------------- Table: a state + view with animated actions ---------------- */
  function Table(host, st, opt) {
    this.host = host; this.st = st; this.opt = opt || {}; this.hand = null; this.goal = null; this.extraMarks = null;
  }
  AZ.Table = Table;
  Table.prototype.board = function () { return this.st.boards[this.st.current]; };
  Table.prototype.html = function () {
    var o = this.opt, st = this.st, t = "", panels = [];
    if (o.palette) panels.push('<div class="panel"><div class="ptitle">Tiles: 20 of each colour</div>' + paletteHTML(o) + "</div>");
    if (o.factories) {
      var showCentre = o.centre !== false, hasF = st.factories.length > 0;
      panels.push('<div class="panel">' + (hasF ? '<div class="ptitle"><span>Factory displays</span><span class="cnt">' + st.factories.length + "</span></div>" + factoriesHTML(st, o) : "") +
        (showCentre ? '<div class="ptitle"' + (hasF ? ' style="margin-top:14px"' : "") + ">Centre of the table</div>" + centreHTML(st, o) : "") + "</div>");
    }
    if (o.hand) panels.push('<div class="panel">' + handHTML(this.hand) + "</div>");
    if (o.supply) panels.push(supplyHTML(o));
    if (o.note) panels.push('<div class="panel">' + o.note + "</div>");
    t += '<div class="table">' + panels.join("") + "</div>";
    if (o.board !== false) {
      var bo = Object.assign({}, o.boardOpt || {});
      ["linesActive", "floorActive", "wallActive", "areas", "markerMine", "only", "who", "hlLines"].forEach(function (k) { if (o[k] !== undefined) bo[k] = o[k]; });
      if (this.extraMarks) bo.marks = this.extraMarks;
      t += '<div class="boardcol" style="display:grid;min-width:0">' + boardHTML(this.board(), bo) + "</div>";
    }
    return t;
  };
  Table.prototype.render = function () {
    this.host.innerHTML = this.html();
    if (this.opt.board === false || (this.opt.factories === undefined && !this.opt.palette && !this.opt.hand && !this.opt.supply)) this.host.style.gridTemplateColumns = "minmax(0,1fr)";
    else this.host.style.gridTemplateColumns = "";
    this.applyGoal();
  };
  Table.prototype.applyGoal = function () {
    $$(".goal", this.host).forEach(function (e) { e.classList.remove("goal"); });
    if (this.goal) $$(this.goal, this.host).forEach(function (e) { e.classList.add("goal"); });
  };
  Table.prototype.rects = function (keys) {
    var m = {}, host = this.host;
    keys.forEach(function (k) { var el = host.querySelector('[data-k="' + k + '"]'); if (el) m[k] = el.getBoundingClientRect(); });
    return m;
  };
  /* moves: [{from: key, to: key, html}] with rects captured before the change */
  Table.prototype.fly = function (moves, rects) {
    var host = this.host;
    if (reduced || !moves.length) return Promise.resolve();
    return new Promise(function (resolve) {
      var left = 0;
      moves.forEach(function (m, i) {
        var fr = rects[m.from], t = host.querySelector('[data-k="' + m.to + '"]');
        if (!fr || !t) return;
        var tr = t.getBoundingClientRect();
        if (!tr.width) return;
        left++;
        t.style.visibility = "hidden";
        var d = document.createElement("div");
        d.className = "fly";
        d.style.left = fr.left + "px"; d.style.top = fr.top + "px"; d.style.width = fr.width + "px"; d.style.height = fr.height + "px";
        d.innerHTML = m.html; var inner = d.firstChild; if (inner && inner.style) inner.style.setProperty("--s", fr.width + "px");
        d.style.transitionDelay = (i * 45) + "ms";
        document.body.appendChild(d);
        requestAnimationFrame(function () { requestAnimationFrame(function () {
          d.style.transform = "translate(" + (tr.left - fr.left) + "px," + (tr.top - fr.top) + "px) scale(" + (tr.width / fr.width) + ")";
          d.style.transformOrigin = "0 0";
        }); });
        setTimeout(function () { d.remove(); t.style.visibility = ""; left--; if (!left) resolve(); }, 560 + i * 45);
      });
      if (!left) resolve();
    });
  };
  Table.prototype.pop = function (key, text, neg) {
    var el = this.host.querySelector('[data-k="' + key + '"]');
    if (!el) return;
    var r = el.getBoundingClientRect(), d = document.createElement("div");
    d.className = "pop" + (neg ? " neg" : ""); d.textContent = text;
    d.style.left = (r.left + r.width / 2) + "px"; d.style.top = (r.top + r.height / 2) + "px";
    document.body.appendChild(d); setTimeout(function () { d.remove(); }, 1250);
  };

  /* Take every tile of `colour` from source (factory index or "centre") into the hand. */
  Table.prototype.take = function (src, colour) {
    var st = this.st, b = this.board(), from = [], pushedFrom = [], restFrom = [], keys = [];
    var oldCentre = st.centre.length, floorBefore = b.floor.length, hadMarker = src === E.CENTRE && st.centre_marker;
    if (src === E.CENTRE) {
      st.centre.forEach(function (c, j) { if (c === colour) from.push("c" + j); else restFrom.push("c" + j); });
    } else {
      st.factories[src].forEach(function (c, j) { if (c === colour) from.push("f" + src + "-" + j); else pushedFrom.push({ k: "f" + src + "-" + j, c: c }); });
    }
    keys = from.concat(pushedFrom.map(function (p) { return p.k; }), restFrom, ["cm"]);
    var rects = this.rects(keys);
    var restColours = src === E.CENTRE ? st.centre.filter(function (c) { return c !== colour; }) : [];
    var info = E.takeTiles(st, src, colour);
    this.hand = { colour: colour, n: info.taken, marker: hadMarker && this.opt.board === false };
    this.lastTake = info;
    this.render();
    var moves = from.map(function (k, q) { return { from: k, to: "h" + q, html: tileHTML(colour, { label: false }) }; });
    pushedFrom.forEach(function (p, q) { moves.push({ from: p.k, to: "c" + (oldCentre + q), html: tileHTML(p.c, { label: false }) }); });
    restFrom.forEach(function (k, q) { moves.push({ from: k, to: "c" + q, html: tileHTML(restColours[q], { label: false }) }); });
    if (hadMarker) moves.push({ from: "cm", to: this.opt.board === false ? "hm" : "fl" + floorBefore, html: markerHTML({ label: false }) });
    Snd.play(pushedFrom.length ? "slide" : "clack");
    return this.fly(moves, rects).then(function () { return info; });
  };
  /* Put the hand into pattern line `line` (0-4) or E.FLOOR. */
  Table.prototype.place = function (line) {
    var st = this.st, b = this.board(), hand = this.hand, self = this;
    var before = line === E.FLOOR ? 0 : b.lines[line].count, floorBefore = b.floor.length;
    var keys = []; for (var q = 0; q < hand.n; q++) keys.push("h" + q);
    var rects = this.rects(keys);
    var info = E.placeTiles(st, hand.colour, hand.n, line);
    this.hand = null;
    this.render();
    var moves = [];
    for (q = 0; q < hand.n; q++) {
      var to = q < info.placed ? "l" + line + "-" + (before + q) : (floorBefore + q - info.placed < E.FLOOR_SPACES ? "fl" + (floorBefore + q - info.placed) : "lid");
      moves.push({ from: "h" + q, to: to, html: tileHTML(hand.colour, { label: false }) });
    }
    Snd.play("place");
    return this.fly(moves, rects).then(function () {
      if (info.to_floor) { Snd.play("lose"); }
      self.lastPlace = info; return info;
    });
  };
  /* Phase B for one complete pattern line: rightmost tile to the wall, score it, the rest to the box lid. */
  Table.prototype.tileLine = function (row) {
    var st = this.st, b = this.board(), pl = b.lines[row], colour = pl.colour, n = pl.count, self = this;
    var col = E.wallColumn(row, colour);
    var keys = []; for (var s = 0; s < n; s++) keys.push("l" + row + "-" + s);
    var rects = this.rects(keys);
    b.wall[row][col] = colour;
    var d = E.scoreDetail(b.wall, row, col);
    b.score += d.points;
    for (s = 0; s < n - 1; s++) st.lid.push(colour);
    pl.colour = null; pl.count = 0;
    if (this.opt.supply && this.opt.supply.lid !== undefined) this.opt.supply.lid = st.lid.length;
    this.extraMarks = { h: d.h > 1 ? d.across : [], v: d.v > 1 ? d.down : [], pick: d.lone ? [[row, col]] : [] };
    this.render();
    var moves = [{ from: "l" + row + "-0", to: "w" + row + "-" + col, html: tileHTML(colour, { label: false }) }];
    for (s = 1; s < n; s++) moves.push({ from: "l" + row + "-" + s, to: "lid", html: tileHTML(colour, { label: false }) });
    return this.fly(moves, rects).then(function () {
      self.pop("w" + row + "-" + col, "+" + d.points); Snd.play("score", d.points);
      return { row: row, col: col, colour: colour, detail: d, points: d.points, to_lid: n - 1 };
    });
  };
  /* Floor line penalty at the end of phase B. */
  Table.prototype.payFloor = function () {
    var st = this.st, b = this.board(), items = b.floor.slice(), self = this;
    var keys = items.map(function (x, i) { return "fl" + i; });
    var rects = this.rects(keys);
    var pen = E.floorPenalty(items.length), before = b.score;
    b.score = Math.max(0, b.score + pen);
    items.forEach(function (t) { if (t !== E.MARKER) st.lid.push(t); });
    b.floor = [];
    var hadMarker = items.indexOf(E.MARKER) >= 0;
    if (hadMarker) this.opt.markerMine = true;
    if (this.opt.supply && this.opt.supply.lid !== undefined) this.opt.supply.lid = st.lid.length;
    this.render();
    var moves = items.map(function (x, i) { return { from: "fl" + i, to: x === E.MARKER ? "pbm" : "lid", html: itemHTML(x, { label: false }) }; });
    if (pen) { this.pop("score", AZ.minus(pen), true); Snd.play("lose"); }
    return this.fly(moves, rects).then(function () { return { items: items.length, penalty: pen, before: before, score: b.score, marker: hadMarker }; });
  };

  /* Text for a scored tile: "across 3 + down 2 = 5" */
  AZ.detailText = function (d) {
    if (d.lone) return "no neighbours = 1";
    var parts = [];
    if (d.h > 1) parts.push("across " + d.h);
    if (d.v > 1) parts.push("down " + d.v);
    return parts.join(" + ") + " = " + d.points;
  };
  AZ.floorText = function (n) {
    var vals = E.FLOOR_VALUES.slice(0, Math.min(n, E.FLOOR_SPACES)).map(function (v) { return Math.abs(v); });
    return vals.length ? vals.join(" + ") + " = " + E.floorPenalty(n) * -1 : "0";
  };

  AZ.parseAct = function (el) {
    var d = el.dataset, a = { kind: d.act, el: el };
    if (d.src !== undefined) a.src = d.src === "centre" ? E.CENTRE : +d.src;
    if (d.colour) a.colour = d.colour;
    if (d.line !== undefined) a.line = +d.line;
    if (d.r !== undefined) { a.r = +d.r; a.c = +d.c; }
    if (d.area) a.area = d.area;
    if (d.i !== undefined) a.i = +d.i;
    if (d.id) a.id = d.id;
    return a;
  };
  /* Answer options: the correct number plus up to three distinct positive distractors, in order. */
  AZ.numOptions = function (correct, cands) {
    var out = [correct];
    cands.forEach(function (x) { if (out.length < 4 && x > 0 && out.indexOf(x) < 0) out.push(x); });
    for (var d = 1; out.length < 4; d++) { if (out.indexOf(correct + d) < 0) out.push(correct + d); if (out.length < 4 && correct - d > 0 && out.indexOf(correct - d) < 0) out.push(correct - d); }
    return out.sort(function (a, b) { return a - b; });
  };
  AZ.placeMsg = function (b, line, colour) {
    var code = E.placeReason(b, line, colour), pl = b.lines[line], n = line + 1;
    if (code === "full") return "Pattern line " + n + " is already full.";
    if (code === "other") return "Pattern line " + n + " already holds " + pl.colour + ". A line holds one colour only.";
    if (code === "wall") return "Row " + n + " of your wall already has a " + colour + " tile, so " + colour + " can't go in pattern line " + n + ".";
    return null;
  };

  /* ---------------- rules overlay ---------------- */
  function rulesHTML() {
    var F = E.FACTORIES, fv = E.FLOOR_VALUES, tot = [];
    for (var n = 1; n <= E.FLOOR_SPACES; n++) tot.push(-E.floorPenalty(n));
    return '<div class="sheet" tabindex="-1"><div class="sheethead"><h2 id="rulesTitle">Azul rules in plain words</h2><button class="btn small" type="button" data-close>Close</button></div>' +
      "<p><b>Goal:</b> collect tiles, fill your pattern lines, and move tiles to your wall for points. The game ends after the round in which someone completes a row across their wall. Most points wins.</p>" +
      '<h3>Words</h3><dl class="words">' +
      "<div><dt>Tile:</dt> <dd>a square piece. 100 tiles, " + E.TILES_PER_COLOUR + " in each colour: blue B, yellow Y, red R, black K, white W.</dd></div>" +
      "<div><dt>Factory display:</dt> <dd>a round disc in the middle of the table. Tiles are offered on it.</dd></div>" +
      "<div><dt>Centre of the table:</dt> <dd>the space inside the ring of factory displays.</dd></div>" +
      "<div><dt>Pattern lines:</dt> <dd>the five rows of spaces on the left of your board. Line 1 has 1 space, line 5 has 5.</dd></div>" +
      "<div><dt>Wall:</dt> <dd>the 5 by 5 grid on the right. Each space shows the colour that belongs there.</dd></div>" +
      "<div><dt>Floor line:</dt> <dd>the seven spaces at the bottom. Tiles you can't use go here and cost points.</dd></div>" +
      "<div><dt>Starting player marker:</dt> <dd>a token with a 1. Whoever has it goes first next round. It is not a tile.</dd></div>" +
      "<div><dt>Box lid:</dt> <dd>where used tiles wait until the bag runs empty.</dd></div></dl>" +
      "<h3>Setup</h3><ul><li>Everyone uses the same side of the player board. Score markers start on 0.</li>" +
      "<li>Factory displays: " + F[2] + " for 2 players, " + F[3] + " for 3 players, " + F[4] + " for 4 players.</li>" +
      "<li>All tiles go in the bag. The starting player takes the marker and puts " + E.TILES_PER_FACTORY + " tiles on each factory display.</li></ul>" +
      "<h3>A. Factory offer (take tiles)</h3><ul><li>The starting player puts the marker in the centre and goes first. Then turns go clockwise (to the left).</li>" +
      "<li>On your turn, take <b>all</b> tiles of <b>one colour</b> from one factory display. Push the rest of that display into the centre. Or take all tiles of one colour from the centre.</li>" +
      "<li>The first player to take from the centre also takes the starting player marker. It goes on the leftmost free space of their floor line.</li>" +
      "<li>Put all the tiles you took into <b>one</b> pattern line, from right to left. A line holds one colour. You can't use a colour that is already in that row of your wall.</li>" +
      "<li>Tiles that don't fit go to your floor line. You may also put them all on the floor line.</li>" +
      "<li>This phase ends when every factory display and the centre are empty.</li></ul>" +
      "<h3>B. Wall-tiling (score)</h3><ul><li>Go through your pattern lines from top to bottom.</li>" +
      "<li>A <b>complete</b> line (every space full) moves its rightmost tile to the space of the same colour in the wall row beside it. The other tiles of that line go to the box lid.</li>" +
      "<li>Lines that aren't complete keep their tiles for the next round.</li>" +
      "<li>A new wall tile with no neighbours scores 1. Otherwise count the unbroken line of tiles across it and the unbroken line down it (each only if it is 2 or more) and add them.</li>" +
      "<li>Then lose points for your floor line. Your score never goes below 0. Floor tiles go to the box lid; the marker stays with you.</li></ul>" +
      '<div class="tscroll"><table class="mini"><tr><th>Floor space</th>' + fv.map(function (v, i) { return "<th>" + (i + 1) + "</th>"; }).join("") + "</tr><tr><td>Costs</td>" + fv.map(function (v) { return "<td>" + AZ.minus(v) + "</td>"; }).join("") +
      "</tr><tr><td>Total lost</td>" + tot.map(function (v) { return "<td>" + v + "</td>"; }).join("") + "</tr></table></div>" +
      "<p>Tiles beyond the seventh floor space go straight to the box lid and cost nothing more.</p>" +
      "<h3>C. Prepare the next round</h3><ul><li>If nobody has completed a row across their wall, the player with the marker fills every factory display with " + E.TILES_PER_FACTORY + " tiles again.</li>" +
      "<li>If the bag runs empty while filling, pour every tile from the box lid into the bag and keep going.</li></ul>" +
      "<h3>End of the game</h3><ul><li>The game ends after wall-tiling in the round when someone completes a row <b>across</b>. A full column does not end it.</li>" +
      "<li>Bonuses: +" + E.ROW_BONUS + " for each complete row, +" + E.COLUMN_BONUS + " for each complete column, +" + E.COLOUR_BONUS + " for each colour with all 5 tiles on your wall.</li>" +
      "<li>Most points wins. If tied, the tied player with more complete rows wins. Still tied: you share the win.</li></ul>" +
      '<p class="why">Full rules: the English player manual (docs/azul/manual.md). This page is an unofficial learning aid with its own tile designs.</p>' +
      '<div class="row-btns"><button class="btn primary" type="button" data-close>Back to where I was</button></div></div>';
  }
  var lastFocus = null;
  AZ.openRules = function () {
    var o = $("#rules");
    lastFocus = document.activeElement;
    o.innerHTML = rulesHTML(); o.hidden = false;
    setTimeout(function () { var s = $(".sheet", o); s.scrollTop = 0; s.focus(); }, 10);
    Snd.ensure(); Snd.play("tap");
  };
  AZ.closeRules = function () { var o = $("#rules"); o.hidden = true; o.innerHTML = ""; if (lastFocus && lastFocus.focus) lastFocus.focus(); };

  /* ---------------- navigation ---------------- */
  AZ.screens = ["home", "lesson", "bridge", "puzzle", "rush"];
  AZ.leaveHooks = [];
  AZ.show = function (id, where) {
    AZ.leaveHooks.forEach(function (f) { try { f(id); } catch (e) { /* ignore */ } });
    AZ.screens.forEach(function (s) { $("#" + s).hidden = s !== id; });
    $("#homeBtn").hidden = id === "home";
    $("#where").textContent = where ? "· " + where : "";
    window.scrollTo(0, 0);
  };
})();
