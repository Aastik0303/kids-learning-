# Backend

FastAPI prototype API for the AI Nursery Learning Platform.

## Setup

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --port 8088
```

Environment defaults are in `.env.example`. `LLM_PROVIDER=none` is the default and needs no API key.
To use Groq for the single guide agent, create `backend/.env` with `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and optionally `GROQ_MODEL`. The default Groq model is `llama-3.1-8b-instant`.

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
- `graph/`: LangGraph-compatible single guide workflow scaffold.

## Prototype Limits

Auth, sessions, and storage are not production security. Passwords are sha256-hashed only as a demo shortcut. State is in memory and can reset. The safety filter is a small keyword/length check and should become layered moderation before production.

## Tests

```bash
python -m pytest
```

The suite covers auth, child creation, stage access, wrong-answer feedback, stage unlocking, mixed final seeding, certificate unlock, practice, single guide responses, guide safety validation, and history storage.
