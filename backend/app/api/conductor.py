"""The class, as four endpoints.

One endpoint takes every kind of child input - a tap, a spoken answer, a traced
letter, silence, a raised hand. That is deliberate. The same lesson used to be
driven from `learning/answer`, `practice/answer`, `agent/guide` and
`companion/session/event`, three of which decided something about teaching, in
three different ways. The teaching loop lives in one place now, and this is its
front door.
"""

from fastapi import APIRouter

from app.schemas.conductor import ConductorDirective, ConductorInput
from app.services import conductor_service

router = APIRouter(prefix="/conductor", tags=["conductor"])


@router.post("/{child_id}/open", response_model=ConductorDirective)
async def open_class(child_id: str) -> ConductorDirective:
    """Start or resume today's class. The child chooses nothing to get here."""
    return conductor_service.open_class(child_id)


@router.post("/sessions/{session_id}/input", response_model=ConductorDirective)
async def send_input(session_id: str, payload: ConductorInput) -> ConductorDirective:
    return conductor_service.send_input(session_id, payload)


@router.get("/sessions/{session_id}", response_model=ConductorDirective)
async def read_session(session_id: str) -> ConductorDirective:
    """Refresh-safe: the same directive again, with nothing moved."""
    return conductor_service.resume(session_id)


@router.post("/sessions/{session_id}/pause", response_model=ConductorDirective)
async def pause(session_id: str) -> ConductorDirective:
    return conductor_service.pause(session_id)
