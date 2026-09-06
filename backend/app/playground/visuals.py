"""What the AI Teacher may draw, and the vocabulary it has to ask in.

A child of three does not read the explanation - they look at it. So every turn
carries a picture as well as words, and this module is the list of pictures that
exist and the check that the model only ever names one of them.

**The model does not draw.** It picks a token - `letter:A`, `count:3`,
`shape:circle` - and the client renders the SVG for it. A model handing back
markup would be a model writing whatever it liked into the page, and there is no
version of that which is safe on a child's screen. It is the same shape as the
guide's `allowed_visual_targets`: the model chooses from a list, the server
checks the answer is on the list, and anything else becomes no picture at all.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


SHAPES = ("circle", "square", "triangle", "rectangle", "star")
COLOURS = ("red", "blue", "yellow", "green", "orange", "purple", "pink", "brown", "black", "white")

# How many things a counting picture may show. Ten is the top of the notes and
# also the most a child can take in at a glance.
MAX_COUNT = 10


@dataclass(frozen=True)
class Visual:
    """A picture named rather than drawn. `kind` is empty when there is none."""

    kind: str = ""
    value: str = ""

    @property
    def is_shown(self) -> bool:
        return bool(self.kind)

    def as_token(self) -> str:
        return f"{self.kind}:{self.value}" if self.kind else ""


def _is_single_letter(text: str) -> bool:
    """One letter, in either script. "क" and "की" are each one letter."""
    if len(text) == 1 and text.isalpha():
        return True
    if not text or any(not ("ऀ" <= char <= "ॿ") for char in text):
        return False
    return len([char for char in text if unicodedata.category(char) == "Lo"]) == 1


def parse(token: str | None) -> Visual:
    """Read a `kind:value` token, or give back no picture at all.

    Deliberately unforgiving. Every branch that cannot be certain what was meant
    returns nothing: a missing picture is a smaller problem than a wrong one
    beside an explanation a child is trying to follow.
    """
    text = (token or "").strip()
    if not text or ":" not in text:
        return Visual()

    kind, _, raw = text.partition(":")
    kind = kind.strip().lower()
    value = raw.strip()

    if kind == "letter" and _is_single_letter(value):
        return Visual(kind="letter", value=value)

    if kind == "number" and re.fullmatch(r"\d{1,3}", value):
        return Visual(kind="number", value=str(int(value)))

    if kind == "count" and re.fullmatch(r"\d{1,2}", value) and 1 <= int(value) <= MAX_COUNT:
        return Visual(kind="count", value=str(int(value)))

    if kind == "shape" and value.lower() in SHAPES:
        return Visual(kind="shape", value=value.lower())

    if kind == "colour" and value.lower() in COLOURS:
        return Visual(kind="colour", value=value.lower())

    return Visual()


def _read(haystack: str, *, letters_from: str = "") -> Visual:
    """The one thing a piece of text is about, or nothing."""
    shape = next((name for name in SHAPES if re.search(rf"\b{name}s?\b", haystack, re.I)), "")
    if shape:
        return Visual(kind="shape", value=shape)

    colour = next((name for name in COLOURS if re.search(rf"\b{name}\b", haystack, re.I)), "")
    if colour:
        return Visual(kind="colour", value=colour)

    digits = re.search(r"\b(\d{1,2})\b", haystack)
    if digits and 0 <= int(digits.group(1)) <= 99:
        return Visual(kind="number", value=str(int(digits.group(1))))

    # "Letters: A, B, C" - the first standalone letter, and only ever from the
    # title. A single letter loose in a sentence is nearly always the word "a".
    letter = re.search(r"\b([A-Za-z])\b", letters_from)
    if letter:
        return Visual(kind="letter", value=letter.group(1).upper())

    # A letter standing on its own, first. "स्वर अ आ" is a level about अ, and
    # the first Devanagari character in that title is the स of the word for
    # "vowel" - so reading character by character drew स on every swar level
    # the author wrote without a colon in its name. What is being taught is
    # written as a letter by itself; the kind of thing it is never is.
    for word in re.split(r"[\s,;।·/|-]+", letters_from):
        candidate = word.strip("()[]{}<>\"'`.,:;!?-")
        if not candidate or not any("ऀ" <= char <= "ॿ" for char in candidate):
            continue
        if _is_single_letter(candidate):
            return Visual(kind="letter", value=candidate)

    devanagari = re.search(r"([ऀ-ॿ])", letters_from)
    if devanagari:
        return Visual(kind="letter", value=devanagari.group(1))

    return Visual()


def from_concept(topic_title: str, explanation: str = "") -> Visual:
    """A picture worked out from the words, for the turns with no model behind them.

    **The title is asked first, and the explanation only if it says nothing.**
    A level called "Colours: Pink, Black, White" is about pink whatever else its
    teaching notes happen to mention - and those notes very often mention red,
    because that is how a colour is explained. Reading both at once let the first
    colour in `COLOURS` win, so a lesson on pink drew a red circle as soon as the
    explanation grew long enough to contain the word.
    """
    # "स्वर: अ, आ" is a lesson about अ, not about the स in the word "स्वर", and
    # "Letters: A, B, C" is about A rather than about the L in "Letters". What a
    # level is called before the colon is the *kind* of thing it teaches; what
    # comes after it is the thing itself.
    named = topic_title.split(":", 1)[1] if ":" in topic_title else topic_title

    titled = _read(named, letters_from=named)
    if titled.is_shown:
        return titled
    titled = _read(topic_title, letters_from=topic_title)
    if titled.is_shown:
        return titled
    return _read(f"{topic_title} {explanation}", letters_from=topic_title)


def for_card(answer: str, drawn: Visual | None = None) -> Visual:
    """The concept a card is really about: the answer to the question on it.

    The picture is worked out from the level's title and, failing that, from the
    notes that were retrieved or from a token the model chose - and on a level
    called "Shapes" the title says nothing, so a card could take whichever shape
    the notes led with, or whichever one the model had in mind while it wrote
    the words. That is how "Tap the circle!" came to be asked under a drawing of
    a square.

    A question that has an answer has already said what its card is about, and a
    person wrote that answer. So when the answer names one of the things the app
    draws - a shape, a colour, a letter, a number - that is the concept, and
    everything else only decides when the answer names none of them.

    This is deliberately the *last* word rather than the first: it is applied
    again where the turn leaves the server, so no path through the teacher can
    put a picture on the board that disagrees with the question beside it.
    """
    named = from_concept(answer or "")
    if named.is_shown:
        return named
    return drawn or Visual()


__all__ = [
    "COLOURS",
    "MAX_COUNT",
    "SHAPES",
    "Visual",
    "for_card",
    "from_concept",
    "parse",
]
