"""What counts as right, and how long a stage lasts.

Pure Python, and that is the whole point of the file existing. The AI Teacher is
an agent that retrieves, explains and asks - and it does not decide whether the
child was right, because a bot that both sets the question and marks it learns
very quickly that the easiest way to be marked well is to give the answer away.
The same rule the class runs on holds here.

**There are no points.** There used to be: +2 for a right answer, -1 for a wrong
one, ten to finish a stage. A number that goes up when a four-year-old is right
and down when they are not is a scoreboard, and a scoreboard beside a child who
is still learning what a letter *is* teaches them to mind the number. What is
left is the shape of the lesson itself:

* **a stage is five questions**, and then it is over;
* each of those five is asked, hinted, and finally answered for the child - see
  `lesson.py`, which owns that part - and only a question that has been *settled*
  one way or the other counts towards the five;
* whether the level passed is worked out at the end from how many of the five
  landed, by the same deterministic scorer the conductor uses, and by nothing
  else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Five questions to a stage, and a stage is one level out of today's plan. This
# is the only counter the child's lesson has now, and it only ever goes up.
QUESTIONS_PER_STAGE = 5

# Number words a child says instead of the digit, and the digit they mean.
_NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "to": "2",
    "too": "2",
    "three": "3",
    "tree": "3",
    "four": "4",
    "for": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "ate": "8",
    "nine": "9",
    "ten": "10",
}


# Signs the syllabus uses as answers or choices, and the word each one reads as.
_SIGN_WORDS = {
    "=": "equal",
    ">": "greater",
    "<": "less",
    "+": "plus",
    "-": "minus",
    "?": "question",
}
_STANDALONE_SIGN = re.compile(r"(?<!\S)([=<>+\-?])(?!\S)")

# What a child says for one of those signs, read as the same word.
_SIGN_SYNONYMS = {
    "equals": "equal",
    "same": "equal",
    "bigger": "greater",
    "smaller": "less",
    "lesser": "less",
}


@dataclass(frozen=True)
class Verdict:
    """What one answer came to. Never written by a model."""

    is_correct: bool
    normalised: str


@dataclass(frozen=True)
class Progress:
    """Where the stage is, after one question has been settled."""

    stage: int
    questions_asked: int
    stage_complete: bool


def normalise(answer: str) -> str:
    """What the child said, in the one shape everything else compares.

    Speech comes back as "the letter A", "it's three", "पहला अ" - the words
    around the answer are not the answer, and a child who says the right thing
    inside a sentence has said the right thing.

    The underscore is treated as a space, because the syllabus writes its answers
    as tokens - `standing_line`, `sleeping_line` - and what the child taps is the
    same thing written for a person to read. "standing line" and "standing_line"
    are one answer, and marking them as two was marking a right answer wrong.
    """
    text = (answer or "").strip().lower()
    # A sign standing on its own is a word: the maths levels ask for "=", ">"
    # and "<", and stripping punctuation turned each of them into nothing - so
    # no option could be the answer and tapping the right sign was marked wrong.
    text = _STANDALONE_SIGN.sub(lambda match: f" {_SIGN_WORDS[match.group(1)]} ", text)
    text = re.sub(r"[^\w\sऀ-ॿ]", " ", text)
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def contains_answer(option: str, answer: str) -> bool:
    """Whether this choice *is* the answer, written out for a child to read.

    An option carries the answer plus decoration - "red apple 🍎" for "red",
    "3 things 🍎🍎🍎" for "3" - so the test cannot be equality. It is whole-word
    containment rather than plain substring, and the difference matters: "a" is a
    substring of "banana", so the loose test would happily put "banana" on the
    screen as the answer to a question about the letter A and then mark it wrong
    when the child tapped it.

    **This is the one rule.** The same function decides which options may be
    shown and whether a tapped option was right, because when those two
    disagree a child can tap the answer that was put in front of them and be
    told they are wrong. That is what was happening.
    """
    wanted = normalise(answer)
    text = normalise(option)
    if not wanted or not text:
        return False
    if wanted == text:
        return True
    return f" {wanted} " in f" {text} "


# Words that carry no meaning of their own in a short answer. "a balloon" and
# "a kite" share the "a", and a child who said "a kite" has not said the balloon.
_FILLER_WORDS = frozenset(
    {"a", "an", "the", "is", "are", "am", "i", "it", "its", "on", "in", "at", "of",
     "to", "and", "you", "he", "she", "they", "we", "this", "that", "my", "s"}
)


def _words(text: str) -> list[str]:
    """Normalised words, with the number words a child says turned into digits.

    Both sides go through this, so "three" and "3", "coin one" and `coin_1`, or
    "equals" and "=", are the same words.
    """
    return [_spoken_form(word) for word in normalise(text).split()]


def _content_words(text: str) -> set[str]:
    """The words of an answer that actually say something, filler dropped first."""
    return {_spoken_form(word) for word in normalise(text).split() if word not in _FILLER_WORDS}


def _spoken_form(word: str) -> str:
    return _NUMBER_WORDS.get(word) or _SIGN_SYNONYMS.get(word) or word


def _contains_phrase(spoken: list[str], key: list[str]) -> bool:
    if not key:
        return False
    return f" {' '.join(key)} " in f" {' '.join(spoken)} "


def judge(
    *,
    said: str,
    expected: str,
    accept: list[str] | None = None,
    offered: list[str] | tuple[str, ...] | None = None,
) -> Verdict:
    """Right or wrong, decided here and nowhere else.

    Generous about how it was said and strict about what was said: the accepted
    answers are the authored ones plus the number words a child uses for them,
    and nothing else counts.

    `offered` is what was on the screen. When the child **tapped** one of those
    choices, that tap is marked by asking whether the choice they touched is the
    one the options were built around - `contains_answer`, the same question that
    put it there. Word-matching a tapped label against the answer is the wrong
    tool for it: the label is the answer dressed up for a child to read, and
    "standing line ⬇️" against `standing_line`, or "3 apples 🍎" against `3`,
    came apart often enough that a child tapping the right box was told they
    were wrong. That was the bug, and it is why this branch exists.

    Speech and typing fall through to the word matching below, where they belong.
    """
    tapped = _tapped(said, offered)
    if tapped is not None:
        keys = [value for value in (expected, *(accept or [])) if value]
        return Verdict(
            is_correct=any(contains_answer(tapped, value) for value in keys),
            normalised=normalise(said),
        )

    keys = [value for value in (expected, *(accept or [])) if normalise(value)]
    spoken = _words(said)
    if not spoken or not keys:
        return Verdict(is_correct=False, normalised=normalise(said))

    return Verdict(is_correct=_said_the_answer(spoken, keys, offered), normalised=normalise(said))


def _said_the_answer(
    spoken: list[str], keys: list[str], offered: list[str] | tuple[str, ...] | None
) -> bool:
    """Whether a spoken or typed answer says one of the keys.

    The whole answer said inside a sentence is right - "i think it is a circle".
    A *part* of a multi-word answer is right only when that part is what tells
    it apart: with "big ball" and "small ball" on the screen, "big" is the
    answer and "ball" is not, because "ball" is just as much the wrong one.
    Matching any shared word used to mark "small ball", "coin 5" and "a kite"
    right for "big ball", "coin 1" and "a balloon".

    With no choices on the screen there is nothing to tell the answer apart
    from, so every word that carries meaning has to be there ("fine" for
    "i am fine").
    """
    heard = set(spoken)
    wrong_options = [
        str(option)
        for option in (offered or [])
        if not any(contains_answer(str(option), key) for key in keys)
    ]
    wrong_words: set[str] = set()
    for option in wrong_options:
        wrong_words |= _content_words(option)

    for key in keys:
        if _contains_phrase(spoken, _words(key)):
            return True

        content = _content_words(key)
        if not content:
            continue
        if not wrong_options:
            if content <= heard:
                return True
            continue

        telling = content - wrong_words
        misleading = wrong_words - content
        if telling and heard & telling and not heard & misleading:
            return True
    return False


def _tapped(said: str, offered: list[str] | tuple[str, ...] | None) -> str | None:
    """The choice the child touched, or None when this was not a tap.

    Matched on the normalised label, so the emoji and the punctuation the option
    is decorated with do not have to survive the round trip to the browser and
    back.
    """
    spoken = normalise(said)
    if not spoken or not offered:
        return None
    for option in offered:
        if normalise(str(option)) == spoken:
            return str(option)
    return None


def settle(*, stage: int, questions_asked: int) -> Progress:
    """One of the five questions is finished with. Move the lesson on.

    Called once per *question*, not once per answer: a question the child got
    wrong and was then given a hint for is still one question, and the three
    turns it took are three tries at the same one.
    """
    next_asked = questions_asked + 1
    complete = next_asked >= QUESTIONS_PER_STAGE
    return Progress(
        stage=stage + 1 if complete else stage,
        # A finished stage starts the next one from nothing; there is no half a
        # question to carry over.
        questions_asked=0 if complete else next_asked,
        stage_complete=complete,
    )


__all__ = [
    "QUESTIONS_PER_STAGE",
    "Progress",
    "Verdict",
    "contains_answer",
    "judge",
    "normalise",
    "settle",
]
