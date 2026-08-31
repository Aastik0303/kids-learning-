"""The AI Teacher, which is the class.

The agent teaches one step at a time (`agent.py`) from the notes and the
syllabus (`rag.py`), the answer is marked in pure Python (`stage.py`), the order
of the steps and the three turns a question gets are `lesson.py`, and this module
holds the sitting: one row per session, one row per turn, and the question the
bot asked kept **server-side** so the client never holds the answer to what it
is about to be asked.

Three shapes are worth saying plainly:

* **A concept is taught, not quizzed.** Explain it, hear it said back, watch it
  drawn, have it picked out of a few, then ask about it cold - `lesson.SEQUENCE`.
  A step that does not land is taught again *differently* up to three times and
  then the lesson moves on; a step the syllabus has nothing for is skipped.
* **Every question gets three turns and nobody is left stuck.** It is asked;
  if it does not land it is asked once more with a **hint** - a deeper
  explanation and two or three choices to pick between - and if that does not
  land either the **answer is told and explained**, and the class moves on. The
  third turn is not a test and is not marked. `lesson.py` owns that shape.
* **A stage is one item of today's frozen plan, and the day is all of them.**
  The plan is the day's work, so the stages *are* the schedule: **five questions
  finish a stage**, the next stage is the next thing the schedule holds, and
  when the last one is through the day is over. `status` goes to
  `day_complete` and the class will not reopen until tomorrow's plan exists.
  That lock is the whole of "finish the day and come back tomorrow"; nothing on
  the client decides it.
* **There is no score on the child's screen.** There is no score anywhere: the
  points this loop used to keep are gone. What the child sees is which question
  of the five they are on and which level of the day - progress, not a mark.
* **Finishing a stage is what moves the Adventure map.** The topic is handed to
  `learning_service.award_topic_completion` - the same deterministic scorer the
  conductor ends a lesson with - which marks the level done, pays the manifest's
  stars and unlocks the next level. Adventure shows that; it no longer teaches
  anything of its own.

The one rule still holds, and holds harder now that this writes a child's
progress: **no model decides correctness, stars or unlocking.** `stage.judge`
marks the answer in plain Python from the authored key, and
`award_topic_completion` decides the level from a score computed out of this
stage's own tally. The agent asks and explains; it never marks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from app.conductor import echo as echo_engine
from app.db.models import PlaygroundSession, PlaygroundTurn
from app.db.session import session_scope
from app.playground import agent, lesson, questions, rag, stage, visuals
from app.services import (
    child_service,
    child_store,
    curriculum_service,
    learning_service,
    plan_service,
)
from app.services.errors import app_error
from app.services.history_service import record_attempt
from app.services.safety_service import safe_text


logger = logging.getLogger(__name__)


@dataclass
class TeacherTurn:
    """One directive from the AI Teacher. The client renders it and reports back."""

    session_id: str
    child_id: str
    # --- where in the day and the stage this is, decided server-side -------
    # `stage` is which item of today's plan this is, and `stages_total` is how
    # many the day holds. The two together are the schedule, on the screen.
    # There is no points field and there is no score: five questions finish a
    # stage, and how many of them have been settled is the only number kept.
    stage: int
    questions_asked: int
    questions_per_stage: int
    # --- what is being taught ---------------------------------------------
    topic_id: str
    topic_title: str
    speech: str
    question: str
    strategy: str
    source: str
    retrieval: str
    # --- where in the lesson this is ---------------------------------------
    # "explain" / "say_it" / "draw" / "match" / "quiz", and what the client
    # should collect for it: "ready", "voice", "trace" or "tap".
    step: str = lesson.EXPLAIN
    expects: str = "ready"
    step_index: int = 0
    steps_total: int = len(lesson.SEQUENCE)
    # Which of the question's turns this is: 1 asks it, 2 asks it again with a
    # hint, 3 gives the answer. `is_hint` and `is_reveal` say which without the
    # client having to know the numbers.
    attempt: int = 1
    attempts_allowed: int = lesson.TRIES_PER_QUESTION
    is_hint: bool = False
    is_reveal: bool = False
    # What to trace, when the step is the drawing one.
    trace_target: str = ""
    options: list[str] = field(default_factory=list)
    visual_kind: str = ""
    visual_value: str = ""
    # --- the answer just given, when there was one -------------------------
    feedback: str = ""
    is_correct: bool | None = None
    advanced: bool = False
    # --- the day, and what finishing a stage did to the map ----------------
    stages_total: int = 0
    # Every stage of today's plan is through. The class is shut until tomorrow;
    # `speech` says so in words a child can hear.
    day_complete: bool = False
    # The level this stage just finished was marked done, and what that opened.
    topic_completed: bool = False
    next_topic_unlocked: bool = False
    stars_earned: int = 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# What the schedule says, and what a topic can be taught with
# --------------------------------------------------------------------------


def _plan_topics(child_id: str) -> tuple[str, list[str]]:
    """Today's topics in order, and the subject of the first one.

    The playground follows the schedule: the plan's own items *are* the stages.
    A finished plan still counts - going over today's work again is exactly what
    a playground is for - and only a child with no plan at all falls back to
    where their own progress is.
    """
    profile = child_service.get_child(child_id)

    plan = plan_service.todays_plan(profile)
    if plan is not None and plan.items:
        topics = [item["topic_id"] for item in plan.items if item.get("topic_id")]
        if topics:
            return _subject_of(topics[0]), topics

    if profile.current_topic_id:
        return (profile.current_subject_id or ""), [profile.current_topic_id]
    return "", []


def _subject_of(topic_id: str) -> str:
    try:
        return curriculum_service.get_topic(topic_id).subject_id
    except Exception:  # pragma: no cover - a topic id the manifest no longer has
        return ""


def _class_of(topic_id: str) -> str:
    """Which class this topic belongs to.

    Retrieval is fenced on it, so a Play Group turn cannot be taught out of the
    UKG pages however close the words are. That is what was making the questions
    too old for the child in front of them.
    """
    if not topic_id:
        return ""
    try:
        return curriculum_service.get_topic(topic_id).class_id
    except Exception:  # pragma: no cover - a topic id the manifest no longer has
        return ""


def _age_band(class_id: str) -> str:
    """"Play Group, where children are 2 to 3 years old" - said to the model.

    A prompt that only knows "a child aged 2 to 6" writes for the top of that
    range, and the top of that range is three years older than the child.
    """
    if not class_id:
        return ""
    try:
        detail = curriculum_service.get_class(class_id)
    except Exception:  # pragma: no cover - a class the manifest no longer has
        return ""
    return f"{detail.title}, where children are {detail.min_age} to {detail.max_age} years old"


def _topic_title(topic_id: str) -> str:
    if not topic_id:
        return "today's lesson"
    try:
        return curriculum_service.get_topic(topic_id).title
    except Exception:  # pragma: no cover - a topic id the manifest no longer has
        return topic_id


def _steps_for(topic_id: str, subject_id: str) -> tuple[str, ...]:
    """The steps this topic actually has.

    `can_say` follows the rule the real class uses for its microphone - English,
    maths and Hindi, and only for a letter or a number - so the playground never
    opens a mic on a colour. `can_draw` is whatever the author wrote a tracing
    card for.
    """
    kinds = rag.topic_kinds(topic_id)
    concept = visuals.from_concept(_topic_title(topic_id))
    can_say = echo_engine.subject_speaks(subject_id) and concept.kind in {"letter", "number"}
    return lesson.sequence_for(can_say=can_say, can_draw="draw" in kinds)


def _trace_target(topic_id: str) -> str:
    """What the drawing step asks for, taken from the author's own tracing card."""
    try:
        activities = curriculum_service.get_activities(topic_id)
    except Exception:  # pragma: no cover - a topic with no authored content
        activities = []
    for activity in activities:
        target = getattr(activity, "trace_target", "")
        if target:
            return target
    concept = visuals.from_concept(_topic_title(topic_id))
    return concept.value if concept.kind in {"letter", "number"} else ""


