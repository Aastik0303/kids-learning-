"""The class runs itself, and the server is the one running it.

Gap 1 of `docs/AI-100-PERCENT-AUTOMATION.md`: the guide answered events, nobody
held the lesson's phase, and the child's device had to decide what came next.
These tests pin the opposite - that the phase, the branch, the scaffolding, the
timeout and the decision to stop all live in one row on the server, and that a
directive tells the client what to render and nothing more.

The branch engine tests come first and touch no database: that engine is the
answer to "aage badhun ya dobara samjhaun", and it must stay a function.
"""

import ast
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.conductor import scaffold as scaffold_engine
from app.conductor import signals as signal_engine
from app.conductor.branch import Branch, BranchInput, decide
from app.conductor.phases import Phase, teaching_sequence
from app.main import app
from app.services import curriculum_service


SUBJECT_ID = "pg_maths"
FIRST_TOPIC = "pg_maths_colours"


def choice_activity(index: int, correct: str, other: str) -> dict:
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
    """One Play Group topic: a teaching card, then two questions."""
    activities_dir = tmp_path / "activities"
    activities_dir.mkdir()
    (activities_dir / f"{SUBJECT_ID}.json").write_text(
        json.dumps(
            {
                "subject_id": SUBJECT_ID,
                "topics": {
                    FIRST_TOPIC: [
                        {
                            "activity_id": f"{FIRST_TOPIC}_intro",
                            "type": "introduce_colour",
                            "prompt": "This is red.",
                            "visual_items": ["red"],
                        },
                        choice_activity(1, "red", "blue"),
                        choice_activity(2, "blue", "red"),
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(curriculum_service, "ACTIVITIES_DIR", activities_dir)
    curriculum_service.reload_curriculum()
    yield
    # Undo the path patch *before* reloading. Fixture finalisers run before
    # `monkeypatch`'s own, so a reload here would otherwise re-read the
    # temporary activities directory and leave that cached for every test in
    # every module after this one.
    monkeypatch.undo()
    curriculum_service.reload_curriculum()


@pytest.fixture()
def client(authored):
    with TestClient(app) as test_client:
        yield test_client


def make_child(client: TestClient, email: str = "conductor@example.com") -> str:
    auth = client.post("/auth/register", json={"name": "P", "email": email, "password": "demo1234"})
    token = auth.json()["session_token"]
    child = client.post(
        "/children",
        json={
            "session_token": token,
            "name": "Mira",
            "birth_year": date.today().year - 2,
            "birth_month": date.today().month,
            "preferred_language": "English",
        },
    )
    return child.json()["child_id"]


def send(client: TestClient, session_id: str, **payload) -> dict:
    response = client.post(f"/conductor/sessions/{session_id}/input", json=payload or {"kind": "ready"})
    assert response.status_code == 200, response.text
    return response.json()


def say_it_back(client: TestClient, directive: dict) -> dict:
    """Answer the say-it-back beat with the word it asked for."""
    return send(
        client,
        directive["session_id"],
        kind="voice",
        answer=directive["listen"]["expect"],
        confidence=0.95,
    )


def run_to_question(client: TestClient, directive: dict) -> dict:
    """Let the class talk its way to the first thing it *asks* the child.

    The say-it-back beat is walked through rather than stopped at: it is the
    child speaking, not the child being questioned, and every test below this
    helper is about a question.
    """
    for _ in range(16):
        if directive["phase"] == "say_it":
            directive = say_it_back(client, directive)
            continue
        if directive["next_input"]["expects"] != "ready":
            return directive
        directive = send(client, directive["session_id"], kind="ready")
    raise AssertionError("the class never reached a question")


# --------------------------------------------------------------------------
# 1. The Branch Decision Engine - six outcomes, one fixed order, no model
# --------------------------------------------------------------------------


def test_a_first_try_correct_answer_advances():
    assert decide(BranchInput(is_correct=True, attempts_on_current=0, skill_mastery=0.0)).decision is Branch.ADVANCE


def test_a_correct_answer_on_a_shaky_skill_still_advances_but_says_so():
    outcome = decide(BranchInput(is_correct=True, attempts_on_current=2, skill_mastery=0.2))
    assert outcome.decision is Branch.ADVANCE
    # It moves on - a child is not made to repeat a question they just got right -
    # but the skill is flagged so the plan brings it back.
    assert outcome.notes["reteach_soon"] is True


def test_a_wrong_answer_re_explains_with_more_support():
    outcome = decide(BranchInput(is_correct=False, attempts_on_current=1, skill_mastery=0.3))
    assert outcome.decision is Branch.RE_EXPLAIN
    assert outcome.scaffold_delta == 1


def test_the_last_of_the_three_tries_stops_explaining_and_starts_simplifying():
    """Three repairs, and the third takes things away instead of adding them."""
    outcome = decide(BranchInput(is_correct=False, attempts_on_current=2, skill_mastery=0.3))
    assert outcome.decision is Branch.SIMPLIFY
    assert outcome.scaffold_delta == 1


def test_out_of_tries_moves_on_rather_than_ending_the_lesson():
    """Spending the three repairs is not a reason to end the sitting.

    It used to be: a fourth wrong answer closed the whole lesson, so a child who
    could not do one question lost the rest of the day's work with it. The
    question is let go of instead - `ADVANCE` with a reason that says the child
    did not get there, so nothing celebrates it or counts it right.
    """
    outcome = decide(BranchInput(is_correct=False, attempts_on_current=3, skill_mastery=0.3))
    assert outcome.decision is Branch.ADVANCE
    assert outcome.reason == "attempts_exhausted"


def test_a_child_who_is_upset_still_stops_rather_than_being_moved_on():
    """The one thing that must still end the sitting."""
    outcome = decide(
        BranchInput(is_correct=False, attempts_on_current=3, skill_mastery=0.3, frustration_score=0.9)
    )
    assert outcome.decision is Branch.END_KINDLY


def test_safety_outranks_everything_else():
    """The priority order is the safety argument, so it is asserted directly.

    A frustrated child with a missing prerequisite on a voice question that the
    microphone cannot hear matches four rules at once. It must stop, not teach.
    """
    outcome = decide(
        BranchInput(
            is_correct=False,
            attempts_on_current=2,
            skill_mastery=0.1,
            frustration_score=0.8,
            modality="voice",
            unresolved_speech_streak=3,
            prerequisite_mastery=0.1,
        )
    )
    assert outcome.decision is Branch.END_KINDLY


def test_a_microphone_problem_is_not_a_learning_problem():
    outcome = decide(
        BranchInput(
            is_correct=False,
            attempts_on_current=1,
            skill_mastery=0.5,
            modality="voice",
            unresolved_speech_streak=2,
            prerequisite_mastery=0.1,
        )
    )
    assert outcome.decision is Branch.SWITCH_MODALITY
    assert outcome.notes["modality"] == "tap"


def test_a_missing_foundation_is_taught_before_the_thing_on_top_of_it():
    outcome = decide(
        BranchInput(is_correct=False, attempts_on_current=1, skill_mastery=0.2, prerequisite_mastery=0.1)
    )
    assert outcome.decision is Branch.PREREQUISITE


def test_an_unauthored_prerequisite_graph_never_sends_a_child_backwards():
    """`None` means "no opinion", and must not read as "the foundation is bad"."""
    outcome = decide(
        BranchInput(is_correct=False, attempts_on_current=1, skill_mastery=0.2, prerequisite_mastery=None)
    )
    assert outcome.decision is Branch.RE_EXPLAIN


def test_a_long_sitting_ends_before_the_child_does():
    outcome = decide(
        BranchInput(
            is_correct=False,
            attempts_on_current=0,
            skill_mastery=0.9,
            minutes_in_session=9.0,
            target_minutes=6.0,
        )
    )
    assert outcome.decision is Branch.END_KINDLY
    assert outcome.reason == "session_overrun"


def test_the_branch_engine_cannot_reach_a_model():
    """The decision is deterministic, and that is checked on the import graph.

    A model deciding whether to move a child on would make the one number that
    matters - did this child learn it? - a matter of opinion.
    """
    for path in (
        Path("app/conductor/branch.py"),
        Path("app/conductor/signals.py"),
        Path("app/conductor/phases.py"),
        Path("app/conductor/scaffold.py"),
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        modules |= {
            alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
        }
        assert not any(
            name.startswith(("app.ai", "app.services", "httpx", "openai", "anthropic"))
            for name in modules
        ), f"{path} must stay decidable without a network"


# --------------------------------------------------------------------------
# 2. Watchers and scaffolding
# --------------------------------------------------------------------------


def test_frustration_rises_with_wrong_answers_and_silence():
    calm = signal_engine.SessionSignals(attempts_on_current=0, recent_answers=(True, True, True))
    struggling = signal_engine.SessionSignals(
        attempts_on_current=3,
        recent_answers=(False, False, False, True),
        idle_rungs_hit=3,
        retry_burst_count=2,
        answers_counted=4,
    )
    assert signal_engine.frustration(calm) == 0.0
    assert signal_engine.frustration(struggling) >= signal_engine.SIMPLIFY_AT


def test_boredom_is_watched_as_well_as_frustration():
    """Too easy loses a child as surely as too hard."""
    bored = signal_engine.SessionSignals(
        consecutive_correct=6, average_latency_ms=800, band_median_latency_ms=4000
    )
    assert signal_engine.is_bored(bored)
    assert not signal_engine.is_bored(signal_engine.SessionSignals(consecutive_correct=2))


def test_the_idle_ladder_asks_the_model_exactly_once():
    """Silence happens on every screen. If every rung called out, the session's
    whole AI budget would be spent on a child who simply looked away."""
    uses_model = [uses for _, uses in signal_engine.IDLE_RUNGS]
    assert sum(uses_model) == 1


def test_idle_timeouts_come_from_the_manifest_not_from_a_constant():
    early = curriculum_service.experience_mode_for_class("playgroup").idle_thresholds_seconds
    standard = curriculum_service.experience_mode_for_class("lkg").idle_thresholds_seconds
    # A two-year-old is given longer to decide to touch the screen at all.
    assert signal_engine.idle_timeout_ms(early, 0) > signal_engine.idle_timeout_ms(standard, 0)


def test_the_answer_is_never_pointed_at_while_the_child_is_answering():
    """Pointing belongs to I DO and WE DO. In YOU DO the help is fewer choices
    and bigger targets - never a finger on the right one."""
    for phase in (Phase.I_DO, Phase.WE_DO):
        block = scaffold_engine.build(
            phase=phase,
            level=4,
            options=["red", "blue"],
            correct_answer="red",
            visual_targets=["visual-item-0", "visual-item-1"],
            max_choices=3,
        )
        assert block.point_at == ["visual-item-0"]

    you_do = scaffold_engine.build(
        phase=Phase.YOU_DO,
        level=4,
        options=["red", "blue"],
        correct_answer="red",
        visual_targets=["visual-item-0", "visual-item-1"],
        max_choices=3,
    )
    assert you_do.point_at == []
    assert you_do.dim_others is False
    assert you_do.demo_tap is False


def test_trimming_options_keeps_the_right_one_and_the_authored_order():
    trimmed = scaffold_engine.trim_options(["red", "blue", "green"], correct_answer="green", limit=2)
    assert "green" in trimmed
    assert len(trimmed) == 2
    assert trimmed == [option for option in ["red", "blue", "green"] if option in trimmed]


def test_we_do_is_skipped_for_a_designed_sequence():
    """A "complete" topic - meet the letter, find it, say it, write it - already
    carries its own I-do and you-do. Injecting WE DO would break the method."""
    assert Phase.WE_DO in teaching_sequence(lesson_flow="sample", needs_answer=True)
    assert Phase.WE_DO not in teaching_sequence(lesson_flow="complete", needs_answer=True)
    assert teaching_sequence(lesson_flow="sample", needs_answer=False) == (Phase.I_DO,)


def test_the_class_waits_for_the_drawing_instead_of_advancing_past_it():
    """A traced letter is not graded, but it is still the child's turn.

    A writing card evaluates as presentational - there is no marking a finger
    drawing right or wrong - and that used to make it I DO alone, so the one
    step of a level that asks for a finger on the screen was shown for a few
    seconds and then advanced past on a timer. YOU DO here means "your turn",
    not "you will be marked".
    """
    assert teaching_sequence(lesson_flow="sample", needs_answer=False, draw=True) == (
        Phase.I_DO,
        Phase.YOU_DO,
    )
    # And the drawing is never also the listening beat: a microphone asking for
    # the word with a finger already on the screen interrupts the writing.
    assert Phase.SAY_IT not in teaching_sequence(
        lesson_flow="sample", needs_answer=False, echo=True, draw=True
    )


# --------------------------------------------------------------------------
# 3. The class, running
# --------------------------------------------------------------------------


def test_the_class_opens_itself_with_no_navigation(client: TestClient):
    """A three-year-old taps nothing to get into a lesson: no subject card, no
    topic card, no start button."""
    child_id = make_child(client)

    response = client.post(f"/conductor/{child_id}/open")

    assert response.status_code == 200
    directive = response.json()
    assert directive["session_id"]
    assert directive["phase"] in ("greet", "set")
    assert directive["speech"]["text"]
    # Nothing is asked of the child, so the class carries on by itself.
    assert directive["auto_advance_in_ms"] > 0
    assert directive["next_input"]["expects"] == "ready"


def test_the_lesson_walks_i_do_we_do_you_do_by_itself(client: TestClient):
    child_id = make_child(client)
    directive = client.post(f"/conductor/{child_id}/open").json()

    phases = [directive["phase"]]
    for _ in range(12):
        if directive["phase"] == "say_it":
            directive = say_it_back(client, directive)
            phases.append(directive["phase"])
            continue
        if directive["next_input"]["expects"] != "ready":
            break
        directive = send(client, directive["session_id"], kind="ready")
        phases.append(directive["phase"])

    assert "i_do" in phases
    assert "we_do" in phases
    assert directive["phase"] == "you_do"
    # Only now is the child asked for anything.
    assert directive["next_input"]["expects"] == "tap"
    assert directive["auto_advance_in_ms"] is None


def test_the_client_never_receives_the_answer_key(client: TestClient):
    child_id = make_child(client)
    directive = run_to_question(client, client.post(f"/conductor/{child_id}/open").json())

    assert directive["activity"]["correct_answer"] is None
    assert directive["activity"]["accept"] == []
    # The options are still there to tap - trimmed server-side, never by the client.
    assert directive["scaffold"]["options_shown"]


def test_a_wrong_answer_re_explains_and_a_right_one_moves_on(client: TestClient):
    child_id = make_child(client)
    directive = run_to_question(client, client.post(f"/conductor/{child_id}/open").json())
    session_id = directive["session_id"]

    wrong = send(client, session_id, kind="tap", answer="blue", latency_ms=4000)
    assert wrong["branch"] == "re_explain"
    assert wrong["phase"] == "we_do"
    # More help, not the same words again.
    assert wrong["scaffold"]["level"] >= directive["scaffold"]["level"]
    # The first wrong answer is encouragement by design - nothing new is taught,
    # so no strategy is spent on it.
    # The first miss goes straight to the policy: something new is said on the
    # very next turn, rather than "good try, go again".
    assert wrong["teaching_strategy"]

    second_wrong = send(client, run_to_question(client, wrong)["session_id"], kind="tap", answer="blue", latency_ms=4000)
    # The second one teaches, and the policy names how.
    assert second_wrong["teaching_strategy"]

    back_to_question = run_to_question(client, second_wrong)
    right = send(client, back_to_question["session_id"], kind="tap", answer="red", latency_ms=4000)
    assert right["branch"] == "advance"
    assert right["progress"]["filled"] == 1


def test_a_question_is_repaired_three_times_and_then_let_go_of(client: TestClient):
    """The worst thing the app can do is sit a child in front of a question they
    cannot answer. Never told they failed, and never asked a fourth time."""
    child_id = make_child(client)
    directive = run_to_question(client, client.post(f"/conductor/{child_id}/open").json())
    first_activity = directive["activity"]["activity_id"]

    seen: list[str] = []
    for _ in range(6):
        directive = send(client, directive["session_id"], kind="tap", answer="blue", latency_ms=4000)
        seen.append(directive["phase"])
        if directive.get("close"):
            break
        activity = (directive.get("activity") or {}).get("activity_id")
        if activity and activity != first_activity:
            break
        directive = run_to_question(client, directive)

    # Either the lesson had another thing to teach and moved to it, or that was
    # the last question and the sitting closed. Never a fourth ask.
    moved_on = (directive.get("activity") or {}).get("activity_id") != first_activity
    assert moved_on or directive.get("close")
    assert "wrong" not in directive["speech"]["text"].lower()
    assert "fail" not in directive["speech"]["text"].lower()


def test_silence_escalates_on_the_server_and_the_client_only_reports_it(client: TestClient):
    child_id = make_child(client)
    directive = run_to_question(client, client.post(f"/conductor/{child_id}/open").json())
    session_id = directive["session_id"]
    assert directive["next_input"]["on_timeout"] == "idle"

    first_idle = send(client, session_id, kind="idle")
    second_idle = send(client, session_id, kind="idle")

    # Each rung waits longer than the last, from the manifest's own thresholds.
    assert second_idle["next_input"]["timeout_ms"] >= first_idle["next_input"]["timeout_ms"]
    assert second_idle["speech"]["text"]


def test_a_refresh_resumes_the_same_turn(client: TestClient):
    """The client holds no lesson state, so reloading cannot lose one."""
    child_id = make_child(client)
    directive = run_to_question(client, client.post(f"/conductor/{child_id}/open").json())

    resumed = client.get(f"/conductor/sessions/{directive['session_id']}").json()

    assert resumed["phase"] == directive["phase"]
    assert resumed["activity"]["activity_id"] == directive["activity"]["activity_id"]
    assert resumed["progress"] == directive["progress"]


def test_reopening_the_app_returns_to_the_same_sitting(client: TestClient):
    child_id = make_child(client)
    first = client.post(f"/conductor/{child_id}/open").json()
    run_to_question(client, first)

    reopened = client.post(f"/conductor/{child_id}/open").json()

    assert reopened["session_id"] == first["session_id"]


def test_answers_land_in_the_attempt_log_with_the_help_that_was_up(client: TestClient):
    """Truth is written before anything is said, and it records how much support
    the child had - a correct answer at S3 is not the same evidence as one at S0."""
    from uuid import UUID

    from app.db.repositories import truth
    from app.db.session import session_scope

    child_id = make_child(client)
    directive = run_to_question(client, client.post(f"/conductor/{child_id}/open").json())
    send(client, directive["session_id"], kind="tap", answer="red", latency_ms=3500)

    with session_scope() as session:
        attempts = truth.attempts_for(session, child_id=UUID(child_id))
        assert [attempt.is_correct for attempt in attempts] == [True]
        assert attempts[0].skill_id == f"{SUBJECT_ID}:{FIRST_TOPIC}"
        assert attempts[0].form_signature == "identify_colour"
        assert attempts[0].scaffold_level >= 0


def test_finishing_the_lesson_awards_and_closes(client: TestClient):
    child_id = make_child(client)
    directive = client.post(f"/conductor/{child_id}/open").json()
    answers = {f"{FIRST_TOPIC}_1": "red", f"{FIRST_TOPIC}_2": "blue"}

    for _ in range(24):
        if directive.get("close"):
            break
        if directive["next_input"]["expects"] == "ready":
            directive = send(client, directive["session_id"], kind="ready")
            continue
        answer = answers.get(directive["activity"]["activity_id"], "red")
        directive = send(client, directive["session_id"], kind="tap", answer=answer, latency_ms=4000)

    assert directive["close"]["reason"] == "completed"
    assert directive["close"]["topic_completed"] is True
    assert directive["phase"] == "close"
    profile = client.get(f"/children/{child_id}").json()
    assert FIRST_TOPIC in profile["subject_progress"][SUBJECT_ID]["completed_topics"]
    assert profile["stars"] > 0
