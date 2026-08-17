"""Deterministic evaluators for every activity type the curriculum may reference.

An activity type is only usable if it is registered here. The curriculum loader
rejects any activity file that names an unregistered type, so a typo in authored
content fails at startup rather than in front of a child.

No LLM is involved in deciding correctness. Evaluators are pure functions.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.services.answer_normalization_service import answers_match, normalize_answer
from app.services.answer_resolution_service import AnswerResolutionContext, resolved_answers_match

# An evaluator takes the activity's answer key plus the child's raw answer and
# returns (is_correct, normalized_answer).
Evaluator = Callable[["EvaluationInput"], tuple[bool, str]]


@dataclass(frozen=True)
class EvaluationInput:
    activity_type: str
    correct_answer: str
    options: list[str]
    answer: str
    confidence: float = 0.9
    # Extra spellings an authored activity is willing to accept, e.g. a letter
    # sound written as "a", "aa" or "ah".
    accepted_answers: tuple[str, ...] = ()
    # "Tell me your name" has no single right answer. Any real attempt counts.
    open_ended: bool = False


def _choice_evaluator(payload: EvaluationInput) -> tuple[bool, str]:
    """Closed-set match: the answer must resolve to one of the offered options."""
    is_correct, resolved = resolved_answers_match(
        AnswerResolutionContext(
            transcript=payload.answer,
            confidence=payload.confidence,
            answer_type=payload.activity_type,
            correct_answer=payload.correct_answer,
            accepted_answers=[payload.correct_answer, *payload.accepted_answers],
            options=payload.options,
        )
    )
    return is_correct, resolved.normalized


def _multi_choice_evaluator(payload: EvaluationInput) -> tuple[bool, str]:
    """A match activity whose answer is a set, written comma-separated.

    "Put the red things together" has two right answers out of three options, so
    a single-value compare would mark a correct child wrong. Order does not
    matter; the child's picks are compared as a set.
    """
    if "," not in payload.correct_answer:
        return _choice_evaluator(payload)

    expected = {part.strip().lower() for part in payload.correct_answer.split(",") if part.strip()}
    given = {part.strip().lower() for part in payload.answer.split(",") if part.strip()}
    return given == expected, ",".join(sorted(given))


def _spoken_evaluator(payload: EvaluationInput) -> tuple[bool, str]:
    """Say-it-back activities: an empty answer is not correct, but any real
    attempt at an open-ended prompt is.

    Every spelling in the activity's `accept` list is a right answer in its own
    right, not merely a hint for resolving the transcript. A letter sound
    authored as "a" with accept ["aa", "ay", "ah"] must mark "ah" correct.
    """
    spoken = payload.answer.strip()
    if not spoken:
        return False, ""
    if payload.open_ended or not payload.correct_answer:
        return True, spoken

    for candidate in (payload.correct_answer, *payload.accepted_answers):
        if candidate and answers_match(spoken, candidate, payload.activity_type):
            return True, normalize_answer(spoken, payload.activity_type)
    return _choice_evaluator(payload)


def _presentational_evaluator(payload: EvaluationInput) -> tuple[bool, str]:
    """Watch/listen/draw activities carry no right answer. Taking part completes them."""
    return True, payload.answer.strip()


# type -> evaluator. Adding a new activity type is a one-line change here plus the
# authored content; nothing else in the codebase needs to know about it.
EVALUATORS: dict[str, Evaluator] = {
    # closed-set choice
    "match": _multi_choice_evaluator,
    "multiple_choice": _choice_evaluator,
    "mixed": _choice_evaluator,
    "select_letter": _choice_evaluator,
    "select_number": _choice_evaluator,
    "select_shape": _choice_evaluator,
    "select_colour": _choice_evaluator,
    "identify_letter": _choice_evaluator,
    "identify_number": _choice_evaluator,
    "identify_colour": _choice_evaluator,
    "identify_shape": _choice_evaluator,
    "recognize_colour": _choice_evaluator,
    "recognize_shape": _choice_evaluator,
    "count_objects": _choice_evaluator,
    "compare_groups": _choice_evaluator,
    "sort_by_attribute": _choice_evaluator,
    "position_choice": _choice_evaluator,
    "sequence_next": _choice_evaluator,
    # spoken back
    "voice_repeat": _spoken_evaluator,
    "repeat_letter": _spoken_evaluator,
    "repeat_number": _spoken_evaluator,
    "repeat_colour": _spoken_evaluator,
    "repeat_shape": _spoken_evaluator,
    "repeat_word": _spoken_evaluator,
    "name_object": _spoken_evaluator,
    # presentational / motor
    "introduce": _presentational_evaluator,
    "introduce_letter": _presentational_evaluator,
    "introduce_number": _presentational_evaluator,
    "introduce_colour": _presentational_evaluator,
    "introduce_shape": _presentational_evaluator,
    "introduce_topic": _presentational_evaluator,
    "story_listen": _presentational_evaluator,
    "rhyme_listen": _presentational_evaluator,
    "trace": _presentational_evaluator,
    "free_draw": _presentational_evaluator,
    "action_song": _presentational_evaluator,
    # Physical-world learning. A screen cannot teach ball-catching, so the app
    # shows the parent an activity card and records completion rather than
    # faking a tap question for it.
    "parent_activity": _presentational_evaluator,
}


def answer_kind(activity_type: str) -> str:
    """How an activity is answered, which decides what the loader may demand of it.

    - "choice": a closed set of options; the correct answer must be one of them.
    - "spoken": said aloud; no options, and the answer may be open-ended.
    - "presentational": watched, listened to, traced or done off-screen. There is
      no right answer, so taking part completes it.
    """
    evaluator = EVALUATORS.get(activity_type)
    if evaluator is _presentational_evaluator:
        return "presentational"
    if evaluator is _spoken_evaluator:
        return "spoken"
    return "choice"


def is_registered(activity_type: str) -> bool:
    return activity_type in EVALUATORS


def registered_types() -> list[str]:
    return sorted(EVALUATORS)


def evaluate(payload: EvaluationInput) -> tuple[bool, str]:
    evaluator = EVALUATORS.get(payload.activity_type)
    if evaluator is None:
        # Unreachable for loaded curriculum: the loader rejects unknown types at
        # startup. Kept as a guard so a bad direct call fails loudly.
        raise KeyError(f"No evaluator registered for activity type '{payload.activity_type}'")
    return evaluator(payload)


def requires_answer(activity_type: str) -> bool:
    return EVALUATORS.get(activity_type) is not _presentational_evaluator
