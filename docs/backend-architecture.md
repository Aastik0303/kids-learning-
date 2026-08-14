# Learn Kids — Production Backend Specification

**Repository:** `Aastik0303/learn_kids`
**Target:** Replace the prototype backend with a production backend that is *right-sized* — genuinely production-grade, deliberately not over-engineered.
**Sized for:** 50,000 registered children, ~6,000 DAU, ~800 peak concurrent sessions.
**Version:** 1.0 · 2026-08-13
**Status:** Ready for phased execution

---

## 0. Read This First

### 0.1 Priority order (governs every trade-off in this document)

```
correctness → child safety & privacy → data integrity → reliability
→ maintainability → scalability → AI quality → optimization
```

When two requirements conflict, the one further left wins. No exceptions. If an agent
is unsure whether to add a cache, an index, an abstraction, or a queue, it asks:
*does this serve something left of "optimization"?* If not, it does not get built.

### 0.2 The five rules that must never be broken

1. **The LLM is never a source of truth.** Not for correctness, scores, mastery,
   rewards, unlocks, ownership, auth, or any DB write. It is a teaching voice on top
   of state the backend already decided.
2. **The client is never trusted.** Score, attempt number, current step, unlock state,
   and child ownership are always re-derived server-side from the session row.
3. **No process-local mutable state.** Any dict, list, or counter at module scope that
   survives a request is a bug — three API replicas will disagree.
4. **Every child-scoped request is ownership-checked** against the authenticated parent,
   at the dependency layer, before the handler runs.
5. **Raw model text never reaches the client.** It passes schema validation, action
   allowlist validation, and safety validation, or it is replaced by a template.

### 0.3 The design thesis: production, not heavy

The previous spec asked for Celery, distributed locks, request coalescing, a five-layer
architecture, twenty tables, and a full observability stack. At 6k DAU that is
infrastructure you maintain instead of product you ship. This spec targets the same
correctness and safety guarantees with roughly 40% less machinery:

| Previous spec | This spec | Why |
|---|---|---|
| `domain/` + `services/` + `repositories/` (5 layers) | `services/` + `repositories/` (3 layers) | The domain layer was pure indirection. Services hold rules, repos hold SQL. |
| Celery + broker + result backend | ARQ (Redis-only, async-native) | ~1/10th the moving parts. Same job guarantees at this volume. |
| 20 tables | 17 tables (incl. a new `consent_records`) | Merged preferences→JSONB, practice→`sessions.mode`, session_steps→JSONB plan, rewards+events→one ledger. |
| 6-file AI package split | 4 files + `providers/` | `context.py`, `policy.py`, `orchestrator.py`, `validate.py`. |
| Server-side drawing validation | Frontend geometry, backend persists result | Tracing correctness is a 20-line frontend check. Shipping it server-side buys nothing. |
| Server-side STT day 1 | On-device STT, server abstraction with one impl | Add Whisper/Deepgram only if measured accuracy fails. |
| Feature flag service | Env config | 6k DAU does not need runtime flag infrastructure. |
| "Scalability" as a goal | 99.5% availability + stated p95 budgets | A number you can fail is worth more than an adjective. |

### 0.4 Deliberately NOT built (and when to revisit)

Every item below is a *decision*, not an omission. Do not let an agent add these
without hitting the trigger.

| Not building | Revisit when |
|---|---|
| Kubernetes | >10 API replicas, or you hire someone whose job is infra |
| Microservices | A single team can no longer merge without conflict |
| Read replicas / sharding | Primary Postgres CPU sustained >60% or p95 read >200ms |
| Server-side STT | On-device transcript accuracy measured <85% on your content |
| RAG / vector DB | Curriculum exceeds what fits in a prompt — not before |
| Event sourcing / CQRS | Never, for this product |
| Kafka | Never, for this product |
| GraphQL | Never — the mobile client has ~20 endpoints |
| Admin web panel | Ops load exceeds ~2 hours/week of CLI work |
| Multi-region | You have paying users on another continent |

### 0.5 What this spec assumes it does NOT know

This document specifies the **target**. It does not describe the current backend,
because that has not been inventoried. **Phase 0 exists precisely to produce that
missing baseline**, and no code-changing phase may begin until Phase 0's output
is committed. Any instruction here that says "replace X" is conditional on Phase 0
confirming X exists.

---

## 1. Non-Functional Requirements

These are the numbers. They are the acceptance criteria for "production-ready."
Anything not measurable here is not a requirement.

### 1.1 Latency budgets

Measured at the API edge, excluding client network, under the load profile in §1.2.

| Endpoint | p95 | p99 | Hard timeout | On timeout |
|---|---|---|---|---|
| `POST /learning/sessions/{id}/answer` (no LLM) | 150 ms | 400 ms | 2 s | 504 + error envelope |
| `POST /learning/sessions/{id}/answer` (with LLM) | 2.5 s | 4.0 s | 4 s | Deterministic template, HTTP 200 |
| `POST /learning/sessions` | 300 ms | 700 ms | 3 s | 504 |
| `GET /progress/{child_id}` | 200 ms | 500 ms | 3 s | 504 |
| `GET /recommendations/{child_id}` | 250 ms | 600 ms | 3 s | 504 |
| `POST /guide/respond` | 2.5 s | 4.0 s | 4 s | Deterministic template, HTTP 200 |
| `POST /doubts/{id}/message` | 3.0 s | 5.0 s | 5 s | Deterministic template, HTTP 200 |
| `GET /health/ready` | 100 ms | 200 ms | 1 s | 503 |

**The critical rule:** the answer-evaluation path must never *wait* on the LLM to
persist truth. Persist the attempt and mastery update, commit, *then* call the AI.
An AI timeout degrades the teaching voice, never the child's progress.

### 1.2 Load profile (the sizing target)

| Metric | Target |
|---|---|
| Registered children | 50,000 |
| Daily active children | 6,000 |
| Peak concurrent sessions | 800 |
| Peak API requests/sec | 80 |
| Peak LLM requests/sec | 8 |
| Average session length | 10–14 activities, 6–9 minutes |
| Answer submissions/day | ~70,000 |

### 1.3 Availability & error budget

- **API availability: 99.5% monthly** (≈3.6 h/month of downtime allowed).
- **Learning-truth durability: 100%.** A committed attempt is never lost. Redis loss,
  AI outage, or worker crash must not corrupt mastery, progress, or unlocks.
