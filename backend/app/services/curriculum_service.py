"""The curriculum is manifest-driven.

`data/curriculum/manifest.json` is the single source of truth for the class ->
subject -> topic -> subtopic taxonomy. `data/curriculum/activities/*.json` hold
the authored activities for a subject and are added incrementally; a subject with
no activity file is a valid, incomplete subject, not an error.

The manifest is validated once at startup (see `app.main`). Anything malformed
raises `CurriculumManifestError`, which names the offending file and field, so a
bad edit stops the server instead of reaching a child.

Adding a class, subject or topic is a manifest edit. No code change is required.
"""

import json
import logging
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.curriculum import (
    ClassDetail,
    ClassResolution,
    ClassSummary,
    CurriculumOverview,
    ExperienceMode,
    Subject,
    Topic,
)
from app.schemas.learning import Activity
from app.services import activity_evaluators
from app.services.errors import app_error

logger = logging.getLogger(__name__)

CURRICULUM_DIR = Path(__file__).resolve().parents[1] / "data" / "curriculum"
MANIFEST_PATH = CURRICULUM_DIR / "manifest.json"
ACTIVITIES_DIR = CURRICULUM_DIR / "activities"

# Scoring defaults for a topic that does not override them in the manifest.
DEFAULT_PASSING_SCORE = 80
DEFAULT_STAR_REWARD = 10

# A subject may pin an exact colour. Anything else is a typo that would reach the
# browser as an unstyled card, so it fails the boot instead.
_HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{6}")


class CurriculumManifestError(RuntimeError):
    """Raised when the curriculum on disk is malformed. Fatal at startup."""


def _fail(where: str, problem: str) -> CurriculumManifestError:
    return CurriculumManifestError(f"{where}: {problem}")


def _require(node: Any, key: str, expected: type | tuple[type, ...], where: str) -> Any:
    if key not in node:
        raise _fail(where, f"missing required field '{key}'")
    value = node[key]
    if not isinstance(value, expected) or isinstance(value, bool) and expected is int:
        names = expected.__name__ if isinstance(expected, type) else "/".join(t.__name__ for t in expected)
        raise _fail(where, f"field '{key}' must be {names}, got {type(value).__name__}")
    return value


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------


