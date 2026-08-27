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
    """
    text = (answer or "").strip().lower()
    text = re.sub(r"[^\w\sऀ-ॿ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _candidates(answer: str) -> set[str]:
    """Every form of the answer worth comparing: the whole thing and its words."""
    text = normalise(answer)
    if not text:
        return set()
    forms = {text}
    for word in text.split():
        forms.add(word)
        if word in _NUMBER_WORDS:
            forms.add(_NUMBER_WORDS[word])
    return forms


def judge(*, said: str, expected: str, accept: list[str] | None = None) -> Verdict:
    """Right or wrong, decided here and nowhere else.

    Generous about how it was said and strict about what was said: the accepted
    answers are the authored ones plus the number words a child uses for them,
    and nothing else counts.
    """
    spoken = _candidates(said)
    wanted: set[str] = set()
    for value in [expected, *(accept or [])]:
        wanted |= _candidates(value)

    if not spoken or not wanted:
        return Verdict(is_correct=False, normalised=normalise(said))

    return Verdict(is_correct=bool(spoken & wanted), normalised=normalise(said))


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
    "judge",
    "normalise",
    "settle",
]
