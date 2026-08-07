from fastapi import APIRouter

from app.schemas.toddler import (
    ModeResolutionRequest,
    ModeResolutionResponse,
    ToddlerAnswerRequest,
    ToddlerLevel,
    ToddlerModuleSummary,
    ToddlerResponse,
    ToddlerStartRequest,
)
from app.services import toddler_service

router = APIRouter(prefix="/toddler", tags=["toddler"])


@router.post("/mode", response_model=ModeResolutionResponse)
async def resolve_mode(payload: ModeResolutionRequest) -> ModeResolutionResponse:
    return toddler_service.resolve_mode(payload.age)


@router.get("/modules", response_model=list[ToddlerModuleSummary])
async def modules() -> list[ToddlerModuleSummary]:
    return toddler_service.list_modules()


@router.get("/curriculum/{module}", response_model=list[ToddlerLevel])
async def curriculum(module: str) -> list[ToddlerLevel]:
    return toddler_service.get_levels(module)


@router.post("/start", response_model=ToddlerResponse)
async def start(payload: ToddlerStartRequest) -> ToddlerResponse:
    return toddler_service.start_toddler(payload)


@router.post("/answer", response_model=ToddlerResponse)
async def answer(payload: ToddlerAnswerRequest) -> ToddlerResponse:
    return toddler_service.answer_toddler(payload.session_id, payload.answer, payload.recognized_speech)
