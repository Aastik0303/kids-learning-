from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.answer_resolution_service import AnswerResolutionContext, AnswerResolutionResult, resolve_answer

router = APIRouter(prefix="/speech", tags=["speech"])


class SpeechNormalizeRequest(BaseModel):
    transcript: str = ""
    confidence: float
    answer_type: str = ""
    activity_id: str | None = None
    correct_answer: str | None = None
    accepted_answers: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)


@router.post("/normalize", response_model=AnswerResolutionResult)
async def normalize(payload: SpeechNormalizeRequest) -> AnswerResolutionResult:
    return resolve_answer(
        AnswerResolutionContext(
            transcript=payload.transcript,
            confidence=max(0.0, min(1.0, payload.confidence)),
            answer_type=payload.answer_type,
            correct_answer=payload.correct_answer,
            accepted_answers=payload.accepted_answers,
            options=payload.options,
        )
    )
