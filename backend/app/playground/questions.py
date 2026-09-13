"""The questions a person already wrote for this class, asked as they were written.

A two-year-old was being asked "Can you show me pre-writing strokes?" - the
topic's own syllabus title bent into a question. A title is written for a
grown-up reading a curriculum; it is not a thing a two-year-old can be asked to
show anybody. Meanwhile the same topic in `data/curriculum/activities/` already
holds "Which one is the standing line? ⬇️" with two choices and their emoji,
written by a person for children of exactly that age.

So the teaching turn asks the author's question. This module is the bridge:
it reads the authored activities for a topic and hands back a question, its
answer, the accepted spellings and the choices, all as plain Python.

**Why this does not weaken the answer-key rule.** Nothing here reaches a model.
`rag.py` deliberately keeps `correct_answer`, `accept` and `options` out of the
retrieval index because everything in that index is pasted into a prompt; what
this module produces goes the other way, into the server's own record of what
the child is being asked, and into `stage.judge`, which is pure Python. The
model still writes the *explanation* around the question and never sees the key.

**Why the tokens are rewritten.** The syllabus writes an answer as an identifier
- `standing_line`, `sleeping_line` - because it is also a key into the art. A
child reads "standing line". Both spellings are accepted, and `stage.normalise`
treats the underscore as a space so they are the same answer either way.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache

from app.services import curriculum_service
from app.services import cache


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Authored:
    """One question out of the syllabus, ready to put in front of a child."""

    activity_id: str
    skill_id: str
    question: str
    answer: str
    accept: tuple[str, ...] = ()
    options: tuple[str, ...] = ()
    hint: str = ""
    # What the author's own visual_items named, so the picture beside the
    # question can be the one they meant rather than one read out of the words.
    visual_items: tuple[str, ...] = field(default=())

    @property
    def is_choice(self) -> bool:
        return len(self.options) >= 2


# An identifier the author uses as a key into the art - "standing_line",
# "big_circle". Anything with an underscore or a run of them is written for the
# machine; what a child reads is the same words with spaces.
def label(token: str) -> str:
    """`standing_line` -> `standing line`. A word already written for a person
    comes back unchanged."""
    text = str(token or "").strip()
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("_", " ")).strip()


def _decorated(token: str, emoji: str) -> str:
    """The choice as it appears on the button: the words, then the author's emoji."""
    words = label(token)
    mark = (emoji or "").strip()
    if not words:
        return mark
    if not mark or mark in words:
        return words
    return f"{words} {mark}"


def _answers(activity) -> tuple[str, tuple[str, ...]]:
    """The answer to show, and every spelling that counts as it.

    A match activity may name several right answers comma-separated - the loader
    allows it - so the first is the one the reveal says out loud and the rest go
    in with the accepted forms.
    """
    raw = (activity.correct_answer or "").strip()
    if not raw:
        return "", ()
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        return "", ()

    answer = label(parts[0])
    accept: list[str] = []
    for value in [*parts, *(activity.accept or [])]:
        for form in (value, label(value)):
            text = str(form or "").strip()
            if text and text != answer and text not in accept:
                accept.append(text)
    return answer, tuple(accept[:8])


def _from_activity(activity) -> Authored | None:
    answer, accept = _answers(activity)
    if not answer:
        return None

    emojis = list(activity.option_emojis or [])
    options: list[str] = []
    for index, option in enumerate(activity.options or []):
        emoji = emojis[index] if index < len(emojis) else ""
        text = _decorated(option, emoji)
        if text and text not in options:
            options.append(text)

    question = (activity.prompt or "").strip()
    if not question:
        return None

    # A choice activity with one door left is not a question. The loader will
    # not author one, but a de-duplicated list can end up there.
    if activity.answer_kind == "choice" and len(options) < 2:
        return None

    return Authored(
        activity_id=activity.activity_id,
        skill_id=activity.skill_id or activity.activity_id,
        question=question,
        answer=answer,
        accept=accept,
        options=tuple(options[:4]),
        hint=(activity.hint or "").strip(),
        visual_items=tuple(activity.visual_items or []),
    )


@lru_cache(maxsize=256)
def for_topic(topic_id: str) -> tuple[Authored, ...]:
    """Every authored question this topic has, choices first.

    Cached: the curriculum is read from disk at boot and does not change under a
    running server, and a child's turn should not pay for parsing it again.

    Choices come first on purpose. A question with buttons is answerable by a
    child who cannot yet type or be understood by a recogniser, and this class
    starts at two years old.
    """
    if not topic_id:
        return ()
    try:
        activities = curriculum_service.get_activities(topic_id)
    except Exception:  # pragma: no cover - a topic id the manifest no longer has
        logger.warning("No authored activities for topic %s", topic_id)
        return ()

    asked = [made for made in (_from_activity(one) for one in activities) if made is not None]
    if not asked:
        asked = list(_from_subtopics(topic_id))
    asked.sort(key=lambda one: 0 if one.is_choice else 1)
    return tuple(asked)


