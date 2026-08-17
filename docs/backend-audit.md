# Backend Audit & Baseline — Phase 0

**Repository:** `d:\testcase` (branch `aastik_test`, HEAD `00eef7e5`)
**Produced:** 2026-08-14
**Spec:** [backend-architecture.md](backend-architecture.md)
**Phase:** 0 — Audit & Baseline. **Zero application code was modified.**

---

## 0. How this audit was produced

| Section | Method |
|---|---|
| File inventory | `git ls-files backend` cross-checked against a filesystem walk; `wc -l` per file |
| Route inventory | **Live OpenAPI schema** — `app.openapi()` imported from `app.main`, not read from source |
| State inventory | Python `ast` walk of every module's top-level `Assign`/`AnnAssign` for mutable literals, plus a grep for `global` |
| Dependency map | `ast` walk of all `Import`/`ImportFrom` nodes, with an explicit cycle search (DFS colouring) |
| Mobile call sites | grep of `mobile/src` for quoted and template-literal paths, resolved against the live route table |
| Test inventory | `pytest` run plus `pytest-cov` line coverage (`pytest-cov` installed into the venv only; no project file changed) |

**Environment note:** the repo venv at `.venv` is **Python 3.14.0**. Compiled artifacts under
`__pycache__` exist for both `cpython-310` and `cpython-314`, so this tree has been run under at
least two interpreters. The spec targets **Python 3.12** (§2.3). See Risk R-11.

---

## 1. File inventory

69 files: 59 source/config files (58 tracked + `backend/.env`, gitignored) and 10 untracked log files.
`__pycache__/` and `.pytest_cache/` are excluded as build artifacts.

### 1.1 Application entry & config

| File | LOC | Purpose |
|---|---:|---|
| `backend/app/main.py` | 61 | FastAPI app object (module-level, not a factory); CORS; two exception handlers; inline `/health`; mounts 11 routers |
| `backend/app/config.py` | 40 | `pydantic-settings` `Settings` with 14 fields, all defaulted; `@lru_cache get_settings()` |
| `backend/app/__init__.py` | 1 | Package marker |
| `backend/app/api/__init__.py` | 1 | Package marker |
| `backend/app/schemas/__init__.py` | 1 | Package marker |
| `backend/app/services/__init__.py` | 1 | Package marker |

### 1.2 API routers (`backend/app/api/`)

| File | LOC | Purpose |
|---|---:|---|
| `auth.py` | 27 | `/auth` — register, login, logout, session |
| `children.py` | 26 | `/children` — create, list, get, patch |
| `companion.py` | 110 | `/companion` — session start/event/next-action; the fattest router, contains real branching logic |
| `dev.py` | 14 | `/dev/seed/{child_id}` — demo unlock shortcut, guarded to `env == "development"` |
| `guide.py` | 11 | `/agent/guide` — single AI guide entry point |
| `history.py` | 11 | `/history/{child_id}` — attempt history read |
| `learning.py` | 46 | `/learning` — paths, stages, start, answer, retry, continue, session read |
| `practice.py` | 21 | `/practice` — topics, start, answer |
| `progress.py` | 22 | `/progress` — progress, rewards, certificate |
| `speech.py` | 77 | `/speech` — deterministic transcript normalization + ElevenLabs TTS proxy; declares its own Pydantic models inline |
| `toddler.py` | 39 | `/toddler` — mode resolution, modules, curriculum, start, answer |

### 1.3 Services (`backend/app/services/`)

| File | LOC | Purpose |
|---|---:|---|
| `guide_agent_service.py` | 779 | Largest file in the backend. Prompt assembly, Groq HTTP call, response validation, action/target allowlists, and template fallbacks — all in one module |
| `learning_service.py` | 377 | Standard-mode session lifecycle: start, answer, retry, continue, stage completion, unlocking, demo seeding |
| `toddler_service.py` | 307 | Under-3 curriculum (hardcoded `TODDLER_CURRICULUM` dict) and its parallel session/answer flow |
| `answer_normalization_service.py` | 276 | Pure text normalization: number words, fillers, articles, colours, shapes, letter examples, speech corrections |
| `practice_service.py` | 219 | Practice-mode topics, session start, answer evaluation, attempt-reset rules |
| `answer_resolution_service.py` | 173 | Wraps normalization into a resolution verdict (`resolved` / `ambiguous` / `unresolved`) with confidence |
| `learning_memory_service.py` | 179 | Optional Postgres store for completed lessons (raw `psycopg`, hand-written SQL) with an in-process dict fallback |
| `avatar_service.py` | 139 | Builds avatar payloads (state, message, animation) from hardcoded message lists |
| `daily_recommendation_service.py` | 118 | Chooses the next path/stage and the welcome message; world ordering |
| `child_service.py` | 74 | Child profile CRUD over the in-memory store; default path progress; mixed-path unlock |
| `mock_auth.py` | 71 | **Prototype auth** — SHA-256 password digest, `demo-<uuid4>` opaque session tokens, no expiry |
| `content_generator.py` | 62 | `ContentGenerator` protocol with `Mock` and `LLM` implementations for hint/intro copy |
| `curriculum_service.py` | 56 | Loads `{path}_path.json` from disk behind `@lru_cache`; path metadata |
| `history_service.py` | 39 | Appends attempts to the in-memory list; reads them back per child |
| `guided_navigation_service.py` | 38 | Validates companion guidance actions against a target allowlist |
| `safety_service.py` | 37 | `safe_text()` — regex blocklist over generated copy |
| `certificate_service.py` | 11 | Certificate eligibility read (no rendering, no storage) |
| `mock_storage.py` | 10 | **8 module-level dicts/lists — the entire database.** See §3 |
| `errors.py` | 5 | `app_error()` → `HTTPException` with a `{code, message}` detail dict |

