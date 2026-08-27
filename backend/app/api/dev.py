from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.services.errors import app_error
from app.services.learning_service import seed_demo_child

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/seed/{child_id}")
def seed(child_id: str, settings: Settings = Depends(get_settings)) -> dict:
    if settings.env != "development":
        raise app_error("DEV_ONLY", "Demo seeding is only available in development.", 403)
    return seed_demo_child(child_id)