- **AI availability is explicitly NOT in the SLA.** The product must remain fully
  usable with the LLM provider completely down.

### 1.4 Cost ceilings

| Budget | Limit | On breach |
|---|---|---|
| LLM calls per session | 12 | Fall back to templates, increment `ai_budget_exhausted_total` |
| LLM calls per child per day | 200 | Same |
| LLM prompt size | 1,200 tokens | Truncate context (drop oldest doubt turns first) |
| LLM output size | 300 tokens | `max_tokens` enforced at provider |
| Speech upload | 5 MB / 60 s | 413 |
| Certificate render | Async only | Never inline |

Track `ai_cost_estimate_usd_total` as a counter. If it is not measured, it is not
controlled.

### 1.5 Infrastructure sizing

| Component | Spec | Notes |
|---|---|---|
| API | 3 × (2 vCPU, 2 GB), 4 uvicorn workers each | Stateless, behind a load balancer |
| PostgreSQL | 2 vCPU, 8 GB, 100 GB SSD | Managed (RDS / Cloud SQL / Neon) |
| PgBouncer | transaction pooling | Required: 3×4×10 = 120 connections exceeds a small Postgres |
| Redis | 1 GB, no persistence needed | Ephemeral by design |
| Worker | 1 × (1 vCPU, 1 GB) ARQ | Certificates, analytics rollups, cleanup |
| Object storage | S3-compatible | Certificates only, day 1 |

DB pool: `pool_size=10, max_overflow=5` per process, `pool_pre_ping=True`.

---

## 2. Architecture

### 2.1 Request path

```
React Native
     │
     ▼
Load Balancer  ──► 3 × FastAPI (stateless)
                        │
      ┌─────────────────┼──────────────────┐
      ▼                 ▼                  ▼
   Routers  ──►    Services  ──►     Repositories
  (thin, ≤15      (ALL business      (ALL SQL,
   lines each)     rules, pure        no business
                   where possible)     logic)
                        │                  │
                        ▼                  ▼
                 AI Orchestrator      PostgreSQL  ◄── source of truth
                  (never in a              ▲
                   transaction)            │
                        │              ARQ Worker
                        ▼                  │
                  Redis (cache,        Object Storage
                  rate limit,          (certificates)
                  idempotency)
```

**Layer contract — enforced in code review and by the phase gates:**

- **Router** — parse, authorize (via dependency), call one service method, return a
  schema. No `select()`, no business rules, no `if` on domain state. Target ≤15 lines.
- **Service** — owns all rules. Composes repositories. Owns transaction boundaries.
  Never imports FastAPI. Never touches `Request` or `Response`.
- **Repository** — owns all SQL. Returns models or plain data. Never decides anything.
- **AI** — called by services, *after* commit, never inside a transaction, always with
  a timeout and always with a fallback.

### 2.2 Project structure

```
backend/
├── app/
│   ├── main.py                    # app factory, middleware, lifespan
│   ├── core/
│   │   ├── config.py              # pydantic-settings, fail-fast validation
│   │   ├── security.py            # argon2, JWT encode/decode
│   │   ├── deps.py                # get_db, current_parent, owned_child
│   │   ├── errors.py              # AppError hierarchy + handlers
│   │   ├── logging.py             # structlog JSON + request_id
│   │   ├── redis.py               # client + helpers
│   │   ├── rate_limit.py          # sliding-window limiter
│   │   └── idempotency.py         # key capture/replay
│   ├── api/v1/
│   │   ├── router.py
│   │   ├── auth.py  children.py  curriculum.py  learning.py
│   │   ├── practice.py  progress.py  rewards.py  guide.py
│   │   ├── doubts.py  speech.py  certificates.py
│   ├── services/
│   │   ├── auth_service.py        session_service.py
│   │   ├── child_service.py       answer_service.py
│   │   ├── curriculum_service.py  mastery_service.py
│   │   ├── recommendation_service.py  reward_service.py
│   │   ├── doubt_service.py       certificate_service.py
│   │   └── speech_service.py
│   ├── ai/
│   │   ├── orchestrator.py        # entry point: respond(event, ctx) -> GuideResponse
│   │   ├── context.py             # build minimal context from trusted state
│   │   ├── policy.py              # decide: template vs LLM, which strategy
│   │   ├── validate.py            # schema + action allowlist + safety
│   │   ├── templates.py           # deterministic fallbacks
│   │   ├── prompts/               # versioned .txt, one per strategy
│   │   └── providers/
│   │       ├── base.py            # Protocol
│   │       └── groq.py
│   ├── db/
│   │   ├── session.py             # async engine, sessionmaker
│   │   ├── models.py              # all SQLAlchemy models (one file is fine at 17 tables)
│   │   └── repositories/
│   ├── schemas/                   # pydantic request/response, never DB models
│   ├── storage/
│   │   ├── base.py                # Protocol
│   │   ├── s3.py  local.py
│   ├── workers/
│   │   ├── main.py                # ARQ WorkerSettings
│   │   └── tasks.py
│   └── evaluation/
│       ├── base.py                # Evaluator Protocol
│       └── evaluators.py          # one per activity type
├── alembic/
├── tests/{unit,integration,contract,e2e,load}/
├── scripts/seed_curriculum.py
├── Dockerfile  docker-compose.yml  pyproject.toml  .env.example
```

### 2.3 Stack

| Concern | Choice | Rejected alternative |
|---|---|---|
| Framework | FastAPI, Python 3.12 | — |
| ORM | SQLAlchemy 2.x async + asyncpg | — |
| Migrations | Alembic | — |
| Validation | Pydantic v2 + pydantic-settings | — |
| Passwords | Argon2id (`argon2-cffi`) | bcrypt (fine, but Argon2id is the current default) |
| Tokens | PyJWT, HS256 | — |
| Cache/limits | redis-py async | — |
| Background jobs | **ARQ** | Celery — too heavy for 3 job types |
| Logs | structlog → JSON → stdout | — |
| Metrics | `prometheus-fastapi-instrumentator` → `/metrics` | Full OTel collector — add later |
| Errors | Sentry SDK | — |
| Tests | pytest, pytest-asyncio, httpx, testcontainers | — |
| Load test | Locust | — |
| Lint/type | ruff + mypy (strict on `services/`, `ai/`, `evaluation/`) | — |

