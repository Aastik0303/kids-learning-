from fastapi import APIRouter

from app.schemas.learning import LearningAnswerRequest, LearningResponse, LearningStartRequest, PathSummary, Stage
from app.services import curriculum_service, learning_service

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/paths", response_model=list[PathSummary])
async def list_paths() -> list[PathSummary]:
    return curriculum_service.list_paths()


@router.get("/paths/{path_id}")
async def get_path(path_id: str) -> dict:
    return curriculum_service.get_path(path_id)


@router.get("/paths/{path_id}/stages", response_model=list[Stage])
async def get_stages(path_id: str) -> list[Stage]:
    return curriculum_service.get_stages(path_id)


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
