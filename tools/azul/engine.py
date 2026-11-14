"""Rules engine + simple AI for Azul (2-4 players).

Single source of truth for every number quoted in docs/azul/ (manual, quick
reference, later the colour manual, HTML pages and videos).

Rules follow the photographed German rulebook (Plan B Games / Next Move,
2018, distributed by Pegasus Spiele), cross-checked against the published
English rules. The two agree on every number; see docs/azul/manual.md.

Coordinates: rows and columns are 0-based in code (row 0 = top row / the
1-space pattern line, col 0 = leftmost wall column). Docs count from 1.

Quick API for later agents
--------------------------
    wall_colour(row, col)          colour printed on the coloured wall
    wall_column(row, colour)       column of that colour in a row (coloured wall)
    score_placement(wall, row, col)  points for a tile placed at (row, col)
    floor_penalty(n)               total (negative) for n items on the floor line
    end_bonus(wall) / bonus_breakdown(wall)
    complete_rows(wall)            count of full horizontal rows (tie-break)
    new_game(n_players, seed, variant) -> state  (factories filled, ready)
    legal_moves(state) -> [Move]   apply_move(state, move) -> info
    tile_walls(state) -> info      (phase B for every player)
    winners(state) -> [player]     after the game ended
    Game(n_players, seed, variant).play() -> log   (seeded AI game)
"""
from __future__ import annotations

import copy
import random
from collections import Counter, namedtuple

# ---------------------------------------------------------------- constants
COLOURS = ("blue", "yellow", "red", "black", "white")
LETTERS = {"blue": "B", "yellow": "Y", "red": "R", "black": "K", "white": "W"}
TILES_PER_COLOUR = 20
TOTAL_TILES = TILES_PER_COLOUR * len(COLOURS)  # 100
SIZE = 5                                        # wall is 5 x 5, 5 pattern lines
TILES_PER_FACTORY = 4
FACTORIES = {2: 5, 3: 7, 4: 9}                  # factory displays per player count
FLOOR_VALUES = (-1, -1, -2, -2, -2, -3, -3)     # printed above the 7 floor spaces
FLOOR_SPACES = len(FLOOR_VALUES)
ROW_BONUS, COLUMN_BONUS, COLOUR_BONUS = 2, 7, 10
MARKER = "marker"                               # the starting player marker
CENTRE = "centre"                               # source: centre of the table
FLOOR = "floor"                                 # target: floor line
COLOURED, GREY = "coloured", "grey"             # board sides (grey = variant)

Move = namedtuple("Move", "source colour line")
Move.__doc__ = ("source: factory index (int) or CENTRE; colour; "
                "line: pattern line 0-4 or FLOOR")


# ---------------------------------------------------------------- wall maths
def wall_colour(row, col):
    """Colour printed on the coloured wall at (row, col).

    Row 0 reads blue, yellow, red, black, white; each row below is the row
    above shifted one space to the right.
    """
    return COLOURS[(col - row) % SIZE]


def wall_column(row, colour):
    """Column where `colour` goes in `row` on the coloured wall."""
    return (COLOURS.index(colour) + row) % SIZE


def empty_wall():
    return [[None] * SIZE for _ in range(SIZE)]


def _filled(wall, r, c, extra):
    return (r, c) == extra or (0 <= r < SIZE and 0 <= c < SIZE and wall[r][c] is not None)


def score_placement(wall, row, col):
    """Points for placing a tile at (row, col).

    `wall` may or may not already contain the new tile. A tile with no
    horizontal or vertical neighbour scores 1. Otherwise it scores the length
    of its horizontal run (if >= 2) plus the length of its vertical run
    (if >= 2), both counting the new tile itself.
    """
    here = (row, col)
    h = 1
    c = col - 1
    while _filled(wall, row, c, here):
        h += 1
        c -= 1
    c = col + 1
    while _filled(wall, row, c, here):
        h += 1
        c += 1
    v = 1
    r = row - 1
    while _filled(wall, r, col, here):
        v += 1
        r -= 1
    r = row + 1
    while _filled(wall, r, col, here):
        v += 1
        r += 1
    if h == 1 and v == 1:
        return 1
    return (h if h > 1 else 0) + (v if v > 1 else 0)


