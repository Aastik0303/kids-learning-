from fastapi import APIRouter

from app.schemas.guide import GuideRequest, GuideResponse
from app.services.guide_agent_service import guide

router = APIRouter(prefix="/agent", tags=["guide-agent"])


@router.post("/guide", response_model=GuideResponse)
def guide_agent(payload: GuideRequest) -> GuideResponse:
    return guide(payload)
