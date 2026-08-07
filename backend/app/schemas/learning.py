from pydantic import BaseModel

from app.schemas.avatar import AvatarPayload


class Activity(BaseModel):
    activity_id: str
    type: str
    prompt: str
    visual_items: list[str] = []
    options: list[str]
    correct_answer: str
    hint: str
    difficulty: str = "easy"


class Stage(BaseModel):
    stage_id: str
    path_id: str
    stage_number: int
    title: str
    objective: str
    module_type: str
    difficulty: str
    intro_message: str
    passing_score: int
    star_reward: int
    activities: list[Activity] = []
    next_stage: int | None = None


class PathSummary(BaseModel):
    path_id: str
    title: str
    description: str
    total_stages: int


class LearningStartRequest(BaseModel):
    child_id: str
    path_id: str
    stage_number: int


class LearningAnswerRequest(BaseModel):
    session_id: str
    answer: str


class LearningResponse(BaseModel):
    session_id: str
    child_id: str
    path_id: str
    stage_number: int
    tutor_response: str
    activity: Activity | None = None
    is_correct: bool | None = None
    attempt_number: int = 0
    feedback: str = ""
    stars_earned: int = 0
    current_score: int = 0
    stage_completed: bool = False
    next_stage_unlocked: bool = False
    recommended_practice: bool = False
    complete: bool = False
    avatar: AvatarPayload | None = None
