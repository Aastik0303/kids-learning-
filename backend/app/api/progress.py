from fastapi import APIRouter

from app.schemas.progress import BadgeState, CertificateResponse, ProgressResponse, RewardsResponse
from app.services import certificate_service, child_service, rewards_service

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/{child_id}", response_model=ProgressResponse)
def progress(child_id: str) -> ProgressResponse:
    return ProgressResponse(child=child_service.get_child(child_id))


@router.get("/{child_id}/rewards", response_model=RewardsResponse)
def rewards(child_id: str) -> RewardsResponse:
    child = child_service.get_child(child_id)
    return RewardsResponse(
        stars=child.stars,
        rewards=child.rewards,
        badges=[BadgeState(**vars(badge)) for badge in rewards_service.badges_for(child)],
    )


@router.get("/{child_id}/certificate", response_model=CertificateResponse)
def certificate(child_id: str) -> CertificateResponse:
    return certificate_service.get_certificate(child_id)