def floor_penalty(n):
    """Total penalty (a negative int, or 0) for n items on the floor line.

    Only the 7 floor spaces count; n above 7 is treated as 7 (extra tiles go
    to the box lid without a penalty)."""
    return sum(FLOOR_VALUES[:max(0, min(n, FLOOR_SPACES))])


def complete_rows(wall):
    return sum(all(t is not None for t in wall[r]) for r in range(SIZE))


def complete_columns(wall):
    return sum(all(wall[r][c] is not None for r in range(SIZE)) for c in range(SIZE))


def complete_colours(wall):
    n = Counter(t for row in wall for t in row if t is not None)
    return sum(1 for col in COLOURS if n[col] == SIZE)


def bonus_breakdown(wall):
    rows, cols, colours = complete_rows(wall), complete_columns(wall), complete_colours(wall)
    return {"rows": rows, "columns": cols, "colours": colours,
            "row_points": rows * ROW_BONUS, "column_points": cols * COLUMN_BONUS,
            "colour_points": colours * COLOUR_BONUS,
            "total": rows * ROW_BONUS + cols * COLUMN_BONUS + colours * COLOUR_BONUS}


def end_bonus(wall):
    """End-of-game bonus: +2 per full row, +7 per full column, +10 per colour
    with all 5 tiles on the wall."""
    return bonus_breakdown(wall)["total"]


def wall_from_rows(rows):
    """Build a wall from 5 strings, e.g. ['B....', '.B...', ...]. Any letter
    marks a placed tile; on a coloured wall the colour is taken from the
    printed pattern, so only the position matters. '.' = empty."""
    w = empty_wall()
    rev = {v: k for k, v in LETTERS.items()}
    for r, s in enumerate(rows):
        for c, ch in enumerate(s):
            if ch != ".":
                w[r][c] = rev.get(ch, wall_colour(r, c))
    return w


def wall_to_rows(wall):
    return ["".join(LETTERS[t] if t else "." for t in row) for row in wall]


# ---------------------------------------------------------------- boards
def new_board():
    return {
        "score": 0,
        "lines": [{"colour": None, "count": 0} for _ in range(SIZE)],
        "wall": empty_wall(),
        "floor": [],  # up to 7 items: colours and/or MARKER
    }


def line_capacity(line):
    return line + 1


def grey_columns(wall, row, colour):
    """Grey-wall variant: free columns in `row` where `colour` may go
    (the column must not already hold that colour)."""
    if colour in wall[row]:
        return []
    return [c for c in range(SIZE) if wall[row][c] is None
            and all(wall[r][c] != colour for r in range(SIZE))]


def can_place(board, line, colour):
    """May tiles of `colour` go into pattern line `line` (with room left)?"""
    pl = board["lines"][line]
    if pl["count"] >= line_capacity(line):
        return False
    if pl["colour"] is not None and pl["colour"] != colour:
        return False
    return colour not in board["wall"][line]


def board_tiles(board):
    """Tiles (not the marker) on a player board: wall + pattern lines + floor."""
    n = sum(1 for row in board["wall"] for t in row if t is not None)
    n += sum(pl["count"] for pl in board["lines"])
    n += sum(1 for x in board["floor"] if x != MARKER)
    return n


# ---------------------------------------------------------------- state
def new_state(n_players=2, seed=0, variant=COLOURED, first_player=0):
    if n_players not in FACTORIES:
        raise ValueError("Azul is for 2, 3 or 4 players")
    if variant not in (COLOURED, GREY):
        raise ValueError("variant must be 'coloured' or 'grey'")
    rng = random.Random(seed)
    bag = [c for c in COLOURS for _ in range(TILES_PER_COLOUR)]
    rng.shuffle(bag)
    return {
        "n": n_players,
        "variant": variant,
        "bag": bag,              # draw order is random.Random(seed) based
        "lid": [],
        "factories": [[] for _ in range(FACTORIES[n_players])],
        "centre": [],
        "centre_marker": False,  # is the starting player marker in the centre?
        "marker_holder": first_player,  # who holds the marker (between rounds)
        "start_player": first_player,
        "current": first_player,
        "boards": [new_board() for _ in range(n_players)],
        "round": 0,
        "phase": "setup",
        "game_over": False,
        "rng_state": rng.getstate(),
    }