### 1.4 Schemas (`backend/app/schemas/`)

| File | LOC | Purpose |
|---|---:|---|
| `guide.py` | 145 | 8 models for the AI guide request/response contract, incl. UI and visual actions |
| `toddler.py` | 103 | 10 models for toddler mode, activities, levels, speech evaluation |
| `learning.py` | 67 | Activity, Stage, PathSummary, start/answer request + unified response |
| `companion.py` | 59 | Companion start/event requests, guidance payload, response |
| `child.py` | 43 | Child create/update requests, `PathProgress`, `ChildProfile` |
| `avatar.py` | 41 | `AvatarPayload` shared by learning, practice, toddler, companion, guide |
| `practice.py` | 36 | Practice topic, start/answer request + response |
| `auth.py` | 31 | Register/login/logout requests, `UserPublic`, auth + session responses |
| `history.py` | 22 | `ActivityAttempt`, `HistoryResponse` |
| `progress.py` | 22 | Progress, rewards, certificate responses |
| `common.py` | 10 | `ErrorBody` / `ErrorResponse` — **0% covered, and not referenced by any handler** |

### 1.5 Data (`backend/app/data/`)

| File | LOC | Purpose |
|---|---:|---|
| `alphabets_path.json` | 148 | Alphabets path stages — loaded by `curriculum_service` |
| `colours_path.json` | 148 | Colours path stages — loaded |
| `numbers_path.json` | 148 | Numbers path stages — loaded |
| `shapes_path.json` | 148 | Shapes path stages — loaded |
| `mixed_final_path.json` | 58 | Final mixed path stages — loaded |
| `avatar_messages.json` | 111 | **Dead data.** No code reads it; `avatar_service.py` uses hardcoded lists instead |
| `rewards.json` | 45 | **Dead data.** No code reads it; star/badge rules are hardcoded in the services |

### 1.6 Tests, deps, docs, artifacts

| File | LOC | Purpose |
|---|---:|---|
| `backend/tests/test_prototype_flow.py` | 768 | The entire test suite — 34 tests in one file |
| `backend/requirements.txt` | 8 | Unpinned except `psycopg`; no ruff, mypy, alembic, sqlalchemy, redis, or coverage |
| `backend/README.md` | 57 | Prototype run instructions |
| `backend/.env.example` | 16 | Documented env vars (tracked) |
| `backend/.env` | 12 | Real local env — **untracked and gitignored**, correctly |
| `backend/*.log` (10 files) | — | `backend-runtime.{err,out}`, `uvicorn.{err,out}`, `uvicorn-8001.{err,out}`, `uvicorn-8088.{err,out}`, `uvicorn-voice.{err,out}` — stray uvicorn capture, gitignored |

---

## 2. Route inventory (verified against the live OpenAPI schema)

**36 routes.** Extracted by importing `app.main:app` and calling `app.openapi()`.
**Every route reports `security: absent`** — the app declares no OpenAPI security scheme at all, so
"auth" below is what the handler actually enforces in code, not what the schema advertises.

Legend — **Auth:** `none` = no credential is read; `header` = `X-Demo-Session` header;
`body` = `session_token` field in the request body. **Own** = ownership is checked against the caller.

| # | Method | Path | Auth | Own | Mobile | Web | Notes |
|---:|---|---|---|---|---|---|---|
| 1 | POST | `/agent/guide` | none | — | ✅ | ✅ | Only LLM route |
| 2 | POST | `/auth/login` | none | — | ✅ | ✅ | No rate limit |
| 3 | POST | `/auth/logout` | body | — | ✅ | — | Pops the token from the dict |
| 4 | POST | `/auth/register` | none | — | ✅ | ✅ | No rate limit |
| 5 | GET | `/auth/session` | header (optional) | — | ✅ | — | Returns empty session if absent |
| 6 | GET | `/children` | **header** | **✅** | ✅ | ✅ | Filters by `user_id` |
| 7 | POST | `/children` | **body** | n/a | ✅ | ✅ | Token in body, not a header |
| 8 | GET | `/children/{child_id}` | **none** | **❌** | ✅ | — | **Any child profile readable by anyone.** See R-02 |
| 9 | PATCH | `/children/{child_id}` | **body** | **✅** | ✅ | ✅ | The only correctly-scoped mutation |
| 10 | POST | `/companion/next-action` | none | ❌ | — | — | **Orphaned** — no client calls it |
| 11 | POST | `/companion/session/event` | none | ❌ | — | — | **Orphaned** — no client calls it |
| 12 | POST | `/companion/session/start` | none | ❌ | — | ✅ | Web only |
| 13 | POST | `/dev/seed/{child_id}` | none | ❌ | ✅ | ✅ | Guarded by `env == "development"` → 403 |
| 14 | GET | `/health` | none | — | ✅ | — | Returns `{ok, mode}`; checks nothing |
| 15 | GET | `/history/{child_id}` | none | ❌ | ✅ | — | Exposes every attempt for any child id |
| 16 | POST | `/learning/answer` | none | ❌ | ✅ | ✅ | Scoring path |
| 17 | POST | `/learning/continue/{session_id}` | none | ❌ | ✅ | — | |
| 18 | GET | `/learning/paths` | none | — | ✅ | ✅ | Curriculum read |
| 19 | GET | `/learning/paths/{path_id}` | none | — | — | — | **Orphaned** — no client calls it |
| 20 | GET | `/learning/paths/{path_id}/stages` | none | — | ✅ | ✅ | |
| 21 | POST | `/learning/retry/{session_id}` | none | ❌ | ✅ | — | |
| 22 | GET | `/learning/session/{session_id}` | none | ❌ | ✅ | — | Resume read |
| 23 | POST | `/learning/start` | none | ❌ | ✅ | ✅ | |
| 24 | POST | `/practice/answer` | none | ❌ | ✅ | ✅ | Scoring path |
| 25 | POST | `/practice/start` | none | ❌ | ✅ | ✅ | |
| 26 | GET | `/practice/topics/{child_id}` | none | ❌ | ✅ | ✅ | |
| 27 | GET | `/progress/{child_id}` | none | ❌ | ✅ | ✅ | |
| 28 | GET | `/progress/{child_id}/certificate` | none | ❌ | ✅ | — | |
| 29 | GET | `/progress/{child_id}/rewards` | none | ❌ | ✅ | — | |
| 30 | POST | `/speech/normalize` | none | — | ✅ | ✅ | Pure function, no I/O |
| 31 | POST | `/speech/synthesize` | none | — | — | ✅ | **Unauthenticated paid TTS proxy.** See R-04 |
| 32 | POST | `/toddler/answer` | none | ❌ | ✅ | ✅ | Scoring path |
| 33 | GET | `/toddler/curriculum/{module}` | none | — | ✅ | — | |
| 34 | POST | `/toddler/mode` | none | — | ✅ | ✅ | |
| 35 | GET | `/toddler/modules` | none | — | ✅ | ✅ | |
| 36 | POST | `/toddler/start` | none | ❌ | ✅ | ✅ | |

