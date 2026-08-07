import json
from functools import lru_cache
from pathlib import Path

from app.schemas.learning import PathSummary, Stage
from app.services.errors import app_error

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


PATH_META = {
    "numbers": ("Numbers", "Count, recognize, and match tiny number groups."),
    "alphabets": ("Alphabets", "Meet letters and starting sounds."),
    "colours": ("Colours", "Name and match bright nursery colours."),
    "shapes": ("Shapes", "Spot simple shapes in friendly objects."),
    "mixed_final": ("Mixed Final Path", "A gentle review that mixes all skills."),
}


@lru_cache
def _load_path(path_id: str) -> list[Stage]:
    file_path = DATA_DIR / f"{path_id}_path.json"
    if not file_path.exists():
        raise app_error("MISSING_CURRICULUM", "That learning path is not available.", 404)
    data = json.loads(file_path.read_text(encoding="utf-8"))
    return [Stage(**stage) for stage in data["stages"]]


def list_paths() -> list[PathSummary]:
    summaries = []
    for path_id, (title, description) in PATH_META.items():
        summaries.append(
            PathSummary(
                path_id=path_id,
                title=title,
                description=description,
                total_stages=len(_load_path(path_id)),
            )
        )
    return summaries


def get_path(path_id: str) -> dict:
    title, description = PATH_META.get(path_id, (path_id.title(), ""))
    return {"path_id": path_id, "title": title, "description": description, "stages": _load_path(path_id)}


def get_stages(path_id: str) -> list[Stage]:
    return _load_path(path_id)


def get_stage(path_id: str, stage_number: int) -> Stage:
    for stage in _load_path(path_id):
        if stage.stage_number == stage_number:
            return stage
    raise app_error("MISSING_CURRICULUM", "That stage is not available.", 404)
