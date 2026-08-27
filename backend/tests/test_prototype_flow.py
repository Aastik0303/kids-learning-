"""Guide, companion and speech behaviour.

Curriculum-specific flows live in test_curriculum.py and test_learning_flow.py.
What is left here is the part of the app that does not care which topic a child
is on: the guide agent's safety contract and speech normalization.
"""

import json
from datetime import date

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.policy import actions as policy_actions
from app.schemas.guide import GuideRequest
from app.services import guide_agent_service
from app.services.guide_agent_service import (
    _STRATEGY_LOG,
    ALL_TEACHING_STRATEGIES,
    DETERMINISTIC_EVENTS,
    EARLY_MODE_TEACHING_STRATEGIES,
    HINT_RESPONSES_ATTEMPT_4_PLUS,
    _fallback_guide,
    _ladder_attempt,
    _model_instruction,
    _payload_for_model,
    _pick_hint,
    _record_strategy,
    _validate_model_response,
    guide,
)


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


def _teaching_payload(attempt: int, experience_mode: str = "standard", event: str = "TOPIC_ANSWER_INCORRECT", **extra) -> GuideRequest:
    """A shapes question at the given attempt, on a wrong answer by default."""
    question = {
        "activity_id": "shapes_01",
        "topic": "pg_shapes",
        "prompt": "Which one is the circle?",
        "answer_type": "multiple_choice",
        "options": ["circle", "square"],
        "correct_answer": "circle",
        "child_answer": "square",
        "attempt": attempt,
    }
    question.update(extra.pop("question", {}))
    return GuideRequest(
        session_id="strategy_test",
        child_id="guest_child",
        mode="learning",
        event=event,
        route="/adventure/shapes",
        screen="topic_session",
        feature="tapped square",
        experience_mode=experience_mode,
        question=question,
        available_actions=["none"],
        available_targets=[],
        **extra,
    )


@pytest.fixture(autouse=True)
def _clear_strategy_log():
    _STRATEGY_LOG.clear()
    yield
    _STRATEGY_LOG.clear()


def test_strategies_used_comes_from_the_server_not_the_client():
    """The client may not tell the guide which strategies are spent.

    A client that could write this field could mark every strategy that works
    as already used and steer the guide into the ones that do not - the same
    reason the answer key never leaves the server either.
    """
    payload = _teaching_payload(2, question={"strategies_used": ["S1_TELL", "S2_SHOW", "S6_DO_TOGETHER"]})
    _record_strategy(payload, "S4_STORY")

    sent = _payload_for_model(payload)

    assert sent["question"]["strategies_used"] == ["S4_STORY"]
    assert "correct_answer" not in sent["question"]


def test_a_spent_strategy_is_named_back_to_the_model():
    payload = _teaching_payload(2)
    assert "No strategy has been spent" in _model_instruction(payload)

    _record_strategy(payload, "S3_EXAMPLE")
    _record_strategy(payload, "S3_EXAMPLE")

    # Recorded twice, listed once: the log is what was spent, not how often.
    assert "do not reuse: ['S3_EXAMPLE']" in _model_instruction(payload)


def test_moving_to_the_next_question_starts_a_fresh_strategy_sheet():
    """Strategies are spent per question, not per session: the next question
    gets the whole menu back."""
    first = _teaching_payload(3)
    _record_strategy(first, "S5_CONTRAST")

    second = _teaching_payload(0, question={"activity_id": "shapes_02"})

    assert _payload_for_model(second)["question"]["strategies_used"] == []


def test_early_mode_never_accepts_a_verbal_reasoning_strategy():
    """Play Group loses S3, S4, S5 and S8 in code, not only in the prompt.

    The model's illegal tag is dropped and the message is kept. The turn is
    still tagged, because a strategy really was spent on it - the policy chose
    one before the model was asked - and that tag is always drawn from the
    early-mode set.
    """
    payload = _teaching_payload(3, experience_mode="early")

    told = _validate_model_response(payload, '{"message":"Almost! Tap the round one.","strategy":"hint","teaching_strategy":"S4_STORY","avatar":{"state":"encouraging","message":"Almost!","speak":true,"animationEffect":"gentle_hint"},"ui_action":{"type":"none"}}')

    assert told.teaching_strategy != "S4_STORY"
    assert told.teaching_strategy in EARLY_MODE_TEACHING_STRATEGIES
    assert told.message


def test_a_navigation_turn_spends_no_strategy():
    payload = GuideRequest(
        session_id="strategy_test",
        child_id="guest_child",
        mode="welcome",
        event="APP_OPENED",
        route="/",
        screen="home",
        feature="opened the app",
        available_actions=["none"],
        available_targets=[],
    )

    assert _fallback_guide(payload).teaching_strategy is None


def _with_provider(monkeypatch):
    """Pretend a provider is configured, without a key or a network call.

    The transport moved to `app/ai/llm`, so what the guide asks now is
    `is_configured()` rather than reading the settings itself.
    """
    monkeypatch.setattr(guide_agent_service, "is_configured", lambda: True)


