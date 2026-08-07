from app.graph.state import GuideState
from app.services.safety_service import safe_text


def safety_node(state: GuideState) -> GuideState:
    if "message" in state:
        state["message"] = safe_text(state["message"])
    state["safety_status"] = "checked"
    return state
