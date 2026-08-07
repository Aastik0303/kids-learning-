import random
from datetime import date
from uuid import uuid4

from app.config import get_settings
from app.schemas.child import PathProgress
from app.schemas.learning import Activity, LearningAnswerRequest, LearningResponse, LearningStartRequest
from app.services.answer_resolution_service import AnswerResolutionContext, resolved_answers_match
from app.services import curriculum_service
from app.services.avatar_service import learning_avatar
from app.services.child_service import CORE_PATHS, get_child, unlock_mixed_if_ready
from app.services.daily_recommendation_service import WORLD_ORDER
from app.services.content_generator import get_content_generator
from app.services.errors import app_error
from app.services.history_service import record_attempt
from app.services.mock_storage import mock_certificates, mock_child_profiles, mock_learning_sessions


CORRECT_FEEDBACK = [
    "Great counting! Here is the next one.",
    "Well done! Let us keep going.",
    "You got it! On to the next question.",
    "Brilliant! Ready for the next one?",
    "Wonderful! Here comes another.",
    "Amazing work! Next question coming up.",
    "Superb! Let us try the next one.",
    "Nice work! Keep going.",
]

STAGE_COMPLETE_SUCCESS = [
    "Wonderful work! This level is complete.",
    "You finished the level! Great effort.",
    "Level done! What an achievement.",
    "All complete! You were fantastic.",
    "Stage cleared! You are a superstar.",
]

STAGE_COMPLETE_NEEDS_PRACTICE = [
    "Let us practise this one a little more.",
    "You tried hard! A little more practice will help.",
    "Almost there! Let us practise and come back stronger.",
    "Good effort! Some practice will help.",
]

WRONG_ATTEMPT_2 = [
    "Almost there! Let us look again with fresh eyes. ",
    "You are so close! Let us try once more. ",
    "Almost. Keep going! ",
    "Do not worry. Let us look at this together. ",
]

WRONG_ATTEMPT_3_PLUS = [
    "Good try. We can practise this together slowly.",
    "No worries! Let us break it down step by step.",
    "Take your time. We will get there together.",
    "Every try teaches us something new. Let us keep going.",
]


def _child_dict(child_id: str) -> dict:
    if child_id not in mock_child_profiles:
        raise app_error("INVALID_CHILD", "We could not find that child profile.", 404)
    return mock_child_profiles[child_id]


def _progress_for(child: dict, path_id: str) -> dict:
    return child["path_progress"].setdefault(path_id, PathProgress().model_dump())


def _check_access(child: dict, path_id: str, stage_number: int) -> None:
    if path_id not in WORLD_ORDER:
        raise app_error("MISSING_CURRICULUM", "That learning path is not available.", 404)
    path_index = WORLD_ORDER.index(path_id)
    for previous_path in WORLD_ORDER[:path_index]:
        if previous_path not in child["completed_paths"]:
            raise app_error("LOCKED_STAGE", "Follow the glowing adventure path first.", 403)
    if path_id == "mixed_final" and not child.get("mixed_path_unlocked"):
        raise app_error("LOCKED_STAGE", "The final path unlocks after the four learning paths.", 403)
    progress = _progress_for(child, path_id)
    if stage_number not in progress["unlocked_stages"]:
        raise app_error("LOCKED_STAGE", "This stage is not unlocked yet.", 403)


def start_learning(payload: LearningStartRequest) -> LearningResponse:
    child = _child_dict(payload.child_id)
    _check_access(child, payload.path_id, payload.stage_number)
    stage = curriculum_service.get_stage(payload.path_id, payload.stage_number)
    if not stage.activities:
        raise app_error("MISSING_CURRICULUM", "This stage needs activities before it can start.", 404)

    session_id = f"learn_{uuid4()}"
    generator = get_content_generator(get_settings().llm_provider)
    mock_learning_sessions[session_id] = {
        "session_id": session_id,
        "child_id": payload.child_id,
        "path_id": payload.path_id,
        "stage_number": payload.stage_number,
        "activity_index": 0,
        "attempt_number": 0,
        "correct_count": 0,
        "correct_streak": 0,
        "stage_completed": False,
    }
    tutor_response = generator.tutor_intro(child["name"], stage)
    return LearningResponse(
        session_id=session_id,
        child_id=payload.child_id,
        path_id=payload.path_id,
        stage_number=payload.stage_number,
        tutor_response=tutor_response,
        activity=stage.activities[0],
        avatar=learning_avatar(is_correct=None, feedback="", tutor_response=tutor_response),
    )