---

## 3. Data Model

17 tables. Every one earns its place. `id` is UUIDv7 unless noted. All timestamps are
`TIMESTAMPTZ`, all times UTC, all API output ISO-8601.

### 3.1 Identity & ownership

**`users`** — parents only. Children never authenticate.
`id, email (unique, citext), password_hash, display_name, locale, consent_record_id,
is_active, created_at, updated_at`

**`refresh_tokens`** — rotation + revocation.
`id, user_id (FK), token_hash (unique), family_id, expires_at, revoked_at,
replaced_by_id, user_agent_hash, created_at`
*Rotation:* on refresh, revoke the old token and issue a new one in the same `family_id`.
Reuse of a revoked token revokes the entire family (theft detection).
Index: `(user_id, expires_at)`, `token_hash`.

**`children`**
`id, user_id (FK), display_name, birth_year, birth_month, locale,
preferences JSONB, current_class_id, current_level_id,
unlocked_level_ids UUID[], avatar_key, created_at, updated_at, deleted_at`
- `preferences` JSONB replaces a separate table: `{voice_speed, tts_voice, daily_goal_minutes, sound_on}`.
- `unlocked_level_ids` is append-only; replaces an unlock table.
- **Never store a child's full DOB or exact name if avoidable** — birth year/month is
  enough for age banding. See §7.
Index: `(user_id)` where `deleted_at IS NULL`.

### 3.2 Curriculum (seeded, read-heavy, small)

**`classes`** — `id, code (unique), title, min_age, max_age, sort_order, is_active`
**`levels`** — `id, class_id (FK), code, title, sort_order, is_active`
**`lessons`** — `id, level_id (FK), code, title, sort_order, is_active`
**`activities`** — `id, lesson_id (FK), code, type, title, config JSONB, skill_ids TEXT[], sort_order, is_active`
**`questions`** — `id, activity_id (FK), code, prompt, media JSONB, answer_spec JSONB, hint, skill_id, difficulty SMALLINT, sort_order, is_active`

- `activities.type` ∈ `voice_repeat, tap_choice, image_match, count_objects,
  shape_match, color_match, letter_trace, shape_trace, free_draw, word_build,
  sentence_repeat, story_listen`.
- `answer_spec` is the evaluator contract, e.g.
  `{"kind":"choice","correct_id":"c2"}` · `{"kind":"numeric","value":4,"tolerance":0}`
  · `{"kind":"phonics","accept":["bee","b"],"min_similarity":0.82}`.
- Adding a class/lesson is **data**, never a code change or a new endpoint.
- Curriculum is cached in Redis for 1 hour, keyed by `curriculum:v{content_version}:*`,
  busted by bumping `content_version` in config.

### 3.3 Learning

**`sessions`** — learning *and* practice, unified.
`id, child_id (FK), mode ('learning'|'practice'), status ('active'|'completed'|'abandoned'),
lesson_id, plan JSONB, current_index SMALLINT, score INT, stars SMALLINT,
ai_calls_used SMALLINT, started_at, last_activity_at, completed_at, expires_at`
- `plan` is the frozen sequence: `[{"activity_id":..., "question_ids":[...]}, ...]`.
  This replaces a `session_steps` table entirely — a 10-step plan is a tiny JSONB blob,
  and resume is a single row read.
- `expires_at = started_at + 24h`. A stale active session is abandoned by the worker.
- Index: `(child_id, status)`, `(status, expires_at)`.

**`attempts`** — the append-only truth of what the child did.
`id, session_id (FK), child_id (FK), question_id (FK), skill_id, attempt_index SMALLINT,
raw_answer JSONB, normalized_answer TEXT, is_correct BOOL, confidence NUMERIC(3,2),
evaluator TEXT, latency_ms INT, created_at`
- Never updated, only inserted. Index: `(child_id, skill_id, created_at DESC)`,
  `(session_id, created_at)`.
- Unique: `(session_id, question_id, attempt_index)` — this is what makes retries idempotent.

**`skill_mastery`** — one row per (child, skill).
`child_id (FK), skill_id, mastery_raw NUMERIC(4,3), attempts_total INT,
correct_total INT, streak SMALLINT, last_attempt_at, updated_at`
PK: `(child_id, skill_id)`. No decay column — decay is computed at read time (§4.3).

### 3.4 Rewards & recognition

**`reward_ledger`** — append-only, replaces both `rewards` and `reward_events`.
`id, child_id (FK), kind ('star'|'badge'|'streak_day'), amount INT, reason,
session_id, skill_id, created_at`
Current totals are `SUM(amount)` grouped by kind, cached in Redis 60 s.
An append-only ledger is auditable and cannot drift; a mutable counter can.

**`certificates`** — `id, child_id (FK), level_id (FK), status ('pending'|'ready'|'failed'), storage_key, issued_at, created_at`
Unique: `(child_id, level_id)`. Rendered by the worker, never inline.

### 3.5 AI & doubts

**`doubts`** — `id, child_id (FK), session_id, question_id, status ('open'|'resolved'|'abandoned'), turns JSONB, opened_at, resolved_at`
- `turns` JSONB: `[{"role":"child","text":...,"at":...},{"role":"guide",...}]`, capped
  at 12 turns. A separate messages table is not worth the join for a bounded conversation.

**`ai_calls`** — observability + cost, never product truth.
`id, child_id, session_id, event, strategy, provider, model, prompt_version,
latency_ms, input_tokens, output_tokens, outcome ('ok'|'invalid'|'unsafe'|'timeout'|'circuit_open'|'budget'), created_at`
- **Never** stores prompt or completion text (child content + cost). Index: `(created_at)`.

**`events`** — analytics + audit, append-only.
`id, child_id, user_id, name, props JSONB, request_id, created_at`
Index: `(name, created_at)`, `(child_id, created_at)`. Partition by month once >50M rows.

### 3.6 Compliance

**`consent_records`** — see §7.
`id, user_id (FK), child_id, purpose TEXT[], method ('existing_verified_user'|'id_document'|'digital_token'),
verified_at, verifier_ref, ip_hash, policy_version, revoked_at, created_at`
Append-only, never updated — a revocation is a new row plus setting `revoked_at`.

---

## 4. Core Algorithms

