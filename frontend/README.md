# Frontend

Next.js App Router frontend for the AI Nursery Learning Platform prototype.

## Setup

```bash
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` in `.env.local` if needed.

## Routes

- `/login`, `/register`, `/onboarding`, `/child/select`
- `/home`
- `/adventure` — the child's class, as its subjects
- `/adventure/[subjectId]` — the topics in one subject
- `/adventure/[subjectId]/[topicId]` — one topic's lesson
- `/practice`, `/practice/[topic]`
- `/rewards`, `/certificate`, `/guide`, `/parent/progress`, `/parent/profile`

`/levels` and `/toddler` were the path-based prototype and are redirected to
`/adventure` in `next.config.js`.

## Curriculum

Every class, subject and topic name is served by the backend from
`backend/app/data/curriculum/manifest.json`. There are no curriculum strings in
this codebase — adding a subject or topic is a manifest edit and appears in the
UI with no frontend change.

Presentation rules (touch target, choices per screen, text density) also come
from the manifest, via the class's experience mode. `lib/experience.ts` applies
them; its only hardcoded numbers are a strict fallback for the moment before the
first response arrives.

## Prototype State

The frontend stores the demo auth token, user, and selected child in `sessionStorage`. This is deliberate for the prototype and must be replaced with secure session handling before production.

## Build

```bash
npm run build
```

The child UI uses large touch targets, short labels, and simple visual activity items. The parent progress page includes a dev-only seed button for the final demo flow.
