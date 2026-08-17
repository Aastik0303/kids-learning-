from fastapi import APIRouter

from app.schemas.practice import (
    PracticeAnswerRequest,
    PracticeAnswerResponse,
    PracticeStartRequest,
    PracticeStartResponse,
    PracticeSubject,
)
from app.services import practice_service

router = APIRouter(prefix="/practice", tags=["practice"])


@router.get("/subjects/{child_id}", response_model=list[PracticeSubject])
async def subjects(child_id: str) -> list[PracticeSubject]:
    return practice_service.subjects_for_child(child_id)


@router.post("/start", response_model=PracticeStartResponse)
async def start(payload: PracticeStartRequest) -> PracticeStartResponse:
    return practice_service.start_practice(payload)


@router.post("/answer", response_model=PracticeAnswerResponse)
async def answer(payload: PracticeAnswerRequest) -> PracticeAnswerResponse:
    return practice_service.answer_practice(payload)
