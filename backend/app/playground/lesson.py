"""The order the AI Teacher teaches one thing in, and what happens to a question
the child cannot answer.

    explain -> say it -> draw it -> match it -> one more question

A bot that only asks questions is a quiz, not a teacher. This is the shape a
person uses: say what the thing is, hear it back, write it, then find it among
others, and only then ask about it cold. Each step is a different *kind* of
knowing the same concept, which is also why the order matters - a child who has
just been shown A can say it long before they can pick it out of four letters.

**Every question gets three turns, and the third one is not a test.**

1. the question, asked plainly;
2. the same question again with a **hint**, and the hint is *options* - two or
   three things to choose between, one of which is the answer - said after a
   longer, deeper explanation of the thing itself;
3. the **answer**, reached as a little story - somewhere the child has been,
   then the picture in front of them, and the name for it last of all - and
   then the class moves on.

Nobody is asked a third time and nobody is left stuck. A child who has missed
something twice has told you that asking again is not what they need; what they
need is to be shown the answer and told why it is the answer, which is what the
third turn is for. It is not marked, because there is nothing to mark - it is
teaching, and the question it settles counts as one of the stage's five either
way.

Two more rules hold the sequence together:

* **Not every step is a question.** Explaining is not a question, and a traced
  letter cannot be marked right or wrong; those steps move on when the child has
  done them, and they have no hint and no reveal.
* **The steps are skipped when they make no sense.** A colours topic has nothing
  to draw and nothing to say back; asking anyway would be the app talking to
  itself.
"""

from __future__ import annotations

from dataclasses import dataclass


EXPLAIN = "explain"
SAY_IT = "say_it"
DRAW = "draw"
MATCH = "match"
QUIZ = "quiz"

SEQUENCE: tuple[str, ...] = (EXPLAIN, SAY_IT, DRAW, MATCH, QUIZ)

# How many times one question is *asked*. Two: once plainly, and once with a
# hint and a deeper telling. A second miss is answered rather than asked again.
TRIES_PER_QUESTION = 2

# Which of those tries carries the hint. Zero is the plain asking, so the hint
# is the second one - and it is the last one, because `TRIES_PER_QUESTION` is 2.
HINT_AT_TRY = 1

# The steps that ask for something and can therefore be got wrong.
SCORED_STEPS = (SAY_IT, MATCH, QUIZ)

# ...and, of those, the ones whose answer may never move the level's score.
#
# The echo is taught, repaired and revealed like any other step - a child who
# cannot say "A" is shown it again - but nothing about it is written to the
# attempt log and nothing about it reaches a star. Speech-to-text on a
# three-year-old mishears constantly, and a level that failed because a
# microphone did not catch a small voice is the app marking its own hardware.
# `app/conductor/echo.py` has always kept this rule; this is the same rule in
# the AI Teacher, which is the class that actually pays stars.
UNMARKED_STEPS = (SAY_IT,)

# What the client is asked to collect for each step.
EXPECTS = {
    EXPLAIN: "ready",
    SAY_IT: "voice",
    DRAW: "trace",
    MATCH: "tap",
    QUIZ: "tap",
}

# Which passages of the syllabus each step should be taught from.
RETRIEVAL_KINDS: dict[str, tuple[str, ...]] = {
    EXPLAIN: ("overview", "teach"),
    SAY_IT: ("teach", "overview"),
    DRAW: ("draw", "teach"),
    MATCH: ("match", "count", "teach"),
    QUIZ: ("quiz", "match", "count", "teach"),
}

# What the guide is doing in each step, said to the model in one line.
BRIEFS = {
    EXPLAIN: (
        "Teach this thing properly, in three or four short sentences: what it is, "
        "the same thing said again in different words, one everyday example the "
        "child has seen for themselves, and what to look at in the picture. "
        "Do not ask a question yet - this turn is the explanation."
    ),
    SAY_IT: "Ask the child to say the thing out loud, by itself. One word is a whole answer here.",
    DRAW: "Ask the child to draw the thing with their finger. Say where to start and which way to move.",
    MATCH: "Ask the child to pick it out from two or three choices.",
    QUIZ: "Ask one more question about it, in a way you have not asked yet.",
}

# The two turns that are not a fresh question: the same one again with help, and
# the one that simply gives the answer. Both are given the question and the
# answer that are already in play, so neither invents a new one.
HINT_BRIEF = (
    "The child did not get this one. Do not ask anything new and do not repeat "
    "the question - it is still on the screen. Teach **the same thing** again "
    "properly and more deeply than you did the first time: four or five short "
    "sentences saying what it is, what makes it different from the other "
    "choices, and two everyday examples the child has seen for themselves. "
    "Then finish with one clue that points at the answer - what it looks like, "
    "what it starts with, where they have seen it - without ever saying the "
    "answer itself. The choices on the screen are the rest of the hint. "
    "Say what tells the answer apart - 'this one has three corners, not none' - "
    "and never turn the turn into a lesson about one of the other choices: a "
    "child who got the triangle wrong needs the triangle again, not the circle."
)