The previous spec said "keep the algorithm simple and explainable" and left it there.
Here it is, specified precisely enough to unit-test.

### 4.1 Answer evaluation

Pure functions. No I/O, no LLM, no randomness.

```python
class Evaluator(Protocol):
    def normalize(self, raw: dict) -> str: ...
    def evaluate(self, normalized: str, spec: dict) -> Verdict  # (is_correct, confidence)
```

| `answer_spec.kind` | Normalization | Correct when |
|---|---|---|
| `choice` | trim option id | `id == spec.correct_id` |
| `numeric` | strip non-digits, parse int | `abs(v - spec.value) <= spec.tolerance` |
| `text` | lowercase, strip punctuation, collapse spaces | exact match against `spec.accept[]` |
| `phonics` | lowercase, strip punctuation, apply `spec.homophones` map | exact match, **or** Jaro-Winkler ≥ `spec.min_similarity` (default 0.82) |
| `match` | sort pairs | set equality with `spec.pairs` |
| `trace` | client sends `{completed: bool, accuracy: float}` | `accuracy >= spec.min_accuracy` (default 0.7) |

**Speech-specific rules:** the similarity threshold exists because a 4-year-old saying
"bee" for the letter B must count. Confidence is stored separately from correctness —
`is_correct=true, confidence=0.84` is a legitimate and useful record. Never let
confidence silently flip correctness; the threshold is the only gate.

**Never** call the LLM to judge an answer. Not as a fallback, not for "hard" cases.

### 4.2 Attempt flow (transaction boundary)

```
1. Load session FOR UPDATE (row lock — no distributed lock needed, Postgres has one)
2. Validate: session active, not expired, question == plan[current_index]
3. Idempotency: if (session, question, attempt_index) exists → return stored result
4. Evaluate deterministically (pure, in-memory)
5. INSERT attempt
6. UPSERT skill_mastery (§4.3)
7. INSERT reward_ledger rows if earned
8. Advance current_index if correct or attempt_index >= 3
9. COMMIT                                    ◄── truth is now durable
10. Call AI orchestrator (outside transaction, with timeout, with fallback)
11. Return {result, progress_delta, guide_response, next_action}
```

Step 9 before step 10 is the single most important ordering rule in this document.
`SELECT ... FOR UPDATE` on the session row serializes concurrent submissions for that
session — which is the only concurrency this app actually has. That is why §0.3 drops
distributed locks.

### 4.3 Mastery (deterministic EWMA with lazy decay)

```python
def outcome(attempt_index: int, is_correct: bool) -> float:
    if not is_correct:            return 0.0
    if attempt_index == 1:        return 1.0
    if attempt_index == 2:        return 0.6
    return 0.3                    # correct, but needed 3+ tries

def update(m: SkillMastery, attempt_index: int, is_correct: bool) -> SkillMastery:
    alpha = 0.30 if m.attempts_total < 5 else 0.15    # learn fast, then stabilize
    o = outcome(attempt_index, is_correct)
    m.mastery_raw    = round(m.mastery_raw + alpha * (o - m.mastery_raw), 3)
    m.attempts_total += 1
    m.correct_total  += int(is_correct)
    m.streak          = m.streak + 1 if is_correct else 0
    m.last_attempt_at = now()
    return m

HALF_LIFE_DAYS = 60
def effective(m: SkillMastery, at=now()) -> float:
    days = (at - m.last_attempt_at).days
    return round(m.mastery_raw * (0.5 ** (days / HALF_LIFE_DAYS)), 3)
```

**Bands:** `weak < 0.40` · `learning 0.40–0.749` · `mastered ≥ 0.75 AND attempts_total ≥ 4`

The `attempts_total ≥ 4` guard prevents one lucky answer from marking a skill mastered
and unlocking a level. Decay is computed at read time — **no cron job, no nightly
batch, no drift**. New mastery starts at `0.0`.

**Worked example — use these as literal test fixtures.** A child answering a fresh skill
correctly on the first try, repeatedly:

| Attempt | `mastery_raw` | Band |
|---|---|---|
| 1 | 0.300 | weak |
| 2 | 0.510 | learning |
| 3 | 0.657 | learning |
| 4 | **0.760** | **mastered** (≥0.75 and ≥4 attempts) |
| 5 | 0.832 | mastered |
| 6 | 0.857 | mastered |

The constants are tuned so that **four consecutive first-try correct answers = mastered**,
and three is not enough. Decay check: `mastery_raw = 0.8` untouched for 60 days →
`effective = 0.400` → drops to the weak band and R3 picks it up. If an implementation
disagrees with this table, the implementation is wrong.

This is a pure function of `(mastery_raw, attempts_total, attempt_index, is_correct, elapsed)`.
It is exhaustively unit-testable and needs zero database access to verify.

### 4.4 Recommendation (ordered rules, first match wins)

```
R1  parent_selected — explicit parent/child choice          → always wins
R2  continue        — an active, unexpired session exists   → resume it
R3  weak_skill      — any skill in current or prior level with
                      effective < 0.40 AND last_attempt_at > 12h ago
R4  revise          — a previously mastered skill decayed below 0.60  (spaced repetition)
R5  new_skill       — next incomplete activity in the current lesson
R6  new_skill       — current level complete → unlock next level, first activity
R7  fallback        — replay the most recent lesson (never return "nothing to do")
```

The `> 12h` guard in R3 stops the engine from grinding a child on the same failed skill
all afternoon — which is how kids quit. R4 is what makes learning stick.

Every response returns `{recommendation, reason}` where `reason` is one of
`continue, revise, weak_skill, new_skill, parent_selected, fallback`. The frontend shows
different copy per reason; the reason is never inferred client-side.

### 4.5 Level unlocking

```
level_complete(child, level) =
    every skill mapped to that level has
        effective_mastery >= 0.75 AND attempts_total >= 4
```

On completion: append the next level's id to `children.unlocked_level_ids`, insert a
`reward_ledger` badge row, and enqueue certificate rendering. Computed server-side only,
inside the same transaction as the attempt that triggered it. The client is told; it
never decides.

---

## 5. AI Guide

### 5.1 Pipeline

