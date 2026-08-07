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
- `/levels`, `/levels/[pathId]`, `/levels/[pathId]/[stageId]`
- `/practice`, `/practice/[topic]`
- `/rewards`, `/certificate`, `/guide`, `/parent/progress`

## Prototype State

The frontend stores the demo auth token, user, and selected child in `sessionStorage`. This is deliberate for the prototype and must be replaced with secure session handling before production.

## Build

```bash
npm run build
```

The child UI uses large touch targets, short labels, and simple visual activity items. The parent progress page includes a dev-only seed button for the final demo flow.
