"""Choosing one teaching strategy: epsilon-greedy, over the hand-written ladder.

Two things make this safe to run on real four-year-olds:

**The prior is the ladder, not zero.** A Q-table initialised at zero and tied
uniformly would hand a child a strategy drawn at random for its first few
hundred episodes. Instead every action the repair ladder would have chosen at
this rung starts with a bonus, and that bonus decays as the table gathers
visits. On day one the policy reproduces today's behaviour; by the time it
departs from it, it has evidence.

**Exploration is rare and never illegal.** `explore_rate` defaults to 0.08 and
exploration draws from the legal set only - it can never park a child early,
repeat a spent explanation, or reach a strategy the child's age band excludes.
"""

import math
import random

# How much a ladder-preferred action is worth before the table has an opinion.
# Larger than any reward a single probe pays (1.35 at most) would make the prior
# unfalsifiable; this is small enough that a handful of settled probes can
# overturn it, and large enough to decide day one.
PRIOR_BONUS = 0.6

# Visits needed before the prior has faded by half.
PRIOR_HALF_LIFE = 6.0


# The largest magnitude a healthy Q-value can reach: the biggest single reward
# is 1.35 and the heaviest penalty 2.0, and with gamma 0.85 the geometric bound
# on the bootstrapped return is about 13. Anything past this is not a strong
# opinion, it is a corrupted row - a half-written float, a bad backfill, a
# migration that put the wrong column here - and it must not be allowed to pin
# one strategy for every child in a state for ever.
Q_ABS_LIMIT = 15.0


def sane(value: float | None) -> bool:
    """Whether a stored Q-value may be believed."""
    if value is None:
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number) and abs(number) <= Q_ABS_LIMIT


def sanitise(stats: dict[str, tuple[float, int]]) -> tuple[dict[str, tuple[float, int]], list[str]]:
    """Drop unusable rows, and say which they were.

    A dropped action is not banned - it falls back to being unseen, which means
    the ladder prior decides it, which is the behaviour on day one. That is the
    right failure: a corrupt table degrades to the hand-written policy rather
    than to noise.
    """
    clean: dict[str, tuple[float, int]] = {}
    dropped: list[str] = []
    for action, entry in (stats or {}).items():
        try:
            value, visits = entry
            visits = int(visits)
        except (TypeError, ValueError):
            dropped.append(action)
            continue
        if not sane(value) or visits < 0:
            dropped.append(action)
            continue
        clean[action] = (float(value), visits)
    return clean, dropped


def prior_weight(visits: int) -> float:
    return PRIOR_BONUS * (PRIOR_HALF_LIFE / (PRIOR_HALF_LIFE + max(0, visits)))


def score(action: str, *, stats: dict[str, tuple[float, int]], preferred: tuple[str, ...]) -> float:
    value, visits = stats.get(action, (0.0, 0))
    return value + (prior_weight(visits) if action in preferred else 0.0)


def choose(
    *,
    legal: list[str],
    stats: dict[str, tuple[float, int]],
    preferred: tuple[str, ...] = (),
    explore_rate: float = 0.0,
    rng: random.Random | None = None,
) -> tuple[str, bool]:
    """Return the strategy to spend, and whether it was an exploration.

    Ties break towards the ladder's own order, then towards the action space's,
    so the same situation gets the same answer twice - a child who sees the
    board reshuffle on every identical turn is being taught by noise.
    """
    if not legal:
        raise ValueError("the policy was asked to choose from an empty action set")

    rng = rng or random.Random()
    stats, _dropped = sanitise(stats)
    # Exploration draws from `legal` and from nothing else. `legal` is what the
    # eligibility filter returned, so there is no path - explore or exploit - by
    # which a strategy the app's own rules removed reaches a child.
    if explore_rate > 0 and rng.random() < explore_rate:
        return rng.choice(legal), True

    order = {action: index for index, action in enumerate(preferred)}
    best = max(
        legal,
        key=lambda action: (
            score(action, stats=stats, preferred=preferred),
            -order.get(action, len(order)),
            -legal.index(action),
        ),
    )
    return best, False


__all__ = ["PRIOR_BONUS", "Q_ABS_LIMIT", "choose", "prior_weight", "sane", "sanitise", "score"]
