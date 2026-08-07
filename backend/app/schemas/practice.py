from pydantic import BaseModel
from app.schemas.avatar import AvatarPayload
from app.schemas.learning import Activity


class PracticeTopic(BaseModel):
    topic: str
    title: str
    unlocked: bool


class PracticeStartRequest(BaseModel):
    child_id: str
    topic: str


class PracticeStartResponse(BaseModel):
    practice_session_id: str
    topic: str
    activities: list[Activity]
    selection_reason: str = "introduced_skills"


class PracticeAnswerRequest(BaseModel):
    practice_session_id: str
    activity_id: str
    answer: str


class PracticeAnswerResponse(BaseModel):
    is_correct: bool
    feedback: str
    hint: str | None = None
    avatar: AvatarPayload | None = None
