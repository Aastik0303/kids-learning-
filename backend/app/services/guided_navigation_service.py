from app.schemas.companion import GuidanceAction, GuidancePayload
from app.services.errors import app_error


APPROVED_GUIDE_TARGETS = {
    "start-practice",
    "continue-adventure",
    "open-rewards",
    "ask-guide",
    "parent-profile",
    "current-map-level",
    "open-certificate",
}

APPROVED_ACTIONS = {
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
}


def validate_guidance(action: GuidanceAction, target_id: str | None = None, wait_for_child_click: bool = False) -> GuidancePayload:
    if action not in APPROVED_ACTIONS:
        raise app_error("UNSAFE_GUIDANCE_ACTION", "Let us use a safe guide step.", 400)
    if target_id and target_id not in APPROVED_GUIDE_TARGETS:
        raise app_error("UNSAFE_GUIDANCE_TARGET", "Let us use a safe guide step.", 400)
    return GuidancePayload(action=action, target_id=target_id, wait_for_child_click=wait_for_child_click)
