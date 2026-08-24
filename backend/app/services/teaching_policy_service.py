"""The bridge between the guide and the learned policy.

`app/policy/` decides, `app/db/repositories/policy.py` remembers, and this
module is what the guide actually calls. It owns three jobs:

- **which strategies are already spent on this question**, read from
  `teaching_events` rather than from an in-process dict, so a child who comes
  back after a restart is not handed the explanation that already failed them;
- **which strategy to spend next**, from the Q-table where it has an opinion and
  from the hand-written ladder where it does not;
- **writing the episode**, with no reward. The reward is paid by
  `retention_service` days later, and by nothing else.

Everything here degrades rather than raises. A guide turn that cannot reach the
database still teaches - it falls back to the ladder, exactly as before this
existed - because a child waiting for the screen to say something is not an
acceptable place to surface an infrastructure failure.
"""

import logging
import random
from dataclasses import dataclass
from uuid import UUID

from app.config import get_settings
from app.db.repositories import policy as policy_repo
from app.db.repositories import truth
from app.db.session import session_scope
from app.policy import actions, selector, state


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeachingDecision:
    """One choice of strategy, and enough context to write the episode later."""

    strategy: str
    spent: tuple[str, ...] = ()
    state_key: str | None = None
    explored: bool = False
    # False when the choice was made without the database - the ladder's answer,
    # not the table's. Such a turn teaches but is never written as an episode: a
    # decision the policy did not make must not train it.
    durable: bool = False
    mastery: float | None = None


def _child_uuid(child_id: str | None) -> UUID | None:
    try:
        return UUID(str(child_id))
    except (ValueError, AttributeError, TypeError):
        return None


def _preferred(experience_mode: str, rung: int) -> tuple[str, ...]:
    return actions.ladder_prior_for(experience_mode).get(rung, ())


def _ladder_choice(*, experience_mode: str, rung: int, spent: list[str]) -> TeachingDecision:
    """What the hand-written ladder would do. No database, no exploration."""
    legal = actions.legal_actions(experience_mode=experience_mode, rung=rung, spent=spent)
    strategy, _ = selector.choose(
        legal=legal,
        stats={},
        preferred=_preferred(experience_mode, rung),
        explore_rate=0.0,
    )
    return TeachingDecision(strategy=strategy, spent=tuple(spent))


def spent_strategies(*, child_id: str | None, activity_id: str | None) -> list[str] | None:
    """What this child has already been shown on this question.

    Returns None when the durable log cannot answer, so the caller can fall back
    to its own memory rather than treat "nothing recorded" as "nothing spent".
    """
    child_uuid = _child_uuid(child_id)
    if child_uuid is None or not activity_id:
        return None
    try:
        with session_scope() as session:
            return policy_repo.strategies_spent(session, child_id=child_uuid, activity_id=activity_id)
    except Exception:  # pragma: no cover - database unavailable
        logger.exception("Could not read spent strategies; falling back to memory")
        return None


def decide(
    *,
    child_id: str | None,
    skill_id: str,
    activity_id: str | None,
    experience_mode: str,
    rung: int,
    spent: list[str] | None = None,
    rng: random.Random | None = None,
) -> TeachingDecision:
    """Pick the strategy for this teaching turn.

    Rung 1 is not passed here: it is the clean second try, where the guide only
    encourages and spends nothing. Consulting the policy there would write an
    episode for a turn it never influenced.
    """
    fallback_spent = list(spent or [])
    child_uuid = _child_uuid(child_id)
    if child_uuid is None:
        return _ladder_choice(experience_mode=experience_mode, rung=rung, spent=fallback_spent)

    try:
        with session_scope() as session:
            durable_spent = (
                policy_repo.strategies_spent(session, child_id=child_uuid, activity_id=activity_id)
                if activity_id
                else []
            )
            # The durable log is authoritative; what the caller remembered
            # in-process is used only when the log has nothing to say.
            spent_now = durable_spent or fallback_spent
            row = truth.mastery_for(session, child_id=child_uuid, skill_id=skill_id)
            mastery = row.mastery if row else None
            key = state.state_key(
                experience_mode=experience_mode, mastery=mastery, rung=rung, spent=len(spent_now)
            )
            legal = actions.legal_actions(experience_mode=experience_mode, rung=rung, spent=spent_now)
            strategy, explored = selector.choose(
                legal=legal,
                stats=policy_repo.action_stats(session, state_key=key),
                preferred=_preferred(experience_mode, rung),
                explore_rate=get_settings().policy_explore_rate,
                rng=rng,
            )
            return TeachingDecision(
                strategy=strategy,
                spent=tuple(spent_now),
                state_key=key,
                explored=explored,
                durable=True,
                mastery=mastery,
            )
    except Exception:  # pragma: no cover - database unavailable
        logger.exception("Policy could not choose; falling back to the ladder")
        return _ladder_choice(experience_mode=experience_mode, rung=rung, spent=fallback_spent)


def commit(
    *,
    child_id: str | None,
    skill_id: str,
    activity_id: str | None,
    decision: TeachingDecision,
    strategy: str,
    experience_mode: str,
    rung: int,
    author: str = "deterministic",
    answer_leak_vetoed: bool = False,
) -> bool:
    """Write down what was actually spent, and the episode waiting on a probe.

    `strategy` is passed separately from `decision.strategy` because the model
    may return a different legal strategy from the one the policy proposed. What
    trains the table is what the child was actually taught.
    """
    child_uuid = _child_uuid(child_id)
    if child_uuid is None or not decision.durable or not strategy:
        return False

    try:
        with session_scope() as session:
            policy_repo.record_teaching_event(
                session,
                child_id=child_uuid,
                skill_id=skill_id,
                activity_id=activity_id or "",
                strategy=strategy,
                attempt_index=rung,
                author=author,
            )
            key = decision.state_key or state.state_key(
                experience_mode=experience_mode,
                mastery=decision.mastery,
                rung=rung,
                spent=len(decision.spent),
            )
            # Close the previous decision on this skill first: it now knows where
            # the child ended up, which is the bootstrap term of its own update.
            # Then open this one.
            previous = policy_repo.last_open_episode(session, child_id=child_uuid, skill_id=skill_id)
            if previous is not None:
                policy_repo.close_episode(session, previous, next_state_key=key)

            policy_repo.record_episode(
                session,
                child_id=child_uuid,
                skill_id=skill_id,
                state_key=key,
                action=strategy,
                # A probe already waiting on this skill pays this episode too;
                # one scheduled later picks it up through `attach_probe`.
                probe=policy_repo.open_probe(session, child_id=child_uuid, skill_id=skill_id),
                answer_leak_vetoed=answer_leak_vetoed,
            )
        return True
    except Exception:  # pragma: no cover - database unavailable
        logger.exception("Could not record the teaching episode")
        return False


def q_table(*, state_key: str) -> dict[str, float]:
    """Read-only view of what the policy believes in one state.

    The table is small and enumerable on purpose: a person can read it, diff it
    and revert it, which is not true of a network.
    """
    try:
        with session_scope() as session:
            return policy_repo.action_values(session, state_key=state_key)
    except Exception:  # pragma: no cover - database unavailable
        return {}
