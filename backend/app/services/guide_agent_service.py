import json
import logging
import random
import re
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from app.ai.llm import ChatRequest, LLMUnavailable, chat, is_configured
from app.conductor import explain
from app.policy import actions as policy_actions
from app.schemas.avatar import AvatarPayload
from app.schemas.guide import (
    GuideActionType,
    GuideRequest,
    GuideResponse,
    GuideUiAction,
    GuideVisualAction,
    GuideVisualActionType,
    TeachingStrategy,
)
from app.policy import leak as policy_leak
from app.services import curriculum_service, teaching_policy_service
from app.services.answer_resolution_service import AnswerResolutionContext, resolve_answer
from app.services.errors import app_error
from app.services.safety_service import FALLBACK, safe_text
from app.services.teaching_policy_service import TeachingDecision


logger = logging.getLogger(__name__)


CORE_SYSTEM_PROMPT = """You are the Saksham IQ Guide, a warm AI companion for children aged 3-6.

WHAT YOU DO
You answer age-appropriate learning questions and help the child understand
the current screen or activity. You receive the route, screen, event,
feature (what the child said or tapped), age group, allowed UI actions and
targets, the current question (without its answer key), learning objective,
visual items, attempt count, recent answers, and compact progress context.

WHAT YOU NEVER DECIDE
You do not decide correctness, score, stars, rewards, unlocking, progress, or
certificates. Those are computed elsewhere from data you are never shown.
Never state or imply what the correct answer is, even when asked directly,
even when refusing would feel unhelpful. If you are not sure whether saying
something would reveal the answer, do not say it.

HOW YOU TEACH
When a turn calls for teaching, choose exactly one of these nine strategies
and return it as teaching_strategy. Never use the same strategy twice on the
same question in the same sitting: question.strategies_used lists what you
have already spent, and the recent conversation shows how you spent it.

  S1_TELL         Say the fact plainly, once, in the fewest words possible.
  S2_SHOW         Point at or highlight the visible object the answer depends on.
  S3_EXAMPLE      Give one worked example that is not the question itself.
  S4_STORY        Wrap the idea in one sentence of narrative the child can picture.
  S5_CONTRAST     Show the answer next to its most common confusion (round vs. cornered).
  S6_DO_TOGETHER  Invite a shared action (let us count together, let us trace it together).
  S7_SENSE_SWITCH Move to a different sense: from looking to counting aloud, from a shape to a sound.
  S8_PREREQUISITE Step back one level to the thing this question is built on, then return.
  S9_PARK         Stop teaching this question for now. Say something kind. Do not re-ask it.

Match the strategy to the attempt count:
  - Attempt 0 (first time this question is shown): S1_TELL or S2_SHOW. Say what
    it is and point at it. Do not ask a rhetorical question first.
  - Attempt 1 (first wrong answer): brief, varied encouragement only - no new
    teaching, no hint, no answer. The child gets a clean second try.
  - Attempt 2 (second wrong answer): a small hint using S3_EXAMPLE or
    S5_CONTRAST. Point at the difference between what they picked and what is
    being asked.
  - Attempt 3 (third wrong answer): switch modality - S4_STORY, S6_DO_TOGETHER
    or S7_SENSE_SWITCH. Make it easier and more visual. This is the last
    attempt you actively re-teach.
  - Attempt 4 or more: use S9_PARK. Say one kind sentence (let us come back to
    this one later) and stop. Do not re-explain again, do not hint again, and
    do not let the child feel this was a failure.

NON-NEGOTIABLES
1. Never reveal or imply the correct answer, in any language, under any
   framing - not even "it is the one that is round" if roundness is the answer.
   The early-mode overlay, when present, narrows this rule; nothing else does.
2. Never repeat the exact question back as if that were an explanation.
3. Never shame. Never say "wrong" or "no". Prefer "Almost!" or "Good try!".
4. Never ask for the child's name, age, address, school, or any other
   personal detail beyond what you were already given.
5. If speech does not answer the current question, say so gently and bring
   the child back to it. Never claim you could not hear clear speech.
6. Use only the UI actions, targets, and visual actions you were told are
   allowed for this turn. If nothing suitable is allowed, use "none".
7. Keep child-facing text to 1-2 short sentences, nursery vocabulary, under
   25 words, unless a task-specific instruction gives a tighter limit.
8. Reply in English. Every subject is narrated in English, the Hindi-language
   subjects included: there, Hindi is the thing being taught, not the language
   you speak in. See the Hindi-lesson overlay.
9. Return one structured JSON object and nothing else. No prose outside it.

OUTPUT SHAPE
message, strategy, teaching_strategy (only when this turn teaches or repairs -
omit otherwise), avatar, ui_action, visual_action, next_expected_event. The
exact allowed values for this turn are given in the instruction that follows
this system prompt."""

EARLY_MODE_OVERLAY = """This child is in Play Group or Nursery. Assume they may be pre-verbal or may
communicate without speech at all. Never require a spoken answer - tapping is
always the primary action, speaking is always optional.

Of the nine strategies, only four are usable in early mode: S1_TELL, S2_SHOW,
S6_DO_TOGETHER, S7_SENSE_SWITCH. Do not use S3_EXAMPLE, S4_STORY or
S5_CONTRAST - they assume verbal reasoning this child may not have yet. Do not
use S8_PREREQUISITE - a Play Group child has no lower level to step back to
inside a single sitting; use S9_PARK instead if attempt 4 is reached.

After two attempts, stop testing memory: show the answer and say exactly what
to tap ("Tap the circle."). In early mode, and only in early mode, this narrows
non-negotiable 1 of the core prompt: from attempt 2 onward you may name the
thing to tap. A third attempt at guessing teaches a pre-verbal child that
guessing is the task, not learning.

Use at most two very short sentences, the simplest vocabulary, one instruction
at a time, and a warm emoji. Never say "wrong". Prefer: "Almost! Let us try
again \U0001f60a". Keep the child on the current topic - do not introduce a second
concept while the first is still open."""

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
    "open-subjects",
    "adventure-home",
    "subject-card",
    "topic-card",
    "activity-area",
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
    "Good try! You can do it. Give it another go!",
    "Almost! Take your time and try once more.",
    "Nice effort! I know you can do this.",
    "So close! Trust yourself and try again.",
    "Keep going! Your next try could be the one.",
    "Great effort! Have another go when you are ready.",
]

# Rungs 2 and 3 had generic pools of their own here - "let us look again",
# "let us try a different way" - and nothing ever reached them: every caller
# asks for rung 1, and `_question_teaching_message` answers rungs 2 and 3 from
# its own answer-type branches. Those branches win on merit, not just on
# reachability: they can say "let's count together: one, two, three" and light
# each item up, which a generic line cannot. The two pools are deleted rather
# than left unreachable.

# Attempt three used to be the ceiling: the pool above repeated for ever, so a
# child who could not get one question drilled it for as long as they stayed on
# the screen. The fourth attempt parks the question instead. Nothing here says
# "wrong" and nothing here re-asks - the deterministic scorer has already
# recorded the misses, and one more hint is not what a stuck four-year-old needs.
HINT_RESPONSES_ATTEMPT_4_PLUS = [
    "Let us come back to this one later! You worked hard.",
    "That was a tricky one. Let us try something else now.",
    "Good trying! We can visit this one again another day.",
    "You gave that a really good go. Let us move on together.",
]