# --------------------------------------------------------------------------
# One turn
# --------------------------------------------------------------------------


def _mode_for(step: lesson.Step) -> str:
    """Which of a question's three turns this is, in the agent's own words."""
    if step.is_reveal:
        return agent.REVEAL
    if step.is_hint:
        return agent.HINT
    return agent.ASK


def _recent_turns(session, row: PlaygroundSession) -> list[dict]:
    """The sitting so far, oldest first: the class's memory of its own words.

    Every turn used to be written from nothing. The log was already here -
    `playground_turns` has held what was said, what was asked and what came back
    since the loop was built - and nothing read it, so a hint could repeat its
    own explanation word for word and the teacher could spend the same everyday
    example twice in a row.

    It is a **reminder handed to the model and nothing else**. The step, the
    strategy and the authored question still decide what the turn is, and
    `stage.judge` still marks in pure Python from the authored key. A memory that
    could move a verdict would be a model upstream of a star.
    """
    try:
        rows = list(
            session.scalars(
                select(PlaygroundTurn)
                .where(PlaygroundTurn.session_id == row.session_id)
                .order_by(PlaygroundTurn.created_at.desc())
                .limit(agent.MEMORY_TURNS)
            ).all()
        )
    except Exception:  # pragma: no cover - the log is not worth a failed turn
        logger.exception("Could not read the sitting's own turns")
        return []
    return [
        {
            "explanation": turn.explanation,
            "question": turn.question,
            "child_answer": turn.child_answer,
            "is_correct": turn.is_correct,
        }
        for turn in reversed(rows)
    ]


