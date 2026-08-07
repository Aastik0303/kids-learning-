from difflib import SequenceMatcher

from pydantic import BaseModel, Field

from app.services.answer_normalization_service import answers_match, normalize_answer


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
        )

    ambiguous = context.confidence < 0.65 and bool(candidates)
    return AnswerResolutionResult(
        raw_transcript=raw,
        normalized=normalized,
        resolved_answer=normalized,
        resolution_confidence=round(max(context.confidence, best_score), 2),
        ambiguous=ambiguous,
        matched_candidate=best_candidate if best_score >= 0.65 else None,
    )


def resolved_answers_match(context: AnswerResolutionContext) -> tuple[bool, AnswerResolutionResult]:
    result = resolve_answer(context)
    if result.ambiguous:
        return False, result
    correct = context.correct_answer or ""
    return answers_match(result.resolved_answer, correct, context.answer_type), result