# The longest a subtopic may be and still fit on a button a child taps. Anything
# longer is a sentence describing a lesson - "Talking about all types of
# transport as well as providing a demonstration of vehicles" - rather than a
# thing that can be picked out of a row.
MAX_SUBTOPIC_WORDS = 4


def _from_subtopics(topic_id: str) -> tuple[Authored, ...]:
    """Questions built from the topic's own list of things, for the topics that
    authored no question at all.

    Some topics are all tracing or all parent activities, so nothing in them has
    a right answer - and the AI Teacher still has to ask five questions to finish
    the stage. Rather than fall back to the topic's title ("which one is
    pre-writing strokes?"), the manifest's own subtopics become the choices: an
    LKG strokes topic lists Standing Line, Sleeping Line, Left Slanting Line, and
    those are exactly the things a child has just been shown.

    Only when they are short enough to be buttons, and only when there are at
    least two of them - one door is not a question.
    """
    try:
        topic = curriculum_service.get_topic(topic_id)
    except Exception:  # pragma: no cover - a topic id the manifest no longer has
        return ()

    icons = list(topic.subtopic_icons or [])
    named: list[tuple[str, str]] = []
    for index, subtopic in enumerate(topic.subtopics or []):
        words = label(subtopic)
        if not words or len(words.split()) > MAX_SUBTOPIC_WORDS:
            continue
        icon = icons[index] if index < len(icons) else ""
        named.append((words, _decorated(words, icon)))
    if len(named) < 2:
        return ()

    options = tuple(shown for _, shown in named[:4])
    return tuple(
        Authored(
            activity_id=f"{topic_id}_subtopic_{index}",
            skill_id=topic_id,
            question=f"Which one is the {words.lower()}?",
            answer=words,
            accept=(words.lower(),),
            options=options,
            hint="",
        )
        for index, (words, _shown) in enumerate(named[:4])
    )


def pick(topic_id: str, *, nth: int, choices_only: bool = False) -> Authored | None:
    """The `nth` authored question for this topic, wrapping round.

    `nth` is how many questions of the stage have been settled, so five questions
    walk the author's list rather than asking the same one five times. It wraps
    because a topic with three authored questions still has to fill a stage of
    five, and the third repeat of a question a child has answered is a smaller
    problem than a question written for a different age.
    """
    pool = for_topic(topic_id)
    if choices_only:
        pool = tuple(one for one in pool if one.is_choice)
    if not pool:
        return None
    return pool[max(0, nth) % len(pool)]


def drawing_prompt(topic_id: str) -> str:
    """The author's own words for the drawing step - "Scribble anywhere you like!"

    The deterministic teacher used to build this out of the topic's title, which
    on a strokes level came out as "can you draw pre-writing strokes with your
    finger?" - a heading, handed to a two-year-old as an instruction. The author
    wrote a real one for the same card.

    It is the *first* tracing card, which is also the one
    `service._trace_target` hands the canvas, so the words and the shape the
    child is drawing into are always the same card.
    """
    if not topic_id:
        return ""
    try:
        activities = curriculum_service.get_activities(topic_id)
    except Exception:  # pragma: no cover - a topic id the manifest no longer has
        return ""
    for activity in activities:
        if activity.trace_target and (activity.prompt or "").strip():
            return activity.prompt.strip()
    return ""


def options_for(topic_id: str, answer: str) -> tuple[str, ...]:
    """The author's own choices for a question whose answer is `answer`.

    Used to rescue a turn whose question came from somewhere else and arrived
    without any choices on it. Nothing is invented: if the syllabus never offered
    this answer as one of a set, this gives back nothing and the caller builds
    the choices from the concept's family instead.
    """
    from app.playground import stage as stage_rules

    if not answer:
        return ()
    for one in for_topic(topic_id):
        if not one.is_choice:
            continue
        if any(stage_rules.contains_answer(option, answer) for option in one.options):
            return one.options
    return ()


def reset() -> None:
    """Drop the cache. Tests use it; nothing in a request does."""
    for_topic.cache_clear()


# Registered so `curriculum_service.reload_curriculum()` empties this too. It
# was not, and a suite that rewrites the manifest on disk went on being answered
# with questions parsed out of the manifest before it.
cache.register("playground.questions", for_topic.cache_clear)


__all__ = [
    "Authored",
    "drawing_prompt",
    "for_topic",
    "label",
    "options_for",
    "pick",
    "reset",
]
