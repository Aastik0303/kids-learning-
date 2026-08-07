from datetime import datetime

from pydantic import BaseModel


class ActivityAttempt(BaseModel):
    id: str
    child_id: str
    session_id: str
    activity_id: str
    topic: str
    skill: str
    level_id: str | None = None
    child_answer: str
    is_correct: bool
    attempt_number: int
    created_at: datetime


class HistoryResponse(BaseModel):
    child_id: str
    attempts: list[ActivityAttempt]