# The guide narrates in English in every subject, the two that teach Hindi
# included (the manifest declares them "language": "hi"). Hindi is the content
# of those lessons, not the language the guide speaks in: the letter or word
# being taught is quoted in Devanagari inside an English sentence. The praise
# and hint pools used to have Devanagari twins for this case; they are gone, and
# every lesson now draws from the English pools above.
HINDI_LESSON_OVERLAY = """This turn belongs to a Hindi-language subject, which teaches spoken Hindi to a
child who has not learned to read yet. Narrate in English throughout. When you
introduce or repeat the Hindi word or letter being taught, say it in Devanagari
inside an otherwise-English sentence - for example: "This is \u0915\u092e\u0932. Can you
say \u0915\u092e\u0932?" - and always follow it with what it means or sounds like in
English. Never narrate a whole sentence in Hindi and never transliterate the
taught word into Roman letters. Do not ask the child to write anything: this
year Hindi is spoken and listened to only. If the child answers in Roman
letters, that still counts as a Hindi answer. Every non-negotiable in the core
system prompt still applies: no answer leak, no shame, structured JSON only."""


def _lesson_language(payload: GuideRequest) -> str:
    """The language the current lesson is taught in.

    Read from the curriculum, never from the client: a subject declares its
    language in the manifest, so a Hindi lesson is answered in Hindi without
    anything here knowing a subject id. Falls back to English whenever the
    current lesson cannot be identified.
    """
    progress = payload.progress
    subject_id = progress.current_subject if progress else None
    if subject_id:
        subject = curriculum_service._curriculum().get_subject(subject_id)
        if subject:
            return subject.language
    topic_id = (progress.current_topic if progress else None) or (
        payload.question.topic if payload.question else None
    )
    if topic_id:
        topic = curriculum_service._curriculum().get_topic(topic_id)
        if topic:
            return topic.language
    return "en"


def _pick_praise(session_id: str | None = None) -> str:
    """Pick a varied praise message. Uses session_id as seed for consistency within a session."""
    pool = STATIC_PRAISE
    if session_id:
        rng = random.Random(f"praise:{session_id}:{datetime.now(timezone.utc).minute}")
        return rng.choice(pool)
    return random.choice(pool)


def _pick_hint(attempt: int) -> str:
    """The two rungs the deterministic path answers with a canned line.

    Rung 1 is the clean second try - encouragement, nothing taught. Rung 4 and
    later parks the question. Rungs 2 and 3 are not here: they belong to
    `_question_teaching_message`, which can point at what is on screen.
    """
    if attempt >= 4:
        return random.choice(HINT_RESPONSES_ATTEMPT_4_PLUS)
    return random.choice(HINT_RESPONSES_ATTEMPT_1)


def _is_second_try_encouragement(payload: GuideRequest) -> bool:
    """The first wrong answer opens the child's second try."""
    return bool(
        payload.event in {"PRACTICE_ANSWER_INCORRECT", "TOPIC_ANSWER_INCORRECT"}
        and payload.question
        and payload.question.attempt == 1
    )


def _time_greeting(payload: GuideRequest) -> str:
    """Return a time-of-day aware greeting prefix, on the child's clock.

    The hour comes from the child's device when it sends one. UTC is never
    right here: a child in IST opening the app at 9am is at 03:30 UTC, which
    would greet their morning with "Good evening". Server local time is the
    fallback, which is correct whenever the backend runs beside the child.
    """
    hour = payload.local_hour if payload.local_hour is not None else datetime.now().hour
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
        return "Open Practice, then choose one of your subjects."
    if any(word in question for word in {"topic", "subject", "lesson"}):
        return "Open Adventure, choose a subject, and tap the bright unlocked topic."
    if "star" in question or "reward" in question:
        stars = progress.session_stars if progress else 0
        return f"You have {stars} stars. Open Rewards to see your badges and prizes."
    if "certificate" in question:
        return "Your certificate unlocks after you finish every topic in your class."
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


# Writing steps that ask for a drawing rather than a shape. The curriculum
# authors these with no accuracy to reach: the point is holding the crayon.
FREE_DRAW_TARGETS = {"free", "free draw", "freedraw", "scribble", "doodle", "anything", "draw"}


def _is_counting_question(payload: GuideRequest) -> bool:
    if not payload.question:
        return False
    answer_type = (payload.question.answer_type or payload.question.topic or "").lower()
    return answer_type in {"count_objects", "select_number"} or "number" in answer_type or "count" in payload.question.prompt.lower()


def _base_teaching_message(payload: GuideRequest) -> tuple[str, GuideVisualAction, str]:
    question = payload.question
    if not question:
        return "Look at the screen. Try one small answer.", GuideVisualAction(), "read_question"

    # The ceiling comes first. Every branch below re-explains, and none of them
    # looked at how many times it had already re-explained - so on the
    # deterministic path (Groq down, another provider configured, or the safety
    # net below falling back) a stuck child was re-taught the same question for
    # as long as they stayed on the screen. Nothing here re-asks or says "wrong".
    if _ladder_attempt(payload) >= 4:
        return random.choice(HINT_RESPONSES_ATTEMPT_4_PLUS), GuideVisualAction(), "re_explain"

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

    # Writing is guided by hand, not by choosing: the help a child needs is
    # where to start and which way to move, said out loud while they draw.
    # Whether the writing is good enough is measured on the device from the
    # gesture — nothing here decides that.
    if any(word in answer_type for word in ("trace", "write", "draw")):
        shape = (question.example or question.correct_answer or (visual_items[0] if visual_items else "") or "shape").replace("_", " ")
        # A free page has no shape to follow, so it must not be described as one.
        if shape in FREE_DRAW_TARGETS:
            return (
                "This page is yours. Draw anything you like, then tap I finished.",
                GuideVisualAction(),
                "visual_explanation",
            )
        if attempt >= 1:
            return (
                f"Tap Watch me. My finger draws {shape}. Then follow the grey line slowly.",
                _visual_action(payload, "trace_shape", visual_targets[:1]),
                "re_explain",
            )
        return (
            f"Put your finger on the blue dot. Follow the grey {shape} all the way.",
            _visual_action(payload, "trace_shape", visual_targets[:1]),
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
            "Look at the letter. Listen to its name, then choose it.",
            _visual_action(payload, "pulse", visual_targets[:1]),
            "visual_explanation" if attempt == 0 else "hint",
        )

    return (
        f"Look at what is shown. {question.hint or question.prompt}",
        _visual_action(payload, "highlight", visual_targets),
        "visual_explanation" if attempt == 0 else "hint",
    )


# How each teaching strategy opens, when the deterministic guide is the one
# doing the talking. Before the policy was wired in, every rung of the repair
# ladder re-ran the same branch of `_base_teaching_message` and the child heard
# the same explanation with a different encouragement in front of it - three
# encouragements, zero new understanding. The frame is what makes the second
# explanation a different explanation.
#
# S1_TELL has no frame on purpose: telling the child plainly is the base
# wording. S9_PARK never reaches here - a parked question returns the park line
# before any of this.
STRATEGY_FRAMES = {
    "S2_SHOW": "Watch the screen with me.",
    "S3_EXAMPLE": "Here is one like it.",
    "S4_STORY": "Little story about this one.",
    "S5_CONTRAST": "Look at both, then choose.",
    "S6_DO_TOGETHER": "Let us do it together.",
    "S7_SENSE_SWITCH": "Say it out loud with me.",
    "S8_PREREQUISITE": "One small step back first.",
}


