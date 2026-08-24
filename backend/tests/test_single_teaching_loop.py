"""One teaching loop, and one attempt log underneath every path into it.

The conductor is the teaching loop now. `/learning` and `/practice` are the
pre-conductor way in and still serve the shipped clients, so they cannot simply
be deleted - but two loops that both grade answers is exactly how two different
ideas of "was this right?" end up in one product.

These tests pin the two things that keep that from happening: the old routes are
marked deprecated so nobody builds anything new on them, and every path that
takes a child's answer writes it through the same attempt log.
"""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.main import app


LEGACY_PREFIXES = ("/learning", "/practice")

ANSWER_PATHS = (
    Path("app/services/learning_service.py"),
    Path("app/services/practice_service.py"),
    Path("app/services/conductor_service.py"),
)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_the_pre_conductor_routes_are_marked_deprecated(client: TestClient):
    schema = client.get("/openapi.json").json()

    legacy = {
        path: operations
        for path, operations in schema["paths"].items()
        if path.startswith(LEGACY_PREFIXES)
    }
    assert legacy, "the legacy lesson routes have moved; update this test with them"
    for path, operations in legacy.items():
        for method, operation in operations.items():
            assert operation.get("deprecated") is True, f"{method.upper()} {path} is not marked deprecated"


def test_the_conductor_route_is_not_deprecated(client: TestClient):
    """The replacement has to be the one that is not marked."""
    schema = client.get("/openapi.json").json()
    conductor = [path for path in schema["paths"] if path.startswith("/conductor")]

    assert conductor
    for path in conductor:
        for operation in schema["paths"][path].values():
            assert operation.get("deprecated") is not True


def test_every_answer_path_writes_the_same_attempt_log():
    """A new way of taking an answer must go through `history_service`.

    That is what puts the answer in `attempts` and rolls it into
    `skill_mastery`. A path that graded an answer and kept the result to itself
    would leave mastery, unlocking and the policy reward reading a partial
    history and never say so.
    """
    for path in ANSWER_PATHS:
        source = path.read_text(encoding="utf-8")
        assert "record_attempt" in source, f"{path} takes answers but does not write the attempt log"
        assert "activity_evaluators" in source, f"{path} takes answers but does not use the evaluator"


def test_no_answer_path_decides_correctness_with_a_model():
    """The one rule that never moves, checked where a child's answer is graded."""
    for path in ANSWER_PATHS:
        source = path.read_text(encoding="utf-8")
        assert "from app.ai" not in source, f"{path} must not reach a model"
        assert "import httpx" not in source, f"{path} must not reach the network"
