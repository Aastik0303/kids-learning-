"""The treasure bag, derived from the child's own ledger.

`data/rewards.json` has always described a shelf of badges; nothing read it, so
the Rewards screen showed whatever list `child["rewards"]` happened to hold and
the milestones were decoration. They are computed here instead, and computed
rather than stored: a badge is a *statement about* the ledger - this many stars,
this many subjects finished - so deriving it on every read means it can never
drift from the stars a parent can see, and no migration is needed to add one.

This is deterministic on purpose. Which badges a child has earned is on the same
list as scoring and unlocking: pure Python over the ledger, never a model.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from app.schemas.child import ChildProfile


REWARDS_PATH = Path(__file__).resolve().parents[1] / "data" / "rewards.json"

# Milestones whose evidence the ledger actually holds. The file also describes
# streak, practice-count and login-streak badges; those are left out rather than
# faked, because nothing counts them yet and a badge that cannot be earned is
# worse than one that is not offered.
STAR_MILESTONES = ("first_star", "ten_stars", "twenty_five_stars", "fifty_stars")


@dataclass(frozen=True)
class Badge:
    badge_id: str
    title: str
    description: str
    earned: bool
    # What is left to do, worded for the grown-up reading it aloud. None once earned.
    progress_hint: str | None


def _catalogue() -> dict:
    return json.loads(REWARDS_PATH.read_text(encoding="utf-8"))


def _stars_to_go(remaining: int) -> str:
    return "1 more star to go." if remaining == 1 else f"{remaining} more stars to go."


def _star_badges(stars: int, catalogue: dict) -> list[Badge]:
    badges: list[Badge] = []
    for badge_id in STAR_MILESTONES:
        entry = catalogue["milestone_badges"].get(badge_id)
        if not entry:
            continue
        threshold = int(entry["threshold"])
        earned = stars >= threshold
        remaining = threshold - stars
        badges.append(
            Badge(
                badge_id=badge_id,
                title=entry["title"],
                description=entry["description"],
                earned=earned,
                progress_hint=None if earned else _stars_to_go(remaining),
            )
        )
    return badges


def _subject_badges(child: ChildProfile) -> list[Badge]:
    """One badge per subject the child has finished.

    `learning_service` already appends "<Subject> Explorer" to the ledger when a
    subject completes, so these are read back rather than recomputed - the
    lesson that finished the subject is what awarded them.
    """
    return [
        Badge(
            badge_id=f"earned:{title}",
            title=title,
            description="Finished every topic in this world.",
            earned=True,
            progress_hint=None,
        )
        for title in child.rewards
    ]


def _worlds_to_go(remaining: int) -> str:
    return "1 more world to finish." if remaining == 1 else f"{remaining} more worlds to finish."


def _paths_badge(child: ChildProfile, catalogue: dict) -> Badge | None:
    entry = catalogue["milestone_badges"].get("all_paths_complete")
    if not entry:
        return None
    finished = len(child.completed_subjects)
    total = len(child.subject_progress) or int(entry["threshold"])
    earned = finished >= total > 0
    return Badge(
        badge_id="all_paths_complete",
        title=entry["title"],
        description=entry["description"],
        earned=earned,
        progress_hint=None if earned else _worlds_to_go(total - finished),
    )


def badges_for(child: ChildProfile) -> list[Badge]:
    """Earned badges first, then the ones still waiting."""
    catalogue = _catalogue()
    badges = _subject_badges(child) + _star_badges(child.stars, catalogue)
    paths = _paths_badge(child, catalogue)
    if paths:
        badges.append(paths)
    return sorted(badges, key=lambda badge: not badge.earned)
