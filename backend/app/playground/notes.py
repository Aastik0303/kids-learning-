"""Revision notes for one level: the author's own teaching lines, nothing more.

The Adventure map is a progress board and it teaches nothing. This is the one
thing it may hand a child besides a status: **the notes for a level they have
already met**, so they can go back over it and it does not fade. Tapping the
letter A on the map should give back what A is, what it looks like, what it
starts with, and a picture of an apple - and say it out loud, because the child
cannot read any of it.

Four rules hold this apart from a lesson, and each of them is why it is safe for
the map to offer it at all:

* **No model, anywhere.** Every line here was typed by the person who wrote the
  syllabus. Nothing is generated, nothing is retrieved by similarity, and the
  same level reads exactly the same on two different afternoons - which is what
  a child revising actually needs. `speech` is handed to Edge TTS as it is.
* **No answer key.** A prompt is only kept when its activity has no
  `correct_answer` - that is a teaching card ("This is A."), not a question.
  Anything with an answer contributes its **hint** and never its prompt, because
  a hint is a teaching line ("A looks like a tent with a belt", "A for apple")
  and the prompt is the asking. `correct_answer`, `accept` and `options` are
  never read.
* **Nothing is marked.** There is no attempt, no tally, no probe, no policy
  episode and no star. Reading your notes is not a performance.
* **It teaches, it does not open.** No lesson starts from here. The class is
  still the AI Teacher and the schedule still decides when a level is taught;
  this is the level a child has *already* been given, handed back to them.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.playground import examples, questions, stage as stage_rules, visuals
from app.playground.agent import EVERYDAY_EXAMPLES
from app.services import cache, curriculum_service


logger = logging.getLogger(__name__)

# How many lines a set of notes may hold. A level can author two dozen cards -
# every letter of the alphabet has three - and a child of four is not revising
# from a page of twenty-four sentences. Enough to remember by, and short enough
# to hear in one go.
MAX_LINES = 8

# Roughly how long the whole thing may be when it is read out. Past this it stops
# being a reminder and becomes a lecture.
MAX_SPEECH_CHARS = 700

# The longest a thing's name may be before it stops being a name. An authored
# answer is usually one word - "circle", "door", "apple" - and a card whose
# answer is a phrase is not one whose hint wants a label bolted onto it.
MAX_LABEL_WORDS = 3


@dataclass(frozen=True)
class RevisionNotes:
    """One level, said back to the child.

    `lines` is both what is shown and what is spoken - there is deliberately not
    a separate script, because two versions of the same notes drift and the one
    the child hears would stop being the one on the screen.
    """

    topic_id: str
    title: str
    lines: tuple[str, ...] = ()
    example_items: tuple[str, ...] = ()
    visual_kind: str = ""
    visual_value: str = ""
    speech: str = ""
    # Whether the author left anything to revise from at all. A level that is all
    # tracing, or one still being written, honestly has no notes - and saying so
    # is better than a page of invented encouragement.
    has_notes: bool = field(default=False)


def _tidy(text: str) -> str:
    """One line of the author's, cleaned up for reading aloud.

    Whitespace is collapsed because the syllabus wraps its lines, and a missing
    full stop is added - a run of sentences without them is read by a speech
    engine as one long breath.
    """
    body = re.sub(r"\s+", " ", str(text or "")).strip()
    if not body:
        return ""
    return body if body[-1] in ".!?।" else f"{body}."


def _overview(topic) -> str:
    """What the level is, from the author's objective and opening line.

    Joined the way `rag._topic_passages` joins them, and for the same reason: an
    objective is a syllabus fragment that rarely ends in a full stop, and run
    into the intro without one the two read as one sentence.
    """
    parts = [
        _tidy(getattr(topic, "objective", "") or ""),
        _tidy(getattr(topic, "intro_message", "") or ""),
    ]
    return " ".join(part for part in parts if part)


def _named(hint: str, answer: str) -> str:
    """The hint with the thing it is about named, when the hint does not name it.

    An author writes a hint to sit under their own question, so it leans on it:
    "Round, with no corners." is a complete thought beside "Tap the circle" and
    a riddle on its own. Notes have no question above them, so a run of hints
    reads as "Round, with no corners. It has three corners." - which teaches
    nobody anything.

    So the thing being taught is put in front, and **only when the hint does not
    already say it**: "A square is equal on every side" is left exactly as the
    author wrote it, while "Round, with no corners" becomes "Circle: round, with
    no corners."

    Whether the hint already names it is `stage.contains_answer` - the same
    whole-word test that decides which options may be shown and which tap is
    right. One rule, so the two cannot drift.

    This does read the authored answer, and that is not the answer-key rule
    being bent. That rule is about a **model**: nothing in this module reaches
    one, and there is no question on this page for an answer to give away. It is
    the same thing the class says out loud when it explains - "This is a circle"
    - which `policy/leak.py` exempts for exactly this reason: naming the thing
    you are teaching is the lesson.
    """
    line = _tidy(hint)
    if not line:
        return ""

    label = questions.label((answer or "").split(",")[0]).strip()
    if not label or len(label.split()) > MAX_LABEL_WORDS:
        return line
    # A single letter or a bare number is not a name to define something by.
    # Those cards ask "what comes after E?" or "how many are there?", and their
    # hint is a method rather than a description - "Sing the alphabet song from
    # D", "Touch them and count" - which stands perfectly well on its own and
    # reads as nonsense with "F:" bolted onto the front of it.
    if len(label) < 2 or label.replace(".", "").isdigit():
        return line
    if stage_rules.contains_answer(line, label):
        return line

    first, _, rest = line.partition(" ")
    # "Round," -> "round,"; "A square..." and "M has..." are left alone, because
    # a one-letter word is the letter being taught rather than a capitalised
    # sentence opening.
    opener = first.lower() if len(first) > 1 and not first.isupper() else first
    body = f"{opener} {rest}".strip() if rest else opener
    return f"{label[0].upper()}{label[1:]}: {body}"


def _teaching_lines(topic_id: str) -> list[str]:
    """The author's teaching lines for this level, in the order they wrote them.

    A card with no `correct_answer` is an introduction, so its prompt is a thing
    said to the child and is kept. A card with an answer is a question, so its
    prompt is the asking and is dropped - only its hint survives, which is the
    part that explains rather than tests.
    """
    try:
        activities = curriculum_service.get_activities(topic_id)
    except Exception:  # pragma: no cover - a topic id the manifest no longer has
        logger.warning("No authored activities to revise for %s", topic_id)
        return []

    lines: list[str] = []
    for activity in activities:
        answer = (activity.correct_answer or "").strip()
        if not answer:
            # A teaching card: its prompt is a thing said to the child, not an
            # asking, so both halves of it are notes.
            candidates = (_tidy(activity.prompt), _tidy(activity.hint))
        else:
            # A question card. The prompt is the asking and is dropped; the hint
            # is the explaining and is kept, with the thing it is about named.
            candidates = (_named(activity.hint, answer),)
        for line in candidates:
            if line and line not in lines:
                lines.append(line)
    return lines


def _everyday(visual: visuals.Visual) -> str:
    """The hand-written everyday example for this concept, when there is one.

    The same table the deterministic teacher reads from, so the tomato a child
    hears in class is the tomato they hear again here. It covers the colours and
    shapes the app can draw and nothing else - a concept with no authored example
    gets none rather than an invented one.
    """
    if not visual.is_shown:
        return ""
    return EVERYDAY_EXAMPLES.get(f"{visual.kind}:{visual.value}", "")


_notes_cache = cache.content_cache("playground.notes", maxsize=512)


def for_topic(topic_id: str) -> RevisionNotes:
    """Everything the map may hand back about one level.

    Never raises: a level the manifest has lost, or one whose author wrote
    nothing yet, comes back with `has_notes` false and empty lines, and the
    page says so kindly rather than showing an error to a four-year-old.
    """
    return _notes_cache.get_or_compute(topic_id, lambda: _build_notes(topic_id))


def _build_notes(topic_id: str) -> RevisionNotes:
    try:
        topic = curriculum_service.get_topic(topic_id)
    except Exception:  # pragma: no cover - a topic id the manifest no longer has
        return RevisionNotes(topic_id=topic_id, title=topic_id)

    title = topic.title or topic_id
    concept = visuals.from_concept(title)

    lines: list[str] = []
    overview = _overview(topic)
    if overview:
        lines.append(overview)
    lines.extend(line for line in _teaching_lines(topic_id) if line not in lines)

    everyday = _everyday(concept)
    if everyday and everyday not in lines:
        # Last, because it is the thing to leave a child looking around the room
        # for - and because the level's own words should be heard first.
        lines.append(everyday)

    lines = lines[:MAX_LINES]

    # The pictures beside the words. There is no question on this page, so
    # nothing has to be held back from being an example - `for_turn` is given no
    # answer and no options, and its other rule still applies: a letter, number,
    # shape or colour is the lesson's own furniture and never an example of
    # itself.
    example_items = examples.for_turn(topic_id, visual=concept, answer="", options=[])

    speech = " ".join(lines)[:MAX_SPEECH_CHARS].strip()

    return RevisionNotes(
        topic_id=topic_id,
        title=title,
        lines=tuple(lines),
        example_items=tuple(example_items),
        visual_kind=concept.kind if concept.is_shown else "",
        visual_value=concept.value if concept.is_shown else "",
        speech=speech,
        has_notes=bool(lines),
    )


__all__ = ["MAX_LINES", "MAX_SPEECH_CHARS", "RevisionNotes", "for_topic"]
