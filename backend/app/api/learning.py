"""Topic lessons, the pre-conductor way.

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

from app.schemas.learning import LearningAnswerRequest, LearningResponse, LearningStartRequest
from app.services import learning_service

router = APIRouter(prefix="/learning", tags=["learning"], deprecated=True)


@router.post("/start", response_model=LearningResponse)
async def start(payload: LearningStartRequest) -> LearningResponse:
    return learning_service.start_learning(payload)


@router.post("/answer", response_model=LearningResponse)
async def answer(payload: LearningAnswerRequest) -> LearningResponse:
    return learning_service.answer_learning(payload)


@router.post("/retry/{session_id}", response_model=LearningResponse)
async def retry(session_id: str) -> LearningResponse:
    return learning_service.retry_learning(session_id)


@router.post("/continue/{session_id}", response_model=LearningResponse)
async def continue_session(session_id: str) -> LearningResponse:
    return learning_service.continue_learning(session_id)


@router.get("/session/{session_id}", response_model=LearningResponse)
async def get_session(session_id: str) -> LearningResponse:
    return learning_service.continue_learning(session_id)
