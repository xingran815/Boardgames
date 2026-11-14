"""Generate random cases with the Python Azul engine for verify.js."""
import copy, importlib.util, json, random, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("azul_engine", "/home/user/Boardgames/tools/azul/engine.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)

rng = random.Random(20261114)
out = {"score": [], "floor": [], "bonus": [], "moves": [], "tiling": [], "evaluate": [], "reason": []}


def rand_wall(density):
    w = E.empty_wall()
    for r in range(5):
        for c in range(5):
            if rng.random() < density:
                w[r][c] = E.wall_colour(r, c)
    return w


for i in range(800):
    w = rand_wall(rng.choice([0.1, 0.3, 0.5, 0.7, 0.9]))
    r, c = rng.randrange(5), rng.randrange(5)
    out["score"].append({"wall": w, "r": r, "c": c, "pts": E.score_placement(w, r, c)})
for n in range(0, 13):
    out["floor"].append({"n": n, "pen": E.floor_penalty(n)})
for i in range(600):
    w = rand_wall(rng.choice([0.5, 0.8, 0.9, 0.95, 1.0]))
    out["bonus"].append({"wall": w, "bd": E.bonus_breakdown(w)})


def snap(st):
    s = E.snapshot(st)
    return json.loads(json.dumps(s))


def jmove(m):
    return [m.source, m.colour, m.line]


def eval_py(st, m, final):
    s = copy.deepcopy(st)
    before = s["boards"][s["current"]]["score"]
    p = s["current"]
    E.apply_move(s, m)
    s["phase"] = "tiling"
    E.tile_wall(s, p)
    b = s["boards"][p]
    if final:
        b["score"] += E.end_bonus(b["wall"])
    return b["score"] - before


games = 0
for seed in range(260):
    n = rng.choice([2, 3, 4])
    st = E.new_game(n, seed)
    games += 1
    rounds = 0
    while not st["game_over"] and rounds < 30:
        while st["phase"] == "offer":
            moves = E.legal_moves(st)
            m = rng.choice(moves)
            if rng.random() < 0.12:
                pre = snap(st)
                legal = sorted(json.dumps(jmove(x)) for x in moves)
                pre_eval = copy.deepcopy(st)
                final = rng.random() < 0.3
                out["evaluate"].append({"state": pre, "move": jmove(m), "final": final,
                                        "value": eval_py(pre_eval, m, final)})
                post = copy.deepcopy(st)
                info = E.apply_move(post, m)
                out["moves"].append({"state": pre, "legal": legal, "move": jmove(m),
                                     "info": {k: info[k] for k in ("taken", "pushed", "placed", "to_floor", "to_lid", "took_marker")},
                                     "after": snap(post)})
                # place reasons for every line/colour on current board
                b = st["boards"][st["current"]]
                out["reason"].append({"board": json.loads(json.dumps(b)),
                                      "can": [[E.can_place(b, l, c) for c in E.COLOURS] for l in range(5)]})
            E.apply_move(st, m)
        if st["phase"] == "tiling":
            pre = snap(st)
            res = E.tile_walls(st)
            out["tiling"].append({"state": pre, "results": json.loads(json.dumps(res)), "after": snap(st)})
        if st["phase"] == "prepare":
            E.start_round(st)
        rounds += 1

json.dump(out, open(sys.argv[1], "w"))
print({k: len(v) for k, v in out.items()}, "games", games)
