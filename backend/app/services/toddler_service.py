from difflib import SequenceMatcher
from uuid import uuid4

from app.schemas.avatar import AvatarPayload
from app.schemas.child import PathProgress
from app.schemas.toddler import (
    ModeResolutionResponse,
    SpeechEvaluation,
    ToddlerActivity,
    ToddlerGuideResponse,
    ToddlerLevel,
    ToddlerModuleSummary,
    ToddlerResponse,
    ToddlerStartRequest,
)
from app.services.answer_normalization_service import normalize_answer
from app.services.child_service import resolve_learning_mode
from app.services.errors import app_error
from app.services.mock_storage import mock_child_profiles, mock_toddler_sessions


TODDLER_CURRICULUM: dict[str, list[ToddlerLevel]] = {
    "alphabets": [
        ToddlerLevel(
            id="toddler-alphabet-abc",
            module="alphabets",
            level=1,
            title="Meet A B C",
            concepts=["A", "B", "C"],
            activities=[
                ToddlerActivity(activity_id="abc-intro-a", type="introduce", prompt="Look! This is A.", speech="This is A. A is for Apple.", concept="A", emoji="🍎", word="Apple", visual_items=["A", "🍎"]),
                ToddlerActivity(activity_id="abc-repeat-a", type="repeat_after_me", prompt="Can you say A?", speech="Now you try. Say A.", concept="A", emoji="🎤", answer="A", accepted=["a", "ay", "hey"]),
                ToddlerActivity(activity_id="abc-find-b", type="recognition", prompt="Can you find B?", speech="Tap B.", concept="B", emoji="🔤", choices=["A", "B", "C"], answer="B"),
                ToddlerActivity(activity_id="abc-repeat-c", type="repeat_after_me", prompt="Can you say C?", speech="Say C.", concept="C", emoji="🐱", answer="C", accepted=["c", "see", "sea"]),
            ],
        ),
        ToddlerLevel(
            id="toddler-alphabet-def",
            module="alphabets",
            level=2,
            title="Meet D E F",
            concepts=["D", "E", "F"],
            activities=[
                ToddlerActivity(activity_id="def-intro-d", type="introduce", prompt="Look! This is D.", speech="This is D. D is for Dog.", concept="D", emoji="🐶", word="Dog", visual_items=["D", "🐶"]),
                ToddlerActivity(activity_id="def-repeat-d", type="repeat_after_me", prompt="Can you say D?", speech="Say D.", concept="D", emoji="🎤", answer="D", accepted=["d", "dee"]),
                ToddlerActivity(activity_id="def-find-e", type="recognition", prompt="Can you find E?", speech="Tap E.", concept="E", emoji="🥚", choices=["D", "E", "F"], answer="E"),
            ],
        ),
    ],
    "numbers": [
        ToddlerLevel(
            id="toddler-numbers-123",
            module="numbers",
            level=1,
            title="Meet 1 2 3",
            concepts=["1", "2", "3"],
            activities=[
                ToddlerActivity(activity_id="num-intro-1", type="introduce", prompt="Look! One apple.", speech="This is one.", concept="1", emoji="🍎", visual_items=["1", "🍎"]),
                ToddlerActivity(activity_id="num-count-2", type="count_objects", prompt="How many apples?", speech="Count the apples.", concept="2", emoji="🍎", visual_items=["🍎", "🍎"], choices=["1", "2", "3"], answer="2"),
                ToddlerActivity(activity_id="num-repeat-2", type="repeat_after_me", prompt="Can you say two?", speech="Say two.", concept="2", emoji="🎤", answer="2", accepted=["2", "two", "too", "to"]),
                ToddlerActivity(activity_id="num-find-3", type="recognition", prompt="Can you find 3?", speech="Tap 3.", concept="3", emoji="🔢", choices=["1", "2", "3"], answer="3"),
            ],
        )
    ],
    "colours": [
        ToddlerLevel(
            id="toddler-colours-rby",
            module="colours",
            level=1,
            title="Red Yellow Blue",
            concepts=["Red", "Yellow", "Blue"],
            activities=[
                ToddlerActivity(activity_id="colour-intro-red", type="introduce", prompt="This is red.", speech="This is red.", concept="Red", emoji="🔴", visual_items=["🔴"]),
                ToddlerActivity(activity_id="colour-repeat-red", type="repeat_after_me", prompt="Can you say red?", speech="Say red.", concept="Red", emoji="🎤", answer="Red", accepted=["red"]),
                ToddlerActivity(activity_id="colour-find-red", type="recognition", prompt="Which one is red?", speech="Tap red.", concept="Red", emoji="🔴", choices=["🔴", "🟡", "🔵"], answer="🔴", accepted=["red"]),
                ToddlerActivity(activity_id="colour-intro-yellow", type="introduce", prompt="This is yellow.", speech="Yellow shines like the sun.", concept="Yellow", emoji="🟡", visual_items=["🟡"]),
                ToddlerActivity(activity_id="colour-repeat-yellow", type="repeat_after_me", prompt="Can you say yellow?", speech="Say yellow.", concept="Yellow", emoji="🎤", answer="Yellow", accepted=["yellow"]),
                ToddlerActivity(activity_id="colour-find-yellow", type="recognition", prompt="Which one is yellow?", speech="Tap yellow.", concept="Yellow", emoji="🟡", choices=["🔵", "🟡", "🔴"], answer="🟡", accepted=["yellow"]),
                ToddlerActivity(activity_id="colour-intro-blue", type="introduce", prompt="This is blue.", speech="Blue looks like the sky.", concept="Blue", emoji="🔵", visual_items=["🔵"]),
                ToddlerActivity(activity_id="colour-repeat-blue", type="repeat_after_me", prompt="Can you say blue?", speech="Say blue.", concept="Blue", emoji="🎤", answer="Blue", accepted=["blue"]),
                ToddlerActivity(activity_id="colour-find-blue", type="recognition", prompt="Which one is blue?", speech="Tap blue.", concept="Blue", emoji="🔵", choices=["🟡", "🔴", "🔵"], answer="🔵", accepted=["blue"]),
            ],
        )
    ],
    "shapes": [
        ToddlerLevel(
            id="toddler-shapes-first",
            module="shapes",
            level=1,
            title="Circle Square Star",
            concepts=["Circle", "Square", "Star"],
            activities=[
                ToddlerActivity(activity_id="shape-intro-circle", type="introduce", prompt="This is a circle.", speech="This is a circle.", concept="Circle", emoji="⭕", visual_items=["⭕"]),
                ToddlerActivity(activity_id="shape-repeat-circle", type="repeat_after_me", prompt="Can you say circle?", speech="Say circle.", concept="Circle", emoji="🎤", answer="Circle", accepted=["circle", "sircle"]),
                ToddlerActivity(activity_id="shape-find-star", type="recognition", prompt="Can you find the star?", speech="Tap the star.", concept="Star", emoji="⭐", choices=["⭕", "⬜", "⭐"], answer="⭐", accepted=["star"]),
            ],
        )
    ],
}


