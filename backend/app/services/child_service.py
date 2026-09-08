"""Child profiles.

A child's class comes from their birth month, resolved on the server. A parent
may move them one class up or down from the parent surface; a child can never
change it, because nothing in the child-facing API accepts a class.
"""

from uuid import UUID

from app.schemas.child import ChildCreateRequest, ChildProfile, ChildUpdateRequest, SubjectProgress
from app.services import child_store, curriculum_service
from app.services.auth_service import get_user_for_token
from app.services.errors import app_error


def _seed_progress(class_id: str) -> dict[str, dict]:
    """Every subject starts with its first topic open.

    Subjects run in parallel, not in a queue: a child who loves numbers should
    not have to finish English first. Within a subject, topics open in order.
    """
    progress: dict[str, dict] = {}
    for subject in curriculum_service.get_class(class_id).subjects:
        first_topic = subject.topics[0].topic_id if subject.topics else None
        progress[subject.subject_id] = SubjectProgress(
            unlocked_topics=[first_topic] if first_topic else [],
            current_topic_id=first_topic,
        ).model_dump()
    return progress


def _apply_class(child: dict, class_id: str, default_class_id: str, age: float) -> None:
    """Point a child at a class, rebuilding progress if the class actually changed."""
    detail = curriculum_service.get_class(class_id)
    changed = child.get("class_id") != class_id
    child["class_id"] = class_id
    child["default_class_id"] = default_class_id
    child["age_years"] = age
    child["experience_mode"] = detail.experience_mode
    if changed:
        # Progress is keyed by subject id and subjects do not span classes, so a
        # class change needs a fresh set. Stars and rewards are kept.
        child["subject_progress"] = _seed_progress(class_id)
        child["completed_subjects"] = []
        first_subject = detail.subjects[0] if detail.subjects else None
        child["current_subject_id"] = first_subject.subject_id if first_subject else None
        child["current_topic_id"] = (
            first_subject.topics[0].topic_id if first_subject and first_subject.topics else None
        )


def create_child(payload: ChildCreateRequest) -> ChildProfile:
    user = get_user_for_token(payload.session_token)
    resolution = curriculum_service.resolve_class_for_child(payload.birth_year, payload.birth_month)
    state = {
        "name": payload.name,
        "birth_year": payload.birth_year,
        "birth_month": payload.birth_month,
        "preferred_language": payload.preferred_language,
        "class_override": None,
        "stars": 0,
        "weak_skills": [],
        "rewards": [],
        "certificate_unlocked": False,
        "class_id": None,
    }
    _apply_class(state, resolution.class_id, resolution.default_class_id, resolution.age_years)
    child = child_store.create(
        parent_id=UUID(user["id"]),
        name=payload.name,
        birth_year=payload.birth_year,
        birth_month=payload.birth_month,
        class_id=state["class_id"],
        experience_mode=state["experience_mode"],
        preferred_language=payload.preferred_language,
        state=state,
    )
    return ChildProfile(**child)


def list_children(session_token: str) -> list[ChildProfile]:
    user = get_user_for_token(session_token)
    return [
        ChildProfile(**sync_class_progress(child))
        for child in child_store.records_for_parent(UUID(user["id"]))
    ]


def get_child(child_id: str) -> ChildProfile:
    return ChildProfile(**get_child_record(child_id))


def get_child_record(child_id: str) -> dict:
    child = child_store.get(child_id)
    # A subject added to the curriculum after this child was created has no
    # progress of its own yet. Fill it in here, so every read of a child sees
    # the class as it is now rather than as it was on the day they signed up.
    return sync_class_progress(child)


def _owned_child(child_id: str, session_token: str) -> dict:
    user = get_user_for_token(session_token)
    child = child_store.find(child_id)
    if not child or child["user_id"] != user["id"]:
        raise app_error("INVALID_CHILD", "We could not find that child profile.", 404)
    return sync_class_progress(child)


def update_child(child_id: str, payload: ChildUpdateRequest) -> ChildProfile:
    child = _owned_child(child_id, payload.session_token)
    for field in ("name", "birth_year", "birth_month", "preferred_language"):
        value = getattr(payload, field)
        if value is not None:
            child[field] = value

    resolution = curriculum_service.resolve_class_for_child(
        child["birth_year"], child["birth_month"], child.get("class_override")
    )
    if resolution.overridden and not curriculum_service.is_adjacent_class(
        resolution.default_class_id, child["class_override"]
    ):
        # A birthday can push the default class far enough that a once-valid
        # override is no longer adjacent. Drop it rather than strand the child.
        child["class_override"] = None
        resolution = curriculum_service.resolve_class_for_child(child["birth_year"], child["birth_month"])

    _apply_class(child, resolution.class_id, resolution.default_class_id, resolution.age_years)
    child_store.save(child)
    return ChildProfile(**child)


def set_class_override(child_id: str, session_token: str, class_id: str) -> ChildProfile:
    """Parent-only. Moves a child to an adjacent class, or clears the override
    when the requested class is the one the birth date already implies."""
    child = _owned_child(child_id, session_token)
    resolution = curriculum_service.resolve_class_for_child(
        child["birth_year"], child["birth_month"], class_id
    )
    child["class_override"] = class_id if resolution.overridden else None
    _apply_class(child, resolution.class_id, resolution.default_class_id, resolution.age_years)
    child_store.save(child)
    return ChildProfile(**child)


