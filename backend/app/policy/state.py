"""The state the policy sees, discretised into a key.

A Q-table needs states it will actually revisit. The raw situation - a child, a
skill, a running mastery estimate, an attempt count, a list of spent strategies -
is continuous enough that no two turns would ever share a row, and the table
would learn nothing from thousands of episodes.

Four features survive the squeeze, and each earns its place by changing what a
good teacher would do next:

- **experience mode**, because Play Group and Nursery cannot be taught with a
  story or a contrast, and the legal action set differs;
- **mastery bucket**, because a child at 0.7 needs a nudge and a child at 0.1
  needs the concept again from the bottom;
- **rung**, how many times this question has already gone wrong;
- **how many strategies are already spent**, because the fourth explanation of
  one question is a different situation from the first, whatever the rung says.

The child's identity is deliberately *not* in the key. A per-child table would
have one row per child per situation and would never leave zero; what is learned
here is how to teach a *kind of moment*, and the child-specific part is the
mastery bucket the moment carries.
"""

# Five buckets, not ten: the estimate is an EWMA over a handful of attempts, and
# pretending to resolve it more finely than that invents precision.
MASTERY_BUCKETS = (0.2, 0.4, 0.6, 0.8)

MAX_SPENT = 4
MAX_RUNG = 6


def mastery_bucket(mastery: float | None) -> int:
    value = 0.0 if mastery is None else max(0.0, min(1.0, mastery))
    return sum(1 for edge in MASTERY_BUCKETS if value >= edge)


def state_key(*, experience_mode: str, mastery: float | None, rung: int, spent: int) -> str:
    mode = "early" if experience_mode == "early" else "std"
    return (
        f"{mode}|m{mastery_bucket(mastery)}"
        f"|r{max(0, min(int(rung), MAX_RUNG))}"
        f"|n{max(0, min(int(spent), MAX_SPENT))}"
    )


def next_state_key(*, experience_mode: str, mastery: float | None, rung: int, spent: int) -> str:
    """Where the child stands after this strategy is spent and fails.

    The successor used for the bootstrap term is the pessimistic one - one rung
    higher, one strategy fewer. A strategy that works is not judged by this
    term at all; it is judged by the probe that pays it days later.
    """
    return state_key(experience_mode=experience_mode, mastery=mastery, rung=rung + 1, spent=spent + 1)


__all__ = ["MASTERY_BUCKETS", "mastery_bucket", "next_state_key", "state_key"]
