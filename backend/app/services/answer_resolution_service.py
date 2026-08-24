from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field

from app.services.answer_normalization_service import COLOURS, SHAPES, answers_match, normalize_answer
from app.services.child_speech_service import ChildSpeechResult, clean_child_speech


class AnswerResolutionContext(BaseModel):
    transcript: str
    confidence: float = 0.0
    answer_type: str = ""
    correct_answer: str | None = None
    accepted_answers: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)


class AnswerResolutionResult(BaseModel):
    raw_transcript: str
    normalized: str
    resolved_answer: str
    resolution_confidence: float
    ambiguous: bool = False
    matched_candidate: str | None = None
    input_kind: Literal["answer", "unresolved", "empty"] = "unresolved"
    # What the deterministic child-speech cleaner made of the transcript, and how
    # sure it is. `retry_suggested` means the app should ask the child to say it
    # again rather than score what was heard.
    child_speech: ChildSpeechResult | None = None


def _candidate_pool(context: AnswerResolutionContext) -> list[str]:
    # The answer key goes LAST, never first. Several scans below return on their
    # first hit, so whatever sits at index 0 wins every race — and when that was
    # `correct_answer`, the same transcript resolved to whichever answer happened
    # to be correct. "cat dog" resolved to cat when cat was right and to dog when
    # dog was right. `child_speech_service` is careful never to see the key; this
    # pool was handing it back.
    candidates = [*context.options, *context.accepted_answers, context.correct_answer]
    seen: set[str] = set()
    unique = []
    for candidate in candidates:
        if not candidate:
            continue
        key = str(candidate).strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(str(candidate).strip())
    return unique


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _tokens(text: str) -> set[str]:
    return set(normalize_answer(text, "").split())


def _semantic_answer(context: AnswerResolutionContext, raw: str, candidates: list[str]) -> str | None:
    answer_type = context.answer_type.lower()
    tokens = normalize_answer(raw, "").split()
    normalized_candidates = [normalize_answer(candidate, context.answer_type) for candidate in candidates]
    numeric_domain = answer_type in {"select_number", "identify_number", "count_objects"} or (
        bool(normalized_candidates) and all(candidate.isdigit() for candidate in normalized_candidates)
    )
    letter_domain = "letter" in answer_type or (
        bool(normalized_candidates) and all(len(candidate) == 1 and candidate.isalpha() for candidate in normalized_candidates)
    )
    colour_domain = "colour" in answer_type or "color" in answer_type or any(candidate in COLOURS for candidate in normalized_candidates)
    shape_domain = "shape" in answer_type or any(candidate in SHAPES for candidate in normalized_candidates)

    if numeric_domain:
        numbers = [token for token in tokens if token.isdigit()]
        if numbers:
            return numbers[-1]
    if letter_domain:
        normalized_letter = normalize_answer(raw, "select_letter")
        if len(normalized_letter) == 1 and normalized_letter.isalpha():
            return normalized_letter
    if colour_domain:
        normalized_colour = normalize_answer(raw, "identify_colour")
        if normalized_colour in COLOURS:
            return normalized_colour
    if shape_domain:
        normalized_shape = normalize_answer(raw, "identify_shape")
        if normalized_shape in SHAPES:
            return normalized_shape
    return None


def resolve_answer(context: AnswerResolutionContext) -> AnswerResolutionResult:
    """Resolve a spoken or tapped answer, with a child-speech rescue behind it.

    The original resolution runs first and is kept whenever it settles on an
    answer, so nothing that already worked changes. Only when it comes up
    unresolved is the transcript run through the deterministic child-speech
    cleaner and tried again — that is what lets "teen", "gol" and "do nahi teen"
    reach the evaluator as 3, circle and 3.
    """
    raw = context.transcript.strip()
    result = _resolve_core(context)

    # Only the visible options are handed over. The correct answer stays out of
    # the cleaner so it can never steer a vague transcript towards being right.
    child = clean_child_speech(raw, context.answer_type, context.options)

    if result.input_kind != "answer" and child.token and child.token != raw.lower():
        rescued = _resolve_core(context.model_copy(update={"transcript": child.token}))
        if rescued.input_kind == "answer":
            result = rescued.model_copy(update={"raw_transcript": raw})

    return result.model_copy(update={"child_speech": child})