class _Curriculum:
    """Validated, in-memory curriculum. Built once, then read-only."""

    def __init__(self, raw: dict, activities: dict[str, dict[str, "_AuthoredTopic"]]) -> None:
        self.version: str = raw["version"]
        self.source: str = raw["source"]
        self.notes: list[str] = raw.get("notes", [])
        self.experience_modes: dict[str, ExperienceMode] = {}
        self.classes: list[ClassDetail] = []
        self._by_class: dict[str, ClassDetail] = {}
        self._by_subject: dict[str, Subject] = {}
        self._by_topic: dict[str, Topic] = {}
        self._activities = activities
        self._build(raw)

    def _build(self, raw: dict) -> None:
        for mode_id, mode in raw["experience_modes"].items():
            self.experience_modes[mode_id] = ExperienceMode(mode_id=mode_id, **mode)

        for class_node in sorted(raw["classes"], key=lambda c: c["sort_order"]):
            class_id = class_node["class_id"]
            mode = self.experience_modes[class_node["experience_mode"]]
            subjects: list[Subject] = []

            for subject_node in sorted(class_node["subjects"], key=lambda s: s["sort_order"]):
                subject_id = subject_node["subject_id"]
                authored = self._activities.get(subject_id, {})
                # A subject declares the language it teaches in once; every topic
                # inherits it, so the tutor and the guide can answer in it.
                language = subject_node.get("language", "en")
                topics: list[Topic] = []

                for topic_node in sorted(subject_node["topics"], key=lambda t: t["sort_order"]):
                    entry = authored.get(topic_node["topic_id"])
                    topic_activities = entry.activities if entry else []
                    # Lesson metadata is authored with the content, so a topic
                    # picks it up when its activities land and falls back to the
                    # manifest until then.
                    meta = entry.meta if entry else {}
                    topic = Topic(
                        topic_id=topic_node["topic_id"],
                        subject_id=subject_id,
                        class_id=class_id,
                        title=topic_node["title"],
                        icon=topic_node.get("icon", "⭐"),
                        sort_order=topic_node["sort_order"],
                        subtopics=topic_node["subtopics"],
                        subtopic_icons=topic_node.get("subtopic_icons", []),
                        subtopic_easy=topic_node.get("subtopic_easy", []),
                        easy_line=topic_node.get("easy_line"),
                        activity_count=len(topic_activities),
                        available=bool(topic_activities),
                        passing_score=topic_node.get("passing_score", DEFAULT_PASSING_SCORE),
                        star_reward=meta.get(
                            "star_reward", topic_node.get("star_reward", DEFAULT_STAR_REWARD)
                        ),
                        objective=meta.get("objective") or topic_node.get("objective"),
                        intro_message=meta.get("intro_message") or topic_node.get("intro_message"),
                        delivery=meta.get("delivery", topic_node.get("delivery", "digital")),
                        lesson_flow=meta.get("lesson_flow", topic_node.get("lesson_flow", "sample")),
                        language=topic_node.get("language", language),
                    )
                    topics.append(topic)
                    self._by_topic[topic.topic_id] = topic

                subject = Subject(
                    subject_id=subject_id,
                    class_id=class_id,
                    title=subject_node["title"],
                    fun_name=subject_node.get("fun_name"),
                    language=language,
                    icon=subject_node.get("icon", "📚"),
                    accent=subject_node.get("accent", "leaf"),
                    colour=subject_node.get("colour"),
                    note=subject_node.get("note"),
                    easy_line=subject_node.get("easy_line"),
                    sort_order=subject_node["sort_order"],
                    topic_count=len(topics),
                    subtopic_count=sum(len(t.subtopics) for t in topics),
                    activity_count=sum(t.activity_count for t in topics),
                    available=any(t.available for t in topics),
                    topics=topics,
                )
                subjects.append(subject)
                self._by_subject[subject_id] = subject

            detail = ClassDetail(
                class_id=class_id,
                code=class_node["code"],
                title=class_node["title"],
                subtitle=class_node.get("subtitle"),
                min_age=class_node["min_age"],
                max_age=class_node["max_age"],
                experience_mode=class_node["experience_mode"],
                sort_order=class_node["sort_order"],
                pedagogy=class_node.get("pedagogy"),
                subject_count=len(subjects),
                topic_count=sum(s.topic_count for s in subjects),
                subtopic_count=sum(s.subtopic_count for s in subjects),
                activity_count=sum(s.activity_count for s in subjects),
                experience=mode,
                removed_subjects=class_node.get("removed_subjects", []),
                removed_subject_ids=class_node.get("removed_subject_ids", []),
                subjects=subjects,
            )
            self.classes.append(detail)
            self._by_class[class_id] = detail

    # lookups -------------------------------------------------------------

    def class_ids(self) -> list[str]:
        return [c.class_id for c in self.classes]

    def get_class(self, class_id: str) -> ClassDetail | None:
        return self._by_class.get(class_id)

    def get_subject(self, subject_id: str) -> Subject | None:
        return self._by_subject.get(subject_id)

    def get_topic(self, topic_id: str) -> Topic | None:
        return self._by_topic.get(topic_id)

    def activities_for(self, topic_id: str) -> list[Activity]:
        topic = self._by_topic.get(topic_id)
        if topic is None:
            return []
        entry = self._activities.get(topic.subject_id, {}).get(topic_id)
        return list(entry.activities) if entry else []