def _teach_step(
    row: PlaygroundSession,
    session=None,
    *,
    feedback: str = "",
    verdict_bits: dict | None = None,
) -> TeacherTurn:
    """Run the agent for the step the sitting is on, and write it onto the row.

    `session` is passed only so the turn can be given the sitting's own memory;
    a caller without one simply teaches without it.
    """
    steps = _steps_for(row.topic_id, row.subject_id)
    step = lesson.current(steps, row.step_index, row.step_tries)
    title = _topic_title(row.topic_id)
    mode = _mode_for(step)
    class_id = _class_of(row.topic_id)

    taught = agent.teach(
        subject=row.subject_id,
        topic=title,
        topic_id=row.topic_id,
        class_id=class_id,
        age_band=_age_band(class_id),
        step=step.name,
        spent=list(row.strategies_spent or []),
        mode=mode,
        # The syllabus's own question for this turn, when the step is one the
        # author wrote questions for. Walked by how many of the stage's five
        # have been settled, so five questions are five different ones rather
        # than the same one five times.
        asked=questions.pick(row.topic_id, nth=row.questions_asked),
        # A hint and a reveal are about the question already in front of the
        # child, so they are handed it rather than writing one.
        question=row.pending_question,
        answer=row.pending_answer,
        offered=list(row.pending_options or []),
        # What this sitting has already said, so the class does not teach the
        # same thing in the same words twice.
        memory=_recent_turns(session, row) if session is not None else [],
    )

    # The same filter the guide's words go through. A playground is still a
    # child's screen.
    explanation = safe_text(taught.explanation) or taught.explanation
    question = (safe_text(taught.question) or taught.question) if taught.question else ""

    if mode == agent.ASK:
        row.pending_question = question
        row.pending_answer = taught.expected_answer
        row.pending_accept = list(taught.accept)
        row.pending_options = list(taught.options)
    elif mode == agent.HINT:
        # The question and its answer do not move on a hint - only the choices
        # do, and they are the hint. Rewriting `pending_answer` here would let a
        # second telling quietly change what the child is being marked against.
        row.pending_options = list(taught.options)
    else:
        # A reveal has nothing left to answer: the answer has just been said.
        _clear_pending(row)
    row.step_index = step.index
    row.step_tries = step.tries
    # The row's own copy of the stage is a mirror of the plan cursor and nothing
    # more. Writing it here means a sitting from before the schedule changed
    # cannot go on claiming a stage the day does not have.
    row.stage = row.plan_index + 1
    spent = list(row.strategies_spent or [])
    if taught.strategy not in spent:
        spent.append(taught.strategy)
    row.strategies_spent = spent
    row.updated_at = _now()

    bits = verdict_bits or {}
    return TeacherTurn(
        session_id=row.session_id,
        child_id=str(row.child_id),
        # A stage is a plan item, so the stage number is where in the day this
        # is. It is derived rather than counted: two numbers for one fact is how
        # a scoreboard and a schedule come to disagree.
        stage=row.plan_index + 1,
        stages_total=len(row.plan_topics or []) or 1,
        questions_asked=row.questions_asked,
        questions_per_stage=stage.QUESTIONS_PER_STAGE,
        topic_id=row.topic_id,
        topic_title=title,
        speech=explanation,
        question=question,
        strategy=taught.strategy,
        source=taught.source,
        retrieval=rag.backend(),
        step=step.name,
        expects=step.expects,
        step_index=step.index,
        steps_total=len(steps),
        attempt=step.tries + 1,
        is_hint=step.is_hint,
        is_reveal=step.is_reveal,
        trace_target=_trace_target(row.topic_id) if step.name == lesson.DRAW else "",
        options=list(taught.options),
        visual_kind=taught.visual.kind,
        visual_value=taught.visual.value,
        feedback=feedback,
        is_correct=bits.get("is_correct"),
        advanced=bool(bits.get("advanced")),
        topic_completed=bool(bits.get("topic_completed")),
        next_topic_unlocked=bool(bits.get("next_topic_unlocked")),
        stars_earned=int(bits.get("stars_earned") or 0),
    )