def resolve_mode(age: int) -> ModeResolutionResponse:
    return ModeResolutionResponse(age=age, learning_mode=resolve_learning_mode(age))


def list_modules() -> list[ToddlerModuleSummary]:
    icons = {"alphabets": "🔤", "numbers": "🔢", "colours": "🎨", "shapes": "⭐"}
    titles = {"alphabets": "ABC", "numbers": "123", "colours": "Colours", "shapes": "Shapes"}
    return [ToddlerModuleSummary(module=module, title=titles[module], icon=icons[module], levels=len(levels)) for module, levels in TODDLER_CURRICULUM.items()]


def get_levels(module: str) -> list[ToddlerLevel]:
    levels = TODDLER_CURRICULUM.get(module)
    if not levels:
        raise app_error("MISSING_TODDLER_CURRICULUM", "That toddler lesson is not ready.", 404)
    return levels


def _get_level(module: str, level_number: int) -> ToddlerLevel:
    for level in get_levels(module):
        if level.level == level_number:
            return level
    raise app_error("MISSING_TODDLER_CURRICULUM", "That toddler level is not ready.", 404)


def _child(child_id: str) -> dict:
    child = mock_child_profiles.get(child_id)
    if not child:
        raise app_error("INVALID_CHILD", "We could not find that child profile.", 404)
    return child


