"""Guide, companion and speech behaviour.

Curriculum-specific flows live in test_curriculum.py and test_learning_flow.py.
What is left here is the part of the app that does not care which topic a child
is on: the guide agent's safety contract and speech normalization.
"""

from datetime import date

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.schemas.guide import GuideRequest
from app.services.guide_agent_service import _fallback_guide, _validate_model_response


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
        json={
            "session_token": token,
            "name": "Aaru",
            "birth_year": date.today().year - 4,
            "birth_month": 6,
            "preferred_language": "English",
        },
    )
    return token, child.json()["child_id"]


def test_guide_help_answers_question_and_accepts_conversation_context():
    payload = GuideRequest(
        session_id="guide_test",
        child_id="guest_child",
        mode="help",
        event="GUIDE_HELP_REQUESTED",
        route="/guide",
        screen="guide_help",
        feature="What is a circle?",
        conversation=[
            {"role": "user", "content": "Can you help with shapes?"},
            {"role": "assistant", "content": "Yes. Which shape?"},
            {"role": "user", "content": "What is a circle?"},
        ],
        available_actions=["none"],
        available_targets=[],
    )

    response = _fallback_guide(payload)

    assert response.strategy == "help"
    assert response.ui_action.type == "none"
    assert "round" in response.message.lower()

    model_response = _validate_model_response(
        payload,
        '{"message":"A circle is round and has no corners.","strategy":"help","avatar":{"state":"calm","message":"Sure","speak":"softly","animationEffect":"smile"}}',
    )
    assert model_response.message == "A circle is round and has no corners."
    assert model_response.avatar.state == "speaking"


def test_guide_help_uses_current_activity_context_for_spoken_confusion():
    payload = GuideRequest(
        session_id="learning_test",
        child_id="guest_child",
        mode="help",
        event="GUIDE_HELP_REQUESTED",
        route="/levels/alphabets/1",
        screen="learning_activity",
        feature="I don't understand this",
        question={
            "activity_id": "letter_a",
            "topic": "alphabets",
            "concept": "select_letter",
            "prompt": "Which letter starts apple?",
            "answer_type": "select_letter",
            "options": ["A", "B", "C"],
            "hint": "Apple starts with the sound A.",
            "attempt": 0,
        },
        available_actions=["none"],
        available_targets=[],
    )

    response = _fallback_guide(payload)

    assert response.strategy == "help"
    assert "apple starts with the sound a" in response.message.lower()


def test_guide_acknowledges_clear_but_irrelevant_activity_response():
    payload = GuideRequest(
        session_id="practice_test",
        child_id="guest_child",
        mode="help",
        event="GUIDE_HELP_REQUESTED",
        route="/practice/numbers",
        screen="practice_session",
        feature="banana car",
        question={
            "activity_id": "numbers_guest_03",
            "topic": "pg_maths",
            "concept": "multiple_choice",
            "prompt": "Two blocks and one more block make how many?",
            "answer_type": "multiple_choice",
            "options": ["1", "3", "5"],
            "correct_answer": "3",
            "hint": "Touch each block: one, two, three.",
            "attempt": 0,
        },
        available_actions=["none"],
        available_targets=[],
    )

    fallback = _fallback_guide(payload)
    model = _validate_model_response(payload, '{"message":"Let us count the blocks together."}')

    assert "i heard you" in fallback.message.lower()
    assert "does not answer this question" in fallback.message.lower()
    assert "i heard you" in model.message.lower()
    assert "one, two, three" in model.message.lower()


def test_register_login_and_create_child(client: TestClient):
    token, child_id = make_child(client)
    assert token.startswith("demo-")
    child = client.get(f"/children/{child_id}")
    assert child.status_code == 200
    assert child.json()["name"] == "Aaru"


def test_companion_welcome_recommends_safe_continue_action(client: TestClient):
    _, child_id = make_child(client)
    response = client.post("/companion/session/start", json={"child_id": child_id, "current_route": "/", "is_guest": False})
    body = response.json()
    assert response.status_code == 200
    assert body["message"]
    assert body["guidance"]["action"] == "highlight_element"
    assert body["guidance"]["target_id"] == "continue-adventure"
    assert body["guidance"]["wait_for_child_click"] is True


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


