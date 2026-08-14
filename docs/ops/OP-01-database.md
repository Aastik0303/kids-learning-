# OP-01 — Advanced PostgreSQL Persistence

**Goal:** every byte of user and child data lives in PostgreSQL. Nothing in process memory,
nothing in `sessionStorage`, nothing lost on restart.
**Blocked by:** nothing. Start here.
**Touches:** `backend/`

---

## 1. The problem

Today the backend keeps everything in memory:

| File | What it holds |
|---|---|
| `backend/app/services/mock_storage.py` | All application state |
| `backend/app/services/mock_auth.py` | Users and demo tokens |

Restart the server and every child's progress, stars, and certificates are gone. The web
client compounds this by keeping its own copy in `sessionStorage` — so there are two
unreliable stores and neither is authoritative.

"Advanced" here does not mean exotic. It means: **one authoritative store, correctly
modelled, with real constraints, real indexes, and real transactions.** A correctly
designed 19-table schema on a single Postgres instance will outlast any amount of clever
caching layered on a broken model.

---

## 2. The complete schema — 19 tables

17 from `../backend-architecture.md` §3, plus two added by OP-05.

### Identity & consent

| Table | Purpose | Key points |
|---|---|---|
| `users` | Parents. Children never authenticate. | `email` unique citext, `password_hash` Argon2id |
| `refresh_tokens` | Rotation + theft detection | `family_id`; reusing a revoked token revokes the family |
| `children` | Child profiles | `birth_year` + `birth_month` only — **never a full DOB**; `preferences` JSONB; `unlocked_level_ids` UUID[] |
| `consent_records` | Verifiable parental consent (DPDP Rule 10) | Append-only; records who, when, what purpose, how verified |

### Curriculum — seeded, read-heavy, near-static

| Table | Purpose |
|---|---|
| `classes` | Number Kingdom, Alphabet Forest, Colour Garden, Shape Island |
| `levels` | Ordered within a class |
| `lessons` | Ordered within a level |
| `activities` | `type` + `config` JSONB + `skill_ids` TEXT[] |
| `questions` | `answer_spec` JSONB — the evaluator contract — plus `hint`, `skill_id`, `difficulty` |

### Learning — the hot path

| Table | Purpose | Key points |
|---|---|---|
| `sessions` | Learning **and** practice, unified by a `mode` column | `plan` JSONB freezes the step sequence; `current_index`; `expires_at` |
| `attempts` | Append-only record of everything the child did | Unique `(session_id, question_id, attempt_index)` — this is what makes retries idempotent |
| `skill_mastery` | One row per (child, skill) | PK `(child_id, skill_id)`; no decay column — decay is computed at read time |

### Rewards & recognition

| Table | Purpose | Key points |
|---|---|---|
| `reward_ledger` | Append-only stars, badges, streak days | Totals are `SUM(amount)`. A ledger cannot drift; a mutable counter can. |
| `certificates` | Per (child, level) | Rendered by the worker, never inline |

### AI & support

| Table | Purpose | Key points |
|---|---|---|
| `doubts` | Hand-raise conversations | `turns` JSONB, capped at 12 |
| `ai_calls` | Cost and latency metadata | **Never** stores prompt or completion text |
| `events` | First-party analytics + audit | Append-only; partition by month past ~50M rows |

### Added by OP-05

| Table | Purpose |
|---|---|
| `daily_plans` | The scheduled study plan — see `OP-05-ai-tracking.md` |
| `learner_profiles` | Per-child pace and preference aggregates — see `OP-05-ai-tracking.md` |

---

## 3. Connection design

Not exotic, just correct.

| Concern | Setting |
|---|---|
| Driver | `asyncpg` via SQLAlchemy 2.x async |
| Pool | `pool_size=10`, `max_overflow=5`, `pool_pre_ping=True` per process |
| Total connections | 3 replicas × 4 workers × 10 = **120** → exceeds a small Postgres |
| Therefore | **PgBouncer in transaction mode is required**, not optional |
| Migrations | Alembic, every change reversible |
| Timezone | Everything `TIMESTAMPTZ`, stored UTC, rendered ISO-8601 |
| IDs | UUIDv7 — time-ordered, so index locality stays good |

With PgBouncer in transaction mode, **do not use server-side prepared statements** —
set `prepared_statement_cache_size=0` on the asyncpg driver or connections will fail
intermittently under load, which is a miserable bug to diagnose later.

---

## 4. Indexes that actually matter

Do not index everything. Index the hot paths.