def test_canned_copy_never_reaches_the_model(monkeypatch):
    """Thirteen of the twenty-three events are a greeting, a well done, a
    topic-finished line or a star count. Sending those to Groq bought latency
    and one more turn an LLM failure could spoil, and nothing else."""

    def _explode(payload):
        raise AssertionError(f"{payload.event} should never reach the model")

    _with_provider(monkeypatch)
    monkeypatch.setattr(guide_agent_service, "_model_guide", _explode)

    for event in sorted(DETERMINISTIC_EVENTS):
        payload = GuideRequest(
            session_id="routing_test",
            child_id="guest_child",
            mode="learning",
            event=event,
            route="/adventure/shapes",
            screen="topic_session",
            feature="moved on",
            available_actions=["none"],
            available_targets=[],
        )

        assert guide(payload).message


def test_a_wrong_answer_still_reaches_the_model(monkeypatch):
    """The three open-ended tasks keep their model call: without it there is
    nothing to vary the repair on."""
    seen = []
    _with_provider(monkeypatch)
    monkeypatch.setattr(
        guide_agent_service,
        "_model_guide",
        lambda payload: seen.append(payload.event) or _fallback_guide(payload),
    )

    for event in ("TOPIC_ANSWER_INCORRECT", "HINT_REQUESTED", "GUIDE_HELP_REQUESTED", "TOPIC_QUESTION_LOADED"):
        guide(_teaching_payload(1, event=event))

    assert seen == ["TOPIC_ANSWER_INCORRECT", "HINT_REQUESTED", "GUIDE_HELP_REQUESTED", "TOPIC_QUESTION_LOADED"]


def test_every_miss_lands_on_a_rung_that_teaches():
    """There is no encouragement-only rung any more.

    Rung 1 used to be the clean second try - "good try, go again" - and nothing
    was taught there and no strategy was spent. A question gets three repairs
    now, and a turn that teaches nothing cannot be one of them, so the first
    miss steps straight onto rung 2 where the policy chooses.
    """
    assert _ladder_attempt(_teaching_payload(1)) == 2
    assert _ladder_attempt(_teaching_payload(2)) == 3

    # A child who asks for a hint is still not dragged back down a rung, and
    # asking on a parked question does not restart the drilling.
    assert _ladder_attempt(_teaching_payload(0, event="HINT_REQUESTED")) == 2
    assert _ladder_attempt(_teaching_payload(1, event="HINT_REQUESTED")) == 2
    assert _ladder_attempt(_teaching_payload(5, event="HINT_REQUESTED")) == 5

    instruction = _model_instruction(_teaching_payload(0, event="HINT_REQUESTED"))
    assert "S3_EXAMPLE or S5_CONTRAST" in instruction
    assert "encouragement only" not in instruction


def test_each_task_gets_only_its_own_instruction():
    """One instruction for every event alike read as a list of exceptions. Each
    task now carries its own job and nobody else's."""
    first = _model_instruction(_teaching_payload(0, event="TOPIC_QUESTION_LOADED"))
    # Attempt 2 is the last repair: rung 3, where the ladder changes how the
    # idea is presented rather than adding words to the same explanation.
    repair = _model_instruction(_teaching_payload(2))
    help_turn = _model_instruction(_teaching_payload(0, event="GUIDE_HELP_REQUESTED"))

    assert "there is nothing to repair yet" in first
    assert "S4_STORY" not in first
    assert "feature is the child's own question" not in first

    assert "Switch how the idea is presented" in repair
    assert "feature is the child's own question" not in repair

    assert "feature is the child's own question" in help_turn
    assert "Omit teaching_strategy, unless" in help_turn
    assert "S5_CONTRAST" not in help_turn


def test_a_parked_question_is_not_re_asked():
    parked = _model_instruction(_teaching_payload(4))

    assert "S9_PARK" in parked
    assert "do not ask the question again" in parked
    assert '"wait_for_child"' in parked


def test_the_fourth_attempt_parks_the_question_instead_of_hinting_again():
    """Attempt three used to repeat for ever, so a stuck child drilled one
    question for as long as they stayed on the screen."""
    parked = {_pick_hint(4) for _ in range(50)}
    third = {_pick_hint(3) for _ in range(50)}

    assert not parked & third
    assert all("?" not in message for message in parked)
    assert all("wrong" not in message.lower() for message in parked)


def test_a_hindi_lesson_is_narrated_in_english():
    """Hindi is what these two subjects teach, not the language the guide
    speaks: the letter itself is quoted, the sentence around it is English."""
    payload = _teaching_payload(
        1,
        progress={"current_class": "nursery", "current_subject": "nur_hindi", "current_topic": "nur_hindi_swar_a_aa"},
        question={"activity_id": "nur_hindi_01", "topic": "nur_hindi_swar_a_aa", "prompt": "Which one is \u0905?"},
    )

    assert _fallback_guide(payload).message.isascii()


