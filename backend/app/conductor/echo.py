"""The say-it-back beat: the child answers the explanation out loud.

A letter level used to go straight from "This is A. A says 'aa'." to a question
about A. In between there is a step every human teacher takes and the app did
not: they stop, and they *listen*. "Now you say it. Can you say A?" - and what
comes back tells you whether the explanation landed, seconds after you gave it,
before the child has been asked anything they can get wrong.

That is what this module builds. Three rules hold it together:

* **No LLM.** The phrase to say comes from the level's own authored content by
  way of `explain.ConceptCard`, and judging what came back is string work over
  a transcript the caller has already cleaned. A model that decided whether a
  child said "A" correctly would be a model deciding correctness.
* **It never touches the answer key.** The echo asks for the *concept being
  taught* - the letter, its sound, the word it is for - and it only ever runs on
  a teaching card, which by definition has no correct answer. There is no path
  by which saying it aloud can leak the answer to the question that follows.
* **It is never a mistake.** An echo that does not match is not wrong, is not
  recorded as an attempt, and costs no star. It is a signal that the
  explanation needs to be given differently, and that is all it is.

Because of the third rule the verdict here is deliberately generous. A child of
three saying "aaa" for A, "ay" for A, or just the word - "apple!" - has heard
the explanation. Only silence and something entirely unrelated are treated as
"that did not land".
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.conductor.explain import ConceptCard


# Which subjects stop and listen: the ones whose levels teach an alphabet or
# numbers - English, maths, and the two Hindi subjects, where the Devanagari
# letter is the alphabet being taught. General awareness, EVS, art and rhymes
# teach by looking and doing, and a microphone in the middle of them interrupts
# rather than teaches.
VOICE_SUBJECT_MARKERS = ("english", "math", "hindi", "language")

# How many times one sitting asks the child to say something back. Once, at the
# start, when the first thing has been explained - and never again in that
# lesson. A microphone that reappears after every card stops being a moment the
# child answers and becomes something they have to get past, and an explanation
# that did not land is answered by explaining it differently rather than by
# asking again louder.
ECHO_ASKS_PER_LESSON = 1

# Below this the recogniser heard noise, not a word. Handled as a microphone
# problem, never as a failed echo.
HEARD_NOTHING_CONFIDENCE = 0.35

# A spoken echo is compared loosely on purpose: see the module docstring.
CLOSE_ENOUGH = 0.62


@dataclass(frozen=True)
class EchoTarget:
    """What the child is being asked to say, and what would count as saying it."""

    # The thing itself, as it should appear on screen: "A", "3", "क".
    thing: str = ""
    # The word the thing is taught through - "apple", "अनार". Asked for
    # alongside the letter; see `ask`.
    word: str = ""
    # Everything that counts as having said it, lowercased.
    accepted: tuple[str, ...] = ()
    # Words to bias the recogniser towards, handed to the client.
    contextual_strings: tuple[str, ...] = ()

    @property
    def is_askable(self) -> bool:
        """Whether there is actually something here worth asking for.

        A card with no symbol and no word gives nothing to say back, and asking
        a child to repeat nothing is worse than not asking."""
        return bool(self.thing and self.accepted)


@dataclass(frozen=True)
class EchoVerdict:
    """What the child's spoken echo came to. Never a score."""

    # "matched"   - they said it, or close enough
    # "unmatched" - they said something, and it was not this
    # "no_speech" - silence, or the recogniser heard nothing usable
    outcome: str = "no_speech"
    heard: str = ""
    similarity: float = 0.0
    notes: dict = field(default_factory=dict)

    @property
    def landed(self) -> bool:
        return self.outcome == "matched"


def subject_speaks(subject_id: str | None) -> bool:
    """Whether this subject stops to listen. English and maths do."""
    lowered = (subject_id or "").lower()
    return any(marker in lowered for marker in VOICE_SUBJECT_MARKERS)


def is_letter_or_number(thing: str) -> bool:
    """Whether this is a thing worth asking a child to say back.

    The beat is for an alphabet and for numbers - "A", "b", "3", "10", "अ", "क"
    - and for nothing else. A colour, a shape or an animal is taught by looking
    and pointing, and asking a four-year-old to say "rectangle" into a browser
    recogniser tests the microphone rather than the child.

    A Devanagari letter counts, because in `nur_hindi` and `ukg_language` it *is*
    the alphabet being taught. One letter, not a word: "अ" and "क" are asked
    for, "अनार" is not - the word is offered alongside the letter by `ask`, and
    counts as having said it, but it is never the thing being asked for.
    """
    text = (thing or "").strip()
    if not text:
        return False
    if len(text) == 1 and "a" <= text.lower() <= "z":
        return True
    if text.isdigit():
        return True
    return _is_single_devanagari_letter(text)


def _is_single_devanagari_letter(text: str) -> bool:
    """One Devanagari letter, with the vowel signs that belong to it.

    "की" is two code points - the letter क and the matra ि - and is still one
    letter. Counting characters would reject it; counting *base* letters is what
    tells क apart from कल.
    """
    if any(not ("ऀ" <= char <= "ॿ") for char in text):
        return False
    bases = [char for char in text if unicodedata.category(char) == "Lo"]
    return len(bases) == 1


