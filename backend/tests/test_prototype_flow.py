from fastapi.testclient import TestClient
import pytest

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def make_child(client: TestClient):
    auth = client.post(
        "/auth/register",
        json={"name": "Test Parent", "email": "parent@example.com", "password": "demo1234"},
    )
    if auth.status_code != 200:
        auth = client.post("/auth/login", json={"email": "parent@example.com", "password": "demo1234"})
    token = auth.json()["session_token"]
    child = client.post(
        "/children",
        json={"session_token": token, "name": "Aaru", "age_group": "4-5", "preferred_language": "English"},
    )
    return token, child.json()["child_id"]


def test_register_login_and_create_child(client: TestClient):
    token, child_id = make_child(client)
    assert token.startswith("demo-")
    child = client.get(f"/children/{child_id}")
    assert child.status_code == 200
    assert child.json()["name"] == "Aaru"


def test_learning_wrong_hint_then_stage_completion_unlocks_next_stage(client: TestClient):
    _, child_id = make_child(client)
    start = client.post("/learning/start", json={"child_id": child_id, "path_id": "numbers", "stage_number": 1})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    wrong = client.post("/learning/answer", json={"session_id": session_id, "answer": "2"})
    assert wrong.json()["is_correct"] is False
    assert wrong.json()["attempt_number"] == 1
    assert "Good try" in wrong.json()["feedback"]

    for answer in ["1", "1", "1"]:
        result = client.post("/learning/answer", json={"session_id": session_id, "answer": answer})
    body = result.json()
    assert body["stage_completed"] is True
    assert body["next_stage_unlocked"] is True

    progress = client.get(f"/progress/{child_id}").json()["child"]
    assert 2 in progress["path_progress"]["numbers"]["unlocked_stages"]
    assert progress["stars"] > 0


def test_locked_stage_is_blocked(client: TestClient):
    _, child_id = make_child(client)
    response = client.post("/learning/start", json={"child_id": child_id, "path_id": "numbers", "stage_number": 3})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LOCKED_STAGE"


def test_future_world_is_blocked_until_previous_world_complete(client: TestClient):
    _, child_id = make_child(client)
    response = client.post("/learning/start", json={"child_id": child_id, "path_id": "alphabets", "stage_number": 1})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LOCKED_STAGE"


def test_companion_welcome_recommends_safe_continue_action(client: TestClient):
    _, child_id = make_child(client)
    response = client.post("/companion/session/start", json={"child_id": child_id, "current_route": "/", "is_guest": False})
    body = response.json()
    assert response.status_code == 200
    assert "Continue Adventure" in body["message"]
    assert body["guidance"]["action"] == "highlight_element"
    assert body["guidance"]["target_id"] == "continue-adventure"
    assert body["guidance"]["wait_for_child_click"] is True


def test_seed_unlocks_mixed_path_and_final_unlocks_certificate(client: TestClient):
    _, child_id = make_child(client)
    seeded = client.post(f"/dev/seed/{child_id}")
    assert seeded.status_code == 200
    assert seeded.json()["mixed_path_unlocked"] is True

    start = client.post("/learning/start", json={"child_id": child_id, "path_id": "mixed_final", "stage_number": 1})
    session_id = start.json()["session_id"]
    for answer in ["three red circles", "Apple", "2"]:
        result = client.post("/learning/answer", json={"session_id": session_id, "answer": answer})
    assert result.json()["stage_completed"] is True

    certificate = client.get(f"/progress/{child_id}/certificate")
    assert certificate.json()["unlocked"] is True
    assert certificate.json()["certificate_id"].startswith("cert_")


def test_practice_topics_and_answer(client: TestClient):
    _, child_id = make_child(client)
    topics = client.get(f"/practice/topics/{child_id}")
    assert topics.status_code == 200
    assert topics.json()[0]["unlocked"] is True

    session = client.post("/practice/start", json={"child_id": child_id, "topic": "numbers"})
    activity = session.json()["activities"][0]
    assert session.json()["selection_reason"] == "introduced_skills"
    answer = client.post(
        "/practice/answer",
        json={
            "practice_session_id": session.json()["practice_session_id"],
            "activity_id": activity["activity_id"],
            "answer": activity["correct_answer"],
        },
    )
    assert answer.json()["is_correct"] is True


