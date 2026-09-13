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

* **The class opens with the check-ins the schedule says are due.** A concept
  taught two days ago is asked about again - a *different* question about the
  same thing - before today's first stage. It is a retention test, not a lesson:
  no strategy is spent, no episode is written, nothing is added to the attempt
  log, no star moves and the day's plan does not advance. What it does move is
  the Q-value of the teaching turn that taught the concept two days ago, which
  is the only way this policy is ever paid. See `app/policy/retention.py` for
  when, `app/services/retention_test_service.py` for the wiring, and
  `app/policy/reward.py` for what it pays.

The one rule still holds, and holds harder now that this writes a child's
progress: **no model decides correctness, stars or unlocking.** `stage.judge`
marks the answer in plain Python from the authored key, and
`award_topic_completion` decides the level from a score computed out of this
stage's own tally. The agent asks and explains; it never marks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from app.conductor import echo as echo_engine
from app.db.models import PlaygroundSession, PlaygroundTurn
from app.db.session import session_scope
from app.playground import agent, examples, lesson, poem, questions, rag, retention, stage, visuals
from app.policy import leak as policy_leak
from app.services import (
    child_service,
    child_store,
    curriculum_service,
    learning_service,
    plan_service,
    retention_service,
    retention_test_service,
    teaching_policy_service,
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
    # The two or three everyday things the author named beside this level, as
    # asset tokens the client draws. This is what the child *reads* instead of
    # the explanation: the words are spoken, the example is looked at. Never the
    # answer to the question on the screen - `examples.for_turn` drops those.
    example_items: list[str] = field(default_factory=list)
    # The everyday words the class may **never** put on the screen while it
    # talks. An explanation reaches for a contrast - "three corners, not round
    # like a ball" - and the client shows the example it is saying at the moment
    # it says it, so a ball appeared beside "Tap the triangle!": the circle's
    # picture on the triangle's card. The client has a table of pictures and no
    # idea whose picture each one is, so the server says. Hand-written and
    # closed - the other members of this concept's own family.
    not_examples: list[str] = field(default_factory=list)
    # This stage is a poem rather than a level: every fifth day one subject's
    # level steps aside for one. Nothing about it is asked, marked, scored or
    # paid - the client only needs it to say "next bit" instead of "got it".
    is_poem: bool = False
    # --- the answer just given, when there was one -------------------------
    feedback: str = ""
    is_correct: bool | None = None
    advanced: bool = False
    # --- the check-in on something taught two days ago ---------------------
    # A retention test, not a lesson: nothing about answering it is marked into
    # the stage, written to the attempt log, or allowed near a star. It is asked
    # before the day's first stage, the schedule decided when, and what it pays
    # goes to the teaching turn that earned it two days ago.
    is_retention_test: bool = False
    retention_test_id: str = ""
    retention_remaining: int = 0
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


def _skill_id(row: PlaygroundSession) -> str:
    """The concept this stage teaches, named the way everything else names it.

    "<subject>:<topic>" is the id `history_service` writes, the mastery roll-up
    groups on, and the retention probe is scheduled against - so a strategy
    spent here and the probe that eventually pays for it line up on one skill.
    One function rather than the same f-string in three places, because when
    those three drifted the policy learned from a join that meant nothing.
    """
    if not row.topic_id:
        return ""
    return f"{row.subject_id}:{row.topic_id}" if row.subject_id else row.topic_id


def _experience_mode(class_id: str) -> str:
    """`early` for Play Group and Nursery, `standard` for the rest.

    Read from the manifest, never from an age test here - the action space the
    policy may choose from depends on it, and two answers to "is this child
    early?" is how a two-year-old gets offered a story to reason about.
    """
    if not class_id:
        return "standard"
    try:
        return curriculum_service.experience_mode_for_class(class_id).mode_id
    except Exception:  # pragma: no cover - a class the manifest no longer has
        return "standard"


def _policy_rung(step: lesson.Step) -> int:
    """The repair rung this turn stands on, in the ladder's own numbering.

    The two do not count the same way and cannot be used interchangeably. The
    ladder's rung 1 is a clean second try that teaches nothing and spends no
    strategy; the AI Teacher has no such turn - its second turn is the hint,
    which is a deeper telling and very much spends one. So try 0 is rung 0 and
    try 1 is rung 2, which are the two rungs `actions.LADDER_PRIOR` actually
    describes.
    """
    return 0 if step.tries <= 0 else 2


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
    # A poem first, because a poem's id is deliberately not in the manifest -
    # that is what keeps every rule which reads the manifest from paying it a
    # star - so the lookup below can only ever fail for one, and what a child
    # would be told they were starting is `poem_moon`.
    titled = poem.title_of(topic_id)
    if titled:
        return titled
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


def _answer_of(asked: questions.Authored | None) -> str:
    """The author's answer to the question a turn is built around, or nothing.

    Only ever used to decide what a card is *about* - never shown, never sent to
    a model, never marked against. `stage.judge` reads `pending_answer` and
    nothing here.
    """
    return (asked.answer or "").strip() if asked is not None else ""


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
    # Every fifth day one of the day's stages is a poem instead of a level, and
    # a poem is said rather than taught: no retrieval, no strategy, no model, no
    # question. Branching here rather than at each caller means every path that
    # reaches for the next turn - opening the class, resuming it, finishing the
    # stage before - gets the poem without having to know about it.
    if poem.is_poem(row.topic_id):
        return _poem_turn(row, feedback=feedback)

    steps = _steps_for(row.topic_id, row.subject_id)
    step = lesson.current(steps, row.step_index, row.step_tries)
    title = _topic_title(row.topic_id)
    mode = _mode_for(step)
    class_id = _class_of(row.topic_id)
    experience = _experience_mode(class_id)
    skill_id = _skill_id(row)
    activity_id = f"teacher_{step.name}"

    # Which of the nine ways to teach it, decided by the learned policy rather
    # than by the ladder alone. The flow is the one `app/policy/` documents -
    # candidates, then the eligibility filter, then epsilon-greedy - and it
    # degrades to the ladder on its own when the database cannot answer, so a
    # child never waits on this. Two of the filter's flags are settled here and
    # not guessed: this class cannot drop to a prerequisite mid-stage, because a
    # stage *is* one item of the day's plan, and whether there is anything to
    # look at is whatever `visuals` can draw for the concept.
    decision = teaching_policy_service.decide(
        child_id=str(row.child_id),
        skill_id=skill_id,
        activity_id=activity_id,
        experience_mode=experience,
        rung=_policy_rung(step),
        spent=list(row.strategies_spent or []),
        has_prerequisite=False,
        has_visual=visuals.from_concept(title).is_shown,
    )

    # The syllabus's own question for this rotation. Held in a name rather than
    # passed inline because the episode records which authored question the turn
    # taught around: the retention test scheduled off it two days from now reads
    # that to ask a *different* one about the same concept.
    asked = questions.pick(row.topic_id, nth=row.questions_asked)

    taught = agent.teach(
        subject=row.subject_id,
        topic=title,
        topic_id=row.topic_id,
        class_id=class_id,
        age_band=_age_band(class_id),
        step=step.name,
        spent=list(row.strategies_spent or []),
        experience_mode=experience,
        strategy=decision.strategy,
        mode=mode,
        # The syllabus's own question for this turn, when the step is one the
        # author wrote questions for. Walked by how many of the stage's five
        # have been settled, so five questions are five different ones rather
        # than the same one five times.
        asked=asked,
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

    # What this turn did with the answer key it was never shown. A reveal is
    # exempt: saying the answer is the whole job of that turn, and marking it as
    # a leak would teach the table to avoid the one turn that exists so nobody
    # is left stuck. Nothing is blocked here - the verdict is recorded, and an
    # outright leak costs the strategy more reward than a passed probe pays.
    verdict = (
        policy_leak.Verdict(policy_leak.NONE)
        if mode == agent.REVEAL
        else policy_leak.classify(
            f"{explanation} {question}".strip(),
            correct_answer=taught.expected_answer if mode == agent.ASK else row.pending_answer,
            prompt=question if mode == agent.ASK else (row.pending_question or ""),
            options=tuple(taught.options or ()),
            accepted=tuple(taught.accept or ()) if mode == agent.ASK else tuple(row.pending_accept or ()),
            # An ASK turn explains the thing and then asks about it, so naming
            # it is the lesson. A hint is help with a question already on the
            # screen, and naming the answer there is handing it over.
            teaching=mode == agent.ASK,
        )
    )
    if verdict.is_leak:
        logger.warning(
            "Answer leak on %s by %s: %s", activity_id, taught.strategy, verdict.evidence
        )

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

    # The episode, with no reward on it. What pays it is a retention probe days
    # from now and nothing else - `_record_attempt` schedules and settles those.
    teaching_policy_service.commit(
        child_id=str(row.child_id),
        skill_id=skill_id,
        activity_id=activity_id,
        decision=decision,
        strategy=taught.strategy,
        experience_mode=experience,
        rung=_policy_rung(step),
        author=taught.source,
        answer_leak_vetoed=verdict.is_leak,
        leak_kind=verdict.kind,
        # Which authored question this turn taught around. The retention test
        # scheduled off this episode asks a different one about the same
        # concept, and tells transfer from recall by comparing the two.
        question_ref=asked.activity_id if asked is not None else "",
        # This turn's own unit of work. Opening a second one here costs a full
        # SQLite busy timeout per turn against the transaction we are inside.
        session=session,
    )

    # What is drawn on the board. The answer the server is holding decides it -
    # the level's title, the retrieved notes and the model's own token all only
    # get a say when the answer names nothing the app can draw.
    #
    # The explaining step holds no answer yet and is still about something: it
    # is the turn that leads into `asked`, and its notes were narrowed to that
    # concept, so the author's answer to the question *coming next* decides the
    # picture there rather than whichever concept the notes led with.
    about = row.pending_answer or taught.expected_answer or _answer_of(asked)
    shown = visuals.for_card(about, taught.visual)

    # What the child looks at in place of the explanation they cannot read. The
    # answer the server is now holding is passed in so an example can never be
    # the thing about to be asked for.
    example_items = examples.for_turn(
        row.topic_id,
        visual=taught.visual,
        answer=about,
        options=list(row.pending_options or taught.options or []),
    )
    # ...and the everyday words that belong to one of this concept's siblings,
    # which the class may say in passing and must never illustrate.
    banned = examples.not_examples(shown)

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
        # The picture is the concept the question asks about, decided here and
        # not only inside the teacher: this is the one place every turn passes
        # through, so a card cannot leave the server drawing a square under
        # "Tap the circle!" however it was built.
        visual_kind=shown.kind,
        visual_value=shown.value,
        example_items=example_items,
        not_examples=banned,
        feedback=feedback,
        is_correct=bits.get("is_correct"),
        advanced=bool(bits.get("advanced")),
        topic_completed=bool(bits.get("topic_completed")),
        next_topic_unlocked=bool(bits.get("next_topic_unlocked")),
        stars_earned=int(bits.get("stars_earned") or 0),
    )


# --------------------------------------------------------------------------
# The check-in: a concept taught two days ago, asked before today's first stage
# --------------------------------------------------------------------------
#
# A retention test is part of the schedule and it is not part of the lesson.
# Everything about the boundary is enforced in this section:
#
# * **the scheduler decides when.** The queue is whatever
#   `retention_test_service.due_for_child` returns - `due_at <= now`, oldest
#   first - and nothing here reads a Q-value to pick or order one.
# * **it is never a teaching turn.** No strategy is chosen, no episode is
#   written, `strategies_spent` is untouched and `teaching_policy_service` is
#   not called. The reward this test pays belongs to the teaching turn from two
#   days ago; crediting it to the asking would be crediting the exam.
# * **it cannot touch the curriculum.** No `attempts` row, no stage tally, no
#   `questions_asked`, no plan cursor, no `award_topic_completion`. A child who
#   gets a check-in wrong has lost nothing at all, and one who gets it right has
#   won nothing but the class's warmth.
# * **it is judged by `stage.judge`**, in pure Python, against the authored key
#   the syllabus already holds - the same function that marks every other
#   answer.

# What is said back, and neither of them is a mark. A check-in the child does
# not remember is answered warmly and let go of: it has told the policy what it
# needed to know, and telling a four-year-old off for forgetting a letter from
# Monday would be teaching them to dread Wednesday.
RETENTION_PASS_FEEDBACK = "You remembered! That is wonderful."


def _retention_miss_feedback(answer: str) -> str:
    text = (answer or "").strip()
    return f"That one was {text}. It is coming back to us!" if text else "That one was tricky - well tried!"


def _load_retention_queue(row: PlaygroundSession, session) -> None:
    """Fill this sitting's check-in queue, once, as the class opens.

    Only on the call that starts the sitting. A reload must not fetch a new
    queue - a child who looks away and back has to find the same check-in in
    front of them, and re-reading would also re-ask one they had just answered
    if it settled between the two calls.
    """
    due = retention_test_service.due_for_child(str(row.child_id), session=session)
    row.retention_queue = [test.test_id for test in due]
    row.retention_index = 0


def _current_retention(row: PlaygroundSession, session):
    """The check-in this sitting is on, or None when the round is through.

    Steps over anything that can no longer be asked - settled from another
    device, or a concept whose authored questions have gone - rather than
    stalling the sitting on it.
    """
    queue = list(row.retention_queue or [])
    while row.retention_index < len(queue):
        test = retention_test_service.load(queue[row.retention_index], session=session)
        if test is not None:
            return test
        row.retention_index += 1
    return None


def _retention_remaining(row: PlaygroundSession) -> int:
    return max(0, len(list(row.retention_queue or [])) - row.retention_index - 1)


def _poem_turn(row: PlaygroundSession, *, feedback: str = "") -> TeacherTurn:
    """One verse of today's poem, as the client renders it.

    A poem stage is the plainest turn in the app: a line on the card, a verse
    said out loud, a picture beside it when the verse names one. Nothing here
    asks a question, so nothing here can be answered wrongly - `expects` is
    always "ready" and the class carries on by itself when the narration is
    done.

    What it deliberately does not touch, and each of these is a rule from
    somewhere else keeping itself: no strategy is chosen and no episode is
    committed (`teaching_policy_service`), because a poem is not a teaching turn
    and there is nothing a retention probe could ask about it two days from now;
    no attempt is written; and the stage tally stays at zero, which is what
    makes `_award_level` return nothing even before it notices the manifest has
    no such topic.
    """
    said = poem.get(row.topic_id)
    parts = said.parts if said is not None else ()
    index = min(max(row.questions_asked, 0), max(len(parts) - 1, 0))
    part = parts[index] if parts else None
    drawn = part.visual if part is not None else visuals.Visual()

    return TeacherTurn(
        session_id=row.session_id,
        child_id=str(row.child_id),
        stage=row.plan_index + 1,
        stages_total=len(row.plan_topics or []) or 1,
        # The dots on the card follow the poem's own length rather than the
        # five a level has, so a child can see how much of it is left.
        questions_asked=row.questions_asked,
        questions_per_stage=len(parts) or 1,
        topic_id=row.topic_id,
        topic_title=said.title if said is not None else _topic_title(row.topic_id),
        speech=part.speech if part is not None else "",
        # The few words printed large. A poem is the one place in this class
        # where the words on the card are worth having: they are short, they are
        # the same every time it comes round, and a grown-up reads them along.
        question=part.line if part is not None else "",
        # No strategy was spent, so there is none to name - the same honest
        # empty string a check-in carries, and for the same reason.
        strategy="",
        source="poem",
        retrieval="",
        step="poem",
        expects="ready",
        step_index=index,
        steps_total=len(parts) or 1,
        attempt=1,
        visual_kind=drawn.kind,
        visual_value=drawn.value,
        is_poem=True,
        feedback=feedback,
    )


def _answer_poem(row: PlaygroundSession, session) -> TeacherTurn:
    """The child has heard this verse. On to the next, or on to the next stage.

    A poem's parts are counted on `questions_asked` - the same field a level's
    five questions use - so the progress dots, the resume and the plan cursor
    all work without knowing what a poem is. Nothing is marked on the way
    through, and `_finish_stage` is what ticks the item off the day: a poem is a
    stage of the schedule, so a day with one in it has to be able to finish.
    """
    said = poem.get(row.topic_id)
    parts = said.parts if said is not None else ()
    row.questions_asked += 1
    row.updated_at = _now()

    if row.questions_asked < len(parts):
        turn = _poem_turn(row)
        _log(row, turn, session)
        return turn

    award, day_over = _finish_stage(row)
    bits = _stage_bits(award)
    closing = "That was our poem. Well said!"
    if day_over:
        turn = _day_done_turn(row, feedback=closing, bits=bits)
        _log(row, turn, session)
        return turn
    turn = _teach_step(row, session, feedback=closing, verdict_bits={**bits, "advanced": True})
    _log(row, turn, session)
    return turn


def _retention_turn(
    row: PlaygroundSession, test, *, feedback: str = "", is_correct: bool | None = None
) -> TeacherTurn:
    """The check-in as the client renders it.

    The topic shown is the *tested* concept, not the one today's plan is on, and
    it is taken from the test rather than written onto the row - a check-in must
    not move the sitting's own cursor by so much as a title.
    """
    title = _topic_title(test.topic_id)
    concept = visuals.from_concept(title)
    return TeacherTurn(
        session_id=row.session_id,
        child_id=str(row.child_id),
        # Where the day is, unchanged. A check-in is not a stage and does not
        # consume one of the stage's five questions.
        stage=row.plan_index + 1,
        stages_total=len(row.plan_topics or []) or 1,
        questions_asked=row.questions_asked,
        questions_per_stage=stage.QUESTIONS_PER_STAGE,
        topic_id=test.topic_id,
        topic_title=title,
        speech=retention.speech(test.question),
        question=test.question,
        # No strategy was spent on this turn, so there is none to name. The
        # empty string is the honest answer and it is what stops a check-in
        # being counted as a teaching episode by anything reading the log.
        strategy="",
        source="deterministic",
        retrieval=rag.backend(),
        step="retention",
        expects=test.expects,
        step_index=0,
        steps_total=1,
        attempt=1,
        options=list(test.options),
        visual_kind=concept.kind if concept.is_shown else "",
        visual_value=concept.value if concept.is_shown else "",
        example_items=examples.for_turn(
            test.topic_id, visual=concept, answer=test.answer, options=list(test.options)
        ),
        feedback=feedback,
        is_correct=is_correct,
        is_retention_test=True,
        retention_test_id=test.test_id,
        retention_remaining=_retention_remaining(row),
    )


def _answer_retention(row: PlaygroundSession, session, test, said: str) -> TeacherTurn:
    """Mark the check-in, pay the teaching turn that earned it, and move on.

    The order is the architecture, and each step belongs to somebody else:
    `stage.judge` decides right or wrong, `retention_test_service.settle` prices
    it through `app/policy/reward.py` and pays the **original teaching
    episode's** (state, action) through `policy.pay_episode`, and only then does
    the class carry on. Nothing in this function may reach a level, a star or
    the plan.
    """
    verdict = stage.judge(
        said=said, expected=test.answer, accept=list(test.accept), offered=list(test.options)
    )

    # On its own session, deliberately: settling writes `policy_episodes` and
    # `policy_q_values`, which have nothing to do with this sitting's row, and on
    # SQLite a second writer inside the turn's open transaction waits out the
    # whole busy timeout.
    outcome = retention_test_service.settle(
        test.test_id, passed=verdict.is_correct, asked_question_ref=test.question_ref
    )
    logger.info(
        "Retention test %s for %s: %s (reward %s to episode %s)",
        test.test_id,
        test.concept_id,
        outcome.get("result"),
        outcome.get("reward"),
        outcome.get("episode_id"),
    )

    row.retention_index += 1
    row.updated_at = _now()
    feedback = (
        RETENTION_PASS_FEEDBACK
        if verdict.is_correct
        else _retention_miss_feedback(test.answer)
    )

    following = _current_retention(row, session)
    if following is not None:
        return _retention_turn(row, following, feedback=feedback, is_correct=verdict.is_correct)

    # The round is through: today's class starts. The check-in's own verdict
    # rides along on the first teaching turn so the child hears it.
    turn = _teach_step(
        row, session, feedback=feedback, verdict_bits={"is_correct": verdict.is_correct}
    )
    _log(row, turn, session)
    return turn


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
    opening = (
        f"Hello! I am so glad you came to class today. "
        f"We have {lessons} to do together, and we are starting with {topic_title}. "
    )
    # The promise the three turns keep - helped, then answered - is about a
    # question, and a poem has none. Opening on one is rare (the planner puts
    # the poem last), but a sitting that starts there must not promise five
    # little questions and then say a rhyme.
    if poem.is_poem(row.topic_id):
        return f"{opening}That one is a poem, so there is nothing to answer - we just say it together."
    return (
        f"{opening}"
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

    # The stage has been taught through, so this item of today's plan is
    # finished with - whatever the level scored, and even when there was nothing
    # to score. `award_topic_completion` ticks the item for every stage that
    # reaches it, pass or fail; this covers the stages that do not reach it at
    # all - a stage whose questions were all unmarked echoes, a topic the
    # manifest no longer has, a level marked unavailable. Without it those
    # stages leave the cursor where it was, `is_day_complete` never becomes
    # true, and the class reopens on the same level for ever.
    #
    # `mark_topic_done` is idempotent - it only writes an item whose
    # `completed_at` is still NULL - so calling it here as well costs nothing.
    if row.topic_id:
        plan_service.mark_topic_done(str(row.child_id), row.topic_id)

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
    # The schedule's clock, not this module's: the two must never disagree
    # about which day it is, or the class shuts on a plan that has moved on.
    today = plan_service.today()

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

        # The check-ins the schedule says are due, taken once as the sitting
        # starts. They are asked before today's first stage and they are not
        # part of it: no strategy, no episode, no attempt, no star.
        if opening:
            _load_retention_queue(row, session)
        check_in = _current_retention(row, session)
        if check_in is not None:
            turn = _retention_turn(row, check_in)
            if opening:
                turn.speech = f"{_class_intro(row, _topic_title(row.topic_id))} {turn.speech}".strip()
            return turn

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

        # A check-in is still in front of the child: this answer is that, and
        # nothing about it belongs to the lesson.
        check_in = _current_retention(row, session)
        if check_in is not None:
            return _answer_retention(row, session, check_in, said)

        # A poem verse. There was nothing to answer - "ready" is the child
        # having listened to it - so nothing is judged, nothing is written to
        # `attempts` and no probe is settled. The next verse, or the next stage.
        if poem.is_poem(row.topic_id):
            return _answer_poem(row, session)

        steps = _steps_for(row.topic_id, row.subject_id)
        step = lesson.current(steps, row.step_index, row.step_tries)

        # The turn that gave the answer away. There was nothing to answer and
        # nothing to mark - the child has heard it, and that question is finished
        # with. It counts as one of the five, and as one that did not land, so
        # the level's own score tells the truth about how the stage went.
        if step.is_reveal:
            _leave_question(row, steps, step)
            return _settle(
                row, session, correct=False, mark=None, feedback="", counts=step.is_marked
            )

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
        # took two goes is not the same history as one that took one. The echo
        # is the exception and `is_marked` is where that is decided - it is
        # taught and repaired, and it is never written down.
        if step.is_marked:
            _record_attempt(row, step, said=said, is_correct=verdict.is_correct)

        if verdict.is_correct:
            _leave_question(row, steps, step)
            return _settle(
                row,
                session,
                correct=True,
                mark=True,
                feedback=agent.praise(),
                counts=step.is_marked,
            )

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
    counts: bool = True,
) -> TeacherTurn:
    """One of the stage's five questions is finished with, and the lesson moves on.

    Called once per *question*, never once per answer: a question that took a
    hint and then the answer is still one question, and its three turns are three
    goes at the same one.

    `correct` is what goes into the stage's tally, which is what decides whether
    the level passed. `mark` is what the child is shown - `None` for the question
    that ended in being told the answer, because there is no tick or cross to put
    on a turn that was teaching rather than testing.

    `counts` is whether it goes into that tally at all. An echo is one of the
    stage's five things and none of the level's score: it still moves the lesson
    on, and a microphone that did not catch a small voice never costs a star.
    """
    progress = stage.settle(stage=row.plan_index + 1, questions_asked=row.questions_asked)
    row.questions_asked = progress.questions_asked
    if counts:
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
    """Put the answer in the one attempt log everything downstream reads, and
    move the retention probe that pays the learned policy.

    Two things happen here and they are different things. `record_attempt` is
    the history: mastery and the weak-skill list the planner reorders on both
    read `attempts`, so a teaching loop that graded an answer and kept the
    verdict to itself would leave both reading a partial history and never say
    so. `is_correct` arrives from `stage.judge` - plain Python over the authored
    key - and from nothing else.

    `retention_service.on_attempt` is the reward, and it is emphatically *not*
    read off this attempt. It settles a probe that came due - the child meeting
    this skill again days after it was taught - and schedules the next one. The
    strategies that taught it are paid by that probe and by nothing that happens
    inside today's turn, which is the whole reason RLHF was rejected here: a
    reward defined on "the child answered correctly" trains a teacher that hands
    the answer over.

    Without this call the AI Teacher wrote episodes that no probe ever paid, so
    the table never moved and `pending_episodes` grew for ever.
    """
    if not row.topic_id:
        return
    skill_id = _skill_id(row)
    record_attempt(
        child_id=str(row.child_id),
        session_id=row.session_id,
        activity_id=f"teacher_{step.name}",
        topic=row.topic_id,
        skill=skill_id,
        child_answer=said,
        is_correct=is_correct,
        # Which of this question's two tries it was, not how far into the stage
        # the child is: an attempt number is about one question.
        attempt_number=step.tries + 1,
    )
    # The step is the form the skill was asked in, so a probe posed on a
    # different step is evidence of transfer rather than of recall.
    #
    # On its own session, deliberately. A correct answer here can be the fifth
    # of the stage, and settling the stage calls `award_topic_completion`, which
    # opens a session of its own to write the plan cursor and the unlock. If the
    # probe were written into the turn's session first, that session would be
    # holding the write lock by the time the award tried for it, and on SQLite
    # the award simply fails. One writer at a time: the probe commits and lets
    # go, and the award has the lock when it needs it.
    retention_service.on_attempt(
        child_id=str(row.child_id),
        skill_id=skill_id,
        form_signature=step.name,
        is_correct=is_correct,
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

        # Asked in the middle of a check-in: answer it, and put the check-in
        # back exactly as it was. The round does not move because the child was
        # curious.
        check_in = _current_retention(row, session)
        if check_in is not None:
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
            turn = _retention_turn(row, check_in)
            turn.speech = answer_text
            turn.source = source
            return turn

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

        # A reload during the check-in round finds the same check-in, because
        # the queue is stored on the sitting and the question the test asks is
        # chosen deterministically out of the syllabus.
        check_in = _current_retention(row, session)
        if check_in is not None:
            return _retention_turn(row, check_in)

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