def _forms(value: str) -> set[str]:
    """The shapes one accepted word can plausibly arrive in.

    A recogniser hands back "ay" for A and "three" for 3; the phonetic cleaner
    upstream turns most of those back, and what survives is handled here.
    """
    text = (value or "").strip().lower()
    if not text:
        return set()
    forms = {text}
    # `\w` alone would delete Devanagari's combining vowel signs - the matras -
    # because they are marks rather than letters, turning अनार into अनर and
    # किताब into कताब. The block is kept explicitly so a Hindi word survives
    # having its punctuation removed.
    stripped = re.sub(r"[^\w\sऀ-ॿ]", "", text).strip()
    if stripped:
        forms.add(stripped)
        forms.update(part for part in stripped.split() if len(part) > 1)
    return {form for form in forms if form}


def target_for(card: ConceptCard) -> EchoTarget:
    """What to ask for, read from the concept the level just taught.

    The symbol is the thing; the sound and the word are accepted alongside it,
    because a child who answers "A says aa" with "aa" has done exactly what was
    asked of them and must not be told otherwise.
    """
    thing = (card.symbol or "").strip()
    if not thing or not is_letter_or_number(thing):
        # Nothing to ask for: either the card teaches no named thing, or the
        # thing is not a letter or a number and so is not asked for out loud.
        return EchoTarget()

    accepted: set[str] = set()
    for value in (thing, card.sound, card.word):
        accepted |= _forms(value)

    contextual = [value.strip() for value in (thing, card.sound, card.word) if value and value.strip()]
    return EchoTarget(
        thing=thing,
        word=(card.word or "").strip(),
        accepted=tuple(sorted(accepted)),
        contextual_strings=tuple(dict.fromkeys(contextual)),
    )


def ask(target: EchoTarget, *, attempt: int = 0) -> str:
    """The guide's own words for the listening beat. Short, and clearly a turn.

    The word is asked for alongside the letter, and that is not decoration. No
    speech recogniser in a browser or on a phone reliably transcribes an
    isolated vowel: "अ" is about a third of a second of sound and comes back as
    silence, over and over, while the same child saying a whole sentence is
    transcribed perfectly. A word gives the recogniser something it can actually
    catch, and `target.accepted` already counts the letter, its sound and its
    word equally - so a child who says either has said it.

    It is also how the level teaches: "अ से अनार", "A is for apple". Asking
    for both is the authored method, not a workaround bolted onto it.

    The wording changes on a second ask so a child who did not answer the first
    time does not simply hear the same sentence louder.
    """
    if not target.is_askable:
        return ""
    thing = target.thing
    word = target.word

    if not word:
        if attempt <= 0:
            return f"Now your turn. Can you say {thing}?"
        return f"Let us try together. Say {thing} with me!"

    if attempt <= 0:
        return f"Now your turn. Say {thing}, {thing} for {word}!"
    return f"Let us try together. Say it with me: {thing}... {word}!"


def judge(*, heard: str, confidence: float, target: EchoTarget) -> EchoVerdict:
    """Did the child say the thing? Generously, and never as a score.

    `heard` is the transcript after the deterministic child-speech cleaner has
    had it. This function does no phonetics of its own; it compares words.
    """
    spoken = (heard or "").strip().lower()
    if not spoken or confidence < HEARD_NOTHING_CONFIDENCE:
        return EchoVerdict(
            outcome="no_speech",
            heard=spoken,
            notes={"reason": "silence" if not spoken else "too_quiet"},
        )

    if not target.is_askable:
        # Nothing was really asked, so anything the child offered counts. This
        # is the safe direction to fail in.
        return EchoVerdict(outcome="matched", heard=spoken, similarity=1.0, notes={"reason": "nothing_asked"})

    spoken_forms = _forms(spoken)
    if spoken_forms & set(target.accepted):
        return EchoVerdict(outcome="matched", heard=spoken, similarity=1.0, notes={"reason": "said_it"})

    best = 0.0
    for accepted in target.accepted:
        for form in spoken_forms or {spoken}:
            best = max(best, SequenceMatcher(None, form, accepted).ratio())

    if best >= CLOSE_ENOUGH:
        return EchoVerdict(outcome="matched", heard=spoken, similarity=round(best, 2), notes={"reason": "close_enough"})

    return EchoVerdict(outcome="unmatched", heard=spoken, similarity=round(best, 2), notes={"reason": "different_word"})


__all__ = [
    "CLOSE_ENOUGH",
    "EchoTarget",
    "EchoVerdict",
    "HEARD_NOTHING_CONFIDENCE",
    "ECHO_ASKS_PER_LESSON",
    "VOICE_SUBJECT_MARKERS",
    "ask",
    "is_letter_or_number",
    "judge",
    "subject_speaks",
    "target_for",
]
