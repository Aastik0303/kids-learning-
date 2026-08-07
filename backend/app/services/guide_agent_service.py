import json
import random
from datetime import datetime, timezone

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.schemas.avatar import AvatarPayload
from app.schemas.guide import GuideActionType, GuideRequest, GuideResponse, GuideUiAction
from app.services.errors import app_error
from app.services.safety_service import FALLBACK, safe_text


SYSTEM_PROMPT = """You are the Little Learning Guide, a friendly AI companion for children aged 3-6.
For Practice and Learning activities, the child primarily answers using voice.
Your job is to explain the current question in very simple language, speak one instruction
at a time, help the child understand what to answer, give a small hint after the first
incorrect answer, re-explain using a familiar example after another incorrect answer,
make later explanations easier and more visual, and keep responses short.
You do NOT evaluate answers, calculate scores, change progress, award stars, unlock levels,
or decide certificate eligibility. The backend gives you question context, the child's
normalized answer result, attempt number, age group, and visual context.
Never ask for sensitive personal information. Never shame the child. Never use: fail, bad,
poor, stupid, weak. Return structured JSON only."""

APPROVED_GUIDE_TARGETS = {
    "home-practice",
    "start-practice",
    "continue-adventure",
    "current-level",
    "current-map-level",
    "question-area",
    "counting-object-group",
    "answer-options",
    "voice-answer-area",
    "microphone-button",
    "home-button",
    "go-home",
    "rewards-button",
    "open-rewards",
    "ask-guide",
    "parent-profile",
    "open-certificate",
    "more-practice",
    "open-levels",
}

APPROVED_GUIDE_ACTIONS: set[GuideActionType] = {
    "none",
    "highlight",
    "scroll_to",
    "open_safe_route",
    "show_tooltip",
    "repeat_instruction",
    "show_hint",
    "wait_for_click",
}

STATIC_PRAISE = [
    "Great job!",
    "Amazing!",
    "Well done!",
    "You got it!",
    "Hooray! That is right.",
    "Wonderful! You are so clever.",
    "Brilliant! Keep going.",
    "Super! That was perfect.",
    "Yay! You nailed it.",
    "Awesome work!",
    "Excellent! You are getting better.",
    "Fantastic! I am so proud.",
]

HINT_RESPONSES_ATTEMPT_1 = [
    "Good try! Look closely and count slowly, then say your answer.",
    "Almost! Take another careful look.",
    "Not quite. Let us look at this together.",
    "So close! Think about it one more time.",
    "That was a brave try! Look carefully again.",
]

HINT_RESPONSES_ATTEMPT_2 = [
    "Almost there! Try a tiny example first, then say this one again.",
    "You are getting closer! Let us think about it differently.",
    "Let us slow down and look at each part one by one.",
    "Keep trying! You are doing great. Look at the hint.",
]

HINT_RESPONSES_ATTEMPT_3_PLUS = [
    "Let us make it easier. Touch each item as you count, then say the total.",
    "No worries! Let us practise this with an easier step.",
    "Take your time. I will help you through this one.",
    "Let us try a different way. Look at the picture carefully.",
]


def _pick_praise(session_id: str | None = None) -> str:
    """Pick a varied praise message. Uses session_id as seed for consistency within a session."""
    if session_id:
        rng = random.Random(f"praise:{session_id}:{datetime.now(timezone.utc).minute}")
        return rng.choice(STATIC_PRAISE)
    return random.choice(STATIC_PRAISE)


def _pick_hint(attempt: int, session_id: str | None = None) -> str:
    """Pick an attempt-aware hint message with variety."""
    if attempt <= 1:
        pool = HINT_RESPONSES_ATTEMPT_1
    elif attempt == 2:
        pool = HINT_RESPONSES_ATTEMPT_2
    else:
        pool = HINT_RESPONSES_ATTEMPT_3_PLUS
    if session_id:
        rng = random.Random(f"hint:{session_id}:{attempt}")
        return rng.choice(pool)
    return random.choice(pool)


def _time_greeting() -> str:
    """Return a time-of-day aware greeting prefix."""
    hour = datetime.now(timezone.utc).hour
    if 5 <= hour < 12:
        return "Good morning"
    elif 12 <= hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"