def _validate_manifest(raw: Any) -> None:
    """Structural validation. Every failure names where it happened."""
    where = str(MANIFEST_PATH.name)
    if not isinstance(raw, dict):
        raise _fail(where, "top level must be an object")

    _require(raw, "version", str, where)
    _require(raw, "source", str, where)
    modes = _require(raw, "experience_modes", dict, where)
    classes = _require(raw, "classes", list, where)

    if not modes:
        raise _fail(where, "at least one experience mode is required")
    if not classes:
        raise _fail(where, "at least one class is required")

    mode_fields = {
        "touch_target_px": int,
        "max_choices_per_screen": int,
        "text_density": str,
        "voice": str,
    }
    for mode_id, mode in modes.items():
        mode_where = f"{where} experience_modes.{mode_id}"
        if not isinstance(mode, dict):
            raise _fail(mode_where, "must be an object")
        for field, kind in mode_fields.items():
            _require(mode, field, kind, mode_where)
        if mode["touch_target_px"] <= 0:
            raise _fail(mode_where, "touch_target_px must be positive")
        if mode["max_choices_per_screen"] < 2:
            raise _fail(mode_where, "max_choices_per_screen must be at least 2")
        rungs = _require(mode, "idle_thresholds_seconds", list, mode_where)
        if not rungs or any(not isinstance(r, int) or r <= 0 for r in rungs):
            raise _fail(mode_where, "idle_thresholds_seconds must be positive integers")
        if rungs != sorted(rungs):
            raise _fail(mode_where, "idle_thresholds_seconds must be ascending")
        _require(mode, "applies_to", list, mode_where)

    seen_class_ids: set[str] = set()
    seen_subject_ids: set[str] = set()
    seen_topic_ids: set[str] = set()
    seen_sort_orders: set[int] = set()

    for index, class_node in enumerate(classes):
        class_where = f"{where} classes[{index}]"
        if not isinstance(class_node, dict):
            raise _fail(class_where, "must be an object")
        class_id = _require(class_node, "class_id", str, class_where)
        class_where = f"{where} class '{class_id}'"
        if class_id in seen_class_ids:
            raise _fail(class_where, "duplicate class_id")
        seen_class_ids.add(class_id)

        _require(class_node, "code", str, class_where)
        _require(class_node, "title", str, class_where)
        min_age = _require(class_node, "min_age", int, class_where)
        max_age = _require(class_node, "max_age", int, class_where)
        if max_age <= min_age:
            raise _fail(class_where, f"max_age ({max_age}) must be greater than min_age ({min_age})")

        sort_order = _require(class_node, "sort_order", int, class_where)
        if sort_order in seen_sort_orders:
            raise _fail(class_where, f"duplicate sort_order {sort_order}")
        seen_sort_orders.add(sort_order)

        mode_id = _require(class_node, "experience_mode", str, class_where)
        if mode_id not in modes:
            raise _fail(class_where, f"unknown experience_mode '{mode_id}'")
        if class_id not in modes[mode_id].get("applies_to", []):
            raise _fail(class_where, f"experience mode '{mode_id}' does not list this class in applies_to")

        subjects = _require(class_node, "subjects", list, class_where)
        if not subjects:
            raise _fail(class_where, "must have at least one subject")

        subject_sort_orders: set[int] = set()
        for s_index, subject_node in enumerate(subjects):
            subject_where = f"{class_where} subjects[{s_index}]"
            if not isinstance(subject_node, dict):
                raise _fail(subject_where, "must be an object")
            subject_id = _require(subject_node, "subject_id", str, subject_where)
            subject_where = f"{class_where} subject '{subject_id}'"
            if subject_id in seen_subject_ids:
                raise _fail(subject_where, "duplicate subject_id")
            seen_subject_ids.add(subject_id)

            _require(subject_node, "title", str, subject_where)
            if "colour" in subject_node:
                colour = _require(subject_node, "colour", str, subject_where)
                if not _HEX_COLOUR.fullmatch(colour):
                    raise _fail(subject_where, f"colour '{colour}' must be a hex value like #34D399")
            s_sort = _require(subject_node, "sort_order", int, subject_where)
            if s_sort in subject_sort_orders:
                raise _fail(subject_where, f"duplicate sort_order {s_sort} within the class")
            subject_sort_orders.add(s_sort)

            topics = _require(subject_node, "topics", list, subject_where)
            if not topics:
                raise _fail(subject_where, "must have at least one topic")

            topic_sort_orders: set[int] = set()
            for t_index, topic_node in enumerate(topics):
                topic_where = f"{subject_where} topics[{t_index}]"
                if not isinstance(topic_node, dict):
                    raise _fail(topic_where, "must be an object")
                topic_id = _require(topic_node, "topic_id", str, topic_where)
                topic_where = f"{subject_where} topic '{topic_id}'"
                if topic_id in seen_topic_ids:
                    raise _fail(topic_where, "duplicate topic_id")
                seen_topic_ids.add(topic_id)

                _require(topic_node, "title", str, topic_where)
                t_sort = _require(topic_node, "sort_order", int, topic_where)
                if t_sort in topic_sort_orders:
                    raise _fail(topic_where, f"duplicate sort_order {t_sort} within the subject")
                topic_sort_orders.add(t_sort)

                subtopics = _require(topic_node, "subtopics", list, topic_where)
                if not subtopics:
                    raise _fail(topic_where, "must have at least one subtopic")
                for sub in subtopics:
                    if not isinstance(sub, str) or not sub.strip():
                        raise _fail(topic_where, "subtopics must be non-empty strings")

                # Both are optional, but all-or-nothing: a short list would
                # silently pair a subtopic with the icon, or the explanation,
                # that belongs to the one before it.
                for field in ("subtopic_icons", "subtopic_easy"):
                    if field not in topic_node:
                        continue
                    parallel = _require(topic_node, field, list, topic_where)
                    if len(parallel) != len(subtopics):
                        raise _fail(
                            topic_where,
                            f"{field} has {len(parallel)} entries but there are "
                            f"{len(subtopics)} subtopics",
                        )
                    for value in parallel:
                        if not isinstance(value, str) or not value.strip():
                            raise _fail(topic_where, f"{field} must be non-empty strings")

                if "passing_score" in topic_node:
                    score = _require(topic_node, "passing_score", int, topic_where)
                    if not 1 <= score <= 100:
                        raise _fail(topic_where, "passing_score must be between 1 and 100")
                if "star_reward" in topic_node:
                    reward = _require(topic_node, "star_reward", int, topic_where)
                    if reward < 0:
                        raise _fail(topic_where, "star_reward cannot be negative")

    _validate_age_bands(classes, where)

    for mode_id, mode in modes.items():
        unknown = [c for c in mode["applies_to"] if c not in seen_class_ids]
        if unknown:
            raise _fail(f"{where} experience_modes.{mode_id}", f"applies_to names unknown classes {unknown}")


