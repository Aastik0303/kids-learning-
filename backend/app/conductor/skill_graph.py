"""Which skill has to come before which.

A child failing "count to five" may not have a problem with five. They may not
have three. Re-explaining five four times to a child who does not have three is
four wasted explanations and one discouraged child, which is why the branch
engine checks the foundation before it reaches the repair ladder.

The graph is an authored data file - `app/data/curriculum/skill_graph.json` -
and not a table, for the same reason the curriculum is a file: it is content. It
should be reviewable in a pull request, diffable, and versioned with the
activities it describes. A model does not write it, because a hallucinated
prerequisite sends a child backwards for no reason.

It ships empty. An empty graph is a graph that never fires the PREREQUISITE
branch, which is exactly right: an invented prerequisite is worse than none, so
this waits for a real curriculum author. The loader validates whatever is there
at startup, the same way the activity loader rejects an unregistered type.
"""

import json
from functools import lru_cache
from pathlib import Path

from app.services.errors import app_error
from app.services import cache


GRAPH_PATH = Path(__file__).resolve().parents[1] / "data" / "curriculum" / "skill_graph.json"


def _fail(detail: str):
    return app_error("INVALID_SKILL_GRAPH", f"skill_graph.json: {detail}", 500)


def _detect_cycle(edges: dict[str, list[str]]) -> list[str] | None:
    """A cycle means "learn A before B before A", which is a lesson that can
    never start. Better to refuse at boot than to loop in front of a child."""
    visiting: set[str] = set()
    done: set[str] = set()
    trail: list[str] = []

    def walk(node: str) -> list[str] | None:
        if node in done:
            return None
        if node in visiting:
            return [*trail, node]
        visiting.add(node)
        trail.append(node)
        for parent in edges.get(node, ()):
            found = walk(parent)
            if found:
                return found
        trail.pop()
        visiting.discard(node)
        done.add(node)
        return None

    for skill in edges:
        found = walk(skill)
        if found:
            return found
    return None


@lru_cache(maxsize=1)
def _graph() -> dict[str, list[str]]:
    if not GRAPH_PATH.exists():
        return {}
    try:
        raw = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _fail(f"is not valid JSON ({exc})") from exc

    prerequisites = raw.get("prerequisites", {})
    if not isinstance(prerequisites, dict):
        raise _fail("'prerequisites' must be an object of skill_id -> [skill_id]")

    edges: dict[str, list[str]] = {}
    for skill_id, parents in prerequisites.items():
        if not isinstance(parents, list) or any(not isinstance(parent, str) for parent in parents):
            raise _fail(f"{skill_id}: prerequisites must be a list of skill ids")
        if skill_id in parents:
            raise _fail(f"{skill_id}: a skill cannot be its own prerequisite")
        edges[skill_id] = list(parents)

    cycle = _detect_cycle(edges)
    if cycle:
        raise _fail(f"prerequisite cycle: {' -> '.join(cycle)}")
    return edges


def load_skill_graph() -> dict[str, list[str]]:
    """Validate and return the graph. Called at startup so a bad file is a boot
    failure with the offending skill named, not a broken lesson."""
    return _graph()


def reload_skill_graph() -> dict[str, list[str]]:
    _graph.cache_clear()
    return _graph()


cache.register("conductor.skill_graph", _graph.cache_clear)


def prerequisites_of(skill_id: str) -> list[str]:
    return list(_graph().get(skill_id, ()))


def weakest_prerequisite(skill_id: str, mastery: dict[str, float]) -> tuple[str | None, float | None]:
    """The prerequisite this child holds least well, and how well.

    Returns `(None, None)` when the skill has no authored prerequisites, which
    the branch engine reads as "no opinion" rather than as "the foundation is
    fine" - the difference matters, because an unauthored graph must not send
    every struggling child backwards.
    """
    parents = prerequisites_of(skill_id)
    if not parents:
        return None, None
    weakest = min(parents, key=lambda parent: mastery.get(parent, 0.0))
    return weakest, mastery.get(weakest, 0.0)


__all__ = [
    "GRAPH_PATH",
    "load_skill_graph",
    "prerequisites_of",
    "reload_skill_graph",
    "weakest_prerequisite",
]
