from uuid import uuid4

from fastapi import APIRouter

from app.schemas.avatar import AvatarPayload
from app.schemas.companion import CompanionEventRequest, CompanionResponse, CompanionStartRequest, request_id
from app.schemas.guide import GuideProgressContext, GuideRequest
from app.services import child_service, curriculum_service
from app.services.daily_recommendation_service import choose_recommendation, welcome_message
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
def start_session(payload: CompanionStartRequest) -> CompanionResponse:
    child = _child_or_guest(payload.child_id, payload.is_guest)
    recommendation = choose_recommendation(child)
    deterministic_message = welcome_message(child, recommendation)
    session_id = f"companion_{uuid4().hex}"
    latest_memory = get_latest_learning_memory(child.child_id) if child else None

    # Every label below is read from the manifest, never hardcoded here.
    recommended_subject_id = recommendation.get("subject_id")
    recommended_topic_id = recommendation.get("topic_id")
    current_subject = (
        curriculum_service.get_subject(recommended_subject_id).title if recommended_subject_id else None
    )
    current_topic = (
        curriculum_service.get_topic(recommended_topic_id).title if recommended_topic_id else None
    )
    last_completed_topic = None
    if latest_memory:
        last_subject = curriculum_service.get_subject(latest_memory.subject_id)
        last_completed_topic = f"{last_subject.title} - {latest_memory.title}"

    progress = GuideProgressContext(
        current_class=child.class_id if child else None,
        current_subject=current_subject,
        current_topic=current_topic,
        last_completed_topic=last_completed_topic,
        last_completed_title=latest_memory.title if latest_memory else None,
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
            class_id=child.class_id if child else None,
            experience_mode=child.experience_mode if child else "standard",
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
def session_event(payload: CompanionEventRequest) -> CompanionResponse:
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
def next_action(payload: CompanionStartRequest) -> CompanionResponse:
    return start_session(payload)
