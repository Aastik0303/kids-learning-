from fastapi import APIRouter

from app.schemas.progress import CertificateResponse, ProgressResponse, RewardsResponse
from app.services import certificate_service, child_service

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/{child_id}", response_model=ProgressResponse)
async def progress(child_id: str) -> ProgressResponse:
    return ProgressResponse(child=child_service.get_child(child_id))


@router.get("/{child_id}/rewards", response_model=RewardsResponse)
async def rewards(child_id: str) -> RewardsResponse:
    child = child_service.get_child(child_id)
    return RewardsResponse(stars=child.stars, rewards=child.rewards)


@router.get("/{child_id}/certificate", response_model=CertificateResponse)
async def certificate(child_id: str) -> CertificateResponse:
    return certificate_service.get_certificate(child_id)
