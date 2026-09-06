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

from sqlalchemy.orm import Session

from app.db.repositories import policy as policy_repo
from app.db.repositories import truth
from app.db.session import session_or, session_scope
from app.policy import actions, eligibility, health, leak, metrics, rollout, selector, state


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
    # Which arm chose: 'ladder', 'shadow' or 'rl'. In shadow the child is taught
    # by the ladder and `shadow_strategy` holds what the learned policy would
    # have done; in 'rl' it is the other way round. Either way the episode
    # records both, which is what makes the two comparable afterwards.
    arm: str = rollout.LADDER
    shadow_strategy: str | None = None
    # What the eligibility filter allowed on this turn, and the rung it stood
    # on, so the episode says what the choice was made *from*.
    eligible: tuple[str, ...] = ()
    rung: int = 0
    explore_rate: float = 0.0
    # Why the ladder answered, when it did. Empty on a learned decision.
    fallback_reason: str = ""


def _child_uuid(child_id: str | None) -> UUID | None:
    try:
        return UUID(str(child_id))
    except (ValueError, AttributeError, TypeError):
        return None


def _preferred(experience_mode: str, rung: int) -> tuple[str, ...]:
    return actions.ladder_prior_for(experience_mode).get(rung, ())


def _context(
    *,
    experience_mode: str,
    rung: int,
    spent: list[str],
    has_prerequisite: bool = True,
    has_visual: bool = True,
    frustrated: bool = False,
) -> eligibility.TurnContext:
    return eligibility.TurnContext(
        experience_mode=experience_mode,
        rung=rung,
        spent=tuple(spent),
        has_prerequisite=has_prerequisite,
        has_visual=has_visual,
        frustrated=frustrated,
    )


def _eligible(context: eligibility.TurnContext) -> list[str]:
    """The filtered action set, with what was removed and why sent to metrics.

    This is the only door into selection. `actions.legal_actions` is still the
    rule about parking and repetition; `eligibility` is that plus the
    context-dependent removals, and both run before any Q-value is read.
    """
    verdict = eligibility.decide(context)
    for strategy, reason in verdict.removed.items():
        metrics.count(metrics.ELIGIBILITY_REMOVED, strategy=strategy, reason=reason)
    if verdict.relaxed:
        metrics.count(metrics.ELIGIBILITY_REMOVED, reason="all_removed_relaxed")
    return verdict.allowed


def _ladder_strategy(*, experience_mode: str, rung: int, spent: list[str], legal: list[str]) -> str:
    """What the hand-written ladder would pick out of the allowed set.

    No database, no exploration, no Q-values: `stats={}` means every action
    scores on the prior alone, which is precisely the ladder's own order. This
    is the permanent fallback, and it is also the thing the learned policy is
    measured against, so it is one function called from both places.
    """
    strategy, _ = selector.choose(
        legal=legal,
        stats={},
        preferred=_preferred(experience_mode, rung),
        explore_rate=0.0,
    )
    return strategy