def _question_teaching_message(payload: GuideRequest) -> tuple[str, GuideVisualAction, str]:
    """The teaching wording, opened in the strategy the policy chose.

    The frame is added only from rung 2, where the guide is re-explaining
    something that has already failed once, and only in standard mode - Play
    Group has fourteen words for the whole turn and cannot spend five of them on
    a lead-in.
    """
    message, visual_action, strategy = _base_teaching_message(payload)
    rung = _ladder_attempt(payload)
    if payload.experience_mode == "early" or rung < 2 or rung >= policy_actions.PARK_RUNG:
        return message, visual_action, strategy

    decision = _turn_decision(payload)
    frame = STRATEGY_FRAMES.get(decision.strategy) if decision else None
    return (f"{frame} {message}" if frame else message), visual_action, strategy


def _fallback_guide(payload: GuideRequest) -> GuideResponse:
    validate_guide_request(payload)
    # Whatever the provider setting says, these words are the app's own.
    _TURN_AUTHOR.set("deterministic")

    if payload.experience_mode == "early":
        return _early_mode_guide(payload)

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
        greeting = _time_greeting(payload)
        topic = payload.progress.current_topic if payload.progress else None
        last = payload.progress.last_completed_topic if payload.progress else None
        completed_at = payload.progress.last_completed_at if payload.progress else None
        if last and topic:
            when = "Last time"
            if completed_at and completed_at.date() == (datetime.now(timezone.utc) - timedelta(days=1)).date():
                when = "Yesterday"
            message = f"{greeting}! {when} you finished {last}. Today, tap Continue Adventure for {topic}."
        elif topic:
            message = f"{greeting}! Tap Continue Adventure to start {topic}."
        else:
            message = f"{greeting}! Tap Continue Adventure to begin."
        strategy = "welcome"
        action = _ui_action(payload, "highlight", ["continue-adventure", "topic-card", "home-practice", "start-practice"])
        next_event = "button_clicked"
        state = "waving"
        effect = "sparkle"

    # --- ADVENTURE_OPENED ---
    elif payload.event == "ADVENTURE_OPENED":
        subject = payload.progress.current_subject if payload.progress else None
        message = (
            f"Here is {subject}! Tap the glowing topic to begin."
            if subject
            else "Here are your subjects! Tap one to begin."
        )
        strategy = "navigation"
        action = _ui_action(payload, "highlight", ["subject-card", "topic-card", "current-map-level"])
        next_event = "button_clicked"
        state = "speaking"
        effect = "sparkle"

    # --- TOPIC_OPENED ---
    elif payload.event == "TOPIC_OPENED":
        topic = payload.progress.current_topic if payload.progress else "this topic"
        message = f"Here is {topic}. Tap to start when you are ready."
        strategy = "navigation"
        action = _ui_action(payload, "highlight", ["topic-card", "current-map-level"])
        next_event = "button_clicked"
        state = "speaking"

    # --- PRACTICE_OPENED ---
    elif payload.event == "PRACTICE_OPENED":
        message = "Practice time! Pick a subject you want to work on."
        strategy = "navigation"
        action = _ui_action(payload, "highlight", ["start-practice", "home-practice"])
        next_event = "button_clicked"
        state = "speaking"
        effect = "bounce"

    # --- PRACTICE_STARTED / TOPIC_STARTED ---
    elif payload.event in {"PRACTICE_STARTED", "TOPIC_STARTED"}:
        message, visual_action, strategy = _question_teaching_message(payload)
        action = _ui_action(payload, "highlight", ["question-area", "voice-answer-area", "microphone-button"])
        next_event = "voice_answer_requested"
        state = "storytelling"
        effect = "story_transition"

    # --- QUESTION LOADED / REPEAT ---
    elif payload.event in {"PRACTICE_QUESTION_LOADED", "TOPIC_QUESTION_LOADED", "REPEAT_REQUESTED"}:
        message, visual_action, strategy = _question_teaching_message(payload)
        action = _ui_action(payload, "highlight", ["question-area", "counting-object-group", "voice-answer-area", "microphone-button"])
        next_event = "voice_answer_requested"

    # --- INCORRECT ANSWER ---
    elif payload.event in {"PRACTICE_ANSWER_INCORRECT", "TOPIC_ANSWER_INCORRECT", "HINT_REQUESTED"}:
        if _is_second_try_encouragement(payload):
            message = _pick_hint(1)
            visual_action = GuideVisualAction()
            strategy = "hint"
            preferred_targets = ["question-area", "voice-answer-area", "microphone-button"]
        else:
            message, visual_action, strategy = _question_teaching_message(payload)
            message = _words(message, 22)
            preferred_targets = ["counting-object-group", "question-area", "voice-answer-area", "microphone-button"]
        action_type: GuideActionType = "show_hint"
        action = _ui_action(payload, action_type, preferred_targets)
        # A parked question is not asked again, so the app must not sit waiting
        # for an answer to it.
        next_event = "next_question_loaded" if _ladder_attempt(payload) >= 4 else "voice_answer_requested"
        state = "encouraging"
        effect = "gentle_hint"

    # --- CORRECT ANSWER ---
    elif payload.event in {"PRACTICE_ANSWER_CORRECT", "TOPIC_ANSWER_CORRECT"}:
        message = _pick_praise(session_id)
        strategy = "none"
        action = GuideUiAction(type="none", target=None)
        next_event = "next_question_loaded"
        state = "celebrating"
        effect = "star_burst"

    # --- COMPLETION EVENTS ---
    elif payload.event in {"PRACTICE_COMPLETED", "TOPIC_COMPLETED", "TOPIC_UNLOCKED", "CERTIFICATE_UNLOCKED", "SUBJECT_COMPLETED"}:
        if payload.event == "PRACTICE_COMPLETED":
            message = "Practice complete! You worked so hard. Tap Subjects or try more practice."
            action = _ui_action(payload, "highlight", ["open-subjects", "more-practice", "continue-adventure"])
        elif payload.event == "CERTIFICATE_UNLOCKED":
            message = "Your certificate is ready! You are a Saksham IQ Explorer. Tap to open it."
            action = _ui_action(payload, "highlight", ["open-certificate"])
            effect = "rainbow"
        elif payload.event == "SUBJECT_COMPLETED":
            subject = payload.progress.current_subject if payload.progress else "this subject"
            message = f"You completed {subject}! Another subject is waiting for you."
            action = _ui_action(payload, "highlight", ["continue-adventure", "open-subjects"])
            effect = "confetti"
        elif payload.event == "TOPIC_UNLOCKED":
            message = "A new topic just opened! Tap Continue Adventure to explore."
            action = _ui_action(payload, "highlight", ["continue-adventure", "topic-card", "open-subjects"])
            effect = "confetti"
        else:
            # Named after no single button: a finished lesson offers "See my
            # levels", the home screen offers "Continue Adventure", and the
            # child is told to tap whichever one is glowing at them.
            message = "Wonderful work! Tap the glowing button to keep going."
            action = _ui_action(payload, "highlight", ["continue-adventure", "topic-card", "open-subjects"])
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
                ["counting-object-group", "question-area", "activity-area", "voice-answer-area", "answer-options"],
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
        teaching_strategy=_deterministic_teaching_strategy(payload),
        avatar=_avatar(message, state=state, effect=effect, speak=True),
        ui_action=action,
        visual_action=visual_action,
        next_expected_event=next_event,
    )


