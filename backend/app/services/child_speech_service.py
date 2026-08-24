"""Stage 1 of the child speech pipeline: deterministic cleanup of a raw transcript.

A two to six year old's answer reaches the browser's recogniser as "tree" for
three, "wed" for red, "teen" for 3, and very often as a self-correction —
"do nahi teen". Grading that transcript as it arrives marks a child wrong for an
answer they actually got right, which is the fastest way to lose their trust in
the app.

Two rules hold this module together:

* No LLM. Every mapping here is a lookup in `data/speech/kid_phonetics.json`,
  which is why it costs nothing and always gives the same answer twice.
* It never judges correctness. This module reports what the child most likely
  *said*; whether that is the right answer stays with the evaluators.

The second rule has a concrete consequence in `clean_child_speech`: it is given
the options that are visible on screen and nothing else. The correct answer is
deliberately not a parameter, so a low-confidence transcript can never be nudged
towards being right.
"""

from __future__ import annotations

import json
import re
import string
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, computed_field

from app.services.answer_normalization_service import normalize_answer

PHONETICS_PATH = Path(__file__).resolve().parents[1] / "data" / "speech" / "kid_phonetics.json"

# Above this the deterministic clean is trusted and the answer goes straight to
# the evaluator. Between the two an AI enhancer would be worth calling — there is
# none yet, so the band is reported and the transcript is used as-is. Below the
# lower bound nothing is worth guessing: the child is asked to say it again, and
# that is not a mistake against them.
CONFIDENT_THRESHOLD = 0.80
RETRY_THRESHOLD = 0.30

CleanStatus = Literal["resolved", "needs_enhancement", "retry", "empty"]

# Which phonetic map to consult first for a given activity type. A token is only
# taken from a non-preferred map when the result is one of the visible options,
# so a colour question can never turn "do" into the number 2.
_NUMBER_TYPE_MARKERS = ("number", "count", "quantity")
_COLOUR_TYPE_MARKERS = ("colour", "color")
_SHAPE_TYPE_MARKERS = ("shape",)


class ChildSpeechResult(BaseModel):
    """What the deterministic cleaner made of one spoken answer."""

    token: str
    confidence: float
    status: CleanStatus
    reason_code: str
    self_corrected: bool = False

    @computed_field
    @property
    def needs_enhancement(self) -> bool:
        """The band an AI enhancer would be called in. Nothing calls one yet."""
        return self.status == "needs_enhancement"

    @computed_field
    @property
    def retry_suggested(self) -> bool:
        """The child should be asked to say it again, gently and without penalty."""
        return self.status in {"retry", "empty"}


@lru_cache(maxsize=1)
def _phonetics() -> dict:
    with PHONETICS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _families() -> list[tuple[str, dict[str, str]]]:
    data = _phonetics()
    return [
        ("number", {**data["numbers_en"], **data["numbers_hi"]}),
        ("colour", data["colors"]),
        ("shape", data["shapes"]),
    ]


def _expected_family(answer_type: str) -> str | None:
    lowered = (answer_type or "").lower()
    if any(marker in lowered for marker in _NUMBER_TYPE_MARKERS):
        return "number"
    if any(marker in lowered for marker in _COLOUR_TYPE_MARKERS):
        return "colour"
    if any(marker in lowered for marker in _SHAPE_TYPE_MARKERS):
        return "shape"
    return None


def _split(raw: str) -> list[str]:
    cleaned = raw.strip().lower()
    cleaned = cleaned.translate(str.maketrans({mark: " " for mark in string.punctuation}))
    return re.sub(r"\s+", " ", cleaned).strip().split()


def _apply_self_correction(tokens: list[str], visible: set[str]) -> tuple[list[str], bool]:
    """"do nahi teen" means 3. Whatever follows the last correction marker wins.

    A marker with nothing after it ("teen nahi") is a child trailing off rather
    than correcting, so the words before it are kept instead of returning empty.

    A marker that is itself on screen is an answer, not a correction — on a
    yes/no question "no" is what the child chose.
    """
    markers = set(_phonetics()["self_correction_markers"]) - visible
    last = max((index for index, token in enumerate(tokens) if token in markers), default=-1)
    if last == -1:
        return tokens, False
    after = tokens[last + 1 :]
    if after:
        return after, True
    return tokens[:last], False


