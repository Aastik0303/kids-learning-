"""Stage 1 of the child speech pipeline.

These tests exist because a two to six year old saying the right answer is the
case most likely to be scored wrong. "tree" is three, "teen" is three, and
"do nahi teen" is a child correcting themselves to three. Every one of those
used to reach the evaluator as a word it had never heard of.

The last group is the important one: the cleaner is never told the correct
answer, and these tests prove it cannot be made to find it.
"""

import pytest

from app.services.answer_resolution_service import (
    AnswerResolutionContext,
    resolve_answer,
    resolved_answers_match,
)
from app.services.child_speech_service import clean_child_speech


# ─── Stage 1: deterministic clean ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("tree", "3"),
        ("free", "3"),
        ("aiph", "5"),
        ("wan", "1"),
    ],
)
def test_english_mispronunciation_maps_to_the_number(transcript: str, expected: str) -> None:
    result = clean_child_speech(transcript, "count_objects", ["2", "3", "5", "1"])
    assert result.token == expected
    assert result.status == "resolved"


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("teen", "3"),
        ("tin", "3"),
        ("paanch", "5"),
        ("ek", "1"),
    ],
)
def test_hindi_numbers_map_to_digits(transcript: str, expected: str) -> None:
    result = clean_child_speech(transcript, "count_objects", ["1", "3", "5"])
    assert result.token == expected


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("laal", "red"),
        ("neela", "blue"),
        ("hara", "green"),
        ("wed", "red"),
        ("bloo", "blue"),
    ],
)
def test_colours_map_across_both_languages(transcript: str, expected: str) -> None:
    result = clean_child_speech(transcript, "identify_colour", ["red", "blue", "green"])
    assert result.token == expected
    assert result.status == "resolved"


@pytest.mark.parametrize(
    ("transcript", "expected"),
    [
        ("gol", "circle"),
        ("sarkal", "circle"),
        ("tikona", "triangle"),
        ("chakor", "square"),
    ],
)
def test_shapes_map_across_both_languages(transcript: str, expected: str) -> None:
    result = clean_child_speech(transcript, "identify_shape", ["circle", "square", "triangle"])
    assert result.token == expected


def test_self_correction_keeps_the_word_after_the_marker() -> None:
    """"do nahi teen" is a child saying two, then correcting to three."""
    result = clean_child_speech("do nahi teen", "count_objects", ["2", "3", "4"])
    assert result.token == "3"
    assert result.self_corrected is True


def test_trailing_correction_marker_keeps_what_came_before() -> None:
    """"teen nahi" is a child trailing off, not correcting to nothing."""
    result = clean_child_speech("teen nahi", "count_objects", ["2", "3", "4"])
    assert result.token == "3"


def test_no_is_an_answer_when_it_is_on_the_screen() -> None:
    """"no" is a correction marker everywhere except a yes/no question."""
    result = clean_child_speech("no", "multiple_choice", ["yes", "no"])
    assert result.token == "no"
    assert result.self_corrected is False


def test_counting_out_loud_answers_with_the_final_number() -> None:
    """A child counting the mangoes lands on the answer; they do not start on it."""
    result = clean_child_speech("ek do teen", "count_objects", ["1", "2", "3"])
    assert result.token == "3"
    assert result.reason_code == "counted_aloud_final"


def test_fillers_are_dropped_around_the_real_word() -> None:
    result = clean_child_speech("umm blue", "identify_colour", ["red", "blue", "green"])
    assert result.token == "blue"
    assert result.confidence == 1.0


def test_padding_around_a_visible_option_still_resolves() -> None:
    result = clean_child_speech("the blue one", "identify_colour", ["red", "blue", "green"])
    assert result.token == "blue"


def test_repetition_is_emphasis_not_two_answers() -> None:
    result = clean_child_speech("blue blue", "identify_colour", ["red", "blue", "green"])
    assert result.token == "blue"


# ─── Confidence bands ────────────────────────────────────────────────────────


def test_silence_is_empty_and_asks_for_a_retry() -> None:
    """An empty transcript is a child thinking, never a wrong answer."""
    result = clean_child_speech("", "count_objects", ["1", "2", "3"])
    assert result.status == "empty"
    assert result.confidence == 0.0
    assert result.retry_suggested is True
    assert result.needs_enhancement is False


def test_an_option_said_plainly_is_certain() -> None:
    result = clean_child_speech("blue", "identify_colour", ["red", "blue", "green"])
    assert result.confidence == 1.0
    assert result.status == "resolved"
    assert result.needs_enhancement is False


def test_a_phonetic_match_clears_the_confident_band() -> None:
    """0.85 is above the 0.80 line, so no enhancer would be called for "tree"."""
    result = clean_child_speech("tree", "count_objects", [])
    assert result.confidence == pytest.approx(0.85)
    assert result.status == "resolved"


