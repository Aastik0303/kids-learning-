"""Practice draws from the topics a child has already met, weighted towards
whatever they found hard. Selection is deterministic given the same child state:
the shuffle is seeded, so a reload does not reshuffle the questions under them.
"""

import random
from uuid import uuid4

from app.schemas.curriculum import Topic
from app.schemas.practice import (
    PracticeAnswerRequest,
    PracticeAnswerResponse,
    PracticeStartRequest,
    PracticeStartResponse,
    PracticeSubject,
)
from app.services import activity_evaluators, curriculum_service, retention_service
from app.services.avatar_service import learning_avatar
from app.services.child_service import get_child_record, subject_progress
from app.services.errors import app_error
from app.services.history_service import record_attempt

# One practice sitting, in flight - the same shape as the lesson cursor in
# `learning_service`, and kept in memory for the same reason: it is rebuilt by
# starting practice again, while everything it produces (attempts, mastery,
# settled retention probes) is written to the database as it happens.
_active_practice: dict[str, dict] = {}

QUESTIONS_PER_SESSION = 5

CORRECT_FEEDBACK = [
    "Nice work!",
    "Great job!",
    "Well done!",
    "Amazing!",
    "You got it!",
    "Brilliant!",
    "Super!",
    "Wonderful!",
    "Hooray!",
    "Fantastic!",
]

INCORRECT_FEEDBACK_ATTEMPT_1 = [
    "Good try! Let us look once more.",
    "Almost! Try again carefully.",
    "Almost. Take another look.",
    "So close! Think about it once more.",
]

INCORRECT_FEEDBACK_ATTEMPT_2 = [
    "Keep trying! You are getting closer.",
    "Let us slow down and look carefully.",
    "Almost there! Here is a hint to help you.",
    "You are doing great. Let us try once more.",
]

INCORRECT_FEEDBACK_ATTEMPT_3_PLUS = [
    "No worries! Let us look at the hint together.",
    "Take your time. The hint will help.",
    "Let us try a different way. Look at the hint.",
    "Each try helps us learn. Here is more help.",
]


def subjects_for_child(child_id: str) -> list[PracticeSubject]:
    """Every subject in the child's class, with an honest availability flag."""
    child = get_child_record(child_id)
    detail = curriculum_service.get_class(child["class_id"])
    subjects = []
    for subject in detail.subjects:
        progress = subject_progress(child, subject.subject_id)
        practisable = [
            t for t in subject.topics if t.available and t.topic_id in progress["unlocked_topics"]
        ]
        subjects.append(
            PracticeSubject(
                subject_id=subject.subject_id,
                title=subject.title,
                class_id=subject.class_id,
                icon=subject.icon,
                unlocked=bool(practisable),
                has_activities=subject.available,
                topic_count=len(practisable),
                fun_name=subject.fun_name,
                colour=subject.colour,
                easy_line=subject.easy_line,
                topic_titles=[t.title for t in practisable],
            )
        )
    return subjects


def start_practice(payload: PracticeStartRequest) -> PracticeStartResponse:
    child = get_child_record(payload.child_id)
    subject = curriculum_service.get_subject(payload.subject_id)
    if subject.class_id != child["class_id"]:
        raise app_error("LOCKED_STAGE", "That subject belongs to a different class.", 403)
    if not subject.available:
        raise app_error(
            "TOPIC_NOT_READY",
            "This subject is still being prepared. Let us try another one.",
            409,
        )

    progress = subject_progress(child, subject.subject_id)
    introduced = [t for t in subject.topics if t.available and t.topic_id in progress["unlocked_topics"]]
    if not introduced:
        raise app_error("LOCKED_STAGE", "Practice opens after a topic is introduced.", 403)

    activities, selection_reason, topic_by_activity = _weighted_activities(
        child, subject.subject_id, introduced, progress
    )
    if not activities:
        raise app_error("MISSING_CURRICULUM", "Practice needs activities before it can start.", 404)

    session_id = f"practice_{uuid4()}"
    _active_practice[session_id] = {
        "child_id": payload.child_id,
        "subject_id": subject.subject_id,
        "activities": [a.model_dump() for a in activities],
        # Practice draws across topics, so the topic a question came from has to
        # travel with the session. Without it every practice answer was filed
        # under its activity *type*, which put rows like "identify_colour" in
        # the mastery table next to real skills.
        "topic_by_activity": topic_by_activity,
        "selection_reason": selection_reason,
        "attempts": {},
        "correct_streak": 0,
    }
    return PracticeStartResponse(
        practice_session_id=session_id,
        subject_id=subject.subject_id,
        subject_title=subject.title,
        subject_fun_name=subject.fun_name,
        subject_easy_line=subject.easy_line,
        activities=activities,
        selection_reason=selection_reason,
    )


