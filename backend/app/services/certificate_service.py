"""The class certificate, read back from the durable table.

Eligibility is not decided here and never by a model: `child_service.
refresh_certificate_eligibility` checks that every playable topic in the class
is complete, in pure Python, and `learning_service` issues the row when it is.
This module only reads.
"""

from uuid import UUID

from app.db.repositories import awards
from app.db.session import session_scope
from app.schemas.progress import CertificateResponse
from app.services import curriculum_service
from app.services.child_service import get_child


def get_certificate(child_id: str) -> CertificateResponse:
    child = get_child(child_id)
    if not child.certificate_unlocked:
        return CertificateResponse(unlocked=False, stars_earned=child.stars)

    with session_scope() as session:
        row = awards.certificate_for(session, child_id=UUID(child.child_id), subject_id=child.class_id)
        if row is None:
            return CertificateResponse(unlocked=False, stars_earned=child.stars)
        detail = curriculum_service.get_class(child.class_id)
        return CertificateResponse(
            unlocked=True,
            certificate_id=str(row.id),
            child_name=child.name,
            completion_message=row.title or f"Completed the {detail.title} curriculum",
            completion_date=row.issued_at.date().isoformat(),
            stars_earned=child.stars,
        )