def _log(row: PlaygroundSession, turn: TeacherTurn, session) -> None:
    session.add(
        PlaygroundTurn(
            session_id=row.session_id,
            stage=row.plan_index + 1,
            strategy=turn.strategy,
            source=turn.source,
            explanation=turn.speech,
            question=turn.question,
        )
    )


# --------------------------------------------------------------------------
# The day: when it is over, and what finishing a stage does to the map
# --------------------------------------------------------------------------

# What is said when the last stage of the day is through. The day being finished
# is good news, and the next one opening tomorrow is the good news rather than a
# door closing - the same thing `plan_service` says when it is asked.
DAY_DONE_SPEECH = (
    "That is your whole class for today, all finished. You worked so hard! "
    "Come back tomorrow and we will learn the next one together."
)


def _class_intro(row: PlaygroundSession, topic_title: str) -> str:
    """The two or three lines the class opens with, before any teaching.

    A child dropped straight into an explanation of a letter has been given no
    way in - they do not know who is talking, how long this is, or what happens
    if they get something wrong. So the class says hello, says what today holds,
    and says how it will go, including the promise the three turns keep: a
    question that will not come is helped, and then answered.

    It is said once, when the sitting opens. A reload teaches the step again; it
    does not re-introduce a class the child is already in the middle of.
    """
    stages = len(row.plan_topics or []) or 1
    lessons = "one lesson" if stages == 1 else f"{stages} lessons"
    return (
        f"Hello! I am so glad you came to class today. "
        f"We have {lessons} to do together, and we are starting with {topic_title}. "
        f"I will show you what it is first, and then I will ask you "
        f"{stage.QUESTIONS_PER_STAGE} little questions - and if one is tricky, "
        f"I will help you with it and then tell you the answer."
    )


def _day_done_turn(
    row: PlaygroundSession, *, feedback: str = "", bits: dict | None = None
) -> TeacherTurn:
    """The locked turn: nothing to answer, nothing to open, come back tomorrow.

    `expects` is "done", which is the client's whole instruction. It renders the
    words and the schedule and offers no way on, because there is no way on -
    tomorrow's plan does not exist yet and will not until tomorrow.
    """
    marks = bits or {}
    total = len(row.plan_topics or []) or 1
    return TeacherTurn(
        session_id=row.session_id,
        child_id=str(row.child_id),
        stage=total,
        stages_total=total,
        questions_asked=row.questions_asked,
        questions_per_stage=stage.QUESTIONS_PER_STAGE,
        topic_id=row.topic_id,
        topic_title=_topic_title(row.topic_id),
        speech=DAY_DONE_SPEECH,
        question="",
        strategy="",
        source="deterministic",
        retrieval=rag.backend(),
        step=lesson.EXPLAIN,
        expects="done",
        step_index=0,
        steps_total=1,
        feedback=feedback,
        # The answer that happened to be the last one of the day is still an
        # answer: the tick belongs on it, not swallowed by the goodbye.
        is_correct=marks.get("is_correct"),
        day_complete=True,
        topic_completed=bool(marks.get("topic_completed")),
        next_topic_unlocked=bool(marks.get("next_topic_unlocked")),
        stars_earned=int(marks.get("stars_earned") or 0),
    )