def _rng(state):
    r = random.Random()
    r.setstate(state["rng_state"])
    return r


def draw_tile(state, rng):
    """Draw one tile at random. If the bag is empty, first refill it with
    every tile from the box lid. Returns None if both are empty."""
    if not state["bag"]:
        if not state["lid"]:
            return None
        state["bag"], state["lid"] = state["lid"], []
        rng.shuffle(state["bag"])
        state.setdefault("refills", 0)
        state["refills"] += 1
    return state["bag"].pop(rng.randrange(len(state["bag"])))


def fill_factories(state):
    """Phase C / setup: the marker holder fills each factory with 4 tiles.
    Stops early (leaving factories short or empty) only if bag and lid are
    both empty."""
    rng = _rng(state)
    for f in state["factories"]:
        assert not f
        for _ in range(TILES_PER_FACTORY):
            t = draw_tile(state, rng)
            if t is None:
                break
            f.append(t)
    state["rng_state"] = rng.getstate()


def start_round(state):
    """Fill the factories, put the marker in the centre, starting player
    moves first."""
    state["round"] += 1
    state["start_player"] = state["marker_holder"]
    state["current"] = state["start_player"]
    fill_factories(state)
    state["centre_marker"] = True
    state["marker_holder"] = None
    state["phase"] = "tiling" if offer_over(state) else "offer"


def new_game(n_players=2, seed=0, variant=COLOURED, first_player=0):
    st = new_state(n_players, seed, variant, first_player)
    start_round(st)
    return st


def offer_over(state):
    return not state["centre"] and not any(state["factories"])


def legal_moves(state):
    """Every legal (source, colour, line) for the current player."""
    board = state["boards"][state["current"]]
    sources = [(i, f) for i, f in enumerate(state["factories"]) if f]
    if state["centre"]:
        sources.append((CENTRE, state["centre"]))
    moves = []
    for src, tiles in sources:
        for colour in COLOURS:
            if colour not in tiles:
                continue
            for line in range(SIZE):
                if can_place(board, line, colour):
                    moves.append(Move(src, colour, line))
            moves.append(Move(src, colour, FLOOR))
    return moves


def _to_floor(state, board, item):
    """Put one item on the leftmost free floor space; tiles that don't fit go
    to the box lid. Returns 'floor' or 'lid'."""
    if len(board["floor"]) < FLOOR_SPACES:
        board["floor"].append(item)
        return "floor"
    if item != MARKER:
        state["lid"].append(item)
    return "lid"


def apply_move(state, move):
    """Carry out one turn of the factory offer for the current player."""
    if state["phase"] != "offer":
        raise ValueError("not in the factory offer phase")
    if move not in legal_moves(state):
        raise ValueError(f"illegal move {move}")
    p = state["current"]
    board = state["boards"][p]
    info = {"player": p, "move": move, "took_marker": False}
    if move.source == CENTRE:
        taken = [t for t in state["centre"] if t == move.colour]
        state["centre"] = [t for t in state["centre"] if t != move.colour]
        pushed = []
        if state["centre_marker"]:
            state["centre_marker"] = False
            state["marker_holder"] = p
            info["took_marker"] = True
            # The marker goes on the floor before the tiles are placed.
            if _to_floor(state, board, MARKER) == "lid":
                info["marker_beside_board"] = True
    else:
        f = state["factories"][move.source]
        taken = [t for t in f if t == move.colour]
        pushed = [t for t in f if t != move.colour]
        state["centre"].extend(pushed)
        state["factories"][move.source] = []
    info["taken"] = len(taken)
    info["pushed"] = len(pushed)
    placed = 0
    if move.line != FLOOR:
        pl = board["lines"][move.line]
        placed = min(len(taken), line_capacity(move.line) - pl["count"])
        pl["colour"] = move.colour
        pl["count"] += placed
    to_floor = to_lid = 0
    for t in taken[placed:]:
        if _to_floor(state, board, t) == "floor":
            to_floor += 1
        else:
            to_lid += 1
    info.update(placed=placed, to_floor=to_floor, to_lid=to_lid)
    if offer_over(state):
        state["phase"] = "tiling"
    else:
        state["current"] = (p + 1) % state["n"]
    return info