**Summary:** 3 of 36 routes read a credential. 2 of 36 check ownership. 21 routes accept a
`child_id` or `session_id` and enforce nothing.

**Target-surface delta vs spec §6:** the spec defines ~30 routes under `/api/v1`. Nothing here is
versioned; `/companion/*`, `/toddler/*`, `/agent/guide`, `/dev/*` and `/speech/synthesize` have no
counterpart in the target surface, while `/auth/refresh`, `DELETE /children/{id}`, the
`/classes|/levels|/lessons` tree, `/recommendations/{child_id}`, `/doubts/*`, `/health/live`,
`/health/ready` and `/metrics` do not exist yet.

---

## 3. State inventory — module-level mutable objects

### 3.1 The in-memory database — `services/mock_storage.py`

Eight module-level containers hold **all** product state. This is the single largest obstacle to
the target architecture and a direct violation of spec §0.2 rule 3.

| Symbol | Line | Type | Holds |
|---|---:|---|---|
| `mock_users` | 3 | `dict[str, dict]` | Parent accounts, keyed by email; SHA-256 digest inline |
| `mock_sessions` | 4 | `dict[str, str]` | Session token → user id. No expiry, no rotation |
| `mock_child_profiles` | 5 | `dict[str, dict]` | Child profiles incl. progress, stars, unlocks |
| `mock_learning_sessions` | 6 | `dict[str, dict]` | Active standard-mode sessions |
| `mock_toddler_sessions` | 7 | `dict[str, dict]` | Active toddler-mode sessions |
| `mock_practice_sessions` | 8 | `dict[str, dict]` | Active practice sessions |
| `mock_certificates` | 9 | `dict[str, dict]` | Issued certificates |
| `mock_activity_attempts` | 10 | `list[dict]` | Every attempt ever recorded — unbounded growth |

**Consequences today:** all learning truth is lost on restart; two API replicas would disagree on
every value; `mock_activity_attempts` grows without bound; and id generation is
`f"user_{len(mock_users) + 101}"` / `f"child_{len(mock_child_profiles) + 101}"`, which is
**not concurrency-safe and collides after any deletion**.

### 3.2 Cross-request mutable state elsewhere

| Symbol | File:line | Type | Assessment |
|---|---|---|---|
| `_session_fallback` | `learning_memory_service.py:69` | `dict[str, LearningMemory]` | Per-process cache of the latest completed lesson; also the *only* store when `database_url` is empty. Replicas will diverge |
| `_schema_ready` | `learning_memory_service.py:70` | `bool` via `global` | One-shot DDL latch guarded by `_schema_lock` (`threading.Lock`) — correct within a process, per-process across replicas |
| `get_settings` | `config.py:38` | `@lru_cache` | Fine — immutable settings |
| `curriculum_service` loader | `curriculum_service.py:20` | `@lru_cache` | Fine — read-only curriculum, but has **no invalidation**, so a data-file edit requires a restart |

### 3.3 Module-level constants (not defects)

35 further module-level containers were found, all `UPPER_SNAKE` constants: feedback and hint
message lists (`learning_service`, `practice_service`, `guide_agent_service`, `avatar_service`,
`content_generator`), allowlists (`APPROVED_GUIDE_TARGETS`, `APPROVED_GUIDE_ACTIONS`,
`APPROVED_VISUAL_ACTIONS`, `BLOCKED_PATTERNS`), normalization tables (`NUMBER_WORDS`, `ARTICLES`,
`FILLERS`, `COLOURS`, `SHAPES`, `SPEECH_CORRECTIONS`, `LETTER_EXAMPLES`), and the hardcoded
`TODDLER_CURRICULUM`. A grep for in-place mutation of any `UPPER` name returned **zero hits**, so
these are effectively immutable and safe to port as-is.

