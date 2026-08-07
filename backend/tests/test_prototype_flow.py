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


def make_toddler(client: TestClient):
    auth = client.post(
        "/auth/register",
        json={"name": "Toddler Parent", "email": "toddler@example.com", "password": "demo1234"},
    )
    if auth.status_code != 200:
        auth = client.post("/auth/login", json={"email": "toddler@example.com", "password": "demo1234"})
    token = auth.json()["session_token"]
    child = client.post(
        "/children",
        json={"session_token": token, "name": "Mira", "age_group": "2 years", "age": 2, "preferred_language": "English"},
    )
    return token, child.json()["child_id"]


def test_register_login_and_create_child(client: TestClient):
    token, child_id = make_child(client)
    assert token.startswith("demo-")
    child = client.get(f"/children/{child_id}")
    assert child.status_code == 200
    assert child.json()["name"] == "Aaru"


def test_age_mode_resolution_and_child_profile_mode(client: TestClient):
    toddler_mode = client.post("/toddler/mode", json={"age": 2})
    standard_mode = client.post("/toddler/mode", json={"age": 3})
    assert toddler_mode.json()["learning_mode"] == "toddler"
    assert standard_mode.json()["learning_mode"] == "standard"

    _, child_id = make_toddler(client)
    child = client.get(f"/children/{child_id}").json()
    assert child["age"] == 2
    assert child["learning_mode"] == "toddler"


def test_toddler_correct_and_close_speech_answers_award_stars(client: TestClient):
    _, child_id = make_toddler(client)
    start = client.post("/toddler/start", json={"child_id": child_id, "module": "alphabets", "level": 1})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    intro = client.post("/toddler/answer", json={"session_id": session_id, "answer": "A"})
    assert intro.json()["evaluation"]["result"] == "correct"

    repeat = client.post("/toddler/answer", json={"session_id": session_id, "recognized_speech": "ay"})
    assert repeat.json()["evaluation"]["result"] == "correct"
    assert repeat.json()["stars_earned"] == 1
    assert repeat.json()["total_stars"] >= 2


def test_toddler_retry_then_level_completion_unlocks_next_level(client: TestClient):
    _, child_id = make_toddler(client)
    start = client.post("/toddler/start", json={"child_id": child_id, "module": "alphabets", "level": 1})
    session_id = start.json()["session_id"]
    client.post("/toddler/answer", json={"session_id": session_id, "answer": "A"})
    client.post("/toddler/answer", json={"session_id": session_id, "recognized_speech": "ay"})

    retry = client.post("/toddler/answer", json={"session_id": session_id, "answer": "A"})
    assert retry.json()["evaluation"]["result"] == "retry"
    assert retry.json()["guide"]["target"] == "B"

    client.post("/toddler/answer", json={"session_id": session_id, "answer": "B"})
    complete = client.post("/toddler/answer", json={"session_id": session_id, "recognized_speech": "see"})
    body = complete.json()
    assert body["level_completed"] is True
    assert body["next_level_unlocked"] is True
    assert body["guide"]["action"] == "complete_level"

    progress = client.get(f"/progress/{child_id}").json()["child"]["path_progress"]["toddler"]
    assert 1 in progress["completed_stages"]
    assert 2 in progress["unlocked_stages"]


