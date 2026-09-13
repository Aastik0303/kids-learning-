"""Development-only fixtures.

Not mounted outside development - see `app/main.py`. Nothing here is part of
the product: it exists so a developer, and the test suite, can reach the late
screens without playing every level by hand.
"""

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.services.errors import app_error
from app.services.learning_service import complete_every_topic

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/seed/{child_id}")
def seed(child_id: str, settings: Settings = Depends(get_settings)) -> dict:
    """Fast-forward a child through every playable topic in their class.

    Checked here as well as at mount time. Two gates rather than one, because
    the cost of this being reachable by mistake is a child's real progress
    ledger rewritten.
    """
    if settings.env.lower() != "development":
        raise app_error("DEV_ONLY", "This is not available.", 403)
    return complete_every_topic(child_id)
