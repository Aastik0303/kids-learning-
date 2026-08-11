import json
import random
from datetime import datetime, timedelta, timezone

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.schemas.avatar import AvatarPayload
from app.schemas.guide import GuideActionType, GuideRequest, GuideResponse, GuideUiAction, GuideVisualAction, GuideVisualActionType
from app.services.answer_resolution_service import AnswerResolutionContext, resolve_answer
from app.services.errors import app_error
from app.services.safety_service import FALLBACK, safe_text


SYSTEM_PROMPT = """You are the Little Learning Guide, a friendly AI companion for children aged 3-6.
Your job is to answer age-appropriate learning questions and help the child understand the
current screen or activity. For GUIDE_HELP_REQUESTED, answer the child's latest question
directly and use the recent conversation when it helps. If a question is unrelated or unsafe,
gently guide the child back to numbers, letters, colours, shapes, stories, or the learning app.
You receive route, screen, event, feature, age group, allowed UI actions/targets, current
question, learning objective, visual items, child answer/result, attempts, recent answers,
and compact progress context.
You do NOT decide correctness, score, stars, rewards, unlocking, progress, or certificates.
Teaching rules: do not simply repeat the question; identify what the child needs to
understand; refer to visible objects; give one small explanation step; then ask for the
answer; use 1-2 short sentences; use nursery words; first wrong attempt gives a small hint;
second wrong attempt uses another familiar example; third or later makes it easier and more
visual; address repeated mistake patterns; never shame; never ask sensitive personal info;
use only allowed UI and visual actions. If clear speech does not fit the current question,
say so gently and bring the child back to that question; never claim you could not hear it.
Return structured JSON only."""

TODDLER_SYSTEM_PROMPT = """For learning_mode toddler, you are a warm, playful nursery teacher helping a child younger than 3.
Use maximum 1-2 very short sentences, simple vocabulary, one instruction at a time, and happy emojis.
Never ask for personal information. Never shame. Never say wrong. Prefer: Almost! Let's try again 😊.
Keep the child focused on the current deterministic toddler lesson."""

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
    "toddler-home",
    "toddler-module-alphabets",
    "toddler-module-numbers",
    "toddler-module-colours",
    "toddler-module-shapes",
    "toddler-activity",
    "toddler-microphone",
    "toddler-choices",
    "toddler-keep-learning",
    "toddler-practice",
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

APPROVED_VISUAL_ACTIONS: set[GuideVisualActionType] = {
    "none",
    "pulse",
    "highlight",
    "highlight_sequence",
    "dim_others",
    "group_objects",
    "trace_shape",
    "show_example",
}

STATIC_PRAISE = [
    "Great job!",
    "Nice work!",
    "Well done!",
    "You got it!",
    "Hooray! That is right.",
    "Great listening!",
    "Nice counting!",
    "Great effort!",
    "Let's try the next one!",
    "Super work!",
    "Good thinking!",
]

