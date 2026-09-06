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
    TopicNotes,
)
from app.schemas.learning import Activity
from app.playground import notes as topic_notes
from app.services import child_service, curriculum_service

router = APIRouter(prefix="/curriculum", tags=["curriculum"])


@router.get("", response_model=CurriculumOverview)
def overview() -> CurriculumOverview:
    return curriculum_service.overview()


@router.get("/classes", response_model=list[ClassSummary])
def list_classes() -> list[ClassSummary]:
    return curriculum_service.list_classes()


@router.get("/classes/{class_id}", response_model=ClassDetail)
def get_class(class_id: str) -> ClassDetail:
    return curriculum_service.get_class(class_id)


@router.get("/classes/{class_id}/experience", response_model=ExperienceMode)
def get_experience(class_id: str) -> ExperienceMode:
    return curriculum_service.experience_mode_for_class(class_id)


@router.get("/subjects/{subject_id}", response_model=Subject)
def get_subject(subject_id: str) -> Subject:
    return curriculum_service.get_subject(subject_id)


@router.get("/topics/{topic_id}", response_model=Topic)
def get_topic(topic_id: str) -> Topic:
    return curriculum_service.get_topic(topic_id)


@router.get("/topics/{topic_id}/activities", response_model=list[Activity])
def get_topic_activities(topic_id: str) -> list[Activity]:
    return curriculum_service.get_activities(topic_id)


@router.get("/topics/{topic_id}/notes", response_model=TopicNotes)
def get_topic_notes(topic_id: str) -> TopicNotes:
    """What this level teaches, in the author's own words, for revising from.

    The one thing the Adventure map may hand a child besides a status. It is
    read-only in every sense that matters: no model writes it, nothing about
    fetching it is marked, no attempt or probe or episode is written, no star
    moves, and it starts no lesson - the class is still the AI Teacher and the
    schedule still decides when a level is taught.

    A level the author has not written yet comes back with `has_notes` false
    rather than an error, because a four-year-old's screen is not the place to
    surface a gap in the syllabus.
    """
    return TopicNotes(**vars(topic_notes.for_topic(topic_id)))


@router.get("/children/{child_id}/class", response_model=ClassDetail)
def class_for_child(child_id: str) -> ClassDetail:
    child = child_service.get_child(child_id)
    return curriculum_service.get_class(child.class_id)


@router.get("/children/{child_id}/class-options", response_model=list[ClassSummary])
def class_options(child_id: str) -> list[ClassSummary]:
    """Classes a parent may move this child to.

    Anchored on the class the birth date implies, not on the current one, so an
    override can never be walked further and further from the child's real age.
    """
    child = child_service.get_child(child_id)
    anchor = child.default_class_id
    allowed = {anchor, *curriculum_service.adjacent_class_ids(anchor)}
    return [c for c in curriculum_service.list_classes() if c.class_id in allowed]


@router.put("/children/{child_id}/class", response_model=ChildProfile)
def set_class_override(child_id: str, payload: ClassOverrideRequest) -> ChildProfile:
    """Parent surface only. Requires the parent's session token; a child never
    holds one, so a child cannot reach this."""
    return child_service.set_class_override(child_id, payload.session_token, payload.class_id)


@router.delete("/children/{child_id}/class", response_model=ChildProfile)
def clear_class_override(child_id: str, session_token: str) -> ChildProfile:
    return child_service.clear_class_override(child_id, session_token)
