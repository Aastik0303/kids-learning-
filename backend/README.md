# Backend

FastAPI prototype API for the AI Nursery Learning Platform.

## Setup

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --port 8008
```

Environment defaults are in `.env.example`. `LLM_PROVIDER=none` is the default and needs no API key.
To use Groq for the single guide agent, create `backend/.env` with `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and optionally `GROQ_MODEL`. The default Groq model is `llama-3.1-8b-instant`.

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

## Main Modules

- `api/`: FastAPI route modules.
- `schemas/`: Pydantic request and response models.
- `services/mock_auth.py`: demo-only register/login/session logic.
- `services/mock_storage.py`: in-memory dictionaries for users, children, sessions, rewards, and activity attempts.
- `services/curriculum_service.py`: reads local curriculum JSON.
- `services/learning_service.py`: deterministic learning workflow, feedback, stars, unlocks, and certificate triggers.
- `services/practice_service.py`: non-blocking practice sessions.
- `services/guide_agent_service.py`: single structured Little Learning Guide Agent for child-facing help.
- `services/history_service.py`: in-memory activity attempt history for progress and recommendations.
- `services/learning_memory_service.py`: PostgreSQL-backed completed-lesson memory used by the AI guide.
- `graph/`: LangGraph-compatible single guide workflow scaffold.

## Prototype Limits

Auth, sessions, and storage are not production security. Passwords are sha256-hashed only as a demo shortcut. State is in memory and can reset. The safety filter is a small keyword/length check and should become layered moderation before production.

## Tests

```bash
python -m pytest
```

The suite covers auth, child creation, stage access, wrong-answer feedback, stage unlocking, mixed final seeding, certificate unlock, practice, single guide responses, guide safety validation, and history storage.
