"""The AI Teacher: the child's class, run off today's frozen plan.

This began as a sandbox and is not one any more. The schedule is wired straight
into it: one stage per planned item, and finishing a stage hands the level to
the same deterministic scorer the conductor ends a lesson with - so the stars,
the completed level and the next unlock all land on the Adventure map. Finishing
the last stage shuts the class until tomorrow.

The path is still `/playground/teacher/...` so the shipped clients keep working.

`/conductor` remains the older conducted loop and still serves the mobile app.
The web app opens straight into these endpoints, and Adventure teaches nothing
of its own any more: it shows the levels this class has moved.
"""

from fastapi import APIRouter

from app.playground import service
from app.schemas.playground import TeacherAnswerRequest, TeacherAskRequest, TeacherTurnResponse

router = APIRouter(prefix="/playground/teacher", tags=["playground"])


def _response(turn: service.TeacherTurn) -> TeacherTurnResponse:
    return TeacherTurnResponse(**vars(turn))


@router.post("/{child_id}/open", response_model=TeacherTurnResponse)
def open_session(child_id: str) -> TeacherTurnResponse:
    """Start or resume today's class, on whatever the frozen plan is pointing at.

    A day already worked through comes back `day_complete` rather than teaching
    anything: the lock is the server's, so a reload cannot get past it.
    """
    return _response(service.open_session(child_id))


@router.post("/sessions/{session_id}/answer", response_model=TeacherTurnResponse)
def answer(session_id: str, payload: TeacherAnswerRequest) -> TeacherTurnResponse:
    """What the child said. Marked in Python, never by the model.

    A question that does not land is asked again with a hint, and one that still
    does not is answered and explained; either way it is one of the stage's five.
    Five settled questions finish the stage, which marks the level done and
    unlocks the next one; the last stage of the day ends the day.
    """
    return _response(service.answer(session_id, payload.answer))


@router.post("/sessions/{session_id}/ask", response_model=TeacherTurnResponse)
def ask(session_id: str, payload: TeacherAskRequest) -> TeacherTurnResponse:
    """Something the child asked. Answered from the notes; the lesson does not move."""
    return _response(service.ask(session_id, payload.question))


@router.get("/sessions/{session_id}", response_model=TeacherTurnResponse)
def read_session(session_id: str) -> TeacherTurnResponse:
    """The same sitting again, with nothing moved."""
    return _response(service.read_session(session_id))