```
Committed backend truth
   → context.build()      minimal, structured, no PII
   → policy.decide()      template or LLM? which strategy? budget left?
   → [template]  ────────────────────────────────────┐
   → prompt + provider (timeout 4s, 1 retry, circuit breaker)
   → validate.schema()    strict Pydantic, else fallback
   → validate.actions()   allowlist + target allowlist, else fallback
   → validate.safety()    banned patterns + length, else fallback
   → GuideResponse ───────────────────────────────────┴──→ client
```

### 5.2 Policy table — when the LLM is actually called

This table is the cost model. It eliminates roughly 60% of naive LLM calls.

| Event | LLM? | Strategy |
|---|---|---|
| `answer_correct` | **No** — template | celebrate |
| `answer_incorrect`, attempt 1 | **No** — use `question.hint` | hint |
| `answer_incorrect`, attempt 2 | Yes | `alternate_example` |
| `answer_incorrect`, attempt 3+ | Yes | `simplify_or_prerequisite` |
| `doubt_asked` | Yes | `answer_doubt` |
| `doubt_not_understood` | Yes | `simplify` |
| `session_start` / `session_complete` | **No** — template | — |
| `idle_nudge` | **No** — template | — |

Attempt 1 uses the curriculum author's own hint. It is faster, free, better written,
and pedagogically more consistent than anything the model will produce cold.

### 5.3 Context contract (what the model is allowed to see)

```json
{
  "event": "ANSWER_INCORRECT",
  "child":    { "age_band": "3-5", "locale": "en-IN" },
  "question": { "concept": "letter_B_sound", "prompt": "...", "hint": "...", "attempt": 2 },
  "progress": { "weak_skills": ["letter_B_sound"], "recent_strength": "letter_A_sound" },
  "ui": {
    "allowed_actions": ["highlight", "show_hint", "start_listening"],
    "allowed_targets": ["letter-B", "ball-image", "microphone-button"]
  }
}
```

**Never in context:** child's name, exact age, DOB, parent email, any id that is not
opaque, raw audio, raw drawing data, or free-text the child typed that has not been
normalized. Age is a *band*, not a number.

### 5.4 Response contract

```json
{
  "say": "string, max 220 chars",
  "strategy": "hint|example|story|simplify|prerequisite|celebrate",
  "actions": [{ "type": "highlight", "target": "letter-B" }],
  "listen_after": true
}
```

Allowed action types (closed set — reject anything else):
`none · highlight · show_hint · repeat_instruction · start_listening · play_animation ·
celebrate · navigate_safe · wait_for_child`

### 5.5 Validation — the concrete rules

1. **Schema** — strict Pydantic. Extra fields → reject.
2. **Actions** — `type` in the closed set; `target` in *this request's*
   `ui.allowed_targets`. A hallucinated target is a rejection, not a filter.
3. **Length** — `say` ≤ 220 chars (roughly 12 seconds of TTS for a 4-year-old).
4. **Safety** — reject on: shaming patterns (`stupid, wrong again, bad, you failed,
   why can't you`), any PII solicitation (`your name, where do you live, how old,
   your address, your phone`), any URL, any imperative to leave the app.
5. **Injection** — the child's doubt text is inserted as a *quoted data block*, never
   concatenated into the instruction section. System policy is restated after user
   content in the prompt.
6. **On any failure** → deterministic template, log `ai_calls.outcome`, increment
   `ai_validation_failure_total{reason}`. Never surface a validation error to the child.

### 5.6 Circuit breaker & budgets (the missing safety net)

- **Provider circuit:** 5 consecutive failures, or >50% errors across 20 calls in 60 s
  → circuit **open** for 30 s → templates only. Then half-open with a single probe.
  State in Redis so all 3 replicas agree.
- **Session budget:** `sessions.ai_calls_used >= 12` → templates only.
- **Child daily budget:** 200 calls/day (Redis counter, TTL 24 h) → templates only.
- **Validation circuit:** if >30% of responses fail validation over 50 calls, alert —
  it means a prompt or model change broke the contract.

Every breaker degrades to a template. None of them ever fails a request.

### 5.7 Pre-launch AI safety gate (non-negotiable)

Before any build reaches a real child:

1. **Adversarial suite** — ≥100 red-team prompts covering prompt injection via doubt
   text, PII solicitation attempts, requests to leave the app, hallucinated targets,
   emotional distress from the child, and non-English injection. Committed as tests.
2. **Zero tolerance** — 0 responses that pass validation but violate §5.5 rule 4.
3. **Human review sample** — 200 real doubt responses reviewed by a person before
   general availability, and 1% sampled weekly afterwards.
4. **Distress escalation** — if a child's doubt text matches distress patterns, respond
   with a fixed, human-written template and flag the event for parent visibility.
   Never let the model improvise here.

---

## 6. API Surface

All under `/api/v1`. Versioned from day one; `/api/v0` prototype routes may be kept as
thin adapters for exactly one release, then deleted.

```
POST   /auth/register            POST   /auth/login
POST   /auth/refresh             POST   /auth/logout

GET    /children                 POST   /children
GET    /children/{id}            PATCH  /children/{id}
DELETE /children/{id}                                  # soft delete + export trigger

GET    /classes                  GET    /classes/{id}/levels
GET    /levels/{id}/lessons      GET    /lessons/{id}/activities

POST   /learning/sessions        GET    /learning/sessions/{id}
POST   /learning/sessions/{id}/answer
POST   /learning/sessions/{id}/complete

POST   /practice/sessions        POST   /practice/sessions/{id}/answer

GET    /progress/{child_id}      GET    /recommendations/{child_id}
GET    /rewards/{child_id}       GET    /certificates/{child_id}

POST   /guide/respond
POST   /doubts                   POST   /doubts/{id}/message
POST   /doubts/{id}/resolve

POST   /speech/transcribe

GET    /health/live              GET    /health/ready      GET /metrics
```

Notes:

- No `/sessions/{id}/resume` — `GET /learning/sessions/{id}` returns everything needed
  to resume. A separate resume endpoint is state the client shouldn't have to manage.
- `GET /health/ready` checks Postgres + Redis + required config. **Never** the LLM
  provider — the app is designed to be healthy without it.

### 6.1 Error envelope

```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "The learning session could not be found.",
    "request_id": "01J8X..."
  }
}
```

Codes are a closed enum, documented, and stable. `message` is safe to show a parent;
it is never a stack trace and never contains child data.

### 6.2 Idempotency

