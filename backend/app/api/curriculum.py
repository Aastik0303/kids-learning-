"""Read-only curriculum surface.

Everything the client renders as curriculum comes from here, so the frontend
holds no class, subject or topic names of its own.
"""

from fastapi import APIRouter

from app.schemas.child import ChildProfile
from app.schemas.curriculum import (
    ClassDetail,
    ClassOverrideRequest,
    ClassSummary,
    CurriculumOverview,
    ExperienceMode,
    Subject,
    Topic,
)
from app.schemas.learning import Activity
from app.services import child_service, curriculum_service

router = APIRouter(prefix="/curriculum", tags=["curriculum"])


@router.get("", response_model=CurriculumOverview)
async def overview() -> CurriculumOverview:
    return curriculum_service.overview()


@router.get("/classes", response_model=list[ClassSummary])
async def list_classes() -> list[ClassSummary]:
    return curriculum_service.list_classes()


@router.get("/classes/{class_id}", response_model=ClassDetail)
async def get_class(class_id: str) -> ClassDetail:
    return curriculum_service.get_class(class_id)


@router.get("/classes/{class_id}/experience", response_model=ExperienceMode)
async def get_experience(class_id: str) -> ExperienceMode:
    return curriculum_service.experience_mode_for_class(class_id)


@router.get("/subjects/{subject_id}", response_model=Subject)
async def get_subject(subject_id: str) -> Subject:
    return curriculum_service.get_subject(subject_id)


@router.get("/topics/{topic_id}", response_model=Topic)
async def get_topic(topic_id: str) -> Topic:
    return curriculum_service.get_topic(topic_id)


@router.get("/topics/{topic_id}/activities", response_model=list[Activity])
async def get_topic_activities(topic_id: str) -> list[Activity]:
    return curriculum_service.get_activities(topic_id)


@router.get("/children/{child_id}/class", response_model=ClassDetail)
async def class_for_child(child_id: str) -> ClassDetail:
    child = child_service.get_child(child_id)
    return curriculum_service.get_class(child.class_id)


@router.get("/children/{child_id}/class-options", response_model=list[ClassSummary])
async def class_options(child_id: str) -> list[ClassSummary]:
    """Classes a parent may move this child to.

    Anchored on the class the birth date implies, not on the current one, so an
    override can never be walked further and further from the child's real age.
    """
    child = child_service.get_child(child_id)
    anchor = child.default_class_id
    allowed = {anchor, *curriculum_service.adjacent_class_ids(anchor)}
    return [c for c in curriculum_service.list_classes() if c.class_id in allowed]


@router.put("/children/{child_id}/class", response_model=ChildProfile)
async def set_class_override(child_id: str, payload: ClassOverrideRequest) -> ChildProfile:
    """Parent surface only. Requires the parent's session token; a child never
    holds one, so a child cannot reach this."""
    return child_service.set_class_override(child_id, payload.session_token, payload.class_id)


@router.delete("/children/{child_id}/class", response_model=ChildProfile)
async def clear_class_override(child_id: str, session_token: str) -> ChildProfile:
    return child_service.clear_class_override(child_id, session_token)