def _validate_age_bands(classes: list[dict], where: str) -> None:
    """Bands must be contiguous and non-overlapping so every age lands in exactly one class."""
    ordered = sorted(classes, key=lambda c: c["sort_order"])
    for previous, current in zip(ordered, ordered[1:]):
        if current["min_age"] != previous["max_age"]:
            raise _fail(
                where,
                f"age bands are not contiguous: class '{previous['class_id']}' ends at "
                f"{previous['max_age']} but '{current['class_id']}' starts at {current['min_age']}",
            )


class _AuthoredTopic:
    """Activities plus the lesson metadata that belongs with the content, not the taxonomy."""

    def __init__(self, activities: list[Activity], meta: dict) -> None:
        self.activities = activities
        self.meta = meta


def _load_activity_files(manifest: dict) -> dict[str, dict[str, _AuthoredTopic]]:
    """Read the authored activity files, validating everything against the taxonomy.

    Two layouts are accepted, told apart by their top-level key:

    - `<class_id>.json`   with `subjects -> topics -> activities`, for authoring
      a whole class in one pass.
    - `<subject_id>.json` with `topics: {topic_id: [...]}`, for filling in one
      subject at a time.
    """
    topics_by_subject: dict[str, set[str]] = {}
    subjects_by_class: dict[str, set[str]] = {}
    class_by_subject: dict[str, str] = {}
    mode_by_class = {c["class_id"]: c["experience_mode"] for c in manifest["classes"]}
    # Subjects deliberately dropped from the published syllabus. Content may
    # still exist for them; it is skipped rather than treated as a typo.
    removed_subject_ids: set[str] = set()
    for class_node in manifest["classes"]:
        subjects_by_class[class_node["class_id"]] = set()
        removed_subject_ids.update(class_node.get("removed_subject_ids", []))
        for subject_node in class_node["subjects"]:
            subject_id = subject_node["subject_id"]
            topics_by_subject[subject_id] = {t["topic_id"] for t in subject_node["topics"]}
            class_by_subject[subject_id] = class_node["class_id"]
            subjects_by_class[class_node["class_id"]].add(subject_id)

    loaded: dict[str, dict[str, _AuthoredTopic]] = {}
    if not ACTIVITIES_DIR.exists():
        return loaded

    def max_choices_for(subject_id: str) -> int:
        return manifest["experience_modes"][mode_by_class[class_by_subject[subject_id]]][
            "max_choices_per_screen"
        ]

    def read_topic(where: str, subject_id: str, topic_id: str, node: dict | list) -> _AuthoredTopic:
        """A topic is either a bare list of activities or an object carrying metadata."""
        if isinstance(node, list):
            activity_nodes, meta = node, {}
        elif isinstance(node, dict):
            activity_nodes = node.get("activities", [])
            meta = node
            if not isinstance(activity_nodes, list):
                raise _fail(f"{where} topic '{topic_id}'", "'activities' must be a list")
        else:
            raise _fail(f"{where} topic '{topic_id}'", "must be a list of activities or an object")

        if topic_id not in topics_by_subject[subject_id]:
            raise _fail(where, f"unknown topic_id '{topic_id}' for subject '{subject_id}'")

        max_choices = max_choices_for(subject_id)
        activities: list[Activity] = []
        seen_ids: set[str] = set()

        for a_index, item in enumerate(activity_nodes):
            a_where = f"{where} topic '{topic_id}' activity[{a_index}]"
            if not isinstance(item, dict):
                raise _fail(a_where, "must be an object")

            activity_type = _require(item, "type", str, a_where)
            if not activity_evaluators.is_registered(activity_type):
                raise _fail(
                    a_where,
                    f"activity type '{activity_type}' has no registered evaluator "
                    f"(registered: {', '.join(activity_evaluators.registered_types())})",
                )
            activity_id = _require(item, "activity_id", str, a_where)
            if activity_id in seen_ids:
                raise _fail(a_where, f"duplicate activity_id '{activity_id}'")
            seen_ids.add(activity_id)

            kind = activity_evaluators.answer_kind(activity_type)
            try:
                activity = Activity(**{**item, "answer_kind": kind})
            except Exception as exc:  # pydantic validation
                raise _fail(a_where, f"invalid activity ({exc})") from exc

            if kind == "choice":
                if not activity.options:
                    raise _fail(a_where, f"type '{activity_type}' requires options")
                if not activity.correct_answer:
                    raise _fail(a_where, f"type '{activity_type}' requires a correct_answer")
                # A match activity may name several right answers, comma-separated.
                expected = [part.strip() for part in activity.correct_answer.split(",")]
                unknown = [part for part in expected if part not in activity.options]
                if unknown:
                    raise _fail(
                        a_where,
                        f"correct_answer {unknown} is not among the options {activity.options}",
                    )
                if len(activity.options) > max_choices:
                    raise _fail(
                        a_where,
                        f"offers {len(activity.options)} choices but this class allows "
                        f"at most {max_choices} per screen",
                    )
            elif kind == "spoken":
                if not activity.correct_answer and not activity.open_ended:
                    raise _fail(
                        a_where,
                        f"type '{activity_type}' needs a correct_answer, or open_ended: true",
                    )

            activities.append(activity)

        return _AuthoredTopic(activities, meta)

    for file_path in sorted(ACTIVITIES_DIR.glob("*.json")):
        where = f"activities/{file_path.name}"
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise _fail(where, f"is not valid JSON ({exc})") from exc
        if not isinstance(raw, dict):
            raise _fail(where, "top level must be an object")

        if "class_id" in raw:
            class_id = _require(raw, "class_id", str, where)
            if class_id not in subjects_by_class:
                raise _fail(where, f"unknown class_id '{class_id}' (not in {MANIFEST_PATH.name})")
            if class_id != file_path.stem:
                raise _fail(where, f"file name must match class_id '{class_id}'")

            for s_index, subject_node in enumerate(_require(raw, "subjects", list, where)):
                if not isinstance(subject_node, dict):
                    raise _fail(f"{where} subjects[{s_index}]", "must be an object")
                subject_id = _require(subject_node, "subject_id", str, f"{where} subjects[{s_index}]")
                if subject_id in removed_subject_ids:
                    # The subject was removed from the curriculum on purpose, so
                    # its authored content is left on disk but never served.
                    logger.info(
                        "Skipping activities for '%s' in %s: the subject was deliberately removed.",
                        subject_id,
                        where,
                    )
                    continue
                if subject_id not in subjects_by_class[class_id]:
                    raise _fail(where, f"subject '{subject_id}' does not belong to class '{class_id}'")
                by_topic = loaded.setdefault(subject_id, {})
                for topic_node in _require(subject_node, "topics", list, f"{where} subject '{subject_id}'"):
                    if not isinstance(topic_node, dict):
                        raise _fail(f"{where} subject '{subject_id}'", "each topic must be an object")
                    topic_id = _require(topic_node, "topic_id", str, f"{where} subject '{subject_id}'")
                    by_topic[topic_id] = read_topic(where, subject_id, topic_id, topic_node)
            continue

        subject_id = _require(raw, "subject_id", str, where)
        if subject_id not in topics_by_subject:
            raise _fail(where, f"unknown subject_id '{subject_id}' (not in {MANIFEST_PATH.name})")
        if subject_id != file_path.stem:
            raise _fail(where, f"file name must match subject_id '{subject_id}'")

        by_topic = loaded.setdefault(subject_id, {})
        for topic_id, node in _require(raw, "topics", dict, where).items():
            by_topic[topic_id] = read_topic(where, subject_id, topic_id, node)

    return loaded