def _early_teaching_script(payload: GuideRequest) -> str:
    """Teach the thing before asking about it, on the lesson screen too.

    The conductor already does this. Play Group and Nursery reach their lessons
    through `/learning` as well - that is what auto-open opens today - and a
    child must not be taught differently depending on which route the app took
    to the same activity.

    First presentation only: a repair turn belongs to the ladder, which has its
    own thing to say.
    """
    if payload.experience_mode != "early" or payload.question is None:
        return ""
    if payload.event not in FIRST_PRESENTATION_EVENTS or _ladder_attempt(payload) != 0:
        return ""

    topic_id = payload.progress.current_topic if payload.progress else None
    if not topic_id:
        return ""
    try:
        topic = curriculum_service.get_topic(topic_id)
        activities = curriculum_service.get_activities(topic_id)
    except Exception:
        return ""
    activity = next(
        (item for item in activities if item.activity_id == payload.question.activity_id), None
    )
    return explain.script_for(topic, activity, activities)


def _early_mode_guide(payload: GuideRequest) -> GuideResponse:
    """Guidance for Play Group and Nursery.

    `early` mode assumes the child may be pre-verbal: tapping is always the
    primary action and speaking is optional. Copy stays under 14 words.
    """
    question = payload.question
    # How the concept is *said*. A Hindi level's answer key is an asset token
    # ("anar"), and speaking that token would have the guide say a Hindi word in
    # Roman letters. `spoken_form` reads the Devanagari back out of the author's
    # own prompt; everything else passes through untouched.
    concept = (
        explain.spoken_form(
            question.correct_answer or "", prompt=question.prompt, hint=question.hint or ""
        )
        if question
        else ""
    )
    activity_type = (question.answer_type if question else "") or ""
    attempt_count = question.attempt if question else 0
    target_preferences = ["activity-area", "answer-options", "microphone-button", "continue-adventure", "start-practice"]
    state = "speaking"
    effect = "none"
    strategy = "read_question"
    next_event = "wait_for_child"
    visual_action = GuideVisualAction()
    # Writing is most of what Play Group and Nursery do, and it is the one
    # activity with nothing to tap. Echoing the prompt back at the child helps
    # nobody: what they need is where to put the finger and which way to go.
    is_writing = bool(question) and any(word in activity_type for word in ("trace", "write", "draw"))
    drawn = ((question.example or question.correct_answer or "") if question else "").replace("_", " ")

    if payload.event in {"APP_OPENED", "HOME_OPENED"}:
        message = "Hi little explorer! 👋 Let's learn."
        state = "waving"
        strategy = "welcome"
        target_preferences = ["continue-adventure", "subject-card", "adventure-home"]
    elif payload.event in {"ADVENTURE_OPENED", "TOPIC_OPENED"}:
        message = "Tap a picture to start. 😊"
        strategy = "navigation"
        target_preferences = ["subject-card", "topic-card", "adventure-home"]
    elif payload.event == "GUIDE_HELP_REQUESTED":
        teaching_payload = payload.model_copy(
            update={"question": question.model_copy(update={"attempt": max(1, question.attempt)})}
        ) if question else payload
        teaching_message, visual_action, strategy = _question_teaching_message(teaching_payload)
        if is_writing:
            message = "Tap Watch me. 👀 Then follow the grey line."
        else:
            message = teaching_message if _is_counting_question(teaching_payload) else f"Here it is. Tap {concept}." if concept else _help_message(payload)
        state = "speaking"
        strategy = "help"
        target_preferences = ["answer-options", "activity-area", "microphone-button"]
    elif payload.event in {"TOPIC_ANSWER_CORRECT", "PRACTICE_ANSWER_CORRECT"}:
        message = f"Yay! That's {concept}! ⭐" if concept else "Yay! Great job! ⭐"
        state = "celebrating"
        effect = "star_burst"
        strategy = "celebrate"
        next_event = "next_activity"
    elif payload.event in {"TOPIC_ANSWER_INCORRECT", "PRACTICE_ANSWER_INCORRECT", "HINT_REQUESTED"}:
        # After two tries, stop testing and simply show the answer - and after
        # four, stop showing it too. Early mode had no ceiling at all: it
        # repeated "Here it is. Tap X." for as long as the child stayed, which
        # is the version of drilling a pre-verbal child actually experiences.
        if _ladder_attempt(payload) >= 4:
            message = _pick_hint(4)
            strategy = "re_explain"
            state = "encouraging"
            effect = "gentle_hint"
            next_event = "next_activity"
            target_preferences = ["continue-adventure", "activity-area"]
        elif is_writing:
            message = "Tap Watch me. 👀 My finger shows the way."
            strategy = "re_explain" if attempt_count >= 2 else "hint"
        elif activity_type.startswith("repeat_") and concept:
            message = f"Tap {concept}. You can say it too."
            strategy = "re_explain" if attempt_count >= 2 else "hint"
        elif attempt_count >= 2 and concept:
            message = f"Here it is. Tap {concept}."
            strategy = "re_explain"
        elif question:
            message, visual_action, strategy = _question_teaching_message(payload)
        else:
            message = f"Almost! 😊 Let's try {concept} again." if concept else "Almost! 😊 Let's try again."
            strategy = "hint"
        state = "encouraging"
        effect = "gentle_hint"
        target_preferences = ["answer-options", "activity-area", "microphone-button"]
    elif payload.event in {"TOPIC_COMPLETED", "PRACTICE_COMPLETED", "SUBJECT_COMPLETED"}:
        message = "Wow! You did it! 🌟"
        state = "celebrating"
        effect = "confetti"
        strategy = "celebrate"
        target_preferences = ["continue-adventure", "start-practice"]
    elif question:
        if is_writing and drawn in FREE_DRAW_TARGETS:
            message = "Draw anything you like! 🎨"
        elif is_writing:
            message = f"Finger on the blue dot. Follow the {drawn}. ✏️" if drawn else "Finger on the blue dot. Follow the grey line. ✏️"
        elif activity_type.startswith("repeat_") and concept:
            message = f"Tap {concept}. You can say it too."
            target_preferences = ["answer-options", "activity-area", "microphone-button"]
        elif activity_type.startswith(("identify_", "recognize_", "select_")) and concept:
            message = f"Tap {concept}."
            target_preferences = ["answer-options", "activity-area"]
        else:
            message = _words(question.learning_objective or question.prompt, 10)
    else:
        message = "Look, listen, then try. 😊"

    # A turn that *teaches* is allowed more than an instruction: fourteen words
    # is the ceiling on telling a two-year-old what to do, not on showing them
    # what a thing is.
    script = _early_teaching_script(payload)
    if script:
        message = script
    message = safe_text(_words(message, explain.MAX_TEACHING_WORDS + 8 if script else 14))
    return GuideResponse(
        message=message,
        strategy=strategy,
        teaching_strategy=_deterministic_teaching_strategy(payload),
        avatar=_avatar(message, state=state, effect=effect, speak=True),
        ui_action=_ui_action(payload, "highlight", target_preferences),
        visual_action=visual_action,
        next_expected_event=next_event,
    )


# The guide does seven jobs, and one instruction used to serve all of them at
# once. Naming them separately is what shows that four never needed a model at
# all: a greeting, a well done, a topic-finished line and a star count are canned
# copy over data the server already holds. Routing those to Groq bought latency
# and one more place an off-menu `ui_action.target` could appear, and nothing
# else - `_fallback_guide` was already computing the right answer underneath.