---

## 4. Import dependency map

**No circular imports.** DFS over the full module graph found zero cycles, and there are **zero
deferred (in-function) imports**, so nothing is masking a cycle. The graph is a clean DAG:
`main → api → services → schemas`, with `config` and `errors` as leaves.

```
main ─┬─► api.{auth,children,companion,dev,guide,history,
      │        learning,practice,progress,speech,toddler}
      ├─► config
      └─► services.learning_memory_service        (lifespan DDL)
```

| Module | Depends on (`app.` stripped) |
|---|---|
| `api.auth` | `schemas.auth`, `services.mock_auth` |
| `api.children` | `schemas.child`, `services.child_service` |
| `api.companion` | `schemas.{avatar,companion,guide}`, `services.{child_service,daily_recommendation_service,errors,guide_agent_service,guided_navigation_service,learning_memory_service}` |
| `api.dev` | `config`, `services.{errors,learning_service}` |
| `api.guide` | `schemas.guide`, `services.guide_agent_service` |
| `api.history` | `schemas.history`, `services.history_service` |
| `api.learning` | `schemas.learning`, `services.{curriculum_service,learning_service}` |
| `api.practice` | `schemas.practice`, `services.practice_service` |
| `api.progress` | `schemas.progress`, `services.{certificate_service,child_service}` |
| `api.speech` | `config`, `services.answer_resolution_service` |
| `api.toddler` | `schemas.toddler`, `services.toddler_service` |
| `services.learning_service` | `config`, `schemas.{child,learning}`, `services.{answer_resolution_service,avatar_service,child_service,content_generator,curriculum_service,daily_recommendation_service,errors,history_service,learning_memory_service,mock_storage}` |
| `services.practice_service` | `schemas.practice`, `services.{answer_resolution_service,avatar_service,child_service,curriculum_service,errors,history_service,mock_storage}` |
| `services.toddler_service` | `schemas.{avatar,child,toddler}`, `services.{answer_normalization_service,child_service,errors,mock_storage}` |
| `services.guide_agent_service` | `config`, `schemas.{avatar,guide}`, `services.{answer_resolution_service,errors,safety_service}` |
| `services.child_service` | `schemas.child`, `services.{errors,mock_auth,mock_storage}` |
| `services.certificate_service` | `schemas.progress`, `services.{child_service,mock_storage}` |
| `services.daily_recommendation_service` | `schemas.child`, `services.curriculum_service` |
| `services.answer_resolution_service` | `services.answer_normalization_service` |
| `services.content_generator` | `schemas.learning`, `services.safety_service` |
| `services.curriculum_service` | `schemas.learning`, `services.errors` |
| `services.guided_navigation_service` | `schemas.companion`, `services.errors` |
| `services.history_service` | `schemas.history`, `services.mock_storage` |
| `services.learning_memory_service` | `config` |
| `services.mock_auth` | `schemas.auth`, `services.{errors,mock_storage}` |
| `services.avatar_service` | `schemas.avatar` |
| `services.answer_normalization_service` | *(none — pure)* |
| `services.safety_service` | *(none — pure)* |
| `services.errors` | *(none)* |

**Structural observations relevant to the target layering:**

1. **Services import Pydantic schemas and return them directly.** `learning_service.answer_learning()`
   returns a `LearningResponse`. Under spec §2.1 the service layer owns rules and the router owns
   schemas, so every service signature changes in the port.
2. **Six services import `mock_storage` directly.** There is no repository layer to swap; the
   storage dependency is spread across `child_service`, `certificate_service`, `history_service`,
   `learning_service`, `practice_service`, `toddler_service`, and `mock_auth`.
3. **`api/companion.py` carries real logic** (110 LOC, its own `_child_or_guest` helper and
   response assembly). It is the one router that clearly breaches the ≤15-line contract.
4. **No `db/`, `repositories/`, `evaluation/`, `storage/`, `workers/`, `core/`, or `ai/` package exists,**
   and there is no `alembic/`. The target tree in §2.2 is greenfield apart from `api/`, `schemas/`,
   and `services/`.

---

## 5. Reuse verdicts

Every one of the 69 files appears exactly once.

**Legend:** `KEEP` — usable essentially as-is · `PORT` — logic is sound, move it into the target
structure with changes · `REPLACE` — the target requires a different implementation ·
`DELETE` — no place in the target.

### 5.1 KEEP (9 files)

| File | Reason |
|---|---|
| `services/answer_normalization_service.py` | Pure, dependency-free, 276 LOC of hard-won child-speech normalization — exactly the deterministic core §4.1 wants |
| `services/safety_service.py` | Pure regex blocklist; slots straight into `ai/validate.py`'s safety rule |
| `app/data/numbers_path.json` | Real curriculum content; becomes seed input |
| `app/data/alphabets_path.json` | As above |
| `app/data/colours_path.json` | As above |
| `app/data/shapes_path.json` | As above |
| `app/data/mixed_final_path.json` | As above |
| `app/__init__.py` | Package marker |
| `app/schemas/__init__.py` | Package marker |

### 5.2 PORT (22 files)