@lru_cache(maxsize=1)
def _curriculum() -> _Curriculum:
    if not MANIFEST_PATH.exists():
        raise _fail(str(MANIFEST_PATH), "curriculum manifest is missing")
    try:
        raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _fail(MANIFEST_PATH.name, f"is not valid JSON ({exc})") from exc

    _validate_manifest(raw)
    activities = _load_activity_files(raw)
    return _Curriculum(raw, activities)


def load_curriculum() -> _Curriculum:
    """Called at startup so a malformed curriculum fails the boot, not a request."""
    return _curriculum()


def reload_curriculum() -> _Curriculum:
    """Drop the cache and re-read from disk. Used by tests."""
    _curriculum.cache_clear()
    return _curriculum()


# --------------------------------------------------------------------------
# read API
# --------------------------------------------------------------------------


def overview() -> CurriculumOverview:
    curriculum = _curriculum()
    return CurriculumOverview(
        version=curriculum.version,
        source=curriculum.source,
        classes=[ClassSummary(**c.model_dump(exclude={"experience", "subjects", "removed_subjects"})) for c in curriculum.classes],
        experience_modes=curriculum.experience_modes,
    )


def list_classes() -> list[ClassSummary]:
    return overview().classes


def get_class(class_id: str) -> ClassDetail:
    detail = _curriculum().get_class(class_id)
    if detail is None:
        raise app_error("MISSING_CURRICULUM", "That class is not available.", 404)
    return detail