def _ladder_choice(
    *, experience_mode: str, rung: int, spent: list[str], reason: str = ""
) -> TeachingDecision:
    """The fallback decision: the ladder's answer, recorded as nobody's episode."""
    legal = _eligible(_context(experience_mode=experience_mode, rung=rung, spent=spent))
    strategy = _ladder_strategy(
        experience_mode=experience_mode, rung=rung, spent=spent, legal=legal
    )
    if reason:
        metrics.count(metrics.FALLBACK, reason=reason)
    metrics.count(metrics.DECISION, arm=rollout.LADDER, strategy=strategy)
    return TeachingDecision(
        strategy=strategy,
        spent=tuple(spent),
        arm=rollout.LADDER,
        eligible=tuple(legal),
        rung=rung,
        fallback_reason=reason,
    )


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
    has_prerequisite: bool = True,
    has_visual: bool = True,
    frustrated: bool = False,
    rng: random.Random | None = None,
) -> TeachingDecision:
    """Pick the strategy for this teaching turn.

    The flow, in order, and the order is the point:

        candidates -> eligibility filter -> epsilon-greedy -> strategy

    The filter runs first and the selector only ever sees what survived it, so
    neither the greedy branch nor the exploring one can reach a strategy the
    app's own rules removed. Then the arm decides whose answer the child
    actually hears - the ladder's, in shadow and in fallback; the table's, for
    the rolled-out fraction.

    Rung 1 is not passed here: it is the clean second try, where the guide only
    encourages and spends nothing. Consulting the policy there would write an
    episode for a turn it never influenced.
    """
    fallback_spent = list(spent or [])
    child_uuid = _child_uuid(child_id)
    arm = rollout.arm_for(child_id)

    if child_uuid is None or arm.name == rollout.LADDER:
        return _ladder_choice(
            experience_mode=experience_mode,
            rung=rung,
            spent=fallback_spent,
            reason=arm.reason if child_uuid is not None else "no_child_uuid",
        )

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
            legal = _eligible(
                _context(
                    experience_mode=experience_mode,
                    rung=rung,
                    spent=spent_now,
                    has_prerequisite=has_prerequisite,
                    has_visual=has_visual,
                    frustrated=frustrated,
                )
            )
            explore_rate = rollout.explore_rate(arm)
            learned, explored = selector.choose(
                legal=legal,
                stats=policy_repo.action_stats(session, state_key=key),
                preferred=_preferred(experience_mode, rung),
                explore_rate=explore_rate,
                rng=rng,
            )
            ladder = _ladder_strategy(
                experience_mode=experience_mode, rung=rung, spent=spent_now, legal=legal
            )
    except Exception:  # pragma: no cover - database unavailable
        logger.exception("Policy could not choose; falling back to the ladder")
        health.record_failure("db")
        return _ladder_choice(
            experience_mode=experience_mode,
            rung=rung,
            spent=fallback_spent,
            reason="db_error",
        )

    health.record_success()

    # In shadow the child is taught by the ladder and the learned choice is
    # only written down. This is the whole safety of the rollout: the recorded
    # comparison costs a child nothing.
    taught = learned if arm.teaches else ladder
    shadow = ladder if arm.teaches else learned
    if not arm.teaches:
        metrics.count(metrics.SHADOW, taught=ladder, recommended=learned, agreed=ladder == learned)

    metrics.count(metrics.DECISION, arm=arm.name, strategy=taught, state=key)
    metrics.count(metrics.EXPLORE if explored else metrics.EXPLOIT, arm=arm.name)

    return TeachingDecision(
        strategy=taught,
        spent=tuple(spent_now),
        state_key=key,
        explored=explored,
        durable=True,
        mastery=mastery,
        arm=arm.name,
        shadow_strategy=shadow,
        eligible=tuple(legal),
        rung=rung,
        explore_rate=explore_rate,
    )


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
    leak_kind: str = leak.NONE,
    question_ref: str = "",
    session: Session | None = None,
) -> bool:
    """Write down what was actually spent, and the episode waiting on a probe.

    `strategy` is passed separately from `decision.strategy` because the model
    may return a different legal strategy from the one the policy proposed. What
    trains the table is what the child was actually taught - so the substitution
    is re-checked against the same eligibility filter the policy's own choice
    passed, and a strategy the filter would have removed is not written as
    though the policy had chosen it.

    "The same filter" means the same *set*, not a filter re-derived here. Three
    of the six things `TurnContext` carries - whether there is a prerequisite to
    drop to, whether the level has a visual, and whether the child is
    frustrated - are known to the caller of `decide()` and not to this function,
    so rebuilding the context from what `commit()` happens to have let a
    substitution back in that the real turn had removed: a story for a child who
    was already close to tears passed the re-check, because the re-check no
    longer knew they were. `decision.eligible` is what the turn actually
    allowed, so that is what the substitution is measured against.
    """
    child_uuid = _child_uuid(child_id)
    if child_uuid is None or not decision.durable or not strategy:
        return False

    if decision.eligible:
        permitted = strategy in decision.eligible
    else:  # pragma: no cover - a decision recorded before `eligible` was carried
        permitted = eligibility.permits(
            strategy, _context(experience_mode=experience_mode, rung=rung, spent=list(decision.spent))
        )
    if not permitted:
        metrics.count(metrics.ELIGIBILITY_REMOVED, reason="substitution_rejected", strategy=strategy)
        strategy = decision.strategy

    try:
        # `session` is the caller's, when the caller is already inside one. The
        # AI Teacher writes its whole turn in a single unit of work, and opening
        # a second one here to write the episode made every teaching turn wait
        # out SQLite's five-second busy timeout against the transaction the turn
        # itself was holding.
        with session_or(session) as session:
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
            row = truth.mastery_for(session, child_id=child_uuid, skill_id=skill_id)
            mastery_now = row.mastery if row else decision.mastery

            # Close the previous decision on this skill first: it now knows where
            # the child ended up, which is the bootstrap term of its own update.
            # Then open this one.
            previous = policy_repo.last_open_episode(session, child_id=child_uuid, skill_id=skill_id)
            if previous is not None:
                policy_repo.close_episode(
                    session, previous, next_state_key=key, mastery_after=mastery_now
                )

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
                activity_id=activity_id or "",
                rung=rung,
                spent_count=len(decision.spent),
                mastery_before=decision.mastery,
                arm=decision.arm,
                shadow_action=decision.shadow_strategy,
                explored=decision.explored,
                explore_rate=decision.explore_rate,
                leak_kind=leak_kind,
                # The authored question this turn taught around. It is written
                # here and read only by the retention test scheduled off this
                # episode, which uses it to ask a different question about the
                # same concept - nothing about a mark, a star or an unlock
                # touches it.
                question_ref=question_ref,
            )
        metrics.count(metrics.LEAK_VERDICT, kind=leak_kind, strategy=strategy)
        return True
    except Exception:  # pragma: no cover - database unavailable
        logger.exception("Could not record the teaching episode")
        health.record_failure("db")
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
