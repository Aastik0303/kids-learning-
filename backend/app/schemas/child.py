from pydantic import BaseModel, Field


class ChildCreateRequest(BaseModel):
    """Birth month is asked once at onboarding. The class is derived from it on
    the server; the client never chooses a class directly."""

    session_token: str
    name: str = Field(min_length=1)
    birth_year: int = Field(ge=2000, le=2100)
    birth_month: int = Field(ge=1, le=12)
    preferred_language: str = "English"


class ChildUpdateRequest(BaseModel):
    session_token: str
    name: str | None = None
    birth_year: int | None = Field(default=None, ge=2000, le=2100)
    birth_month: int | None = Field(default=None, ge=1, le=12)
    preferred_language: str | None = None


class SubjectProgress(BaseModel):
    """Per-subject progress. Topics are keyed by id, never by position, so
    reordering or inserting a topic in the manifest cannot corrupt progress."""

    completed_topics: list[str] = []
    unlocked_topics: list[str] = []
    current_topic_id: str | None = None
    scores: dict[str, int] = {}


class ChildProfile(BaseModel):
    child_id: str
    user_id: str
    name: str
    birth_year: int
    birth_month: int
    age_years: float
    # class_id is what the child actually sees. default_class_id is what the
    # birth date implies; they differ only when a parent has set an override.
    class_id: str
    default_class_id: str
    class_override: str | None = None
    experience_mode: str = "standard"
    preferred_language: str = "English"
    stars: int = 0
    current_subject_id: str | None = None
    current_topic_id: str | None = None
    completed_subjects: list[str] = []
    subject_progress: dict[str, SubjectProgress] = {}
    weak_skills: list[str] = []
    rewards: list[str] = []
    certificate_unlocked: bool = False
