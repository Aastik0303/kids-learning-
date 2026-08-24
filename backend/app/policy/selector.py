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

import random

# How much a ladder-preferred action is worth before the table has an opinion.
# Larger than any reward a single probe pays (1.35 at most) would make the prior
# unfalsifiable; this is small enough that a handful of settled probes can
# overturn it, and large enough to decide day one.
PRIOR_BONUS = 0.6

# Visits needed before the prior has faded by half.
PRIOR_HALF_LIFE = 6.0


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


__all__ = ["PRIOR_BONUS", "choose", "prior_weight", "score"]