| File | Reason |
|---|---|
| `services/answer_resolution_service.py` | Verdict logic is right; must expose the `Evaluator` protocol and stop returning a Pydantic model |
| `services/curriculum_service.py` | Same read shape, but source becomes Postgres + Redis instead of `lru_cache` over JSON |
| `services/child_service.py` | Rules are sound; storage and the ownership check both change |
| `services/learning_service.py` | The session lifecycle to preserve, but it must be split across `session_service` + `answer_service` and gain the §4.2 transaction |
| `services/practice_service.py` | Merges into the unified session engine via `sessions.mode = 'practice'` |
| `services/toddler_service.py` | Hardcoded `TODDLER_CURRICULUM` must become seeded rows; the flow logic ports |
| `services/daily_recommendation_service.py` | Becomes `recommendation_service` implementing the ordered R1–R7 rules |
| `services/avatar_service.py` | Becomes `ai/templates.py` — the deterministic fallback voice |
| `services/content_generator.py` | Provider protocol shape is right; becomes `ai/providers/` |
| `services/guided_navigation_service.py` | Target allowlist validation folds into `ai/validate.py` |
| `services/history_service.py` | Becomes the `attempts` repository |
| `services/certificate_service.py` | Eligibility rule ports; rendering moves to the ARQ worker |
| `services/guide_agent_service.py` | Highest-value port and the biggest job: split 779 LOC into `ai/{context,policy,orchestrator,validate,templates}.py` + `providers/groq.py` |
| `api/auth.py` | Same operations, plus refresh; routers get thin |
| `api/children.py` | Needs `owned_child`, soft delete, and 404-not-403 |
| `api/learning.py` | Reshapes to `/api/v1/learning/sessions/*` |
| `api/practice.py` | Reshapes to `/api/v1/practice/sessions/*` |
| `api/progress.py` | Splits into `/progress`, `/rewards`, `/certificates` |
| `api/toddler.py` | Folds into the curriculum/session surface once toddler content is seeded |
| `api/speech.py` | `/normalize` ports as the STT abstraction; `/synthesize` needs auth + rate limits |
| `api/guide.py` | Becomes `/api/v1/guide/respond` |
| `tests/test_prototype_flow.py` | 34 real behavioural assertions worth preserving, but must be split across `tests/{unit,integration,e2e}/` and given isolation |

### 5.3 REPLACE (10 files)

| File | Reason |
|---|---|
| `services/mock_storage.py` | The eight in-memory dicts become 17 Postgres tables |
| `services/mock_auth.py` | SHA-256 + non-expiring opaque tokens → Argon2id + JWT with refresh rotation |
| `services/learning_memory_service.py` | Hand-rolled `psycopg` DDL and string SQL → SQLAlchemy models + Alembic |
| `services/errors.py` | 5-line `app_error()` → the `AppError` hierarchy and §6.1 envelope |
| `app/config.py` | Every field defaults to empty; needs fail-fast production validation |
| `app/main.py` | Module-level `app` → app factory with lifespan, request-id middleware, structlog, metrics |
| `app/schemas/common.py` | Currently unreferenced and 0% covered; the real error envelope replaces it |
| `requirements.txt` | 8 unpinned deps → pinned `pyproject.toml` with SQLAlchemy, Alembic, Redis, ARQ, Argon2, structlog, ruff, mypy |
| `backend/README.md` | Prototype run instructions no longer describe the system |
| `backend/.env.example` | Must document the new required variables |

### 5.4 DELETE (28 files)

| File | Reason |
|---|---|
| `api/companion.py` | Overlaps `/guide` and `/recommendations`; no counterpart in the target surface, and 2 of its 3 routes are already orphaned |
| `api/dev.py` | Demo seeding shortcut; seeding belongs in `scripts/seed_curriculum.py` |
| `api/history.py` | Superseded by `GET /progress/{child_id}` |
| `schemas/companion.py` | Dies with the companion router |
| `schemas/history.py` | Dies with the history router |
| `schemas/auth.py` | Token-in-body shape is wrong for the target |
| `schemas/child.py` | Carries `session_token` in the body and a full `age`, not birth year/month |
| `schemas/guide.py` | Replaced by the §5.4 response contract |
| `schemas/learning.py` | Replaced by session/attempt schemas |
| `schemas/practice.py` | Replaced by the unified session schema |
| `schemas/progress.py` | Replaced by progress/rewards/certificate schemas |
| `schemas/toddler.py` | Toddler content becomes ordinary seeded curriculum |
| `schemas/avatar.py` | Avatar payload is not in the target `GuideResponse` |
| `app/data/rewards.json` | **Dead data** — no code path reads it |
| `app/data/avatar_messages.json` | **Dead data** — no code path reads it |
| `app/api/__init__.py` | Replaced by `api/v1/router.py` |
| `app/services/__init__.py` | Regenerated in the new tree |
| `backend/.env` | Local-only; must be recreated for the new variables (already gitignored) |
| `backend/backend-runtime.err.log` | Stray runtime capture |
| `backend/backend-runtime.out.log` | Stray runtime capture |
| `backend/uvicorn.err.log` | Stray runtime capture |
| `backend/uvicorn.out.log` | Stray runtime capture (empty) |
| `backend/uvicorn-8001.err.log` | Stray runtime capture |
| `backend/uvicorn-8001.out.log` | Stray runtime capture |
| `backend/uvicorn-8088.err.log` | Stray runtime capture |
| `backend/uvicorn-8088.out.log` | Stray runtime capture |
| `backend/uvicorn-voice.err.log` | Stray runtime capture |
| `backend/uvicorn-voice.out.log` | Stray runtime capture |

**Tally:** KEEP 9 · PORT 22 · REPLACE 10 · DELETE 28 = **69**.

---

## 6. Mobile call-site inventory

