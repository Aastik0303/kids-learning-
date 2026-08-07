from fastapi import APIRouter

from app.schemas.practice import PracticeAnswerRequest, PracticeAnswerResponse, PracticeStartRequest, PracticeStartResponse, PracticeTopic
from app.services import practice_service

router = APIRouter(prefix="/practice", tags=["practice"])


@router.get("/topics/{child_id}", response_model=list[PracticeTopic])
async def topics(child_id: str) -> list[PracticeTopic]:
    return practice_service.topics_for_child(child_id)


@router.post("/start", response_model=PracticeStartResponse)
async def start(payload: PracticeStartRequest) -> PracticeStartResponse:
    return practice_service.start_practice(payload)


@router.post("/answer", response_model=PracticeAnswerResponse)
async def answer(payload: PracticeAnswerRequest) -> PracticeAnswerResponse:
    return practice_service.answer_practice(payload)