def test_toddler_guide_uses_safe_structured_targets(client: TestClient):
    _, child_id = make_toddler(client)
    response = client.post(
        "/agent/guide",
        json={
            "session_id": "session_toddler",
            "child_id": child_id,
            "mode": "learning",
            "event": "LEVEL_ANSWER_INCORRECT",
            "route": "/toddler",
            "screen": "toddler_lesson",
            "feature": "alphabets",
            "age": 2,
            "learning_mode": "toddler",
            "toddler": {
                "learning_mode": "toddler",
                "age": 2,
                "module": "alphabets",
                "level": 1,
                "concept": "A",
                "activity_type": "repeat_after_me",
                "expected_answer": "A",
                "recognized_speech": "",
                "attempt_count": 1,
                "stars": 1,
                "recent_result": "unclear",
            },
            "available_actions": ["highlight"],
            "available_targets": ["toddler-microphone", "toddler-choices"],
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert body["strategy"] == "hint"
    assert body["ui_action"]["target"] == "toddler-microphone"
    assert "Almost" in body["message"]


def test_learning_wrong_hint_then_stage_completion_unlocks_next_stage(client: TestClient):
    _, child_id = make_child(client)
    start = client.post("/learning/start", json={"child_id": child_id, "path_id": "numbers", "stage_number": 1})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    wrong = client.post("/learning/answer", json={"session_id": session_id, "answer": "2"})
    assert wrong.json()["is_correct"] is False
    assert wrong.json()["attempt_number"] == 1
    assert "one apple" in wrong.json()["feedback"]

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

    start = client.post("/learning/start", json={"child_id": child_id, "path_id": "mixed_final", "stage_number": 2})
    session_id = start.json()["session_id"]
    for answer in ["4", "Dog", "star"]:
        result = client.post("/learning/answer", json={"session_id": session_id, "answer": answer})
    assert result.json()["stage_completed"] is True

    start = client.post("/learning/start", json={"child_id": child_id, "path_id": "mixed_final", "stage_number": 3})
    session_id = start.json()["session_id"]
    for answer in ["5", "Fish", "two yellow stars"]:
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


def test_speech_normalize_resolves_browser_transcript_without_audio(client: TestClient):
    response = client.post(
        "/speech/normalize",
        json={
            "session_id": "session_1",
            "activity_id": "activity_1",
            "answer_type": "count_objects",
            "transcript": "tree",
            "confidence": 0.54,
            "correct_answer": "3",
            "accepted_answers": ["3", "three"],
            "options": ["2", "3", "4"],
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert body["raw_transcript"] == "tree"
    assert body["normalized"] == "3"
    assert body["resolved_answer"] == "3"
    assert body["resolution_confidence"] >= 0.9


def test_speech_normalize_marks_empty_transcript_ambiguous(client: TestClient):
    response = client.post(
        "/speech/normalize",
        json={"activity_id": "activity_1", "answer_type": "count_objects", "transcript": "", "confidence": 0, "correct_answer": "3", "options": ["2", "3", "4"]},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["ambiguous"] is True


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
                "learning_objective": "Count three visible apples one at a time.",
                "prompt": "How many apples are there?",
                "answer_type": "count_objects",
                "options": ["2", "3", "4"],
                "correct_answer": "3",
                "child_answer": "2",
                "attempt": 1,
                "hint": "Count each apple only once.",
                "visual_items": ["apple", "apple", "apple"],
                "accepted_answers": ["3", "three"],
                "recent_answers": ["2"],
            },
            "available_actions": ["show_hint", "highlight"],
            "available_targets": ["counting-object-group", "voice-answer-area"],
            "allowed_visual_targets": ["visual-item-0", "visual-item-1", "visual-item-2"],
        },
    )
    body = wrong.json()
    assert wrong.status_code == 200
    assert body["strategy"] == "hint"
    assert len(body["message"].split()) <= 22
    assert body["ui_action"]["target"] == "counting-object-group"
    assert body["visual_action"]["type"] == "highlight_sequence"
    assert body["visual_action"]["targets"] == ["visual-item-0", "visual-item-1", "visual-item-2"]


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


def test_guide_rejects_invalid_visual_target(client: TestClient):
    response = client.post(
        "/agent/guide",
        json={
            "mode": "practice",
            "event": "PRACTICE_QUESTION_LOADED",
            "route": "/practice/numbers",
            "screen": "practice_session",
            "feature": "numbers_practice",
            "question": {"activity_id": "a1", "prompt": "How many apples?", "visual_items": ["apple"]},
            "available_actions": ["highlight"],
            "available_targets": ["question-area"],
            "allowed_visual_targets": ["#unsafe"],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSAFE_VISUAL_TARGET"


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
