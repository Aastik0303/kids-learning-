"""What a child actually says, as opposed to what the question expected.

Open a microphone in front of a three-year-old and the transcript that comes
back is very often not an answer at all. It is "pata nahi". It is "again". It is
"I want mumma". It is the question read back word for word, or forty seconds of
narration about a dog. Scored as an answer, every one of those is wrong, and a
child who is told they are wrong for saying "I don't know" learns not to speak.

This module reads an utterance that did **not** resolve to an answer and says
what kind of thing it was, so the conductor can respond to it as the thing it
is. Four rules:

* **No LLM, and no answer key.** The classifier is given the utterance and the
  options that are on the screen, and nothing else. It cannot nudge a vague
  transcript towards being right because it does not know what right is.
* **An option is always an answer.** "No" on a yes/no question is a choice, not
  a refusal, and "red" is a colour, not chatter. Anything on screen leaves here
  classified `answer` and is handed straight back to the evaluator.
* **Nothing here is a mistake.** Every kind carries an action and a reply, and
  none of them is "wrong". The strongest outcome is stopping kindly.
* **The reply is English**, like everything the app says to a child. The
  utterance being classified may well be Hindi - a child at home speaks Hindi -
  and that is exactly why the vocabularies below carry Hindi words. Recognising
  Hindi is not narrating in it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# What to do next. The conductor maps each of these onto a phase; none of them
# advances the lesson on the strength of an unresolved utterance.
Action = str

RETRY = "retry"  # ask again, same words, gently
REPEAT = "repeat"  # they asked for it again - say the explanation again
TOGETHER = "together"  # stop testing, do it with them
MOVE_ON = "move_on"  # this one is not happening today; carry on elsewhere
END_KINDLY = "end_kindly"  # the child is done, and saying so


@dataclass(frozen=True)
class Utterance:
    """One thing a child said that was not an answer."""

    kind: str
    action: Action
    reply: str
    # True when the class should not count this against the child in any way -
    # which is every kind here, and is stated rather than assumed.
    blameless: bool = True


# "I don't know", in the words a child of three actually uses for it. This is
# the single most common non-answer and it deserves the kindest handling: it
# means the explanation has not landed, so the class explains again rather than
# asking again.
DONT_KNOW = {
    "dont", "dunno", "know", "idk", "nothing", "nahi", "nahin", "pata",
    "patanahi", "malum", "maloom", "confuse", "confused", "forgot", "forget",
}
DONT_KNOW_PHRASES = ("dont know", "do not know", "pata nahi", "nahi pata", "no idea", "i forgot")

# Asking for it again. A child who says "again" has told you exactly what to do.
REPEAT_WORDS = {"again", "what", "huh", "repeat", "phir", "dobara", "kya", "sorry", "pardon"}

# Wanting to stop. Never argued with.
STOP_WORDS = {"stop", "finish", "finished", "bye", "done", "enough", "bas", "khatam", "band"}

# A child who is not in a state to be taught. This outranks everything else in
# the file: the lesson stops, warmly, and nothing is recorded against them.
DISTRESS_WORDS = {
    "mumma", "mummy", "mama", "mom", "papa", "daddy", "dad", "maa",
    "tired", "sleepy", "sleep", "scared", "hurt", "sad", "crying", "hungry",
    "susu", "potty", "toilet",
}

# Noises rather than words. A recogniser hands these back when a child hums,
# breathes on the microphone, or says the sound without the word.
FILLER_WORDS = {"um", "umm", "uh", "uhh", "hmm", "mmm", "aa", "ah", "eh", "oh", "haan", "ha"}

# Above this many words, a young child is telling you about their day rather
# than answering. It is a lovely thing to do and a terrible answer.
CHATTER_WORDS = 7

# How much of the question has to come back to count as the child reading the
# prompt out loud rather than answering it.
ECHO_OVERLAP = 0.6


def _tokens(text: str) -> list[str]:
    # The Devanagari block is kept alongside `\w`: a child's answer arrives in
    # Devanagari on a Hindi level, and `\w` would strip its matras and leave a
    # different word behind.
    cleaned = re.sub(r"[^\w\sऀ-ॿ]", " ", (text or "").lower())
    return [token for token in cleaned.split() if token]


def _matches_option(tokens: list[str], text: str, options: list[str]) -> bool:
    spoken = set(tokens)
    lowered = text.strip().lower()
    for option in options:
        candidate = str(option or "").strip().lower()
        if not candidate:
            continue
        if candidate == lowered or candidate in spoken:
            return True
    return False


def classify(
    transcript: str,
    *,
    options: list[str] | None = None,
    prompt: str = "",
    confidence: float = 1.0,
    attempts: int = 0,
) -> Utterance:
    """Name what the child said, and say what the class should do about it.

    `options` are the choices visible on screen. They are checked first and they
    win: an utterance that names something the child can see is an answer, and
    this module refuses to reinterpret it as anything else.
    """
    text = (transcript or "").strip()
    tokens = _tokens(text)
    visible = [str(option) for option in (options or []) if str(option or "").strip()]

    if tokens and _matches_option(tokens, text, visible):
        return Utterance(
            kind="answer",
            action=RETRY,
            reply="",
            blameless=True,
        )

    if not tokens:
        return Utterance(
            kind="silence",
            action=TOGETHER if attempts else RETRY,
            reply="I did not hear that one. Let us try again together!",
        )

    # Distress first: a child asking for their mother is not answering a
    # question, and no amount of re-explaining is the right response.
    if set(tokens) & DISTRESS_WORDS:
        return Utterance(
            kind="distress",
            action=END_KINDLY,
            reply="That is okay. Let us stop here for now - you did lovely work today.",
        )

    if set(tokens) & STOP_WORDS:
        return Utterance(
            kind="stop_request",
            action=END_KINDLY,
            reply="Okay! We can play again later. Well done today.",
        )

    lowered = " ".join(tokens)
    if any(phrase in lowered for phrase in DONT_KNOW_PHRASES) or (
        len(tokens) <= 3 and set(tokens) & DONT_KNOW
    ):
        return Utterance(
            kind="dont_know",
            action=TOGETHER,
            reply="That is alright - nobody knows it the first time. Let us look again together.",
        )

    if len(tokens) <= 2 and set(tokens) & REPEAT_WORDS:
        return Utterance(
            kind="asked_again",
            action=REPEAT,
            reply="Of course! Listen once more.",
        )

    if all(token in FILLER_WORDS for token in tokens) or confidence < 0.3:
        return Utterance(
            kind="mumbled",
            action=RETRY,
            reply="Almost! Say it once more in your big voice.",
        )

    prompt_tokens = set(_tokens(prompt))
    if prompt_tokens and len(tokens) >= 3:
        overlap = len(set(tokens) & prompt_tokens) / len(set(tokens))
        if overlap >= ECHO_OVERLAP:
            return Utterance(
                kind="read_the_question",
                action=TOGETHER,
                reply="You read it beautifully! Now let us find the answer together.",
            )

    if len(tokens) > CHATTER_WORDS:
        return Utterance(
            kind="chatter",
            action=RETRY,
            reply="What a story! Now, in one word - what is it?",
        )

    # Something clear, and not this. Most often the child answered a different
    # question, or named something else on the screen entirely.
    return Utterance(
        kind="off_topic",
        action=TOGETHER if attempts else RETRY,
        reply="Good try! That is a different one. Look here with me.",
    )


__all__ = [
    "END_KINDLY",
    "MOVE_ON",
    "REPEAT",
    "RETRY",
    "TOGETHER",
    "Utterance",
    "classify",
]