def get_subject(subject_id: str) -> Subject:
    subject = _curriculum().get_subject(subject_id)
    if subject is None:
        raise app_error("MISSING_CURRICULUM", "That subject is not available.", 404)
    return subject


def get_topic(topic_id: str) -> Topic:
    topic = _curriculum().get_topic(topic_id)
    if topic is None:
        raise app_error("MISSING_CURRICULUM", "That topic is not available.", 404)
    return topic


def get_activities(topic_id: str) -> list[Activity]:
    get_topic(topic_id)
    return _curriculum().activities_for(topic_id)


def experience_mode_for_class(class_id: str) -> ExperienceMode:
    return get_class(class_id).experience


def class_ids() -> list[str]:
    return _curriculum().class_ids()


# --------------------------------------------------------------------------
# age -> class
# --------------------------------------------------------------------------


def age_years(birth_year: int, birth_month: int, today: date | None = None) -> float:
    """Age in years from a birth month. Derived on the server, never sent by the client."""
    today = today or date.today()
    if not 1 <= birth_month <= 12:
        raise app_error("INVALID_BIRTH_DATE", "That birth month does not look right.", 400)
    months = (today.year - birth_year) * 12 + (today.month - birth_month)
    if months < 0:
        raise app_error("INVALID_BIRTH_DATE", "That birth date is in the future.", 400)
    return round(months / 12, 4)


