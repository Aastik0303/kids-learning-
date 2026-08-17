"""What to offer a child the moment they arrive.

Every label here comes from the manifest. There are no hardcoded curriculum
names, so adding a subject changes the greeting without touching this file.
"""

from typing import Literal

from app.schemas.child import ChildProfile
from app.services import curriculum_service

RecommendationKind = Literal[
    "start_next_topic",
    "recommended_practice",
    "open_certificate",
    "show_safe_choices",
]


def next_topic(child: ChildProfile) -> tuple[str | None, str | None]:
    """The first unlocked, playable, unfinished topic in the child's class.

    Subjects are walked in manifest order, so a child who is mid-way through
    Maths is offered Maths before English.
    """
    detail = curriculum_service.get_class(child.class_id)
    for subject in detail.subjects:
        progress = child.subject_progress.get(subject.subject_id)
        completed = set(progress.completed_topics) if progress else set()
        unlocked = set(progress.unlocked_topics) if progress else set()
        for topic in subject.topics:
            if not topic.available or topic.topic_id in completed:
                continue
            if topic.topic_id in unlocked:
                return subject.subject_id, topic.topic_id
    return None, None


def choose_recommendation(child: ChildProfile | None) -> dict:
    if child is None:
        return {
            "kind": "show_safe_choices",
            "subject_id": None,
            "topic_id": None,
            "target_id": "continue-adventure",
            "route": "/adventure",
            "label": "Start Learning",
        }

    if child.certificate_unlocked:
        return {
            "kind": "open_certificate",
            "subject_id": None,
            "topic_id": None,
            "target_id": "open-certificate",
            "route": "/certificate",
            "label": "Open Certificate",
        }

    subject_id, topic_id = next_topic(child)
    if subject_id and topic_id:
        return {
            "kind": "start_next_topic",
            "subject_id": subject_id,
            "topic_id": topic_id,
            "target_id": "continue-adventure",
            "route": "/adventure",
            "label": "Continue Adventure",
        }

    if child.weak_skills:
        return {
            "kind": "recommended_practice",
            "subject_id": None,
            "topic_id": None,
            "target_id": "start-practice",
            "route": "/practice",
            "label": "Start Practice",
        }

    return {
        "kind": "show_safe_choices",
        "subject_id": None,
        "topic_id": None,
        "target_id": "continue-adventure",
        "route": "/adventure",
        "label": "Explore Subjects",
    }


def welcome_message(child: ChildProfile | None, recommendation: dict) -> str:
    if child is None:
        return "Hello! Welcome to Saksham IQ."

    name = child.name or "Explorer"
    if recommendation["kind"] == "open_certificate":
        return f"Welcome back, {name}! Your certificate is ready."

    topic_id = recommendation.get("topic_id")
    if topic_id:
        topic = curriculum_service.get_topic(topic_id)
        subject = curriculum_service.get_subject(topic.subject_id)
        progress = child.subject_progress.get(topic.subject_id)
        done = len(progress.completed_topics) if progress else 0
        if done:
            return (
                f"Welcome back, {name}! You have finished {done} "
                f"{'topic' if done == 1 else 'topics'} in {subject.title}. "
                f"Today, let us try {topic.title}."
            )
        return f"Hello, {name}! Let us begin with {topic.title}."

    if recommendation["kind"] == "recommended_practice":
        return f"Welcome back, {name}! Let us start a short practice."

    detail = curriculum_service.get_class(child.class_id)
    return f"Hello, {name}! Your {detail.title} subjects are ready."