def _words(text: str, limit: int) -> str:
    parts = text.split()
    if len(parts) <= limit:
        return text
    return " ".join(parts[:limit]).rstrip(".,!") + "."


def _first_allowed_target(payload: GuideRequest, preferred: list[str]) -> str | None:
    supplied = [target for target in payload.available_targets if target in APPROVED_GUIDE_TARGETS]
    for target in preferred:
        if target in supplied:
            return target
    return supplied[0] if supplied else None


def _ui_action(payload: GuideRequest, action_type: GuideActionType, preferred_targets: list[str] | None = None) -> GuideUiAction:
    if action_type not in _approved_actions_from_request(payload):
        action_type = "none"
    if action_type == "none":
        return GuideUiAction(type="none", target=None)
    target = _first_allowed_target(payload, preferred_targets or [])
    if action_type in {"highlight", "scroll_to", "show_tooltip", "wait_for_click"} and not target:
        return GuideUiAction(type="none", target=None)
    return GuideUiAction(type=action_type, target=target)


def _approved_actions_from_request(payload: GuideRequest) -> set[GuideActionType]:
    requested = set(payload.available_actions)
    return requested & APPROVED_GUIDE_ACTIONS if requested else APPROVED_GUIDE_ACTIONS


def _avatar(message: str, state: str = "speaking", effect: str = "gentle_hint", speak: bool = True) -> AvatarPayload:
    return AvatarPayload(state=state, message=message, speak=speak, animationEffect=effect)


def validate_guide_request(payload: GuideRequest) -> None:
    unsafe_targets = [target for target in payload.available_targets if target not in APPROVED_GUIDE_TARGETS]
    if unsafe_targets:
        raise app_error("UNSAFE_GUIDE_TARGET", "Let us use a safe guide step.", 400)
    unsafe_actions = [action for action in payload.available_actions if action not in APPROVED_GUIDE_ACTIONS]
    if unsafe_actions:
        raise app_error("UNSAFE_GUIDE_ACTION", "Let us use a safe guide step.", 400)