Every `POST` that mutates accepts `Idempotency-Key`. The key + request hash is stored
in Redis for 24 h; a replay returns the original response with `Idempotency-Replayed: true`.
Mobile networks drop requests — without this, a retried answer submission double-counts
a child's score, which parents notice and do not forgive.

### 6.3 Rate limits (sliding window, Redis)

| Scope | Limit |
|---|---|
| `POST /auth/login` | 5 / 15 min per email **and** 20 / 15 min per IP |
| `POST /auth/register` | 3 / hour per IP |
| `POST /auth/refresh` | 30 / hour per user |
| AI endpoints (`/guide/*`, `/doubts/*`) | 30 / min per child |
| `POST /speech/transcribe` | 20 / min per child |
| Answer submission | 60 / min per session |
| Global default | 300 / min per user |

Return `429` with `Retry-After`.

---

## 7. Child Safety, Privacy & Compliance

This section is **not** advisory. It is the one area where the previous spec's
"prepare the architecture for consent" is a legal exposure rather than a technical gap.

### 7.1 The regulatory position

India's **Digital Personal Data Protection Rules, 2025** were notified on
**14 November 2025**, operationalizing the DPDP Act, 2023. Substantive obligations
become enforceable on **13 May 2027**. That is the design window — not a reason to wait.

**Rule 10** requires *verifiable* consent from a parent or lawful guardian before
processing the personal data of **anyone under 18**. "Verifiable" means taking reasonable
steps to confirm both (a) that the consenting person is an adult, and (b) that they are
genuinely the child's parent or guardian. Recognized methods:

- reliance on an **already-verified adult user** of the platform,
- **voluntarily provided identity documents**,
- **virtual tokens** mapped to a verified identity (e.g. via DigiLocker-style services).

The DPDP Act also **prohibits tracking, behavioural monitoring, and targeted advertising
directed at children**, and requires breach notification to the Data Protection Board
and to affected principals.

If the app ships to the US, **COPPA** applies below 13; to the EU, **GDPR Article 8**
applies. Both are stricter in places than DPDP. **Get this reviewed by counsel before
launch — this document is engineering guidance, not legal advice.**

### 7.2 What that means in the schema and code

| Requirement | Implementation |
|---|---|
| Verifiable parental consent | `consent_records` table (§3.6); no child profile can be created without an active row |
| Immutable consent audit trail | Append-only; records *who* consented, *when*, *for what purpose*, *how verified*, and the policy version |
| No behavioural ad tracking | No third-party analytics SDK. No ad SDK. `events` is first-party and product-only. Non-negotiable. |
| Data minimization | Birth year + month, never full DOB. Display name, never legal name. No address, no phone, no school. |
| Purpose limitation | `consent_records.purpose[]` is checked before any non-core processing |
| Right to erasure | `DELETE /children/{id}` → soft delete → worker hard-deletes after 30 days |
| Right to export | Worker generates a JSON bundle of the child's profile, attempts, mastery, rewards |
| Retention | Attempts & mastery: while account active + 30 days. Audio: **never stored by default**. Transcripts: 90 days. `ai_calls`: 180 days (metadata only). `events`: 12 months. Enforced by a worker job, not by intent. |
| Breach readiness | Documented runbook, DPB + parent notification templates, `security-contact` in config |
| Encryption | TLS 1.2+ in transit; DB encryption at rest; secrets in the platform secret manager, never in git |

### 7.3 Logging rules (enforced by test)

**Never logged, at any level, ever:** raw child speech, raw drawing data, prompt text,
model completions, passwords, tokens, full email addresses, child display names.

Add a test that greps structured log output produced during the e2e suite for known
child-content fixtures. A privacy rule that isn't tested is a privacy rule that will
be broken by the third contributor.

### 7.4 Transport & client-side security

The attack surface is not backend-only. The mobile client is named in the requirements,
so it is in scope.

| Control | Requirement |
|---|---|
| CORS | Explicit origin allowlist from config. **Never** `allow_origins=["*"]` together with credentials. The RN app doesn't need CORS; a web build does — allowlist that origin only. |
| Security headers | `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` |
| TLS | 1.2 minimum, terminated at the load balancer, HTTP redirected |
| Token storage (mobile) | Refresh token in **iOS Keychain / Android Keystore** via `expo-secure-store` or `react-native-keychain` — never `AsyncStorage`. Otherwise a compromised device exposes a parent session for 30 days. |
| Token in transit | `Authorization: Bearer` header only. Never a query parameter — query strings land in access logs. |
| Dependency scanning | `pip-audit` in CI, failing the build on HIGH/CRITICAL. Dependabot or Renovate enabled. |
| Secret scanning | `gitleaks` in CI. A leaked key in git history is a rotation event, not a delete-the-commit event. |
| Key rotation | `SECRET_KEY` rotation supported via a key-id (`kid`) claim in the JWT, so rotating doesn't log every parent out |
| Request size | Global 1 MB body limit, except the speech upload route |
| SQL | Parameterized only, via the SQLAlchemy expression language. Zero string-formatted SQL, CI-enforced. |

**Deliberately not doing:** certificate pinning. At this scale it breaks more releases
than it prevents attacks. Revisit if the app ever handles payments in-process.

---

## 8. Observability

Small, useful, not a project of its own.

**Logs** — structlog JSON to stdout. Every line carries `request_id`, `route`, `status`,
`duration_ms`, and `user_id`/`child_id` where relevant. `request_id` comes from
`X-Request-ID` or is generated, returned in the response, and included in every error
envelope. Parent reports a bug → you have the trace.

**Metrics** — Prometheus at `/metrics`:

- `http_request_duration_seconds{route,method,status}` (histogram)
- `ai_calls_total{outcome,strategy}` · `ai_latency_seconds` · `ai_cost_estimate_usd_total`
- `ai_validation_failure_total{reason}` · `ai_circuit_state`
- `attempts_total{correct}` · `sessions_started_total` · `sessions_completed_total`
- `db_pool_in_use` · `db_pool_available`
- `arq_jobs_total{status}` · `arq_queue_depth`
- `rate_limit_rejected_total{scope}`

**Errors** — Sentry, with a `before_send` scrubber that drops child content.

**Alerts (only 6 — alert fatigue is a real outage cause):**

1. p95 answer latency > 500 ms for 10 min
2. 5xx rate > 1% for 5 min
3. AI circuit open > 5 min
4. AI validation failure rate > 30%
5. DB pool exhausted
6. ARQ queue depth > 500 or worker heartbeat missing