def _toddler_progress(child: dict) -> dict:
    return child["path_progress"].setdefault("toddler", PathProgress(unlocked_stages=[1]).model_dump())


def start_toddler(payload: ToddlerStartRequest) -> ToddlerResponse:
    child = _child(payload.child_id)
    level = _get_level(payload.module, payload.level)
    progress = _toddler_progress(child)
    if payload.level not in progress["unlocked_stages"]:
        raise app_error("LOCKED_TODDLER_LEVEL", "This toddler level opens soon.", 403)
    session_id = f"toddler_{uuid4()}"
    mock_toddler_sessions[session_id] = {
        "session_id": session_id,
        "child_id": payload.child_id,
        "module": payload.module,
        "level": payload.level,
        "activity_index": 0,
        "attempt_count": 0,
        "completed_activities": [],
        "learned_concepts": [],
        "practice": payload.practice,
    }
    activity = level.activities[0]
    return _response(mock_toddler_sessions[session_id], level, activity, guide=_guide(activity.speech, "happy", "👋", "speak"))


def answer_toddler(session_id: str, answer: str, recognized_speech: str = "") -> ToddlerResponse:
    session = mock_toddler_sessions.get(session_id)
    if not session:
        raise app_error("EXPIRED_TODDLER_SESSION", "Let us start this little lesson again.", 404)
    level = _get_level(session["module"], session["level"])
    if session["activity_index"] >= len(level.activities):
        return _response(session, level, None, guide=_guide("You did it! 🌟", "celebrate", "🌟", "complete_level"), level_completed=True)

    activity = level.activities[session["activity_index"]]
    heard = (recognized_speech or answer).strip()
    evaluation = evaluate_activity(activity, heard)
    if evaluation.result in {"correct", "close"}:
        child = _child(session["child_id"])
        child["stars"] += 1
        if activity.activity_id not in session["completed_activities"]:
            session["completed_activities"].append(activity.activity_id)
        if activity.concept not in session["learned_concepts"]:
            session["learned_concepts"].append(activity.concept)
        session["attempt_count"] = 0
        session["activity_index"] += 1
        if session["activity_index"] >= len(level.activities):
            return _complete_level(session, child, level, evaluation)
        next_activity = level.activities[session["activity_index"]]
        return _response(
            session,
            level,
            next_activity,
            evaluation=evaluation,
            guide=_guide("Yay! Great job! ⭐", "celebrate", "⭐", "next_activity"),
            stars_earned=1,
        )

    session["attempt_count"] += 1
    if session["attempt_count"] >= 4:
        session["attempt_count"] = 0
        session["activity_index"] = (session["activity_index"] + 1) % len(level.activities)
        next_activity = level.activities[session["activity_index"]]
        return _response(
            session,
            level,
            next_activity,
            evaluation=evaluation,
            guide=_guide("Let's try a different little question.", "encouraging", "😊", "next_activity"),
            question_changed=True,
        )
    retry_speech = f"Almost! 😊 Let's try {activity.concept} again."
    if session["attempt_count"] >= 2 and activity.answer:
        retry_speech = f"Let's find {activity.concept} together. 😊"
    return _response(
        session,
        level,
        activity,
        evaluation=evaluation,
        guide=_guide(retry_speech, "gentle_retry", "😊", "repeat", repeat=True, target=activity.answer),
    )


