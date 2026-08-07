from pydantic import BaseModel, Field


class ChildCreateRequest(BaseModel):
    session_token: str
    name: str = Field(min_length=1)
    age_group: str = "4-5"
    age: int | None = Field(default=None, ge=0, le=8)
    preferred_language: str = "English"


class ChildUpdateRequest(BaseModel):
    session_token: str
    name: str | None = None
    age_group: str | None = None
    age: int | None = Field(default=None, ge=0, le=8)
    preferred_language: str | None = None


class PathProgress(BaseModel):
    current_stage: int = 1
    completed_stages: list[int] = []
    unlocked_stages: list[int] = [1]
    score: int = 0


class ChildProfile(BaseModel):
    child_id: str
    user_id: str
    name: str
    age_group: str
    age: int | None = None
    learning_mode: str = "standard"
    preferred_language: str
    stars: int = 0
    current_path: str = "numbers"
    current_stage: int = 1
    completed_paths: list[str] = []
    path_progress: dict[str, PathProgress] = {}
    weak_skills: list[str] = []
    rewards: list[str] = []
    mixed_path_unlocked: bool = False
    certificate_unlocked: bool = False