def test_speech_normalize_resolves_letter_example_phrase(client: TestClient):
    response = client.post(
        "/speech/normalize",
        json={
            "session_id": "session_letters",
            "activity_id": "activity_a",
            "answer_type": "multiple_choice",
            "transcript": "a start with apple",
            "confidence": 0.74,
            "correct_answer": "A",
            "accepted_answers": ["A"],
            "options": ["A", "B", "C"],
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert body["raw_transcript"] == "a start with apple"
    assert body["normalized"] == "a"
    assert body["resolved_answer"] == "a"
    assert body["matched_candidate"] == "A"


def test_speech_normalize_preserves_a_spoken_letter_a(client: TestClient):
    response = client.post(
        "/speech/normalize",
        json={
            "session_id": "speech_letter_a",
            "activity_id": "abc-repeat-a",
            "answer_type": "repeat_after_me",
            "transcript": "A",
            "confidence": 0.86,
            "correct_answer": "A",
            "accepted_answers": ["A", "ay", "hey"],
            "options": [],
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["normalized"] == "a"
    assert body["resolved_answer"] == "a"
    assert body["input_kind"] == "answer"
    assert body["matched_candidate"] == "A"


def test_speech_normalize_treats_out_of_option_number_as_clear_answer(client: TestClient):
    response = client.post(
        "/speech/normalize",
        json={
            "session_id": "session_2",
            "activity_id": "numbers_guest_03",
            "answer_type": "multiple_choice",
            "transcript": "two blocks",
            "confidence": 0.32,
            "correct_answer": "3",
            "accepted_answers": ["3"],
            "options": ["1", "3", "5"],
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["resolved_answer"] == "2"
    assert body["input_kind"] == "answer"
    assert body["ambiguous"] is False
    assert body["matched_candidate"] is None


def test_speech_normalize_marks_irrelevant_words_unresolved(client: TestClient):
    response = client.post(
        "/speech/normalize",
        json={
            "activity_id": "numbers_guest_03",
            "answer_type": "multiple_choice",
            "transcript": "banana car",
            "confidence": 0.91,
            "correct_answer": "3",
            "options": ["1", "3", "5"],
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["input_kind"] == "unresolved"
    assert body["matched_candidate"] is None


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
            "progress": {"current_subject": "Basic Mathematics", "current_topic": "Colours", "session_stars": 0},
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
            "route": "/practice/pg_maths",
            "screen": "practice_session",
            "feature": "pg_maths_practice",
            "question": {
                "activity_id": "numbers_count_3_apples_001",
                "topic": "pg_maths",
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
    assert body["ui_action"]["target"] == "voice-answer-area"
    assert "count" not in body["message"].lower()
    assert "one, two, three" not in body["message"].lower()
    assert body["visual_action"] == {"type": "none", "targets": []}


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


def test_counting_help_counts_aloud_and_highlights_each_item(client: TestClient):
    response = client.post(
        "/agent/guide",
        json={
            "session_id": "counting_help",
            "mode": "help",
            "event": "GUIDE_HELP_REQUESTED",
            "route": "/practice/pg_maths",
            "screen": "practice_session",
            "feature": "I don't understand. Show me and count each item with me.",
            "question": {
                "activity_id": "count_three_apples",
                "topic": "pg_maths",
                "concept": "counting_3",
                "prompt": "How many apples are there?",
                "answer_type": "count_objects",
                "options": ["2", "3", "4"],
                "correct_answer": "3",
                "hint": "Count each apple once.",
                "visual_items": ["apple", "apple", "apple"],
                "attempt": 0,
            },
            "available_actions": ["highlight", "show_hint", "repeat_instruction"],
            "available_targets": ["counting-object-group", "question-area", "voice-answer-area"],
            "allowed_visual_targets": ["visual-item-0", "visual-item-1", "visual-item-2"],
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert "one, two, three" in body["message"].lower()
    assert body["ui_action"] == {"type": "highlight", "target": "counting-object-group"}
    assert body["visual_action"] == {
        "type": "highlight_sequence",
        "targets": ["visual-item-0", "visual-item-1", "visual-item-2"],
    }


def test_guide_rejects_invalid_visual_target(client: TestClient):
    response = client.post(
        "/agent/guide",
        json={
            "mode": "practice",
            "event": "PRACTICE_QUESTION_LOADED",
            "route": "/practice/pg_maths",
            "screen": "practice_session",
            "feature": "pg_maths_practice",
            "question": {"activity_id": "a1", "prompt": "How many apples?", "visual_items": ["apple"]},
            "available_actions": ["highlight"],
            "available_targets": ["question-area"],
            "allowed_visual_targets": ["#unsafe"],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSAFE_VISUAL_TARGET"
