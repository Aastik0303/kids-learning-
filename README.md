# learn_kids

AI Nursery Learning Platform

Prototype AI-assisted nursery learning app for toddlers and children ages 3-5, with a light parent layer. The child surface stays tiny: age-aware entry, Continue Levels, Practice, Rewards, and Ask Guide.

## Current Prototype

- Next.js App Router frontend with TypeScript and Tailwind CSS.
- FastAPI backend with Pydantic models for every request/response.
- In-memory auth, child profiles, learning sessions, practice sessions, rewards, and certificates.
- Browser `sessionStorage` for demo session state.
- Mock-first content generation; no paid API keys are required.
- Browser SpeechRecognition is the prototype speech-to-text source; no raw voice recording is stored or uploaded by default.
- Question-aware transcript normalization at `POST /speech/normalize`, including speech corrections such as `tree -> three -> 3`.
- Deterministic answer checking, scoring, stars, path unlocking, mixed final unlocking, toddler progress, and certificate eligibility.
- Single structured Little Learning Guide Agent at `POST /agent/guide`.
- Whitelisted visual explanation actions such as `highlight_sequence` for visible question objects.
- Keyword safety filter for generated/mock strings.
- Dev-only `POST /dev/seed/{child_id}` route to unlock the mixed final demo.

Prototype shortcuts are intentional: state resets when the server/browser session resets, auth tokens are demo-only, and no real personal data should be entered.

## Target Users

- Parent or carer: registers, creates a child profile, updates age/learning mode, views progress, prints the certificate.
- Child: opens toddler mode or standard levels based on age, answers activities, earns stars, practices introduced topics, unlocks rewards.

## Learning Structure

Age under 3 opens Toddler Mode: voice-first, visual-first ABC, numbers, colours, and shapes mini lessons with large touch targets.

Age 3+ uses the standard core paths: Numbers, Alphabets, Colours, Shapes. Each has eight stages. Numbers is fully authored; Alphabets, Colours, and Shapes have real early stages plus runnable later-stage placeholders marked in the curriculum JSON for Phase 3 expansion.

Mixed Final Path unlocks only when all four core paths are completed. Completing it unlocks the Little Learning Explorer Certificate.

## Architecture

Backend services are split by concern: auth, children, curriculum, learning, toddler learning, practice, history, certificate, safety, recommendation, speech normalization, and guide context. Deterministic services own correctness, scoring, stars, progress, rewards, unlocking, and certificate eligibility.

The Little Learning Guide Agent is the only AI-shaped workflow. The frontend sends route, screen, feature, semantic event, available actions, allowed targets, allowed visual targets, question context, and compact progress context to `POST /agent/guide`; the response is structured JSON for avatar speech, safe UI guidance, and safe visual actions. Visible question data is passed directly to the guide, so question explanation does not use RAG.

Normal correct answers use short static praise and deterministic progression. The AI is used only for explanation, guidance, targeted wrong-answer help, and safe UI/visual direction; it never calculates scores, awards stars, unlocks levels, or writes progress.

## Future Production Version

Replace prototype pieces with real auth, parent consent flows, Postgres or another persistent store, encrypted child data, secure session management, rate limiting, LLM monitoring, audit logs, persistent vector retrieval, and production certificate generation.

## Run Locally

Backend:

```bash
cd backend
python -m uvicorn app.main:app --port 8088
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Test

```bash
cd backend
python -m pytest
```

```bash
cd frontend
npm run build
```
