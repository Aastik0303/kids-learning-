from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.avatar import AvatarPayload


GuideMode = Literal["welcome", "navigation", "learning", "practice", "help", "reward", "parent_help"]

GuideEvent = Literal[
    "APP_OPENED",
    "HOME_OPENED",
    "PRACTICE_OPENED",
    "PRACTICE_STARTED",
    "PRACTICE_QUESTION_LOADED",
    "PRACTICE_ANSWER_CORRECT",
    "PRACTICE_ANSWER_INCORRECT",
    "PRACTICE_COMPLETED",
    "ADVENTURE_OPENED",
    "LEVEL_OPENED",
    "LEVEL_STARTED",
    "LEVEL_QUESTION_LOADED",
    "LEVEL_ANSWER_CORRECT",
    "LEVEL_ANSWER_INCORRECT",
    "LEVEL_COMPLETED",
    "WORLD_COMPLETED",
    "WORLD_UNLOCKED",
    "REWARDS_OPENED",
    "CERTIFICATE_UNLOCKED",
    "GUIDE_HELP_REQUESTED",
    "HINT_REQUESTED",
    "REPEAT_REQUESTED",
]

GuideActionType = Literal[
    "none",
    "highlight",
    "scroll_to",
    "open_safe_route",
    "show_tooltip",
    "repeat_instruction",
    "show_hint",
    "wait_for_click",
]


class GuideQuestionContext(BaseModel):
    activity_id: str
    topic: str | None = None
    concept: str | None = None
    prompt: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str | None = None
    child_answer: str | None = None
    attempt: int = 0
    hint: str | None = None


class GuideProgressContext(BaseModel):
    current_world: str | None = None
    current_level: str | None = None
    last_completed_level: str | None = None
    weak_skills: list[str] = Field(default_factory=list)
    session_stars: int = 0


class GuideRequest(BaseModel):
    session_id: str | None = None
    child_id: str | None = None
    mode: GuideMode
    event: GuideEvent
    route: str
    screen: str
    feature: str
    age_group: str = "3-6"
    preferred_language: str = "en"
    question: GuideQuestionContext | None = None
    progress: GuideProgressContext | None = None
    available_actions: list[GuideActionType] = Field(default_factory=list)
    available_targets: list[str] = Field(default_factory=list)


class GuideUiAction(BaseModel):
    type: GuideActionType = "none"
    target: str | None = None


class GuideResponse(BaseModel):
    message: str
    strategy: Literal["welcome", "navigation", "read_question", "hint", "re_explain", "celebrate", "help", "none"]
    avatar: AvatarPayload
    ui_action: GuideUiAction
    next_expected_event: str = "wait_for_child"