def clear_class_override(child_id: str, session_token: str) -> ChildProfile:
    child = _owned_child(child_id, session_token)
    child["class_override"] = None
    resolution = curriculum_service.resolve_class_for_child(child["birth_year"], child["birth_month"])
    _apply_class(child, resolution.class_id, resolution.default_class_id, resolution.age_years)
    child_store.save(child)
    return ChildProfile(**child)


# --------------------------------------------------------------------------
# progress helpers
# --------------------------------------------------------------------------


def subject_progress(child: dict, subject_id: str) -> dict:
    progress = child.setdefault("subject_progress", {})
    if subject_id not in progress:
        subject = curriculum_service.get_subject(subject_id)
        first_topic = subject.topics[0].topic_id if subject.topics else None
        progress[subject_id] = SubjectProgress(
            unlocked_topics=[first_topic] if first_topic else [],
            current_topic_id=first_topic,
        ).model_dump()
    return progress[subject_id]


def sync_class_progress(child: dict) -> dict:
    """Reconcile a child's progress with the class as the curriculum has it now.

    Progress is seeded once, when the class is assigned, but the curriculum is a
    file that changes underneath it. Two things can drift, and both leave a
    subject that a child cannot enter:

    - A class gains a subject — Nursery gained Hindi — and a child created
      before that has no entry for it at all.
    - A topic leaves a subject — LKG's writing moved to Art & Writing — and the
      ids left behind in `unlocked_topics` name topics that are not on this
      subject's board any more.

    The child surface reads `unlocked_topics` to decide what is playable, so in
    either case the subject renders every topic locked with no way in, and
    Practice refuses to start because nothing counts as introduced. Reconciling
    on read opens it instead.

    Nothing earned is taken away: a completed topic stays completed and its
    score is kept, for as long as the topic is still part of the subject.
    """
    if not child.get("class_id"):
        return child
    for subject in curriculum_service.get_class(child["class_id"]).subjects:
        progress = subject_progress(child, subject.subject_id)
        _forget_departed_topics(progress, subject)
        _open_what_completions_earned(progress, subject)
    return child


def _forget_departed_topics(progress: dict, subject) -> None:
    """Drop topic ids that no longer belong to this subject, and keep a way in.

    Progress is keyed by topic id, which is what makes reordering the manifest
    safe — but an id that moved to another subject matches nothing on this
    subject's board, so it is dead weight that can also be the child's only
    unlocked topic. When it is, the subject reopens at its first topic, exactly
    as a new child would find it.
    """
    live = {topic.topic_id for topic in subject.topics}

    progress["unlocked_topics"] = [t for t in progress.get("unlocked_topics", []) if t in live]
    progress["completed_topics"] = [t for t in progress.get("completed_topics", []) if t in live]
    progress["scores"] = {t: s for t, s in progress.get("scores", {}).items() if t in live}

    if not progress["unlocked_topics"] and subject.topics:
        progress["unlocked_topics"] = [subject.topics[0].topic_id]

    if progress.get("current_topic_id") not in live:
        unfinished = [t for t in progress["unlocked_topics"] if t not in progress["completed_topics"]]
        candidates = unfinished or progress["unlocked_topics"]
        progress["current_topic_id"] = candidates[0] if candidates else None


def _open_what_completions_earned(progress: dict, subject) -> None:
    """Every finished topic opens the one after it. Say so again on read.

    Finishing a level unlocks the next one, and `award_topic_completion` writes
    both facts in the same breath. They can still come apart: a record written
    before this rule existed, an id that was renamed and pruned out of
    `unlocked_topics` by `_forget_departed_topics` above while the completion
    survived, a subject whose last topic was completed and which then grew
    another one in the manifest.

    When they do, the subject is not merely untidy - it is finished as far as
    the schedule can tell. `plan_service._candidates` looks for the first
    *unlocked* topic this child has not completed, and there is none, so the
    subject drops out of the day altogether and can never come back on its own:
    a child with one completed EVS level and nothing unlocked behind it simply
    stops being taught EVS. Restating the rule here is deterministic - it is the
    manifest's own sort order, the same one `learning_service._next_topic` uses -
    and it grants nothing that was not already earned.
    """
    ordered = subject.topics
    unlocked = list(progress.get("unlocked_topics", []))
    completed = set(progress.get("completed_topics", []))
    for index, topic in enumerate(ordered[:-1]):
        following = ordered[index + 1].topic_id
        if topic.topic_id in completed and following not in unlocked:
            unlocked.append(following)
    progress["unlocked_topics"] = unlocked

    # "Where am I" follows the board: a pointer left on a finished level while
    # an unfinished one is now open is the same drift one step further on.
    if progress.get("current_topic_id") in completed:
        unfinished = [topic_id for topic_id in unlocked if topic_id not in completed]
        if unfinished:
            progress["current_topic_id"] = unfinished[0]


def refresh_certificate_eligibility(child: dict) -> bool:
    """A certificate needs every playable topic in the class finished.

    Topics with no authored activities cannot be completed, so they are not
    counted. A class with nothing authored yet never unlocks a certificate.
    """
    detail = curriculum_service.get_class(child["class_id"])
    playable = [t.topic_id for s in detail.subjects for t in s.topics if t.available]
    if not playable:
        child["certificate_unlocked"] = False
        return False
    completed = {
        topic_id
        for progress in child.get("subject_progress", {}).values()
        for topic_id in progress.get("completed_topics", [])
    }
    child["certificate_unlocked"] = all(topic_id in completed for topic_id in playable)
    return child["certificate_unlocked"]
