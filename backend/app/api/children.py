from fastapi import APIRouter, Header

from app.schemas.child import ChildCreateRequest, ChildProfile, ChildUpdateRequest
from app.services import child_service

router = APIRouter(prefix="/children", tags=["children"])


@router.post("", response_model=ChildProfile)
async def create_child(payload: ChildCreateRequest) -> ChildProfile:
    return child_service.create_child(payload)


@router.get("", response_model=list[ChildProfile])
async def list_children(x_demo_session: str = Header()) -> list[ChildProfile]:
    return child_service.list_children(x_demo_session)


@router.get("/{child_id}", response_model=ChildProfile)
async def get_child(child_id: str) -> ChildProfile:
    return child_service.get_child(child_id)


@router.patch("/{child_id}", response_model=ChildProfile)
async def update_child(child_id: str, payload: ChildUpdateRequest) -> ChildProfile:
    return child_service.update_child(child_id, payload)