Base URL resolution: `mobile/src/config/env.ts` — Expo `hostUri` in dev, `10.0.2.2` on the Android
emulator, `EXPO_PUBLIC_API_BASE_URL` / `expoConfig.extra.apiBaseUrl` otherwise. **Default port 8008.**
Timeouts: 6 s general, 12 s for guide calls.

All 31 call sites resolve to a live route. **No orphaned mobile call sites.**

| # | Call site | Method | Path | Route |
|---:|---|---|---|---|
| 1 | `mobile/src/services/api/authApi.ts:7` | POST | `/auth/register` | ✅ 4 |
| 2 | `mobile/src/services/api/authApi.ts:11` | POST | `/auth/login` | ✅ 2 |
| 3 | `mobile/src/services/api/authApi.ts:15` | POST | `/auth/logout` | ✅ 3 |
| 4 | `mobile/src/services/api/authApi.ts:20` | GET | `/auth/session` | ✅ 5 |
| 5 | `mobile/src/services/api/childApi.ts:23` | POST | `/children` | ✅ 7 |
| 6 | `mobile/src/services/api/childApi.ts:34` | GET | `/children` | ✅ 6 |
| 7 | `mobile/src/services/api/childApi.ts:38` | GET | `/children/${childId}` | ✅ 8 |
| 8 | `mobile/src/services/api/childApi.ts:42` | PATCH | `/children/${childId}` | ✅ 9 |
| 9 | `mobile/src/services/api/client.ts:192` | GET | `/health` | ✅ 14 |
| 10 | `mobile/src/services/api/guideApi.ts:14` | POST | `/agent/guide` | ✅ 1 |
| 11 | `mobile/src/services/api/learningApi.ts:8` | GET | `/learning/paths` | ✅ 18 |
| 12 | `mobile/src/services/api/learningApi.ts:12` | GET | `/learning/paths/${pathId}/stages` | ✅ 20 |
| 13 | `mobile/src/services/api/learningApi.ts:16` | POST | `/learning/start` | ✅ 23 |
| 14 | `mobile/src/services/api/learningApi.ts:28` | POST | `/learning/answer` | ✅ 16 |
| 15 | `mobile/src/services/api/learningApi.ts:36` | POST | `/learning/retry/${sessionId}` | ✅ 21 |
| 16 | `mobile/src/services/api/learningApi.ts:41` | POST | `/learning/continue/${sessionId}` | ✅ 17 |
| 17 | `mobile/src/services/api/learningApi.ts:46` | GET | `/learning/session/${sessionId}` | ✅ 22 |
| 18 | `mobile/src/services/api/practiceApi.ts:12` | GET | `/practice/topics/${childId}` | ✅ 26 |
| 19 | `mobile/src/services/api/practiceApi.ts:16` | POST | `/practice/start` | ✅ 25 |
| 20 | `mobile/src/services/api/practiceApi.ts:23` | POST | `/practice/answer` | ✅ 24 |
| 21 | `mobile/src/services/api/progressApi.ts:12` | GET | `/progress/${childId}` | ✅ 27 |
| 22 | `mobile/src/services/api/progressApi.ts:16` | GET | `/progress/${childId}/rewards` | ✅ 29 |
| 23 | `mobile/src/services/api/progressApi.ts:24` | GET | `/progress/${childId}/certificate` | ✅ 28 |
| 24 | `mobile/src/services/api/progressApi.ts:28` | GET | `/history/${childId}` | ✅ 15 |
| 25 | `mobile/src/services/api/sessionApi.ts:17` | POST | `/dev/seed/${childId}` | ✅ 13 |
| 26 | `mobile/src/services/api/speechApi.ts:13` | POST | `/speech/normalize` | ✅ 30 |
| 27 | `mobile/src/services/api/toddlerApi.ts:17` | POST | `/toddler/mode` | ✅ 34 |
| 28 | `mobile/src/services/api/toddlerApi.ts:21` | GET | `/toddler/modules` | ✅ 35 |
| 29 | `mobile/src/services/api/toddlerApi.ts:25` | GET | `/toddler/curriculum/${module}` | ✅ 33 |
| 30 | `mobile/src/services/api/toddlerApi.ts:29` | POST | `/toddler/start` | ✅ 32 |
| 31 | `mobile/src/services/api/toddlerApi.ts:38` | POST | `/toddler/answer` | ✅ 31 |

**Routes with no mobile caller (5):** `/companion/next-action`, `/companion/session/event`,
`/companion/session/start` (web only), `/learning/paths/{path_id}`, `/speech/synthesize` (web only).
Of these, **three have no caller in either client** and are fully orphaned: `/companion/next-action`,
`/companion/session/event`, `/learning/paths/{path_id}`.

**One thing the mobile client already gets right:** the session token is persisted via
`expo-secure-store` (`mobile/src/services/storage/secureStore.ts`, used by
`mobile/src/store/authStore.ts:84,109`), not `AsyncStorage` — which satisfies spec §7.4 ahead of time.
`AsyncStorage` (`mobile/src/services/storage/kv.ts`) is used only for non-secret preferences.

---

## 7. Test inventory & real coverage

**34 tests, all passing, in a single 768-line file** (`backend/tests/test_prototype_flow.py`),
running in ~9 s. Measured line coverage: **80% (1,910 statements, 378 missed).**

### 7.1 What the tests actually cover

