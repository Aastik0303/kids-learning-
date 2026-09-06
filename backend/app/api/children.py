from fastapi import APIRouter, Depends

from app.schemas.child import ChildCreateRequest, ChildProfile, ChildUpdateRequest
from app.api.deps import required_token
from app.services import child_service

router = APIRouter(prefix="/children", tags=["children"])


@router.post("", response_model=ChildProfile)
def create_child(payload: ChildCreateRequest) -> ChildProfile:
    return child_service.create_child(payload)


@router.get("", response_model=list[ChildProfile])
def list_children(token: str = Depends(required_token)) -> list[ChildProfile]:
    return child_service.list_children(token)


@router.get("/{child_id}", response_model=ChildProfile)
def get_child(child_id: str) -> ChildProfile:
    return child_service.get_child(child_id)


@router.patch("/{child_id}", response_model=ChildProfile)
def update_child(child_id: str, payload: ChildUpdateRequest) -> ChildProfile:
    return child_service.update_child(child_id, payload)
