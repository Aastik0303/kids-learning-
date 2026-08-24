# AI Nursery Agent Notes

## Source of truth

- Follow `README.md` and, for the AI classroom, the `docs/` family:
  `AI-100-PERCENT-AUTOMATION.md` (what "100% automation" means and its phase
  plan), `AGENT-FLOW.md` (build order and the LangGraph verdict),
  `AI-ARCHITECTURE-DECISIONS.md` (why RLHF was rejected), and
  `TEACHING-GRAPH-SPEC.md` (nodes, edges, contract tests).

## The one rule that never moves

- **Do not use an LLM for deterministic correctness, scoring, stars, unlocking,
  or certificate eligibility.** The branch decision - advance, re-explain,
  simplify, drop to a prerequisite, switch modality, stop kindly - is on the
  same list: `app/conductor/branch.py` is a pure function and may not import
  `app.ai` or `app.services`. "100% AI" means zero manual decisions on the
  *child's* surface — no navigation, no menus, no "next" button — not that a
  model grades anything. The evaluator is pure Python and must not reach
  `app/agents/` or any model client through any import path.
- The same rule binds the learned policy. A reward defined on "the child
  answered correctly" trains a teacher that hands over the answer; that is why
  RLHF was rejected here, and a Q-learning reward built the same way fails
  identically. Rewards are paid by retention probes days later
  (`app/db/repositories/policy.py`) and by nothing else.

## Infrastructure — this project is past the prototype stage

- PostgreSQL is the durable truth. Schema lives in `app/db/models.py`, access in
  `app/db/repositories/`, migrations in `backend/alembic/`. Run them with
  `cd backend && alembic upgrade head`.
- `app/services/mock_storage.py` and `mock_auth.py` are gone. Auth is
  `app/services/auth_service.py` (PBKDF2, `parents` / `auth_sessions`), the
  child's progress ledger is `app/services/child_store.py`, and the attempt log
  is `app/services/history_service.py` writing `attempts`. Do not reintroduce a
  module-level dict as storage; the only ones left are the in-flight lesson and
  practice cursors, which are rebuilt by starting again.
- The class is conducted server-side. `app/conductor/` decides (state machine,
  Branch Decision Engine, frustration and idle watchers, scaffolding) and
  `app/services/conductor_service.py` holds the state, writes the truth and asks
  the guide for the words. One row in `lesson_states` is the live lesson, and
  `POST /conductor/{child_id}/open` plus `POST /conductor/sessions/{id}/input`
  drive the whole sitting. The client renders a `ConductorDirective` and reports
  what the child did; it decides nothing, including what silence means.
- **The day's plan is the day's work.** `plan_service.may_open()` is the gate:
  a topic opens if today's frozen plan holds it, or if the child has already
  finished it. Anything else is tomorrow's, including the level the lesson just
  unlocked - unlocking is what a lesson earns, and *when* it is played is the
  plan's to decide. A day holds one level per subject, the subjects rotate by
  day so none is starved, and with no plan at all the gate opens rather than
  locking a child out over infrastructure. Both `/learning/start` and the
  conductor enforce it; refusals are `NOT_TODAYS_PLAN` and are worded for a
  child.
- The Planner Agent is a LangGraph graph in `app/ai/planner/`, run on a timer by
  `app/services/planner_runner.py` and frozen into `daily_plans`. It may only
  reorder the candidates `plan_service` computed; an off-menu answer is dropped
  whole and the day stays `deterministic`.
- The teaching policy is wired: `app/services/teaching_policy_service.py`
  chooses a strategy for every teaching turn (with no model configured too),
  `app/services/retention_service.py` schedules and settles the probes that pay
  its reward, and `app/services/plan_service.py` freezes one plan per child per
  day. Anything reaching a language model goes through `app/ai/llm/`.
- Tests run on in-memory SQLite; the models use portable SQLAlchemy types so one
  migration describes both backends.

## Child-facing copy

- Keep it short, gentle, and non-technical.
- Narrate in English in every subject, the Hindi-language ones included: there,
  Hindi is the content being taught, quoted in Devanagari inside an English
  sentence.

## Still off the table

- Payments, leaderboards, and real personal data beyond a parent's email and a
  child's first name and birth month.
- Automated consent. DPDP and COPPA both require an explicit act by a person,
  so `parents.consent_granted_at` is written by the parent surface only.
