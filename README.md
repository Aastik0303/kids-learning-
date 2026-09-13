# learn_kids

AI Nursery Learning Platform

AI-assisted nursery learning app for children ages 2-6, with a light parent layer. The child surface stays tiny: the AI Teacher's class, Adventure, Rewards, and Ask Guide.

## What is running

- Next.js App Router frontend with TypeScript and Tailwind CSS.
- FastAPI backend with Pydantic models for every request/response.
- PostgreSQL for parents, children, attempts, mastery, plans and the learned policy. Schema in `backend/app/db/models.py`, migrations in `backend/alembic/`.
- Parent sign-in two ways, both ending in the same session: **Google** (`POST /auth/google`, the ID token verified server-side against Google's keys and pinned to `GOOGLE_CLIENT_ID`) and an email address with a PBKDF2-stretched password. The bearer is an HS256 JWT naming an `auth_sessions` row, so signing out and resetting a password actually end the session. A child never has an account.
- Browser `localStorage` for the parent's session, with the server's own thirty-day lifetime.
- No paid API keys are required: the voice is Microsoft Edge's free neural voices and retrieval runs local sentence embeddings.
- Browser SpeechRecognition is the prototype speech-to-text source; no raw voice recording is stored or uploaded by default.
- Question-aware transcript normalization at `POST /speech/normalize`, including speech corrections such as `tree -> three -> 3`.
- Deterministic answer checking, scoring, stars, topic unlocking, and certificate eligibility.
- Single structured Little Learning Guide Agent at `POST /agent/guide`.
- Whitelisted visual explanation actions such as `highlight_sequence` for visible question objects.
- Keyword safety filter for generated/mock strings.
- Manifest-driven curriculum at `GET /curriculum`: the CBSE 2026-27 syllabus as four age classes.
- `POST /dev/seed/{child_id}` completes a class without playing it. It is a development fixture and is **not mounted at all** outside development.

The only personal data held is a parent's email address and name, and a child's first name and birth month. Consent is written by a parent tapping the control and by nothing else - never by any automation.

## Running the backend

With Docker, which is also what production runs:

```bash
docker compose up --build      # API on :8008, its own PostgreSQL on :5433
```

The migrations run on the way up - `backend/start.sh` is the same entrypoint
the deployed image uses - so a clean checkout becomes a working schema without
anybody running alembic by hand. The database is a volume of its own and does
not touch whatever `backend/.env` points at. `GROQ_API_KEY`, the SMTP
credentials and `GOOGLE_CLIENT_ID` are read from `backend/.env` if it is there.

Without Docker:

```bash
cd backend && alembic upgrade head && uvicorn app.main:app --port 8008
cd frontend && npm run dev      # :5000
```

## Target Users

- Parent or carer: registers, creates a child profile, updates age/learning mode, views progress, prints the certificate.
- Child: opens their class's subjects, answers activities, earns stars, practices introduced topics, unlocks rewards.

## Learning Structure

The curriculum is the CBSE 2026-27 syllabus, organised as four age classes:

| Class | Age | Mode | Subjects | Topics |
|---|---|---|---|---|
| Play Group | 2-3 | `early` | 3 | 58 |
| Nursery | 3-4 | `early` | 5 | 29 |
| LKG | 4-5 | `standard` | 5 | 23 |
| UKG | 5-6 | `standard` | 5 | 17 |

Class -> Subject -> Topic -> Activity -> Question. A child's class is derived on the
server from their birth month, asked once at onboarding. A parent may move a child to an
adjacent class; a child cannot change it.

Two presentation modes, not four: `early` uses 96px touch targets, three choices per screen
and no written words; `standard` uses 64px, four choices and short words. Both come from
the manifest, and the choice limit is enforced when activity content is loaded.

Within a subject, topics unlock in order. Subjects run in parallel, so a child is never
made to finish English before starting Maths. Finishing every playable topic in the class
unlocks the Little Learning Explorer Certificate.

`backend/app/data/curriculum/manifest.json` is the single source of truth, and it holds
taxonomy only. Activities are authored into
`backend/app/data/curriculum/activities/`, one file per class or subject. Nursery, LKG
and UKG, plus the Play Group curriculum, are authored (339 activities). See `backend/app/data/curriculum/README.md`.

## Architecture

Backend services are split by concern: auth, children, curriculum, learning, practice, history, certificate, safety, recommendation, speech normalization, and guide context. Deterministic services own correctness, scoring, stars, progress, rewards, unlocking, and certificate eligibility.

The Little Learning Guide Agent is the only AI-shaped workflow. The frontend sends route, screen, feature, semantic event, available actions, allowed targets, allowed visual targets, question context, and compact progress context to `POST /agent/guide`; the response is structured JSON for avatar speech, safe UI guidance, and safe visual actions. Visible question data is passed directly to the guide, so question explanation does not use RAG.

Normal correct answers use short static praise and deterministic progression. The AI is used only for explanation, guidance, targeted wrong-answer help, and safe UI/visual direction; it never calculates scores, awards stars, unlocks topics, or writes progress.

## Future Production Version

Replace prototype pieces with real auth, parent consent flows, Postgres or another persistent store, encrypted child data, secure session management, rate limiting, LLM monitoring, audit logs, persistent vector retrieval, and production certificate generation.

## Run Locally

Backend:

```bash
cd backend
python -m uvicorn app.main:app --port 8008
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5000`.

## Test

```bash
cd backend
python -m pytest
```

```bash
cd frontend
npm run build
```
