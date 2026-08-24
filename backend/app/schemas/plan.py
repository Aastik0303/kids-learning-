"""The daily plan, as the client reads it."""

from datetime import date

from pydantic import BaseModel


class PlanItem(BaseModel):
    topic_id: str
    skill_id: str
    title: str
    # 'new', 'revisit' or 'prerequisite' - why this item is in today's plan.
    # Stored rather than re-derived, so the reason a parent is shown is the
    # reason the planner actually had.
    reason: str = "new"
    done: bool = False
    current: bool = False


class TodayPlanResponse(BaseModel):
    child_id: str
    plan_date: date
    # 'planner_agent' or 'deterministic'. The client shows the plan the same way
    # either way; this is here so a week of plans can be read back and the
    # agent's contribution separated from the fallback's.
    source: str = "deterministic"
    items: list[PlanItem] = []
    current_topic_id: str | None = None
    completed: int = 0
    total: int = 0
    # Every item done. The client stops offering new work and shows the day as
    # finished: what comes next is tomorrow's plan, not the next level.
    complete: bool = False
    # Whether the app should open today's lesson by itself instead of waiting to
    # be tapped. True only for Play Group and Nursery, and only while the day
    # still has work in it. The client never decides this: a two-year-old cannot
    # navigate, but a five-year-old can and should.
    autopilot: bool = False


class PlanHistoryEntry(BaseModel):
    plan_date: date
    source: str
    items: list[PlanItem] = []


class PlanHistoryResponse(BaseModel):
    child_id: str
    plans: list[PlanHistoryEntry] = []