def _fallback_guide(payload: GuideRequest) -> GuideResponse:
    validate_guide_request(payload)

    message = FALLBACK
    strategy = "help"
    action = GuideUiAction(type="none", target=None)
    next_event = "wait_for_child"
    state = "speaking"
    effect = "gentle_hint"
    session_id = payload.session_id

    # --- APP_OPENED / HOME_OPENED ---
    if payload.event in {"APP_OPENED", "HOME_OPENED"}:
        greeting = _time_greeting()
        level = payload.progress.current_level if payload.progress else None
        last = payload.progress.last_completed_level if payload.progress else None
        if last and level:
            message = f"{greeting}! Welcome back! Last time you finished {last}. Tap Continue Adventure for {level}."
        elif level:
            message = f"{greeting}! Tap Continue Adventure to start {level}."
        else:
            message = f"{greeting}! Tap Continue Adventure to begin."
        strategy = "welcome"
        action = _ui_action(payload, "highlight", ["continue-adventure", "current-level", "home-practice", "start-practice"])
        next_event = "button_clicked"
        state = "waving"
        effect = "sparkle"

    # --- ADVENTURE_OPENED ---
    elif payload.event == "ADVENTURE_OPENED":
        world = payload.progress.current_world if payload.progress else "your adventure"
        message = f"Welcome to {world}! Follow the path and tap the glowing level."
        strategy = "navigation"
        action = _ui_action(payload, "highlight", ["current-map-level", "current-level"])
        next_event = "button_clicked"
        state = "pointing"
        effect = "sparkle"

    # --- LEVEL_OPENED ---
    elif payload.event == "LEVEL_OPENED":
        level = payload.progress.current_level if payload.progress else "this level"
        message = f"Here is {level}. Tap to start when you are ready."
        strategy = "navigation"
        action = _ui_action(payload, "highlight", ["current-level", "current-map-level"])
        next_event = "button_clicked"
        state = "pointing"

    # --- PRACTICE_OPENED ---
    elif payload.event == "PRACTICE_OPENED":
        message = "Practice time! Pick a topic you want to work on."
        strategy = "navigation"
        action = _ui_action(payload, "highlight", ["start-practice", "home-practice"])
        next_event = "button_clicked"
        state = "speaking"
        effect = "bounce"

    # --- PRACTICE_STARTED / LEVEL_STARTED ---
    elif payload.event in {"PRACTICE_STARTED", "LEVEL_STARTED"}:
        prompt = payload.question.prompt if payload.question else None
        if prompt:
            message = f"Listen carefully. {prompt} Say your answer when you are ready."
        else:
            message = "Let us try one little question. Say your answer after I finish."
        strategy = "read_question"
        action = _ui_action(payload, "highlight", ["question-area", "voice-answer-area", "microphone-button"])
        next_event = "voice_answer_requested"
        state = "storytelling"
        effect = "story_transition"

    # --- QUESTION LOADED / REPEAT ---
    elif payload.event in {"PRACTICE_QUESTION_LOADED", "LEVEL_QUESTION_LOADED", "REPEAT_REQUESTED"}:
        prompt = payload.question.prompt if payload.question else "Look at the question."
        hint = payload.question.hint if payload.question and payload.question.hint else ""
        if payload.event == "REPEAT_REQUESTED" and hint:
            message = f"Let me say it again. {prompt} Remember: {hint}"
        else:
            message = f"Listen carefully. {prompt} Say your answer when you are ready."
        strategy = "read_question"
        action = _ui_action(payload, "highlight", ["question-area", "counting-object-group", "voice-answer-area", "microphone-button"])
        next_event = "voice_answer_requested"

    # --- INCORRECT ANSWER ---
    elif payload.event in {"PRACTICE_ANSWER_INCORRECT", "LEVEL_ANSWER_INCORRECT", "HINT_REQUESTED"}:
        attempt = payload.question.attempt if payload.question else 1
        question_hint = payload.question.hint if payload.question and payload.question.hint else ""

        if attempt <= 1:
            base = _pick_hint(1, session_id)
            message = f"{base} {question_hint}".strip() if question_hint else base
            strategy = "hint"
            action_type: GuideActionType = "show_hint"
            limit = 25
        elif attempt == 2:
            base = _pick_hint(2, session_id)
            message = f"{base} {question_hint}".strip() if question_hint else base
            strategy = "re_explain"
            action_type = "show_hint"
            limit = 35
        else:
            base = _pick_hint(3, session_id)
            if payload.progress and payload.progress.weak_skills:
                message = f"{base} Let us practise this skill a little more."
            else:
                message = f"{base} {question_hint}".strip() if question_hint else base
            strategy = "re_explain"
            action_type = "show_hint"
            limit = 35
        message = _words(message, limit)
        action = _ui_action(payload, action_type, ["counting-object-group", "question-area", "voice-answer-area", "microphone-button"])
        next_event = "voice_answer_requested"
        state = "encouraging"
        effect = "gentle_hint"

    # --- CORRECT ANSWER ---
    elif payload.event in {"PRACTICE_ANSWER_CORRECT", "LEVEL_ANSWER_CORRECT"}:
        message = _pick_praise(session_id)
        strategy = "none"
        action = GuideUiAction(type="none", target=None)
        next_event = "next_question_loaded"
        state = "celebrating"
        effect = "star_burst"

    # --- COMPLETION EVENTS ---
    elif payload.event in {"PRACTICE_COMPLETED", "LEVEL_COMPLETED", "WORLD_UNLOCKED", "CERTIFICATE_UNLOCKED", "WORLD_COMPLETED"}:
        if payload.event == "PRACTICE_COMPLETED":
            message = "Practice complete! You worked so hard. Tap Levels or try more practice."
            action = _ui_action(payload, "highlight", ["open-levels", "more-practice", "continue-adventure"])
        elif payload.event == "CERTIFICATE_UNLOCKED":
            message = "Your certificate is ready! You are a Little Learning Explorer. Tap to open it."
            action = _ui_action(payload, "highlight", ["open-certificate"])
            effect = "rainbow"
        elif payload.event == "WORLD_COMPLETED":
            world = payload.progress.current_world if payload.progress else "this world"
            message = f"You completed {world}! A new world is waiting for you."
            action = _ui_action(payload, "highlight", ["continue-adventure", "open-levels"])
            effect = "confetti"
        elif payload.event == "WORLD_UNLOCKED":
            message = "A new world just opened! Tap Continue Adventure to explore."
            action = _ui_action(payload, "highlight", ["continue-adventure", "current-level", "open-levels"])
            effect = "confetti"
        else:
            message = "Wonderful work! Tap Continue Adventure for the next level."
            action = _ui_action(payload, "highlight", ["continue-adventure", "current-level", "open-levels"])
        strategy = "celebrate"
        next_event = "button_clicked"
        state = "celebrating"
        if effect == "gentle_hint":
            effect = "confetti"

    # --- REWARDS_OPENED ---
    elif payload.event == "REWARDS_OPENED":
        stars = payload.progress.session_stars if payload.progress else 0
        if stars > 0:
            message = f"Look at your rewards! You have earned {stars} stars so far."
        else:
            message = "This is your rewards collection. Keep learning to earn stars and badges."
        strategy = "navigation"
        action = _ui_action(payload, "highlight", ["open-rewards", "rewards-button"])
        next_event = "button_clicked"
        state = "happy"
        effect = "sparkle"

    # --- GUIDE_HELP_REQUESTED ---
    elif payload.event == "GUIDE_HELP_REQUESTED":
        feature = payload.feature.replace("_", " ")
        message = f"I am your Little Learning Guide. Tap the glowing {feature} button."
        strategy = "navigation"
        action = _ui_action(payload, "highlight", ["continue-adventure", "home-practice", "start-practice", "open-rewards", "ask-guide"])
        next_event = "button_clicked"
        state = "pointing"
        effect = "pulse"

    message = safe_text(message)
    return GuideResponse(
        message=message,
        strategy=strategy,
        avatar=_avatar(message, state=state, effect=effect, speak=True),
        ui_action=action,
        next_expected_event=next_event,
    )


