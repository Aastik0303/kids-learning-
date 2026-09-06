"""The learning-to-teach loop: teaching events, retention probes, Q-learning.

The one rule this module exists to enforce: **a reward is paid by a retention
probe and by nothing else.** RLHF was rejected for this project because a reward
defined on "the child answered correctly" trains a teacher that hands over the
answer - it scores 1.0 every time, immediately, and the child learns nothing.
A Q-learning reward built the same way has the identical failure, so the reward
column stays NULL until a probe scheduled days later comes back.

`record_episode()` therefore cannot take a reward, and `pay_episode()` is the
only function that writes one - `settle_probe()` and the scheduled retention
test in `repositories/retention_tests.py` both go through it, so there is one
place where "has this episode already been paid?" is asked and one answer.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import PolicyEpisode, PolicyQValue, RetentionProbe, TeachingEvent
from app.policy import metrics, reward as reward_rules, selector


logger = logging.getLogger(__name__)


# Q-learning constants. Deliberately conservative: this policy teaches real
# children while it learns, so it moves slowly and explores rarely.
LEARNING_RATE = 0.15
DISCOUNT = 0.85

# Reward weights. Retention and transfer are the only positive terms; nothing
# here can be earned inside the turn that spends the strategy.
#
# The numbers now live in `app/policy/reward.py`, which reads them from the
# settings so they can be tuned without a code change. These names are kept
# because they are the ones this module has always been read by, and they are
# the configured defaults - `reward.weights()` is what an actual settlement
# reads, so a changed environment is picked up here too.
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


# How far back a probe may reach for the teaching it is judging. A probe is
# scheduled the moment a skill is first answered correctly, so the strategies it
# is evidence about are the ones spent in the sitting that led there - not the
# ones spent a fortnight ago on the same skill and forgotten in between. Without
# this window, a child who struggled with counting in April and met it again in
# June would pay June's probe to April's strategies, and the table would learn
# from a join that means nothing.
#
# Seven days: long enough to cover a skill taught across two or three sittings
# in a week, short enough that an abandoned attempt from last month is out.
ATTRIBUTION_WINDOW = timedelta(days=7)


def attach_probe(
    session: Session,
    *,
    child_id: UUID,
    skill_id: str,
    probe: RetentionProbe,
    now: datetime | None = None,
) -> int:
    """Point the recent unpaid episodes for this skill at the probe that pays them.

    A teaching decision is taken before the child has answered anything, so the
    probe that judges it does not exist yet. This is the join, made when the
    probe is finally scheduled: without it every episode taught before the first
    correct answer - which is most of them, and all the interesting ones - would
    stay unpaid for ever and teach the table nothing.

    Bounded by `ATTRIBUTION_WINDOW`, and only over episodes not already attached
    to some other probe, so one retention result cannot be credited to a
    teaching action it had nothing to do with.
    """
    cutoff = (now or _now()) - ATTRIBUTION_WINDOW
    episodes = session.scalars(
        select(PolicyEpisode).where(
            PolicyEpisode.child_id == child_id,
            PolicyEpisode.skill_id == skill_id,
            PolicyEpisode.reward_resolved_at.is_(None),
            PolicyEpisode.retention_probe_id.is_(None),
            PolicyEpisode.taken_at >= cutoff,
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
    activity_id: str = "",
    rung: int = 0,
    spent_count: int = 0,
    mastery_before: float | None = None,
    arm: str = "rl",
    shadow_action: str | None = None,
    explored: bool = False,
    explore_rate: float = 0.0,
    leak_kind: str = "none",
    question_ref: str = "",
) -> PolicyEpisode:
    """Log a teaching decision. Note there is still no `reward` parameter.

    `immediate_correct` is recorded for diagnostics - reading it next to the
    leak-veto rate is how the answer-leak failure mode is caught - but it never
    becomes the reward. That is the whole point of the split.

    Everything after `answer_leak_vetoed` is attribution: which question, which
    rung, how many strategies were already gone, where the child's mastery stood
    before the turn, which arm chose and what the other one would have chosen.
    None of it is read by the update; all of it is read when somebody asks why
    the table moved.
    """
    episode = PolicyEpisode(
        child_id=child_id,
        skill_id=skill_id,
        state_key=state_key,
        action=action,
        immediate_correct=immediate_correct,
        answer_leak_vetoed=answer_leak_vetoed,
        retention_probe_id=probe.id if probe else None,
        activity_id=activity_id or "",
        rung=rung,
        spent_count=spent_count,
        mastery_before=mastery_before,
        arm=arm,
        shadow_action=shadow_action,
        explored=explored,
        explore_rate=explore_rate,
        leak_kind=leak_kind,
        # The authored question this turn taught with, so the retention test
        # scheduled off this episode can ask a different one about the same
        # concept and tell transfer from recall.
        question_ref=question_ref or "",
    )
    session.add(episode)
    session.flush()
    return episode


def close_episode(
    session: Session,
    episode: PolicyEpisode,
    *,
    next_state_key: str | None,
    mastery_after: float | None = None,
) -> None:
    """Record where the child ended up, for the bootstrap term in the update.

    `mastery_after` is not used by the update - the reward is the probe's, not
    the mastery move's - but an episode whose mastery went 0.3 -> 0.3 and one
    whose mastery went 0.3 -> 0.7 are different evidence about the same reward,
    and only one of the two is legible without it.
    """
    episode.next_state_key = next_state_key
    if mastery_after is not None:
        episode.mastery_after = mastery_after
    session.flush()


def _reward_for(probe: RetentionProbe, episode: PolicyEpisode) -> float:
    """What one resolved probe pays the episode waiting on it.

    A strategy that got today's answer by giving it away shows up here as a
    correct attempt on the day and a failed probe two days later, so it is paid
    less than a strategy that taught more slowly and held.

    The arithmetic is `app/policy/reward.py`'s, so the opportunistic probe and
    the scheduled retention test pay from one table of weights. A cleared
    `form_signature` means the probe was posed the same way the skill was
    taught, which is recall rather than transfer.
    """
    return reward_rules.for_retention(
        passed=bool(probe.was_correct),
        transfer=bool(probe.form_signature),
        answer_leak_vetoed=bool(episode.answer_leak_vetoed),
    ).value


def settle_probe(
    session: Session,
    probe: RetentionProbe,
    *,
    was_correct: bool,
    now: datetime | None = None,
) -> list[PolicyEpisode]:
    """Resolve a probe and pay every episode that was waiting on it.

    This is the only function in the codebase that writes `PolicyEpisode.reward`,
    and it is **idempotent twice over**:

    - a probe that already has a `resolved_at` is not settled again, so a retry,
      a double-submitted attempt or a second worker picking up the same due probe
      pays nothing and returns nothing;
    - within one settlement, only episodes whose `reward_resolved_at` is NULL are
      paid, so an episode attached to a probe that was partly settled before a
      crash is not paid twice either.

    Both matter more than they look. The update moves Q(s,a) by
    alpha * (target - Q); applying one probe's evidence twice is not a rounding
    error, it is counting one child's Tuesday as two children's.
    """
    settled_at = now or _now()
    if probe.resolved_at is not None:
        # Already paid. Say so in the metrics - a nonzero rate here means
        # something upstream is asking twice, which is worth knowing even though
        # it is harmless.
        metrics.count(metrics.PROBE, kind=probe.kind, duplicate=True)
        return []

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
    paid = [
        episode
        for episode in episodes
        if pay_episode(
            session,
            episode,
            reward=_reward_for(probe, episode),
            probe_kind=probe.kind,
            probe_passed=was_correct,
            now=settled_at,
        )
    ]
    metrics.count(metrics.PROBE, kind=probe.kind, passed=bool(was_correct), episodes=len(paid))
    session.flush()
    return paid


# The `probe_kind` a scheduled retention test writes onto the episode it pays,
# beside the opportunistic probe's own 'day2' and 'day7'. Four characters
# because the column is eight wide and was written for those two.
TEST_KIND = "test"


def pay_episode(
    session: Session,
    episode: PolicyEpisode,
    *,
    reward: float,
    probe_kind: str = TEST_KIND,
    probe_passed: bool | None = None,
    now: datetime | None = None,
) -> bool:
    """Pay one episode, once, and move the Q-value its action owns.

    **This is the only function that writes `PolicyEpisode.reward`**, and both
    payers go through it: the opportunistic probe in `settle_probe`, and the
    scheduled retention test in `repositories/retention_tests.py`. One door
    means one place where "has this already been paid?" is asked, and it is
    asked here:

        an episode with a `reward_resolved_at` is not paid again, and the
        function returns False rather than raising.

    That guard is what makes the whole feature safe to retry. A sweep that runs
    twice, a second worker picking up the same due test, a child who
    double-taps - none of them can apply one piece of evidence twice, and
    applying it twice is not a rounding error: the update moves Q(s,a) by
    `alpha * (target - Q)`, so a doubled reward is a doubled step towards it.
    """
    if episode.reward_resolved_at is not None:
        metrics.count(metrics.PROBE, kind=probe_kind, duplicate=True)
        return False

    settled_at = now or _now()
    episode.reward = reward
    episode.reward_resolved_at = settled_at
    episode.probe_kind = probe_kind
    episode.probe_passed = probe_passed
    _apply_q_update(session, episode)
    metrics.observe(
        metrics.REWARD,
        episode.reward,
        arm=episode.arm,
        action=episode.action,
        probe=probe_kind,
    )
    session.flush()
    return True


# --------------------------------------------------------------------------
# The Q-table
# --------------------------------------------------------------------------


def get_q_value(session: Session, *, state_key: str, action: str) -> PolicyQValue:
    """The row for one (state, action), created at zero if it is not there yet.

    Two workers settling two probes for the same state at the same moment both
    find no row and both insert one; the unique constraint rejects the second,
    and without this the whole settlement - probe included - rolls back and the
    reward is lost. So the insert runs in a SAVEPOINT and a conflict is resolved
    by reading the row the other worker just wrote.

    Zero is the right default and not merely a convenient one: an unseen action
    is scored by the ladder prior, which is the day-one behaviour.
    """
    row = _select_q_value(session, state_key=state_key, action=action)
    if row is not None:
        return row
    try:
        with session.begin_nested():
            row = PolicyQValue(state_key=state_key, action=action, q_value=0.0, visits=0)
            session.add(row)
            session.flush()
        return row
    except IntegrityError:
        existing = _select_q_value(session, state_key=state_key, action=action)
        if existing is None:  # pragma: no cover - the constraint fired for another reason
            raise
        return existing


def _select_q_value(session: Session, *, state_key: str, action: str) -> PolicyQValue | None:
    statement = select(PolicyQValue).where(
        PolicyQValue.state_key == state_key, PolicyQValue.action == action
    )
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        # Serialise the read-modify-write against a concurrent settlement. Two
        # probes updating one cell without this apply alpha * (target - Q) from
        # the same stale Q, and one of the two updates is silently lost.
        statement = statement.with_for_update()
    return session.scalar(statement)


def best_q_value(session: Session, *, state_key: str) -> float:
    """The bootstrap term. An unseen state is worth 0, not negative infinity -
    optimism about the unknown is what lets a new state be tried at all."""
    values = [
        value
        for value in session.scalars(
            select(PolicyQValue.q_value).where(PolicyQValue.state_key == state_key)
        ).all()
        if selector.sane(value)
    ]
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
    clean, dropped = selector.sanitise({row.action: (row.q_value, row.visits) for row in rows})
    if dropped:
        logger.warning("Ignored unusable Q-values in %s: %s", state_key, dropped)
        metrics.count(metrics.Q_UPDATE, unusable=len(dropped), state=state_key)
    return clean


def _apply_q_update(session: Session, episode: PolicyEpisode) -> PolicyQValue:
    """Q(s,a) <- Q(s,a) + alpha * (r + gamma * max Q(s',a') - Q(s,a)).

    The value on either side of the arithmetic is written back onto the episode.
    That is the difference between a table somebody can audit and a table
    somebody has to trust: `q_before` and `q_after` on the row that caused the
    move mean a surprising Q-value can be traced to the probes that built it.

    A stored value that is not a finite number in range is treated as zero
    rather than propagated - NaN plus anything is NaN, and one corrupt cell
    would otherwise poison the state's bootstrap term for every later update.
    """
    if episode.reward is None:
        raise ValueError("an episode with no settled reward cannot update the table")
    row = get_q_value(session, state_key=episode.state_key, action=episode.action)

    before = row.q_value if selector.sane(row.q_value) else 0.0
    if before != row.q_value:
        logger.warning(
            "Discarded an unusable Q-value for %s/%s: %r", episode.state_key, episode.action, row.q_value
        )
        metrics.count(metrics.Q_UPDATE, repaired=True, state=episode.state_key)

    future = best_q_value(session, state_key=episode.next_state_key) if episode.next_state_key else 0.0
    target = episode.reward + DISCOUNT * future
    after = before + LEARNING_RATE * (target - before)

    row.q_value = after
    row.visits = max(0, row.visits or 0) + 1
    episode.q_before = before
    episode.q_after = after
    metrics.observe(metrics.Q_UPDATE, after, state=episode.state_key, action=episode.action)
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


def settled_episodes(
    session: Session,
    *,
    since: datetime | None = None,
    arm: str | None = None,
) -> list[PolicyEpisode]:
    """Every episode a probe has already paid, for the offline evaluation.

    This is the read side of the whole design: the evaluation compares arms on
    what the probes actually returned, not on anything computed inside a
    teaching turn. `arm` separates the children the learned policy taught from
    the ones the ladder taught, which is what makes the comparison a comparison.
    """
    statement = select(PolicyEpisode).where(PolicyEpisode.reward_resolved_at.is_not(None))
    if since is not None:
        statement = statement.where(PolicyEpisode.taken_at >= since)
    if arm is not None:
        statement = statement.where(PolicyEpisode.arm == arm)
    return list(session.scalars(statement.order_by(PolicyEpisode.taken_at)).all())


def q_table(session: Session) -> list[PolicyQValue]:
    """The whole table, small enough to read. Used by the health endpoint and
    by anybody who wants to diff it before and after a week of teaching."""
    return list(session.scalars(select(PolicyQValue).order_by(PolicyQValue.state_key, PolicyQValue.action)).all())
