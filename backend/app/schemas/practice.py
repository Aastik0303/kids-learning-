from pydantic import BaseModel

from app.schemas.avatar import AvatarPayload
from app.schemas.learning import Activity


class PracticeSubject(BaseModel):
    subject_id: str
    title: str
    class_id: str
    icon: str
    unlocked: bool
    has_activities: bool = False
    topic_count: int = 0
    # The same presentation the adventure gets, so a subject looks and reads the
    # same on both surfaces and the frontend still holds no curriculum names.
    fun_name: str | None = None
    colour: str | None = None
    easy_line: str | None = None
    # The topics this practice would actually draw from, named so a child can see
    # what they are about to practise instead of a bare count.
    topic_titles: list[str] = []


class PracticeStartRequest(BaseModel):
    child_id: str
    subject_id: str


class PracticeStartResponse(BaseModel):
    practice_session_id: str
    subject_id: str
    subject_title: str
    subject_fun_name: str | None = None
    subject_easy_line: str | None = None
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
    attempt_number: int = 0
    question_changed: bool = False
    avatar: AvatarPayload | None = None
