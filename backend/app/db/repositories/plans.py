"""The daily plan, and the freeze that makes it a routine.

A plan is generated once per `(child_id, plan_date)` and read every time after
that. Refresh, re-login and back-navigation all take the read path. Without the
freeze the Planner Agent produces a slightly different plan on every load, and a
three-year-old never gets the same lesson twice in a row - which is the opposite
of what a routine is.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db.models import Child, DailyPlan, DailyPlanItem


@dataclass(frozen=True)
class PlannedItem:
    topic_id: str
    skill_id: str
    reason: str = "new"


def plan_for(session: Session, *, child_id: UUID, plan_date: date) -> DailyPlan | None:
    return session.scalar(
        select(DailyPlan)
        .options(selectinload(DailyPlan.items))
        .where(DailyPlan.child_id == child_id, DailyPlan.plan_date == plan_date)
    )


def freeze_plan(
    session: Session,
    *,
    child_id: UUID,
    plan_date: date,
    items: Sequence[PlannedItem],
    source: str = "deterministic",
) -> DailyPlan:
    """Write the plan, or return the one already frozen for that day.

    The unique constraint, not this read, is what actually guarantees one plan
    per day: two requests can both find nothing and both try to write. The
    IntegrityError path is the real freeze, and it returns the winner's plan
    rather than raising, because from the child's side either plan is the plan.
    """
    existing = plan_for(session, child_id=child_id, plan_date=plan_date)
    if existing is not None:
        return existing

    plan = DailyPlan(child_id=child_id, plan_date=plan_date, source=source)
    plan.items = [
        DailyPlanItem(position=index, topic_id=item.topic_id, skill_id=item.skill_id, reason=item.reason)
        for index, item in enumerate(items)
    ]
    session.add(plan)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        winner = plan_for(session, child_id=child_id, plan_date=plan_date)
        if winner is None:  # pragma: no cover - only if the constraint is gone
            raise
        return winner
    return plan


def recent_plans(session: Session, *, child_id: UUID, since: date, limit: int = 60) -> list[DailyPlan]:
    """The child's plans from `since` onwards, newest first.

    The parent surface reads this to see what the week actually looked like -
    and, because `source` travels with each row, how much of it the Planner
    Agent decided rather than the deterministic fallback.
    """
    return list(
        session.scalars(
            select(DailyPlan)
            .options(selectinload(DailyPlan.items))
            .where(DailyPlan.child_id == child_id, DailyPlan.plan_date >= since)
            .order_by(DailyPlan.plan_date.desc())
            .limit(limit)
        ).all()
    )


def children_missing_a_plan(session: Session, *, plan_date: date, limit: int = 500) -> list[UUID]:
    """Every child with no plan frozen for that date.

    This is what the background planner sweeps. It is a small anti-join rather
    than "load every child and check": the whole point of running it on a timer
    is that it costs nothing on the days it finds nothing to do.
    """
    planned = select(DailyPlan.child_id).where(DailyPlan.plan_date == plan_date)
    return list(
        session.scalars(
            select(Child.id).where(Child.id.not_in(planned)).order_by(Child.created_at).limit(limit)
        ).all()
    )


def plan_cursor(plan: DailyPlan, *, completed_topic_ids: set[str]) -> DailyPlanItem | None:
    """The next item the child has not finished, in plan order."""
    for item in plan.items:
        if item.topic_id not in completed_topic_ids:
            return item
    return None
