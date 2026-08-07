from typing import Literal
from uuid import uuid4

from pydantic import BaseModel

from app.schemas.avatar import AvatarPayload


GuidanceAction = Literal[
    "highlight_element",
    "scroll_to_element",
    "open_safe_route",
    "show_tooltip",
    "show_next_step",
    "repeat_instruction",
    "show_hint",
    "wait_for_child_click",
    "dismiss_guide",
    "open_current_stage",
    "open_practice",
    "open_rewards",
    "open_parent_profile",
    "go_home",
]


class GuidancePayload(BaseModel):
    action: GuidanceAction
    target_id: str | None = None
    wait_for_child_click: bool = False


class CompanionStartRequest(BaseModel):
    child_id: str | None = None
    current_route: str = "/"
    is_guest: bool = True


class CompanionEventRequest(BaseModel):
    session_id: str | None = None
    child_id: str | None = None
    event_type: str
    current_route: str = "/"
    target_id: str | None = None


class CompanionResponse(BaseModel):
    request_id: str = ""
    session_id: str
    mode: str = "welcome"
    message: str
    avatar: AvatarPayload
    guidance: GuidancePayload
    next_action: str
    recommendation: dict = {}


def request_id() -> str:
    return f"req_{uuid4().hex[:10]}"