HINT_RESPONSES_ATTEMPT_1 = [
    "Good try! Look closely and count slowly, then say your answer.",
    "Almost! Take another careful look.",
    "Almost. Let us look at this together.",
    "So close! Think about it one more time.",
    "Good try. Look carefully again.",
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


def _is_contextual_mismatch(payload: GuideRequest) -> bool:
    question = payload.question
    spoken = payload.feature.lower().strip()
    if not question or any(phrase in spoken for phrase in ("help", "understand", "explain", "what", "why", "how", "repeat", "confused")):
        return False
    resolution = resolve_answer(
        AnswerResolutionContext(
            transcript=payload.feature,
            confidence=0.9,
            answer_type=question.answer_type or "",
            correct_answer=question.correct_answer,
            accepted_answers=question.accepted_answers,
            options=question.options,
        )
    )
    return resolution.input_kind == "unresolved"


def _contextual_mismatch_message(payload: GuideRequest) -> str:
    question = payload.question
    if not question:
        return FALLBACK
    teaching_hint = question.hint or question.learning_objective or question.prompt
    return _words(f"I heard you, but that does not answer this question yet. {teaching_hint}", 22)


def _help_message(payload: GuideRequest) -> str:
    question = payload.feature.lower().strip()
    progress = payload.progress

    if any(word in question.split() for word in {"hi", "hello", "hey"}):
        return "Hello! What would you like to learn today?"
    if "practice" in question:
        return "Open Practice, then choose Numbers, Alphabets, Colours, Shapes, or Mixed Practice."
    if any(word in question for word in {"level", "path", "stage"}):
        return "Open Adventure and tap the bright unlocked level on your learning path."
    if "star" in question or "reward" in question:
        stars = progress.session_stars if progress else 0
        return f"You have {stars} stars. Open Rewards to see your badges and prizes."
    if "certificate" in question:
        return "Your certificate unlocks after you complete the Mixed Final Path."
    if "circle" in question:
        return "A circle is round all the way around and has no corners."
    if "square" in question:
        return "A square has four equal sides and four corners."
    if "triangle" in question:
        return "A triangle has three sides and three corners."
    if "alphabet" in question or "letter" in question:
        return "Letters make words. Ask me about one letter, like: What sound does A make?"
    if "number" in question or "count" in question:
        return "I can help you count. Tell me which objects or numbers you want to count."
    if "colour" in question or "color" in question:
        return "I can help with colours. Ask me about a colour you see."
    if "parent" in question or "login" in question:
        return "Tap Parent Login at the top of the screen to open the parent area."
    if _is_contextual_mismatch(payload):
        return _contextual_mismatch_message(payload)
    if payload.question:
        teaching_hint = payload.question.hint or payload.question.learning_objective
        asks_for_help = any(
            phrase in question
            for phrase in ("help", "understand", "explain", "what", "why", "how", "repeat", "confused")
        )
        if teaching_hint:
            prefix = "No problem. Let's try together." if asks_for_help else "I heard you, but that does not answer this question yet."
            return _words(f"{prefix} {teaching_hint}", 22)
        prefix = "No problem. Let's look together." if asks_for_help else "That does not fit this question yet. Let's try this:"
        return _words(f"{prefix} {payload.question.prompt}", 22)
    return FALLBACK


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


def _visual_action(payload: GuideRequest, action_type: GuideVisualActionType, targets: list[str] | None = None) -> GuideVisualAction:
    if action_type not in APPROVED_VISUAL_ACTIONS:
        return GuideVisualAction()
    allowed = set(payload.allowed_visual_targets)
    safe_targets = [target for target in (targets or payload.allowed_visual_targets) if target in allowed]
    if action_type == "none" or not safe_targets:
        return GuideVisualAction()
    return GuideVisualAction(type=action_type, targets=safe_targets)


def _visual_targets(payload: GuideRequest) -> list[str]:
    return [target for target in payload.allowed_visual_targets if target.startswith("visual-item-")]


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
    unsafe_visual_targets = [target for target in payload.allowed_visual_targets if not target.startswith(("visual-item-", "visual-example-"))]
    if unsafe_visual_targets:
        raise app_error("UNSAFE_VISUAL_TARGET", "Let us use a safe visual step.", 400)


def _is_counting_question(payload: GuideRequest) -> bool:
    if not payload.question:
        return False
    answer_type = (payload.question.answer_type or payload.question.topic or "").lower()
    return answer_type in {"count_objects", "select_number"} or "number" in answer_type or "count" in payload.question.prompt.lower()


def _question_teaching_message(payload: GuideRequest) -> tuple[str, GuideVisualAction, str]:
    question = payload.question
    if not question:
        return "Look at the screen. Try one small answer.", GuideVisualAction(), "read_question"

    answer_type = (question.answer_type or question.topic or "").lower()
    visual_items = question.visual_items
    visual_targets = _visual_targets(payload)
    attempt = question.attempt

    if _is_counting_question(payload):
        item_name = visual_items[0] if visual_items and visual_items[0].isascii() else "item"
        if attempt >= 1 and visual_items:
            count_words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
            count_sequence = ", ".join(count_words[index] if index < len(count_words) else str(index) for index in range(1, len(visual_items) + 1))
            total = count_words[len(visual_items)] if len(visual_items) < len(count_words) else str(len(visual_items))
            return (
                f"Let's count together: {count_sequence}. There are {total}. Watch each {item_name} light up.",
                _visual_action(payload, "show_example" if attempt >= 3 else "highlight_sequence", visual_targets),
                "hint" if attempt == 1 else "re_explain",
            )
        return (
            f"Look at the {item_name}s. Count each one only once. How many do you see?",
            _visual_action(payload, "highlight_sequence" if len(visual_targets) > 1 else "pulse", visual_targets),
            "visual_explanation",
        )

    if "colour" in answer_type or "color" in answer_type:
        return (
            "Look at the visible colour. Match it with the same colour answer.",
            _visual_action(payload, "highlight", visual_targets),
            "visual_explanation" if attempt == 0 else "hint",
        )

    if "shape" in answer_type:
        return (
            "Look at the shape. Check if it is round or has corners.",
            _visual_action(payload, "trace_shape", visual_targets[:1]),
            "visual_explanation" if attempt == 0 else "hint",
        )

    if "letter" in answer_type or "alphabet" in answer_type:
        return (
            f"Look at the letter. Listen to its name, then choose it.",
            _visual_action(payload, "pulse", visual_targets[:1]),
            "visual_explanation" if attempt == 0 else "hint",
        )

    return (
        f"Look at what is shown. {question.hint or question.prompt}",
        _visual_action(payload, "highlight", visual_targets),
        "visual_explanation" if attempt == 0 else "hint",
    )


def _fallback_guide(payload: GuideRequest) -> GuideResponse:
    validate_guide_request(payload)

    if payload.learning_mode == "toddler" or (payload.toddler and payload.toddler.learning_mode == "toddler"):
        return _toddler_fallback_guide(payload)

    message = FALLBACK
    strategy = "help"
    action = GuideUiAction(type="none", target=None)
    next_event = "wait_for_child"
    state = "speaking"
    effect = "gentle_hint"
    session_id = payload.session_id
    visual_action = GuideVisualAction()

    # --- APP_OPENED / HOME_OPENED ---
    if payload.event in {"APP_OPENED", "HOME_OPENED"}:
        greeting = _time_greeting()
        level = payload.progress.current_level if payload.progress else None
        last = payload.progress.last_completed_level if payload.progress else None
        objective = payload.progress.last_completed_objective if payload.progress else None
        completed_at = payload.progress.last_completed_at if payload.progress else None
        if last and level:
            studied = objective or last
            when = "Last time"
            if completed_at and completed_at.date() == (datetime.now(timezone.utc) - timedelta(days=1)).date():
                when = "Yesterday"
            message = f"{greeting}! {when} you studied {studied} in {last}. Today, tap Continue Adventure for {level}."
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
        state = "speaking"
        effect = "sparkle"

    # --- LEVEL_OPENED ---
    elif payload.event == "LEVEL_OPENED":
        level = payload.progress.current_level if payload.progress else "this level"
        message = f"Here is {level}. Tap to start when you are ready."
        strategy = "navigation"
        action = _ui_action(payload, "highlight", ["current-level", "current-map-level"])
        next_event = "button_clicked"
        state = "speaking"

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
        message, visual_action, strategy = _question_teaching_message(payload)
        action = _ui_action(payload, "highlight", ["question-area", "voice-answer-area", "microphone-button"])
        next_event = "voice_answer_requested"
        state = "storytelling"
        effect = "story_transition"

    # --- QUESTION LOADED / REPEAT ---
    elif payload.event in {"PRACTICE_QUESTION_LOADED", "LEVEL_QUESTION_LOADED", "REPEAT_REQUESTED"}:
        message, visual_action, strategy = _question_teaching_message(payload)
        action = _ui_action(payload, "highlight", ["question-area", "counting-object-group", "voice-answer-area", "microphone-button"])
        next_event = "voice_answer_requested"

    # --- INCORRECT ANSWER ---
    elif payload.event in {"PRACTICE_ANSWER_INCORRECT", "LEVEL_ANSWER_INCORRECT", "HINT_REQUESTED"}:
        message, visual_action, strategy = _question_teaching_message(payload)
        message = _words(message, 22)
        action_type: GuideActionType = "show_hint"
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
        message = _help_message(payload)
        strategy = "help"
        if payload.question:
            teaching_payload = payload.model_copy(
                update={"question": payload.question.model_copy(update={"attempt": max(1, payload.question.attempt)})}
            )
            teaching_message, visual_action, strategy = _question_teaching_message(teaching_payload)
            if _is_counting_question(teaching_payload):
                message = teaching_message
            strategy = "help"
            action = _ui_action(
                payload,
                "highlight",
                ["counting-object-group", "question-area", "toddler-activity", "voice-answer-area", "toddler-choices"],
            )
        else:
            action = GuideUiAction(type="none", target=None)
        next_event = "wait_for_child"
        state = "speaking"
        effect = "pulse"

    message = safe_text(message)
    return GuideResponse(
        message=message,
        strategy=strategy,
        avatar=_avatar(message, state=state, effect=effect, speak=True),
        ui_action=action,
        visual_action=visual_action,
        next_expected_event=next_event,
    )


def _toddler_fallback_guide(payload: GuideRequest) -> GuideResponse:
    toddler = payload.toddler
    concept = toddler.concept if toddler and toddler.concept else payload.question.correct_answer if payload.question else ""
    result = toddler.recent_result if toddler else None
    target_preferences = ["toddler-activity", "toddler-microphone", "toddler-choices", "toddler-keep-learning", "toddler-practice"]
    state = "speaking"
    effect = "none"
    strategy = "read_question"
    next_event = "wait_for_child"
    visual_action = GuideVisualAction()

    if payload.event in {"APP_OPENED", "HOME_OPENED"}:
        message = "Hi little explorer! 👋 Let's learn."
        state = "waving"
        strategy = "welcome"
        target_preferences = ["toddler-module-alphabets", "toddler-home"]
    elif payload.event == "GUIDE_HELP_REQUESTED":
        teaching_payload = payload.model_copy(
            update={"question": payload.question.model_copy(update={"attempt": max(1, payload.question.attempt)})}
        ) if payload.question else payload
        teaching_message, visual_action, strategy = _question_teaching_message(teaching_payload)
        message = teaching_message if _is_counting_question(teaching_payload) else _help_message(payload)
        state = "speaking"
        strategy = "help"
        target_preferences = ["toddler-activity", "toddler-microphone", "toddler-choices"]
    elif result in {"correct", "close"} or payload.event in {"LEVEL_ANSWER_CORRECT", "PRACTICE_ANSWER_CORRECT"}:
        message = f"Yay! That's {concept}! ⭐" if concept else "Yay! Great job! ⭐"
        state = "celebrating"
        effect = "star_burst"
        strategy = "celebrate"
        next_event = "next_activity"
    elif result in {"retry", "unclear"} or payload.event in {"LEVEL_ANSWER_INCORRECT", "PRACTICE_ANSWER_INCORRECT", "HINT_REQUESTED"}:
        if payload.question:
            message, visual_action, strategy = _question_teaching_message(payload)
        else:
            message = f"Almost! 😊 Let's try {concept} again." if concept else "Almost! 😊 Let's try again."
            strategy = "hint"
        state = "encouraging"
        effect = "gentle_hint"
        target_preferences = ["toddler-microphone", "toddler-choices", "toddler-activity"]
    elif payload.event in {"LEVEL_COMPLETED", "PRACTICE_COMPLETED"}:
        message = "Wow! You did it! 🌟"
        state = "celebrating"
        effect = "confetti"
        strategy = "celebrate"
        target_preferences = ["toddler-keep-learning", "toddler-practice"]
    elif payload.question:
        message = _words(payload.question.learning_objective or payload.question.prompt, 10)
    else:
        message = "Look, listen, then try. 😊"

    message = safe_text(_words(message, 14))
    return GuideResponse(
        message=message,
        strategy=strategy,
        avatar=_avatar(message, state=state, effect=effect, speak=True),
        ui_action=_ui_action(payload, "highlight", target_preferences),
        visual_action=visual_action,
        next_expected_event=next_event,
    )


def _payload_for_model(payload: GuideRequest) -> dict:
    return payload.model_dump(mode="json", exclude_none=True)


def _model_instruction(payload: GuideRequest) -> str:
    allowed_actions = sorted(_approved_actions_from_request(payload))
    allowed_targets = [target for target in payload.available_targets if target in APPROVED_GUIDE_TARGETS]
    allowed_visual_targets = [target for target in payload.allowed_visual_targets if target.startswith(("visual-item-", "visual-example-"))]
    return (
        "Create one Little Learning Guide response for this event. "
        "Return exactly one JSON object with keys: message, strategy, avatar, ui_action, visual_action, next_expected_event. "
        f"Allowed ui_action.type values: {allowed_actions}. "
        f"Allowed ui_action.target values: {allowed_targets}; use null if no target is needed. "
        f"Allowed visual_action.type values: {sorted(APPROVED_VISUAL_ACTIONS)}. "
        f"Allowed visual_action.targets values: {allowed_visual_targets}. "
        "avatar must include state, message, speak, animationEffect. "
        "Do not decide if the answer is correct. Do not change score, stars, rewards, progress, unlocking, or certificates. "
        "For voice practice, explain before listening, never tell the app to listen while avatar is speaking, "
        "and use the microphone or voice-answer targets when asking for an answer. "
        "Use only the supplied question and concept. Keep child-facing text short (under 25 words). "
        "When giving a hint after a wrong answer, incorporate the question's hint field if present. "
        "For GUIDE_HELP_REQUESTED, feature is the child's latest question. Answer it directly, "
        "using conversation and the current question for context. If feature is unrelated or nonsensical, acknowledge "
        "that it does not answer the current question and give one relevant hint. Never call clear speech unclear. "
        "Do not tell the child to tap a button unless they asked how to navigate. "
        "Always use warm, encouraging language. Never shame the child."
    )


def _validate_model_response(payload: GuideRequest, raw_content: str) -> GuideResponse:
    try:
        decoded = json.loads(raw_content)
    except json.JSONDecodeError:
        return _fallback_guide(payload)

    if payload.event == "GUIDE_HELP_REQUESTED" and isinstance(decoded, dict):
        raw_message = decoded.get("message")
        if isinstance(raw_message, str) and raw_message.strip():
            message = _contextual_mismatch_message(payload) if _is_contextual_mismatch(payload) else raw_message.strip()
            message = safe_text(_words(message, 25))
            teaching_payload = payload.model_copy(
                update={"question": payload.question.model_copy(update={"attempt": max(1, payload.question.attempt)})}
            ) if payload.question else payload
            teaching_message, visual_action, _ = _question_teaching_message(teaching_payload)
            if payload.question and _is_counting_question(teaching_payload) and not _is_contextual_mismatch(payload):
                message = safe_text(_words(teaching_message, 25))
            target_preferences = ["toddler-activity", "toddler-choices"] if payload.learning_mode == "toddler" else ["counting-object-group", "question-area"]
            return GuideResponse(
                message=message,
                strategy="help",
                avatar=_avatar(message, state="speaking", effect="pulse", speak=True),
                ui_action=_ui_action(payload, "highlight", target_preferences),
                visual_action=visual_action,
                next_expected_event="wait_for_child",
            )

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
    if response.visual_action.type not in APPROVED_VISUAL_ACTIONS:
        return _fallback_guide(payload)
    allowed_visual_targets = set(payload.allowed_visual_targets)
    if any(target not in allowed_visual_targets for target in response.visual_action.targets):
        return _fallback_guide(payload)

    teaching_event = payload.event in {
        "PRACTICE_ANSWER_INCORRECT",
        "LEVEL_ANSWER_INCORRECT",
        "HINT_REQUESTED",
        "GUIDE_HELP_REQUESTED",
    }
    if teaching_event and payload.question and payload.allowed_visual_targets:
        required_message, required_visual_action, _ = _question_teaching_message(payload)
        if response.visual_action.type == "none" or not response.visual_action.targets:
            response = response.model_copy(update={"visual_action": required_visual_action})
        if payload.event != "GUIDE_HELP_REQUESTED":
            response = response.model_copy(
                update={
                    "message": safe_text(_words(required_message, 25)),
                    "avatar": response.avatar.model_copy(update={"message": safe_text(_words(required_message, 25))}),
                }
            )

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
            {"role": "system", "content": TODDLER_SYSTEM_PROMPT if payload.learning_mode == "toddler" else ""},
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
            timeout=6.0,
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
