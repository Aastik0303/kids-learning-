"""The Conductor: the half of the class that runs it.

`app/conductor/` decides; this module holds the state, writes the truth, and
finds the words. One directive goes back for every input, and the child's device
renders it and reports what happened next. It never decides anything.

The order inside a turn is fixed and is the reason a slow model can never cost a
child their progress:

    1. evaluate            deterministic - `activity_evaluators`
    2. record the attempt  deterministic - `attempts`, `skill_mastery`
    3. settle / schedule   deterministic - retention probes
    4. branch              deterministic - `conductor.branch`
    5. commit                            <- everything above is durable here
    6. voice the step      the guide, which may reach a model
    7. build the directive

Steps 1-5 do not know whether a provider is configured. If step 6 times out the
child hears the app's own words and keeps every star they earned.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from app.conductor import branch as branch_engine
from app.conductor import explain
from app.conductor import scaffold as scaffold_engine
from app.conductor import signals as signal_engine
from app.conductor import skill_graph
from app.conductor.phases import Phase, next_in_sequence, teaching_sequence
from app.db.models import LessonState
from app.db.repositories import truth
from app.db.session import session_scope
from app.schemas.avatar import AvatarPayload
from app.schemas.conductor import (
    CloseBlock,
    ConductorDirective,
    ConductorInput,
    NextInput,
    PresentationBlock,
    ProgressBlock,
    ScaffoldBlock,
    SpeechBlock,
)
from app.schemas.curriculum import Topic
from app.schemas.guide import GuideRequest, GuideResponse, GuideVisualAction
from app.schemas.learning import Activity
from app.services import (
    activity_evaluators,
    child_service,
    child_store,
    curriculum_service,
    daily_recommendation_service,
    guide_agent_service,
    learning_service,
    plan_service,
    retention_service,
)
from app.services.errors import app_error
from app.services.history_service import record_attempt


logger = logging.getLogger(__name__)

# Below this the recogniser did not hear a word, and treating that as a wrong
# answer would punish a child for a microphone. It is not an attempt at all.
UNRESOLVED_SPEECH_CONFIDENCE = 0.45

# A tap this fast after the question appeared was not a decision.
RETRY_BURST_MS = signal_engine.RETRY_BURST_MS

# How long the class waits while the guide is talking before carrying on by
# itself. This is the "next" button, replaced by arithmetic: roughly reading
# speed for a young listener, floored and capped so nothing drags or races.
MS_PER_WORD = 420
MIN_AUTO_ADVANCE_MS = 1800
MAX_AUTO_ADVANCE_MS = 7000

# The last few verdicts kept beside the state for the frustration score.
RECENT_ANSWER_WINDOW = 6

# What the client is allowed to be pointed at during a lesson. Same approved
# list the guide validates against; naming a subset here keeps a lesson turn
# from ever being told to open a route.
LESSON_TARGETS = ["activity-area", "answer-options", "question-area", "voice-answer-area"]
LESSON_ACTIONS = ["none", "highlight", "show_hint", "repeat_instruction"]


@dataclass
class _State:
    """The lesson row, as a plain object the rest of this module can reason about."""

    session_id: str
    child_id: str
    topic_id: str
    phase: str
    cursor: int
    scaffold_level: int
    ladder_rung: int
    attempts_on_current: int
    consecutive_correct: int
    correct_count: int
    frustration_score: float
    modality: str
    idle_rung: int
    idle_rungs_hit: int
    retry_burst_count: int
    unresolved_speech: int
    speech_attempts: int
    answers_counted: int
    activity_ids: list[str]
    explanations_used: list[str]
    recent_answers: list[bool]
    current_skill_id: str
    paused_for: str | None
    resume_payload: dict | None
    status: str
    started_at: datetime
    last_input_at: datetime | None


@dataclass
class _Turn:
    """What this input turned into: the new state, and what to say about it."""

    state: _State
    topic: Topic
    child: dict
    activity: Activity | None
    event: str
    branch: str | None = None
    is_correct: bool | None = None
    close: CloseBlock | None = None
    expects_answer: bool = True
    speech_override: str = ""
    extra_visual: GuideVisualAction | None = None
    notes: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# Reading and writing the state
# --------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_state(row: LessonState) -> _State:
    return _State(
        session_id=row.session_id or "",
        child_id=str(row.child_id),
        topic_id=row.topic_id,
        phase=row.phase,
        cursor=row.cursor,
        scaffold_level=row.scaffold_level,
        ladder_rung=row.ladder_rung,
        attempts_on_current=row.attempts_on_current,
        consecutive_correct=row.consecutive_correct,
        correct_count=row.correct_count,
        frustration_score=row.frustration_score,
        modality=row.modality,
        idle_rung=row.idle_rung,
        idle_rungs_hit=row.idle_rungs_hit,
        retry_burst_count=row.retry_burst_count,
        unresolved_speech=row.unresolved_speech,
        speech_attempts=row.speech_attempts,
        answers_counted=len(row.recent_answers or []),
        activity_ids=list(row.activity_ids or []),
        explanations_used=list(row.explanations_used or []),
        recent_answers=list(row.recent_answers or []),
        current_skill_id=row.current_skill_id,
        paused_for=row.paused_for,
        resume_payload=row.resume_payload,
        status=row.status,
        started_at=row.started_at,
        last_input_at=row.last_input_at,
    )


def _read_state(session_id: str) -> _State:
    with session_scope() as session:
        row = session.scalar(select(LessonState).where(LessonState.session_id == session_id))
        if row is None:
            raise app_error("EXPIRED_LEARNING_SESSION", "Let us start this again.", 404)
        return _to_state(row)


def _save_state(state: _State) -> None:
    with session_scope() as session:
        row = session.scalar(select(LessonState).where(LessonState.session_id == state.session_id))
        if row is None:  # pragma: no cover - the row is created before this runs
            return
        row.phase = state.phase
        row.cursor = state.cursor
        row.scaffold_level = state.scaffold_level
        row.ladder_rung = state.ladder_rung
        row.attempts_on_current = state.attempts_on_current
        row.consecutive_correct = state.consecutive_correct
        row.correct_count = state.correct_count
        row.frustration_score = state.frustration_score
        row.modality = state.modality
        row.idle_rung = state.idle_rung
        row.idle_rungs_hit = state.idle_rungs_hit
        row.retry_burst_count = state.retry_burst_count
        row.unresolved_speech = state.unresolved_speech
        row.speech_attempts = state.speech_attempts
        row.activity_ids = list(state.activity_ids)
        row.explanations_used = list(state.explanations_used)
        row.recent_answers = list(state.recent_answers)[-RECENT_ANSWER_WINDOW:]
        row.current_skill_id = state.current_skill_id
        row.paused_for = state.paused_for
        row.resume_payload = state.resume_payload
        row.status = state.status
        row.last_input_at = state.last_input_at or _now()


def _open_state(child: dict, topic: Topic) -> _State:
    """Find this child's live sitting on the topic, or start one.

    The unique `(child_id, topic_id)` row is what makes reopening the app
    resume: the sitting is the row, not the tab it was opened in.
    """
    child_uuid = UUID(child["child_id"])
    with session_scope() as session:
        row = session.scalar(
            select(LessonState).where(
                LessonState.child_id == child_uuid, LessonState.topic_id == topic.topic_id
            )
        )
        resuming = row is not None and row.status == "in_progress" and bool(row.activity_ids)
        if row is None:
            row = LessonState(child_id=child_uuid, topic_id=topic.topic_id)
            session.add(row)

        if not resuming:
            session_id = f"class_{uuid4().hex}"
            activities = learning_service.lesson_activities(topic, session_id)
            row.session_id = session_id
            row.activity_ids = [activity.activity_id for activity in activities]
            row.cursor = 0
            row.correct_count = 0
            row.attempts_on_current = 0
            row.ladder_rung = 0
            row.explanations_used = []
            row.recent_answers = []
            row.retry_burst_count = 0
            row.unresolved_speech = 0
            row.speech_attempts = 0
            row.idle_rung = 0
            row.idle_rungs_hit = 0
            row.consecutive_correct = 0
            row.frustration_score = 0.0
            row.scaffold_level = 4 if child.get("experience_mode") == "early" else 3
            row.status = "in_progress"
            row.paused_for = None
            row.resume_payload = None
            row.started_at = _now()
            # A child who has finished something before is greeted about it;
            # a first ever lesson goes straight to what today is about.
            row.phase = Phase.GREET.value if child.get("stars") else Phase.SET.value
            row.current_skill_id = learning_service.skill_slug(topic)
        session.flush()
        return _to_state(row)


# --------------------------------------------------------------------------
# The lesson's own material
# --------------------------------------------------------------------------


def _activities(state: _State, topic: Topic) -> list[Activity]:
    by_id = {activity.activity_id: activity for activity in curriculum_service.get_activities(topic.topic_id)}
    return [by_id[activity_id] for activity_id in state.activity_ids if activity_id in by_id]


def _current_activity(state: _State, topic: Topic) -> Activity | None:
    activities = _activities(state, topic)
    if not activities or state.cursor >= len(activities):
        return None
    return activities[state.cursor]


def _needs_answer(activity: Activity | None) -> bool:
    return bool(activity) and activity_evaluators.requires_answer(activity.type)


def _sequence_for(state: _State, topic: Topic) -> tuple[Phase, ...]:
    return teaching_sequence(
        lesson_flow=topic.lesson_flow, needs_answer=_needs_answer(_current_activity(state, topic))
    )


def _signals_of(state: _State) -> signal_engine.SessionSignals:
    return signal_engine.SessionSignals(
        attempts_on_current=state.attempts_on_current,
        recent_answers=tuple(state.recent_answers),
        retry_burst_count=state.retry_burst_count,
        answers_counted=max(1, len(state.recent_answers)),
        idle_rungs_hit=state.idle_rungs_hit,
        idle_rungs_available=len(signal_engine.IDLE_RUNGS),
        unresolved_speech=state.unresolved_speech,
        speech_attempts=state.speech_attempts,
        consecutive_correct=state.consecutive_correct,
    )


def _minutes_in(state: _State) -> float:
    started = state.started_at or _now()
    if started.tzinfo is None:  # pragma: no cover - SQLite handled by UTCDateTime
        started = started.replace(tzinfo=timezone.utc)
    return max(0.0, (_now() - started).total_seconds() / 60)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def open_class(child_id: str) -> ConductorDirective:
    """Open today's class for this child. No menu, no choice, no taps.

    The topic comes from the frozen daily plan, so the app opens on the same
    lesson all day, and falls back to the next unlocked topic when there is no
    plan to read.
    """
    child = child_service.get_child_record(child_id)
    profile = child_service.get_child(child_id)

    subject_id, topic_id = plan_service.todays_topic(profile)
    if not topic_id:
        # A finished plan is not the same as no plan. Today's work being done is
        # the day closing warmly; only a child with no plan at all - a class with
        # nothing authored, or a database that is not answering - falls back to
        # the next unlocked topic, so infrastructure never costs a child a lesson.
        if plan_service.is_day_complete(profile):
            return _day_complete(child)
        subject_id, topic_id = daily_recommendation_service.next_topic(profile)
    if not topic_id:
        return _nothing_to_do(child)

    gate = plan_service.may_open(profile, topic_id)
    if not gate.allowed:  # pragma: no cover - the plan cursor cannot point off-plan
        return _day_complete(child)

    topic = curriculum_service.get_topic(topic_id)
    if not topic.available:
        return _nothing_to_do(child)

    state = _open_state(child, topic)
    child["current_subject_id"] = subject_id or topic.subject_id
    child["current_topic_id"] = topic.topic_id
    child_store.save(child)

    turn = _Turn(
        state=state,
        topic=topic,
        child=child,
        activity=None,
        event="TOPIC_STARTED" if state.phase == Phase.SET.value else "APP_OPENED",
        expects_answer=False,
    )
    return _build(turn)


def resume(session_id: str) -> ConductorDirective:
    """The same directive again, for a refresh or a second device.

    Nothing moves: re-reading the state is not an input, and a child who reloads
    the page must not lose a turn or be asked the question twice.
    """
    state = _read_state(session_id)
    child = child_service.get_child_record(state.child_id)
    topic = curriculum_service.get_topic(state.topic_id)
    activity = _current_activity(state, topic)
    phase = Phase(state.phase)
    return _build(
        _Turn(
            state=state,
            topic=topic,
            child=child,
            activity=activity if phase in (Phase.I_DO, Phase.WE_DO, Phase.YOU_DO) else None,
            event=_event_for_phase(phase),
            expects_answer=phase == Phase.YOU_DO and _needs_answer(activity),
        )
    )


def pause(session_id: str) -> ConductorDirective:
    """Stop for now, kindly, and keep the place."""
    state = _read_state(session_id)
    child = child_service.get_child_record(state.child_id)
    topic = curriculum_service.get_topic(state.topic_id)

    state.phase = Phase.CLOSE.value
    state.paused_for = "doubt"
    state.last_input_at = _now()
    _save_state(state)

    return _build(
        _Turn(
            state=state,
            topic=topic,
            child=child,
            activity=None,
            event="TOPIC_COMPLETED",
            expects_answer=False,
            close=CloseBlock(reason="paused", topic_completed=False),
            speech_override="Let us take a little break. We can come back any time.",
        )
    )


def send_input(session_id: str, payload: ConductorInput) -> ConductorDirective:
    """One child input, one directive. Everything in between is decided here."""
    state = _read_state(session_id)
    child = child_service.get_child_record(state.child_id)
    topic = curriculum_service.get_topic(state.topic_id)

    if payload.kind == "idle":
        turn = _handle_idle(state, child, topic)
    elif payload.kind == "doubt":
        return pause(session_id)
    elif payload.kind == "ready" or not _needs_answer(_current_activity(state, topic)):
        turn = _advance_phase(state, child, topic)
    else:
        turn = _handle_answer(state, child, topic, payload)

    turn.state.last_input_at = _now()
    _save_state(turn.state)
    child_store.save(child)
    return _build(turn)


# --------------------------------------------------------------------------
# The three kinds of turn
# --------------------------------------------------------------------------


def _advance_phase(state: _State, child: dict, topic: Topic) -> _Turn:
    """The guide finished talking. Move the class on by itself."""
    phase = Phase(state.phase)
    state.idle_rung = 0

    if phase == Phase.GREET:
        state.phase = Phase.SET.value
        return _Turn(state, topic, child, None, event="TOPIC_STARTED", expects_answer=False)

    if phase == Phase.SET:
        state.phase = Phase.I_DO.value
        activity = _current_activity(state, topic)
        return _Turn(
            state, topic, child, activity, event="TOPIC_QUESTION_LOADED", expects_answer=False
        )

    activity = _current_activity(state, topic)
    if activity is None:
        return _close_lesson(state, child, topic, reason="completed")

    sequence = _sequence_for(state, topic)
    following = next_in_sequence(sequence, phase)

    if following is None:
        # A presentational card has nothing to check: the next thing is the next
        # activity, and the class moves there without asking anyone.
        return _next_activity(state, child, topic)

    state.phase = following.value
    if following == Phase.WE_DO:
        state.scaffold_level = max(state.scaffold_level, 3)
    return _Turn(
        state,
        topic,
        child,
        activity,
        event="TOPIC_QUESTION_LOADED",
        expects_answer=following == Phase.YOU_DO,
    )


def _handle_idle(state: _State, child: dict, topic: Topic) -> _Turn:
    """The child said nothing. The server decides what silence means."""
    activity = _current_activity(state, topic)
    state.idle_rungs_hit += 1
    state.idle_rung = signal_engine.next_idle_rung(state.idle_rung)
    state.frustration_score = signal_engine.frustration(_signals_of(state))

    action, uses_model = signal_engine.idle_action(state.idle_rung - 1)

    if state.idle_rung >= len(signal_engine.IDLE_RUNGS):
        # The last rung never traps the child: it offers something else.
        return _close_lesson(state, child, topic, reason="end_kindly")

    if action == "do_together":
        state.phase = Phase.WE_DO.value
        state.scaffold_level = 4
    elif action == "re_explain_simpler":
        state.scaffold_level = min(4, state.scaffold_level + 1)
        state.ladder_rung = min(5, state.ladder_rung + 1)

    return _Turn(
        state,
        topic,
        child,
        activity,
        # Rung 3 is the only one that asks the model for words; the others are
        # the authored instruction and hint, repeated gently.
        event="HINT_REQUESTED" if uses_model else "TOPIC_QUESTION_LOADED",
        expects_answer=_needs_answer(activity),
        notes={"idle_rung": state.idle_rung, "idle_action": action},
    )


def _handle_answer(state: _State, child: dict, topic: Topic, payload: ConductorInput) -> _Turn:
    """Evaluate, commit, branch. In that order, and the model is not in it."""
    activity = _current_activity(state, topic)
    if activity is None:  # pragma: no cover - guarded by the caller
        return _close_lesson(state, child, topic, reason="completed")

    skill_id = learning_service.skill_slug(topic)
    state.current_skill_id = skill_id
    state.phase = Phase.CHECK.value

    # A microphone that could not hear is not a wrong answer.
    if payload.kind == "voice":
        state.speech_attempts += 1
        if payload.confidence < UNRESOLVED_SPEECH_CONFIDENCE:
            state.unresolved_speech += 1
            return _apply_branch(
                state,
                child,
                topic,
                activity,
                outcome=branch_engine.decide(_branch_input(state, topic, is_correct=False)),
                is_correct=None,
            )

    is_correct, normalized = activity_evaluators.evaluate(
        activity_evaluators.EvaluationInput(
            activity_type=activity.type,
            correct_answer=activity.correct_answer or "",
            options=activity.options,
            answer=payload.answer,
            confidence=payload.confidence,
            accepted_answers=tuple(activity.accept),
            open_ended=activity.open_ended,
        )
    )

    # 2 and 3: the truth, written before anything is said about it.
    record_attempt(
        child_id=state.child_id,
        session_id=state.session_id,
        activity_id=activity.activity_id,
        topic=topic.topic_id,
        skill=skill_id,
        level_id=topic.subject_id,
        child_answer=normalized,
        is_correct=is_correct,
        attempt_number=0 if is_correct else state.attempts_on_current + 1,
        form_signature=activity.type,
        forms_available=learning_service.forms_available(topic),
        # How much help was up when the child answered. A correct answer at S3
        # is weaker evidence than one at S0, and the mastery roll-up discounts
        # it accordingly - which is what makes WE DO safe to score at all.
        scaffold_level=state.scaffold_level,
    )
    retention_service.on_attempt(
        child_id=state.child_id,
        skill_id=skill_id,
        form_signature=activity.type,
        is_correct=is_correct,
    )

    if payload.latency_ms and payload.latency_ms < RETRY_BURST_MS and not is_correct:
        state.retry_burst_count += 1
    state.recent_answers = [*state.recent_answers, is_correct][-RECENT_ANSWER_WINDOW:]
    state.unresolved_speech = 0 if payload.kind == "voice" else state.unresolved_speech
    state.consecutive_correct = state.consecutive_correct + 1 if is_correct else 0
    state.frustration_score = signal_engine.frustration(_signals_of(state))
    if is_correct:
        state.correct_count += 1

    outcome = branch_engine.decide(_branch_input(state, topic, is_correct=is_correct))
    return _apply_branch(state, child, topic, activity, outcome=outcome, is_correct=is_correct)


def _branch_input(state: _State, topic: Topic, *, is_correct: bool) -> branch_engine.BranchInput:
    skill_id = learning_service.skill_slug(topic)
    with session_scope() as session:
        row = truth.mastery_for(session, child_id=UUID(state.child_id), skill_id=skill_id)
        mastery = row.mastery if row else 0.0
        mastery_map = truth.mastery_map(session, child_id=UUID(state.child_id))

    _, prerequisite_mastery = skill_graph.weakest_prerequisite(skill_id, mastery_map)
    age_band = "early" if curriculum_service.experience_mode_for_class(topic.class_id).mode_id == "early" else "standard"

    return branch_engine.BranchInput(
        is_correct=is_correct,
        attempts_on_current=state.attempts_on_current,
        skill_mastery=mastery,
        consecutive_correct=state.consecutive_correct,
        frustration_score=state.frustration_score,
        ladder_rungs_used=tuple(state.explanations_used),
        scaffold_level=state.scaffold_level,
        minutes_in_session=_minutes_in(state),
        target_minutes=branch_engine.target_minutes_for(age_band),
        modality=state.modality,
        unresolved_speech_streak=state.unresolved_speech,
        prerequisite_mastery=prerequisite_mastery,
        age_band=age_band,
    )


def _apply_branch(
    state: _State,
    child: dict,
    topic: Topic,
    activity: Activity,
    *,
    outcome: branch_engine.BranchOutcome,
    is_correct: bool | None,
) -> _Turn:
    """Turn one of the six decisions into the next state of the class."""
    decision = outcome.decision

    if decision == branch_engine.Branch.ADVANCE:
        turn = _next_activity(state, child, topic, celebrate=True)
        turn.branch = decision.value
        turn.is_correct = True
        return turn

    if decision == branch_engine.Branch.END_KINDLY:
        learning_service.mark_weak(child, topic)
        turn = _close_lesson(state, child, topic, reason="end_kindly")
        turn.branch = decision.value
        turn.is_correct = is_correct
        return turn

    if decision == branch_engine.Branch.SWITCH_MODALITY:
        state.modality = "tap"
        state.unresolved_speech = 0
        state.phase = Phase.YOU_DO.value
        return _Turn(
            state,
            topic,
            child,
            activity,
            event="TOPIC_QUESTION_LOADED",
            branch=decision.value,
            is_correct=is_correct,
            speech_override="Let us tap the answer this time.",
        )

    # Everything left teaches again: the question stays and the help goes up.
    state.attempts_on_current += 1
    state.scaffold_level = min(4, state.scaffold_level + outcome.scaffold_delta)
    state.ladder_rung = min(5, state.ladder_rung + 1)
    rung_name = f"L{state.ladder_rung}"
    if rung_name not in state.explanations_used:
        state.explanations_used.append(rung_name)

    if decision == branch_engine.Branch.PREREQUISITE:
        return _start_prerequisite(state, child, topic, outcome)

    state.phase = (
        Phase.YOU_DO.value if decision == branch_engine.Branch.SIMPLIFY else Phase.WE_DO.value
    )
    return _Turn(
        state,
        topic,
        child,
        activity,
        event="TOPIC_ANSWER_INCORRECT",
        branch=decision.value,
        is_correct=False,
        expects_answer=decision == branch_engine.Branch.SIMPLIFY,
    )


def _start_prerequisite(
    state: _State, child: dict, topic: Topic, outcome: branch_engine.BranchOutcome
) -> _Turn:
    """Park this question and quietly teach the thing underneath it.

    The child is not told they have gone backwards - "let us look at one small
    thing first" - and the exact place they were is kept, so the lesson comes
    back to the same question rather than restarting.
    """
    weakest, _ = skill_graph.weakest_prerequisite(state.current_skill_id, {})
    prerequisite_topic_id = weakest.split(":")[-1] if weakest else None
    prerequisite_topic = (
        curriculum_service.get_topic(prerequisite_topic_id) if prerequisite_topic_id else None
    )
    if prerequisite_topic is None:  # pragma: no cover - graph validated at startup
        state.phase = Phase.WE_DO.value
        return _Turn(state, topic, child, _current_activity(state, topic), event="TOPIC_ANSWER_INCORRECT")

    state.resume_payload = {
        "topic_id": state.topic_id,
        "cursor": state.cursor,
        "activity_ids": list(state.activity_ids),
    }
    state.paused_for = "prerequisite"
    # Three activities at most: this is a detour, not a second lesson.
    state.activity_ids = [
        activity.activity_id for activity in curriculum_service.get_activities(prerequisite_topic.topic_id)
    ][:3]
    state.cursor = 0
    state.attempts_on_current = 0
    state.phase = Phase.I_DO.value
    return _Turn(
        state,
        topic,
        child,
        _current_activity(state, prerequisite_topic),
        event="TOPIC_QUESTION_LOADED",
        branch=branch_engine.Branch.PREREQUISITE.value,
        expects_answer=False,
        speech_override="Let us look at one small thing first!",
    )


def _next_activity(state: _State, child: dict, topic: Topic, *, celebrate: bool = False) -> _Turn:
    """Move to the next thing in the lesson, or end it."""
    state.cursor += 1
    state.attempts_on_current = 0
    state.ladder_rung = 0
    state.explanations_used = []
    state.idle_rung = 0
    # The support comes back down for a new question. Fading it is the point of
    # having it at all.
    state.scaffold_level = max(0, state.scaffold_level - 1)

    activities = _activities(state, topic)
    if state.cursor >= len(activities):
        if state.paused_for == "prerequisite" and state.resume_payload:
            return _resume_after_prerequisite(state, child, topic)
        return _close_lesson(state, child, topic, reason="completed")

    state.phase = Phase.I_DO.value
    return _Turn(
        state,
        topic,
        child,
        activities[state.cursor],
        event="TOPIC_ANSWER_CORRECT" if celebrate else "TOPIC_QUESTION_LOADED",
        expects_answer=False,
    )


def _resume_after_prerequisite(state: _State, child: dict, topic: Topic) -> _Turn:
    payload = state.resume_payload or {}
    state.activity_ids = list(payload.get("activity_ids") or [])
    state.cursor = int(payload.get("cursor") or 0)
    state.paused_for = None
    state.resume_payload = None
    state.phase = Phase.WE_DO.value
    state.attempts_on_current = 0
    return _Turn(
        state,
        topic,
        child,
        _current_activity(state, topic),
        event="TOPIC_QUESTION_LOADED",
        expects_answer=False,
        speech_override="Now we know that one. Let us go back!",
    )


def _close_lesson(state: _State, child: dict, topic: Topic, *, reason: str) -> _Turn:
    """End the sitting. Warmly, always - a child is never told they failed."""
    # Out of the questions, not out of everything played. A teaching card is
    # watched, not answered, and counting it in the denominator would cap a
    # perfect lesson below its own passing score.
    questions = [activity for activity in _activities(state, topic) if _needs_answer(activity)]
    score = round((state.correct_count / len(questions)) * 100) if questions else 100

    award = {"passed": False, "topic_reward": 0, "perfect_bonus": 0, "feedback": ""}
    if reason == "completed":
        # The same deterministic scoring the `/learning` endpoints use: the
        # topic's own passing score decides, and the manifest's reward pays.
        award = learning_service.award_topic_completion(child, topic, score=score)
    elif reason in ("end_kindly", "session_overrun"):
        learning_service.mark_weak(child, topic)

    state.phase = Phase.CLOSE.value
    state.status = "mastered" if award.get("passed") else "parked"
    state.idle_rung = 0

    return _Turn(
        state,
        topic,
        child,
        None,
        event="TOPIC_COMPLETED",
        expects_answer=False,
        close=CloseBlock(
            reason=reason,  # type: ignore[arg-type]
            stars_earned=int(award.get("topic_reward", 0)) + int(award.get("perfect_bonus", 0)),
            topic_completed=bool(award.get("passed")),
            revisit_skill_id=state.current_skill_id if reason != "completed" else None,
        ),
        speech_override=(
            award.get("feedback", "")
            if reason == "completed"
            else "That one was tricky. You worked hard today - let us try something else!"
        ),
    )


def _day_complete(child: dict) -> ConductorDirective:
    """Today's plan is finished. The next level is tomorrow's, and that is a
    good thing to hear rather than a door being shut."""
    message = "You finished today's plan! Come back tomorrow for the next one."
    return ConductorDirective(
        session_id="",
        child_id=child["child_id"],
        topic_id="",
        phase="close",
        speech=SpeechBlock(text=message, speak=True),
        avatar=AvatarPayload(state="celebrating", message=message, speak=True, animationEffect="confetti"),
        next_input=NextInput(expects="ready", timeout_ms=0, on_timeout="ready"),
        close=CloseBlock(reason="day_complete"),
    )


def _nothing_to_do(child: dict) -> ConductorDirective:
    """Every playable topic is done. Say so kindly and stop."""
    message = "You have finished everything for today. Wonderful work!"
    return ConductorDirective(
        session_id="",
        child_id=child["child_id"],
        topic_id="",
        phase="close",
        speech=SpeechBlock(text=message, speak=True),
        avatar=AvatarPayload(state="celebrating", message=message, speak=True, animationEffect="confetti"),
        next_input=NextInput(expects="ready", timeout_ms=0, on_timeout="ready"),
        close=CloseBlock(reason="completed"),
    )


# --------------------------------------------------------------------------
# Voicing the step, and building the directive
# --------------------------------------------------------------------------


def _event_for_phase(phase: Phase) -> str:
    return {
        Phase.GREET: "APP_OPENED",
        Phase.SET: "TOPIC_STARTED",
        Phase.I_DO: "TOPIC_QUESTION_LOADED",
        Phase.WE_DO: "TOPIC_QUESTION_LOADED",
        Phase.YOU_DO: "TOPIC_QUESTION_LOADED",
        Phase.CHECK: "TOPIC_QUESTION_LOADED",
        Phase.BRANCH: "TOPIC_QUESTION_LOADED",
        Phase.CLOSE: "TOPIC_COMPLETED",
    }[phase]


def _client_activity(activity: Activity | None) -> Activity | None:
    """The activity as the child's device may see it.

    The answer key is stripped for anything answered by choosing or speaking:
    the server grades, so the client has no use for it, and a client that holds
    it is one screenshot away from being the thing that decided the star. Trace
    and other presentational activities keep theirs - the target shape is what
    the device draws, and it is judged from the gesture on the device.
    """
    if activity is None:
        return None
    if activity_evaluators.answer_kind(activity.type) == "presentational":
        return activity
    return activity.model_copy(update={"correct_answer": None, "accept": []})


def _visual_targets(activity: Activity | None) -> list[str]:
    if not activity:
        return []
    return [f"visual-item-{index}" for index in range(len(activity.visual_items))]


def _guide_voice(turn: _Turn) -> GuideResponse:
    """Ask the guide for the words, under the decision already taken.

    Everything the guide does here is the wiring from the previous phase of this
    work: the policy chooses the teaching strategy, the model writes the sentence
    only if a provider is configured, the safety filter trims it, and the
    strategy is recorded as spent. The conductor decides *when* to teach; the
    guide decides *how it sounds*.
    """
    state = turn.state
    activity = turn.activity
    visual_targets = _visual_targets(activity)
    question = None
    if activity is not None:
        question = {
            "activity_id": activity.activity_id,
            "topic": activity.type,
            "concept": activity.skill_id or activity.type,
            "learning_objective": turn.topic.objective,
            "prompt": activity.prompt,
            "answer_type": activity.type,
            "options": activity.options,
            "correct_answer": activity.correct_answer,
            "child_answer": "",
            "attempt": state.attempts_on_current,
            "hint": activity.hint,
            "visual_items": activity.visual_items,
            "accepted_answers": list(activity.accept),
        }

    request = GuideRequest(
        session_id=state.session_id,
        child_id=state.child_id,
        mode="learning",
        event=turn.event,  # type: ignore[arg-type]
        route=f"/class/{turn.topic.topic_id}",
        screen="conductor",
        feature=state.phase,
        class_id=turn.topic.class_id,
        experience_mode=curriculum_service.experience_mode_for_class(turn.topic.class_id).mode_id,
        question=question,  # type: ignore[arg-type]
        progress={
            "current_class": turn.topic.class_id,
            "current_subject": turn.topic.subject_id,
            "current_topic": turn.topic.topic_id,
            "weak_skills": turn.child.get("weak_skills", []),
            "session_stars": int(turn.child.get("stars", 0)),
        },  # type: ignore[arg-type]
        available_actions=LESSON_ACTIONS,  # type: ignore[arg-type]
        available_targets=LESSON_TARGETS,
        allowed_visual_targets=visual_targets,
    )
    try:
        return guide_agent_service.guide(request)
    except Exception:  # pragma: no cover - the class must not stop for this
        logger.exception("The guide could not voice this turn; using the activity's own prompt")
        message = (activity.prompt if activity else "Let us keep going.")
        return GuideResponse(
            message=message,
            strategy="read_question",
            avatar=AvatarPayload(state="speaking", message=message, speak=True, animationEffect="gentle_hint"),
            ui_action={"type": "none"},  # type: ignore[arg-type]
        )


def _early_teaching_line(turn: _Turn, voice: GuideResponse) -> str:
    """The playful, concrete version of this turn, for Play Group and Nursery.

    The policy has already chosen the strategy and the episode is already
    written; this only changes the *words*, and only for the age band that
    cannot use the guide's longer, more verbal sentences. A child who has never
    met the letter A hears "This is A. A says aa." and then "Together: aa...
    apple! Now you." instead of "Tap A." four times.

    Empty means "nothing better to say than what the guide wrote", and the
    guide's own line is kept.
    """
    if turn.activity is None or not voice.teaching_strategy:
        return ""
    if curriculum_service.experience_mode_for_class(turn.topic.class_id).mode_id != "early":
        return ""

    try:
        activities = curriculum_service.get_activities(turn.topic.topic_id)
        card = explain.card_for(turn.topic, turn.activity, activities)
    except Exception:  # pragma: no cover - a topic whose file moved under us
        return ""

    # The first time a question is put to the child, it is taught before it is
    # asked. "Tap the red one" means nothing to a two-year-old who has not just
    # been shown red - so they hear "This is red. Red like an apple. Now you
    # try. Tap the red one!" and only then is anything expected of them. On a
    # second attempt this stands aside: that turn belongs to the repair ladder.
    if turn.state.attempts_on_current == 0:
        script = explain.script_for(turn.topic, turn.activity, activities)
        if script:
            return script

    return explain.beat(
        strategy=voice.teaching_strategy,
        card=card,
        # Same question, same attempt, same words on a refresh; a new attempt
        # gets a different shape so nothing is said twice in a row.
        seed=f"{turn.state.session_id}:{turn.activity.activity_id}:{turn.state.attempts_on_current}",
    )


def _auto_advance_ms(text: str) -> int:
    words = max(1, len(text.split()))
    return max(MIN_AUTO_ADVANCE_MS, min(MAX_AUTO_ADVANCE_MS, words * MS_PER_WORD + 900))


def _expected_input(activity: Activity | None, modality: str) -> str:
    if activity is None:
        return "ready"
    kind = activity_evaluators.answer_kind(activity.type)
    if kind == "presentational":
        return "trace" if activity.trace_target else "ready"
    if kind == "spoken":
        return "voice" if modality != "tap" else "tap"
    return "tap"


def _build(turn: _Turn) -> ConductorDirective:
    """Assemble the one object the client renders."""
    state = turn.state
    topic = turn.topic
    mode = curriculum_service.experience_mode_for_class(topic.class_id)
    activity = turn.activity
    voice = _guide_voice(turn)

    text = turn.speech_override or _early_teaching_line(turn, voice) or voice.message
    phase = Phase(state.phase)

    scaffold = scaffold_engine.build(
        phase=phase,
        level=state.scaffold_level,
        options=activity.options if activity else [],
        correct_answer=activity.correct_answer if activity else None,
        visual_targets=_visual_targets(activity),
        max_choices=mode.max_choices_per_screen,
        co_narrate=text if phase == Phase.WE_DO else "",
    )
    presentation = scaffold_engine.presentation(
        touch_target_px=mode.touch_target_px,
        max_choices_per_screen=mode.max_choices_per_screen,
        text_density=mode.text_density,
        level=state.scaffold_level,
        frustration_score=state.frustration_score,
        options_shown=len(scaffold.options_shown),
    )

    expects = _expected_input(activity, state.modality) if turn.expects_answer else "ready"
    timeout_ms = signal_engine.idle_timeout_ms(mode.idle_thresholds_seconds, state.idle_rung)
    activities_total = len(state.activity_ids)

    return ConductorDirective(
        session_id=state.session_id,
        child_id=state.child_id,
        topic_id=topic.topic_id,
        phase=state.phase,  # type: ignore[arg-type]
        activity=_client_activity(activity),
        scaffold=ScaffoldBlock(**scaffold.__dict__),
        presentation=PresentationBlock(**presentation.__dict__),
        speech=SpeechBlock(
            text=text,
            language=topic.language,
            speak=True,
            voice_speed=presentation.narration_speed,
            source="llm" if voice.teaching_strategy and not turn.speech_override else "template",
        ),
        avatar=voice.avatar.model_copy(update={"message": text}),
        visual_action=turn.extra_visual or voice.visual_action,
        next_input=NextInput(
            expects=expects,  # type: ignore[arg-type]
            timeout_ms=timeout_ms,
            on_timeout="idle",
        ),
        progress=ProgressBlock(filled=state.correct_count, total=activities_total),
        # The class carries on by itself whenever nothing is expected of the
        # child. This is where the "next" button used to be.
        auto_advance_in_ms=None if turn.expects_answer or turn.close else _auto_advance_ms(text),
        close=turn.close,
        branch=turn.branch,
        teaching_strategy=voice.teaching_strategy,
    )
