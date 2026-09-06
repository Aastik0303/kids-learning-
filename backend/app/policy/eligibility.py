"""The gate between the action space and the policy: what may be chosen at all.

`selector.choose` picks the highest-scoring action out of a set. This module
decides what goes into that set, and it is deliberately a *separate* step from
selection, because the two answer different questions:

- eligibility answers "is this strategy allowed for this child, on this turn,
  under the app's own rules" - and the answer must not be learnable. A policy
  that could discover a reward for parking a hard child early, or for repeating
  an explanation the child has already failed, would find it;
- selection answers "of the allowed ones, which looks best" - and that is the
  only question the Q-table is asked.

So the flow is `candidates -> filter -> epsilon-greedy -> strategy`, and
exploration draws from the *filtered* set. There is no path in which a random
draw reaches a strategy the filter removed.

`decide()` never returns an empty set. If every rule fires at once - which
should not happen, and did not in the suite - it falls back to the mode's own
non-park strategies, because a turn that teaches nothing is worse for the child
than a repeated explanation.
"""

from dataclasses import dataclass, field

from app.policy import actions


# Why a strategy was removed. These strings are logged and aggregated, so they
# are stable names rather than sentences.
REASON_NOT_IN_ACTION_SPACE = "not_in_action_space"
REASON_MODE_EXCLUDED = "mode_excluded"
REASON_ALREADY_SPENT = "already_spent"
REASON_PARK_NOT_YET = "park_not_yet"
REASON_PARK_ONLY = "park_rung"
REASON_NO_PREREQUISITE = "no_prerequisite"
REASON_NO_VISUAL = "no_visual"
REASON_FRUSTRATED = "frustrated_high_load"

# Strategies that ask the child to hold something extra in their head - a story
# to follow, two things to compare, an analogy to carry across. They are good
# teaching and they are the wrong thing to hand a child who is already close to
# tears, which is a judgement the app makes and the table may not overturn.
HIGH_LOAD_STRATEGIES = frozenset({"S3_EXAMPLE", "S4_STORY", "S5_CONTRAST"})


@dataclass(frozen=True)
class TurnContext:
    """Everything the filter needs, and nothing the selector needs.

    Kept as plain flags rather than a reference to the lesson state so this
    module has no imports out of `app/policy/` - it is called from the guide,
    from the offline evaluation harness and from the tests, and each of those
    knows these four facts by a different route.
    """

    experience_mode: str = "standard"
    rung: int = 0
    spent: tuple[str, ...] = ()
    # False when there is no lower level to drop to inside this sitting, which
    # makes S8_PREREQUISITE a promise the app cannot keep.
    has_prerequisite: bool = True
    # False when the level has no picture, shape or letterform to switch to.
    has_visual: bool = True
    # The frustration watcher's verdict for this turn.
    frustrated: bool = False


@dataclass(frozen=True)
class Eligibility:
    allowed: list[str]
    removed: dict[str, str] = field(default_factory=dict)
    # True when every rule fired and the fallback set was used instead.
    relaxed: bool = False


def _mode_strategies(experience_mode: str) -> tuple[str, ...]:
    return actions.strategies_for(experience_mode)


def decide(context: TurnContext, *, candidates: tuple[str, ...] | None = None) -> Eligibility:
    """Which strategies this turn may choose between, and why the rest are out."""
    pool = tuple(candidates if candidates is not None else actions.ALL_STRATEGIES)
    mode_allowed = set(_mode_strategies(context.experience_mode))
    spent = set(context.spent)
    at_park_rung = context.rung >= actions.PARK_RUNG

    allowed: list[str] = []
    removed: dict[str, str] = {}

    for strategy in pool:
        reason = _reason_to_remove(
            strategy,
            context=context,
            mode_allowed=mode_allowed,
            spent=spent,
            at_park_rung=at_park_rung,
        )
        if reason is None:
            allowed.append(strategy)
        else:
            removed[strategy] = reason

    if allowed:
        return Eligibility(allowed=allowed, removed=removed)

    # Nothing survived. Park if the rung says so, otherwise hand back the mode's
    # own teaching strategies - a repeat beats a blank turn.
    if at_park_rung:
        return Eligibility(allowed=[actions.PARK], removed=removed, relaxed=True)
    relaxed = [s for s in _mode_strategies(context.experience_mode) if s != actions.PARK]
    return Eligibility(allowed=relaxed or [actions.PARK], removed=removed, relaxed=True)


def _reason_to_remove(
    strategy: str,
    *,
    context: TurnContext,
    mode_allowed: set[str],
    spent: set[str],
    at_park_rung: bool,
) -> str | None:
    if not actions.valid(strategy):
        return REASON_NOT_IN_ACTION_SPACE
    if at_park_rung:
        # The question is over. Parking is the only thing left, and it is not a
        # choice the policy gets to make differently.
        return None if strategy == actions.PARK else REASON_PARK_ONLY
    if strategy == actions.PARK:
        return REASON_PARK_NOT_YET
    if strategy not in mode_allowed:
        return REASON_MODE_EXCLUDED
    if strategy in spent:
        return REASON_ALREADY_SPENT
    if strategy == "S8_PREREQUISITE" and not context.has_prerequisite:
        return REASON_NO_PREREQUISITE
    if strategy == "S7_SENSE_SWITCH" and not context.has_visual:
        return REASON_NO_VISUAL
    if context.frustrated and strategy in HIGH_LOAD_STRATEGIES:
        return REASON_FRUSTRATED
    return None


def permits(strategy: str, context: TurnContext) -> bool:
    """Whether one named strategy would survive the filter.

    Used to check the model's substitution: the guide may return a different
    legal strategy from the one the policy proposed, and it must pass the same
    gate the policy's own choice did.
    """
    return strategy in decide(context).allowed


__all__ = [
    "Eligibility",
    "HIGH_LOAD_STRATEGIES",
    "REASON_ALREADY_SPENT",
    "REASON_FRUSTRATED",
    "REASON_MODE_EXCLUDED",
    "REASON_NOT_IN_ACTION_SPACE",
    "REASON_NO_PREREQUISITE",
    "REASON_NO_VISUAL",
    "REASON_PARK_NOT_YET",
    "REASON_PARK_ONLY",
    "TurnContext",
    "decide",
    "permits",
]
