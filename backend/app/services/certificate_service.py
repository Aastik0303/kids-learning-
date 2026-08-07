from app.schemas.progress import CertificateResponse
from app.services.child_service import get_child
from app.services.mock_storage import mock_certificates


def get_certificate(child_id: str) -> CertificateResponse:
    child = get_child(child_id)
    cert = mock_certificates.get(child_id)
    if not child.certificate_unlocked or not cert:
        return CertificateResponse(unlocked=False, stars_earned=child.stars)
    return CertificateResponse(**cert)
