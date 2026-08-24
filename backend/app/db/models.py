"""Durable truth for the Saksham IQ classroom.

Replaces `services/mock_storage.py`, whose dictionaries lost every learner the
moment the process restarted - which is why nothing could resume a lesson
tomorrow, and why no learned policy could exist at all: a policy needs a history
longer than one process lifetime.

Three groups of tables, and the boundary between them is the point:

1. **Truth** - `attempts`, `skill_mastery`, `lesson_states`. Written only by the
   deterministic evaluator. No agent, no policy and no LLM writes here.
2. **Plan** - `daily_plans`, `daily_plan_items`. Written by the Planner Agent
   through the envelope, or by the deterministic fallback. Frozen per day.
3. **Learning-to-teach** - `teaching_events`, `retention_probes`,
   `policy_episodes`, `policy_q_values`. The Q-learning loop. It reads truth and
   never writes it.

The reward lives in group 3 and is deliberately *not* computed from group 1's
`attempts.is_correct` at teach time. See `policy_episodes.reward`.
"""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UTCDateTime


def _pk() -> Mapped[UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid4)


def _now_column() -> Mapped[datetime]:
    return mapped_column(UTCDateTime(), server_default=func.now(), nullable=False)


# --------------------------------------------------------------------------
# Identity and consent
# --------------------------------------------------------------------------


