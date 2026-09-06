"""Scheduled retention tests: create one per teaching episode, settle it once.

The chain this table exists to hold, end to end:

    teaching episode -> concept -> retention test -> result -> reward
    -> the episode's own (state, action) -> Q-value

Three rules are enforced here rather than hoped for upstream.

**One test per teaching episode.** `create_for_episode` is idempotent twice
over: it reads first, and it catches the unique constraint on
`source_teaching_episode_id` when two workers read at the same moment. A sweep
that runs every fifteen minutes must be able to run every fifteen minutes.

**One payment per teaching episode.** `settle` pays through
`policy.pay_episode`, which refuses an episode that already has a
`reward_resolved_at` - so a test whose episode was already paid by the older
opportunistic probe records its result and its reward for the audit trail, and
moves no Q-value. `episodes_paid` on the row says which of the two happened.

**One settlement per test.** A test that already has a `settled_at` is not
settled again, whatever arrives.

Nothing here decides whether the child was right: `passed` arrives from
`stage.judge`, in pure Python, from the authored key.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import PolicyEpisode, RetentionTest
from app.policy import metrics, retention as retention_rules, reward as reward_rules
from app.db.repositories import policy as policy_repo


logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Creating them - the scheduler's write side
# --------------------------------------------------------------------------


def episodes_awaiting_a_test(
    session: Session,
    *,
    now: datetime | None = None,
    child_id: UUID | None = None,
    limit: int = 500,
) -> list[PolicyEpisode]:
    """Teaching episodes old enough to be tested and not yet scheduled.

    Three conditions, and each removes a way of paying for teaching twice:

    * **old enough** - taught at least `retention.delay()` ago, so the test is
      about what was retained rather than about what was just said;
    * **not yet paid** - an episode whose reward has already landed has nothing
      left to learn from a test;
    * **no test already** - the anti-join against `retention_tests` is what makes
      a repeated sweep write nothing.

    Ordered oldest first so a backlog is worked through in the order it was
    taught, and capped so one sweep is one bounded query.
    """
    cutoff = retention_rules.as_utc(now or _now()) - retention_rules.delay()
    scheduled = select(RetentionTest.source_teaching_episode_id)
    statement = (
        select(PolicyEpisode)
        .where(
            PolicyEpisode.taken_at <= cutoff,
            PolicyEpisode.reward_resolved_at.is_(None),
            PolicyEpisode.id.not_in(scheduled),
        )
        .order_by(PolicyEpisode.taken_at)
        .limit(limit)
    )
    if child_id is not None:
        statement = statement.where(PolicyEpisode.child_id == child_id)
    return list(session.scalars(statement).all())


def for_episode(session: Session, *, episode_id: UUID) -> RetentionTest | None:
    return session.scalar(
        select(RetentionTest).where(RetentionTest.source_teaching_episode_id == episode_id)
    )


def create_for_episode(
    session: Session,
    *,
    episode: PolicyEpisode,
    topic_id: str,
    now: datetime | None = None,
) -> RetentionTest:
    """Schedule the one test this episode gets, or return the one it already has.

    `due_at` is `episode.taken_at + retention.delay()` and nothing else. It is
    computed from when the *teaching* happened rather than from when the sweep
    runs, so a sweep that was down for a day does not push every test a day
    later - the debt was already due.
    """
    existing = for_episode(session, episode_id=episode.id)
    if existing is not None:
        return existing

    test = RetentionTest(
        child_id=episode.child_id,
        concept_id=episode.skill_id,
        topic_id=topic_id or "",
        source_teaching_episode_id=episode.id,
        due_at=retention_rules.due_at(episode.taken_at),
        status=retention_rules.PENDING,
        taught_question_ref=episode.question_ref or "",
        scheduled_at=now or _now(),
    )
    session.add(test)
    try:
        with session.begin_nested():
            session.flush()
    except IntegrityError:
        # Another worker got there first. From the schedule's side either row is
        # the row, so the winner's is returned rather than raising.
        winner = for_episode(session, episode_id=episode.id)
        if winner is None:  # pragma: no cover - the constraint fired for another reason
            raise
        return winner
    metrics.count(metrics.PROBE, kind=policy_repo.TEST_KIND, scheduled=True)
    return test


# --------------------------------------------------------------------------
# Reading them - the scheduler's read side
# --------------------------------------------------------------------------


def due_for_child(
    session: Session, *, child_id: UUID, now: datetime | None = None, limit: int = 0
) -> list[RetentionTest]:
    """This child's pending tests that have come due, in a deterministic order.

    The order is `retention.order_key` - oldest debt, then concept, then id - so
    "if several are due, process them deterministically" is a property of the
    data rather than of which worker asked. Q-learning has no say in it, and
    neither has a shuffle.
    """
    moment = retention_rules.as_utc(now or _now())
    rows = list(
        session.scalars(
            select(RetentionTest).where(
                RetentionTest.child_id == child_id,
                RetentionTest.status == retention_rules.PENDING,
                RetentionTest.due_at <= moment,
            )
        ).all()
    )
    rows.sort(key=retention_rules.order_key)
    return rows[:limit] if limit and limit > 0 else rows


def get(session: Session, *, test_id: UUID) -> RetentionTest | None:
    return session.scalar(select(RetentionTest).where(RetentionTest.id == test_id))


def source_episode(session: Session, test: RetentionTest) -> PolicyEpisode | None:
    return session.scalar(
        select(PolicyEpisode).where(PolicyEpisode.id == test.source_teaching_episode_id)
    )


# --------------------------------------------------------------------------
# Settling them - the only path from a result to a Q-value
# --------------------------------------------------------------------------


def mark_void(session: Session, test: RetentionTest, *, now: datetime | None = None) -> None:
    """This concept has no question that can be asked of a child.

    Marked rather than left pending: a test nobody can answer would otherwise
    sit at the head of the queue for ever and hold up the ones behind it. The
    episode stays unpaid, which is the truth about it.
    """
    test.status = retention_rules.VOID
    test.completed_at = now or _now()
    session.flush()


def settle(
    session: Session,
    test: RetentionTest,
    *,
    passed: bool,
    asked_question_ref: str = "",
    now: datetime | None = None,
) -> dict:
    """Turn one retention result into a reward and one Q-value update.

    The order is the architecture, and each step is somebody else's job done
    somewhere else:

    1. the **judge** has already decided `passed` - `stage.judge`, pure Python;
    2. the **reward system** prices it - `policy/reward.py`, from the settings;
    3. the **credit assignment** finds the *original* teaching episode through
       `source_teaching_episode_id` - never the retention question, which chose
       nothing and is nobody's action;
    4. **Q-learning** updates `Q(episode.state_key, episode.action)` through
       `policy.pay_episode`, which is where the no-double-payment guard lives;
    5. the test is marked settled with what it paid.

    Returns a small summary so a caller can log it and a test can assert on it
    without reaching back into the row.
    """
    settled_at = now or _now()
    if test.settled_at is not None:
        # Already settled. A retry, a double-tapped answer, a second worker: all
        # harmless, all worth counting.
        metrics.count(metrics.PROBE, kind=policy_repo.TEST_KIND, duplicate=True)
        return {
            "settled": False,
            "result": test.result,
            "reward": test.reward,
            "episodes_paid": test.episodes_paid,
            "transfer": test.transfer,
        }

    episode = source_episode(session, test)
    asked = asked_question_ref or test.question_ref or ""
    transfer = retention_rules.is_transfer(
        taught_question_ref=test.taught_question_ref, asked_question_ref=asked
    )
    reward = reward_rules.for_retention(
        passed=passed,
        transfer=transfer,
        answer_leak_vetoed=bool(episode.answer_leak_vetoed) if episode is not None else False,
    )

    paid = False
    if episode is not None:
        paid = policy_repo.pay_episode(
            session,
            episode,
            reward=reward.value,
            probe_kind=policy_repo.TEST_KIND,
            probe_passed=passed,
            now=settled_at,
        )

    test.question_ref = asked
    test.transfer = transfer
    test.result = reward.result
    test.reward = reward.value
    test.status = retention_rules.SETTLED
    test.completed_at = settled_at
    test.settled_at = settled_at
    test.episodes_paid = 1 if paid else 0
    session.flush()

    metrics.count(
        metrics.PROBE, kind=policy_repo.TEST_KIND, passed=bool(passed), episodes=1 if paid else 0
    )
    return {
        "settled": True,
        "result": reward.result,
        "reward": reward.value,
        "terms": reward.terms,
        "episodes_paid": 1 if paid else 0,
        "transfer": transfer,
        "episode_id": str(episode.id) if episode is not None else "",
        "state_key": episode.state_key if episode is not None else "",
        "action": episode.action if episode is not None else "",
    }


def pending_count(session: Session, *, child_id: UUID | None = None) -> int:
    """How many tests are scheduled and not yet asked. A number that only grows
    means tests are being created and never served."""
    statement = select(RetentionTest).where(RetentionTest.status == retention_rules.PENDING)
    if child_id is not None:
        statement = statement.where(RetentionTest.child_id == child_id)
    return len(list(session.scalars(statement).all()))


__all__ = [
    "create_for_episode",
    "due_for_child",
    "episodes_awaiting_a_test",
    "for_episode",
    "get",
    "mark_void",
    "pending_count",
    "settle",
    "source_episode",
]
