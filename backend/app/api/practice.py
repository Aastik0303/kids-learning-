"""Practice sessions, the pre-conductor way.

Deprecated. The teaching loop lives in `POST /conductor/sessions/{id}/input`:
one endpoint that evaluates, commits, decides the branch and returns the next
directive. These routes stay because the web and mobile clients still call them,
and they are marked deprecated in the OpenAPI schema so that stays visible.

They are not a second answer to "was this right?". Correctness comes from
`activity_evaluators` here exactly as it does in the conductor, and every answer
lands in the same `attempts` table through `history_service`, so the two paths
cannot drift on the thing that matters. What is duplicated is the *loop* - the
attempt counting and the progression - and that is what retires when the clients
move.
"""

from fastapi import APIRouter

from app.schemas.practice import (
    PracticeAnswerRequest,
    PracticeAnswerResponse,
    PracticeStartRequest,
    PracticeStartResponse,
    PracticeSubject,
)
from app.services import practice_service

router = APIRouter(prefix="/practice", tags=["practice"], deprecated=True)


@router.get("/subjects/{child_id}", response_model=list[PracticeSubject])
def subjects(child_id: str) -> list[PracticeSubject]:
    return practice_service.subjects_for_child(child_id)


@router.post("/start", response_model=PracticeStartResponse)
def start(payload: PracticeStartRequest) -> PracticeStartResponse:
    return practice_service.start_practice(payload)


@router.post("/answer", response_model=PracticeAnswerResponse)
def answer(payload: PracticeAnswerRequest) -> PracticeAnswerResponse:
    return practice_service.answer_practice(payload)
