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
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from app.conductor import branch as branch_engine
from app.conductor import echo as echo_engine
from app.conductor import explain
from app.conductor import scaffold as scaffold_engine
from app.conductor import signals as signal_engine
from app.conductor import skill_graph
from app.conductor import unexpected as unexpected_engine
from app.conductor.phases import Phase, next_in_sequence, teaching_sequence
from app.db.models import LessonState
from app.db.repositories import truth
from app.db.session import session_scope
from app.schemas.avatar import AvatarPayload
from app.schemas.conductor import (
    CloseBlock,
    ConductorDirective,
    ConductorInput,
    ListenBlock,
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
from app.services.answer_resolution_service import AnswerResolutionContext, resolve_answer
from app.services.child_speech_service import clean_child_speech
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
    echo_attempts: int
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
        echo_attempts=row.echo_attempts,
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
        row.echo_attempts = state.echo_attempts
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
            row.echo_attempts = 0
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
            # English, maths and Hindi are taught out loud, so those sittings
            # start in voice: the say-it-back beat runs, and an activity whose
            # answer is spoken by design gets the microphone rather than a
            # tap. Everything else starts tapping, exactly as before. The
            # branch engine can still drop a struggling child back to taps.
            row.modality = "voice" if echo_engine.subject_speaks(topic.subject_id) else "tap"
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
    activity = _current_activity(state, topic)
    return teaching_sequence(
        lesson_flow=topic.lesson_flow,
        needs_answer=_needs_answer(activity),
        echo=_echoes(state, topic, activity),
        draw=_is_drawing(activity),
    )


def _echoes(state: _State, topic: Topic, activity: Activity | None) -> bool:
    """Whether this card stops and listens after it has been explained.

    Three things all have to be true, and each of them is a boundary rather
    than a preference:

    * the subject is one that is taught out loud - English, maths, Hindi;
    * the card is a teaching card, so there is no answer key anywhere near the
      open microphone;
    * it is the *last* teaching card of the run, so a level that explains a
      letter over three cards - the shape, the sound, the word - is listened to
      once when the explanation is finished, not after every sentence;
    * the concept has a name worth saying back, which `echo.target_for` decides
      from the level's own authored content rather than by guessing.

    A drawing card is a teaching card by this codebase's reckoning - it has no
    answer - and is deliberately excluded. The order the child is taught in is
    explain, say it, draw; asking for the word again with a finger already on
    the screen interrupts the drawing rather than teaching anything.

    The modality is *not* one of them. A child who has been dropped back to
    tapping because the recogniser could not hear them keeps taps, which is what
    `state.modality` is for.
    """
    if state.echo_attempts >= echo_engine.ECHO_ASKS_PER_LESSON:
        # Already listened once in this sitting. The microphone is a moment near
        # the start of the lesson, not a checkpoint on every card: a class that
        # reopens it after each thing it explains turns a question the child
        # answers into something they have to get past.
        return False
    if state.modality == "tap" or _needs_answer(activity) or activity is None:
        return False
    if not echo_engine.subject_speaks(topic.subject_id):
        return False
    if _is_drawing(activity):
        return False
    if _is_teaching_card(_next_card(state, topic)):
        # The explanation is still running. Let it finish.
        return False
    return _echo_target(state, topic, activity).is_askable


def _is_drawing(activity: Activity | None) -> bool:
    """A card the child answers with a finger rather than a voice."""
    if activity is None:
        return False
    return bool(activity.trace_target) or "trace" in (activity.type or "").lower()


def _is_teaching_card(activity: Activity | None) -> bool:
    """A card that explains, as opposed to one that asks or one that is drawn."""
    return activity is not None and not _needs_answer(activity) and not _is_drawing(activity)


def _next_card(state: _State, topic: Topic) -> Activity | None:
    activities = _activities(state, topic)
    index = state.cursor + 1
    return activities[index] if 0 <= index < len(activities) else None


def _echo_target(state: _State, topic: Topic, activity: Activity | None) -> echo_engine.EchoTarget:
    """What this card asks the child to say back."""
    if activity is None:
        return echo_engine.EchoTarget()
    card = explain.card_for(topic, activity, _activities(state, topic))
    return echo_engine.target_for(card)


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


def open_class(child_id: str, topic_id: str | None = None) -> ConductorDirective:
    """Open today's class for this child. No menu, no choice, no taps.

    The topic comes from the frozen daily plan, so the app opens on the same
    lesson all day, and falls back to the next unlocked topic when there is no
    plan to read.

    `topic_id` is the one exception, and it is not the child choosing: Adventure
    is a browse of the map a grown-up sits through, and opening a level from
    there has to run *this* loop rather than a second one. It changes which
    topic is conducted and nothing else - the day's plan still decides whether
    that topic may be opened at all, so an off-plan level is refused here
    exactly as `/learning` refuses it.
    """
    child = child_service.get_child_record(child_id)
    profile = child_service.get_child(child_id)

    if topic_id:
        gate = plan_service.may_open(profile, topic_id)
        if not gate.allowed:
            raise app_error("NOT_TODAYS_PLAN", gate.message, 403)
        return _conduct_topic(child, topic_id, subject_id=None)

    # The day's first unfinished **level**. Every fifth day one of the day's
    # stages is a poem instead, and this loop cannot say one: a poem has no
    # manifest entry, no phases and no question, and asking `get_topic` for it
    # is a 404 - which is exactly what a child on a poem morning used to get,
    # for the rest of the day, because the cursor stays on the poem until
    # something finishes it. The web class says the poem; this one steps over it
    # rather than breaking on it, and leaves it unfinished for that class.
    subject_id, topic_id = plan_service.todays_level(profile)
    if not topic_id:
        # A finished plan is not the same as no plan. Today's work being done is
        # the day closing warmly - and so is a day whose only remaining stage is
        # a poem, because everything this loop can teach is behind it. Only a
        # child with no plan at all - a class with nothing authored, or a
        # database that is not answering - falls back to the next unlocked
        # topic, so infrastructure never costs a child a lesson.
        if plan_service.todays_plan(profile) is not None:
            return _day_complete(child)
        subject_id, topic_id = daily_recommendation_service.next_topic(profile)
    if not topic_id:
        return _nothing_to_do(child)

    gate = plan_service.may_open(profile, topic_id)
    if not gate.allowed:  # pragma: no cover - the plan cursor cannot point off-plan
        return _day_complete(child)

    return _conduct_topic(child, topic_id, subject_id=subject_id)


def _conduct_topic(child: dict, topic_id: str, *, subject_id: str | None) -> ConductorDirective:
    """Start or resume the class on one topic, the gate already passed."""
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
            activity=activity if phase in (Phase.I_DO, Phase.SAY_IT, Phase.WE_DO, Phase.YOU_DO) else None,
            event=_event_for_phase(phase),
            expects_answer=(phase == Phase.SAY_IT)
            or (phase == Phase.YOU_DO and (_needs_answer(activity) or _is_drawing(activity))),
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

    if payload.kind == "doubt":
        return pause(session_id)
    elif state.phase == Phase.SAY_IT.value:
        # The microphone is open and the class is waiting for the child to say
        # the thing back. Silence is handled here too: in this beat it means
        # "they did not say it", not "they wandered off", and the two are
        # answered very differently.
        turn = _handle_echo(state, child, topic, payload)
    elif payload.kind == "idle":
        turn = _handle_idle(state, child, topic)
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
    if following == Phase.SAY_IT:
        # Counted here, where the class actually asks, so the one ask this
        # sitting gets is spent by asking rather than by the child answering -
        # a child who says nothing has still been asked.
        state.echo_attempts += 1
    if following == Phase.WE_DO:
        state.scaffold_level = max(state.scaffold_level, 3)
    return _Turn(
        state,
        topic,
        child,
        activity,
        event="TOPIC_QUESTION_LOADED",
        expects_answer=following in (Phase.YOU_DO, Phase.SAY_IT),
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


# What the guide says when the child says it back. Warm, short, and about the
# saying rather than about being right - because nothing here was graded.
ECHO_PRAISE = (
    "Yes! You said it.",
    "Lovely voice!",
    "That is it - well said!",
)


def _handle_echo(state: _State, child: dict, topic: Topic, payload: ConductorInput) -> _Turn:
    """The child was asked to say the thing back. This is what came back.

    Nothing in this function records an attempt, touches mastery, awards a star
    or moves a skill. An echo is evidence about the *explanation*, not about the
    child: it either landed, in which case the class moves on, or it did not, in
    which case the class explains it once more in different words and then moves
    on anyway. The child is never asked a second time - a child who cannot say it
    out loud today is not a child who may not do the drawing.
    """
    activity = _current_activity(state, topic)
    target = _echo_target(state, topic, activity)
    raw = (payload.answer or "").strip()

    if payload.kind == "voice":
        state.speech_attempts += 1

    # The deterministic cleaner first: "ay", "tree", "do nahi teen". It is given
    # the words this card would accept and never the answer to any question,
    # because on a teaching card there is no question to have an answer to.
    cleaned = clean_child_speech(raw, activity.type if activity else "", list(target.contextual_strings))
    heard = cleaned.token or raw
    if not heard and payload.alternatives:
        # The recogniser's first guess was unusable; its second sometimes is not.
        heard = next((alt for alt in payload.alternatives if alt.strip()), "")

    verdict = echo_engine.judge(heard=heard, confidence=payload.confidence, target=target)

    if verdict.landed:
        state.unresolved_speech = 0
        turn = _after_echo(state, child, topic)
        turn.speech_override = random.choice(ECHO_PRAISE)
        turn.notes = {"echo": "matched", "heard": verdict.heard}
        return turn

    if verdict.outcome == "no_speech":
        state.unresolved_speech += 1

    said = unexpected_engine.classify(
        raw,
        # No options: a teaching card shows the child a thing, it does not
        # offer them a choice. Passing the accepted words here would let a
        # near-miss be re-read as an answer after the judge has said it is not.
        options=[],
        prompt=(activity.prompt if activity else ""),
        confidence=payload.confidence,
        attempts=state.echo_attempts,
    )
    state.frustration_score = signal_engine.frustration(_signals_of(state))

    if said.action == unexpected_engine.END_KINDLY:
        # A child asking for their mother, or asking to stop, is answered as a
        # person rather than as a wrong transcript.
        turn = _close_lesson(state, child, topic, reason="end_kindly")
        turn.speech_override = said.reply
        turn.notes = {"echo": verdict.outcome, "heard_as": said.kind}
        return turn

    if state.modality == "voice" and state.unresolved_speech >= branch_engine.UNRESOLVED_SPEECH_LIMIT:
        # Twice in a row the microphone heard nothing usable. That is a device
        # problem, and the child has now been asked to speak twice for reasons
        # that are not theirs. Put the mic away for this sitting and carry on.
        state.modality = "tap"
        state.unresolved_speech = 0
        turn = _after_echo(state, child, topic)
        turn.speech_override = "Let us keep going - I will do the talking!"
        turn.notes = {"echo": verdict.outcome, "heard_as": "microphone_unavailable"}
        return turn

    # Explain it again, differently - and then carry on. The child is asked to
    # say something back once in a lesson, so this does not come back round to
    # the microphone: `_echoes` has already spent this sitting's one ask, and
    # the class goes on to the drawing after this explanation.
    #
    # The rung and the spent-explanation list are what make the second
    # explanation a different one: the teaching policy reads them and will not
    # spend a strategy this child has already had.
    state.ladder_rung = min(5, state.ladder_rung + 1)
    state.scaffold_level = min(4, state.scaffold_level + 1)
    rung_name = f"L{state.ladder_rung}"
    if rung_name not in state.explanations_used:
        state.explanations_used.append(rung_name)
    state.phase = Phase.I_DO.value

    return _Turn(
        state,
        topic,
        child,
        activity,
        # The model is asked for words here, which is exactly where it belongs:
        # the decision to re-explain was taken above, deterministically.
        event="HINT_REQUESTED",
        expects_answer=False,
        notes={"echo": verdict.outcome, "heard_as": said.kind, "echo_attempt": state.echo_attempts},
    )


def _after_echo(state: _State, child: dict, topic: Topic) -> _Turn:
    """Carry on from the listening beat, however it went.

    A teaching card's sequence is (I DO, SAY IT), so there is normally nothing
    after this and the class moves to the next activity - the drawing, then the
    questions. `next_in_sequence` is still consulted so that a future sequence
    with something after SAY IT needs no change here.
    """
    activity = _current_activity(state, topic)
    following = next_in_sequence(_sequence_for(state, topic), Phase.SAY_IT)
    if following is None:
        return _next_activity(state, child, topic)

    state.phase = following.value
    return _Turn(
        state,
        topic,
        child,
        activity,
        event="TOPIC_QUESTION_LOADED",
        expects_answer=following in (Phase.YOU_DO, Phase.SAY_IT),
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

    # An utterance that is not an answer must not be scored as a wrong one.
    # "Pata nahi", the question read back, a story about a dog and forty seconds
    # of humming are all things a three-year-old says into an open microphone,
    # and all of them used to land in `attempts` as a failure. They are answered
    # as what they are instead, and nothing is written against the child.
    if payload.kind == "voice" and (activity.options or activity.accept):
        resolution = resolve_answer(
            AnswerResolutionContext(
                transcript=payload.answer,
                confidence=payload.confidence,
                answer_type=activity.type,
                correct_answer=activity.correct_answer,
                accepted_answers=list(activity.accept),
                options=list(activity.options),
                alternatives=list(payload.alternatives),
            )
        )
        # Only `input_kind` is read. The resolver is given the answer key so it
        # can build its candidate pool; what comes back here is "was this an
        # answer at all", never "was it the right one".
        if resolution.input_kind != "answer":
            return _handle_unexpected_answer(state, child, topic, activity, payload)

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


def _handle_unexpected_answer(
    state: _State,
    child: dict,
    topic: Topic,
    activity: Activity,
    payload: ConductorInput,
) -> _Turn:
    """The child spoke, and it was not an answer to this question.

    This is a first-class outcome, not an error path. It is never recorded as an
    attempt, so it cannot cost a star or move a mastery score, and the class
    responds to the kind of thing that was said: a child who asked to hear it
    again hears it again, a child who said "I don't know" is shown it rather
    than asked again, and a child who wants their mother is allowed to stop.
    """
    said = unexpected_engine.classify(
        payload.answer,
        options=list(activity.options),
        prompt=activity.prompt or "",
        confidence=payload.confidence,
        attempts=state.attempts_on_current,
    )
    if not payload.answer.strip():
        state.unresolved_speech += 1
    state.frustration_score = signal_engine.frustration(_signals_of(state))
    notes = {"heard_as": said.kind, "blameless": said.blameless}

    if said.action == unexpected_engine.END_KINDLY:
        turn = _close_lesson(state, child, topic, reason="end_kindly")
        turn.speech_override = said.reply
        turn.notes = notes
        return turn

    if state.modality == "voice" and state.unresolved_speech >= branch_engine.UNRESOLVED_SPEECH_LIMIT:
        # The microphone, not the child. Offer the same question as taps.
        state.modality = "tap"
        state.unresolved_speech = 0
        state.phase = Phase.YOU_DO.value
        return _Turn(
            state,
            topic,
            child,
            activity,
            event="TOPIC_QUESTION_LOADED",
            branch=branch_engine.Branch.SWITCH_MODALITY.value,
            speech_override="Let us tap the answer this time.",
            notes=notes,
        )

    if said.action == unexpected_engine.TOGETHER:
        # Stop testing and do it together. The help goes up; the score does not
        # move, because nothing was answered.
        state.scaffold_level = min(4, state.scaffold_level + 1)
        state.phase = Phase.WE_DO.value
        return _Turn(
            state,
            topic,
            child,
            activity,
            event="TOPIC_QUESTION_LOADED",
            expects_answer=False,
            speech_override=said.reply,
            notes=notes,
        )

    # RETRY and REPEAT both leave the question exactly where it was, with the
    # microphone open again and one kind sentence in front of it.
    state.phase = Phase.YOU_DO.value
    return _Turn(
        state,
        topic,
        child,
        activity,
        event="HINT_REQUESTED" if said.action == unexpected_engine.REPEAT else "TOPIC_QUESTION_LOADED",
        speech_override=said.reply,
        notes=notes,
    )


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
        # Two different things arrive here: the child got it, or the three
        # repairs are spent and the class is letting the question go. Only the
        # first is celebrated, and only the second is remembered as weak.
        moved_on_unsolved = outcome.reason == "attempts_exhausted"
        if moved_on_unsolved:
            learning_service.mark_weak(child, topic)
        turn = _next_activity(state, child, topic, celebrate=not moved_on_unsolved)
        turn.branch = decision.value
        turn.is_correct = False if moved_on_unsolved else True
        if moved_on_unsolved:
            # Never "you got that wrong": the child tried three times and the
            # class is the thing that moves, not them.
            turn.speech_override = "Good trying! Let us do the next one."
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
    # `echo_attempts` is deliberately *not* reset: it counts the asks made in
    # this sitting, and there is one. It goes back to zero when a new sitting
    # opens the lesson state, in `_open_state`.
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
        Phase.SAY_IT: "TOPIC_QUESTION_LOADED",
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


def _expected_input(activity: Activity | None, modality: str, phase: Phase) -> str:
    if phase == Phase.SAY_IT:
        # The whole point of the beat. It is only ever reached in a voice
        # sitting, so there is no tap fallback to fall back to here - the
        # fallback is leaving the beat entirely, which `_handle_echo` does.
        return "voice"
    if activity is None:
        return "ready"
    kind = activity_evaluators.answer_kind(activity.type)
    if kind == "presentational":
        return "trace" if activity.trace_target else "ready"
    if kind == "spoken":
        if modality != "tap":
            return "voice"
        # Dropped back to tapping - but a spoken card like `repeat_letter` has
        # no options, so "tap" here puts a child in front of a screen with
        # nothing on it and no way forward. A microphone that may not hear them
        # is worse than nothing to touch; the idle ladder is still the way out
        # if it really cannot.
        return "tap" if activity.options else "voice"
    return "tap"


def _build(turn: _Turn) -> ConductorDirective:
    """Assemble the one object the client renders."""
    state = turn.state
    topic = turn.topic
    mode = curriculum_service.experience_mode_for_class(topic.class_id)
    activity = turn.activity
    voice = _guide_voice(turn)

    phase = Phase(state.phase)
    text = turn.speech_override or _early_teaching_line(turn, voice) or voice.message

    listen_target = (
        _echo_target(state, topic, activity) if phase == Phase.SAY_IT else echo_engine.EchoTarget()
    )
    if phase == Phase.SAY_IT:
        # The guide does not improvise the ask. "Can you say A?" is a fixed,
        # authored sentence built from the concept card, so a child is never
        # asked to repeat something a model invented.
        text = echo_engine.ask(listen_target, attempt=max(0, state.echo_attempts - 1)) or text

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

    expects = _expected_input(activity, state.modality, phase) if turn.expects_answer else "ready"
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
        listen=ListenBlock(
            active=expects == "voice",
            expect=listen_target.thing,
            # On a question, the recogniser is biased towards what is on the
            # screen; on the say-it beat, towards the concept just taught. The
            # answer key is in neither: the options are what the child can
            # already see, and `scaffold.options_shown` is what they were given.
            contextual_strings=list(listen_target.contextual_strings)
            or list(scaffold.options_shown),
            language=topic.language,
            attempt=max(0, state.echo_attempts - 1),
            max_attempts=echo_engine.ECHO_ASKS_PER_LESSON,
            hold_open_ms=min(timeout_ms, 8000),
        ),
        progress=ProgressBlock(filled=state.correct_count, total=activities_total),
        # The class carries on by itself whenever nothing is expected of the
        # child. This is where the "next" button used to be.
        auto_advance_in_ms=None if turn.expects_answer or turn.close else _auto_advance_ms(text),
        close=turn.close,
        branch=turn.branch,
        teaching_strategy=voice.teaching_strategy,
        heard_as=turn.notes.get("heard_as"),
    )