def _weighted_activities(
    child: dict, subject_id: str, introduced: list[Topic], progress: dict
) -> tuple[list, str, dict[str, str]]:
    """Weak topics come up most, then recent ones, then mastered ones."""
    completed = set(progress["completed_topics"])
    weak_skills = set(child["weak_skills"])

    weak = [t for t in introduced if f"{subject_id}:{t.topic_id}" in weak_skills]
    recent_ids = set(progress["completed_topics"][-2:])
    if progress.get("current_topic_id"):
        recent_ids.add(progress["current_topic_id"])
    recent = [t for t in introduced if t.topic_id in recent_ids and t not in weak]
    mastered = [t for t in introduced if t.topic_id in completed and t not in weak and t not in recent]

    pool = (weak * 12) + (recent * 5) + (mastered * 3) or introduced

    seed = f"{child['child_id']}:{subject_id}:{','.join(sorted(weak_skills))}:{len(completed)}"
    rng = random.Random(seed)

    chosen: list = []
    topic_by_activity: dict[str, str] = {}
    seen_activity_ids: set[str] = set()
    attempts = 0
    while len(chosen) < QUESTIONS_PER_SESSION and attempts < 60:
        attempts += 1
        topic = rng.choice(pool)
        candidates = [
            activity
            for activity in curriculum_service.get_activities(topic.topic_id)
            if activity.activity_id not in seen_activity_ids
            # nothing to practise in a watch-and-listen activity
            and activity_evaluators.requires_answer(activity.type)
        ]
        if not candidates:
            continue
        # A topic holds several examples of the same skill. Practice takes one
        # at random rather than always the first, so a child who met "red" in
        # the adventure meets "blue" here instead of the same question twice.
        # Still deterministic: the rng is seeded from the child's own state.
        activity = rng.choice(candidates)
        chosen.append(activity)
        topic_by_activity[activity.activity_id] = topic.topic_id
        seen_activity_ids.add(activity.activity_id)

    if weak:
        reason = "weak_skills_60_recent_25_mastered_15"
    elif recent and completed:
        reason = "recent_skills_25_mastered_15"
    else:
        reason = "introduced_skills"
    return chosen[:QUESTIONS_PER_SESSION], reason, topic_by_activity


def _pick_incorrect_feedback(attempt_number: int) -> str:
    if attempt_number <= 1:
        return random.choice(INCORRECT_FEEDBACK_ATTEMPT_1)
    if attempt_number == 2:
        return random.choice(INCORRECT_FEEDBACK_ATTEMPT_2)
    return random.choice(INCORRECT_FEEDBACK_ATTEMPT_3_PLUS)


def answer_practice(payload: PracticeAnswerRequest) -> PracticeAnswerResponse:
    session = _active_practice.get(payload.practice_session_id)
    if not session:
        raise app_error("EXPIRED_LEARNING_SESSION", "Let us start practice again.", 404)
    activity = next(
        (item for item in session["activities"] if item["activity_id"] == payload.activity_id), None
    )
    if not activity:
        raise app_error("INVALID_ANSWER", "That practice question was not found.", 404)

    is_correct, normalized_answer = activity_evaluators.evaluate(
        activity_evaluators.EvaluationInput(
            activity_type=activity["type"],
            correct_answer=activity.get("correct_answer") or "",
            options=activity.get("options", []),
            answer=payload.answer,
            accepted_answers=tuple(activity.get("accept") or []),
            open_ended=bool(activity.get("open_ended")),
        )
    )

    attempts = session.setdefault("attempts", {})
    attempt_number = 0 if is_correct else attempts.get(payload.activity_id, 0) + 1
    question_changed = not is_correct and attempt_number >= 4
    attempts[payload.activity_id] = 0 if is_correct or question_changed else attempt_number
    session["correct_streak"] = session.get("correct_streak", 0) + 1 if is_correct else 0

    topic_id = session.get("topic_by_activity", {}).get(payload.activity_id, session["subject_id"])
    skill_id = f"{session['subject_id']}:{topic_id}"
    record_attempt(
        child_id=session["child_id"],
        session_id=payload.practice_session_id,
        activity_id=payload.activity_id,
        topic=topic_id,
        skill=skill_id,
        level_id=session["subject_id"],
        child_answer=normalized_answer,
        is_correct=is_correct,
        attempt_number=attempt_number,
        form_signature=activity["type"],
    )
    # Practice is where a retention probe naturally comes due: it re-asks a
    # skill days after the lesson taught it, usually in a different form. That
    # is what pays the teaching strategy the child was given at the time.
    retention_service.on_attempt(
        child_id=session["child_id"],
        skill_id=skill_id,
        form_signature=activity["type"],
        is_correct=is_correct,
    )

    if is_correct:
        streak = session["correct_streak"]
        feedback = random.choice(CORRECT_FEEDBACK)
        if streak >= 3:
            feedback = f"{feedback} {streak} in a row!"
        hint = None
    elif question_changed:
        feedback = "Let us try a different question now."
        hint = None
    else:
        feedback = _pick_incorrect_feedback(attempt_number)
        hint = activity["hint"]

    return PracticeAnswerResponse(
        is_correct=is_correct,
        feedback=feedback,
        hint=hint,
        attempt_number=0 if question_changed else attempt_number,
        question_changed=question_changed,
        avatar=learning_avatar(is_correct=is_correct, feedback=f"{feedback} {hint or ''}".strip()),
    )
