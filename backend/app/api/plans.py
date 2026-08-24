"""Today's plan, and the week behind it.

`GET /plans/{child_id}/today` is what the child's home screen shows and what the
background planner has usually already written. Reading it never generates a
second plan: if one is frozen for today it is returned as it is, and if none is
the read freezes one.
"""

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Query

from app.db.repositories import plans as plans_repo
from app.db.session import session_scope
from app.schemas.plan import PlanHistoryEntry, PlanHistoryResponse, PlanItem, TodayPlanResponse
from app.services import child_service, plan_service
from app.services.errors import app_error

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/{child_id}/today", response_model=TodayPlanResponse)
async def today(child_id: str) -> TodayPlanResponse:
    child = child_service.get_child(child_id)
    plan = plan_service.todays_plan(child)
    if plan is None:
        # A class with nothing authored yet, or every unlocked topic finished.
        # An empty plan is an honest answer; the client shows the day as clear.
        return TodayPlanResponse(child_id=child_id, plan_date=date.today(), source="deterministic")

    return TodayPlanResponse(
        child_id=child_id,
        plan_date=plan.plan_date,
        source=plan.source,
        items=[PlanItem(**item) for item in plan.items],
        current_topic_id=plan.current_topic_id,
        completed=plan.completed,
        total=len(plan.items),
        complete=plan.current_topic_id is None and bool(plan.items),
        # Play Group and Nursery only. A child of two or three cannot open their
        # own lesson, and every tap between them and it is a place the day ends
        # early; from LKG the child chooses, and taking that away would be worse
        # than the taps.
        autopilot=child.experience_mode == "early" and plan.current_topic_id is not None,
    )


@router.get("/{child_id}/history", response_model=PlanHistoryResponse)
async def history(child_id: str, days: int = Query(default=30, ge=1, le=90)) -> PlanHistoryResponse:
    child = child_service.get_child(child_id)
    try:
        child_uuid = UUID(child.child_id)
    except ValueError:  # pragma: no cover - a profile with no durable row
        raise app_error("INVALID_CHILD", "We could not find that child profile.", 404) from None

    with session_scope() as session:
        rows = plans_repo.recent_plans(
            session, child_id=child_uuid, since=date.today() - timedelta(days=days)
        )
        return PlanHistoryResponse(
            child_id=child_id,
            plans=[
                PlanHistoryEntry(
                    plan_date=row.plan_date,
                    source=row.source,
                    items=[
                        PlanItem(
                            topic_id=item.topic_id,
                            skill_id=item.skill_id,
                            title=plan_service.topic_title(item.topic_id),
                            reason=item.reason,
                        )
                        for item in row.items
                    ],
                )
                for row in rows
            ],
        )
