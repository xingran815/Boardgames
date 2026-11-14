// Playwright run-through of docs/azul/learn.html.
// usage: node test.js [width] [height] [light|dark] [reduce|no-preference] [shots]
const { chromium } = require("/opt/node22/lib/node_modules/playwright");
const fs = require("fs");
const path = require("path");
const DIR = __dirname;
const [W = 1280, H = 800, SCHEME = "light", MOTION = "reduce", SHOTS = ""] = process.argv.slice(2);
const tag = `${W}-${SCHEME}`;
const src = fs.readFileSync("/home/user/Boardgames/docs/azul/learn.html", "utf8");
// Same skeleton the artifact host wraps around the page.
const wrapped = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><style>:root{color-scheme:light;padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)}body{margin:0;font:14px system-ui}img{max-width:100%}[hidden]{display:none!important}</style></head><body>${src}</body></html>`;
fs.writeFileSync(path.join(DIR, "wrapped.html"), wrapped);
const shotDir = path.join(DIR, "shots"); fs.mkdirSync(shotDir, { recursive: true });

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: +W, height: +H }, colorScheme: SCHEME, reducedMotion: MOTION, hasTouch: +W < 600 });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  page.on("console", (m) => { if (m.type() === "error" && !/fonts\.g|ERR_FAILED|net::/.test(m.text())) errors.push("console: " + m.text()); });
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (r) => r.abort());
  await page.goto("file://" + path.join(DIR, "wrapped.html"));
  await page.evaluate(() => { try { localStorage.clear(); } catch (e) {} });
  await page.reload();
  const stats = { lessons: 0, wrongActions: 0, wrongChoices: 0, nexts: 0, puzzles: 0, puzzleWrong: 0, rushQ: 0, overflow: [] };
  const wait = (ms) => page.waitForTimeout(MOTION === "reduce" ? Math.min(ms, 120) : ms);
  async function shot(name) { if (SHOTS) await page.screenshot({ path: path.join(shotDir, `${tag}-${name}.png`), fullPage: false }); }
  async function checkOverflow(where) {
    const o = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (o > 0) stats.overflow.push(where + ":" + o);
  }
  await shot("home");
  await checkOverflow("home");

  // ---------- lessons ----------
  const nLessons = await page.evaluate(() => AZ.LESSONS.length);
  for (let li = 0; li < nLessons; li++) {
    await page.evaluate((i) => AZ.openLesson(i), li);
    await wait(300);
    let guard = 0, triedWrongFor = "", shotN = 0;
    while (guard++ < 200) {
      if (await page.$("#lEnd .remember")) break;
      const say = await page.$eval("#cSay", (e) => e.textContent).catch(() => "");
      // multiple choice: click each button in order until one is right
      const choices = await page.$$("#cChoices:not([hidden]) .btn:not([disabled]):not(.wrong)");
      if (choices.length && !(await page.$("#cChoices .right"))) {
        for (const c of choices) {
          await c.click(); await wait(200);
          if (await c.evaluate((e) => e.classList.contains("right"))) break;
          stats.wrongChoices++;
          const m = await page.$eval("#cMsg", (e) => (e.hidden ? "" : e.textContent));
          if (!m) throw new Error("wrong choice gave no message in lesson " + (li + 1));
        }
        await wait(600);
        continue;
      }
      const goal = await page.$("#lStage .goal");
      if (goal) {
        if (triedWrongFor !== say) {
          triedWrongFor = say;
          // try a wrong action: any other active control in the stage
          const others = await page.$$('#lStage [data-act]:not(.goal)');
          for (const o of others) {
            const isGoalChild = await o.evaluate((e) => !!e.closest(".goal") || !!e.querySelector(".goal"));
            if (isGoalChild) continue;
            const box = await o.boundingBox(); if (!box) continue;
            await o.click(); await wait(150);
            const m = await page.$eval("#cMsg", (e) => (e.hidden ? "" : e.textContent));
            if (m) { stats.wrongActions++; break; }
          }
          if (SHOTS && shotN++ < 2) await shot(`lesson${li + 1}-${shotN}`);
        }
        const g = await page.$("#lStage .goal");
        if (g) { await g.click(); await wait(700); }
        continue;
      }
      const next = await page.$("#cNext");
      if (next) { await next.click(); stats.nexts++; await wait(400); continue; }
      // no goal: find-the-bonus steps tap every wall button until progress
      const walls = await page.$$('#lStage [data-act="wall"]');
      if (walls.length) {
        for (let k = 0; k < walls.length; k++) {
          const ws = await page.$$('#lStage [data-act="wall"]');
          if (!ws[k]) break;
          await ws[k].click(); await wait(120);
          const now = await page.$eval("#cSay", (e) => e.textContent).catch(() => "");
          if (now !== say || (await page.$("#cNext"))) break;
        }
        continue;
      }
      await wait(300);
    }
    if (!(await page.$("#lEnd .remember"))) throw new Error("lesson " + (li + 1) + " did not finish: " + (await page.$eval("#cSay", (e) => e.textContent)));
    stats.lessons++;
    await checkOverflow("lesson" + (li + 1));
    if (SHOTS) await shot(`lesson${li + 1}-remember`);
  }

  // ---------- skip path on a fresh profile ----------
  await page.evaluate(() => { localStorage.clear(); AZ.Save.reset(); AZ.goHome(); });
  const skip = await page.$('[data-go="skip"]');
  if (!skip) throw new Error("no skip button");
  await skip.click(); await wait(200);
  if (await page.$eval("#bridge", (e) => e.hidden)) throw new Error("skip did not open the bridge");
  await shot("bridge");

  // ---------- puzzles ----------
  const puzzles = await page.evaluate(() => AZ.PUZZLES.map((p) => ({ id: p.id, kind: p.kind })));
  for (let pi = 0; pi < puzzles.length; pi++) {
    await page.evaluate((i) => AZ.openPuzzle(i), pi);
    await wait(200);
    await page.click("#pHint"); await wait(100);
    const hint = await page.$eval("#pMsg", (e) => e.textContent);
    if (!/Hint/.test(hint)) throw new Error("no hint");
    if (puzzles[pi].kind === "score") {
      const btns = await page.$$("#pChoices .btn");
      for (const b of btns) { await b.click(); await wait(150); if (await page.$("#pCard")) break; stats.puzzleWrong++; }
    } else {
      // pass 1: a deliberately worst move (first illegal line attempt, then floor)
      const sol = await page.evaluate(() => { const P = AZ.PUZZLES; return null; });
      const plan = await page.evaluate((i) => {
        const E = AzulEngine, def = AZ.PUZZLES[i];
        const st = E.makeState({ board: E.makeBoard(def.board), factories: def.factories || [], centre: def.centre || [], centre_marker: def.centre_marker !== false });
        const S = E.solve(st, !!def.final);
        const worst = S.all.slice().sort((a, b) => a.value - b.value)[0];
        return { best: S.bestMoves[0].move, bestValue: S.best, worst: worst.move, worstValue: worst.value, n: S.all.length };
      }, pi);
      async function doMove(m, tryIllegal) {
        const sel = `#pStage [data-act="take"][data-src="${m.source}"][data-colour="${m.colour}"]`;
        await page.click(sel); await wait(500);
        if (tryIllegal) {
          // find a line that is illegal for this colour, click it, expect a message
          const bad = await page.evaluate(([i, colour]) => {
            const E = AzulEngine, b = E.makeBoard(AZ.PUZZLES[i].board);
            return [0, 1, 2, 3, 4].filter((l) => E.placeReason(b, l, colour));
          }, [pi, m.colour]);
          for (const l of bad) {
            await page.click(`#pStage [data-act="line"][data-line="${l}"]`); await wait(150);
            const msg = await page.$eval("#pMsg", (e) => (e.hidden ? "" : e.textContent));
            if (!msg || /Hint/.test(msg)) throw new Error("illegal line gave no reason");
            stats.puzzleWrong++; break;
          }
        }
        if (!(await page.$("#pCard"))) {
          await page.click(m.line === "floor" ? '#pStage [data-act="floor"]' : `#pStage [data-act="line"][data-line="${m.line}"]`);
        }
        await page.waitForSelector("#pCard", { timeout: 15000 });
      }
      await doMove(plan.worst, true);
      const s1 = await page.$$eval("#pCard .stars .off", (x) => x.length);
      await page.click("#pAgain"); await wait(200);
      await doMove(plan.best, false);
      const s2 = await page.$$eval("#pCard .stars .off", (x) => x.length);
      if (s2 !== 0) throw new Error("best move did not get 3 stars in puzzle " + (pi + 1));
      if (plan.worstValue < plan.bestValue && s1 === 0) throw new Error("worst move got 3 stars in puzzle " + (pi + 1));
      // replay the best move once
      if (pi === 0 || pi === puzzles.length - 1) { await page.click("#pAgain"); await doMove(plan.worst, false); await page.click("#pWatch"); await page.waitForSelector("#pCard", { timeout: 20000 }); }
    }
    stats.puzzles++;
    await checkOverflow("puzzle" + (pi + 1));
    if (SHOTS) await shot(`puzzle${pi + 1}`);
  }

  // ---------- rules overlay from every screen ----------
  for (const s of ["home", "lesson", "puzzle", "rush", "bridge"]) {
    await page.evaluate((s) => { if (s === "home") AZ.goHome(); if (s === "lesson") AZ.openLesson(2); if (s === "puzzle") AZ.openPuzzle(3); if (s === "rush") AZ.openRush(); if (s === "bridge") AZ.openBridge(); }, s);
    await wait(200);
    await page.click("#rulesBtn"); await wait(150);
    if (await page.$eval("#rules", (e) => e.hidden)) throw new Error("rules did not open on " + s);
    if (s === "lesson") await shot("rules");
    await page.keyboard.press("Escape"); await wait(100);
    if (!(await page.$eval("#rules", (e) => e.hidden))) throw new Error("rules did not close on " + s);
  }

  // ---------- quick-fire ----------
  for (const mode of ["tile", "floor"]) {
    await page.evaluate((m) => AZ.openRush(m), mode);
    await wait(200);
    let q = 0;
    while (q < 40) {
      const st = await page.evaluate(() => { const R = AZ.rushState(); return R ? { ans: R.q.answer, lives: R.lives, locked: R.locked, kind: R.q.kind, q: R.q } : null; });
      if (!st) break;
      if (st.locked) { await page.waitForTimeout(250); continue; }
      // check the answer against the engine independently
      const check = await page.evaluate(() => {
        const R = AZ.rushState(), E = AzulEngine, q = R.q;
        if (q.kind === "tile") { const w = E.clone(q.wall); w[q.at[0]][q.at[1]] = null; return E.scorePlacement(w, q.at[0], q.at[1]); }
        return -E.floorPenalty(q.items.length + q.extra);
      });
      if (check !== st.ans) throw new Error("rush answer mismatch");
      q++; stats.rushQ++;
      if (q === 2 && SHOTS) await shot("rush-" + mode);
      // answer right a few times, then wrong until game over
      const right = q < 6;
      const key = await page.evaluate((right) => { const btns = [...document.querySelectorAll("#rBox [data-rans]")]; const R = AZ.rushState(); const i = btns.findIndex((b) => (+b.dataset.rans === R.q.answer) === right); return i + 1; }, right);
      await page.keyboard.press(String(key));
      await page.waitForTimeout(MOTION === "reduce" ? 1300 : 2400);
    }
    if (!(await page.$("#rAgain"))) throw new Error("rush did not reach game over");
    if (SHOTS) await shot("rush-over-" + mode);
  }
  // timeout path once
  await page.evaluate(() => AZ.openRush("floor"));
  await page.waitForTimeout(16500);
  const lives = await page.evaluate(() => AZ.rushState() && AZ.rushState().lives);
  if (lives !== 2) throw new Error("timeout did not cost a life: " + lives);
  await page.evaluate(() => AZ.goHome());
  await shot("home-after");
  await checkOverflow("home-after");

  console.log(JSON.stringify({ tag, motion: MOTION, stats, errors }, null, 1));
  await browser.close();
  process.exit(errors.length || stats.overflow.length ? 1 : 0);
})().catch((e) => { console.error("TEST FAILED:", e.message); process.exit(2); });