def _award_level(row: PlaygroundSession) -> dict:
    """Hand the finished stage to the class's own deterministic scorer.

    This is the join between the AI Teacher and the Adventure map, and it is one
    function call on purpose. `award_topic_completion` is what the conductor ends
    a lesson with: the topic's own `passing_score` decides whether it is done,
    the manifest's `star_reward` pays, the next level in sort order unlocks, and
    the certificate is re-checked. Two implementations of "did this level pass?"
    would be two answers to the only question the child cares about.

    The score is this stage's own tally and nothing else - no model has been
    upstream of either number, because `stage.judge` marked every one of them.
    """
    if not row.topic_id or not row.topic_answered:
        return {}
    try:
        topic = curriculum_service.get_topic(row.topic_id)
    except Exception:  # pragma: no cover - a topic id the manifest no longer has
        return {}
    if not topic.available:
        return {}

    score = round((row.topic_correct / row.topic_answered) * 100)
    child = child_store.get(str(row.child_id))
    award = learning_service.award_topic_completion(child, topic, score=score)
    child_store.save(child)
    return award


def _open_stage(row: PlaygroundSession, topic_id: str) -> None:
    """Start a stage on `topic_id`, from the top and with a clean tally."""
    row.topic_id = topic_id
    row.subject_id = _subject_of(topic_id)
    row.stage = row.plan_index + 1
    row.step_index = 0
    row.step_tries = 0
    row.strategies_spent = []
    row.questions_asked = 0
    row.topic_correct = 0
    row.topic_answered = 0
    _clear_pending(row)


def _finish_stage(row: PlaygroundSession) -> tuple[dict, bool]:
    """Close the stage the sitting is on and move to the next one.

    Returns what the award came to and whether that was the last stage of the
    day. Ending the day writes `day_complete` on the row, which is the lock: the
    next `open_session` reads it and refuses to teach again until tomorrow.
    """
    award = _award_level(row)
    topics = list(row.plan_topics or [])

    if not topics or row.plan_index + 1 >= len(topics):
        row.status = "day_complete"
        row.plan_index = max(len(topics) - 1, 0)
        row.stage = row.plan_index + 1
        _clear_pending(row)
        row.updated_at = _now()
        return award, True

    row.plan_index += 1
    _open_stage(row, topics[row.plan_index])
    return award, False


def _stage_bits(award: dict) -> dict:
    """What the client is told about a level that has just been finished."""
    return {
        "topic_completed": bool(award.get("passed")),
        "next_topic_unlocked": bool(award.get("next_topic_unlocked")),
        "stars_earned": int(award.get("topic_reward", 0)) + int(award.get("perfect_bonus", 0)),
    }


# --------------------------------------------------------------------------
# The sitting
# --------------------------------------------------------------------------


def open_session(child_id: str) -> TeacherTurn:
    """Start or resume today's class.

    Four answers, in order, and only the last one teaches anything:

    - **today's plan is already finished** - the class is shut. Whatever
      finished it, the day is the day;
    - **there is a `day_complete` row for today** - the same answer, from this
      sitting's own record of having ended;
    - **the in-progress row belongs to an earlier day** - it is yesterday's, so
      it is closed and today starts clean rather than resuming last night's
      half-taught stage;
    - **otherwise** - teach the step the sitting is on.
    """
    profile = child_service.get_child(child_id)
    subject_id, topics = _plan_topics(child_id)
    child_uuid = UUID(profile.child_id)
    today = date.today()

    with session_scope() as session:
        row = session.scalar(
            select(PlaygroundSession)
            .where(PlaygroundSession.child_id == child_uuid)
            .order_by(PlaygroundSession.started_at.desc())
        )

        # The day being over is the schedule's call, not this sitting's: a plan
        # finished through any path shuts the class until tomorrow.
        if plan_service.is_day_complete(profile, today=today):
            if row is None or row.plan_date != today:
                row = PlaygroundSession(
                    child_id=child_uuid,
                    session_id=f"teach_{uuid4().hex}",
                    plan_date=today,
                    plan_topics=topics,
                    plan_index=max(len(topics) - 1, 0),
                    subject_id=subject_id,
                    topic_id=topics[-1] if topics else "",
                    status="day_complete",
                )
                session.add(row)
                session.flush()
            else:
                row.status = "day_complete"
            return _day_done_turn(row)

        if row is not None and (row.plan_date != today or row.status != "in_progress"):
            # Yesterday's sitting, or one that already ended. Either way it is
            # not today's class, and today's starts from the top of the plan.
            row = None

        # Whether this call is the one that starts today's class, which is the
        # only one that says hello.
        opening = row is None

        if row is None:
            row = PlaygroundSession(
                child_id=child_uuid,
                session_id=f"teach_{uuid4().hex}",
                plan_date=today,
                plan_topics=topics,
                plan_index=0,
                subject_id=subject_id,
                topic_id=topics[0] if topics else "",
            )
            session.add(row)
            session.flush()
        elif topics and list(row.plan_topics or []) != topics:
            # The plan has been rebuilt underneath the sitting: follow it rather
            # than carrying on with a list that is no longer the day.
            row.plan_topics = topics
            row.plan_index = min(row.plan_index, len(topics) - 1)
            _open_stage(row, topics[row.plan_index])
        elif topics:
            # The stage the day is actually on. A level finished elsewhere - or
            # on an earlier visit - must not be taught again while the rest of
            # the day is still waiting.
            _resume_at_plan_cursor(row, profile, topics)

        # Opening the tab teaches the current step again on a clean menu of ways
        # to teach it; an unanswered question from an hour ago is owed nothing.
        row.strategies_spent = []

        turn = _teach_step(row, session)
        if opening:
            turn.speech = f"{_class_intro(row, turn.topic_title)} {turn.speech}".strip()
        _log(row, turn, session)
        return turn


