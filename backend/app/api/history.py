from fastapi import APIRouter

from app.schemas.history import HistoryResponse
from app.services import history_service

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/{child_id}", response_model=HistoryResponse)
def history(child_id: str) -> HistoryResponse:
    return history_service.history_for_child(child_id)
