"""Shared fixtures. Puts tools/sotw on sys.path so `import engine` etc. work."""
import copy
import sys
from pathlib import Path

import pytest

SOTW = Path(__file__).resolve().parents[1] / "tools" / "sotw"
if str(SOTW) not in sys.path:
    sys.path.insert(0, str(SOTW))

import engine as E  # noqa: E402

SWEEP_SEEDS = range(120)


def mk(rabbit=(), turtle=(), salmon=(), owl=(), triple=(), pair=(), bonus=()):
    """Hand-build a board."""
    b = E.new_board()
    b["rabbit"] = list(rabbit)
    b["turtle"] = list(turtle)
    b["salmon"] = list(salmon)
    b["owl"] = [list(p) for p in owl]
    b["beaver"] = {"triple": list(triple), "pair": list(pair)}
    for a in bonus:
        b["bonus"][a] = True
    return b


def total_stones(state):
    """Every stone (bag + bowl + boards + clear stones used as bonus markers)."""
    n = state["bag"] + len(state["bowl"])
    for b in state["boards"]:
        for a in E.ANIMALS:
            n += len(E.stones_in(b, a)) + (1 if b["bonus"][a] else 0)
    return n


def all_states(log):
    """Yield every snapshot contained in a game log."""
    for e in log:
        if e["type"] == "turn":
            yield e["pre"]
            yield from e.get("snaps", [])
            yield e["post"]
        else:
            yield e["state"]


@pytest.fixture(scope="session")
def games():
    """seed -> (Game, log) for a sweep of full simulated games (cached)."""
    out = {}
    for s in SWEEP_SEEDS:
        g = E.Game(seed=s)
        out[s] = (g, g.play())
    return out


@pytest.fixture
def base_state():
    """A deterministic, fully populated table snapshot (setup of a real game)."""
    g = E.Game(seed=1)
    g.setup()
    st = copy.deepcopy(g.snapshot())
    st["bowl"] = ["red", "blue", "white", "clear"]
    st["bag"] = 52
    st["clear_out"] = 1  # the clear stone sitting in the bowl
    st["current"] = 0
    return st


def rescore(st):
    st["scores"] = [E.total_score(b) for b in st["boards"]]
    return st