# T1 welcome and navigation, T4 celebrate a correct answer, T5 completion and
# unlock, T6 rewards narration. None of these call the model.
DETERMINISTIC_EVENTS = {
    "APP_OPENED",
    "HOME_OPENED",
    "ADVENTURE_OPENED",
    "TOPIC_OPENED",
    "PRACTICE_OPENED",
    "PRACTICE_ANSWER_CORRECT",
    "TOPIC_ANSWER_CORRECT",
    "PRACTICE_COMPLETED",
    "TOPIC_COMPLETED",
    "TOPIC_UNLOCKED",
    "CERTIFICATE_UNLOCKED",
    "SUBJECT_COMPLETED",
    "REWARDS_OPENED",
}

# T2: the first explanation a child hears for a concept.
FIRST_PRESENTATION_EVENTS = {
    "PRACTICE_STARTED",
    "TOPIC_STARTED",
    "PRACTICE_QUESTION_LOADED",
    "TOPIC_QUESTION_LOADED",
    "REPEAT_REQUESTED",
}

# T3: the repair ladder. The one task where the choice of strategy depends on
# how the child got it wrong, rather than on which event fired.
REPAIR_EVENTS = {
    "PRACTICE_ANSWER_INCORRECT",
    "TOPIC_ANSWER_INCORRECT",
    "HINT_REQUESTED",
}

# T7: the child asked something in their own words.
HELP_EVENTS = {"GUIDE_HELP_REQUESTED"}

# The nine teaching strategies, and which of them each turn may use. A turn that
# only moves the child around the app - a welcome, a route change, a
# celebration - teaches nothing and spends no strategy, so it returns none.
TEACHING_EVENTS = FIRST_PRESENTATION_EVENTS | REPAIR_EVENTS | HELP_EVENTS

ALL_TEACHING_STRATEGIES = (
    "S1_TELL",
    "S2_SHOW",
    "S3_EXAMPLE",
    "S4_STORY",
    "S5_CONTRAST",
    "S6_DO_TOGETHER",
    "S7_SENSE_SWITCH",
    "S8_PREREQUISITE",
    "S9_PARK",
)

# Play Group and Nursery lose the four that assume verbal reasoning or a lower
# level to step back to. The overlay says so in words; this says so in code, so
# a model that ignores the words still cannot return S4_STORY to a three-year-old.
EARLY_MODE_TEACHING_STRATEGIES = ("S1_TELL", "S2_SHOW", "S6_DO_TOGETHER", "S7_SENSE_SWITCH", "S9_PARK")


def _is_teaching_turn(payload: GuideRequest) -> bool:
    """Whether this turn explains something about the current question."""
    return bool(payload.question) and payload.event in TEACHING_EVENTS


def _allowed_teaching_strategies(payload: GuideRequest) -> tuple[str, ...]:
    if payload.experience_mode == "early":
        return EARLY_MODE_TEACHING_STRATEGIES
    return ALL_TEACHING_STRATEGIES


# Which strategies the guide has already spent on one question in one session,
# so it can be told not to repeat itself. `conversation` alone cannot carry this
# - it holds eight turns of raw text, scrolls out from under a long repair
# sequence, and never names the strategy.
#
# The durable copy is `teaching_events`, written through
# `teaching_policy_service`, and that is what a real child's turn reads. This
# dict is the fallback for the two cases with no learner behind them: a guide
# call with no child id (the demo and the test payloads), and a database that is
# not answering. It is lost on restart, which is exactly why it is not the
# primary any more - a child returning after a crash used to be handed the
# explanation that had already failed them.
_STRATEGY_LOG: dict[tuple[str, str], list[str]] = {}
_STRATEGY_LOG_MAX_QUESTIONS = 500


# The policy's choice for the turn being served, so the wording, the tag on the
# response and the episode written afterwards all describe the same decision.
# A ContextVar rather than an argument threaded through eleven call sites, and
# request-scoped rather than global: two children being taught at once must not
# see each other's strategy.
_TURN_DECISION: ContextVar[TeachingDecision | None] = ContextVar("guide_turn_decision", default=None)

# Who wrote the words the child heard. `teaching_events.author` separates the
# model's turns from the deterministic ones, which is the whole basis of the
# holdout comparison - a policy trained on a mix of the two, with no record of
# which was which, cannot be evaluated against the fallback it is meant to beat.
_TURN_AUTHOR: ContextVar[str] = ContextVar("guide_turn_author", default="deterministic")


def _skill_id(payload: GuideRequest) -> str:
    """The concept this turn teaches, named the way `learning_service` names it.

    "<subject>:<topic>" is the id the attempt log and the mastery roll-up use,
    so a strategy spent here and the retention probe that eventually pays for it
    line up on the same skill. `question.topic` carries the activity type from
    the client and is only a last resort.
    """
    progress = payload.progress
    subject = (progress.current_subject if progress else None) or "unknown"
    topic = (progress.current_topic if progress else None) or (
        payload.question.topic if payload.question else None
    ) or "unknown"
    return f"{subject}:{topic}"


def _policy_decision(payload: GuideRequest) -> TeachingDecision | None:
    """Ask the policy which strategy this turn should spend.

    None on a turn that teaches nothing, and on rung 1 - the clean second try,
    where the guide only encourages. Spending a strategy there would burn one of
    the nine on a turn that said nothing new.
    """
    if not _is_teaching_turn(payload):
        return None
    rung = _ladder_attempt(payload)
    if not policy_actions.is_teaching_rung(rung):
        return None
    return teaching_policy_service.decide(
        child_id=payload.child_id,
        skill_id=_skill_id(payload),
        activity_id=payload.question.activity_id if payload.question else None,
        experience_mode=payload.experience_mode,
        rung=rung,
        spent=_strategies_used(payload),
    )


def _turn_decision(payload: GuideRequest) -> TeachingDecision | None:
    """The decision for this turn, computed once by `guide()`.

    `_fallback_guide` is also called on its own - by the tests, and as the
    safety net inside `_validate_model_response` - so it falls back to asking.
    Asking is a read; only `guide()` ever writes the episode.
    """
    decision = _TURN_DECISION.get()
    return decision if decision is not None else _policy_decision(payload)


def _deterministic_strategy_for_substitution(payload: GuideRequest) -> TeachingStrategy | None:
    """The model was overruled and the app wrote the words. Say so, then tag."""
    _TURN_AUTHOR.set("deterministic")
    return _deterministic_teaching_strategy(payload)


def _deterministic_teaching_strategy(payload: GuideRequest) -> TeachingStrategy | None:
    """The strategy the deterministic wording just spent, for the response tag.

    Before this, `teaching_strategy` was only ever set by the model - so with no
    provider configured, which is the default, the nine-strategy action space
    existed on paper and nothing in the running app ever chose from it, recorded
    one, or avoided repeating one.
    """
    decision = _turn_decision(payload)
    if decision is None:
        return None
    strategy = decision.strategy
    return strategy if strategy in _allowed_teaching_strategies(payload) else None  # type: ignore[return-value]