# The third turn: the one that settles a question nobody got. It is a **story**,
# and the answer is the end of it rather than the beginning.
#
# It used to open with "The answer is triangle" and explain afterwards, and a
# child who has just been handed the answer has no reason left to listen to the
# why. Told the other way round the same words become a small thing to follow:
# somewhere they have been, then the picture in front of them, and only then the
# name for it - which is the shape a person uses when they explain something to
# a small child, and the reason the child is still there at the end of it.
REVEAL_BRIEF = (
    "The child has tried this twice and it has not come. Do not ask anything and "
    "do not hint. This turn is a little story in three beats, and the answer is "
    "the last thing in it - never the first. "
    "1. A real moment out of the child's own day where this thing turns up. Two "
    "or three short sentences, told as a scene they can picture - the samosa on "
    "the plate, the wheel on the toy car, the window in the kitchen. Do not name "
    "the answer here. "
    "2. Send them to the picture beside you and say what to look at in it - one "
    "or two sentences. Have them count it, or trace it with a finger. "
    "3. Only now, in the very last sentence, tell them warmly what it is called. "
    "Nothing comes after that except moving on to the next thing, kindly."
)


@dataclass(frozen=True)
class Step:
    """Where the lesson is, and what the client should collect.

    `tries` is how many times the question in front of the child has been asked.
    Zero is the plain asking, `HINT_AT_TRY` is the asking that carries the hint,
    and `TRIES_PER_QUESTION` is not an asking at all - it is the turn that gives
    the answer away on purpose.
    """

    name: str
    index: int
    tries: int = 0

    @property
    def asks_a_question(self) -> bool:
        """Whether this step is the kind that has an answer at all."""
        return self.name in SCORED_STEPS

    @property
    def is_reveal(self) -> bool:
        """This turn tells the child the answer and moves on. Nothing is marked."""
        return self.asks_a_question and self.tries >= TRIES_PER_QUESTION

    @property
    def is_hint(self) -> bool:
        """The second asking: a deeper explanation, a clue, and options to choose from."""
        return self.asks_a_question and HINT_AT_TRY <= self.tries < TRIES_PER_QUESTION

    @property
    def expects(self) -> str:
        # The reveal has nothing to collect but the child's attention, and the
        # hint is answered by tapping one of the choices it came with.
        if self.is_reveal:
            return "ready"
        if self.is_hint:
            return "tap"
        return EXPECTS.get(self.name, "tap")

    @property
    def is_scored(self) -> bool:
        return self.asks_a_question and not self.is_reveal

    @property
    def is_marked(self) -> bool:
        """Whether what happens on this step may move the level's score.

        Not the same question as `is_scored`. A reveal is not scored - there is
        nothing to mark on a turn that hands the answer over - and it still
        counts against the level, because a question the teacher had to answer
        is a question that did not land. An echo is the other way round: it is
        asked and it is repaired, and none of it is ever counted.
        """
        return self.asks_a_question and self.name not in UNMARKED_STEPS

    @property
    def retrieval_kinds(self) -> tuple[str, ...]:
        return RETRIEVAL_KINDS.get(self.name, ())

    @property
    def brief(self) -> str:
        if self.is_reveal:
            return REVEAL_BRIEF
        if self.is_hint:
            return HINT_BRIEF
        return BRIEFS.get(self.name, "")


def sequence_for(*, can_say: bool, can_draw: bool) -> tuple[str, ...]:
    """The steps this concept actually has.

    `can_say` is for the things that *are* a sound - a letter, a number - and
    `can_draw` for the ones with a shape to trace. A colour has neither, and a
    lesson that asked a child to draw "red" would be the app talking to itself.
    """
    steps = [EXPLAIN]
    if can_say:
        steps.append(SAY_IT)
    if can_draw:
        steps.append(DRAW)
    steps.extend((MATCH, QUIZ))
    return tuple(steps)


def current(steps: tuple[str, ...], index: int, tries: int = 0) -> Step:
    position = max(0, min(index, len(steps) - 1))
    return Step(name=steps[position], index=position, tries=tries)


def after_answer(steps: tuple[str, ...], step: Step, *, is_correct: bool) -> Step:
    """Where the lesson goes next.

    Right, or a step that is not a question: on to the next kind of knowing it.
    Wrong the first time: the same question again, with the hint. Wrong the
    second time: the turn that gives the answer - which stays on the same step,
    because it is still about this question, and is followed by `advance`.
    """
    if is_correct or not step.is_scored:
        return advance(steps, step)
    return Step(name=step.name, index=step.index, tries=step.tries + 1)


def advance(steps: tuple[str, ...], step: Step) -> Step:
    """The next step, wrapping round to the first when the lesson is through."""
    following = step.index + 1
    if following >= len(steps):
        # Round again on the same concept: the sitting ends on the stage's five
        # questions, not on running out of steps.
        return Step(name=steps[0], index=0, tries=0)
    return Step(name=steps[following], index=following, tries=0)


__all__ = [
    "BRIEFS",
    "DRAW",
    "EXPECTS",
    "EXPLAIN",
    "HINT_AT_TRY",
    "HINT_BRIEF",
    "MATCH",
    "QUIZ",
    "REVEAL_BRIEF",
    "SAY_IT",
    "SCORED_STEPS",
    "SEQUENCE",
    "TRIES_PER_QUESTION",
    "UNMARKED_STEPS",
    "Step",
    "advance",
    "after_answer",
    "current",
    "sequence_for",
]
