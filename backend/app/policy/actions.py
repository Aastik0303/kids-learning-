"""The action space: the nine teaching strategies, and which are legal when.

This is the canonical list. `app/schemas/guide.py` declares the same nine as a
`Literal` for the wire format, and `test_policy.py` asserts the two never drift -
a policy that can choose an action the schema rejects fails at the last step,
after the child has already waited.
"""

from app.schemas.guide import TeachingStrategy


ALL_STRATEGIES: tuple[str, ...] = (
    "S1_TELL",
    "S2_SHOW",
    "S3_EXAMPLE",
    "S4_STORY",
    "S5_CONTRAST",
    "S6_DO_TOGETHER",
    "S7_SENSE_SWITCH",
    "S8_PREREQUISITE",
    "S9_PARK",
)

# Play Group and Nursery lose the four that assume verbal reasoning, or a lower
# level to step back to inside one sitting.
EARLY_STRATEGIES: tuple[str, ...] = ("S1_TELL", "S2_SHOW", "S6_DO_TOGETHER", "S7_SENSE_SWITCH", "S9_PARK")

PARK = "S9_PARK"

# The rung at which a question stops being taught and is parked instead.
PARK_RUNG = 4

# What the hand-written ladder would pick at each rung. This is not a
# suggestion to the policy - it is the policy's prior (see `priors.py`). A
# Q-table that starts at zero and explores uniformly would hand a three-year-old
# a randomly chosen strategy for its first few hundred episodes, which is not a
# thing you may do to a real child. Starting from the ladder means the policy's
# worst case on day one is today's behaviour.
LADDER_PRIOR: dict[int, tuple[str, ...]] = {
    0: ("S1_TELL", "S2_SHOW"),
    2: ("S3_EXAMPLE", "S5_CONTRAST"),
    3: ("S4_STORY", "S6_DO_TOGETHER", "S7_SENSE_SWITCH"),
}

EARLY_LADDER_PRIOR: dict[int, tuple[str, ...]] = {
    0: ("S1_TELL", "S2_SHOW"),
    2: ("S1_TELL", "S2_SHOW"),
    3: ("S2_SHOW", "S6_DO_TOGETHER"),
}


def strategies_for(experience_mode: str) -> tuple[str, ...]:
    return EARLY_STRATEGIES if experience_mode == "early" else ALL_STRATEGIES


def ladder_prior_for(experience_mode: str) -> dict[int, tuple[str, ...]]:
    return EARLY_LADDER_PRIOR if experience_mode == "early" else LADDER_PRIOR


def legal_actions(*, experience_mode: str, rung: int, spent: list[str]) -> list[str]:
    """What the policy may choose on this turn.

    Three constraints, and none of them are learnable - a policy must not be
    able to discover that repeating a failed explanation or refusing to park is
    worth trying:

    - at the park rung, the only action is to park;
    - below it, parking is not on the menu, so the policy cannot learn to give
      up early on a child it finds hard;
    - a strategy already spent on this question is gone, because the child has
      already heard it and it did not work.
    """
    if rung >= PARK_RUNG:
        return [PARK]
    allowed = [s for s in strategies_for(experience_mode) if s != PARK and s not in spent]
    # Everything has been tried and the rung is still below the park. Repeating
    # the least-bad option beats returning nothing.
    return allowed or [s for s in strategies_for(experience_mode) if s != PARK]


def is_teaching_rung(rung: int) -> bool:
    """Rung 1 is the clean second try: encouragement, nothing taught.

    No strategy is spent there, so the policy is not consulted and no episode is
    written - otherwise the table would learn from a turn it never influenced.
    """
    return rung != 1


def valid(strategy: str) -> bool:
    return strategy in ALL_STRATEGIES


__all__ = [
    "ALL_STRATEGIES",
    "EARLY_STRATEGIES",
    "LADDER_PRIOR",
    "PARK",
    "PARK_RUNG",
    "TeachingStrategy",
    "is_teaching_rung",
    "ladder_prior_for",
    "legal_actions",
    "strategies_for",
    "valid",
]
