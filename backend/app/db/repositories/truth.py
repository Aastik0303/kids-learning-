"""Attempts, mastery and lesson state - the rows only the evaluator may write.

Nothing in this module imports `app.agents`, `app.ai` or any LLM client, and
nothing here takes a model's opinion as an argument. `record_attempt()` takes
`is_correct` as a plain bool because the caller is `activity_evaluators`, which
compares the child's answer to the answer key in pure Python.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Attempt, LessonState, SkillMastery


# The mastery gate, all four clauses. A single lucky answer must not open a
# topic: the child has to hold the skill across attempts, across question forms
# and across days, because a skill that only survives inside one afternoon is
# not a skill the child has.
MASTERY_THRESHOLD = 0.75
MIN_ATTEMPTS = 4
MIN_DISTINCT_FORMS = 2
MIN_DISTINCT_DAYS = 2

# How fast one answer moves the running estimate. Low enough that a child who
# guesses right once does not jump the gate, high enough that genuine progress
# is visible inside a week.
EWMA_ALPHA = 0.3

# A correct answer with heavy support is weaker evidence than an unaided one.
# Without this, the fastest route to "mastered" is to keep the scaffolding up.
SCAFFOLD_CREDIT = {0: 1.0, 1: 0.9, 2: 0.75, 3: 0.55, 4: 0.35}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record_attempt(
    session: Session,
    *,
    child_id: UUID,
    topic_id: str,
    activity_id: str,
    skill_id: str,
    is_correct: bool,
    attempt_index: int = 0,
    child_answer: str | None = None,
    scaffold_level: int = 0,
    form_signature: str = "",
    forms_available: int | None = None,
    now: datetime | None = None,
) -> Attempt:
    attempt = Attempt(
        child_id=child_id,
        topic_id=topic_id,
        activity_id=activity_id,
        skill_id=skill_id,
        is_correct=is_correct,
        attempt_index=attempt_index,
        child_answer=child_answer,
        scaffold_level=scaffold_level,
        form_signature=form_signature,
    )
    if now is not None:
        attempt.answered_at = now
    session.add(attempt)
    session.flush()
    update_mastery(session, child_id=child_id, skill_id=skill_id, forms_available=forms_available, now=now)
    return attempt


def server_attempt_index(session: Session, *, child_id: UUID, activity_id: str) -> int:
    """How many times this child has already answered this activity.

    The repair ladder used to take this from the client, which meant a client
    stuck at zero silently defeated every escalation. Counted here it cannot be.
    """
    return int(
        session.scalar(
            select(func.count())
            .select_from(Attempt)
            .where(Attempt.child_id == child_id, Attempt.activity_id == activity_id)
        )
        or 0
    )


def attempts_for(session: Session, *, child_id: UUID, limit: int = 500) -> list[Attempt]:
    """The child's answers, oldest first, for the parent-facing report."""
    rows = session.scalars(
        select(Attempt)
        .where(Attempt.child_id == child_id)
        .order_by(Attempt.answered_at.desc())
        .limit(limit)
    ).all()
    return list(reversed(rows))


def _mastery_row(session: Session, *, child_id: UUID, skill_id: str) -> SkillMastery:
    row = session.scalar(
        select(SkillMastery).where(SkillMastery.child_id == child_id, SkillMastery.skill_id == skill_id)
    )
    if row is None:
        row = SkillMastery(child_id=child_id, skill_id=skill_id)
        session.add(row)
        session.flush()
    return row


def update_mastery(
    session: Session,
    *,
    child_id: UUID,
    skill_id: str,
    forms_available: int | None = None,
    now: datetime | None = None,
) -> SkillMastery:
    """Recompute one skill from its attempts. Pure function of the attempt log.

    `forms_available` is how many question forms the curriculum holds for this
    skill. The caller knows the curriculum and this module deliberately does
    not, so it is passed in and remembered on the row - `is_mastered()` stays a
    function of the row alone.
    """
    attempts = list(
        session.scalars(
            select(Attempt)
            .where(Attempt.child_id == child_id, Attempt.skill_id == skill_id)
            .order_by(Attempt.answered_at)
        ).all()
    )
    row = _mastery_row(session, child_id=child_id, skill_id=skill_id)
    if forms_available is not None:
        row.forms_available = max(1, forms_available)

    mastery = 0.0
    for attempt in attempts:
        credit = SCAFFOLD_CREDIT.get(attempt.scaffold_level, 0.35) if attempt.is_correct else 0.0
        mastery = (1 - EWMA_ALPHA) * mastery + EWMA_ALPHA * credit

    row.mastery = round(min(1.0, max(0.0, mastery)), 4)
    row.attempts = len(attempts)
    row.correct_attempts = sum(1 for a in attempts if a.is_correct)
    row.distinct_forms = len({a.form_signature for a in attempts if a.is_correct and a.form_signature})
    row.distinct_days = len({a.answered_at.date() for a in attempts if a.is_correct and a.answered_at})
    row.last_seen_at = attempts[-1].answered_at if attempts else None

    if is_mastered(row) and row.mastered_at is None:
        row.mastered_at = now or _now()
    elif not is_mastered(row):
        row.mastered_at = None

    session.flush()
    return row


def required_forms(row: SkillMastery) -> int:
    """Two forms where two exist, one where only one does.

    A flat two would be the stricter-looking rule and the wrong one: 276 of the
    579 authored skills have exactly one activity, so a flat gate leaves those
    skills unmasterable for ever and every topic that depends on them locked -
    a child answering perfectly would simply stop being able to progress.
    Raising `forms_available` as the variant bank grows tightens the gate
    without a code change.
    """
    return min(MIN_DISTINCT_FORMS, max(1, row.forms_available))


def is_mastered(row: SkillMastery) -> bool:
    return (
        row.mastery >= MASTERY_THRESHOLD
        and row.attempts >= MIN_ATTEMPTS
        and row.distinct_forms >= required_forms(row)
        and row.distinct_days >= MIN_DISTINCT_DAYS
    )


def mastery_for(session: Session, *, child_id: UUID, skill_id: str) -> SkillMastery | None:
    return session.scalar(
        select(SkillMastery).where(SkillMastery.child_id == child_id, SkillMastery.skill_id == skill_id)
    )


def mastery_map(session: Session, *, child_id: UUID) -> dict[str, float]:
    rows = session.scalars(select(SkillMastery).where(SkillMastery.child_id == child_id)).all()
    return {row.skill_id: row.mastery for row in rows}


# --------------------------------------------------------------------------
# Lesson state - so tomorrow resumes
# --------------------------------------------------------------------------


def save_lesson_state(
    session: Session,
    *,
    child_id: UUID,
    topic_id: str,
    cursor: int,
    scaffold_level: int = 0,
    status: str = "in_progress",
) -> LessonState:
    row = session.scalar(
        select(LessonState).where(LessonState.child_id == child_id, LessonState.topic_id == topic_id)
    )
    if row is None:
        row = LessonState(child_id=child_id, topic_id=topic_id)
        session.add(row)
    row.cursor = cursor
    row.scaffold_level = scaffold_level
    row.status = status
    session.flush()
    return row


def resume_point(session: Session, *, child_id: UUID, topic_id: str) -> LessonState | None:
    return session.scalar(
        select(LessonState).where(LessonState.child_id == child_id, LessonState.topic_id == topic_id)
    )