---

## 9. Execution Phases

Nine phases. Each is independently shippable, independently testable, and has a **hard
gate**. An agent may not begin phase N+1 until phase N's gate passes and is committed.

Each phase below contains a **standalone prompt** — copy it verbatim into a fresh agent
session. It is written to be self-contained; it references this document by path.

---

### Phase 0 — Audit & Baseline (no code changes)

**Goal:** produce the baseline this specification currently lacks.

**Deliverable:** `docs/backend-audit.md` containing:

1. File inventory: every backend file, LOC, and a one-line purpose.
2. Route inventory: every existing endpoint, method, auth requirement, and current consumer.
3. State inventory: **every** module-level mutable object, in-memory store, and global.
4. Dependency map: what imports what; every circular import flagged.
5. Reuse verdict per file: `KEEP` / `PORT` / `REPLACE` / `DELETE`, with a one-line reason.
6. Mobile call-site inventory: every backend URL the React Native app calls, with the
   file:line of each call.
7. Test inventory: what tests exist, what they actually cover.
8. Risk list: anything surprising found along the way.

**Acceptance criteria**

- [ ] Every backend file appears exactly once with a verdict.
- [ ] Every route in the running app appears in the route inventory (verified against
      the live OpenAPI schema, not by reading code).
- [ ] Every mobile call site is mapped to a route, or explicitly flagged as orphaned.
- [ ] Zero code files modified in this phase.

**Gate:** the audit is committed and a human has read it. **No exceptions** — every
later phase depends on knowing what "replace the prototype" actually means.

> **Prompt — Phase 0**
>
> Read `docs/backend-architecture.md` in full, then audit the existing backend of this
> repository **without modifying a single line of code**. Produce `docs/backend-audit.md`
> with these eight sections: (1) file inventory with LOC and purpose, (2) route inventory
> verified against the live OpenAPI schema, (3) inventory of every module-level mutable
> object / in-memory store / global, (4) import dependency map with circular imports
> flagged, (5) a KEEP/PORT/REPLACE/DELETE verdict with a one-line reason for every file,
> (6) every backend URL called by the React Native client with file:line, (7) existing
> test inventory and real coverage, (8) a risk list. Every backend file must appear
> exactly once with a verdict. Do not write, edit, or delete any application code. If
> the repo layout contradicts anything in the architecture doc, say so explicitly in
> the risk list rather than assuming.

---

### Phase 1 — Platform Skeleton

**Goal:** an empty but genuinely production-shaped application that boots, connects,
logs, migrates, and deploys.

**In scope:** app factory · pydantic-settings config with fail-fast validation ·
structlog JSON logging + `request_id` middleware · error envelope + handlers ·
async SQLAlchemy engine + session dependency · Alembic wired with one empty migration ·
`/api/v1` router mounted (no business routes) · `/health/live`, `/health/ready`,
`/metrics` · Dockerfile (multi-stage, non-root) · docker-compose (api + postgres + redis) ·
pytest + ruff + mypy + CI pipeline.

**Out of scope:** every domain feature. Auth. Any table.

**Acceptance criteria**

- [ ] `docker compose up` → healthy API, Postgres, Redis in <60 s from clean.
- [ ] `GET /health/ready` returns 200 with DB + Redis status; returns 503 within 1 s
      when Postgres is stopped.
- [ ] App **refuses to start** in `ENV=production` if `SECRET_KEY`, `DATABASE_URL`, or
      `REDIS_URL` is missing — with a clear message naming the missing variable.
- [ ] Every response carries `X-Request-ID`; every log line carries the same value.
- [ ] Raising any `AppError` produces the §6.1 envelope; an unhandled exception produces
      a 500 envelope with **no** stack trace in the body.
- [ ] `alembic upgrade head` and `alembic downgrade base` both succeed.
- [ ] Docker image runs as a non-root user; `docker image inspect` confirms.
- [ ] CI runs ruff + mypy + pytest and fails the build on any error.

**Gate:** CI green, image builds, compose stack healthy.

> **Prompt — Phase 1**
>
> Read `docs/backend-architecture.md` (especially §0.2, §2.2, §2.3) and `docs/backend-audit.md`.
> Build **only** the platform skeleton described in Phase 1 — no domain features, no auth,
> no tables. Create the directory structure from §2.2 with empty packages. Implement:
> app factory with lifespan; `core/config.py` using pydantic-settings that fails fast in
> production on missing SECRET_KEY / DATABASE_URL / REDIS_URL naming the missing variable;
> `core/logging.py` with structlog JSON to stdout plus a request_id middleware that reads
> `X-Request-ID` or generates one and echoes it on the response; `core/errors.py` with an
> AppError hierarchy and handlers emitting exactly the §6.1 envelope with no stack traces;
> async SQLAlchemy engine and `get_db` dependency with pool_size=10, max_overflow=5,
> pool_pre_ping=True; Alembic with one empty baseline migration; an `/api/v1` router with
> no routes; `/health/live`, `/health/ready` (checks Postgres and Redis, never the LLM,
> returns within 1s), and `/metrics` via prometheus-fastapi-instrumentator; a multi-stage
> Dockerfile running as a non-root user; docker-compose with api + postgres + redis;
> pyproject with ruff and mypy (strict for `services/`, `ai/`, `evaluation/`); pytest with
> httpx AsyncClient; and a CI workflow running ruff, mypy, and pytest. Meet every Phase 1
> acceptance checkbox and show me the passing output for each.

---

### Phase 2 — Auth & Child Ownership

**Goal:** real authentication, and an ownership guarantee that later phases can rely on.

**In scope:** `users`, `refresh_tokens`, `children`, `consent_records` tables ·
Argon2id hashing · access (15 min) + refresh (30 d) tokens with rotation and family-based
theft detection · `current_parent` and `owned_child` dependencies · child CRUD ·
soft delete · auth rate limits · consent record creation gating child creation.

**Acceptance criteria**

- [ ] Passwords stored as Argon2id; the plaintext appears in **no** log, response, or column.
- [ ] Access token expires in 15 min; refresh in 30 days.
- [ ] Refresh rotates: the old token is revoked and a new one issued in the same family.
- [ ] **Reusing a revoked refresh token revokes the entire family** and returns 401 —
      with a test proving it.