def resolve_class(age: float) -> str:
    """Map an age in years to a class using the manifest's bands.

    Bands are validated as contiguous, so this is exactly the rule in OP-07 5:
    below 3 -> playgroup, below 4 -> nursery, below 5 -> lkg, otherwise ukg.
    Ages below the youngest band get the youngest class; ages above the oldest
    band get the oldest, so no child is ever left without a class.
    """
    classes = _curriculum().classes
    for detail in classes:
        if age < detail.max_age:
            return detail.class_id
    return classes[-1].class_id


def resolve_class_for_child(
    birth_year: int | None,
    birth_month: int | None,
    override: str | None = None,
    today: date | None = None,
) -> ClassResolution:
    if birth_year is None or birth_month is None:
        raise app_error("MISSING_BIRTH_DATE", "We need a birth month to pick the right class.", 400)

    age = age_years(birth_year, birth_month, today)
    default_class_id = resolve_class(age)
    if override and override != default_class_id:
        if override not in class_ids():
            raise app_error("MISSING_CURRICULUM", "That class is not available.", 404)
        if not is_adjacent_class(default_class_id, override):
            raise app_error(
                "CLASS_NOT_ADJACENT",
                "A class can only be changed to the one just below or just above.",
                400,
            )
        return ClassResolution(
            class_id=override,
            age_years=age,
            resolved_from="parent_override",
            overridden=True,
            default_class_id=default_class_id,
        )

    return ClassResolution(
        class_id=default_class_id,
        age_years=age,
        resolved_from="birth_date",
        overridden=False,
        default_class_id=default_class_id,
    )


def is_adjacent_class(class_id: str, candidate: str) -> bool:
    order = class_ids()
    if class_id not in order or candidate not in order:
        return False
    return abs(order.index(class_id) - order.index(candidate)) == 1


def adjacent_class_ids(class_id: str) -> list[str]:
    """The classes a parent may switch a child to. Never exposed to the child."""
    order = class_ids()
    if class_id not in order:
        return []
    index = order.index(class_id)
    return [order[i] for i in (index - 1, index + 1) if 0 <= i < len(order)]
