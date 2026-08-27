from pydantic import BaseModel
from app.schemas.child import ChildProfile


class BadgeState(BaseModel):
    badge_id: str
    title: str
    description: str
    earned: bool
    # Wording for what is still missing; None once the badge is earned.
    progress_hint: str | None = None


class RewardsResponse(BaseModel):
    stars: int
    rewards: list[str]
    # The whole shelf, earned and unearned. `rewards` stays as it was so an
    # older client keeps working.
    badges: list[BadgeState] = []


class CertificateResponse(BaseModel):
    unlocked: bool
    certificate_id: str | None = None
    child_name: str | None = None
    title: str = "Saksham IQ Explorer Certificate"
    completion_message: str | None = None
    completion_date: str | None = None
    stars_earned: int = 0
    celebration_line: str = "You explored numbers, letters, colours, and shapes!"


class ProgressResponse(BaseModel):
    child: ChildProfile
