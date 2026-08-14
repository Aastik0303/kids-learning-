# Learn Kids — Frontend Production Specification (Next.js Web)

**Target:** `frontend/` — Next.js 16.3 · React 19.2 · App Router · Tailwind 3.4 · TypeScript 5.5
**Companion to:** `docs/backend-architecture.md` (the `/api/v1` production backend)
**Scope:** migrate the web client from the prototype backend to the production backend, and
remove every place the client currently decides something the server owns.
**Version:** 1.0 · 2026-08-13
**Out of scope:** `mobile/` (Expo RN app — separate track)

---

## 0. Read This First

### 0.1 Priority order (identical to the backend, deliberately)

```
correctness → child safety & privacy → data integrity → reliability
→ maintainability → scalability → AI quality → optimization
```

When a UX improvement conflicts with correctness, correctness wins. A snappier screen
that shows a star the server did not award is a **bug**, not a feature.

### 0.2 The five rules that must never be broken

1. **The client never decides correctness.** No answer checking, no scoring, no star
   arithmetic, no unlock logic in browser code. Ever.
2. **No silent fallback to local state.** A failed request shows a friendly retry — it
   does **not** quietly substitute mock data. (This is the single biggest change; see §1.)
3. **The access token never touches `localStorage` or `sessionStorage`.**
4. **Every mutating request carries an `Idempotency-Key`.** Retries must not double-count.
5. **Model output never controls the DOM directly.** It passes the client validator and
   the live target registry, or it degrades to static copy.

### 0.3 What is actually wrong today

This is not a greenfield build. Grounded in the current `frontend/` source:

| Problem | Where | Why it's serious |
|---|---|---|
| **Client-side answer evaluation** | `services/learning.ts` → `answerLearning()` `.catch()` block | Normalizes the answer, compares it to `activity.correct_answer`, computes `isCorrect`, awards `starsEarned`, and writes `path_progress` / `certificate_unlocked` into `sessionStorage`. The client is grading the child. |
| **21 silent fallbacks in `services/`** (plus 4 more in `app/` and `components/`) | `learning.ts` ×4, `child.ts` ×4, `toddler.ts` ×4, `practice.ts` ×3, `auth.ts` ×2, `speech.ts` ×2, `companion.ts` ×1, `guide.ts` ×1 — then `app/certificate`, `app/levels`, `AIAvatar`, `ToddlerLesson` | Every backend failure is invisible. A totally down API still "works", so bugs never surface and the child's real progress silently diverges. |
| **Rewards and certificates never call the backend at all** | `app/rewards/page.tsx` reads `getOrCreateGuestChild()`; stars come from `child.stars` in `sessionStorage` | The entire reward surface is client state. The backend's `rewards` and `certificates` endpoints exist and are simply never called. |
| **Raw `fetch` outside the API boundary** | `services/speech.ts:140` calls `/speech/synthesize` directly; `AIAvatar.tsx:45` HEAD-probes a Rive asset | Bypasses timeout, error parsing, and every future auth header. |
| **Fake auth on failure** | `services/auth.ts` | A failed login returns `session_token: "local-session-<timestamp>"` and a fabricated user. Login cannot fail. |
| **Token in `sessionStorage`** | `services/session.ts` | XSS-readable. No refresh token, no rotation, no expiry handling. |
| **No `Authorization` header at all** | `services/api.ts` | The client holds a token it never actually sends. |
| **Client-side curriculum mirror** | `data/prototype.ts` | Duplicates content that will become server data. Two sources of truth. |
| **20 prototype routes, none versioned** | all of `services/` | Every one moves under `/api/v1`. Several disappear entirely. |
| **No retry, no request id, no error codes** | `services/api.ts` (30 lines) | Thrown errors are bare `Error(message)`. Nothing correlates to a backend `request_id`. |
| **Hardcoded timeouts by path prefix** | `services/api.ts` | `path.startsWith("/agent/") ? 8000 : 4500` — breaks the moment routes are renamed. |
| **No hand-raise / doubt UI** | — | The backend will expose `/doubts/*`; the web client has no equivalent (the mobile app does). |

**The `.catch()` fallbacks are not resilience.** Resilience is retrying, queueing, and
telling the user. Substituting locally-computed results for server truth is data
corruption with a friendly face. All 21 are deleted in Phase 1.

### 0.4 Deliberately NOT building

| Not building | Revisit when |
|---|---|
| Redux / Zustand global store | React Query + `useContext` stops being enough — likely never at this size |
| Server Components for the child flow | Never. It's a stateful, voice-driven, session-bound UI; RSC buys nothing. |
| SSR for authenticated pages | Never — no SEO value, and it complicates token handling |
| Offline-first / write queue | The child flow requires server truth per answer. Show an honest offline state instead. |
| PWA / service worker | Install rate justifies it, or a parent asks for offline |
| Storybook | Component count exceeds ~60 |
| E2E on every PR | Suite exceeds 5 min — then move it to nightly + pre-release |
| i18n framework | A second locale is actually committed to |

### 0.5 The one backend change this spec requires

The backend spec (§7.4) assumes a React Native client storing the refresh token in
Keychain/Keystore. A browser has no such store. Therefore:

> **Backend addition needed:** `POST /api/v1/auth/login` and `/refresh` must, when called
> with `X-Client: web`, set the refresh token as an **`HttpOnly; Secure; SameSite=Lax;
> Path=/api/v1/auth`** cookie instead of returning it in the JSON body, and `/refresh`
> must read it from that cookie. The access token stays in the JSON body (held in memory
> only). CSRF is covered by `SameSite=Lax` plus requiring a JSON content type on the
> refresh call.

This is additive and does not change the mobile contract. **Raise it before Phase 2 —
do not let an agent work around it by putting the refresh token in `localStorage`.**

---

## 1. Non-Functional Requirements

The current frontend has none. These are measurable and gate Phase 8.

### 1.1 Core Web Vitals (mid-tier Android, throttled 4G)