```sql
-- the answer path, hit on every submission
CREATE INDEX ON attempts (child_id, skill_id, created_at DESC);
CREATE INDEX ON attempts (session_id, created_at);

-- session resume and expiry sweep
CREATE INDEX ON sessions (child_id, status);
CREATE INDEX ON sessions (status, expires_at);

-- ownership checks, on every child-scoped request
CREATE INDEX ON children (user_id) WHERE deleted_at IS NULL;

-- auth
CREATE INDEX ON refresh_tokens (user_id, expires_at);
CREATE UNIQUE INDEX ON refresh_tokens (token_hash);

-- plan lookup
CREATE UNIQUE INDEX ON daily_plans (child_id, plan_date);

-- analytics
CREATE INDEX ON events (name, created_at);
CREATE INDEX ON events (child_id, created_at);
```

---

## 5. Transaction rules

The single most important ordering rule in the whole system:

```
1. SELECT session FOR UPDATE          ← Postgres row lock; no distributed lock needed
2. validate step, check idempotency
3. evaluate deterministically (pure, in memory)
4. INSERT attempt
5. UPSERT skill_mastery
6. INSERT reward_ledger rows
7. advance current_index
8. COMMIT                              ← truth is now durable
9. call the AI                         ← outside the transaction, with a timeout
```

**Never call the AI, an HTTP service, or anything with a network timeout inside a
transaction.** A slow LLM must not hold a row lock.

`SELECT ... FOR UPDATE` on the session row serialises concurrent submissions for that
session, which is the only real concurrency this application has. That is why no
distributed locking is needed anywhere.

---

## 6. Acceptance criteria

- [ ] `mock_storage.py` and `mock_auth.py` are deleted; nothing imports them.
- [ ] `grep -rn "^[A-Z_]* = {}\|^[a-z_]* = \[\]" backend/app` finds no module-level mutable state.
- [ ] All 19 tables exist with the stated constraints, foreign keys, and indexes.
- [ ] `alembic upgrade head` then `alembic downgrade base` both succeed from clean.
- [ ] Restarting the API loses **nothing** — a test seeds a child, restarts the process, and reads identical state back.
- [ ] 20 concurrent identical answer submissions produce exactly **one** `attempts` row.
- [ ] A forced rollback mid-transaction leaves neither an attempt nor a mastery row — never one without the other.
- [ ] `SUM(reward_ledger)` reconciles exactly against a 500-attempt simulation.
- [ ] No `TIMESTAMP WITHOUT TIME ZONE` column exists anywhere.
- [ ] `children` has no full date-of-birth column.
- [ ] PgBouncer is configured, and asyncpg runs with `prepared_statement_cache_size=0`.
- [ ] `EXPLAIN ANALYZE` on the answer path, the progress read, and the ownership check shows index scans, not sequential scans, with 5,000 seeded attempts.

---

## 7. Prompt

> Read `docs/backend-architecture.md` §3 and §4.2, `docs/backend-audit.md`, and
> `docs/ops/OP-01-database.md`. Replace all in-memory backend state with PostgreSQL.
>
> Set up an async SQLAlchemy 2.x engine on asyncpg with `pool_size=10`, `max_overflow=5`,
> `pool_pre_ping=True`, and `prepared_statement_cache_size=0` (required because PgBouncer
> will run in transaction mode). Wire Alembic. Then create migrations for all 19 tables
> listed in OP-01 §2 — the 17 from the architecture doc plus `daily_plans` and
> `learner_profiles` — with every foreign key, unique constraint and index specified in §2
> and §4. Use `TIMESTAMPTZ` everywhere, UUIDv7 for ids, and store only `birth_year` and
> `birth_month` for children, never a full date of birth.
>
> Implement the repository layer so that **all** SQL lives in `db/repositories/` and no
> business logic does. Implement the answer transaction in the exact order given in §5:
> `SELECT ... FOR UPDATE` on the session row, validate, evaluate as a pure function, insert
> the attempt, upsert mastery, insert reward ledger rows, advance the index, commit — and
> only then make any external call. No network call may happen inside a transaction.
>
> Delete `backend/app/services/mock_storage.py` and `mock_auth.py` and every import of
> them. Remove all module-level mutable state.
>
> Prove it: `alembic upgrade head` and `downgrade base` both succeed from clean; a test
> that seeds a child, restarts the process and reads identical state back; a test firing 20
> concurrent identical submissions that asserts exactly one attempt row; a forced-rollback
> test showing the attempt and mastery row never diverge; a 500-attempt simulation whose
> `SUM(reward_ledger)` reconciles exactly; and `EXPLAIN ANALYZE` output for the answer path,
> progress read and ownership check showing index scans with 5,000 attempts seeded.