def continue_learning(session_id: str) -> LearningResponse:
    session = mock_learning_sessions.get(session_id)
    if not session:
        raise app_error("EXPIRED_LEARNING_SESSION", "Let us start this stage again.", 404)
    stage = curriculum_service.get_stage(session["path_id"], session["stage_number"])
    activity = None if session["stage_completed"] else stage.activities[session["activity_index"]]
    return _response(session, stage, activity=activity)


def answer_learning(payload: LearningAnswerRequest) -> LearningResponse:
    session = mock_learning_sessions.get(payload.session_id)
    if not session:
        raise app_error("EXPIRED_LEARNING_SESSION", "Let us start this stage again.", 404)
    if session["stage_completed"]:
        return continue_learning(payload.session_id)

    child = _child_dict(session["child_id"])
    stage = curriculum_service.get_stage(session["path_id"], session["stage_number"])
    activity = stage.activities[session["activity_index"]]
    is_correct, resolved = resolved_answers_match(
        AnswerResolutionContext(
            transcript=payload.answer,
            confidence=0.9,
            answer_type=activity.type,
            correct_answer=activity.correct_answer,
            accepted_answers=[activity.correct_answer],
            options=activity.options,
        )
    )
    normalized_answer = resolved.normalized
    next_attempt_number = 0 if is_correct else session["attempt_number"] + 1
    record_attempt(
        child_id=session["child_id"],
        session_id=session["session_id"],
        activity_id=activity.activity_id,
        topic=stage.path_id,
        skill=stage.objective.lower().replace(" ", "_"),
        level_id=stage.stage_id,
        child_answer=normalized_answer,
        is_correct=is_correct,
        attempt_number=next_attempt_number,
    )

    if is_correct:
        child["stars"] += 3
        session["correct_count"] += 1
        session["correct_streak"] = session.get("correct_streak", 0) + 1
        session["attempt_number"] = 0
        session["activity_index"] += 1
        if session["activity_index"] >= len(stage.activities):
            return _complete_stage(session, child, stage, is_correct=True, stars_earned=3)

        streak = session.get("correct_streak", 1)
        if streak >= 3:
            feedback = f"{random.choice(CORRECT_FEEDBACK)} {streak} correct in a row!"
        else:
            feedback = random.choice(CORRECT_FEEDBACK)

        next_activity = stage.activities[session["activity_index"]]
        return _response(
            session,
            stage,
            activity=next_activity,
            is_correct=True,
            feedback=feedback,
            stars_earned=3,
        )

    session["attempt_number"] += 1
    session["correct_streak"] = 0
    generator = get_content_generator(get_settings().llm_provider)
    if session["attempt_number"] == 1:
        feedback = generator.hint(stage, activity.hint)
    elif session["attempt_number"] == 2:
        prefix = random.choice(WRONG_ATTEMPT_2)
        feedback = prefix + activity.hint
    else:
        weak_skill = stage.objective.lower().replace(" ", "_")
        if weak_skill not in child["weak_skills"]:
            child["weak_skills"].append(weak_skill)
        feedback = random.choice(WRONG_ATTEMPT_3_PLUS)

    return _response(
        session,
        stage,
        activity=activity,
        is_correct=False,
        feedback=feedback,
        recommended_practice=session["attempt_number"] >= 3,
    )


def retry_learning(session_id: str) -> LearningResponse:
    return continue_learning(session_id)


