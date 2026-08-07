from app.schemas.child import ChildCreateRequest, ChildProfile, ChildUpdateRequest, PathProgress
from app.services.errors import app_error
from app.services.mock_auth import get_user_for_token
from app.services.mock_storage import mock_child_profiles


CORE_PATHS = ["numbers", "alphabets", "colours", "shapes"]


def _default_progress() -> dict[str, dict]:
    progress = {path: PathProgress(unlocked_stages=[]).model_dump() for path in CORE_PATHS + ["mixed_final"]}
    progress["numbers"] = PathProgress(unlocked_stages=[1]).model_dump()
    return progress


def create_child(payload: ChildCreateRequest) -> ChildProfile:
    user = get_user_for_token(payload.session_token)
    child_id = f"child_{len(mock_child_profiles) + 101}"
    child = {
        "child_id": child_id,
        "user_id": user["id"],
        "name": payload.name,
        "age_group": payload.age_group,
        "preferred_language": payload.preferred_language,
        "stars": 0,
        "current_path": "numbers",
        "current_stage": 1,
        "completed_paths": [],
        "path_progress": _default_progress(),
        "weak_skills": [],
        "rewards": [],
        "mixed_path_unlocked": False,
        "certificate_unlocked": False,
    }
    mock_child_profiles[child_id] = child
    return ChildProfile(**child)


def list_children(session_token: str) -> list[ChildProfile]:
    user = get_user_for_token(session_token)
    return [ChildProfile(**child) for child in mock_child_profiles.values() if child["user_id"] == user["id"]]


def get_child(child_id: str) -> ChildProfile:
    child = mock_child_profiles.get(child_id)
    if not child:
        raise app_error("INVALID_CHILD", "We could not find that child profile.", 404)
    return ChildProfile(**child)


def update_child(child_id: str, payload: ChildUpdateRequest) -> ChildProfile:
    user = get_user_for_token(payload.session_token)
    child = mock_child_profiles.get(child_id)
    if not child or child["user_id"] != user["id"]:
        raise app_error("INVALID_CHILD", "We could not find that child profile.", 404)
    for field in ["name", "age_group", "preferred_language"]:
        value = getattr(payload, field)
        if value is not None:
            child[field] = value
    return ChildProfile(**child)


def unlock_mixed_if_ready(child: dict) -> None:
    if all(path in child["completed_paths"] for path in CORE_PATHS):
        child["mixed_path_unlocked"] = True
        progress = child["path_progress"].setdefault("mixed_final", PathProgress().model_dump())
        progress["unlocked_stages"] = [1]