| Area | Tests | Depth |
|---|---:|---|
| AI guide contract & validation | 8 | Good — includes invalid-target and invalid-visual-target rejection |
| Toddler mode | 7 | Good — stars, retry, level unlock, activity swap after 4 wrong, tap preference |
| Speech normalization | 7 | **Strongest area** — letter examples, out-of-option numbers, irrelevant words, empty transcript |
| Learning flow | 5 | Hint → completion → unlock; locked stage and locked world blocking |
| Practice | 3 | Topics, answer, attempt reset |
| Companion | 2 | Welcome recommendation, memory-driven welcome |
| Auth & child | 2 | One happy-path register/login/create; age→mode resolution |
| Seed/certificate | 1 | Mixed path unlock → certificate |
| Attempt history | 1 | Attempt stored after evaluation |

### 7.2 Coverage by module (worst first)

| Module | Cover | Missed |
|---|---:|---:|
| `services/guide_agent_service.py` | 62% | 163 |
| `services/answer_normalization_service.py` | 63% | 47 |
| `api/speech.py` | 60% | 14 |
| `services/child_service.py` | 68% | 13 |
| `services/curriculum_service.py` | 72% | 8 |
| `services/daily_recommendation_service.py` | 78% | 11 |
| `api/learning.py` | 79% | 6 |
| `services/mock_auth.py` | 80% | 9 |
| `services/learning_memory_service.py` | 80% | 13 |
| `services/answer_resolution_service.py` | 83% | 16 |
| `services/learning_service.py` | 88% | 21 |
| `services/practice_service.py` | 90% | 12 |
| `services/toddler_service.py` | 91% | 11 |
| `schemas/common.py` | **0%** | 3 |
| *(all other modules)* | 86–100% | — |

### 7.3 What the tests do **not** cover — the gaps that matter

- **No cross-parent access test anywhere.** Nothing asserts that Parent A cannot read Parent B's
  child. This is the single most important missing test, and the reason R-02 went unnoticed.
- **No auth failure paths.** No wrong password, no missing token, no expired token, no logout-then-reuse.
- **No concurrency test.** No `asyncio.gather`, no double-submit, no idempotency.
- **No test isolation.** There is no fixture that clears `mock_storage` between tests; the 34 tests
  share and accumulate global state, so they are order-dependent by construction.
- **No error-envelope test.** The `{"error": {...}}` shape is never asserted.
- **No load or latency test**, and no Locust suite.
- **No privacy/logging test** of the kind spec §7.3 mandates.
- **No adversarial AI suite.** The spec's §5.7 pre-launch gate requires ≥100 red-team prompts;
  there are currently 3 validation-rejection tests.
- **Test tooling gap:** `pytest-cov`, `pytest-asyncio`, `ruff`, and `mypy` are not in
  `requirements.txt`; there is no `conftest.py`, no `pytest.ini`/`pyproject` config, and no CI workflow
  anywhere in the repo.

---

## 8. Risk list

Ordered by the spec's priority chain (§0.1): safety and privacy first.