def _drop_fillers(tokens: list[str]) -> list[str]:
    fillers = set(_phonetics()["fillers"])
    kept = [token for token in tokens if token not in fillers]
    # "umm" on its own is still a turn taken; keep it rather than reporting empty
    # speech, so the caller can tell silence apart from noise.
    return kept or tokens


def _map_tokens(tokens: list[str], expected: str | None, visible: set[str]) -> tuple[list[str], bool]:
    """Rewrite kid pronunciations to the word they meant.

    Ordering matters: the map matching the activity type is consulted first, and
    a match from any other map is accepted only when it lands on something the
    child can actually see. That is what keeps "do" a filler word on a colour
    question and the number two on a counting one.
    """
    families = _families()
    ordered = sorted(families, key=lambda family: family[0] != expected)
    mapped_any = False
    result: list[str] = []
    for token in tokens:
        replacement = token
        for family, mapping in ordered:
            if token not in mapping:
                continue
            candidate = mapping[token]
            if family == expected or candidate in visible or (expected is None and not visible):
                replacement = candidate
                break
        if replacement != token:
            mapped_any = True
        result.append(replacement)
    return result, mapped_any


def _visible_forms(options: list[str], answer_type: str) -> set[str]:
    forms: set[str] = set()
    for option in options:
        text = str(option).strip()
        if not text:
            continue
        forms.add(text.lower())
        normalized = normalize_answer(text, answer_type)
        if normalized:
            forms.add(normalized)
    return forms


def _best_similarity(token: str, visible: set[str]) -> float:
    if not token or not visible:
        return 0.0
    return max(SequenceMatcher(None, token, option).ratio() for option in visible)


def _score(token: str, raw: str, visible: set[str], mapped: bool) -> tuple[float, str]:
    """Confidence that `token` is what the child meant — never whether it is right.

    `visible` holds only the options on screen. The correct answer never reaches
    this function, so a wrong-but-clear answer scores just as high as a right one.
    """
    if token and token in visible:
        return 1.00, "exact_option"
    if _best_similarity(token, visible) > 0.85:
        return 0.90, "fuzzy_option"
    if mapped:
        return 0.85, "phonetic_map"
    if len(raw.split()) > 4:
        return 0.30, "long_utterance"
    return 0.50, "plain_token"


def _band(confidence: float) -> CleanStatus:
    if confidence >= CONFIDENT_THRESHOLD:
        return "resolved"
    if confidence >= RETRY_THRESHOLD:
        return "needs_enhancement"
    return "retry"


def clean_child_speech(
    raw: str,
    answer_type: str = "",
    options: list[str] | None = None,
) -> ChildSpeechResult:
    """Turn a messy transcript into one answer token plus a confidence band.

    `options` are the choices visible on screen. Passing them makes the result
    far sharper — a token that matches one of them is certain — but they are not
    required, and the correct answer is never among the arguments.
    """
    visible = _visible_forms(options or [], answer_type)

    if not raw or not raw.strip():
        # Silence is a child thinking or a microphone that heard nothing. It is
        # never a wrong answer, so it gets its own status rather than a score.
        return ChildSpeechResult(token="", confidence=0.0, status="empty", reason_code="no_speech")

    tokens = _split(raw)
    if not tokens:
        return ChildSpeechResult(token="", confidence=0.0, status="empty", reason_code="no_speech")

    tokens, self_corrected = _apply_self_correction(tokens, visible)
    tokens = _drop_fillers(tokens)
    expected = _expected_family(answer_type)
    tokens, mapped = _map_tokens(tokens, expected, visible)

    if not tokens:
        return ChildSpeechResult(token="", confidence=0.0, status="empty", reason_code="no_speech")

    digits = [token for token in tokens if token.isdigit()]
    matches = [token for token in tokens if token in visible]

    if len(digits) > 1 and len(digits) == len(tokens):
        # A child counting the objects out loud — "ek do teen" — is answering
        # with the number they land on, not the one they start from.
        token = digits[-1]
        reason = "counted_aloud_final"
    elif len(set(matches)) == 1:
        # Exactly one thing they said is on the screen; the rest was padding.
        token = matches[0]
        reason = ""
    else:
        joined = " ".join(tokens)
        token = normalize_answer(joined, answer_type) or joined
        reason = ""

    confidence, score_reason = _score(token, raw, visible, mapped)
    if self_corrected:
        reason = reason or "self_correction"
    return ChildSpeechResult(
        token=token,
        confidence=confidence,
        status=_band(confidence),
        reason_code=reason or score_reason,
        self_corrected=self_corrected,
    )