class Parent(Base):
    """The account holder. A child never has an account of their own."""

    __tablename__ = "parents"

    id: Mapped[UUID] = _pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Consent is deliberately not automated - DPDP and COPPA both require an
    # explicit act by a person, so this column is written by a parent tapping a
    # control and by nothing else.
    consent_granted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = _now_column()

    children: Mapped[list["Child"]] = relationship(back_populates="parent", cascade="all, delete-orphan")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    parent_id: Mapped[UUID] = mapped_column(ForeignKey("parents.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = _now_column()
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class AuthThrottle(Base):
    """Failed sign-in attempts, counted per account.

    Without this, a login endpoint with a 600k-round password hash is still a
    password oracle: slow per guess, but unlimited. Eight failures inside the
    window locks the account for a short while, and one success clears it.

    Counted per email rather than per IP on purpose - an attacker distributing
    guesses across addresses is exactly the case an IP counter misses. The cost
    is that someone who knows a parent's email can lock them out for the lockout
    window; that is why the window is minutes and not hours.
    """

    __tablename__ = "auth_throttle"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_started_at: Mapped[datetime] = _now_column()
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PasswordReset(Base):
    """A single-use, expiring permission to set a new password.

    Only the SHA-256 of the token is stored. A database dump is then not a set
    of live reset links - which is the whole reason the raw token never touches
    a column.
    """

    __tablename__ = "password_resets"

    id: Mapped[UUID] = _pk()
    parent_id: Mapped[UUID] = mapped_column(ForeignKey("parents.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = _now_column()

    __table_args__ = (Index("ix_password_resets_parent", "parent_id", "created_at"),)


class Child(Base):
    """The learner. `class_id` and `experience_mode` come from the curriculum
    manifest, never from the client."""

    __tablename__ = "children"

    id: Mapped[UUID] = _pk()
    parent_id: Mapped[UUID] = mapped_column(ForeignKey("parents.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    birth_year: Mapped[int] = mapped_column(Integer, nullable=False)
    birth_month: Mapped[int] = mapped_column(Integer, nullable=False)
    class_id: Mapped[str] = mapped_column(String(32), nullable=False)
    experience_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="standard")
    preferred_language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    created_at: Mapped[datetime] = _now_column()

    parent: Mapped[Parent] = relationship(back_populates="children")

    __table_args__ = (
        CheckConstraint("birth_month BETWEEN 1 AND 12", name="birth_month_range"),
    )


class ChildProgress(Base):
    """The progress ledger the prototype kept in `mock_child_profiles`.

    Stars, rewards, weak skills and the per-subject unlock board are what the
    child surface reads to decide what is playable. They lived in a dictionary
    that lost every family on restart, which is the single reason a lesson could
    not be resumed tomorrow.

    It is one JSON document rather than five tables on purpose: this is a
    presentation ledger, re-derivable from the rows below it, and no decision the
    policy makes reads it. `attempts`, `skill_mastery` and `lesson_states` are
    still written alongside for every answer, and those - not this - are the
    truth the Q-learning loop and the mastery gate read.
    """

    __tablename__ = "child_progress"

    id: Mapped[UUID] = _pk()
    child_id: Mapped[UUID] = mapped_column(
        ForeignKey("children.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    state: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# --------------------------------------------------------------------------
# Group 1 - truth. The deterministic evaluator owns every row here.
# --------------------------------------------------------------------------


class Attempt(Base):
    """One answer to one activity, as graded by `activity_evaluators`.

    This is the truth node's output. If a row here can ever be written from a
    model's opinion, every number downstream - mastery, unlocking, certificates,
    and the Q-learning reward - is downstream of a hallucination.
    """

    __tablename__ = "attempts"

    id: Mapped[UUID] = _pk()
    child_id: Mapped[UUID] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"), nullable=False)
    topic_id: Mapped[str] = mapped_column(String(64), nullable=False)
    activity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Which try this was on this activity, server-counted. The client used to be
    # the only source of this, and it drives every rung of the repair ladder.
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    child_answer: Mapped[str | None] = mapped_column(Text)
    # S0-S4: how much support the child had. A correct answer at S4 is not the
    # same evidence as a correct answer at S0, and mastery must not treat them alike.
    scaffold_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    form_signature: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    answered_at: Mapped[datetime] = _now_column()

    __table_args__ = (
        Index("ix_attempts_child_skill_time", "child_id", "skill_id", "answered_at"),
        CheckConstraint("scaffold_level BETWEEN 0 AND 4", name="scaffold_range"),
    )


class SkillMastery(Base):
    """Rolled up from `attempts`, never from an agent's judgement.

    The four columns after `mastery` are the gate's other three clauses: a skill
    is not mastered because one lucky answer pushed an average over a line, but
    because it held up across attempts, across question forms, and across days.
    """

    __tablename__ = "skill_mastery"

    id: Mapped[UUID] = _pk()
    child_id: Mapped[UUID] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mastery: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distinct_forms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distinct_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # How many question forms the curriculum actually has for this skill. 48% of
    # skills are authored with a single activity, so a flat "two forms required"
    # gate locks those skills - and every topic depending on them - permanently
    # shut, however well the child answers. The gate asks for two forms where two
    # exist and one where only one does, and the variant bank raises this number
    # as forms are authored.
    forms_available: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    mastered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        UniqueConstraint("child_id", "skill_id", name="uq_skill_mastery_child_skill"),
        CheckConstraint("mastery BETWEEN 0 AND 1", name="mastery_range"),
    )


class LessonState(Base):
    """The live class, on the server. The Conductor's own row.

    This began as a resume point - cursor and status, so tomorrow did not
    restart. It is now the whole state of a sitting, because the alternative was
    a client that held the lesson: which phase it was in, how many times this
    question had gone wrong, what had already been explained. A client holding
    that is a client deciding it, and two tabs then disagree about a child.

    Everything the Branch Decision Engine reads comes from these columns, and
    `session_id` is unique so one sitting can never have two states.
    """

    __tablename__ = "lesson_states"

    id: Mapped[UUID] = _pk()
    child_id: Mapped[UUID] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"), nullable=False)
    topic_id: Mapped[str] = mapped_column(String(64), nullable=False)
    cursor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scaffold_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="in_progress")

    # --- the conductor's state ------------------------------------------
    session_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    phase: Mapped[str] = mapped_column(String(16), nullable=False, default="greet")
    current_skill_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # Which rung of the explanation ladder this skill has reached, and which
    # rungs are already spent - a sitting never gives the same explanation twice.
    ladder_rung: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    explanations_used: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    attempts_on_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    frustration_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    modality: Mapped[str] = mapped_column(String(8), nullable=False, default="tap")
    idle_rung: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # The activities this sitting drew, in order. Held here rather than redrawn,
    # so a refresh does not hand the child a different lesson.
    activity_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # The last few verdicts, for the frustration score. Truth lives in
    # `attempts`; this is a short window kept beside the state that reads it.
    recent_answers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    retry_burst_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unresolved_speech: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    speech_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idle_rungs_hit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # "doubt" or "prerequisite", with the exact place to come back to.
    paused_for: Mapped[str | None] = mapped_column(String(16))
    resume_payload: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = _now_column()
    last_input_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("child_id", "topic_id", name="uq_lesson_states_child_topic"),
        CheckConstraint("status IN ('in_progress', 'mastered', 'parked')", name="status_values"),
        Index("ix_lesson_states_child_updated", "child_id", "updated_at"),
    )


# --------------------------------------------------------------------------
# Group 2 - the plan. Written by the Planner Agent through the envelope.
# --------------------------------------------------------------------------


class DailyPlan(Base):
    """One plan per child per day, frozen on first read.

    The unique constraint is the freeze. Without it the planner produces a
    slightly different plan on every refresh and back-navigation, and a
    three-year-old never builds a routine out of it.
    """

    __tablename__ = "daily_plans"

    id: Mapped[UUID] = _pk()
    child_id: Mapped[UUID] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"), nullable=False)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 'planner_agent' or 'deterministic' - so a week of plans can be read back
    # and the agent's contribution separated from the fallback's.
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="deterministic")
    frozen_at: Mapped[datetime] = _now_column()

    items: Mapped[list["DailyPlanItem"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="DailyPlanItem.position"
    )

    __table_args__ = (
        UniqueConstraint("child_id", "plan_date", name="uq_daily_plans_child_date"),
        CheckConstraint("source IN ('planner_agent', 'deterministic')", name="source_values"),
    )


class DailyPlanItem(Base):
    __tablename__ = "daily_plan_items"

    id: Mapped[UUID] = _pk()
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("daily_plans.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    topic_id: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Why this item is here - 'new', 'revisit', 'prerequisite'. Read back to a
    # parent in the daily digest, so it is stored rather than re-derived.
    reason: Mapped[str] = mapped_column(String(24), nullable=False, default="new")

    plan: Mapped[DailyPlan] = relationship(back_populates="items")

    __table_args__ = (UniqueConstraint("plan_id", "position", name="uq_daily_plan_items_plan_position"),)


# --------------------------------------------------------------------------
# Group 3 - learning to teach. Reads truth, never writes it.
# --------------------------------------------------------------------------


class TeachingEvent(Base):
    """Which strategy the guide spent on which concept, durably.

    This replaces the in-process `_STRATEGY_LOG` dict in
    `guide_agent_service`, which could not survive a restart and so could not
    stop the guide repeating a strategy across two sittings.
    """

    __tablename__ = "teaching_events"

    id: Mapped[UUID] = _pk()
    child_id: Mapped[UUID] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    activity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy: Mapped[str] = mapped_column(String(20), nullable=False)
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 'agent' or 'deterministic' - the holdout comparison needs to know which
    # turns the agent actually authored.
    author: Mapped[str] = mapped_column(String(16), nullable=False, default="deterministic")
    created_at: Mapped[datetime] = _now_column()

    __table_args__ = (Index("ix_teaching_events_child_skill", "child_id", "skill_id", "created_at"),)


class RetentionProbe(Base):
    """A scheduled re-ask, and the only thing that can pay a policy reward.

    A probe is created when a skill is first answered correctly, and comes due
    days later. When it resolves it settles every episode waiting on it. This
    delay is the whole design: a strategy that reached the right answer by
    handing it over produces a correct attempt today and a failed probe on day
    two, so leaking the answer *lowers* the reward instead of maximising it.
    """

    __tablename__ = "retention_probes"

    id: Mapped[UUID] = _pk()
    child_id: Mapped[UUID] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    due_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    # The probe must not be the same question in the same clothes - a child can
    # recall a picture without holding the skill. A different signature is what
    # makes a pass evidence of transfer.
    form_signature: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    was_correct: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = _now_column()

    __table_args__ = (
        CheckConstraint("kind IN ('day2', 'day7')", name="kind_values"),
        Index("ix_retention_probes_due", "child_id", "due_at", "resolved_at"),
    )


class PolicyEpisode(Base):
    """One teaching decision, and the reward it eventually earned.

    `reward` is NULL on write and stays NULL until a retention probe resolves.
    Nothing may fill it in from `immediate_correct`: that column is recorded for
    diagnostics only, and using it as the reward is exactly the reward hack that
    made RLHF-on-child-correctness unusable here. A policy trained on it learns
    that telling the child the answer scores 1.0 every time.
    """

    __tablename__ = "policy_episodes"

    id: Mapped[UUID] = _pk()
    child_id: Mapped[UUID] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # The discretised state the policy saw: age band, mastery bucket, attempt
    # rung, strategies already spent. Stored as the key, not the raw features,
    # so a Q-value lookup is a string compare.
    state_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    next_state_key: Mapped[str | None] = mapped_column(String(128))
    immediate_correct: Mapped[bool | None] = mapped_column(Boolean)
    answer_leak_vetoed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reward: Mapped[float | None] = mapped_column(Float)
    reward_resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    retention_probe_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("retention_probes.id", ondelete="SET NULL")
    )
    taken_at: Mapped[datetime] = _now_column()

    __table_args__ = (
        Index("ix_policy_episodes_pending", "skill_id", "reward_resolved_at"),
    )


class PolicyQValue(Base):
    """The Q-table: one row per (state, action).

    Small and enumerable on purpose - the action space is the nine teaching
    strategies and the state is discretised, so the whole table can be read,
    diffed and reverted by a person. A neural policy would be a better
    approximator and a worse thing to hand a four-year-old.
    """

    __tablename__ = "policy_q_values"

    id: Mapped[UUID] = _pk()
    state_key: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    q_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("state_key", "action", name="uq_policy_q_values_state_action"),)


class TopicMemory(Base):
    """The guide's memory of a finished lesson: one row per child per topic.

    This is what lets the guide open with "you finished Shapes yesterday" rather
    than greeting a returning child as a stranger. It is a summary, not truth -
    the attempt log is truth - so it is safe to overwrite when a topic is
    replayed, which is what the unique constraint makes it do.

    The columns match the table the old raw-psycopg module created by hand, so
    an existing `topic_memories` in a running database is picked up as it is
    rather than migrated. `child_id` is text rather than a foreign key for that
    same reason: it predates children having UUIDs.
    """

    __tablename__ = "topic_memories"

    id: Mapped[UUID] = _pk()
    child_id: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[str] = mapped_column(Text, nullable=False)
    topic_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        UniqueConstraint("child_id", "topic_id", name="uq_topic_memories_child_topic"),
        Index("ix_topic_memories_child_completed", "child_id", "completed_at"),
        CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),
    )


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[UUID] = _pk()
    child_id: Mapped[UUID] = mapped_column(ForeignKey("children.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    issued_at: Mapped[datetime] = _now_column()

    __table_args__ = (UniqueConstraint("child_id", "subject_id", name="uq_certificates_child_subject"),)
