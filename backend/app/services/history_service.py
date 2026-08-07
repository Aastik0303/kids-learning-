from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.history import ActivityAttempt, HistoryResponse
from app.services.mock_storage import mock_activity_attempts


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
) -> ActivityAttempt:
    attempt = {
        "id": f"attempt_{uuid4().hex[:10]}",
        "child_id": child_id,
        "session_id": session_id,
        "activity_id": activity_id,
        "topic": topic,
        "skill": skill,
        "level_id": level_id,
        "child_answer": child_answer,
        "is_correct": is_correct,
        "attempt_number": attempt_number,
        "created_at": datetime.now(timezone.utc),
    }
    mock_activity_attempts.append(attempt)
    return ActivityAttempt(**attempt)


def history_for_child(child_id: str) -> HistoryResponse:
    attempts = [ActivityAttempt(**attempt) for attempt in mock_activity_attempts if attempt["child_id"] == child_id]
    return HistoryResponse(child_id=child_id, attempts=attempts)