| ID | Sev | Risk |
|---|---|---|
| **R-01** | **Critical** | **33 of 36 routes are unauthenticated.** Every session, progress, practice, toddler, history and certificate route accepts a `child_id` or `session_id` and performs no credential check whatsoever. Any client that can guess `child_102` reads and writes that child's learning record. Directly violates spec §0.2 rule 4. |
| **R-02** | **Critical** | **`GET /children/{child_id}` has no ownership check** (`child_service.get_child`, [child_service.py:50](../backend/app/services/child_service.py#L50)) — it returns any child profile to any caller, including the child's display name and age. `PATCH` on the same path *does* check ownership, so the omission looks accidental rather than deliberate. |
| **R-03** | **Critical** | **All learning truth is process-local and volatile.** The eight dicts in `mock_storage.py` lose every account, session, attempt and certificate on restart, and cannot be shared across replicas. Spec §1.3 requires 100% learning-truth durability. |
| **R-04** | **High** | **`POST /speech/synthesize` is an unauthenticated proxy to a paid ElevenLabs account** ([speech.py:40](../backend/app/api/speech.py#L40)), accepting up to 600 characters per call with no rate limit. Anyone who can reach the host can bill the project's TTS quota. |
| **R-05** | **High** | **Password hashing is a bare SHA-256 digest**, unsalted and uniterated ([mock_auth.py:12](../backend/app/services/mock_auth.py#L12)), and session tokens (`demo-<uuid4>`) never expire and are never rotated. The file is honestly labelled as prototype-only, but it is what the running app uses. |
| **R-06** | **High** | **The Groq call blocks the event loop.** `api/guide.py:10` is `async def` but calls the synchronous `guide()`, which reaches `httpx.post(...)` at [guide_agent_service.py:761](../backend/app/services/guide_agent_service.py#L761) with a 6 s timeout. Under concurrency this stalls the whole worker — it is also why an AI outage would degrade *every* endpoint, not just the guide, contradicting spec §1.3. |
| **R-07** | **High** | **Id generation is not concurrency-safe.** `f"user_{len(mock_users) + 101}"` and `f"child_{len(mock_child_profiles) + 101}"` collide under concurrent creation and reuse ids after any deletion. Sequential ids also make R-01/R-02 trivially enumerable. |
| **R-08** | **High** | **No test proves cross-parent isolation.** With 34 passing tests and 80% coverage, the suite still cannot catch R-02. Coverage here measures lines executed, not guarantees held. |
| **R-09** | **Medium** | **Raw child answers are persisted indefinitely.** `history_service.record_attempt` stores `child_answer` verbatim into an unbounded module-level list, with no retention policy. Spec §7.2 caps transcripts at 90 days. |
| **R-10** | **Medium** | **`app/schemas/common.py` defines the error envelope but nothing imports it.** `main.py` builds the `{"error": {...}}` shape inline instead, so the "shared" contract is decorative — and `main.py:39` uses a bare `print()` for unhandled exceptions rather than a logger. |
| **R-11** | **Medium** | **Interpreter drift.** The venv is Python 3.14.0 while `__pycache__` holds both `cpython-310` and `cpython-314` artifacts; the spec targets 3.12. Pick one and pin it before Phase 1. |
| **R-12** | **Medium** | **`requirements.txt` is unpinned** (7 of 8 entries have no version constraint) and omits every tool the spec's CI gate needs. There is no lockfile, no `pyproject.toml`, and no CI workflow in the repo at all. |
| **R-13** | **Medium** | **Curriculum has no invalidation path.** `curriculum_service` reads `{path}_path.json` behind `@lru_cache`, so editing curriculum data requires a process restart — the opposite of the Phase 3 goal that adding a lesson is a data change. |
| **R-14** | **Medium** | **`/companion/*` overlaps `/guide` and `/recommendations` and is half-dead.** Two of its three routes have no caller, but `api/companion.py` still holds 110 LOC of branching logic — the only router that materially breaches the ≤15-line contract. |
| **R-15** | **Low** | **Three fully orphaned routes** — `/companion/next-action`, `/companion/session/event`, `/learning/paths/{path_id}` — have no caller in either client. |
| **R-16** | **Low** | **Two dead data files.** `app/data/rewards.json` (45 LOC) and `app/data/avatar_messages.json` (111 LOC) are read by nothing; the corresponding rules and copy are hardcoded in the services. Anyone editing them to change behaviour will be silently ignored. |
| **R-17** | **Low** | **CORS allows credentials against a configured origin list** that defaults to `localhost:5000` — but the mobile client defaults to port **8008** ([env.ts](../mobile/src/config/env.ts)) and the web app to Next.js's 3000, so the committed default matches neither client. |
| **R-18** | **Low** | **10 stray uvicorn log files** are sitting in `backend/`. They are gitignored, so this is hygiene rather than exposure. |

### 8.1 Where the repo layout contradicts the architecture document

Recorded here rather than assumed away, per the Phase 0 prompt.

1. **The repo is not `Aastik0303/learn_kids` as the spec header states** — this is a local tree
   `d:\testcase` on branch `aastik_test`, whose remotes include a `prototype/main`. Confirm the spec
   is pointed at the right repository before Phase 1.
2. **`mobile/` is entirely untracked.** `git ls-files mobile` returns **0 files**. The spec names the
   React Native client as in-scope (§7.4) and this audit's §6 inventories 31 of its call sites, but
   none of that code is in version control. **This should be committed before any phase depends on it** —
   otherwise the call-site inventory describes code that could vanish without a trace.
3. **There are two frontends, not one.** The spec assumes a single React Native client, but the repo
   also has a tracked Next.js app in `frontend/` that is the *only* consumer of `/companion/session/start`
   and `/speech/synthesize`. Deleting `api/companion.py` per §5.4 breaks the web app. The spec does not
   say whether `frontend/` is being retired — **this needs an explicit decision before Phase 4.**
4. **The spec's §2.2 target tree assumes `backend/app/api/v1/`**, but the current tree has no
   versioning at all. Spec §6 permits `/api/v0` adapters for one release; if both clients are to keep
   working through the migration, those adapters are mandatory, not optional.
5. **`CLAUDE.md` says "no real database"** while the spec's Phase 1 requires Postgres, Alembic and
   Docker Compose. `learning_memory_service.py` already breaches the project instruction with an
   optional Postgres path. The project instructions need updating in the same commit that starts
   Phase 1, or the two documents will keep contradicting each other.

### 8.2 What the prototype already gets right

Worth stating, because the port should not regress any of it:

- **Correctness is already deterministic.** `resolved_answers_match()` decides every `is_correct`
  value; the Groq call only produces teaching copy. Spec §0.2 rule 1 is already honoured.
- **The AI response is already validated** against action and target allowlists
  (`APPROVED_GUIDE_TARGETS`, `APPROVED_GUIDE_ACTIONS`, `APPROVED_VISUAL_ACTIONS`) with a template
  fallback on every failure path — the shape §5.5 asks for is present, if not yet complete.
- **The mobile client already stores its session token in the Keychain/Keystore**, satisfying §7.4.
- **`/dev/seed` is environment-guarded** and returns 403 outside development.
- **`backend/.env` is correctly gitignored**; only `.env.example` is tracked.
- **No circular imports and no deferred imports** — the module graph is a clean DAG, which makes the
  restructuring in Phases 1–4 considerably cheaper than it could have been.

---

## 9. Phase 0 acceptance

| Criterion | Status |
|---|---|
| Every backend file appears exactly once with a verdict | ✅ 69 files — KEEP 9, PORT 22, REPLACE 10, DELETE 28 |
| Every route in the running app appears in the route inventory, verified against the live OpenAPI schema | ✅ 36 routes, extracted via `app.openapi()` |
| Every mobile call site is mapped to a route, or flagged as orphaned | ✅ 31 call sites, all mapped; 0 orphaned mobile calls; 3 orphaned *routes* flagged |
| Zero code files modified | ✅ `git status` shows only the new untracked `docs/` |

**Gate:** this audit must be read by a human before Phase 1 begins. Two items need an explicit
decision, not just a read: **the fate of `frontend/`** (§8.1 item 3) and **committing `mobile/` to
version control** (§8.1 item 2).