| Metric | Target | Hard fail |
|---|---|---|
| LCP (child home) | ≤ 2.0 s | > 2.5 s |
| INP (tap an answer) | ≤ 150 ms | > 200 ms |
| CLS | ≤ 0.05 | > 0.1 |
| TTFB | ≤ 600 ms | > 800 ms |

### 1.2 Product-specific latency

| Interaction | Target | Notes |
|---|---|---|
| Tap answer → visible feedback | ≤ 100 ms | Local acknowledgement only (see §3.3) — never a correctness claim |
| Answer submit → server verdict rendered | ≤ 400 ms p95 | Backend budget is 150 ms p95; the rest is network + render |
| Session start → first activity on screen | ≤ 1.2 s | |
| Guide response rendered | ≤ 3.0 s p95 | Show a thinking state after 400 ms, never a spinner-of-death |
| Mic tap → listening indicator | ≤ 100 ms | Perceived responsiveness matters more than actual STT start |

### 1.3 Bundle budgets

| Budget | Limit |
|---|---|
| First-load JS (child home route) | ≤ 180 KB gzipped |
| First-load JS (any route) | ≤ 250 KB gzipped |
| Largest single route chunk | ≤ 90 KB gzipped |
| Total image weight per route | ≤ 400 KB |
| Video (`learning-adventure-theme.mp4`) | Lazy, never in the critical path |

Enforced in CI with `next build` output parsing; a regression fails the build.

### 1.4 Accessibility — WCAG 2.2 AA, plus kid-specific rules