def _resolve_core(context: AnswerResolutionContext) -> AnswerResolutionResult:
    raw = context.transcript.strip()

    # A tapped answer arrives as the option's own text, so it needs none of the
    # speech handling below — and must not be put through it. An option of "an",
    # "please" or ">" normalizes to nothing, which used to end this function as
    # "empty" and score a correct tap wrong every single time. An exact match
    # against what was offered settles the answer before any of that.
    for candidate in _candidate_pool(context):
        if raw.lower() == candidate.lower():
            # Still report the normalized form where there is one, so a spoken
            # "A" resolves to "a" as it always has. The literal is the fallback
            # only for answers normalization cannot represent.
            resolved = normalize_answer(candidate, context.answer_type) or candidate
            return AnswerResolutionResult(
                raw_transcript=raw,
                normalized=resolved,
                resolved_answer=resolved,
                resolution_confidence=round(min(max(context.confidence, 0.99), 1.0), 2),
                matched_candidate=candidate,
                input_kind="answer",
            )

    normalized = normalize_answer(raw, context.answer_type)
    if not raw or not normalized:
        return AnswerResolutionResult(
            raw_transcript=raw,
            normalized="",
            resolved_answer="",
            resolution_confidence=0.0,
            ambiguous=True,
            input_kind="empty",
        )

    candidates = _candidate_pool(context)
    normalized_candidates = [(candidate, normalize_answer(candidate, context.answer_type)) for candidate in candidates]

    for candidate, normalized_candidate in normalized_candidates:
        if normalized_candidate and normalized_candidate == normalized:
            confidence = max(context.confidence, 0.95)
            return AnswerResolutionResult(
                raw_transcript=raw,
                normalized=normalized_candidate,
                resolved_answer=normalized_candidate,
                resolution_confidence=round(min(confidence, 1.0), 2),
                matched_candidate=candidate,
                input_kind="answer",
            )

    # Scanning the utterance for any offered answer is what rescues "umm the
    # blue one". It is also how a child who reads the choices out loud —
    # "cat? ...dog?", completely normal at three — used to be scored. More than
    # one answer in one breath is not an answer; say so instead of picking.
    raw_tokens = _tokens(raw)
    token_hits: list[tuple[str, str]] = []
    hit_values: set[str] = set()
    for candidate, normalized_candidate in normalized_candidates:
        if normalized_candidate and normalized_candidate in raw_tokens and normalized_candidate not in hit_values:
            hit_values.add(normalized_candidate)
            token_hits.append((candidate, normalized_candidate))

    if len(token_hits) > 1:
        # Counting out loud is not ambiguity: "one, two, three" while pointing at
        # apples means three. The domain rules below read the utterance itself
        # (last number spoken, the single letter, the colour named) and never
        # consult the answer key, so they are safe to trust here.
        counted = _semantic_answer(context, raw, candidates)
        if counted:
            return AnswerResolutionResult(
                raw_transcript=raw,
                normalized=normalized,
                resolved_answer=counted,
                resolution_confidence=round(max(context.confidence, 0.9), 2),
                input_kind="answer",
            )
        # Two different offered answers in one breath, and no domain rule to
        # break the tie. Ask again rather than guess: guessing here is what
        # scored the answer key every time.
        return AnswerResolutionResult(
            raw_transcript=raw,
            normalized=normalized,
            resolved_answer="",
            resolution_confidence=0.0,
            ambiguous=True,
            input_kind="unresolved",
        )

    if token_hits:
        candidate, normalized_candidate = token_hits[0]
        confidence = max(context.confidence, 0.9)
        return AnswerResolutionResult(
            raw_transcript=raw,
            normalized=normalized_candidate,
            resolved_answer=normalized_candidate,
            resolution_confidence=round(min(confidence, 1.0), 2),
            matched_candidate=candidate,
            input_kind="answer",
        )

    semantic_answer = _semantic_answer(context, raw, candidates)
    if semantic_answer:
        return AnswerResolutionResult(
            raw_transcript=raw,
            normalized=normalized,
            resolved_answer=semantic_answer,
            resolution_confidence=round(max(context.confidence, 0.9), 2),
            ambiguous=False,
            input_kind="answer",
        )

    best_candidate = None
    best_normalized = normalized
    best_score = 0.0
    for candidate, normalized_candidate in normalized_candidates:
        score = max(_similarity(normalized, normalized_candidate), _similarity(raw.lower(), candidate.lower()))
        if score > best_score:
            best_score = score
            best_candidate = candidate
            best_normalized = normalized_candidate or candidate

    if best_candidate and best_score >= 0.84:
        return AnswerResolutionResult(
            raw_transcript=raw,
            normalized=best_normalized,
            resolved_answer=best_normalized,
            resolution_confidence=round(max(context.confidence, best_score), 2),
            matched_candidate=best_candidate,
            input_kind="answer",
        )

    ambiguous = context.confidence < 0.65 and bool(candidates)
    return AnswerResolutionResult(
        raw_transcript=raw,
        normalized=normalized,
        resolved_answer=normalized,
        resolution_confidence=round(max(context.confidence, best_score), 2),
        ambiguous=ambiguous,
        matched_candidate=best_candidate if best_score >= 0.65 else None,
        input_kind="unresolved",
    )


def resolved_answers_match(context: AnswerResolutionContext) -> tuple[bool, AnswerResolutionResult]:
    result = resolve_answer(context)
    if result.ambiguous:
        return False, result
    correct = context.correct_answer or ""
    return answers_match(result.resolved_answer, correct, context.answer_type), result