def _resume_at_plan_cursor(row: PlaygroundSession, profile, topics: list[str]) -> None:
    """Point the sitting at the first stage today's plan has not finished.

    Only ever forwards. The plan's cursor is the day's own record of what is
    done; a sitting behind it would teach a finished level again while the rest
    of the day waited, and a sitting dragged backwards would lose the stage the
    child is in the middle of.
    """
    plan = plan_service.todays_plan(profile)
    if plan is None or plan.current_topic_id is None:
        return
    try:
        index = topics.index(plan.current_topic_id)
    except ValueError:
        return
    if index <= row.plan_index:
        return
    row.plan_index = index
    _open_stage(row, topics[index])


def answer(session_id: str, said: str) -> TeacherTurn:
    """The child answered. Mark it here, in Python, and teach the next turn.

    Three turns to a question, and only the first two are answers:

    1. it is asked, and a right answer settles it;
    2. a wrong one brings the **hint** - the thing explained again and more
       deeply, and two or three choices to pick between;
    3. a second wrong one brings the **answer**, told and explained, and then the
       class moves on. That turn has nothing to answer, so the "answer" that
       arrives for it is only the child saying they are ready.

    A question settles once, however many turns it took, and five settled
    questions finish the stage.
    """
    with session_scope() as session:
        row = session.scalar(
            select(PlaygroundSession).where(PlaygroundSession.session_id == session_id)
        )
        if row is None:
            raise app_error("PLAYGROUND_SESSION_GONE", "Let us start that again.", 404)
        if row.status == "day_complete":
            return _day_done_turn(row)

        steps = _steps_for(row.topic_id, row.subject_id)
        step = lesson.current(steps, row.step_index, row.step_tries)

        # The turn that gave the answer away. There was nothing to answer and
        # nothing to mark - the child has heard it, and that question is finished
        # with. It counts as one of the five, and as one that did not land, so
        # the level's own score tells the truth about how the stage went.
        if step.is_reveal:
            _leave_question(row, steps, step)
            return _settle(row, session, correct=False, mark=None, feedback="")

        # Explaining and drawing are not questions. The child has watched, or
        # has drawn; the lesson moves on and nothing is marked.
        if not step.is_scored or not row.pending_question:
            following = lesson.advance(steps, step)
            row.step_index, row.step_tries = following.index, following.tries
            row.strategies_spent = []
            _clear_pending(row)
            turn = _teach_step(row, session, feedback=_moving_on(step.name))
            _log(row, turn, session)
            return turn

        verdict = stage.judge(
            said=said,
            expected=row.pending_answer,
            accept=list(row.pending_accept or []),
            # What was on the screen. A tap is marked by which button it was,
            # not by word-matching its label against the answer - the label is
            # the answer dressed up for a child ("standing line ⬇️" for
            # `standing_line`), and matching the two as words is what marked a
            # child wrong for tapping the right box.
            offered=list(row.pending_options or []),
        )

        session.add(
            PlaygroundTurn(
                session_id=row.session_id,
                stage=row.plan_index + 1,
                strategy=(row.strategies_spent or ["S1_TELL"])[-1],
                source="deterministic",
                question=row.pending_question,
                child_answer=said,
                is_correct=verdict.is_correct,
            )
        )
        # Every try is written to the attempt log, both of them: mastery and the
        # weak-skill list are about what the child could do, and a question that
        # took two goes is not the same history as one that took one.
        _record_attempt(row, step, said=said, is_correct=verdict.is_correct)

        if verdict.is_correct:
            _leave_question(row, steps, step)
            return _settle(row, session, correct=True, mark=True, feedback=agent.praise())

        # Not right, and not finished either. The same question stays in front of
        # the child - `pending_answer` and `pending_accept` are deliberately left
        # alone - and the next turn is the hint, or the answer.
        following = lesson.after_answer(steps, step, is_correct=False)
        row.step_index, row.step_tries = following.index, following.tries
        turn = _teach_step(
            row,
            session,
            feedback=agent.reassure() if following.is_reveal else agent.encourage(),
            verdict_bits={"is_correct": False, "advanced": False},
        )
        _log(row, turn, session)
        return turn