def test_a_vague_answer_lands_in_the_enhancement_band() -> None:
    """"wo wala" points at something without naming it — Stage 1 cannot settle it."""
    result = clean_child_speech("umm wo wala", "identify_colour", ["red", "blue", "green"])
    assert result.status == "needs_enhancement"
    assert result.needs_enhancement is True
    assert result.retry_suggested is False


def test_a_long_ramble_scores_at_the_bottom_of_the_enhancement_band() -> None:
    """A rambling child still said something, so Stage 1 hands it on rather than
    guessing. Only silence falls below the band and is asked for again."""
    result = clean_child_speech(
        "mummy ne kaha tha ki wo cheez waha rakhi hai",
        "identify_colour",
        ["red", "blue", "green"],
    )
    assert result.confidence == pytest.approx(0.30)
    assert result.status == "needs_enhancement"


# ─── The cleaner must not be able to grade ───────────────────────────────────


def test_the_correct_answer_is_not_an_input_to_the_cleaner() -> None:
    """`clean_child_speech` takes visible options only — there is no way to leak."""
    from inspect import signature

    assert "correct_answer" not in signature(clean_child_speech).parameters


def test_a_clearly_wrong_answer_scores_as_high_as_a_right_one() -> None:
    """Confidence measures what was said, not whether it was right.

    If a wrong answer scored lower it would be quietly retried while a right one
    was accepted, which is grading by the back door.
    """
    correct = clean_child_speech("teen", "count_objects", ["1", "2", "3"])
    wrong = clean_child_speech("ek", "count_objects", ["1", "2", "3"])
    assert correct.confidence == wrong.confidence
    assert wrong.token == "1"


def test_an_answer_already_tried_and_wrong_is_returned_again() -> None:
    """Repeating a wrong answer is real data about the child, not noise to fix."""
    result = clean_child_speech("laal", "identify_colour", ["red", "blue", "green"])
    assert result.token == "red"


def test_hidden_correct_answer_does_not_pull_a_vague_transcript() -> None:
    context = AnswerResolutionContext(
        transcript="umm wo wala",
        confidence=0.5,
        answer_type="identify_colour",
        correct_answer="green",
        options=["red", "blue", "green"],
    )
    result = resolve_answer(context)
    assert result.resolved_answer != "green"


# ─── Wired into answer resolution ────────────────────────────────────────────


def test_hindi_answer_reaches_the_evaluator_as_correct() -> None:
    is_correct, result = resolved_answers_match(
        AnswerResolutionContext(
            transcript="teen",
            confidence=0.6,
            answer_type="count_objects",
            correct_answer="3",
            options=["1", "2", "3"],
        )
    )
    assert is_correct is True
    assert result.resolved_answer == "3"


def test_self_corrected_answer_reaches_the_evaluator_as_correct() -> None:
    is_correct, _ = resolved_answers_match(
        AnswerResolutionContext(
            transcript="do nahi teen",
            confidence=0.6,
            answer_type="count_objects",
            correct_answer="3",
            options=["2", "3", "4"],
        )
    )
    assert is_correct is True


def test_hindi_shape_answer_reaches_the_evaluator_as_correct() -> None:
    is_correct, _ = resolved_answers_match(
        AnswerResolutionContext(
            transcript="gol",
            confidence=0.6,
            answer_type="identify_shape",
            correct_answer="circle",
            options=["circle", "square", "triangle"],
        )
    )
    assert is_correct is True


def test_a_hindi_wrong_answer_is_still_wrong() -> None:
    """The rescue must resolve the transcript, not rescue the child's score."""
    is_correct, result = resolved_answers_match(
        AnswerResolutionContext(
            transcript="do",
            confidence=0.6,
            answer_type="count_objects",
            correct_answer="3",
            options=["1", "2", "3"],
        )
    )
    assert is_correct is False
    assert result.resolved_answer == "2"


def test_the_raw_transcript_survives_the_rescue() -> None:
    """A parent log and the guide agent both need what the child actually said."""
    result = resolve_answer(
        AnswerResolutionContext(
            transcript="do nahi teen",
            confidence=0.6,
            answer_type="count_objects",
            correct_answer="3",
            options=["2", "3", "4"],
        )
    )
    assert result.raw_transcript == "do nahi teen"
    assert result.child_speech is not None
    assert result.child_speech.self_corrected is True


def test_a_tapped_option_skips_the_pipeline_untouched() -> None:
    result = resolve_answer(
        AnswerResolutionContext(
            transcript="blue",
            confidence=1.0,
            answer_type="identify_colour",
            correct_answer="blue",
            options=["red", "blue", "green"],
        )
    )
    assert result.input_kind == "answer"
    assert result.resolved_answer == "blue"