# ---------------------------------------------------------------- phase B
def best_grey_column(wall, row, colour):
    """Default column chooser for the grey wall: most points, then leftmost."""
    cols = grey_columns(wall, row, colour)
    if not cols:
        return None
    return max(cols, key=lambda c: (score_placement(wall, row, c), -c))


def tile_wall(state, p, choose_column=None):
    """Phase B for one player. Returns a dict of what happened.

    choose_column(state, p, row, colour, options) -> col is used on the grey
    wall; default picks the most points (leftmost on ties)."""
    board = state["boards"][p]
    wall = board["wall"]
    before = board["score"]
    placements = []
    for row in range(SIZE):
        pl = board["lines"][row]
        if pl["count"] != line_capacity(row):
            continue
        colour = pl["colour"]
        if state["variant"] == COLOURED:
            col = wall_column(row, colour)
            assert wall[row][col] is None
        else:
            options = grey_columns(wall, row, colour)
            if not options:
                # Special case (grey wall): the whole line goes to the floor.
                for _ in range(pl["count"]):
                    _to_floor(state, board, colour)
                placements.append({"row": row, "colour": colour, "col": None,
                                   "points": 0, "to_floor": pl["count"]})
                pl["colour"], pl["count"] = None, 0
                continue
            col = (choose_column(state, p, row, colour, options)
                   if choose_column else best_grey_column(wall, row, colour))
            if col not in options:
                raise ValueError("illegal grey-wall column")
        wall[row][col] = colour
        pts = score_placement(wall, row, col)
        board["score"] += pts
        state["lid"].extend([colour] * (pl["count"] - 1))
        pl["colour"], pl["count"] = None, 0
        placements.append({"row": row, "colour": colour, "col": col, "points": pts})
    items = list(board["floor"])
    n_items = len(items)
    pen = floor_penalty(n_items)
    after_wall = board["score"]
    board["score"] = max(0, board["score"] + pen)
    state["lid"].extend(t for t in items if t != MARKER)
    board["floor"] = []
    return {"player": p, "placements": placements, "floor_items": n_items,
            "floor_marker": MARKER in items, "floor_penalty": pen,
            "score_before": before, "score_after_wall": after_wall,
            "score": board["score"]}


def tile_walls(state, choose_column=None):
    """Phase B for all players, then the end check / phase C."""
    if state["phase"] != "tiling":
        raise ValueError("not in the wall-tiling phase")
    results = [tile_wall(state, p, choose_column) for p in range(state["n"])]
    if state["marker_holder"] is None:
        # Nobody took from the centre this round (every factory pick took all
        # four tiles). House rule: the same player starts again.
        state["centre_marker"] = False
        state["marker_holder"] = state["start_player"]
    if any(complete_rows(b["wall"]) for b in state["boards"]):
        finish_game(state)
    else:
        state["phase"] = "prepare"
    return results


def finish_game(state):
    state["bonuses"] = []
    for b in state["boards"]:
        bd = bonus_breakdown(b["wall"])
        b["score"] += bd["total"]
        state["bonuses"].append(bd)
    state["phase"] = "over"
    state["game_over"] = True


def winners(state):
    """Most points wins; tie -> most complete rows; still tied -> shared."""
    best = max(b["score"] for b in state["boards"])
    tied = [i for i, b in enumerate(state["boards"]) if b["score"] == best]
    most = max(complete_rows(state["boards"][i]["wall"]) for i in tied)
    return [i for i in tied if complete_rows(state["boards"][i]["wall"]) == most]


