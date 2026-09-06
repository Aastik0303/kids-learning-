"""Certificates, which are earned and therefore have to be remembered.

A certificate is issued by the deterministic completion check in
`learning_service` - every playable topic in the class finished - and by nothing
else. It used to live in a dictionary, so a child who finished a whole class
lost the certificate when the server restarted, which is the one thing in the
app a four-year-old would actually notice going missing.

The unique constraint on `(child_id, subject_id)` is what makes issuing
idempotent: finishing the last topic twice does not produce two certificates.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Certificate


def certificate_for(session: Session, *, child_id: UUID, subject_id: str) -> Certificate | None:
    return session.scalar(
        select(Certificate).where(Certificate.child_id == child_id, Certificate.subject_id == subject_id)
    )


def issue(session: Session, *, child_id: UUID, subject_id: str, title: str) -> Certificate:
    existing = certificate_for(session, child_id=child_id, subject_id=subject_id)
    if existing is not None:
        return existing

    certificate = Certificate(child_id=child_id, subject_id=subject_id, title=title)
    session.add(certificate)
    try:
        session.flush()
    except IntegrityError:
        # Two requests finished the last topic at once. Either row is the
        # certificate; the child gets one.
        session.rollback()
        winner = certificate_for(session, child_id=child_id, subject_id=subject_id)
        if winner is None:  # pragma: no cover - only if the constraint is gone
            raise
        return winner
    return certificate


