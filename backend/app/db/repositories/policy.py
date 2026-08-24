"""The learning-to-teach loop: teaching events, retention probes, Q-learning.

The one rule this module exists to enforce: **a reward is paid by a retention
probe and by nothing else.** RLHF was rejected for this project because a reward
defined on "the child answered correctly" trains a teacher that hands over the
answer - it scores 1.0 every time, immediately, and the child learns nothing.
A Q-learning reward built the same way has the identical failure, so the reward
column stays NULL until a probe scheduled days later comes back.

`record_episode()` therefore cannot take a reward, and `settle_probe()` is the
only function that writes one.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PolicyEpisode, PolicyQValue, RetentionProbe, TeachingEvent


# Q-learning constants. Deliberately conservative: this policy teaches real
# children while it learns, so it moves slowly and explores rarely.
LEARNING_RATE = 0.15
DISCOUNT = 0.85

# Reward weights. Retention and transfer are the only positive terms; nothing
# here can be earned inside the turn that spends the strategy.
REWARD_RETENTION_PASS = 1.0
REWARD_TRANSFER_BONUS = 0.35
PENALTY_ANSWER_LEAK = 1.5
PENALTY_RETENTION_FAIL = 0.5

PROBE_DELAYS = {"day2": timedelta(days=2), "day7": timedelta(days=7)}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Teaching events - what was spent, so it is not spent twice
# --------------------------------------------------------------------------


def record_teaching_event(
    session: Session,
    *,
    child_id: UUID,
    skill_id: str,
    activity_id: str,
    strategy: str,
    attempt_index: int = 0,
    author: str = "deterministic",
) -> TeachingEvent:
    event = TeachingEvent(
        child_id=child_id,
        skill_id=skill_id,
        activity_id=activity_id,
        strategy=strategy,
        attempt_index=attempt_index,
        author=author,
    )
    session.add(event)
    session.flush()
    return event


def strategies_spent(session: Session, *, child_id: UUID, activity_id: str) -> list[str]:
    """Which strategies this child has already seen on this activity.

    Ordered by when they were spent, de-duplicated, and durable - the in-process
    dict this replaces forgot everything on restart, so a child returning after
    a crash got the same explanation that had already failed them.
    """
    rows = session.scalars(
        select(TeachingEvent.strategy)
        .where(TeachingEvent.child_id == child_id, TeachingEvent.activity_id == activity_id)
        .order_by(TeachingEvent.created_at)
    ).all()
    seen: list[str] = []
    for strategy in rows:
        if strategy not in seen:
            seen.append(strategy)
    return seen


# --------------------------------------------------------------------------
# Retention probes - the only source of reward
# --------------------------------------------------------------------------


def schedule_probe(
    session: Session,
    *,
    child_id: UUID,
    skill_id: str,
    kind: str = "day2",
    form_signature: str = "",
    now: datetime | None = None,
) -> RetentionProbe:
    if kind not in PROBE_DELAYS:
        raise ValueError(f"unknown probe kind: {kind}")
    probe = RetentionProbe(
        child_id=child_id,
        skill_id=skill_id,
        kind=kind,
        due_at=(now or _now()) + PROBE_DELAYS[kind],
        form_signature=form_signature,
    )
    session.add(probe)
    session.flush()
    return probe


def due_probes(session: Session, *, child_id: UUID, now: datetime | None = None) -> list[RetentionProbe]:
    return list(
        session.scalars(
            select(RetentionProbe)
            .where(
                RetentionProbe.child_id == child_id,
                RetentionProbe.resolved_at.is_(None),
                RetentionProbe.due_at <= (now or _now()),
            )
            .order_by(RetentionProbe.due_at)
        ).all()
    )


def open_probe(session: Session, *, child_id: UUID, skill_id: str) -> RetentionProbe | None:
    """The probe already waiting on this skill, if there is one.

    One open probe per skill at a time. Scheduling a second every time a child
    answers correctly would pay the same strategy twice for one piece of
    evidence, and the Q-table would drift upwards on repetition alone.
    """
    return session.scalar(
        select(RetentionProbe)
        .where(
            RetentionProbe.child_id == child_id,
            RetentionProbe.skill_id == skill_id,
            RetentionProbe.resolved_at.is_(None),
        )
        .order_by(RetentionProbe.due_at)
    )


def attach_probe(session: Session, *, child_id: UUID, skill_id: str, probe: RetentionProbe) -> int:
    """Point every unpaid episode for this skill at the probe that will pay it.

    A teaching decision is taken before the child has answered anything, so the
    probe that judges it does not exist yet. This is the join, made when the
    probe is finally scheduled: without it every episode taught before the first
    correct answer - which is most of them, and all the interesting ones - would
    stay unpaid for ever and teach the table nothing.
    """
    episodes = session.scalars(
        select(PolicyEpisode).where(
            PolicyEpisode.child_id == child_id,
            PolicyEpisode.skill_id == skill_id,
            PolicyEpisode.reward_resolved_at.is_(None),
            PolicyEpisode.retention_probe_id.is_(None),
        )
    ).all()
    for episode in episodes:
        episode.retention_probe_id = probe.id
    session.flush()
    return len(episodes)


# --------------------------------------------------------------------------
# Episodes - one teaching decision each, reward paid later
# --------------------------------------------------------------------------


def record_episode(
    session: Session,
    *,
    child_id: UUID,
    skill_id: str,
    state_key: str,
    action: str,
    probe: RetentionProbe | None = None,
    immediate_correct: bool | None = None,
    answer_leak_vetoed: bool = False,
) -> PolicyEpisode:
    """Log a teaching decision. Note there is no `reward` parameter.

    `immediate_correct` is recorded for diagnostics - reading it next to the
    leak-veto rate is how the answer-leak failure mode is caught - but it never
    becomes the reward. That is the whole point of the split.
    """
    episode = PolicyEpisode(
        child_id=child_id,
        skill_id=skill_id,
        state_key=state_key,
        action=action,
        immediate_correct=immediate_correct,
        answer_leak_vetoed=answer_leak_vetoed,
        retention_probe_id=probe.id if probe else None,
    )
    session.add(episode)
    session.flush()
    return episode


def close_episode(session: Session, episode: PolicyEpisode, *, next_state_key: str | None) -> None:
    """Record where the child ended up, for the bootstrap term in the update."""
    episode.next_state_key = next_state_key
    session.flush()


def _reward_for(probe: RetentionProbe, episode: PolicyEpisode) -> float:
    """What one resolved probe pays the episode waiting on it.

    A strategy that got today's answer by giving it away shows up here as a
    correct attempt on the day and a failed probe two days later, so it is paid
    less than a strategy that taught more slowly and held.
    """
    reward = 0.0
    if probe.was_correct:
        reward += REWARD_RETENTION_PASS
        # The probe was posed in a different form from the teaching question, so
        # passing it is evidence of transfer rather than of recall.
        if probe.form_signature:
            reward += REWARD_TRANSFER_BONUS
    else:
        reward -= PENALTY_RETENTION_FAIL
    if episode.answer_leak_vetoed:
        reward -= PENALTY_ANSWER_LEAK
    return reward


def settle_probe(
    session: Session,
    probe: RetentionProbe,
    *,
    was_correct: bool,
    now: datetime | None = None,
) -> list[PolicyEpisode]:
    """Resolve a probe and pay every episode that was waiting on it.

    This is the only function in the codebase that writes `PolicyEpisode.reward`.
    """
    settled_at = now or _now()
    probe.was_correct = was_correct
    probe.resolved_at = settled_at

    episodes = list(
        session.scalars(
            select(PolicyEpisode).where(
                PolicyEpisode.retention_probe_id == probe.id,
                PolicyEpisode.reward_resolved_at.is_(None),
            )
        ).all()
    )
    for episode in episodes:
        episode.reward = _reward_for(probe, episode)
        episode.reward_resolved_at = settled_at
        _apply_q_update(session, episode)
    session.flush()
    return episodes


# --------------------------------------------------------------------------
# The Q-table
# --------------------------------------------------------------------------


def get_q_value(session: Session, *, state_key: str, action: str) -> PolicyQValue:
    row = session.scalar(
        select(PolicyQValue).where(PolicyQValue.state_key == state_key, PolicyQValue.action == action)
    )
    if row is None:
        row = PolicyQValue(state_key=state_key, action=action, q_value=0.0, visits=0)
        session.add(row)
        session.flush()
    return row


def best_q_value(session: Session, *, state_key: str) -> float:
    """The bootstrap term. An unseen state is worth 0, not negative infinity -
    optimism about the unknown is what lets a new state be tried at all."""
    values = session.scalars(
        select(PolicyQValue.q_value).where(PolicyQValue.state_key == state_key)
    ).all()
    return max(values) if values else 0.0


def action_values(session: Session, *, state_key: str) -> dict[str, float]:
    """Every action this policy has an opinion about in this state."""
    rows = session.scalars(select(PolicyQValue).where(PolicyQValue.state_key == state_key)).all()
    return {row.action: row.q_value for row in rows}


def action_stats(session: Session, *, state_key: str) -> dict[str, tuple[float, int]]:
    """Value and visit count per action.

    The selector needs both: the value says what the table believes, and the
    visit count says how much to believe it. An action tried twice does not get
    to outrank the hand-written ladder yet.
    """
    rows = session.scalars(select(PolicyQValue).where(PolicyQValue.state_key == state_key)).all()
    return {row.action: (row.q_value, row.visits) for row in rows}


def _apply_q_update(session: Session, episode: PolicyEpisode) -> PolicyQValue:
    """Q(s,a) <- Q(s,a) + alpha * (r + gamma * max_a' Q(s',a') - Q(s,a))."""
    if episode.reward is None:
        raise ValueError("an episode with no settled reward cannot update the table")
    row = get_q_value(session, state_key=episode.state_key, action=episode.action)
    future = best_q_value(session, state_key=episode.next_state_key) if episode.next_state_key else 0.0
    target = episode.reward + DISCOUNT * future
    row.q_value = row.q_value + LEARNING_RATE * (target - row.q_value)
    row.visits += 1
    session.flush()
    return row


def last_open_episode(session: Session, *, child_id: UUID, skill_id: str) -> PolicyEpisode | None:
    """The most recent decision on this skill that has no successor state yet.

    Q-learning bootstraps off where the child ended up, so an episode is only
    complete once the *next* decision has been taken and can name the state it
    was taken in.
    """
    return session.scalar(
        select(PolicyEpisode)
        .where(
            PolicyEpisode.child_id == child_id,
            PolicyEpisode.skill_id == skill_id,
            PolicyEpisode.next_state_key.is_(None),
        )
        .order_by(PolicyEpisode.taken_at.desc())
    )


def pending_episodes(session: Session, *, skill_id: str | None = None) -> list[PolicyEpisode]:
    """Episodes still waiting on a probe. A large and growing number here means
    probes are being scheduled and never asked, and the policy has stopped
    learning without erroring."""
    statement = select(PolicyEpisode).where(PolicyEpisode.reward_resolved_at.is_(None))
    if skill_id:
        statement = statement.where(PolicyEpisode.skill_id == skill_id)
    return list(session.scalars(statement).all())
