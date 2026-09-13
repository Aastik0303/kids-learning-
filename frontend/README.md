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

## Session

The parent's bearer token, their account and the selected child are kept in
`localStorage` (`services/session.ts`), which is why a closed tab does not sign
anybody out: the lifetime is the server's - the signed JWT and the
`auth_sessions` row it names, thirty days by default - rather than the tab's.
The token is sent as `Authorization: Bearer`, it is revocable, and signing out
ends the row on the server as well as clearing it here.

Sign-in is either Google or an email and password; `components/auth/AuthForm.tsx`
offers both. Google's button is drawn by Google's own script and appears only
where the server reports a client id it can verify against
(`GET /auth/google/config`).

## Build

```bash
npm run build
```

The child UI uses large touch targets, short labels, and simple visual activity items. The parent progress page reads the attempt log, the frozen plans and the curriculum's own subject titles.
