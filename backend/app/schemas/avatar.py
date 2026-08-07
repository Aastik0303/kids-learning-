from typing import Literal

from pydantic import BaseModel


AvatarState = Literal[
    "idle",
    "waving",
    "listening",
    "thinking",
    "speaking",
    "happy",
    "celebrating",
    "encouraging",
    "storytelling",
    "sleeping",
    "error_fallback",
]

AvatarEffect = Literal[
    "star_burst",
    "confetti",
    "level_unlock",
    "reward_chest",
    "gentle_hint",
    "story_transition",
    "certificate_celebration",
    "none",
]


class AvatarPayload(BaseModel):
    state: AvatarState
    message: str
    speak: bool = False
    animationEffect: AvatarEffect | None = None
    durationMs: int | None = None
