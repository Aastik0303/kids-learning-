from pydantic import BaseModel
from app.schemas.child import ChildProfile


class RewardsResponse(BaseModel):
    stars: int
    rewards: list[str]


class CertificateResponse(BaseModel):
    unlocked: bool
    certificate_id: str | None = None
    child_name: str | None = None
    title: str = "Little Learning Explorer Certificate"
    completion_message: str | None = None
    completion_date: str | None = None
    stars_earned: int = 0
    celebration_line: str = "You explored numbers, letters, colours, and shapes!"


class ProgressResponse(BaseModel):
    child: ChildProfile