- [ ] Logout revokes the presented refresh token's whole family.
- [ ] Parent A requesting **any** of Parent B's children returns **404** (not 403 — 403
      confirms the resource exists). One test per child-scoped route, no exceptions.
- [ ] 6th login attempt for one email within 15 min returns 429 with `Retry-After`.
- [ ] A child profile cannot be created without an active `consent_records` row.
- [ ] `children` stores `birth_year` + `birth_month` only — no full DOB column exists.
- [ ] Coverage on `services/auth_service.py` ≥ 90%.

**Gate:** the cross-parent access test suite passes for every child-scoped route, and a
human reviews the token rotation logic.

> **Prompt — Phase 2**
>
> Read `docs/backend-architecture.md` §3.1, §3.6, §6.3, §7. Implement Phase 2: real auth
> and child ownership. Create Alembic migrations for `users`, `refresh_tokens`, `children`,
> and `consent_records` exactly as specified in §3. Implement Argon2id password hashing;
> 15-minute access tokens and 30-day refresh tokens; refresh rotation where the old token
> is revoked and the replacement joins the same `family_id`; and reuse-detection where
> presenting an already-revoked refresh token revokes the entire family and returns 401.
> Implement `current_parent` and `owned_child` FastAPI dependencies — `owned_child` must
> return **404**, never 403, when the child belongs to another parent. Implement child
> CRUD with soft delete, storing only `birth_year` and `birth_month` (do not add a DOB
> column). Block child creation unless an active `consent_records` row exists for that
> parent. Add the auth rate limits from §6.3 using Redis sliding windows. Write tests
> covering every acceptance checkbox in Phase 2, including one cross-parent 404 test per
> child-scoped route, and reach ≥90% coverage on `auth_service.py`.

---

### Phase 3 — Curriculum & Seeding

**Goal:** curriculum becomes data. Adding a lesson never requires a deploy.

**In scope:** `classes`, `levels`, `lessons`, `activities`, `questions` · read endpoints ·
Redis caching with version-based invalidation · an idempotent seed CLI · a curriculum
JSON schema with a validator.

**Acceptance criteria**

- [ ] `python scripts/seed_curriculum.py data/curriculum.json` is idempotent — running
      it three times produces identical DB state (verified by row-count and checksum).
- [ ] The seeder **validates before writing** and fails atomically on a malformed file,
      leaving the DB untouched.
- [ ] Adding a new class + level + lesson + 5 activities requires **zero** code changes.
- [ ] Every `activities.type` in the seed data has a registered evaluator, or the seeder
      rejects the file naming the offending type.
- [ ] Curriculum reads are cached in Redis (1 h TTL); bumping `CONTENT_VERSION` in config
      invalidates all of it.
- [ ] `GET /classes` p95 < 100 ms warm, < 300 ms cold.
- [ ] With Redis stopped, every curriculum endpoint still returns correct data from Postgres.

**Gate:** the real curriculum seeds clean, and the Redis-down test passes.

> **Prompt — Phase 3**
>
> Read `docs/backend-architecture.md` §3.2, §4.1. Implement Phase 3: the curriculum model
> and seeding. Create migrations for `classes`, `levels`, `lessons`, `activities`, and
> `questions` per §3.2, including the `answer_spec` JSONB contract. Implement read-only
> endpoints for classes, levels, lessons, and activities. Add Redis caching with a 1-hour
> TTL keyed by `curriculum:v{CONTENT_VERSION}:*`, and make every endpoint fall back
> correctly to Postgres when Redis is unavailable. Write `scripts/seed_curriculum.py` that
> loads a JSON curriculum file, validates it fully against a schema **before** writing
> anything, writes atomically in one transaction, is idempotent across repeated runs, and
> rejects the file if any `activities.type` has no registered evaluator. Prove idempotency
> with a test that seeds three times and asserts identical row counts and checksums. Then
> demonstrate that adding a new class with a level, a lesson, and five activities requires
> only a data-file change and zero code changes.

---

### Phase 4 — Session Engine & Deterministic Evaluation

**Goal:** the heart of the product. Sessions that resume, answers judged by code, truth
that survives anything. **This is the highest-value phase in the document.**

**In scope:** `sessions`, `attempts` tables · session start with a frozen plan ·
the §4.2 attempt transaction · the §4.1 evaluator registry · resume · complete ·
idempotency on answer submission.

**Out of scope:** mastery updates, recommendations, AI. Answers are judged and stored;
nothing learns from them yet.

**Acceptance criteria**

- [ ] Session ids are server-generated UUIDv7; a client-supplied id is ignored.
- [ ] `POST /answer` with a `question_id` that isn't `plan[current_index]` returns 409.
- [ ] The same `Idempotency-Key` submitted twice produces **one** attempt row and two
      identical responses, the second carrying `Idempotency-Replayed: true`.
- [ ] 20 concurrent identical submissions for one session produce exactly one attempt row
      (test with `asyncio.gather`).
- [ ] Killing the API process mid-session and restarting loses nothing: `GET /sessions/{id}`
      returns the exact resume point.
- [ ] Every evaluator has ≥10 unit tests including edge cases; phonics includes the
      "bee" → letter B case, numeric includes `"four"` and `" 4 "`.
- [ ] Evaluators are pure: no DB, no network, no clock, no randomness — enforced by test.
- [ ] Submitted score, attempt number, and step index in the request body are **ignored**;
      a test asserts that a client claiming `score: 9999` changes nothing.
- [ ] p95 answer latency < 150 ms at 80 req/s (Locust, no AI in the path).
- [ ] With Redis fully

<!-- ============================================================
     SOURCE TEXT TRUNCATED HERE.

     The specification as supplied to the agent was cut off
     mid-sentence at the Phase 4 acceptance criterion beginning
     "With Redis fully". Everything above this marker is verbatim
     from the source; everything below it in the original document
     is MISSING, namely:

       - the remainder of Phase 4's acceptance criteria and gate
       - the Phase 4 standalone prompt
       - Phases 5, 6, 7, 8 and 9 in their entirety
       - any sections numbered §10 and beyond

     Phase 0 (audit) and Phases 1-3 are complete and executable
     from this document. Do NOT begin Phase 4 or later until the
     missing text is supplied and appended here.
     ============================================================ -->