def _leak_verdict(payload: GuideRequest, response: GuideResponse) -> "policy_leak.Verdict":
    """What this turn did with the answer key it was never shown.

    The model is handed the question with `correct_answer` stripped, which stops
    it *reading* the answer out and does not stop it guessing one and telling the
    child. The server still holds the key, so it can check the sentence it is
    about to send - and it checks the deterministic wording too, because a
    template that names the answer is the same leak with a different author.

    A leak is not blocked here; blocking would leave the child with silence on
    the turn they needed most. It is *recorded*, and the recording costs the
    strategy 1.5 of reward - more than a passed probe pays - so a strategy that
    leaks is unlearned rather than merely tutted at.
    """
    question = payload.question
    spoken = " ".join(
        part for part in (response.message, getattr(response.avatar, "message", None)) if part
    )
    return policy_leak.classify(
        spoken,
        correct_answer=question.correct_answer if question else None,
        prompt=question.prompt if question else "",
        options=tuple(question.options) if question else (),
        accepted=tuple(question.accepted_answers) if question else (),
    )


def _spend_turn(payload: GuideRequest, response: GuideResponse) -> None:
    """Record what the child was actually taught, once per served turn."""
    author = _TURN_AUTHOR.get()
    strategy = response.teaching_strategy
    if not strategy:
        return
    _record_strategy(payload, strategy)
    decision = _TURN_DECISION.get()
    if decision is None:
        return
    verdict = _leak_verdict(payload, response)
    if verdict.is_leak:
        logger.warning(
            "Answer leak on %s by %s (%s): %s",
            payload.question.activity_id if payload.question else "?",
            strategy,
            author,
            verdict.evidence,
        )
    teaching_policy_service.commit(
        child_id=payload.child_id,
        skill_id=_skill_id(payload),
        activity_id=payload.question.activity_id if payload.question else None,
        decision=decision,
        strategy=strategy,
        experience_mode=payload.experience_mode,
        rung=_ladder_attempt(payload),
        author=author,
        answer_leak_vetoed=verdict.is_leak,
        leak_kind=verdict.kind,
    )


def _ladder_attempt(payload: GuideRequest) -> int:
    """Which rung of the repair ladder this turn stands on.

    HINT_REQUESTED has no wrong answer behind it - the child asked for help
    unprompted - so it never sits on rung 1, where the guide only encourages: a
    child who asks for a hint has already said that encouragement will not do.
    It is raised to rung 2 rather than pinned there, so asking for a hint on a
    question that is already parked does not drag it back into being drilled.
    """
    # `attempt` arrives from the client and is trusted, unlike the answer key or
    # `strategies_used`. That is defensible - it is app UI state, and nothing
    # scores off it: `activity_evaluators` and `answer_resolution_service` never
    # read it. But it does drive every rung of the ladder, so it is clamped to a
    # range the ladder has an answer for. A client stuck at 0 still defeats the
    # escalation; that is a client bug to fix in the client, not here.
    attempt = max(0, min(payload.question.attempt if payload.question else 0, 6))
    if payload.event == "HINT_REQUESTED":
        return max(2, attempt)
    if attempt >= 1:
        # Rung 1 was the clean second try: encouragement, nothing taught, no
        # strategy spent. A question gets three repairs now, and none of them
        # can afford to be a turn that teaches nothing - a child who has just
        # got it wrong is told something new on the very next turn, chosen by
        # the policy. So the first miss steps straight onto the ladder.
        return min(attempt + 1, policy_actions.PARK_RUNG)
    return attempt


def _strategy_log_key(payload: GuideRequest) -> tuple[str, str] | None:
    """One log per question per session, so moving on clears the history."""
    if not payload.session_id or not payload.question:
        return None
    return (payload.session_id, payload.question.activity_id)


def _strategies_used(payload: GuideRequest) -> list[str]:
    """What this child has already heard on this question.

    The durable log wins when it can answer; the in-process dict is the fallback
    for a payload with no learner behind it. Either way this is server state -
    `question.strategies_used` arriving from the client is never read, because a
    client that could write it could mark every strategy that works as spent.
    """
    durable = teaching_policy_service.spent_strategies(
        child_id=payload.child_id,
        activity_id=payload.question.activity_id if payload.question else None,
    )
    key = _strategy_log_key(payload)
    remembered = list(_STRATEGY_LOG.get(key, ())) if key else []
    if durable is None:
        return remembered
    # Both, in durable-first order: a turn served before the write landed is
    # still a turn the child heard.
    return durable + [strategy for strategy in remembered if strategy not in durable]


def _record_strategy(payload: GuideRequest, strategy: str | None) -> None:
    key = _strategy_log_key(payload)
    if not key or not strategy:
        return
    used = _STRATEGY_LOG.setdefault(key, [])
    if strategy not in used:
        used.append(strategy)
    if len(_STRATEGY_LOG) > _STRATEGY_LOG_MAX_QUESTIONS:
        _STRATEGY_LOG.pop(next(iter(_STRATEGY_LOG)))


# A model that was never shown the answer key congratulating a child on a miss
# is the one failure the blanket message override existed to stop, and it is a
# real one: the deterministic grader has already recorded the miss, so on a
# repair turn any of these contradicts the score the app is about to show.
# Everything else the model says on such a turn is now trusted.
AFFIRMS_CORRECT = re.compile(
    r"\b(that's right|thats right|that is right|you're right|youre right|you are right"
    r"|correct|well done|good job|great job|perfect|exactly right|you got it"
    r"|nailed it|spot on|you did it)\b"
    r"|\byes\s*[!.]",
    re.IGNORECASE,
)


def _model_message_is_usable(message: str, response: GuideResponse) -> bool:
    """Whether the model's own repair wording may reach the child.

    Three ways it may not: it claims the child was right, it carries no legal
    teaching strategy (a malformed answer like any other), or safety trimming
    left nothing - `safe_text` returning FALLBACK on a repair turn means the
    child would hear "I can help you with numbers, letters..." instead of help
    with the question actually in front of them.
    """
    if not message.strip() or message == FALLBACK:
        return False
    if response.teaching_strategy is None:
        return False
    return not AFFIRMS_CORRECT.search(message)


def _teaching_strategy_from(payload: GuideRequest, decoded: object) -> TeachingStrategy | None:
    """The model's chosen strategy, or None if it is not one this turn may use.

    A bad value drops the field rather than the whole response: the message the
    child sees is the part that matters, and a missing tag costs one turn of
    repeat-avoidance, not a turn of teaching.
    """
    if not isinstance(decoded, dict) or not _is_teaching_turn(payload):
        return None
    raw = decoded.get("teaching_strategy")
    if isinstance(raw, str) and raw.strip().upper() in _allowed_teaching_strategies(payload):
        return raw.strip().upper()  # type: ignore[return-value]
    return None


# The model is never shown the answer key. It used to receive the whole request,
# question context included, and nothing in the prompt forbade repeating the
# answer on a help request — so "what is the answer?", which is the first thing a
# four-year-old asks the guide, could be answered. The child then taps it and the
# deterministic scorer awards the star, which makes the LLM the thing that
# decided the star. Every deterministic path that needs the key already holds it
# locally; the model only ever needed the prompt, the hint and the options.
ANSWER_KEY_FIELDS = ("correct_answer", "accepted_answers")


def _payload_for_model(payload: GuideRequest) -> dict:
    data = payload.model_dump(mode="json", exclude_none=True)
    question = data.get("question")
    if isinstance(question, dict):
        data["question"] = {key: value for key, value in question.items() if key not in ANSWER_KEY_FIELDS}
        # Whatever the client sent in `strategies_used` is discarded and the
        # server's own log put in its place - the same trust boundary as the
        # answer key above. A client that could write this could mark every
        # strategy that works as already spent.
        data["question"]["strategies_used"] = _strategies_used(payload)
    return data


