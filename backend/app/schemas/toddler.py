from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.avatar import AvatarPayload


LearningMode = Literal["standard", "toddler"]
ToddlerModule = Literal["alphabets", "numbers", "colours", "shapes"]
ToddlerActivityType = Literal["introduce", "repeat_after_me", "recognition", "count_objects", "complete"]
ToddlerResult = Literal["correct", "close", "retry", "unclear"]
ToddlerAction = Literal["speak", "listen", "repeat", "next_activity", "show_visual", "give_reward", "complete_level"]
ToddlerEmotion = Literal["happy", "encouraging", "thinking", "celebrate", "gentle_retry"]


class ModeResolutionRequest(BaseModel):
    age: int = Field(ge=0, le=8)


class ModeResolutionResponse(BaseModel):
    age: int
    learning_mode: LearningMode


class ToddlerActivity(BaseModel):
    activity_id: str
    type: ToddlerActivityType
    prompt: str
    speech: str
    concept: str
    emoji: str = ""
    word: str | None = None
    visual_items: list[str] = Field(default_factory=list)
    choices: list[str] = Field(default_factory=list)
    answer: str | None = None
    accepted: list[str] = Field(default_factory=list)


class ToddlerLevel(BaseModel):
    id: str
    mode: Literal["toddler"] = "toddler"
    module: ToddlerModule
    level: int
    title: str
    concepts: list[str] = Field(default_factory=list)
    star_reward: int = 3
    activities: list[ToddlerActivity] = Field(default_factory=list)


class ToddlerModuleSummary(BaseModel):
    module: ToddlerModule
    title: str
    icon: str
    levels: int


class SpeechEvaluation(BaseModel):
    result: ToddlerResult
    confidence: float
    expected: str
    heard: str
    retry: bool


class ToddlerGuideResponse(BaseModel):
    speech: str
    emotion: ToddlerEmotion
    emoji: str
    action: ToddlerAction
    repeat: bool = False
    target: str | None = None


class ToddlerStartRequest(BaseModel):
    child_id: str
    module: ToddlerModule = "alphabets"
    level: int = 1
    practice: bool = False


class ToddlerAnswerRequest(BaseModel):
    session_id: str
    answer: str = ""
    recognized_speech: str = ""


class ToddlerResponse(BaseModel):
    session_id: str
    child_id: str
    module: ToddlerModule
    level: int
    activity: ToddlerActivity | None = None
    guide: ToddlerGuideResponse
    evaluation: SpeechEvaluation | None = None
    stars_earned: int = 0
    total_stars: int = 0
    attempt_count: int = 0
    completed_activities: list[str] = Field(default_factory=list)
    level_completed: bool = False
    next_level_unlocked: bool = False
    learned_concepts: list[str] = Field(default_factory=list)
    avatar: AvatarPayload