def _complete_stage(session: dict, child: dict, stage, is_correct: bool, stars_earned: int) -> LearningResponse:
    score = round((session["correct_count"] / len(stage.activities)) * 100)
    session["stage_completed"] = score >= stage.passing_score
    session["score"] = score
    recommended_practice = 70 <= score < 80
    stage_reward = 0
    next_stage_unlocked = False

    # Bonus for perfect stage
    perfect_bonus = 0
    if score == 100:
        perfect_bonus = 3
        child["stars"] += perfect_bonus

    if session["stage_completed"]:
        progress = _progress_for(child, stage.path_id)
        if stage.stage_number not in progress["completed_stages"]:
            progress["completed_stages"].append(stage.stage_number)
        progress["score"] = score
        progress["current_stage"] = stage.next_stage or stage.stage_number
        stage_reward = stage.star_reward
        child["stars"] += stage_reward

        if stage.next_stage:
            if stage.next_stage not in progress["unlocked_stages"]:
                progress["unlocked_stages"].append(stage.next_stage)
            next_stage_unlocked = True
        else:
            _complete_path(child, stage.path_id)
    else:
        weak_skill = stage.objective.lower().replace(" ", "_")
        if weak_skill not in child["weak_skills"]:
            child["weak_skills"].append(weak_skill)
        recommended_practice = True

    if session["stage_completed"]:
        if score == 100:
            feedback = "All correct! Every answer was right."
        else:
            feedback = random.choice(STAGE_COMPLETE_SUCCESS)
    else:
        feedback = random.choice(STAGE_COMPLETE_NEEDS_PRACTICE)

    return _response(
        session,
        stage,
        activity=None,
        is_correct=is_correct,
        feedback=feedback,
        stars_earned=stars_earned + stage_reward + perfect_bonus,
        stage_completed=session["stage_completed"],
        next_stage_unlocked=next_stage_unlocked,
        recommended_practice=recommended_practice,
        complete=True,
    )


def _complete_path(child: dict, path_id: str) -> None:
    if path_id not in child["completed_paths"]:
        child["completed_paths"].append(path_id)
    badge = {
        "numbers": "Number Friend",
        "alphabets": "Letter Listener",
        "colours": "Colour Finder",
        "shapes": "Shape Spotter",
        "mixed_final": "Little Learning Explorer",
    }.get(path_id)
    if badge and badge not in child["rewards"]:
        child["rewards"].append(badge)
    unlock_mixed_if_ready(child)
    if path_id == "mixed_final":
        child["certificate_unlocked"] = True
        cert_id = f"cert_{uuid4().hex[:8]}"
        mock_certificates[child["child_id"]] = {
            "unlocked": True,
            "certificate_id": cert_id,
            "child_name": child["name"],
            "completion_message": "Completed the AI Nursery Learning Path",
            "completion_date": date.today().isoformat(),
            "stars_earned": child["stars"],
        }


def _response(
    session: dict,
    stage,
    activity: Activity | None,
    is_correct: bool | None = None,
    feedback: str = "",
    stars_earned: int = 0,
    stage_completed: bool = False,
    next_stage_unlocked: bool = False,
    recommended_practice: bool = False,
    complete: bool = False,
) -> LearningResponse:
    score = session.get("score", round((session["correct_count"] / len(stage.activities)) * 100))
    return LearningResponse(
        session_id=session["session_id"],
        child_id=session["child_id"],
        path_id=session["path_id"],
        stage_number=session["stage_number"],
        tutor_response=stage.intro_message,
        activity=activity,
        is_correct=is_correct,
        attempt_number=session["attempt_number"],
        feedback=feedback,
        stars_earned=stars_earned,
        current_score=score,
        stage_completed=stage_completed,
        next_stage_unlocked=next_stage_unlocked,
        recommended_practice=recommended_practice,
        complete=complete,
        avatar=learning_avatar(
            is_correct=is_correct,
            feedback=feedback,
            tutor_response=stage.intro_message,
            complete=complete,
            next_stage_unlocked=next_stage_unlocked,
            recommended_practice=recommended_practice,
        ),
    )


def seed_demo_child(child_id: str) -> dict:
    child = _child_dict(child_id)
    for path_id in CORE_PATHS:
        stages = curriculum_service.get_stages(path_id)
        progress = _progress_for(child, path_id)
        progress["completed_stages"] = [stage.stage_number for stage in stages]
        progress["unlocked_stages"] = [stage.stage_number for stage in stages]
        progress["current_stage"] = stages[-1].stage_number
        progress["score"] = 100
        if path_id not in child["completed_paths"]:
            child["completed_paths"].append(path_id)
    child["stars"] = max(child["stars"], 80)
    unlock_mixed_if_ready(child)
    return get_child(child_id).model_dump()