def _model_instruction(payload: GuideRequest) -> str:
    """The per-task instruction for this turn.

    This used to be one string for every event alike, which is why it read as a
    list of exceptions: a paragraph for GUIDE_HELP_REQUESTED, a clause about
    hints after a wrong answer, a clause about voice practice, all sent whether
    or not they applied. Only three tasks reach here now, and each gets the
    instruction for its own job and nothing else.
    """
    if payload.event in REPAIR_EVENTS:
        task = _repair_instruction(payload)
    elif payload.event in HELP_EVENTS:
        task = _help_instruction(payload)
    else:
        task = _first_presentation_instruction(payload)
    return _instruction_envelope(payload, task)


def _policy_proposal(payload: GuideRequest) -> str:
    """Hand the model the policy's choice, as a strong default it may refuse.

    The policy picks the strategy; the model writes the sentence. Making it a
    default rather than an order matters in one direction only: the model can
    see the question and the policy cannot, so a strategy that is impossible for
    this particular question - a contrast where there is nothing to contrast
    with - should be dropped rather than forced. Whatever comes back is what is
    written to the episode, so the table learns from what was really said.
    """
    decision = _turn_decision(payload)
    if decision is None or not _is_teaching_turn(payload):
        return ""
    return (
        f"The teaching policy has chosen {decision.strategy} for this turn, from what has worked for "
        "children at this stage. Use it unless this question makes it impossible, and then pick another "
        "from the allowed list. "
    )


def _instruction_envelope(payload: GuideRequest, task: str) -> str:
    """The allowed values and the standing limits, shared by all three tasks."""
    allowed_actions = sorted(_approved_actions_from_request(payload))
    allowed_targets = [target for target in payload.available_targets if target in APPROVED_GUIDE_TARGETS]
    allowed_visual_targets = [target for target in payload.allowed_visual_targets if target.startswith(("visual-item-", "visual-example-"))]
    keys = (
        "message, strategy, teaching_strategy, avatar, ui_action, visual_action, next_expected_event"
        if _is_teaching_turn(payload)
        else "message, strategy, avatar, ui_action, visual_action, next_expected_event"
    )
    return (
        "Create one Saksham IQ Guide response for this event. "
        f"Return exactly one JSON object with keys: {keys}. "
        + task
        + _policy_proposal(payload)
        + f"Allowed ui_action.type values: {allowed_actions}. "
        f"Allowed ui_action.target values: {allowed_targets}; use null if no target is needed. "
        f"Allowed visual_action.type values: {sorted(APPROVED_VISUAL_ACTIONS)}. "
        f"Allowed visual_action.targets values: {allowed_visual_targets}. "
        "avatar must include state, message, speak, animationEffect. "
        "Do not decide if the answer is correct. Do not change score, stars, rewards, progress, unlocking, or certificates. "
        "For voice practice, explain before listening, never tell the app to listen while avatar is speaking, "
        "and use the microphone or voice-answer targets when asking for an answer. "
        "Use only the supplied question and concept. Keep child-facing text short (under 25 words). "
        "Do not tell the child to tap a button unless they asked how to navigate. "
        "Always use warm, encouraging language. Never shame the child."
    )


def _first_presentation_instruction(payload: GuideRequest) -> str:
    """T2. The first explanation, where there is nothing to repair yet."""
    if not payload.question:
        return (
            "The child is starting this activity and no question is loaded yet. Say one short, warm sentence "
            'about what they are about to do. Set strategy to "read_question" and omit teaching_strategy. '
        )
    return (
        "This is the child's first look at this question, or they asked to hear it again with no wrong answer "
        "yet. Use S1_TELL or S2_SHOW only - do not hint and do not simplify, there is nothing to repair yet. "
        "Say what the concept is in the fewest words, referring to what is actually visible. If visual_items "
        "are present, point at them by name rather than describing them abstractly, then ask for the answer in "
        "one short sentence. Do not restate the question as your explanation - restating is not teaching. "
        "For a counting activity, count the visible items aloud in order before asking how many there are "
        "altogether. For a trace, write or draw activity, say where to put the finger and which way to move; "
        "do not mention accuracy, the device measures the gesture and you do not. "
        'Set strategy to "read_question" or "visual_explanation", teaching_strategy to "S1_TELL" or "S2_SHOW", '
        'and next_expected_event to "voice_answer_requested". '
    )


def _repair_instruction(payload: GuideRequest) -> str:
    """T3. The repair ladder: which rung, which strategies are left, what to set."""
    attempt = _ladder_attempt(payload)
    allowed = list(_allowed_teaching_strategies(payload))
    spent = _strategies_used(payload)
    early = payload.experience_mode == "early"
    asked_for_help = payload.event == "HINT_REQUESTED"

    opening = (
        "The child asked for a hint on this question without answering it wrongly first, so treat it as a "
        "hint turn and never as bare encouragement. "
        if asked_for_help
        else "The child answered this question incorrectly. "
    )

    if attempt >= 4:
        rung = (
            'This question is parked. Use S9_PARK: one kind sentence under 14 words, no hint, no '
            're-explanation, and do not ask the question again. Set strategy to "re_explain" and '
            'next_expected_event to "wait_for_child" so the app can move the child on. '
        )
    elif attempt <= 2:
        # The rung that used to be bare encouragement - "good try, go again" -
        # is gone: a question gets three repairs and none of them can be a turn
        # that teaches nothing.
        rung = (
            "This is the child's first wrong answer. Stop testing memory: use S1_TELL or S2_SHOW and say "
            "exactly what to tap. "
            if early
            else "This is the child's first wrong answer. Encouragement alone is not enough - give one "
            "small hint with S3_EXAMPLE or S5_CONTRAST, pointing at what makes the child's answer "
            "different from what is being asked. "
        ) + 'Set strategy to "hint" and next_expected_event to "voice_answer_requested". '
    else:
        rung = (
            "This is the last turn you re-teach this question. Show what to tap and say it plainly. "
            if early
            else "This is the last turn you re-teach this question. Switch how the idea is presented: "
            "S4_STORY, S6_DO_TOGETHER or S7_SENSE_SWITCH. Make it easier and more visual. "
        ) + 'Set strategy to "re_explain" and next_expected_event to "voice_answer_requested". '

    return (
        opening
        + f"Attempt count on this question is {attempt}. "
        + rung
        + f"Set teaching_strategy to exactly one of: {allowed}. "
        + (
            f"Already spent on this question, do not reuse: {spent}. "
            if spent
            else "No strategy has been spent on this question yet. "
        )
        + "Read recent_answers and conversation for a pattern before choosing. If the child keeps confusing "
        "this concept with one particular other one, name that contrast rather than repeating a generic hint. "
        "Keep the diagnosis to yourself: choose the strategy it implies, and never put it in the message. "
        'Never say what the correct answer is, never say "wrong", and never count the items or give the total '
        "for a counting question. "
    )


def _help_instruction(payload: GuideRequest) -> str:
    """T7. The one genuinely open-ended task: the child's own words."""
    concept_strategies = '"S1_TELL" or "S2_SHOW"' if payload.experience_mode == "early" else '"S1_TELL" or "S3_EXAMPLE"'
    return (
        "feature is the child's own question or comment, word for word. Answer it directly and simply, using "
        "the recent conversation for context where it helps. If it is a real question about numbers, letters, "
        "colours, shapes, stories or the current activity, answer it in one or two short sentences. "
        "If it neither answers nor relates to the current question and is not a request for help, say gently "
        "that it does not answer this question yet, then restate the current question's hint or objective. "
        "Never say that you could not hear or understand clear speech - if it does not fit, say so in terms of "
        "the question, never in terms of the child's speech. If it is unrelated to learning altogether, redirect "
        "to numbers, letters, colours, shapes, stories or the app in one short sentence, without scolding. "
        "Never give away the answer to the current question, including as background information: telling a "
        "child that a circle has no corners while a round-versus-cornered question is open is leaking the "
        'answer. Set strategy to "help". Omit teaching_strategy, unless the child asked about the concept the '
        f"current question tests, in which case set it to {concept_strategies}. Set next_expected_event to "
        '"wait_for_child". '
    )