def _leave_question(
    row: PlaygroundSession, steps: tuple[str, ...], step: lesson.Step
) -> None:
    """Done with this question: on to the next kind of knowing, on a clean menu."""
    following = lesson.advance(steps, step)
    row.step_index, row.step_tries = following.index, following.tries
    row.strategies_spent = []
    _clear_pending(row)


def _settle(
    row: PlaygroundSession,
    session,
    *,
    correct: bool,
    mark: bool | None,
    feedback: str,
) -> TeacherTurn:
    """One of the stage's five questions is finished with, and the lesson moves on.

    Called once per *question*, never once per answer: a question that took a
    hint and then the answer is still one question, and its three turns are three
    goes at the same one.

    `correct` is what goes into the stage's tally, which is what decides whether
    the level passed. `mark` is what the child is shown - `None` for the question
    that ended in being told the answer, because there is no tick or cross to put
    on a turn that was teaching rather than testing.
    """
    progress = stage.settle(stage=row.plan_index + 1, questions_asked=row.questions_asked)
    row.questions_asked = progress.questions_asked
    row.topic_answered += 1
    row.topic_correct += 1 if correct else 0

    if not progress.stage_complete:
        turn = _teach_step(
            row, session, feedback=feedback, verdict_bits={"is_correct": mark, "advanced": False}
        )
        _log(row, turn, session)
        return turn

    # Five questions is the whole stage. The level goes to the same
    # deterministic scorer the conductor ends a lesson with, out of this stage's
    # own tally, and the day moves on to the next thing the schedule holds.
    award, day_over = _finish_stage(row)
    bits = _stage_bits(award)
    if bits["topic_completed"]:
        feedback = f"{feedback} {award.get('feedback', '')}".strip()
    if day_over:
        turn = _day_done_turn(row, feedback=feedback, bits={**bits, "is_correct": mark})
        _log(row, turn, session)
        return turn
    turn = _teach_step(
        row,
        session,
        feedback=feedback,
        verdict_bits={"is_correct": mark, "advanced": True, **bits},
    )
    _log(row, turn, session)
    return turn


def _record_attempt(
    row: PlaygroundSession, step: lesson.Step, *, said: str, is_correct: bool
) -> None:
    """Put the answer in the one attempt log everything downstream reads.

    Mastery, the weak-skill list the planner reorders on, and the learned
    policy's reward all read `attempts`. A teaching loop that graded an answer
    and kept the verdict to itself would leave every one of them reading a
    partial history and never say so. `is_correct` arrives here from
    `stage.judge` - plain Python over the authored key - and from nothing else.
    """
    if not row.topic_id:
        return
    record_attempt(
        child_id=str(row.child_id),
        session_id=row.session_id,
        activity_id=f"teacher_{step.name}",
        topic=row.topic_id,
        skill=f"{row.subject_id}:{row.topic_id}" if row.subject_id else row.topic_id,
        child_answer=said,
        is_correct=is_correct,
        # Which of this question's two tries it was, not how far into the stage
        # the child is: an attempt number is about one question.
        attempt_number=step.tries + 1,
    )


