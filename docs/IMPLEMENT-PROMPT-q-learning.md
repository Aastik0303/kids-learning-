# Implementation Prompt — Q-learning policy for the repair ladder

Paste this whole file as one instruction to a coding session with
`D:\testcase\backend` open. It implements real Q-learning on top of the
existing S1–S9 repair ladder in `guide_agent_service.py`, backed by
Postgres, updated in real time (not a nightly batch).

**Hard prerequisite:** `docs/FIX-PROMPT-guide-agent-repair-ladder.md`,
Task 1, must be applied first. Right now `_validate_model_response`
discards every repair turn's `teaching_strategy` and overwrites it with
`None` before the response leaves the function. If Q-learning is wired in
before that fix, it will faithfully log `action=None` on every turn and
learn nothing. Do Task 1 of that prompt, confirm `response.teaching_strategy`
is non-`None` on a real repair turn, then start here.

**Design decision, stated up front:** you previously said the LLM keeps the
teaching decision, not an algorithm ("mai agents ko decision ke liye
rakhunga"). Q-learning here does not override that: it does not choose
`teaching_strategy` directly. It **narrows the legal menu** the model is
allowed to choose from, the same "constrain the menu, not the diner"
pattern already used for tools and UI targets elsewhere in this file — the
model still decides, Q-learning just gets to remove options that have
statistically stopped working for this situation, once it has seen enough
of them. Below `MIN_VISITS_TO_NARROW` visits for a state, nothing changes
from today's behavior — the full legal set is offered, same as now.

---

## Task 1 — Postgres schema

New table, same connection pattern as `learning_memory_service.py`
(`psycopg`, `get_settings().database_url`, in-memory fallback when no
database is configured — this codebase already accepts that tradeoff for
`_STRATEGY_LOG`, and the Q-table is the one piece here that must actually
survive a restart, since it is a shared model across every child, not
per-session data).

```sql
CREATE TABLE IF NOT EXISTS rl_policy (
    state_key   TEXT NOT NULL,
    action      TEXT NOT NULL,
    q_value     NUMERIC NOT NULL DEFAULT 0,
    visits      INTEGER NOT NULL DEFAULT 0,
    updated_at  TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (state_key, action)
);

CREATE INDEX IF NOT EXISTS rl_policy_state_idx ON rl_policy (state_key);
```

No second table for in-flight (state, action) pairs — see Task 4's note on
why that stays in-memory, same trust level as `_STRATEGY_LOG`.

---

## Task 2 — `app/services/policy/q_table.py` (new file)

```python
"""Tabular Q-learning over the repair-ladder strategies.

The Q-table is a shared, durable model across every child — it belongs in
Postgres, same reasoning as learning_memory_service.py. What's in-flight
inside one repair sequence (which state/action is waiting on an outcome) is
per-session and disposable, so it stays in memory, same trust level as
guide_agent_service._STRATEGY_LOG.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock

from app.config import get_settings

logger = logging.getLogger(__name__)

GAMMA = 0.9
MIN_VISITS_TO_NARROW = 30   # below this, offer the full legal set unchanged
NARROW_TO_TOP_K = 3
EPSILON = 0.10               # only spent when narrowing is already active

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS rl_policy (
    state_key TEXT NOT NULL,
    action TEXT NOT NULL,
    q_value NUMERIC NOT NULL DEFAULT 0,
    visits INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (state_key, action)
)
"""
CREATE_INDEX_SQL = "CREATE INDEX IF NOT EXISTS rl_policy_state_idx ON rl_policy (state_key)"

UPSERT_SQL = """
INSERT INTO rl_policy (state_key, action, q_value, visits, updated_at)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (state_key, action) DO UPDATE SET
    q_value = EXCLUDED.q_value, visits = EXCLUDED.visits, updated_at = EXCLUDED.updated_at
"""
SELECT_STATE_SQL = "SELECT action, q_value, visits FROM rl_policy WHERE state_key = %s"

# In-memory fallback + in-flight (state, action) tracker. Same shortcut as
# _STRATEGY_LOG: prototype-only, lost on restart, replace before production.
_MEMORY_TABLE: dict[tuple[str, str], tuple[float, int]] = {}
_PENDING: dict[tuple[str, str], tuple[str, str]] = {}  # (session_id, activity_id) -> (state_key, action)
_LOCK = Lock()
_schema_ready = False


def _postgres_enabled() -> bool:
    return bool(get_settings().database_url.strip())


def _connect():
    import psycopg
    settings = get_settings()
    return psycopg.connect(settings.database_url, connect_timeout=settings.database_connect_timeout)


def _ensure_schema() -> bool:
    global _schema_ready
    if not _postgres_enabled():
        return False
    if _schema_ready:
        return True
    with _LOCK:
        if _schema_ready:
            return True
        try:
            with _connect() as conn:
                conn.execute(CREATE_TABLE_SQL)
                conn.execute(CREATE_INDEX_SQL)
            _schema_ready = True
        except Exception:
            logger.exception("Could not initialize rl_policy schema")
            return False
    return True


@dataclass(frozen=True)
class StateContext:
    """Everything the state key is built from. Keep this small and stable —
    every new field multiplies the state space and slows convergence."""
    answer_kind: str        # "choice" | "spoken" | "presentational" — from activity_evaluators.answer_kind
    attempt_rung: int       # 1, 2, 3, or 4 (4 = park, capped)
    last_strategy: str      # most recent entry in strategies_used, or "NONE"
    early_mode: bool


def state_key(ctx: StateContext) -> str:
    return f"{ctx.answer_kind}|{min(ctx.attempt_rung, 4)}|{ctx.last_strategy}|{'early' if ctx.early_mode else 'std'}"


def _row_values(key: str) -> dict[str, tuple[float, int]]:
    if _ensure_schema():
        try:
            with _connect() as conn:
                rows = conn.execute(SELECT_STATE_SQL, (key,)).fetchall()
            return {action: (float(q), int(v)) for action, q, v in rows}
        except Exception:
            logger.exception("Could not read rl_policy for %s", key)
    return {a: qv for (k, a), qv in _MEMORY_TABLE.items() if k == key}


def _write(key: str, action: str, q_value: float, visits: int) -> None:
    now = datetime.now(timezone.utc)
    _MEMORY_TABLE[(key, action)] = (q_value, visits)
    if _ensure_schema():
        try:
            with _connect() as conn:
                conn.execute(UPSERT_SQL, (key, action, q_value, visits, now))
        except Exception:
            logger.exception("Could not write rl_policy for %s/%s", key, action)


def narrow_legal_actions(key: str, legal: list[str]) -> list[str]:
    """The menu the model is offered. Unchanged until a state has enough
    data; then trimmed to its top-scoring legal actions."""
    values = _row_values(key)
    total_visits = sum(v for _q, v in values.values())
    if total_visits < MIN_VISITS_TO_NARROW:
        return legal
    ranked = sorted(legal, key=lambda a: values.get(a, (0.0, 0))[0], reverse=True)
    return ranked[:NARROW_TO_TOP_K] or legal


def record_pending(session_id: str | None, activity_id: str | None, key: str, action: str) -> None:
    if not session_id or not activity_id or not action:
        return
    _PENDING[(session_id, activity_id)] = (key, action)


def pop_pending(session_id: str | None, activity_id: str | None) -> tuple[str, str] | None:
    if not session_id or not activity_id:
        return None
    return _PENDING.pop((session_id, activity_id), None)


def update(key: str, action: str, reward: float, next_key: str | None, next_legal: list[str]) -> None:
    """One Q-learning step. alpha decays with visit count (Robbins-Monro),
    so no learning-rate tuning is needed and early observations move the
    value fast while later ones refine it."""
    values = _row_values(key)
    q, visits = values.get(action, (0.0, 0))
    next_max = 0.0
    if next_key:
        next_values = _row_values(next_key)
        next_max = max((next_values.get(a, (0.0, 0))[0] for a in next_legal), default=0.0)
    alpha = 1.0 / (1 + visits)
    new_q = q + alpha * (reward + GAMMA * next_max - q)
    _write(key, action, new_q, visits + 1)
```

**Note on warm start:** this deliberately does *not* seed `rl_policy` with
any rows at deploy time. `narrow_legal_actions` returns the untouched legal
set until `MIN_VISITS_TO_NARROW` is reached, which is the warm-start
guarantee — day-1 behavior equals today's ladder, because nothing has
enough visits to narrow anything yet.

---

## Task 3 — Reward function (new file or bottom of `q_table.py`)

```python
def reward_for_outcome(*, was_correct: bool, attempts_used: int, was_parked: bool, was_vetoed: bool) -> float:
    if was_vetoed:
        return -1.0
    if was_parked:
        return -0.6
    if was_correct:
        return {1: 1.0, 2: 0.6}.get(attempts_used, 0.3)
    return -0.15  # another wrong attempt followed — the strategy did not resolve it
```

`was_vetoed` means the envelope (once `FIX-PROMPT` Task 1's narrower safety
check exists) rejected the model's message outright — treat that as the
strategy having failed at the earliest possible point, worse than a wrong
answer, because it never even reached the child. The +0.8 next-day-retention
bonus from the original design is deliberately left out of this real-time
path — see Task 5.

---

## Task 4 — Wire into `guide_agent_service.py`

**4a. Close the previous turn's loop, at the very top of `guide()`:**

```python
def guide(payload: GuideRequest) -> GuideResponse:
    validate_guide_request(payload)
    _resolve_pending_rl_outcome(payload)
    ...
```

```python
def _resolve_pending_rl_outcome(payload: GuideRequest) -> None:
    """If the previous repair turn on this exact question is waiting on an
    outcome, this event is that outcome. Update the Q-table synchronously,
    right here — this is the real-time part, not a queued job."""
    if not payload.question:
        return
    pending = q_table.pop_pending(payload.session_id, payload.question.activity_id)
    if not pending:
        return
    prev_key, prev_action = pending

    if payload.event in {"PRACTICE_ANSWER_CORRECT", "TOPIC_ANSWER_CORRECT"}:
        reward = reward_for_outcome(was_correct=True, attempts_used=payload.question.attempt or 1,
                                     was_parked=False, was_vetoed=False)
        q_table.update(prev_key, prev_action, reward, next_key=None, next_legal=[])
    elif payload.event in REPAIR_EVENTS:
        ctx = _state_context(payload)
        next_key = q_table.state_key(ctx)
        was_parked = _ladder_attempt(payload) >= 4
        reward = reward_for_outcome(was_correct=False, attempts_used=0,
                                     was_parked=was_parked, was_vetoed=False)
        q_table.update(prev_key, prev_action, reward,
                        next_key=next_key, next_legal=list(_allowed_teaching_strategies(payload)))
    # Any other event on the same activity_id (child navigated away) — the
    # pending pair is simply dropped by pop_pending above. No reward, no
    # penalty: an abandoned question is not evidence the strategy failed.
```

**4b. Build the state and narrow the menu inside `_repair_instruction`:**

```python
def _state_context(payload: GuideRequest) -> "q_table.StateContext":
    spent = _strategies_used(payload)
    answer_type = (payload.question.answer_type or "") if payload.question else ""
    return q_table.StateContext(
        answer_kind=activity_evaluators.answer_kind(answer_type) if answer_type else "choice",
        attempt_rung=_ladder_attempt(payload),
        last_strategy=spent[-1] if spent else "NONE",
        early_mode=payload.experience_mode == "early",
    )
```

In `_repair_instruction`, where `allowed = list(_allowed_teaching_strategies(payload))`
is built, replace it with:

```python
    ctx = _state_context(payload)
    key = q_table.state_key(ctx)
    allowed = q_table.narrow_legal_actions(key, list(_allowed_teaching_strategies(payload)))
```

**4c. Log the pending pair once the model's decision is known** — in
`_groq_guide`, right after `_record_strategy(payload, response.teaching_strategy)`:

```python
    _record_strategy(payload, response.teaching_strategy)
    if response.teaching_strategy and payload.question:
        q_table.record_pending(
            payload.session_id, payload.question.activity_id,
            q_table.state_key(_state_context(payload)), response.teaching_strategy,
        )
```

This only ever logs a real action once `FIX-PROMPT` Task 1 is applied —
before that, `response.teaching_strategy` is always `None` here and
`record_pending`'s guard clause (`if ... or not action: return`) makes this
a safe no-op, not a source of garbage data.

---

## Task 5 — What "real time" actually covers, stated plainly

Everything above updates synchronously, inside the request that observes
the outcome — the extra-attempt penalty, the success reward, the park
penalty, all happen the moment the next event for that question arrives, no
batch job, no queue.

**One reward component cannot be real-time and this file does not pretend
otherwise:** the original design's +0.8 next-day-retention bonus needs a
second day to have passed before anyone knows if the child remembered.
There is no architecture that makes tomorrow's data arrive today. If you
want that signal too, it has to be a separate, small, once-a-day job —
query `topic_memories`/`history_service` for skills last taught by a
tracked (state, action) 20-30 hours ago, and top up `rl_policy` with the
retention bonus. Everything else in this prompt runs without it.

---

## Task 6 — Acceptance checks

1. With `DATABASE_URL` unset, run a repair turn end to end (mocked Groq
   response with a legal `teaching_strategy`) followed by a
   `PRACTICE_ANSWER_CORRECT` on the same `activity_id`/`session_id`. Assert
   `q_table._MEMORY_TABLE` gained an entry for that `(state_key, action)`
   with `visits == 1` and `q_value > 0`.
2. Same flow, but the second event is another
   `PRACTICE_ANSWER_INCORRECT` on the same question — assert the entry's
   `q_value` moved negative and a *new* pending pair was recorded for the
   next state.
3. Call `narrow_legal_actions` on a fresh state (`visits == 0`) — assert it
   returns the input list unchanged (warm start holds).
4. Manually write 40 rows to `rl_policy` for one `state_key` in a real
   Postgres instance, call `narrow_legal_actions` again — assert it returns
   at most 3 actions, and that they are the 3 highest `q_value` rows.
5. With `DATABASE_URL` set to a real instance, restart the process and
   confirm `_row_values` for a previously-written key returns the same
   values it held before restart — the in-memory fallback must not be the
   only thing carrying state across a restart when Postgres is configured.
