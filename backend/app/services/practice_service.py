from uuid import uuid4
import random

from app.schemas.practice import PracticeAnswerRequest, PracticeAnswerResponse, PracticeStartRequest, PracticeStartResponse, PracticeTopic
from app.services.answer_normalization_service import answers_match, normalize_answer
from app.services import curriculum_service
from app.services.avatar_service import learning_avatar
from app.services.child_service import get_child
from app.services.errors import app_error
from app.services.history_service import record_attempt
from app.services.mock_storage import mock_practice_sessions


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
    "Not quite. Take another look.",
    "So close! Think about it once more.",
    "That was brave! Let us try again.",
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
    "Every try makes you smarter! Here is more help.",
]


def topics_for_child(child_id: str) -> list[PracticeTopic]:
    child = get_child(child_id)
    topics = []
    for path_id, title in [("numbers", "Numbers"), ("alphabets", "Alphabets"), ("colours", "Colours"), ("shapes", "Shapes")]:
        progress = child.path_progress.get(path_id)
        unlocked = bool(progress and progress.unlocked_stages)
        topics.append(PracticeTopic(topic=path_id, title=title, unlocked=unlocked))
    mixed_unlocked = child.mixed_path_unlocked
    topics.append(PracticeTopic(topic="mixed_final", title="Mixed Practice", unlocked=mixed_unlocked))
    return topics


def start_practice(payload: PracticeStartRequest) -> PracticeStartResponse:
    child = get_child(payload.child_id)
    available = {topic.topic: topic.unlocked for topic in topics_for_child(payload.child_id)}
    if not available.get(payload.topic):
        raise app_error("LOCKED_STAGE", "Practice opens after a topic is introduced.", 403)
    stages = curriculum_service.get_stages(payload.topic)
    activities, selection_reason = _weighted_practice_activities(child, payload.topic, stages)
    if not activities:
        raise app_error("MISSING_CURRICULUM", "Practice needs activities before it can start.", 404)
    session_id = f"practice_{uuid4()}"
    mock_practice_sessions[session_id] = {
        "child_id": payload.child_id,
        "topic": payload.topic,
        "activities": [a.model_dump() for a in activities],
        "selection_reason": selection_reason,
        "attempts": {},
        "correct_streak": 0,
    }
    return PracticeStartResponse(
        practice_session_id=session_id,
        topic=payload.topic,
        activities=activities,
        selection_reason=selection_reason,
    )


def _skill_slug(text: str) -> str:
    return text.lower().replace(" ", "_")


def _weighted_practice_activities(child, topic: str, stages) -> tuple[list, str]:
    progress = child.path_progress.get(topic)
    unlocked = set(progress.unlocked_stages if progress else [1])
    completed = set(progress.completed_stages if progress else [])
    introduced = [stage for stage in stages if stage.stage_number in unlocked]
    weak_skills = set(child.weak_skills)
    weak = [stage for stage in introduced if _skill_slug(stage.objective) in weak_skills]
    recent_numbers = set(sorted(completed)[-2:])
    if progress:
        recent_numbers.add(progress.current_stage)
    recent = [stage for stage in introduced if stage.stage_number in recent_numbers and stage not in weak]
    mastered = [stage for stage in introduced if stage.stage_number in completed and stage not in weak and stage not in recent]

    weighted_pool = (weak * 12) + (recent * 5) + (mastered * 3)
    if not weighted_pool:
        weighted_pool = introduced or stages[:1]

    seed = f"{child.child_id}:{topic}:{','.join(sorted(weak_skills))}:{len(completed)}"
    rng = random.Random(seed)
    chosen_stage_numbers: list[int] = []
    attempts = 0
    while len(chosen_stage_numbers) < 5 and attempts < 30:
        attempts += 1
        stage = rng.choice(weighted_pool)
        if chosen_stage_numbers and chosen_stage_numbers[-1] == stage.stage_number:
            continue
        if chosen_stage_numbers.count(stage.stage_number) >= 2:
            continue
        chosen_stage_numbers.append(stage.stage_number)

    chosen = []
    seen_activity_ids = set()
    for stage_number in chosen_stage_numbers:
        stage = next(item for item in stages if item.stage_number == stage_number)
        for activity in stage.activities:
            if activity.activity_id in seen_activity_ids:
                continue
            chosen.append(activity)
            seen_activity_ids.add(activity.activity_id)
            break
        if len(chosen) >= 5:
            break

    if not chosen:
        chosen = [activity for stage in introduced for activity in stage.activities][:5]

    if weak:
        reason = "weak_skills_60_recent_25_mastered_15"
    elif recent and completed:
        reason = "recent_skills_25_mastered_15"
    else:
        reason = "introduced_skills"
    return chosen[:5], reason


def _pick_incorrect_feedback(attempt_number: int) -> str:
    """Pick attempt-aware incorrect feedback with variety."""
    if attempt_number <= 1:
        return random.choice(INCORRECT_FEEDBACK_ATTEMPT_1)
    elif attempt_number == 2:
        return random.choice(INCORRECT_FEEDBACK_ATTEMPT_2)
    else:
        return random.choice(INCORRECT_FEEDBACK_ATTEMPT_3_PLUS)


def answer_practice(payload: PracticeAnswerRequest) -> PracticeAnswerResponse:
    session = mock_practice_sessions.get(payload.practice_session_id)
    if not session:
        raise app_error("EXPIRED_LEARNING_SESSION", "Let us start practice again.", 404)
    activity = next((item for item in session["activities"] if item["activity_id"] == payload.activity_id), None)
    if not activity:
        raise app_error("INVALID_ANSWER", "That practice question was not found.", 404)
    answer_type = activity.get("type", session["topic"])
    normalized_answer = normalize_answer(payload.answer, answer_type)
    is_correct = answers_match(payload.answer, activity["correct_answer"], answer_type)
    attempts = session.setdefault("attempts", {})
    attempt_number = 0 if is_correct else attempts.get(payload.activity_id, 0) + 1
    attempts[payload.activity_id] = 0 if is_correct else attempt_number

    # Track streaks
    if is_correct:
        session["correct_streak"] = session.get("correct_streak", 0) + 1
    else:
        session["correct_streak"] = 0

    record_attempt(
        child_id=session["child_id"],
        session_id=payload.practice_session_id,
        activity_id=payload.activity_id,
        topic=session["topic"],
        skill=activity.get("type", session["topic"]),
        child_answer=normalized_answer,
        is_correct=is_correct,
        attempt_number=attempt_number,
    )

    if is_correct:
        streak = session.get("correct_streak", 1)
        if streak >= 3:
            feedback = f"{random.choice(CORRECT_FEEDBACK)} {streak} in a row!"
        else:
            feedback = random.choice(CORRECT_FEEDBACK)
        hint = None
    else:
        feedback = _pick_incorrect_feedback(attempt_number)
        hint = activity["hint"]

    return PracticeAnswerResponse(
        is_correct=is_correct,
        feedback=feedback,
        hint=hint,
        avatar=learning_avatar(is_correct=is_correct, feedback=f"{feedback} {hint or ''}".strip()),
    )
