"""The attempt log, written to the durable truth table.

Every answer a child gives lands in `attempts` and rolls up into
`skill_mastery`. Both are written from the deterministic evaluator's verdict and
from nothing else - `is_correct` arrives here as a plain bool that
`activity_evaluators` computed by comparing the answer to the key in pure
Python. Nothing in this module imports an agent or a model client, and adding
such an import would put a hallucination upstream of mastery, unlocking and
certificate eligibility.

This replaces the `mock_activity_attempts` list, which a parent lost the moment
the server restarted.
"""

from uuid import UUID

from app.db.repositories import truth
from app.db.session import session_scope
from app.schemas.history import ActivityAttempt, HistoryResponse


def _child_uuid(child_id: str) -> UUID | None:
    try:
        return UUID(str(child_id))
    except (ValueError, AttributeError, TypeError):
        return None


def record_attempt(
    *,
    child_id: str,
    session_id: str,
    activity_id: str,
    topic: str,
    skill: str,
    child_answer: str,
    is_correct: bool,
    attempt_number: int,
    level_id: str | None = None,
    form_signature: str = "",
    forms_available: int | None = None,
    scaffold_level: int = 0,
) -> ActivityAttempt | None:
    """Log one graded answer. Returns None for a child with no durable row.

    The guide's own test payloads use ids like `guest_child`, and a demo run
    with no learner behind it must not 500 on the way to the score.
    """
    child_uuid = _child_uuid(child_id)
    if child_uuid is None:
        return None
    with session_scope() as session:
        attempt = truth.record_attempt(
            session,
            child_id=child_uuid,
            topic_id=topic,
            activity_id=activity_id,
            skill_id=skill,
            is_correct=is_correct,
            attempt_index=attempt_number,
            child_answer=child_answer,
            scaffold_level=scaffold_level,
            form_signature=form_signature or "",
            forms_available=forms_available,
        )
        return ActivityAttempt(
            id=str(attempt.id),
            child_id=child_id,
            session_id=session_id,
            activity_id=attempt.activity_id,
            topic=attempt.topic_id,
            skill=attempt.skill_id,
            level_id=level_id,
            child_answer=attempt.child_answer or "",
            is_correct=attempt.is_correct,
            attempt_number=attempt.attempt_index,
            created_at=attempt.answered_at,
        )


def history_for_child(child_id: str) -> HistoryResponse:
    child_uuid = _child_uuid(child_id)
    if child_uuid is None:
        return HistoryResponse(child_id=child_id, attempts=[])
    with session_scope() as session:
        rows = truth.attempts_for(session, child_id=child_uuid)
        attempts = [
            ActivityAttempt(
                id=str(row.id),
                child_id=child_id,
                # The session an answer belonged to is not part of the truth
                # table: an attempt is true whether or not the sitting it came
                # from is still open.
                session_id="",
                activity_id=row.activity_id,
                topic=row.topic_id,
                skill=row.skill_id,
                # `skill_id` is "<subject>:<topic>", so the subject a parent
                # sees in the report is read back off it rather than stored twice.
                level_id=row.skill_id.split(":")[0] if ":" in row.skill_id else None,
                child_answer=row.child_answer or "",
                is_correct=row.is_correct,
                attempt_number=row.attempt_index,
                created_at=row.answered_at,
            )
            for row in rows
        ]
    return HistoryResponse(child_id=child_id, attempts=attempts)
