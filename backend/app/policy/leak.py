"""Telling the difference between helping a child and handing them the answer.

`policy_episodes.answer_leak_vetoed` has been in the schema since the table was
written, and until now nothing set it: every episode was recorded as clean, and
the heaviest penalty in the reward function (-1.5, larger than a passed probe
pays) had never once been applied. This module is what fills that column in.

The distinction it has to hold is the whole difficulty. A guide that never says
the answer word is not automatically safe, and a guide that says it is not
automatically leaking:

- **scaffolding** narrows the field or restates the question. "Is it round or
  does it have corners?" and "Which one is the circle?" both contain the answer
  and neither gives it away, because the question itself already did;
- **partial assistance** hands over part of the answer - the first sound, the
  letter it starts with, the number of legs. This is what the second rung of the
  ladder is *for*, so it is recorded and not punished;
- **a leak** is the answer, told. "The answer is the circle." "Tap the square."
  A strategy that does this gets today's attempt right and fails the probe on
  Tuesday, which is exactly what the delayed reward exists to catch - but the
  reward alone learns it slowly and one child at a time, so the veto marks it
  the moment it happens.

Everything here is string work over the server's own answer key. No model is
consulted, and nothing in this module is upstream of a mark, a star or an
unlock: the verdict only ever reaches the policy's reward.
"""

import re
from dataclasses import dataclass


NONE = "none"
SCAFFOLD = "scaffold"
PARTIAL = "partial"
LEAK = "leak"

# The frames that end the thinking. The answer word is spliced in as a group at
# call time, so these are templates.
#
# They come in two kinds, and the difference is what a *teaching* turn is
# allowed to say. **Directive** frames talk about the task - what to do, which
# one is right - and there is no turn on which saying one of those is teaching.
# **Naming** frames are the ordinary way to introduce a thing: "This is a
# square." Beside a question the child is being marked on that is handing the
# answer over; as the first sentence of an explanation it is the lesson, and it
# is the first sentence of nearly every explanation ever written for a
# four-year-old. So a teaching turn is judged on the directive frames alone.
DIRECTIVE_FRAMES = (
    r"(?:the\s+)?answer\s+is(?:\s+(?:a|an|the))?\s+{a}",
    r"(?:tap|touch|press|pick|choose|select|click)\s+(?:on\s+)?(?:the\s+|a\s+|an\s+)?{a}\b",
    r"(?:the\s+)?(?:right|correct)\s+(?:one|answer)\s+is(?:\s+(?:a|an|the))?\s+{a}",
    r"{a}\s+is\s+(?:the\s+)?(?:right|correct)(?:\s+answer)?\b",
)

NAMING_FRAMES = (
    r"it(?:'s|s| is)(?:\s+(?:a|an|the))?\s+{a}\b(?!\s*(?:\?|or\b))",
    r"this\s+(?:one\s+)?is(?:\s+(?:a|an|the))?\s+{a}\b(?!\s*(?:\?|or\b))",
)

TELL_FRAMES = (*DIRECTIVE_FRAMES, *NAMING_FRAMES)

# A frame that offers the answer among alternatives is narrowing, not telling.
CHOICE_MARKERS = re.compile(r"\bor\b|\?", re.IGNORECASE)

# Help that hands over a piece of the answer without the answer itself.
PARTIAL_MARKERS = re.compile(
    r"\b(?:starts?\s+with|begins?\s+with|first\s+(?:letter|sound)|rhymes?\s+with"
    r"|sounds?\s+like|ends?\s+with|has\s+\w+\s+(?:corners|sides|legs|letters))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Verdict:
    kind: str
    evidence: str = ""

    @property
    def is_leak(self) -> bool:
        return self.kind == LEAK


def normalise(text: str) -> str:
    """Lowercase, underscores to spaces, punctuation kept - the frames need it."""
    return re.sub(r"\s+", " ", (text or "").replace("_", " ")).strip().lower()


def _mentions(text: str, answer: str) -> bool:
    if not answer:
        return False
    return re.search(rf"(?<![\w]){re.escape(answer)}(?![\w])", text) is not None


def _told(text: str, answer: str, *, teaching: bool = False) -> str | None:
    for template in DIRECTIVE_FRAMES if teaching else TELL_FRAMES:
        pattern = template.format(a=re.escape(answer))
        found = re.search(pattern, text, re.IGNORECASE)
        if found:
            return found.group(0)
    return None


def classify(
    message: str,
    *,
    correct_answer: str | None,
    prompt: str = "",
    options: tuple[str, ...] = (),
    accepted: tuple[str, ...] = (),
    teaching: bool = False,
) -> Verdict:
    """What this guide turn did with the answer.

    `prompt` matters as much as `message`: a question that names its own answer -
    "Which one is the circle?", which is how every identify-the-shape level is
    written - cannot be leaked by repeating it, and marking those as leaks would
    veto the entire subject.

    `teaching` is for the turn that explains a thing and *then* asks about it,
    which is the shape every AI Teacher `match` and `quiz` turn has. Such a turn
    names the concept on purpose - "This is a square. A square has four straight
    sides." - before asking "which shape has four equal sides?", and the naming
    is the lesson rather than the answer being handed over. Without this flag the
    bare-mention rule below marks one turn in eight as a leak and charges it 1.5
    of reward, which is more than a passed probe pays: the table would learn to
    stop explaining, which is the opposite of the thing this module exists to
    protect. An outright telling - "the answer is the square", "tap the square" -
    is still a leak on a teaching turn, because it is about the task rather than
    about the thing. See `DIRECTIVE_FRAMES` and `NAMING_FRAMES`.
    """
    text = normalise(message)
    if not text:
        return Verdict(NONE)

    answers = [normalise(a) for a in (correct_answer, *accepted) if a and normalise(a)]
    if not answers:
        # No key to leak. Partial help is still worth naming for the metrics.
        return Verdict(PARTIAL if PARTIAL_MARKERS.search(text) else NONE)

    asked = normalise(prompt)
    option_words = [normalise(o) for o in options if normalise(o)]

    for answer in answers:
        if not _mentions(text, answer):
            continue
        if _mentions(asked, answer):
            # The question said it first. Saying it back is reading the question.
            return Verdict(SCAFFOLD, evidence="answer is in the prompt")
        told = _told(text, answer, teaching=teaching)
        if told:
            return Verdict(LEAK, evidence=told)
        others = [o for o in option_words if o != answer and _mentions(text, o)]
        if others and CHOICE_MARKERS.search(text):
            return Verdict(SCAFFOLD, evidence=f"offered against {others[0]}")
        if teaching:
            # Named, not told. See `teaching` above.
            return Verdict(SCAFFOLD, evidence="named while teaching it")
        return Verdict(LEAK, evidence=answer)

    if PARTIAL_MARKERS.search(text):
        return Verdict(PARTIAL, evidence="partial clue")
    return Verdict(NONE)


def vetoes(
    message: str,
    *,
    correct_answer: str | None,
    prompt: str = "",
    options: tuple[str, ...] = (),
    accepted: tuple[str, ...] = (),
    teaching: bool = False,
) -> bool:
    """The one-line form the guide calls. True only for an outright leak."""
    return classify(
        message,
        correct_answer=correct_answer,
        prompt=prompt,
        options=options,
        accepted=accepted,
        teaching=teaching,
    ).is_leak


__all__ = [
    "DIRECTIVE_FRAMES",
    "LEAK",
    "NAMING_FRAMES",
    "NONE",
    "PARTIAL",
    "SCAFFOLD",
    "TELL_FRAMES",
    "Verdict",
    "classify",
    "normalise",
    "vetoes",
]
