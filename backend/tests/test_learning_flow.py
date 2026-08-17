"""Learning and practice over the real manifest.

The shipped curriculum is taxonomy only, so these tests author a small activity
file for a real subject and point the loader at it. That keeps content out of
the repo while still exercising the whole path: unlock, answer, score, unlock
the next topic.
"""

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import curriculum_service
from app.services.mock_storage import mock_certificates

# Play Group Maths: `early` mode, so at most two choices per screen. The first
# two topics teach 1-2-3 then 4-5-6, so the second is what the first unlocks.
SUBJECT_ID = "pg_maths"
FIRST_TOPIC = "pg_maths_number_123"
SECOND_TOPIC = "pg_maths_number_456"


def activity(index: int, correct: str, other: str) -> dict:
    return {
        "activity_id": f"{FIRST_TOPIC}_{index}",
        "type": "identify_colour",
        "prompt": f"Tap {correct}.",
        "visual_items": [correct, other],
        "options": [correct, other],
        "correct_answer": correct,
        "hint": f"{correct} is the bright one.",
    }


@pytest.fixture()
def authored(tmp_path, monkeypatch):
    """Author two topics of Play Group Maths for the duration of one test."""
    activities_dir = tmp_path / "activities"
    activities_dir.mkdir()
    (activities_dir / f"{SUBJECT_ID}.json").write_text(
        json.dumps(
            {
                "subject_id": SUBJECT_ID,
                "topics": {
                    FIRST_TOPIC: [
                        activity(1, "red", "blue"),
                        activity(2, "blue", "red"),
                    ],
                    SECOND_TOPIC: [
                        {
                            "activity_id": "pg_maths_shapes_1",
                            "type": "identify_shape",
                            "prompt": "Tap the circle.",
                            "options": ["circle", "square"],
                            "correct_answer": "circle",
                            "hint": "A circle is round.",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(curriculum_service, "ACTIVITIES_DIR", activities_dir)
    curriculum_service.reload_curriculum()
    yield
    curriculum_service.reload_curriculum()


@pytest.fixture()
def client(authored):
    with TestClient(app) as test_client:
        yield test_client


def make_playgroup_child(client: TestClient, email: str):
    auth = client.post("/auth/register", json={"name": "P", "email": email, "password": "demo1234"})
    if auth.status_code != 200:
        auth = client.post("/auth/login", json={"email": email, "password": "demo1234"})
    token = auth.json()["session_token"]
    child = client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Mira",
            # Two years old today, so the server puts her in Play Group.
            "birth_year": date.today().year - 2,
            "birth_month": date.today().month,
            "preferred_language": "English",
        },
    )
    assert child.json()["class_id"] == "playgroup"
    return token, child.json()["child_id"]


def test_first_topic_of_every_subject_starts_unlocked(client: TestClient):
    _, child_id = make_playgroup_child(client, "unlock@example.com")
    profile = client.get(f"/children/{child_id}").json()
    for subject_id, progress in profile["subject_progress"].items():
        assert len(progress["unlocked_topics"]) == 1, subject_id


def test_completing_a_topic_unlocks_the_next_one(client: TestClient):
    _, child_id = make_playgroup_child(client, "flow@example.com")
    started = client.post("/learning/start", json={"child_id": child_id, "topic_id": FIRST_TOPIC}).json()
    assert started["experience_mode"] == "early"
    assert started["activity_total"] == 2

    first = client.post("/learning/answer", json={"session_id": started["session_id"], "answer": "red"}).json()
    assert first["is_correct"] is True

    second = client.post("/learning/answer", json={"session_id": started["session_id"], "answer": "blue"}).json()
    assert second["is_correct"] is True
    assert second["complete"] is True
    assert second["topic_completed"] is True
    assert second["current_score"] == 100
    assert second["next_topic_id"] == SECOND_TOPIC
    assert second["next_topic_unlocked"] is True

    progress = client.get(f"/children/{child_id}").json()["subject_progress"][SUBJECT_ID]
    assert FIRST_TOPIC in progress["completed_topics"]
    assert SECOND_TOPIC in progress["unlocked_topics"]


def test_a_locked_topic_cannot_be_started(client: TestClient):
    _, child_id = make_playgroup_child(client, "locked@example.com")
    response = client.post("/learning/start", json={"child_id": child_id, "topic_id": SECOND_TOPIC})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LOCKED_STAGE"


def test_a_topic_from_another_class_cannot_be_started(client: TestClient):
    _, child_id = make_playgroup_child(client, "otherclass@example.com")
    response = client.post("/learning/start", json={"child_id": child_id, "topic_id": "ukg_maths_shapes"})
    assert response.status_code == 403


def test_a_topic_with_no_authored_activities_is_honest_not_a_crash(client: TestClient):
    """`nur_maths` has no activity file, so the topic reports itself unready."""
    auth = client.post("/auth/register", json={"name": "P", "email": "soon@example.com", "password": "demo1234"})
    token = auth.json()["session_token"]
    child = client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Ana",
            "birth_year": date.today().year - 3,
            "birth_month": date.today().month,
            "preferred_language": "English",
        },
    ).json()
    assert child["class_id"] == "nursery"

    topic = client.get("/curriculum/topics/nur_maths_shapes").json()
    assert topic["available"] is False
    assert topic["activity_count"] == 0

    response = client.post("/learning/start", json={"child_id": child["child_id"], "topic_id": "nur_maths_shapes"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TOPIC_NOT_READY"


def test_wrong_answers_give_a_hint_then_change_the_question(client: TestClient):
    _, child_id = make_playgroup_child(client, "hint@example.com")
    started = client.post("/learning/start", json={"child_id": child_id, "topic_id": FIRST_TOPIC}).json()
    session_id = started["session_id"]

    first = client.post("/learning/answer", json={"session_id": session_id, "answer": "blue"}).json()
    assert first["is_correct"] is False
    assert first["attempt_number"] == 1
    assert "bright" in first["feedback"]

    for _ in range(2):
        client.post("/learning/answer", json={"session_id": session_id, "answer": "blue"})

    fourth = client.post("/learning/answer", json={"session_id": session_id, "answer": "blue"}).json()
    assert fourth["question_changed"] is True
    assert fourth["attempt_number"] == 0
    assert fourth["recommended_practice"] is True


def test_a_wrong_topic_is_recorded_as_a_weak_skill(client: TestClient):
    _, child_id = make_playgroup_child(client, "weak@example.com")
    started = client.post("/learning/start", json={"child_id": child_id, "topic_id": FIRST_TOPIC}).json()
    for _ in range(4):
        client.post("/learning/answer", json={"session_id": started["session_id"], "answer": "blue"})
    weak = client.get(f"/children/{child_id}").json()["weak_skills"]
    assert f"{SUBJECT_ID}:{FIRST_TOPIC}" in weak


def test_a_spoken_answer_inside_a_phrase_is_accepted(client: TestClient):
    _, child_id = make_playgroup_child(client, "spoken@example.com")
    started = client.post("/learning/start", json={"child_id": child_id, "topic_id": FIRST_TOPIC}).json()
    answered = client.post(
        "/learning/answer", json={"session_id": started["session_id"], "answer": "I think it is the red one"}
    ).json()
    assert answered["is_correct"] is True


def test_practice_offers_only_subjects_with_authored_activities(client: TestClient):
    _, child_id = make_playgroup_child(client, "practice@example.com")
    subjects = {s["subject_id"]: s for s in client.get(f"/practice/subjects/{child_id}").json()}
    assert subjects[SUBJECT_ID]["unlocked"] is True
    assert subjects[SUBJECT_ID]["has_activities"] is True
    # Play Group English has no activity file in this fixture.
    assert subjects["pg_english"]["has_activities"] is False
    assert subjects["pg_english"]["unlocked"] is False


def test_practice_runs_over_introduced_topics(client: TestClient):
    _, child_id = make_playgroup_child(client, "practicerun@example.com")
    session = client.post("/practice/start", json={"child_id": child_id, "subject_id": SUBJECT_ID}).json()
    assert session["subject_title"] == "Early Mathematics"
    assert session["activities"]
    for item in session["activities"]:
        # `early` mode: never more than two choices on a screen.
        assert len(item["options"]) <= 2

    first = session["activities"][0]
    answered = client.post(
        "/practice/answer",
        json={
            "practice_session_id": session["practice_session_id"],
            "activity_id": first["activity_id"],
            "answer": first["correct_answer"],
        },
    ).json()
    assert answered["is_correct"] is True


def test_practice_on_an_unauthored_subject_is_refused_honestly(client: TestClient):
    _, child_id = make_playgroup_child(client, "practicesoon@example.com")
    response = client.post("/practice/start", json={"child_id": child_id, "subject_id": "pg_english"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TOPIC_NOT_READY"


def test_attempts_are_recorded_in_history(client: TestClient):
    _, child_id = make_playgroup_child(client, "history@example.com")
    started = client.post("/learning/start", json={"child_id": child_id, "topic_id": FIRST_TOPIC}).json()
    client.post("/learning/answer", json={"session_id": started["session_id"], "answer": "red"})
    attempts = client.get(f"/history/{child_id}").json()["attempts"]
    assert attempts
    assert attempts[-1]["topic"] == FIRST_TOPIC
    assert attempts[-1]["is_correct"] is True


def test_seed_completes_the_class_and_unlocks_the_certificate(client: TestClient):
    _, child_id = make_playgroup_child(client, "seed@example.com")
    mock_certificates.pop(child_id, None)
    seeded = client.post(f"/dev/seed/{child_id}").json()
    # Only pg_maths has activities in this fixture, and it is fully completed,
    # so every playable topic in the class is done.
    assert seeded["certificate_unlocked"] is True
    certificate = client.get(f"/progress/{child_id}/certificate").json()
    assert certificate["unlocked"] is True
    assert certificate["child_name"] == "Mira"


def test_companion_recommends_the_next_unlocked_topic(client: TestClient):
    _, child_id = make_playgroup_child(client, "companion@example.com")
    response = client.post("/companion/session/start", json={"child_id": child_id, "is_guest": False}).json()
    assert response["recommendation"]["kind"] == "start_next_topic"
    assert response["recommendation"]["topic_id"] == FIRST_TOPIC
    assert response["recommendation"]["route"] == "/adventure"
