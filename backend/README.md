# Backend

FastAPI service for the AI Nursery Learning Platform.

## Setup

```bash
python -m pip install -r requirements.txt
alembic upgrade head          # PostgreSQL only; a local SQLite file is created for you
python -m uvicorn app.main:app --port 8008
```

`DATABASE_URL` decides where the durable data goes. With PostgreSQL set, Alembic
owns the schema and the app never creates a table; with the setting empty, a
local `saksham.db` SQLite file is created from the models so a clean checkout
runs with no server at all. A bare `postgresql://` URL is normalised to psycopg
3, which is the driver `requirements.txt` pins.

Environment defaults are in `.env.example`. `LLM_PROVIDER=none` is the default and needs no API key.
To use Groq for the single guide agent, create `backend/.env` with `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and optionally `GROQ_MODEL`. The default Groq model is `openai/gpt-oss-20b`.

To use the configured ElevenLabs learning voice, add your API key. The voice ID is already set to `JBFqnCBsd6RMkjVDRZzb`; keep the key on the backend only.

```env
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
ELEVENLABS_MODEL=eleven_flash_v2_5
ELEVENLABS_MODEL_ID=eleven_flash_v2_5
ELEVENLABS_OUTPUT_FORMAT=mp3_22050_32
ELEVENLABS_OPTIMIZE_STREAMING_LATENCY=3
```

To persist the AI guide's learning memory, set `DATABASE_URL` to a PostgreSQL connection string. The backend creates the `learning_memories` table and stores one compact row per completed lesson: path, level, lesson title, objective, score, and completion time. Normal guide conversation is not written to PostgreSQL and remains limited to the current session.

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/child_ai
DATABASE_CONNECT_TIMEOUT=5
```

## The class, end to end

```
POST /conductor/{child_id}/open           -> ConductorDirective   (today's plan, opened for the child)
POST /conductor/sessions/{id}/input       -> ConductorDirective   (tap | voice | trace | idle | doubt | ready)
GET  /conductor/sessions/{id}             -> ConductorDirective   (refresh-safe; nothing moves)
POST /conductor/sessions/{id}/pause       -> ConductorDirective
```

One endpoint takes every kind of input, including silence: `next_input.on_timeout`
tells the client which event to report when the child does nothing, and the
server decides what that means. The directive carries the activity (without its
answer key), the scaffolding, the screen, the words to speak, and
`auto_advance_in_ms` for the turns where nothing is asked of the child - which is
what replaces the "next" button.

## Main Modules

- `api/`: FastAPI route modules.
- `schemas/`: Pydantic request and response models.
- `db/models.py`: the durable schema - identity, truth (attempts, mastery, lesson
  state), the daily plan, and the learning-to-teach tables.
- `db/repositories/`: every write the app makes. `truth.py` is the boundary that
  matters: it is written only by the deterministic evaluator and imports no
  agent and no model client.
- `conductor/`: the class state machine, the Branch Decision Engine, the
  frustration and idle watchers, and the scaffolding rules. Pure Python - it
  imports no service and no model client.
- `services/conductor_service.py`: the running class. Holds `lesson_states`,
  writes the attempt before anything is said about it, and asks the guide for
  the words afterwards.
- `policy/`: the learned teaching policy - the nine strategies, the discretised
  state, and the epsilon-greedy selector that starts from the hand-written ladder.
- `ai/llm/`: the only place anything reaches a language model, behind a timeout
  and a circuit breaker.
- `ai/planner/`: the Planner Agent, a LangGraph state graph
  (`gather -> propose -> validate -> freeze`). It orders the day and may do
  nothing else: the candidate topics are computed deterministically by
  `plan_service`, and an ordering that names anything outside them is thrown
  away with `daily_plans.source` left at `deterministic`.
- `services/auth_service.py`: parent accounts on `parents` / `auth_sessions`,
  with PBKDF2-stretched passwords, a per-account failure lockout
  (`auth_throttle`) and single-use expiring password resets
  (`password_resets`).
- `services/learning_memory_service.py`: what the guide remembers about finished
  lessons, now on the SQLAlchemy layer like everything else.
- `services/child_store.py`: the child's progress ledger, loaded and saved as one
  document.
- `services/teaching_policy_service.py`: the bridge the guide calls to choose a
  strategy and write the episode.
- `services/retention_service.py`: retention probes - the only thing that pays a
  policy reward, days after the lesson.
- `services/plan_service.py`: today's plan - which topics are legal today, and
  the frozen result read back with a cursor.
- `services/planner_runner.py`: the background sweep that runs the planner on a
  timer, so a plan exists before the child opens the app. `PLANNER_AUTO_RUN=0`
  turns it off.
- `services/curriculum_service.py`: reads local curriculum JSON.
- `services/learning_service.py`: deterministic learning workflow, feedback, stars, unlocks, and certificate triggers.
- `services/practice_service.py`: non-blocking practice sessions.
- `services/guide_agent_service.py`: single structured Little Learning Guide Agent for child-facing help.
- `services/history_service.py`: the attempt log, written to `attempts` and rolled up into `skill_mastery`.

## Known limits

Passwords are stretched with PBKDF2-HMAC-SHA256 at the OWASP round count and
sessions expire after 30 days, but there is still no rate limiting, no lockout
and no password reset. The safety filter is a small keyword and length check and
should become layered moderation before production. In-flight lesson and
practice sittings are kept in process memory: a restart mid-lesson restarts the
lesson, while everything it produced - the answers, the mastery they moved, the
stars, the unlock board - is already on disk.

`/learning` and `/practice` still carry the pre-conductor teaching loop and are
marked deprecated in the OpenAPI schema. They serve the shipped web and mobile
clients; they retire when those clients move to
`POST /conductor/sessions/{id}/input`. Both already grade with the same
evaluator and write the same attempt log, so the two paths cannot disagree about
whether an answer was right.

There is no mailer, so `POST /auth/password/forgot` returns the reset token in
the response outside production and logs it. Wire an email sender before
`ENV=production`.

## Tests

```bash
python -m pytest
```

Each test runs against its own SQLite database and never reaches the network -
`tests/conftest.py` pins `LLM_PROVIDER=none` for the suite. The tests cover auth,
child creation, topic access, wrong-answer feedback, unlocking, certificates,
practice, guide responses and safety validation, the durable repositories
(`test_durable_storage.py`), and the policy wiring end to end
(`test_policy_wiring.py`): that a teaching turn chooses a strategy and records
it, that a reward is paid only by a retention probe, and that nothing in the
evaluator or the truth layer can reach a model. `test_conductor.py` covers the
class itself: the six branch outcomes and their priority order, the watchers,
the scaffolding boundary, and a whole sitting driven end to end through
`/conductor` with no navigation and no "next" button.
