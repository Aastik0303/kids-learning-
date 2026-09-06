"""The question a retention test asks: the same concept, a different question.

The test is not a re-run of the lesson. "Which letter does Apple start with?"
and "Which letter does Ant start with?" are two questions and one concept, and
only the second one is evidence that the letter was learned rather than the
sentence memorised. So this module's whole job is: given the concept and the
question it was *taught* with, hand back a different authored question about the
same concept.

Everything here comes out of `questions.py` - the syllabus a person wrote for
that class - and nothing is generated. That matters twice over:

* **the answer key is authored, so the judge stays deterministic.** What comes
  back goes into the server's own record of what the child is being asked and
  then into `stage.judge`, which is pure Python. No model is upstream of the
  verdict, and therefore none is upstream of the reward.
* **no model is asked to invent a question about a concept a two-year-old is
  learning.** The syllabus already has several, written for exactly that age.

The choice is deterministic: the pool is the authored order with choice
questions first, and the pick is the first entry that is not the taught one. The
same child, concept and teaching question produce the same retention question on
every worker and after every restart - which is what lets a test be scheduled on
Monday and asked on Wednesday without storing the question text anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.playground import questions


@dataclass(frozen=True)
class RetentionQuestion:
    """One authored question, ready to put in front of a child as a check-in."""

    activity_id: str
    question: str
    answer: str
    accept: tuple[str, ...] = ()
    options: tuple[str, ...] = ()

    @property
    def expects(self) -> str:
        """A question with buttons is tapped; one without is spoken.

        A tap question with no choices is a typing box in front of a child who
        cannot type, so the absence of options is what decides this rather than
        a flag somebody has to remember to set.
        """
        return "tap" if len(self.options) >= 2 else "voice"


# What is said before the question, so a check-in from two days ago does not
# arrive as a cold demand. Deterministic and short: the question is the thing
# the child has to hear, and it is said last.
LEAD_IN = "Before we start today, let us remember something we learned before."


def pick(topic_id: str, *, taught_ref: str = "") -> RetentionQuestion | None:
    """A question about this concept that is not the one it was taught with.

    Preference order, and each step is a fallback rather than a choice:

    1. an authored **choice** question whose activity is not `taught_ref` - a
       child of two can tap, and cannot always be understood by a recogniser;
    2. any authored question that is not `taught_ref`;
    3. the taught question itself, when the concept authored only one. Asking
       the same question again is weaker evidence, and it is priced as such:
       `retention.is_transfer` sees the same reference and the transfer bonus is
       not paid.

    None when the concept has no answerable authored question at all - a topic
    that is all tracing, or one whose activities have gone. The caller marks
    such a test `void` rather than leaving it at the head of the queue for ever.
    """
    pool = questions.for_topic(topic_id)
    if not pool:
        return None

    taught = (taught_ref or "").strip()
    fresh = [one for one in pool if one.activity_id != taught] if taught else list(pool)

    chosen = (
        next((one for one in fresh if one.is_choice), None)
        or next(iter(fresh), None)
        or next((one for one in pool if one.is_choice), None)
        or pool[0]
    )
    return RetentionQuestion(
        activity_id=chosen.activity_id,
        question=chosen.question,
        answer=chosen.answer,
        accept=tuple(chosen.accept),
        options=tuple(chosen.options),
    )


def speech(question: str) -> str:
    """The whole of what the check-in says: the lead-in, then the question.

    Deterministic on purpose. This turn spends no teaching strategy and writes
    no episode - it is being *tested*, not taught - so there is nothing for a
    model to phrase and nothing for the policy to choose.
    """
    text = (question or "").strip()
    return f"{LEAD_IN} {text}".strip()


__all__ = ["LEAD_IN", "RetentionQuestion", "pick", "speech"]