def count_tiles(state):
    """Every tile in the game (should always be 100)."""
    n = len(state["bag"]) + len(state["lid"]) + len(state["centre"])
    n += sum(len(f) for f in state["factories"])
    n += sum(board_tiles(b) for b in state["boards"])
    return n


def snapshot(state):
    s = copy.deepcopy(state)
    s.pop("rng_state", None)
    return s


# ---------------------------------------------------------------- AI
def evaluate_move(state, move):
    """Heuristic value of a move for the current player (higher = better)."""
    board = state["boards"][state["current"]]
    tiles = state["centre"] if move.source == CENTRE else state["factories"][move.source]
    n = tiles.count(move.colour)
    floor_now = len(board["floor"])
    extra_floor = 1 if (move.source == CENTRE and state["centre_marker"]) else 0
    value = 0.0
    if move.line == FLOOR:
        overflow = n
    else:
        pl = board["lines"][move.line]
        room = line_capacity(move.line) - pl["count"]
        placed = min(n, room)
        overflow = n - placed
        if placed == room:
            wall = board["wall"]
            if state["variant"] == COLOURED:
                col = wall_column(move.line, move.colour)
            else:
                col = best_grey_column(wall, move.line, move.colour)
            if col is None:
                value -= 3 + move.line  # would all drop to the floor
            else:
                value += score_placement(wall, move.line, col) + 1.5
                filled_row = sum(t is not None for t in wall[move.line])
                value += 0.5 * filled_row  # head towards a full row
        else:
            # Unfinished lines carry over; reward progress, penalise the gap.
            value += 0.4 * placed - 0.25 * (room - placed)
    value += floor_penalty(floor_now + extra_floor + overflow) - floor_penalty(floor_now)
    if extra_floor:
        value += 0.5  # starting next round is worth a little
    return value


def choose_move(state, rng):
    """Deterministic heuristic AI: best evaluation, seeded tie-break."""
    moves = legal_moves(state)
    scored = [(round(evaluate_move(state, m), 6), m) for m in moves]
    best = max(v for v, _ in scored)
    top = [m for v, m in scored if v == best]
    return top[rng.randrange(len(top))]


class Game:
    """A complete seeded AI game. play() returns an event log."""

    MAX_ROUNDS = 40

    def __init__(self, n_players=2, seed=0, variant=COLOURED, first_player=0):
        self.seed = seed
        self.state = new_state(n_players, seed, variant, first_player)
        self.ai_rng = random.Random(f"azul-ai-{seed}")
        self.log = []

    def snapshot(self):
        return snapshot(self.state)

    def play(self):
        st = self.state
        while not st["game_over"]:
            if st["round"] >= self.MAX_ROUNDS:
                raise RuntimeError("game did not finish")
            start_round(st)
            self.log.append({"type": "round", "round": st["round"],
                             "start_player": st["start_player"],
                             "state": self.snapshot()})
            while st["phase"] == "offer":
                if offer_over(st):  # no tiles at all this round
                    st["phase"] = "tiling"
                    break
                move = choose_move(st, self.ai_rng)
                info = apply_move(st, move)
                info["type"] = "turn"
                info["post"] = self.snapshot()
                self.log.append(info)
            res = tile_walls(st)
            self.log.append({"type": "tiling", "round": st["round"], "results": res,
                             "state": self.snapshot()})
        self.log.append({"type": "end", "scores": [b["score"] for b in st["boards"]],
                         "bonuses": st["bonuses"], "winners": winners(st),
                         "state": self.snapshot()})
        return self.log


def describe_wall(wall):
    return "\n".join(wall_to_rows(wall))


if __name__ == "__main__":  # pragma: no cover
    import sys
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    g = Game(n, seed)
    log = g.play()
    end = log[-1]
    print(f"seed {seed}, {n} players, {g.state['round']} rounds")
    for i, b in enumerate(g.state["boards"]):
        print(f"player {i}: {b['score']} points, bonus {end['bonuses'][i]['total']}")
        print(describe_wall(b["wall"]))
    print("winners:", end["winners"])