def evaluate_activity(activity: ToddlerActivity, heard: str) -> SpeechEvaluation:
    expected = activity.answer or activity.concept
    if activity.type == "introduce":
        return SpeechEvaluation(result="correct", confidence=1, expected=expected, heard=heard, retry=False)
    if not heard:
        return SpeechEvaluation(result="unclear", confidence=0, expected=expected, heard="", retry=True)

    accepted = {normalize_answer(item, activity.type) for item in [expected, activity.concept, *activity.accepted] if item}
    normalized_heard = normalize_answer(heard, activity.type)
    if heard in activity.choices and heard == expected:
        return SpeechEvaluation(result="correct", confidence=1, expected=expected, heard=heard, retry=False)
    if normalized_heard in accepted or heard in activity.accepted:
        return SpeechEvaluation(result="correct", confidence=0.92, expected=expected, heard=heard, retry=False)

    best_ratio = max([SequenceMatcher(None, normalized_heard, candidate).ratio() for candidate in accepted if candidate] or [0])
    if best_ratio >= 0.72:
        return SpeechEvaluation(result="close", confidence=round(best_ratio, 2), expected=expected, heard=heard, retry=False)
    return SpeechEvaluation(result="retry", confidence=round(best_ratio, 2), expected=expected, heard=heard, retry=True)


def _complete_level(session: dict, child: dict, level: ToddlerLevel, evaluation: SpeechEvaluation) -> ToddlerResponse:
    progress = _toddler_progress(child)
    if level.level not in progress["completed_stages"]:
        progress["completed_stages"].append(level.level)
        child["stars"] += level.star_reward
    next_level = level.level + 1
    next_unlocked = next_level <= len(TODDLER_CURRICULUM[level.module])
    if next_unlocked and next_level not in progress["unlocked_stages"]:
        progress["unlocked_stages"].append(next_level)
    progress["current_stage"] = next_level if next_unlocked else level.level
    progress["score"] = 100
    return _response(
        session,
        level,
        None,
        evaluation=evaluation,
        guide=_guide(f"Wow! You learned {' '.join(level.concepts)}! 🌟", "celebrate", "🌟", "complete_level"),
        stars_earned=1 + level.star_reward,
        level_completed=True,
        next_level_unlocked=next_unlocked,
    )


def _guide(speech: str, emotion: str, emoji: str, action: str, repeat: bool = False, target: str | None = None) -> ToddlerGuideResponse:
    safe_target = target if target in {None, "A", "B", "C", "D", "E", "F", "1", "2", "3", "🔴", "🟡", "🔵", "⭕", "⬜", "⭐"} else None
    return ToddlerGuideResponse(speech=speech, emotion=emotion, emoji=emoji, action=action, repeat=repeat, target=safe_target)


def _avatar(guide: ToddlerGuideResponse) -> AvatarPayload:
    state = {
        "happy": "happy",
        "encouraging": "encouraging",
        "thinking": "thinking",
        "celebrate": "celebrating",
        "gentle_retry": "encouraging",
    }[guide.emotion]
    effect = "star_burst" if guide.emotion == "celebrate" else "gentle_hint" if guide.emotion == "gentle_retry" else "sparkle"
    if effect == "sparkle":
        effect = "none"
    return AvatarPayload(state=state, message=guide.speech, speak=True, animationEffect=effect)


def _response(
    session: dict,
    level: ToddlerLevel,
    activity: ToddlerActivity | None,
    guide: ToddlerGuideResponse,
    evaluation: SpeechEvaluation | None = None,
    stars_earned: int = 0,
    level_completed: bool = False,
    next_level_unlocked: bool = False,
    question_changed: bool = False,
) -> ToddlerResponse:
    child = _child(session["child_id"])
    return ToddlerResponse(
        session_id=session["session_id"],
        child_id=session["child_id"],
        module=level.module,
        level=level.level,
        activity=activity,
        guide=guide,
        evaluation=evaluation,
        stars_earned=stars_earned,
        total_stars=child.get("stars", 0),
        attempt_count=session["attempt_count"],
        completed_activities=session["completed_activities"],
        level_completed=level_completed,
        next_level_unlocked=next_level_unlocked,
        question_changed=question_changed,
        learned_concepts=session["learned_concepts"],
        avatar=_avatar(guide),
    )
