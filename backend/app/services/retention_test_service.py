"""Retention tests as part of the schedule: created by the sweep, asked by the class.

This is the orchestration layer for the feature. It owns three verbs and no
rules - the rules are `app/policy/retention.py` (when), `app/policy/reward.py`
(what it pays), `app/playground/retention.py` (what is asked) and
`app/playground/stage.py` (whether it was right):

* **`schedule`** - for every teaching episode old enough and not yet paid,
  create the one retention test it gets, due `teaching_time + 2 days`. Run by
  `planner_runner.sweep` beside the daily plan, because a retention test *is*
  part of the schedule and not a background mechanism of its own.
* **`due_for_child`** - the tests that have come due, in a deterministic order,
  with the question each one should ask already resolved out of the syllabus.
* **`settle`** - one result in, one reward out, paid to the *original* teaching
  episode's (state, action).

**What this deliberately does not touch.** A retention test never marks a level
done, never unlocks anything, never pays a star, never writes to `attempts` and
never moves the day's plan cursor or the stage tally. It is a check-in that
feeds the learned policy, and the curriculum runs exactly as it did before it
existed. The one thing it moves is a Q-value.

**And it is never an episode of its own.** No strategy is chosen for it, so
`teaching_policy_service` is not called and no `policy_episodes` row is written.
The reward belongs to the teaching action that earned it two days ago; crediting
it to the asking of the test would be crediting the exam for the lesson.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.repositories import retention_tests as repo
from app.db.session import session_or, session_scope
from app.playground import retention as retention_questions
from app.policy import retention as retention_rules


logger = logging.getLogger(__name__)

# One sweep schedules at most this many tests. A backlog is worked through over
# several passes rather than in one long transaction that holds a connection
# while the app is trying to serve lessons - the same shape as the planner's own
# batch, and for the same reason.
BATCH = 500


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _child_uuid(child_id: str | None) -> UUID | None:
    try:
        return UUID(str(child_id))
    except (ValueError, AttributeError, TypeError):
        return None


def _topic_of(concept_id: str) -> str:
    """The topic inside a concept id. `"nur_english:letter_a"` -> `"letter_a"`.

    The concept id is the skill id everything else uses, and its topic half is
    where the syllabus keeps the questions.
    """
    text = str(concept_id or "")
    return text.split(":", 1)[1] if ":" in text else text


@dataclass(frozen=True)
class DueTest:
    """A due test with its question resolved: what the class puts on the screen."""

    test_id: str
    concept_id: str
    topic_id: str
    source_episode_id: str
    due_at: datetime
    question_ref: str
    question: str
    answer: str
    accept: tuple[str, ...] = ()
    options: tuple[str, ...] = ()

    @property
    def expects(self) -> str:
        return "tap" if len(self.options) >= 2 else "voice"


# --------------------------------------------------------------------------
# Scheduling - the sweep's half
# --------------------------------------------------------------------------


def schedule(
    *,
    child_id: str | None = None,
    now: datetime | None = None,
    limit: int = BATCH,
    session: Session | None = None,
) -> dict:
    """Create the retention tests that are owed, and no others.

    Idempotent: the query behind it is an anti-join against `retention_tests`,
    and the write is guarded by a unique constraint on the source episode. Two
    sweeps in the same minute, or two workers in the same second, produce the
    same rows.

    Returns `{"considered": n, "created": n}` so the caller can log it.
    """
    moment = now or _now()
    summary = {"considered": 0, "created": 0}
    child_uuid = _child_uuid(child_id) if child_id is not None else None
    if child_id is not None and child_uuid is None:
        return summary

    try:
        with session_or(session) as work:
            episodes = repo.episodes_awaiting_a_test(
                work, now=moment, child_id=child_uuid, limit=limit
            )
            summary["considered"] = len(episodes)
            for episode in episodes:
                before = repo.for_episode(work, episode_id=episode.id)
                repo.create_for_episode(
                    work,
                    episode=episode,
                    topic_id=_topic_of(episode.skill_id),
                    now=moment,
                )
                if before is None:
                    summary["created"] += 1
    except Exception:  # pragma: no cover - database unavailable
        logger.exception("Could not schedule retention tests")
    return summary


# --------------------------------------------------------------------------
# Reading - what the class asks
# --------------------------------------------------------------------------


def due_for_child(
    child_id: str,
    *,
    now: datetime | None = None,
    limit: int | None = None,
    session: Session | None = None,
) -> list[DueTest]:
    """The due tests this child owes, questions resolved, in schedule order.

    A test whose concept has no answerable authored question is marked `void`
    here rather than returned: it cannot be asked, and leaving it pending would
    park it at the head of the queue for ever.

    Quiet on failure. A database that will not answer means no check-in today,
    never an error on a child's screen.
    """
    child_uuid = _child_uuid(child_id)
    if child_uuid is None:
        return []

    moment = now or _now()
    wanted = retention_rules.per_sitting() if limit is None else max(0, int(limit))
    if wanted == 0:
        return []

    ready: list[DueTest] = []
    try:
        with session_or(session) as work:
            for row in repo.due_for_child(work, child_id=child_uuid, now=moment):
                topic_id = row.topic_id or _topic_of(row.concept_id)
                asked = retention_questions.pick(topic_id, taught_ref=row.taught_question_ref)
                if asked is None:
                    repo.mark_void(work, row, now=moment)
                    continue
                ready.append(
                    DueTest(
                        test_id=str(row.id),
                        concept_id=row.concept_id,
                        topic_id=topic_id,
                        source_episode_id=str(row.source_teaching_episode_id),
                        due_at=retention_rules.as_utc(row.due_at),
                        question_ref=asked.activity_id,
                        question=asked.question,
                        answer=asked.answer,
                        accept=tuple(asked.accept),
                        options=tuple(asked.options),
                    )
                )
                if len(ready) >= wanted:
                    break
    except Exception:  # pragma: no cover - database unavailable
        logger.exception("Could not read the due retention tests")
        return []
    return ready


def load(test_id: str, *, session: Session | None = None) -> DueTest | None:
    """One test by id, with its question resolved the same way `due_for_child` does.

    The pick is deterministic, so this returns the same question the child was
    shown even across a reload and a different worker - nothing about the
    question text is stored on the row until it settles.
    """
    try:
        row_id = UUID(str(test_id))
    except (ValueError, TypeError):
        return None
    try:
        with session_or(session) as work:
            row = repo.get(work, test_id=row_id)
            if row is None or row.status != retention_rules.PENDING:
                return None
            topic_id = row.topic_id or _topic_of(row.concept_id)
            asked = retention_questions.pick(topic_id, taught_ref=row.taught_question_ref)
            if asked is None:
                return None
            return DueTest(
                test_id=str(row.id),
                concept_id=row.concept_id,
                topic_id=topic_id,
                source_episode_id=str(row.source_teaching_episode_id),
                due_at=retention_rules.as_utc(row.due_at),
                question_ref=asked.activity_id,
                question=asked.question,
                answer=asked.answer,
                accept=tuple(asked.accept),
                options=tuple(asked.options),
            )
    except Exception:  # pragma: no cover - database unavailable
        logger.exception("Could not read retention test %s", test_id)
        return None


# --------------------------------------------------------------------------
# Settling - one result, one reward, one Q-value
# --------------------------------------------------------------------------


def settle(
    test_id: str,
    *,
    passed: bool,
    asked_question_ref: str = "",
    now: datetime | None = None,
    session: Session | None = None,
) -> dict:
    """Pay the teaching episode this test was scheduled off.

    `passed` comes from `stage.judge` and from nothing else - this function does
    not look at what the child said, on purpose: the judge is a separate
    responsibility and keeping it that way is what stops a reward path growing
    an opinion about correctness.

    Runs on **its own session by default**. Settling is a write against
    `policy_episodes` and `policy_q_values` that has nothing to do with the
    turn's own row, and on SQLite a second writer inside the turn's open
    transaction waits out the whole busy timeout.
    """
    try:
        row_id = UUID(str(test_id))
    except (ValueError, TypeError):
        return {"settled": False}

    try:
        with session_or(session) as work:
            row = repo.get(work, test_id=row_id)
            if row is None:
                return {"settled": False}
            return repo.settle(
                work,
                row,
                passed=bool(passed),
                asked_question_ref=asked_question_ref,
                now=now or _now(),
            )
    except Exception:  # pragma: no cover - database unavailable
        logger.exception("Could not settle retention test %s", test_id)
        return {"settled": False}


def pending_count(child_id: str | None = None) -> int:
    """How many tests are scheduled and not yet asked, for the operator's view."""
    child_uuid = _child_uuid(child_id) if child_id is not None else None
    if child_id is not None and child_uuid is None:
        return 0
    try:
        with session_scope() as session:
            return repo.pending_count(session, child_id=child_uuid)
    except Exception:  # pragma: no cover - database unavailable
        return 0


__all__ = ["BATCH", "DueTest", "due_for_child", "load", "pending_count", "schedule", "settle"]