| Rule | Requirement |
|---|---|
| Touch targets | **≥ 64 × 64 px** for any child-facing control (WCAG's 24 px is nowhere near enough for a 3-year-old) |
| Spacing between targets | ≥ 12 px, so a mis-tap doesn't select the neighbour |
| Contrast | ≥ 4.5:1 body, ≥ 3:1 large text and UI components |
| Motion | Every animation respects `prefers-reduced-motion`; nothing flashes >3 Hz |
| No time pressure | No countdowns, no auto-advance on the child surface |
| Audio | Never autoplay speech without an explicit child action; always a visible mute |
| Focus | Visible focus ring on every interactive element; full keyboard path through the parent surface |
| Text | No child-facing copy above ~grade-1 reading level; icons paired with words |
| Errors | Child-facing errors are gentle and actionable, never technical (existing `childMessage` pattern is right — keep it) |

### 1.5 Reliability

- **Zero** silent fallbacks to local state (`.catch(() => mock)` count must be **0**, CI-enforced).
- Backend fully down → every screen shows an honest retry state; no fabricated progress.
- A dropped answer request, retried, produces **one** attempt server-side (idempotency).
- Refreshing the browser mid-session resumes at the exact server-recorded step.

---

## 2. Architecture

### 2.1 Layers

```
app/**            App Router pages — layout, routing, suspense boundaries only
  └── features/   feature UI (learning, practice, rewards, parent, guide)
        └── hooks/        React Query hooks — the ONLY place server state is read
              └── services/api/   typed endpoint functions
                    └── lib/apiClient.ts   the single fetch boundary
```

**Contract:**

- **Nothing outside `lib/apiClient.ts` calls `fetch`.** CI-enforced by lint rule.
- **Nothing outside `hooks/` reads server state.** Components take props.
- **No component computes correctness, score, stars, or unlocks.** They render what the
  server returned.
- `services/api/*` functions are thin: build path, call client, return typed response.

### 2.2 Target structure

```
frontend/
├── app/                        # routes only — thin
│   ├── (child)/                # child surface, own layout + guide dock
│   ├── (parent)/               # parent surface, own layout + gate
│   ├── (auth)/
│   └── layout.tsx  providers.tsx
├── features/
│   ├── auth/  children/  curriculum/  learning/  practice/
│   ├── progress/  rewards/  certificates/  guide/  doubts/
│   └── <feature>/{components,hooks,copy.ts}
├── lib/
│   ├── apiClient.ts            # THE fetch boundary: auth, refresh, retry, idempotency
│   ├── tokenStore.ts           # access token, in memory only
│   ├── idempotency.ts
│   ├── errors.ts               # ApiError + child-safe copy mapping
│   └── queryClient.ts
├── services/api/               # one file per backend resource group
├── guide/
│   ├── TargetRegistry.tsx      # live registry of mounted, guide-addressable targets
│   ├── validateGuideResponse.ts# client-side defence in depth
│   ├── ActionExecutor.tsx      # the only place a validated action touches the UI
│   └── templates.ts            # static fallbacks
├── components/                 # presentational, no data fetching
├── types/                      # mirrors backend schemas 1:1
└── e2e/                        # Playwright
```

### 2.3 Stack additions

| Concern | Choice | Rationale |
|---|---|---|
| Server state | **`@tanstack/react-query` v5** | Replaces 21 hand-rolled `.catch()` fallbacks with real caching, retry, and invalidation. Same library the mobile app already uses — one mental model across clients. |
| Forms | `react-hook-form` + `zod` | Auth and parent forms only |
| Runtime validation | `zod` | Guide responses and any untrusted payload |
| E2E | Playwright | |
| Component tests | Vitest + Testing Library | |
| A11y CI | `@axe-core/playwright` | |
| Bundle CI | `next build` output assertion | |

Nothing else. No state library, no UI kit — Tailwind and the existing components stay.

---

## 3. Key Design Decisions

### 3.1 Authentication

```
Access token   → React memory (module-scope var + context). Lost on refresh, by design.
Refresh token  → HttpOnly Secure SameSite=Lax cookie, scoped to /api/v1/auth (see §0.5)
On app load    → call /auth/refresh once; cookie present → silently restored
On 401         → single-flight refresh, replay the original request once
On refresh 401 → clear everything, route to login, show "please sign in again"
```

**Single-flight is mandatory.** Ten queries hitting a stale token must trigger **one**
refresh, not ten — ten would trip the backend's rotation-reuse detection and revoke the
whole token family, logging the parent out for what was actually correct behaviour.

`services/session.ts` is deleted. All of it.

### 3.2 Parental consent (new — DPDP)

The backend blocks child creation without an active `consent_records` row. The web client
needs a consent step that did not exist before:

- Shown once, before the first child profile is created.
- Plain-language explanation of what is collected (learning answers, progress) and what
  is **not** (audio, location, contacts).
- Explicit affirmative action — a checkbox plus a button, never a pre-ticked box or an
  implied consent-by-continuing.
- Captures the policy version and posts to the backend's consent endpoint.
- Parent-visible record afterwards, with a withdrawal path in parent settings.
- **Never behind the child surface.** Consent lives behind the parent gate.

### 3.3 Optimistic UI without lying

The child must feel instant response. The client must not claim correctness.

**Allowed immediately on tap (local, no server):** the tapped option visually depresses;
a soft tap sound; a neutral "thinking" avatar state; the mic indicator changes.

**Never before the server responds:** correct/incorrect styling, stars, score changes,
progress bar movement, celebration animation, unlock reveal, "next" advancement.

If the verdict takes >400 ms, show the avatar thinking — a designed waiting state, not a
spinner. The child sees continuity; the truth still comes from the server.

### 3.4 The guide safety boundary

The existing `GUIDE_TARGETS` map in `services/guide.ts` is the right idea and becomes a
**live** registry: a target is addressable only while its component is actually mounted.

```
Screen registers mounted targets
   → request includes ui.allowed_actions + ui.allowed_targets  (backend validates against these)
   → response → zod schema → action allowlist → live target check → ActionExecutor → UI
   → any failure → static template, logged, never thrown
```

Client validation is **defence in depth**, not a substitute for the backend's — both run.
A target the backend approved but which has since unmounted is still dropped client-side.

### 3.5 Error handling

Every error maps to a `code` from the backend envelope and renders child-safe copy. Keep
the existing `childMessage` idea from the mobile client — it's the correct pattern.

| Situation | Child surface | Parent surface |
|---|---|---|
| Offline | "I cannot hear the internet right now. Let us try again!" + retry | Explicit offline banner |
| 5xx | "Something went wrong. Let us try again!" | Error code + `request_id`, copyable |
| 401 after refresh fails | "Please ask a grown-up to help you sign in." | Redirect to login |
| 429 | "Let us take a little break and try again soon." + honour `Retry-After` | Rate-limit notice |
| 404 on a child resource | "I could not find that. Let us go back home." | 404 page |
| Guide unavailable | Static encouragement — **the child must never learn the AI is down** | — |

Always surface `request_id` on the parent surface. It is the only way to trace a real
report back to a backend log.

---

## 4. API Migration Map

Every route the frontend calls today, and what it becomes. Nothing is left ambiguous.

### 4.1 Direct moves

| Today | Production |
|---|---|
| `POST /auth/register` | `POST /api/v1/auth/register` |
| `POST /auth/login` | `POST /api/v1/auth/login` |
| `POST /children` | `POST /api/v1/children` |
| `PATCH /children/{id}` | `PATCH /api/v1/children/{id}` |
| `GET /progress/{childId}` | `GET /api/v1/progress/{child_id}` |
| `POST /agent/guide` | `POST /api/v1/guide/respond` |
| `POST /speech/normalize` | `POST /api/v1/speech/transcribe` |

### 4.2 Reshaped

| Today | Production | Change |
|---|---|---|
| `GET /learning/paths` | `GET /api/v1/classes` | "Path" → "class" |
| `GET /learning/paths/{id}/stages` | `GET /api/v1/classes/{id}/levels` → `GET /api/v1/levels/{id}/lessons` | Stage splits into level + lesson |
| `POST /learning/start` | `POST /api/v1/learning/sessions` | Returns a server-frozen plan |
| `POST /learning/answer` | `POST /api/v1/learning/sessions/{id}/answer` | Session id in the path; requires `Idempotency-Key` |
| `POST /practice/start` | `POST /api/v1/practice/sessions` | |
| `POST /practice/answer` | `POST /api/v1/practice/sessions/{id}/answer` | |
| `GET /practice/topics/{childId}` | `GET /api/v1/recommendations/{child_id}` | Now returns `{recommendation, reason}` |

### 4.3 New (no current equivalent)

| Endpoint | Frontend work |
|---|---|
| `POST /api/v1/auth/refresh` | Single-flight refresh in `apiClient` |
| `POST /api/v1/auth/logout` | Real logout, clears the cookie |
| `GET /api/v1/children` | List children (currently only local state) |
| `DELETE /api/v1/children/{id}` | Parent-facing delete + export |
| `GET /api/v1/learning/sessions/{id}` | **Resume** — replaces all client session reconstruction |
| `POST /api/v1/learning/sessions/{id}/complete` | Explicit completion |
| `POST /api/v1/doubts` · `/{id}/message` · `/{id}/resolve` | **Hand-raise UI — entirely new on web** |
| `GET /api/v1/rewards/{child_id}` | **Rewards are client state today** (`app/rewards/page.tsx` reads `sessionStorage`). The whole surface becomes server-backed. |
| `GET /api/v1/certificates/{child_id}` | Same — `certificate_unlocked` is a client boolean today |
| Consent endpoint | Consent screen (§3.2) |

### 4.4 Deleted

| Today | Why |
|---|---|
| `POST /companion/session/start` | Folded into the guide orchestrator |
| `GET /toddler/modules` · `POST /toddler/start` · `/toddler/answer` · `/toddler/mode` | Curriculum is data-driven now. Toddler is an **age band + activity types**, not a parallel API. One session engine serves both. |
| `POST /dev/seed/{childId}` | Dev-only, never in production |
| `POST /speech/synthesize` | TTS is client-side (`speechSynthesis`); hosted voice is a later flag |

### 4.5 The toddler consolidation

Today `toddler/` is a parallel stack: its own API, own components (`ToddlerExperience`,
`ToddlerHome`, `ToddlerLesson`), own guide (`toddlerGuide.ts`), own voice
(`toddlerVoice.ts`). The production backend has **one** session engine; toddler content
is curriculum data with an age band and simpler activity types.

So the frontend collapses to one renderer with a **presentation mode**:

```
resolveExperienceMode(child.age_band) → "toddler" | "standard"
   → same ActivityRenderer, same session hooks, same guide
   → mode changes: type scale, target size, copy length, whether text appears at all
```

Delete `toddlerGuide.ts` and `toddlerVoice.ts`. Keep the *visual* toddler treatment as
props on shared components. This is the single largest simplification available and it
tracks the backend's own consolidation.

### 4.6 Guide contract change

The response shape changes materially:

```ts
// Today
{ message, strategy, avatar:{state,animationEffect},
  ui_action:{type,target}, visual_action:{type,targets}, next_expected_event }

// Production (backend §5.4)
{ say: string,                    // ≤ 220 chars
  strategy: "hint"|"example"|"story"|"simplify"|"prerequisite"|"celebrate",
  actions: [{ type, target }],    // array, not one action
  listen_after: boolean }
```

Action types are renamed and closed:
`none · highlight · show_hint · repeat_instruction · start_listening · play_animation ·
celebrate · navigate_safe · wait_for_child`

Note `highlight_sequence` → `highlight` (repeated entries in `actions[]` give the
sequence), and `open_safe_route` → `navigate_safe`. Avatar state is **derived
client-side from `strategy`**, not sent by the model — one less thing the model controls.

---

## 5. Execution Phases

Nine phases, each **paired to a backend phase**. A frontend phase may not start until its
paired backend gate has passed — otherwise the client is coded against an API that does
not exist yet.

| FE Phase | Requires backend | Theme |
|---|---|---|
| 0 | BE Phase 0 | Frontend audit |
| 1 | **BE Phase 1 gate** | API client, delete all fallbacks |
| 2 | **BE Phase 2 gate** | Real auth + consent |
| 3 | **BE Phase 3 gate** | Curriculum from server |
| 4 | **BE Phase 4 gate** | Server-authoritative sessions |
| 5 | **BE Phase 5 gate** | Mastery, recommendations, rewards |
| 6 | **BE Phase 6 gate** | Guide + doubts |
| 7 | **BE Phase 7 gate** | Speech, tracing, certificates |
| 8 | **BE Phase 8 gate** | Hardening, a11y, cutover |

---

### FE Phase 0 — Frontend Audit

**Goal:** the frontend equivalent of the backend baseline.

**Deliverable:** `docs/frontend-audit.md`

1. Route inventory: every `app/**/page.tsx`, who reaches it, and whether it is child,
   parent, or auth surface.
2. Every `fetch`/`api()` call site with file:line and the backend route it hits.
3. **Every `.catch()` fallback**, with exactly what fake data it substitutes.
4. **Every place the client computes correctness, score, stars, progress, or unlocks.**
5. Every `sessionStorage` / `localStorage` read and write.
6. Component inventory with a KEEP / ADAPT / REPLACE / DELETE verdict each.
7. `data/prototype.ts` usage map — every import of client-side curriculum.
8. Current bundle size per route (`next build` output) as the baseline for §1.3.
9. Accessibility baseline: axe scan of every route, current violations listed.

**Acceptance criteria**

- [ ] All 21 `.catch()` fallbacks documented with their substituted payload.
- [ ] The client-side evaluation in `services/learning.ts` documented line by line.
- [ ] Every component has exactly one verdict.
- [ ] Baseline bundle sizes and axe violation counts recorded.
- [ ] Zero source files modified.

> **Prompt — FE Phase 0**
>
> Read `docs/frontend-architecture.md` and `docs/backend-architecture.md`. Audit the
> `frontend/` Next.js app **without modifying any source file**. Produce
> `docs/frontend-audit.md` with: (1) route inventory across `app/**/page.tsx` labelled
> child/parent/auth; (2) every `fetch` and `api()` call site with file:line and the backend
> route it targets; (3) **every `.catch()` fallback with the exact fake data it
> substitutes** — there are 21 across 8 service files, find them all; (4) every location
> where client code computes correctness, score, stars, progress, or unlock state, quoted
> line by line — start with `answerLearning()` in `services/learning.ts`; (5) every
> `sessionStorage`/`localStorage` access; (6) a KEEP/ADAPT/REPLACE/DELETE verdict for every
> component; (7) an import map for `data/prototype.ts`; (8) per-route bundle sizes from
> `next build`; (9) an axe accessibility scan of every route with current violations.
> Modify nothing.

---

### FE Phase 1 — API Client & Fallback Removal ← *BE Phase 1 gate*

**Goal:** one honest fetch boundary. This phase makes the app *more* likely to visibly
fail — that is the point.

**In scope:** `lib/apiClient.ts` · `lib/errors.ts` · `lib/tokenStore.ts` ·
`lib/idempotency.ts` · React Query setup · delete all 21 fallbacks · delete
`services/api.ts` · error boundaries · offline detection.

**Out of scope:** auth logic (Phase 2), any endpoint change (Phase 3+). Point the new
client at the existing prototype routes for now.

**Acceptance criteria**

- [ ] `grep -rn "\.catch(" frontend/services frontend/app frontend/components frontend/features`
      returns **zero** fallback-style results (21 in `services/`, 4 in `app/`+`components/`).
- [ ] A lint rule fails the build on any `fetch(` outside `lib/apiClient.ts` — this catches
      the two current offenders, `services/speech.ts:140` and `AIAvatar.tsx:45`.
- [ ] `services/api.ts` and `services/session.ts` are deleted.
- [ ] The client parses the §6.1 backend error envelope into a typed `ApiError` carrying
      `code`, `status`, `requestId`, and child-safe copy.
- [ ] Retries apply **only** to timeouts, network errors, and 5xx — never to 4xx.
- [ ] Every mutating request sends a UUID `Idempotency-Key`; a retried request reuses the
      **same** key (tested).
- [ ] `X-Request-ID` is generated per request and logged alongside failures.
- [ ] With the backend stopped, every route renders a retry state and **no fabricated
      content** — verified route by route with screenshots.
- [ ] React Query configured: no `refetchOnWindowFocus` on the child surface (it would
      interrupt a session), sensible `staleTime` per resource.
- [ ] An error boundary per route group; a thrown render error never blanks the screen.

**Gate:** the zero-fallback grep, the fetch lint rule, and the backend-down walkthrough.

> **Prompt — FE Phase 1**
>
> Backend Phase 1 has passed its gate. Read `docs/frontend-architecture.md` §0.3, §2, §3.5
> and `docs/frontend-audit.md`. Build the new API boundary and **remove every silent
> fallback**. Create `lib/apiClient.ts` as the only place in the app that calls `fetch`,
> with: configurable timeout per call (not by path prefix), exponential-backoff retry for
> timeouts / network errors / 5xx only, parsing of the backend error envelope
> `{error:{code,message,request_id}}` into a typed `ApiError` exposing `code`, `status`,
> `requestId` and a child-safe `childMessage`, a generated `X-Request-ID` per request, and
> an `Idempotency-Key` on every mutating request where a retry of the same logical
> operation reuses the same key. Add `lib/tokenStore.ts` (in-memory only — no storage API),
> `lib/errors.ts`, and React Query with `refetchOnWindowFocus` disabled on the child
> surface. Then **delete every `.catch(() => fallback)` block** — 21 in `services/` and 4
> more in `app/certificate`, `app/levels`, `AIAvatar.tsx` and `ToddlerLesson.tsx` — do not
> replace them with anything; failures must surface. Delete `services/api.ts` and
> `services/session.ts`. Route the two raw `fetch` calls (`services/speech.ts:140` and
> `AIAvatar.tsx:45`) through the new client. Add a lint rule failing the build on `fetch(`
> outside `lib/apiClient.ts`, and an error boundary per route group. Keep pointing at the existing
> prototype routes — endpoint migration is Phase 3+. Prove it: `grep -rn "catch(() =>"`
> returns nothing; with the backend stopped, walk every route and show it renders an honest
> retry state with zero fabricated content.

---

### FE Phase 2 — Real Auth & Parental Consent ← *BE Phase 2 gate*

**Prerequisite:** the §0.5 cookie-based refresh must be live on the backend. Confirm
before starting.

**Acceptance criteria**

- [ ] Access token exists **only** in memory; `grep -rn "sessionStorage\|localStorage"` in
      `frontend/` returns zero results for tokens.
- [ ] Refresh token is never readable from JavaScript (HttpOnly cookie), verified in devtools.
- [ ] A page reload silently restores the session via one `/auth/refresh` call.
- [ ] **Single-flight refresh:** 10 concurrent 401s trigger exactly **one** refresh call
      (tested with a request counter).
- [ ] A failed refresh clears state and routes to login exactly once — no redirect loop.
- [ ] Login failure shows a real error. **No fabricated session, ever** — the old
      `local-session-${Date.now()}` path must be gone (tested).
- [ ] Consent screen blocks first child creation; no consent → no child.
- [ ] Consent is explicit: unticked checkbox + button. No pre-tick, no implied consent.
- [ ] Consent screen sits behind the parent gate, unreachable from the child surface.
- [ ] Parent settings shows the consent record and offers withdrawal.
- [ ] Requesting another parent's child renders the 404 state, never a crash or partial UI.
- [ ] Logout clears memory, cookie, and the entire React Query cache.

**Gate:** single-flight test, no-fabricated-session test, and consent gating all pass.

> **Prompt — FE Phase 2**
>
> Backend Phase 2 has passed its gate, and the backend now sets the refresh token as an
> HttpOnly cookie for web clients (spec §0.5) — verify this before you start; if it is not
> live, stop and report rather than storing the refresh token in JavaScript. Read
> `docs/frontend-architecture.md` §3.1, §3.2 and backend §7. Implement real auth: access
> token in memory only via `lib/tokenStore.ts`; session restored on load by a single
> `/api/v1/auth/refresh` call against the cookie; a **single-flight** refresh interceptor
> where N concurrent 401s produce exactly one refresh call and then replay their original
> requests once; and a failed refresh that clears state and routes to login without
> looping. **Delete the fabricated-session fallbacks in `services/auth.ts`** — a failed
> login must show a real error. Build the parental consent flow: behind the parent gate,
> shown before the first child can be created, plain-language about what is and is not
> collected, an unticked checkbox plus an explicit button, posting the policy version to
> the backend consent endpoint, with the record and a withdrawal path visible in parent
> settings. Handle 404 on another parent's child as a clean not-found state. Prove:
> zero token references to `sessionStorage`/`localStorage`; the refresh cookie is not
> readable from JS; 10 concurrent 401s produce exactly one refresh; and login failure
> produces an error rather than a session.

---

### FE Phase 3 — Curriculum From The Server ← *BE Phase 3 gate*

**Acceptance criteria**

- [ ] `data/prototype.ts` is **deleted**; nothing imports it.
- [ ] Classes, levels, lessons, and activities all come from `/api/v1/*`.
- [ ] Adding a class server-side makes it appear with **zero** frontend changes — demonstrated.
- [ ] Unknown `activity.type` renders a safe placeholder and reports, rather than crashing.
- [ ] Curriculum queries have a long `staleTime` (content is near-static).
- [ ] Loading states are skeletons matched to final layout — CLS stays ≤ 0.05.
- [ ] The toddler API calls are gone; toddler is a presentation mode (§4.5).
- [ ] `toddlerGuide.ts` and `toddlerVoice.ts` are deleted.

> **Prompt — FE Phase 3**
>
> Backend Phase 3 has passed its gate; curriculum is now server data. Read
> `docs/frontend-architecture.md` §4.2, §4.5. Replace all client-side curriculum with
> server data: fetch classes, levels, lessons, and activities from `/api/v1`, and
> **delete `data/prototype.ts` entirely** along with every import of it. Collapse the
> parallel toddler stack per §4.5 — remove the `/toddler/*` API calls, delete
> `services/toddlerGuide.ts` and `services/toddlerVoice.ts`, and make toddler a
> presentation mode resolved from the child's age band that changes type scale, target
> size, and copy length on the *same* shared components and renderer. Handle an unknown
> `activity.type` with a safe placeholder plus a report, never a crash. Use a long
> `staleTime` for curriculum queries and skeletons that match the final layout so CLS
> stays under 0.05. Demonstrate that adding a new class on the backend surfaces in the UI
> with zero frontend code changes.

---

### FE Phase 4 — Server-Authoritative Sessions ← *BE Phase 4 gate*

**The most important frontend phase.** All client grading dies here.

**Acceptance criteria**

- [ ] **Zero client-side answer evaluation.** `grep -rn "correct_answer"` in `frontend/`
      returns nothing outside type definitions.
- [ ] No client code computes score, stars, attempt number, or step index.
- [ ] Every session read comes from `GET /api/v1/learning/sessions/{id}`.
- [ ] Browser refresh mid-session resumes at the exact server step — tested at three
      different points in a session.
- [ ] A submitted answer retried after a network drop produces **one** attempt server-side
      (same `Idempotency-Key`) — tested by forcing a failure mid-flight.
- [ ] Double-tapping an answer sends **one** request.
- [ ] Optimistic UI follows §3.3 exactly: tap acknowledgement is allowed; correctness,
      stars, progress movement, and celebration wait for the server — verified by
      throttling the response to 3 s and confirming nothing green appears early.
- [ ] Feedback renders within 400 ms p95 of the server responding.
- [ ] A session that expires server-side surfaces a gentle "let's start a new adventure".
- [ ] Practice and learning share one renderer and one hook set.

**Gate:** the `correct_answer` grep, the throttled-response check, and the resume tests.

> **Prompt — FE Phase 4**
>
> Backend Phase 4 has passed its gate; sessions and evaluation are now server-owned. Read
> `docs/frontend-architecture.md` §0.2, §3.3, §4.2 and backend §4.2. Make the client fully
> server-authoritative. **Delete every trace of client-side answer evaluation** — starting
> with the `.catch()` body of `answerLearning()` in `services/learning.ts`, which currently
> normalizes the answer, compares it to `activity.correct_answer`, computes correctness,
> awards stars, and writes progress into `sessionStorage`. Remove all of it. No client code
> may compute correctness, score, stars, attempt number, step index, or unlock state.
> Move session start / answer / complete to `/api/v1/learning/sessions*`, and read session
> state exclusively from `GET /api/v1/learning/sessions/{id}` so a browser refresh resumes
> at the exact server step. Every answer submission carries an `Idempotency-Key` that is
> reused on retry. Implement optimistic UI strictly per §3.3: the tapped option may depress
> and the avatar may enter a thinking state immediately, but correct/incorrect styling,
> stars, progress movement, celebration, and advancement must wait for the server response.
> Unify practice and learning onto one renderer and one hook set. Prove it: `grep -rn
> "correct_answer"` finds nothing outside type files; throttle the answer response to 3
> seconds and show no correctness signal appears before it lands; force a mid-flight
> network failure and show the retry creates exactly one attempt; and resume correctly
> after a refresh at three different points in a session.

---

### FE Phase 5 — Mastery, Recommendations & Rewards ← *BE Phase 5 gate*

**Goal:** surface the adaptive signals the backend now produces. This is where the app
starts feeling personalised — the first phase that is a genuine product upgrade rather
than a migration.

**Acceptance criteria**

- [ ] The recommendation card shows different copy per `reason` — all six of `continue`,
      `revise`, `weak_skill`, `new_skill`, `parent_selected`, `fallback` — child-friendly,
      never clinical. ("Let's practise this again!" not "weak skill detected".)
- [ ] `reason` is never inferred client-side; it is read from the response.
- [ ] Parent progress shows mastery bands (weak / learning / mastered) per skill, with
      plain-language explanation of what each means.
- [ ] Parent progress explains *why* a level is locked, from server state.
- [ ] Weak skills appear on the parent surface only — **never framed negatively to the
      child**. No "you are bad at" copy anywhere, in any state.
- [ ] **`app/rewards/page.tsx` is rebuilt against `/api/v1/rewards/{child_id}`.** It
      currently reads stars and badges entirely from `sessionStorage` via
      `getOrCreateGuestChild()` and never calls the backend — no client arithmetic survives.
- [ ] Unlock celebration triggers only on a server-confirmed unlock.
- [ ] `GET /progress` renders within 400 ms p95 for a child with 5,000 attempts.
- [ ] Empty states are warm, not blank — a brand-new child sees an invitation, not zeros.

> **Prompt — FE Phase 5**
>
> Backend Phase 5 has passed its gate; mastery, recommendations, rewards and unlocks are
> now server-computed. Read `docs/frontend-architecture.md` §1.4 and backend §4.3–§4.5.
> Surface the new signals. The recommendation card must render distinct, warm,
> child-friendly copy for each of the six `reason` values returned by
> `/api/v1/recommendations/{child_id}` — read the reason from the response, never infer it.
> On the parent surface, show per-skill mastery bands (weak / learning / mastered) with a
> plain-language explanation of each, and explain from server state why a level is locked.
> Weak-skill information appears **only** on the parent surface — no child-facing copy may
> ever frame a child as bad at something, in any state. Rebuild `app/rewards/page.tsx`
> against `/api/v1/rewards/{child_id}` — it currently reads stars and badges entirely from
> `sessionStorage` and never calls the backend at all. Do the same for the certificate
> surface. No client arithmetic survives, and trigger unlock celebrations
> only on a server-confirmed unlock. Write warm empty states for a brand-new child. Verify
> progress renders within 400 ms p95 for a child with 5,000 seeded attempts.

---

### FE Phase 6 — Guide & Hand-Raise ← *BE Phase 6 gate*

**Acceptance criteria**

- [ ] Requests send `ui.allowed_actions` and `ui.allowed_targets` from the **live**
      registry — only currently-mounted targets.
- [ ] Responses validated with zod against the §4.6 contract; unknown fields dropped.
- [ ] An action naming an unmounted target is dropped client-side even if the backend
      approved it (tested by unmounting between request and response).
- [ ] An action type outside the closed set is dropped.
- [ ] `navigate_safe` is checked against the safe-route allowlist **twice** — in validation
      and again in the executor. Auth, parent, and destructive routes are absent from the
      allowlist and unreachable from any model output (tested).
- [ ] Avatar state is derived client-side from `strategy` — the model does not control it.
- [ ] Guide failure or a templated response is **visually indistinguishable** to the child
      from a model response.
- [ ] Hand-raise: a visible, always-reachable button on the child surface; pauses without
      unmounting; resumes the exact step.
- [ ] Doubt conversation wires to `/api/v1/doubts*`; "I don't understand" triggers a
      simpler explanation.
- [ ] `say` longer than 220 chars is truncated gracefully, never mid-word.
- [ ] Rendering never blocks on the guide — the child can always continue.
- [ ] Guide markup, code, and URLs are stripped before display or speech (defence in depth).

**Gate:** the unmounted-target test, the double-checked route allowlist test, and the
templated-response indistinguishability check.

> **Prompt — FE Phase 6**
>
> Backend Phase 6 has passed its gate; the guide contract is now `{say, strategy, actions[],
> listen_after}` with the closed action set in `docs/frontend-architecture.md` §4.6. Read
> §3.4 and §4.6 plus backend §5. Rebuild the guide integration. Convert the existing
> `GUIDE_TARGETS` constant in `services/guide.ts` into a **live** `TargetRegistry` where a
> target is addressable only while its component is mounted, and send
> `ui.allowed_actions` + `ui.allowed_targets` from that registry on every request. Validate
> responses with zod against the new contract, dropping unknown fields, actions outside the
> closed set, and any action naming a target that is no longer mounted — even one the
> backend approved. Check `navigate_safe` against the safe-route allowlist twice, once in
> validation and again in the executor, with auth, parent, and destructive routes absent
> from that allowlist. Derive avatar state client-side from `strategy` rather than letting
> the model send it. Strip markup, code, and URLs before anything is displayed or spoken.
> Build the hand-raise / doubt flow — a visible always-reachable button on the child
> surface that pauses the session without unmounting it, a doubt conversation wired to
> `/api/v1/doubts*`, an "I don't understand" path that requests a simpler explanation, and
> a resume that returns to the exact paused step. A templated fallback response must be
> visually indistinguishable from a model response, and the child must always be able to
> continue without the guide. Test: unmount a target between request and response and show
> the action is dropped; show auth and parent routes are unreachable from model output.

---

### FE Phase 7 — Speech, Tracing & Certificates ← *BE Phase 7 gate*

**Acceptance criteria**

- [ ] Speech uses browser `SpeechRecognition`, posting the transcript to
      `/api/v1/speech/transcribe`. **No audio bytes leave the browser.**
- [ ] Every STT failure mode (no permission, no support, no speech, network) has a distinct
      gentle message and a **tap fallback** — a child must never be stuck at a mic.
- [ ] Mic permission is requested on an explicit child action, never on page load.
- [ ] A visible listening indicator and a visible stop control at all times while listening.
- [ ] Tracing geometry runs client-side; the client posts only `{completed, accuracy}`.
- [ ] Tracing works with mouse, touch, and stylus; strokes are never dropped mid-draw.
- [ ] Certificates poll `status: pending` with a friendly waiting state, never an error.
- [ ] Certificate signed URLs are treated as short-lived; an expired one refetches silently.
- [ ] Print/download works from the parent surface.
- [ ] No child audio, drawing bitmap, or transcript is written to any browser storage.

> **Prompt — FE Phase 7**
>
> Backend Phase 7 has passed its gate. Read `docs/frontend-architecture.md` §1.4 and backend
> §7.2. Wire the remaining surfaces. Speech: keep browser `SpeechRecognition` on the client
> and post only the resulting transcript to `/api/v1/speech/transcribe` — no audio bytes may
> leave the browser, and none may be written to browser storage. Give every STT failure mode
> (permission denied, unsupported browser, no speech detected, network failure) its own
> gentle message and a tap-to-answer fallback so a child is never stuck at a microphone,
> request mic permission only on an explicit child action, and always show a listening
> indicator plus a stop control while listening. Tracing: run the geometry scoring
> client-side and post only `{completed, accuracy}` to the backend, supporting mouse, touch
> and stylus without dropping strokes mid-draw. Certificates: poll the `status: pending`
> state with a friendly waiting UI rather than an error, treat signed URLs as short-lived
> and refetch silently when one expires, and support print/download from the parent surface.

---

### FE Phase 8 — Hardening, Accessibility & Cutover ← *BE Phase 8 gate*

**Acceptance criteria**

- [ ] All §1.1 Core Web Vitals targets met on throttled 4G / mid-tier Android.
- [ ] All §1.3 bundle budgets met; CI fails on regression.
- [ ] **axe: zero critical or serious violations** on every route.
- [ ] Every child-facing control is ≥ 64 × 64 px with ≥ 12 px spacing — automated check.
- [ ] Contrast verified across the full palette; no failures.
- [ ] `prefers-reduced-motion` honoured by every animation; nothing flashes above 3 Hz.
- [ ] Full keyboard traversal of the parent surface; visible focus everywhere.
- [ ] Screen-reader pass on the parent surface (child surface is voice/touch-first, but must
      not actively break a reader).
- [ ] 429 handled with `Retry-After` and gentle copy on both surfaces.
- [ ] Offline banner appears within 2 s of connection loss and clears on restore.
- [ ] E2E covers: register → consent → child → lesson → answer → guide → progress → reward
      → certificate, plus resume-after-refresh and answer-retry-idempotency.
- [ ] E2E chaos: backend down, backend slow (3 s), 429 storm, guide unavailable — no
      fabricated content in any of them.
- [ ] `request_id` visible on every parent-surface error.
- [ ] Zero references to prototype routes anywhere in the codebase.
- [ ] Legacy code deleted **only after** production traffic confirms the new paths work.

**Gate:** Lighthouse + axe + bundle reports committed to `docs/`.

> **Prompt — FE Phase 8**
>
> Backend Phase 8 has passed its gate. Read `docs/frontend-architecture.md` §1 in full.
> Harden and cut over. Meet every Core Web Vitals target in §1.1 on throttled 4G with a
> mid-tier Android profile, and every bundle budget in §1.3 with a CI check that fails on
> regression. Reach zero critical and zero serious axe violations on every route. Enforce
> §1.4: child-facing controls at least 64×64 px with 12 px spacing (add an automated check),
> verified contrast across the palette, `prefers-reduced-motion` honoured by every animation,
> nothing flashing above 3 Hz, full keyboard traversal with visible focus on the parent
> surface, and a screen-reader pass there. Handle 429 with `Retry-After` and gentle copy,
> and show an offline banner within 2 seconds of connection loss. Write Playwright E2E
> covering register → consent → child → lesson → answer → guide → progress → reward →
> certificate, plus resume-after-refresh and answer-retry idempotency, and chaos scenarios
> for backend down, backend slow at 3 s, a 429 storm, and the guide unavailable — asserting
> **no fabricated content** in any of them. Surface `request_id` on every parent-surface
> error. Confirm zero references to prototype routes remain, and commit the Lighthouse, axe,
> and bundle reports to `docs/`. Delete legacy code only after production traffic confirms
> the new paths work.

---

## 6. Definition of Done

**Correctness**

- [ ] Zero client-side correctness, scoring, star, or unlock logic (grep-verified).
- [ ] Zero `.catch(() => fallback)` blocks.
- [ ] Retried submissions create exactly one attempt.
- [ ] Refresh mid-session resumes exactly.

**Child safety & privacy**

- [ ] Consent gates child creation; withdrawal path exists.
- [ ] No audio, drawing bitmap, or transcript in browser storage.
- [ ] No child-facing copy frames a child negatively, in any state.
- [ ] Model output cannot reach auth, parent, or destructive routes.
- [ ] Guide markup/code/URLs stripped before display or speech.

**Reliability**

- [ ] Backend down → honest retry states, zero fabricated content, every route.
- [ ] Guide down → child cannot tell.
- [ ] 10 concurrent 401s → exactly one refresh.

**Accessibility**

- [ ] Zero critical/serious axe violations.
- [ ] ≥64 px targets, ≥4.5:1 contrast, reduced-motion honoured.

**Performance**

- [ ] LCP ≤2.0 s, INP ≤150 ms, CLS ≤0.05.
- [ ] First-load JS ≤180 KB gzipped on the child home route.

**Maintainability**

- [ ] `fetch` only inside `lib/apiClient.ts` (lint-enforced).
- [ ] Server state read only in `hooks/`.
- [ ] `data/prototype.ts`, `services/api.ts`, `services/session.ts`, `toddlerGuide.ts`,
      `toddlerVoice.ts` all deleted.
- [ ] A new class added server-side needs zero frontend changes.

---

## 7. Standing Rules for the Coding Agent

1. **Never start a frontend phase before its paired backend gate passes.** Stop and say so.
2. **Never re-add a fallback.** If a request fails, the user finds out.
3. **Never compute correctness, score, stars, or unlocks in the browser.**
4. **Never put a token in `localStorage` or `sessionStorage`.** If the backend cookie work
   from §0.5 isn't ready, stop — do not work around it.
5. **Never let model output reach the DOM without validation and a live target check.**
6. **Never show a child a technical error.**
7. **Never ship a child-facing control smaller than 64 px.**
8. **Never autoplay audio without an explicit child action.**
9. **Never add a dependency outside §2.3** without stating what it replaces.
10. **When the spec conflicts with reality, stop and report.** Do not silently work around it.

---

## Appendix A — Phase Cheat Sheet

| FE Phase | Blocked by | One-line brief |
|---|---|---|
| 0 | BE 0 | Audit only, zero code changes |
| 1 | BE 1 gate | One fetch boundary; delete all 21 fallbacks |
| 2 | BE 2 gate | Memory token + cookie refresh + consent |
| 3 | BE 3 gate | Curriculum from server; delete `prototype.ts`; collapse toddler |
| 4 | BE 4 gate | Server-authoritative sessions; delete client grading |
| 5 | BE 5 gate | Recommendation reasons, mastery bands, server rewards |
| 6 | BE 6 gate | New guide contract, live target registry, hand-raise |
| 7 | BE 7 gate | Speech, tracing, async certificates |
| 8 | BE 8 gate | CWV, a11y, E2E, chaos, cutover |

## Appendix B — Cross-Team Dependencies

Raise these with whoever owns the backend **before** the phase that needs them.

| Needed by | Dependency |
|---|---|
| FE Phase 2 | Cookie-based refresh for web clients (§0.5) — **not in the backend spec yet** |
| FE Phase 2 | A consent-record endpoint the web client can post to |
| FE Phase 3 | Curriculum seeded with the canonical 12 activity types from backend §3.2 |
| FE Phase 5 | `reason` present on every recommendation response |
| FE Phase 5 | Mastery band exposed on `/progress`, not just the raw score |
| FE Phase 6 | Final guide response contract frozen before the client validator is written |
| FE Phase 7 | Certificate `status: pending` and signed-URL expiry semantics confirmed |