def test_voice_number_words_are_normalized_before_practice_evaluation(client: TestClient):
    _, child_id = make_child(client)
    session = client.post("/practice/start", json={"child_id": child_id, "topic": "numbers"})
    activity = next(item for item in session.json()["activities"] if item["correct_answer"] == "1")
    answer = client.post(
        "/practice/answer",
        json={
            "practice_session_id": session.json()["practice_session_id"],
            "activity_id": activity["activity_id"],
            "answer": "number one",
        },
    )
    assert answer.status_code == 200
    assert answer.json()["is_correct"] is True


def test_speech_transcribe_discards_audio_and_returns_transcript(client: TestClient):
    response = client.post(
        "/speech/transcribe",
        files={"audio": ("answer.webm", b"temporary audio", "audio/webm")},
        data={"session_id": "session_1", "activity_id": "activity_1", "answer_type": "select_number", "transcript": "number three", "confidence": "0.94"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["transcript"] == "number three"
    assert body["normalized"] == "3"
    assert body["confidence"] == 0.94


def test_single_guide_app_open_and_wrong_attempt_contract(client: TestClient):
    _, child_id = make_child(client)
    app_open = client.post(
        "/agent/guide",
        json={
            "session_id": "session_101",
            "child_id": child_id,
            "mode": "welcome",
            "event": "APP_OPENED",
            "route": "/",
            "screen": "home",
            "feature": "home",
            "progress": {"current_world": "numbers", "current_level": "Level 1", "session_stars": 0},
            "available_actions": ["highlight", "wait_for_click"],
            "available_targets": ["continue-adventure", "start-practice"],
        },
    )
    assert app_open.status_code == 200
    assert app_open.json()["strategy"] == "welcome"
    assert app_open.json()["ui_action"] == {"type": "highlight", "target": "continue-adventure"}

    wrong = client.post(
        "/agent/guide",
        json={
            "session_id": "session_101",
            "child_id": child_id,
            "mode": "practice",
            "event": "PRACTICE_ANSWER_INCORRECT",
            "route": "/practice/numbers",
            "screen": "practice_session",
            "feature": "numbers_practice",
            "question": {
                "activity_id": "numbers_count_3_apples_001",
                "topic": "numbers",
                "concept": "counting_3",
                "prompt": "How many apples are there?",
                "options": ["2", "3", "4"],
                "correct_answer": "3",
                "child_answer": "2",
                "attempt": 1,
            },
            "available_actions": ["show_hint", "highlight"],
            "available_targets": ["counting-object-group", "voice-answer-area"],
        },
    )
    body = wrong.json()
    assert wrong.status_code == 200
    assert body["strategy"] == "hint"
    assert len(body["message"].split()) <= 20
    assert body["ui_action"]["target"] == "counting-object-group"


def test_guide_rejects_invalid_target(client: TestClient):
    response = client.post(
        "/agent/guide",
        json={
            "mode": "help",
            "event": "GUIDE_HELP_REQUESTED",
            "route": "/guide",
            "screen": "guide_help",
            "feature": "help",
            "available_actions": ["highlight"],
            "available_targets": ["#admin-panel"],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSAFE_GUIDE_TARGET"


def test_answer_attempt_history_is_stored_after_backend_evaluation(client: TestClient):
    _, child_id = make_child(client)
    start = client.post("/practice/start", json={"child_id": child_id, "topic": "numbers"})
    activity = start.json()["activities"][0]
    answer = client.post(
        "/practice/answer",
        json={
            "practice_session_id": start.json()["practice_session_id"],
            "activity_id": activity["activity_id"],
            "answer": "not the answer",
        },
    )
    assert answer.json()["is_correct"] is False

    history = client.get(f"/history/{child_id}")
    attempts = history.json()["attempts"]
    assert history.status_code == 200
    assert attempts[-1]["activity_id"] == activity["activity_id"]
    assert attempts[-1]["is_correct"] is False
    assert attempts[-1]["attempt_number"] == 1
