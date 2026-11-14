"""Explore puzzle positions with the Python engine. usage: python3 design.py puzzles.json"""
import copy, importlib.util, json, sys
spec = importlib.util.spec_from_file_location("azul_engine", "/home/user/Boardgames/tools/azul/engine.py")
E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)


def make(p):
    b = E.new_board()
    b["score"] = p["board"].get("score", 0)
    for r, s in enumerate(p["board"].get("wall", [])):
        for c, ch in enumerate(s):
            if ch != ".":
                b["wall"][r][c] = E.wall_colour(r, c)
    for i, l in enumerate(p["board"].get("lines", [])):
        if l:
            b["lines"][i] = {"colour": l[0], "count": l[1]}
    b["floor"] = list(p["board"].get("floor", []))
    st = {"variant": "coloured", "n": 1, "factories": copy.deepcopy(p.get("factories", [])), "centre": list(p.get("centre", [])),
          "centre_marker": p.get("centre_marker", True), "marker_holder": None, "start_player": 0, "current": 0,
          "boards": [b], "lid": [], "bag": [], "phase": "offer", "game_over": False, "round": 1}
    return st


def value(st, m, final):
    s = copy.deepcopy(st)
    before = s["boards"][0]["score"]
    E.apply_move(s, m)
    s["phase"] = "tiling"
    E.tile_wall(s, 0)
    b = s["boards"][0]
    if final:
        b["score"] += E.end_bonus(b["wall"])
    return b["score"] - before


def solve(p):
    if p.get("kind") == "score":
        w = E.empty_wall()
        for r, s in enumerate(p["wall"]):
            for c, ch in enumerate(s):
                if ch != ".":
                    w[r][c] = E.wall_colour(r, c)
        r, c = p["tile"]
        return {"answer": E.score_placement(w, r, c)}
    st = make(p)
    vals = sorted(((value(st, m, p.get("final", False)), [m.source, m.colour, m.line]) for m in E.legal_moves(st)),
                  key=lambda x: -x[0])
    return {"best": vals[0][0], "values": vals}


if __name__ == "__main__":
    ps = json.load(open(sys.argv[1]))
    for p in ps:
        res = solve(p)
        print("==", p["id"], p.get("title"))
        if "answer" in res:
            print("  answer", res["answer"])
        else:
            for v, m in res["values"][:int(sys.argv[2]) if len(sys.argv) > 2 else 8]:
                print("  ", v, m)