def ask(session_id: str, question: str) -> TeacherTurn:
    """The child asked something of their own. Answer it; move nothing.

    The step stays where it was, the question the bot had already asked is still
    waiting, no strategy is spent and nothing is marked. A child interrupting to
    ask why a circle is round is the most cooperative thing they can do, and the
    app answering them is the whole point of a microphone that is not only for
    answers.
    """
    with session_scope() as session:
        row = session.scalar(select(PlaygroundSession).where(PlaygroundSession.session_id == session_id))
        if row is None:
            raise app_error("PLAYGROUND_SESSION_GONE", "Let us start that again.", 404)

        if row.status == "day_complete":
            return _day_done_turn(row)

        title = _topic_title(row.topic_id)
        answer_text, source = agent.answer_question(
            topic=title,
            topic_id=row.topic_id,
            question=question,
            # The child's question lands in the middle of a lesson, so the
            # answer is given what the lesson has just been saying.
            memory=_recent_turns(session, row),
        )
        answer_text = safe_text(answer_text) or answer_text
        row.updated_at = _now()

        steps = _steps_for(row.topic_id, row.subject_id)
        step = lesson.current(steps, row.step_index, row.step_tries)

        session.add(
            PlaygroundTurn(
                session_id=row.session_id,
                stage=row.plan_index + 1,
                strategy="ASKED",
                source=source,
                explanation=answer_text,
                question=question,
            )
        )

        return TeacherTurn(
            session_id=row.session_id,
            child_id=str(row.child_id),
            stage=row.plan_index + 1,
            stages_total=len(row.plan_topics or []) or 1,
            questions_asked=row.questions_asked,
            questions_per_stage=stage.QUESTIONS_PER_STAGE,
            topic_id=row.topic_id,
            topic_title=title,
            speech=answer_text,
            question=row.pending_question,
            strategy=(row.strategies_spent or [""])[-1],
            source=source,
            retrieval=rag.backend(),
            step=step.name,
            expects=step.expects,
            step_index=step.index,
            steps_total=len(steps),
            attempt=step.tries + 1,
            is_hint=step.is_hint,
            is_reveal=step.is_reveal,
            trace_target=_trace_target(row.topic_id) if step.name == lesson.DRAW else "",
            options=list(row.pending_options or []),
            visual_kind="",
            visual_value="",
        )


def _clear_pending(row: PlaygroundSession) -> None:
    row.pending_question = ""
    row.pending_answer = ""
    row.pending_accept = []
    row.pending_options = []


def _moving_on(step_name: str) -> str:
    """What is said when a step that is not marked is finished."""
    if step_name == lesson.DRAW:
        return "You drew it!"
    if step_name == lesson.EXPLAIN:
        return ""
    return "Good!"


def read_session(session_id: str) -> TeacherTurn:
    """The same sitting again, with nothing moved. Safe after a reload."""
    with session_scope() as session:
        row = session.scalar(select(PlaygroundSession).where(PlaygroundSession.session_id == session_id))
        if row is None:
            raise app_error("PLAYGROUND_SESSION_GONE", "Let us start that again.", 404)
        if row.status == "day_complete":
            return _day_done_turn(row)

        steps = _steps_for(row.topic_id, row.subject_id)
        step = lesson.current(steps, row.step_index, row.step_tries)
        return TeacherTurn(
            session_id=row.session_id,
            child_id=str(row.child_id),
            stage=row.plan_index + 1,
            stages_total=len(row.plan_topics or []) or 1,
            questions_asked=row.questions_asked,
            questions_per_stage=stage.QUESTIONS_PER_STAGE,
            topic_id=row.topic_id,
            topic_title=_topic_title(row.topic_id),
            speech="",
            question=row.pending_question,
            strategy=(row.strategies_spent or [""])[-1],
            source="template",
            retrieval=rag.backend(),
            step=step.name,
            expects=step.expects,
            step_index=step.index,
            steps_total=len(steps),
            attempt=step.tries + 1,
            is_hint=step.is_hint,
            is_reveal=step.is_reveal,
            trace_target=_trace_target(row.topic_id) if step.name == lesson.DRAW else "",
            options=list(row.pending_options or []),
        )


__all__ = ["DAY_DONE_SPEECH", "TeacherTurn", "answer", "ask", "open_session", "read_session"]