def _model_reply(message: str, strategy: str = "hint", teaching_strategy: str | None = "S5_CONTRAST") -> str:
    body = {
        "message": message,
        "strategy": strategy,
        "avatar": {"state": "encouraging", "message": message, "speak": True, "animationEffect": "gentle_hint"},
        "ui_action": {"type": "none"},
    }
    if teaching_strategy:
        body["teaching_strategy"] = teaching_strategy
    return json.dumps(body)


def test_the_repair_ladder_keeps_the_model_wording():
    """T3's whole argument is that the wording changes with how the child got it
    wrong. This used to overwrite it on every repair turn at every attempt, so
    the guide paid for a call and threw the answer away."""
    payload = _teaching_payload(2)

    response = _validate_model_response(payload, _model_reply("A circle is smooth all the way round, like a wheel."))

    assert response.message == "A circle is smooth all the way round, like a wheel."
    assert response.teaching_strategy == "S5_CONTRAST"


def test_a_model_that_congratulates_a_miss_is_overruled():
    """The failure the old blanket override was built for. The grader has
    already recorded the miss, so this contradicts the score the app is about
    to show."""
    for claim in ("That's right! Well done.", "Yes! You got it.", "Perfect, that is correct."):
        response = _validate_model_response(_teaching_payload(2), _model_reply(claim))

        assert claim not in response.message
        # The model's wording is gone and the app's own is in its place, so the
        # tag names the strategy that wording was written under - the policy's
        # choice for this turn, not the model's.
        assert response.teaching_strategy in ALL_TEACHING_STRATEGIES


def test_a_repair_turn_with_no_legal_strategy_falls_back():
    """An untagged model answer is a malformed one: the wording is replaced.

    What replaces it is the deterministic branch written under the policy's
    chosen strategy, so the turn is still tagged with what the child heard.
    """
    response = _validate_model_response(_teaching_payload(2), _model_reply("Look again at the two shapes.", teaching_strategy=None))

    assert response.message != "Look again at the two shapes."
    assert response.teaching_strategy in ALL_TEACHING_STRATEGIES


def test_the_clean_second_try_is_still_the_apps_own_words():
    """Attempt 1 is bare encouragement by design - nothing is taught, so there
    is nothing of the model's to keep."""
    response = _validate_model_response(_teaching_payload(1), _model_reply("A circle has no corners at all."))

    assert "corners" not in response.message
    assert response.strategy == "hint"
    assert response.teaching_strategy is None


def test_the_deterministic_path_parks_a_stuck_child():
    """`_question_teaching_message` had no ceiling: every branch re-explained,
    and none looked at how often it had already re-explained."""
    response = _fallback_guide(_teaching_payload(5))

    assert response.message in HINT_RESPONSES_ATTEMPT_4_PLUS
    assert response.next_expected_event != "voice_answer_requested"


def test_a_parked_turn_on_the_model_path_moves_the_child_on():
    response = _validate_model_response(_teaching_payload(4), _model_reply("Let us come back to this one later!", teaching_strategy="S9_PARK"))

    assert response.next_expected_event == "next_question_loaded"


def test_a_runaway_attempt_count_parks_rather_than_falling_off_the_ladder():
    """`attempt` is client UI state. Nothing scores off it, but every rung of
    the ladder is chosen by it, so it is clamped to the top of the ladder -
    where the only thing left to do is park the question."""
    assert _ladder_attempt(_teaching_payload(999)) == policy_actions.PARK_RUNG
    assert _fallback_guide(_teaching_payload(999)).message in HINT_RESPONSES_ATTEMPT_4_PLUS


def test_early_mode_parks_too():
    """Early mode had no ceiling at all - it repeated "Here it is. Tap X." for
    as long as the child stayed, which is what drilling looks like to a
    pre-verbal child."""
    response = _fallback_guide(_teaching_payload(5, experience_mode="early"))

    assert response.message in HINT_RESPONSES_ATTEMPT_4_PLUS
    assert response.next_expected_event == "next_activity"


def test_early_mode_word_cap_is_enforced_on_the_model_path():
    """The 14-word cap lived in `_early_mode_guide`, which only runs when the
    model is not called - so with a live key a three-year-old got the
    five-year-old's budget."""
    long_message = "Look carefully at the two shapes on the screen and then think about which one of them is the round one"
    payload = _teaching_payload(2, experience_mode="early")

    response = _validate_model_response(payload, _model_reply(long_message, teaching_strategy="S2_SHOW"))

    assert len(response.message.split()) <= 14
    assert len(response.avatar.message.split()) <= 14


def test_register_login_and_create_child(client: TestClient):
    token, child_id = make_child(client)
    # An opaque session token, stored in `auth_sessions` with an expiry. The old
    # "demo-" prefix belonged to a dictionary that forgot every account on
    # restart.
    assert token and len(token) >= 32
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
