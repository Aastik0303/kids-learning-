from typing import Literal

from app.schemas.child import ChildProfile
from app.services import curriculum_service


WORLD_ORDER = ["numbers", "alphabets", "colours", "shapes", "mixed_final"]
WORLD_NAMES = {
    "numbers": "Number Kingdom",
    "alphabets": "Alphabet Forest",
    "colours": "Colour Garden",
    "shapes": "Shape Island",
    "mixed_final": "Mixed Magic Castle",
}

RecommendationKind = Literal[
    "start_next_level",
    "recommended_practice",
    "open_certificate",
    "show_safe_choices",
]


def _total(path_id: str) -> int:
    return len(curriculum_service.get_stages(path_id))


def _completed_count(child: ChildProfile, path_id: str) -> int:
    progress = child.path_progress.get(path_id)
    return len(progress.completed_stages) if progress else 0


def path_complete(child: ChildProfile, path_id: str) -> bool:
    return path_id in child.completed_paths or _completed_count(child, path_id) >= _total(path_id)


def next_path_and_stage(child: ChildProfile) -> tuple[str | None, int | None]:
    for path_id in WORLD_ORDER:
        if path_id == "mixed_final" and not child.mixed_path_unlocked:
            return None, None
        if path_complete(child, path_id):
            continue
        progress = child.path_progress.get(path_id)
        completed = set(progress.completed_stages if progress else [])
        for stage_number in range(1, _total(path_id) + 1):
            if stage_number not in completed:
                return path_id, stage_number
    return None, None


def choose_recommendation(child: ChildProfile | None) -> dict:
    if child is None:
        return {
            "kind": "start_next_level",
            "path_id": "numbers",
            "stage_number": 1,
            "target_id": "continue-adventure",
            "route": "/levels",
            "label": "Continue Adventure",
        }

    if child.certificate_unlocked:
        return {
            "kind": "open_certificate",
            "path_id": None,
            "stage_number": None,
            "target_id": "open-certificate",
            "route": "/certificate",
            "label": "Open Certificate",
        }

    path_id, stage_number = next_path_and_stage(child)
    if path_id and stage_number:
        return {
            "kind": "start_next_level",
            "path_id": path_id,
            "stage_number": stage_number,
            "target_id": "continue-adventure",
            "route": "/levels",
            "label": "Continue Adventure",
        }

    if child.weak_skills:
        return {
            "kind": "recommended_practice",
            "path_id": "numbers",
            "stage_number": None,
            "target_id": "start-practice",
            "route": "/practice",
            "label": "Start Practice",
        }

    return {
        "kind": "show_safe_choices",
        "path_id": None,
        "stage_number": None,
        "target_id": "start-practice",
        "route": "/practice",
        "label": "Start Practice",
    }


def welcome_message(child: ChildProfile | None, recommendation: dict) -> str:
    if child is None:
        return "Hello! Welcome to Little Learning. Let us begin with Number Kingdom."

    name = child.name or "Explorer"
    path_id = recommendation.get("path_id")
    stage_number = recommendation.get("stage_number")
    if recommendation["kind"] == "open_certificate":
        return f"Welcome back, {name}! Your certificate is ready."
    if path_id and stage_number:
        completed = max(stage_number - 1, 0)
        world_name = WORLD_NAMES.get(path_id, "your adventure")
        if completed:
            return f"Welcome back, {name}! Last time you completed {world_name} Level {completed}. Today, let us start Level {stage_number}."
        return f"Hello, {name}! Let us begin with {world_name}."
    return f"Welcome back, {name}! Let us start a short practice."