def _validate_model_response(payload: GuideRequest, raw_content: str) -> GuideResponse:
    try:
        decoded = json.loads(raw_content)
    except json.JSONDecodeError:
        return _fallback_guide(payload)

    # Provisional: every path below that hands the turn back to the
    # deterministic wording sets this back, either by calling `_fallback_guide`
    # or by saying so where it substitutes.
    _TURN_AUTHOR.set("agent")

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
            target_preferences = (
                ["activity-area", "answer-options"]
                if payload.experience_mode == "early"
                else ["counting-object-group", "question-area"]
            )
            return GuideResponse(
                message=message,
                strategy="help",
                teaching_strategy=_teaching_strategy_from(payload, decoded)
                or _deterministic_teaching_strategy(payload),
                avatar=_avatar(message, state="speaking", effect="pulse", speak=True),
                ui_action=_ui_action(payload, "highlight", target_preferences),
                visual_action=visual_action,
                next_expected_event="wait_for_child",
            )

    try:
        response = GuideResponse.model_validate(decoded)
    except ValidationError:
        return _fallback_guide(payload)

    response = response.model_copy(update={"teaching_strategy": _teaching_strategy_from(payload, decoded)})

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

    if _is_second_try_encouragement(payload):
        # The second try is encouragement by design, not teaching: nothing new
        # is said, so there is nothing of the model's to keep and no strategy
        # is spent, however the model tagged the turn.
        message = safe_text(_words(_pick_hint(1), 25))
        response = response.model_copy(
            update={
                "message": message,
                "strategy": "hint",
                "teaching_strategy": None,
                "avatar": response.avatar.model_copy(
                    update={"state": "encouraging", "message": message, "animationEffect": "gentle_hint"}
                ),
                "ui_action": _ui_action(payload, "show_hint", ["question-area", "voice-answer-area", "microphone-button"]),
                "visual_action": GuideVisualAction(),
                "next_expected_event": "voice_answer_requested",
            }
        )
    elif payload.event in REPAIR_EVENTS and payload.question:
        # GUIDE_HELP_REQUESTED cannot reach here - it returns from the dedicated
        # block at the top of this function - so this branch is the repair
        # ladder and nothing else.
        #
        # It used to overwrite the model's message on every repair turn at every
        # attempt, which meant T3, the one task whose whole argument is that the
        # wording should change with how the child got it wrong, paid for a Groq
        # call and threw the answer away. The failure it was guarding against is
        # real, so it is now checked for by name instead of by discarding
        # everything.
        deterministic_message, deterministic_visual, _ = _question_teaching_message(payload)
        if payload.allowed_visual_targets and (response.visual_action.type == "none" or not response.visual_action.targets):
            response = response.model_copy(update={"visual_action": deterministic_visual})

        offered = safe_text(_words(response.message, 25))
        if _model_message_is_usable(offered, response):
            response = response.model_copy(
                update={
                    "message": offered,
                    "avatar": response.avatar.model_copy(update={"message": offered}),
                }
            )
        else:
            message = safe_text(_words(deterministic_message, 25))
            response = response.model_copy(
                update={
                    "message": message,
                    # The deterministic wording replaced the model's, so the
                    # model's tag no longer describes what the child heard. The
                    # policy's own choice does: that is the strategy the
                    # deterministic branch was written under.
                    "teaching_strategy": _deterministic_strategy_for_substitution(payload),
                    "avatar": response.avatar.model_copy(update={"message": message}),
                }
            )

        if _ladder_attempt(payload) >= 4:
            # A parked question is not asked again, so the app must not sit
            # waiting for an answer to it.
            response = response.model_copy(update={"next_expected_event": "next_question_loaded"})

    message = safe_text(response.message)
    avatar_message = safe_text(response.avatar.message)
    if payload.experience_mode == "early":
        # `_early_mode_guide` caps a Play Group turn at 14 words, but it only
        # ever ran on the deterministic path - so with a live key, which is most
        # turns, a three-year-old got the same 25-word budget as a five-year-old
        # because the cap lived in the prompt and nowhere else. The illegal
        # strategies are already filtered: `_teaching_strategy_from` asks
        # `_allowed_teaching_strategies`, which is early-mode aware, and it runs
        # on this path too. The word cap was the half that was missing.
        message = _words(message, 14)
        avatar_message = _words(avatar_message, 14)
    return response.model_copy(
        update={
            "message": message,
            "avatar": response.avatar.model_copy(update={"message": avatar_message}),
        }
    )


def _model_guide(payload: GuideRequest) -> GuideResponse:
    """Ask the configured provider for the wording of this turn.

    The transport, the timeout, the key and the circuit breaker live in
    `app/ai/llm`; what is left here is what the guide actually knows about - the
    system prompt, the overlays that apply, and the fallback when no answer
    comes back.
    """
    # Only the overlays that apply. This used to send three system messages
    # every turn, two of them empty strings on any non-early English lesson.
    system = [CORE_SYSTEM_PROMPT]
    if payload.experience_mode == "early":
        system.append(EARLY_MODE_OVERLAY)
    # A Hindi lesson is still narrated in English; the overlay says how the
    # taught word is quoted. The language comes from the subject in the
    # manifest, not from anything the client sends.
    if _lesson_language(payload) == "hi":
        system.append(HINDI_LESSON_OVERLAY)

    try:
        content = chat(
            ChatRequest(
                system=system,
                user=[
                    _model_instruction(payload),
                    json.dumps(_payload_for_model(payload), ensure_ascii=True),
                ],
                temperature=0.4,
                max_tokens=300,
            )
        )
    except LLMUnavailable:
        return _fallback_guide(payload)

    return _validate_model_response(payload, content)


def guide(payload: GuideRequest) -> GuideResponse:
    validate_guide_request(payload)

    # One decision per turn, taken before anything is worded, so the wording,
    # the tag on the response and the episode written afterwards all describe
    # the same choice. Reading the policy is free of side effects; the episode
    # is written once, at the end, by `_spend_turn`.
    decision_token = _TURN_DECISION.set(_policy_decision(payload))
    author_token = _TURN_AUTHOR.set("deterministic")
    try:
        # Thirteen of the twenty-three events are canned copy over data the
        # server already has, and they take the deterministic path whatever the
        # provider setting says. There is no upside to asking a model to say
        # "well done" for an answer it was never shown, or to name the next
        # subject when `daily_recommendation_service` has already worked it out:
        # only latency, and one more turn an LLM failure can degrade a response
        # that was correct.
        if payload.event in DETERMINISTIC_EVENTS:
            response = _fallback_guide(payload)
        elif is_configured():
            response = _model_guide(payload)
        else:
            response = _fallback_guide(payload)

        _spend_turn(payload, response)
        return response
    finally:
        _TURN_DECISION.reset(decision_token)
        _TURN_AUTHOR.reset(author_token)
