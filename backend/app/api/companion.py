from uuid import uuid4

from fastapi import APIRouter

from app.schemas.avatar import AvatarPayload
from app.schemas.companion import CompanionEventRequest, CompanionResponse, CompanionStartRequest, request_id
from app.schemas.guide import GuideProgressContext, GuideRequest
from app.services import child_service
from app.services.daily_recommendation_service import WORLD_NAMES, choose_recommendation, welcome_message
from app.services.errors import app_error
from app.services.guide_agent_service import guide
from app.services.guided_navigation_service import validate_guidance
from app.services.learning_memory_service import get_latest_learning_memory

router = APIRouter(prefix="/companion", tags=["companion"])


def _child_or_guest(child_id: str | None, is_guest: bool):
    if is_guest or not child_id:
        return None
    return child_service.get_child(child_id)


@router.post("/session/start", response_model=CompanionResponse)
async def start_session(payload: CompanionStartRequest) -> CompanionResponse:
    child = _child_or_guest(payload.child_id, payload.is_guest)
    recommendation = choose_recommendation(child)
    deterministic_message = welcome_message(child, recommendation)
    session_id = f"companion_{uuid4().hex}"
    latest_memory = get_latest_learning_memory(child.child_id) if child else None
    recommended_path = recommendation.get("path_id")
    recommended_stage = recommendation.get("stage_number")
    current_level = None
    if recommended_path and recommended_stage:
        current_level = f"{WORLD_NAMES.get(recommended_path, recommended_path.title())} Level {recommended_stage}"

    last_completed_level = None
    if latest_memory:
        last_world = WORLD_NAMES.get(latest_memory.path_id, latest_memory.path_id.title())
        last_completed_level = f"{last_world} Level {latest_memory.stage_number}"
    elif recommended_path and recommended_stage and recommended_stage > 1:
        world_name = WORLD_NAMES.get(recommended_path, recommended_path.title())
        last_completed_level = f"{world_name} Level {recommended_stage - 1}"

    progress = GuideProgressContext(
        current_world=recommended_path,
        current_level=current_level,
        last_completed_level=last_completed_level,
        last_completed_title=latest_memory.title if latest_memory else None,
        last_completed_objective=latest_memory.objective if latest_memory else None,
        last_completed_at=latest_memory.completed_at if latest_memory else None,
        weak_skills=child.weak_skills if child else [],
        session_stars=child.stars if child else 0,
    )
    guide_response = guide(
        GuideRequest(
            session_id=session_id,
            child_id=child.child_id if child else payload.child_id,
            mode="welcome",
            event="APP_OPENED",
            route=payload.current_route,
            screen="home",
            feature=recommendation["kind"],
            age_group=child.age_group if child else "3-6",
            preferred_language=child.preferred_language if child else "en",
            progress=progress,
            available_actions=["highlight", "wait_for_click"],
            available_targets=[recommendation["target_id"], "continue-adventure", "start-practice"],
        )
    )
    message = guide_response.message or deterministic_message
    guidance = validate_guidance("highlight_element", recommendation["target_id"], True)
    return CompanionResponse(
        request_id=request_id(),
        session_id=session_id,
        mode="welcome",
        message=message,
        avatar=AvatarPayload(
            state=guide_response.avatar.state,
            message=message,
            speak=guide_response.avatar.speak,
            animationEffect=guide_response.avatar.animationEffect,
        ),
        guidance=guidance,
        next_action=recommendation["kind"],
        recommendation=recommendation,
    )


@router.post("/session/event", response_model=CompanionResponse)
async def session_event(payload: CompanionEventRequest) -> CompanionResponse:
    if payload.event_type not in {"route_changed", "button_clicked", "answer_submitted", "guide_step_confirmed"}:
        raise app_error("INVALID_EVENT", "Let us try that again.", 400)
    guidance = validate_guidance("wait_for_child_click")
    message = "Great! Keep going."
    return CompanionResponse(
        request_id=request_id(),
        session_id=payload.session_id or f"companion_{uuid4().hex}",
        mode="guide",
        message=message,
        avatar=AvatarPayload(state="happy", message=message, speak=False, animationEffect="none"),
        guidance=guidance,
        next_action="continue",
        recommendation={},
    )


@router.post("/next-action", response_model=CompanionResponse)
async def next_action(payload: CompanionStartRequest) -> CompanionResponse:
    return await start_session(payload)
