from datetime import datetime
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
    "TOPIC_OPENED",
    "TOPIC_STARTED",
    "TOPIC_QUESTION_LOADED",
    "TOPIC_ANSWER_CORRECT",
    "TOPIC_ANSWER_INCORRECT",
    "TOPIC_COMPLETED",
    "SUBJECT_COMPLETED",
    "TOPIC_UNLOCKED",
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

GuideVisualActionType = Literal[
    "none",
    "pulse",
    "highlight",
    "highlight_sequence",
    "dim_others",
    "group_objects",
    "trace_shape",
    "show_example",
]


class GuideConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=600)


class GuideQuestionContext(BaseModel):
    activity_id: str
    topic: str | None = None
    concept: str | None = None
    learning_objective: str | None = None
    prompt: str
    answer_type: str | None = None
    options: list[str] = Field(default_factory=list)
    correct_answer: str | None = None
    child_answer: str | None = None
    attempt: int = 0
    hint: str | None = None
    visual_items: list[str] = Field(default_factory=list)
    accepted_answers: list[str] = Field(default_factory=list)
    recent_answers: list[str] = Field(default_factory=list)
    example: str | None = None
    difficulty: str | None = None


class GuideProgressContext(BaseModel):
    current_class: str | None = None
    current_subject: str | None = None
    current_topic: str | None = None
    last_completed_topic: str | None = None
    last_completed_title: str | None = None
    last_completed_at: datetime | None = None
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
    class_id: str | None = None
    # Presentation mode from the manifest: "early" or "standard".
    experience_mode: str = "standard"
    preferred_language: str = "en"
    conversation: list[GuideConversationTurn] = Field(default_factory=list, max_length=8)
    question: GuideQuestionContext | None = None
    progress: GuideProgressContext | None = None
    available_actions: list[GuideActionType] = Field(default_factory=list)
    available_targets: list[str] = Field(default_factory=list)
    allowed_visual_targets: list[str] = Field(default_factory=list)


class GuideUiAction(BaseModel):
    type: GuideActionType = "none"
    target: str | None = None


class GuideVisualAction(BaseModel):
    type: GuideVisualActionType = "none"
    targets: list[str] = Field(default_factory=list)


class GuideResponse(BaseModel):
    message: str
    strategy: Literal["welcome", "navigation", "read_question", "visual_explanation", "hint", "re_explain", "celebrate", "help", "none"]
    avatar: AvatarPayload
    ui_action: GuideUiAction
    visual_action: GuideVisualAction = Field(default_factory=GuideVisualAction)
    next_expected_event: str = "wait_for_child"
