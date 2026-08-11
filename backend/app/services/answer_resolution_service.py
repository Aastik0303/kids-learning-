from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, Field

from app.services.answer_normalization_service import COLOURS, SHAPES, answers_match, normalize_answer


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


def _candidate_pool(context: AnswerResolutionContext) -> list[str]:
    candidates = [context.correct_answer, *context.accepted_answers, *context.options]
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
    raw = context.transcript.strip()
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

    raw_tokens = _tokens(raw)
    for candidate, normalized_candidate in normalized_candidates:
        if normalized_candidate and normalized_candidate in raw_tokens:
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