def _payload_for_model(payload: GuideRequest) -> dict:
    return payload.model_dump(exclude_none=True)


def _model_instruction(payload: GuideRequest) -> str:
    allowed_actions = sorted(_approved_actions_from_request(payload))
    allowed_targets = [target for target in payload.available_targets if target in APPROVED_GUIDE_TARGETS]
    return (
        "Create one Little Learning Guide response for this event. "
        "Return exactly one JSON object with keys: message, strategy, avatar, ui_action, next_expected_event. "
        f"Allowed ui_action.type values: {allowed_actions}. "
        f"Allowed ui_action.target values: {allowed_targets}; use null if no target is needed. "
        "avatar must include state, message, speak, animationEffect. "
        "Do not decide if the answer is correct. Do not change score, stars, rewards, progress, unlocking, or certificates. "
        "For voice practice, explain before listening, never tell the app to listen while avatar is speaking, "
        "and use the microphone or voice-answer targets when asking for an answer. "
        "Use only the supplied question and concept. Keep child-facing text short (under 25 words). "
        "When giving a hint after a wrong answer, incorporate the question's hint field if present. "
        "Always use warm, encouraging language. Never shame the child."
    )


def _validate_model_response(payload: GuideRequest, raw_content: str) -> GuideResponse:
    try:
        decoded = json.loads(raw_content)
    except json.JSONDecodeError:
        return _fallback_guide(payload)

    try:
        response = GuideResponse.model_validate(decoded)
    except ValidationError:
        return _fallback_guide(payload)

    if response.ui_action.type not in _approved_actions_from_request(payload):
        return _fallback_guide(payload)
    if response.ui_action.target and response.ui_action.target not in payload.available_targets:
        return _fallback_guide(payload)
    if response.ui_action.target and response.ui_action.target not in APPROVED_GUIDE_TARGETS:
        return _fallback_guide(payload)

    message = safe_text(response.message)
    return response.model_copy(
        update={
            "message": message,
            "avatar": response.avatar.model_copy(update={"message": safe_text(response.avatar.message)}),
        }
    )


def _groq_guide(payload: GuideRequest) -> GuideResponse:
    settings = get_settings()
    if not settings.groq_api_key:
        return _fallback_guide(payload)

    body = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _model_instruction(payload)},
            {"role": "user", "content": json.dumps(_payload_for_model(payload), ensure_ascii=True)},
        ],
        "temperature": 0.4,
        "max_completion_tokens": 300,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    try:
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=body,
            timeout=2.5,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return _fallback_guide(payload)

    return _validate_model_response(payload, content)


def guide(payload: GuideRequest) -> GuideResponse:
    validate_guide_request(payload)
    if get_settings().llm_provider.lower() == "groq":
        return _groq_guide(payload)
    return _fallback_guide(payload)
