# Frontend Audit & Baseline — FE Phase 0

**Repository:** `d:\testcase` (branch `aastik_test`) · target `frontend/`
**Produced:** 2026-08-14
**Specs:** [frontend-architecture.md](frontend-architecture.md) · [backend-architecture.md](backend-architecture.md)
**Phase:** FE Phase 0 — Frontend Audit. **Zero source files were modified.**

Stack as built: Next.js 16.3.0 (Turbopack) · React 19.2.8 · Tailwind 3.4.4 · TypeScript 5.5.3.
Runtime dependencies are exactly four: `next`, `react`, `react-dom`, `framer-motion`,
`@rive-app/react-canvas`. No data-fetching, form, validation, or test library is installed.

> **Read §10 first if you are about to execute FE Phase 1.** The spec's fallback counts and
> its list of files to change are close but not exact, and one file it tells you to strip is
> already correct. §10 lists every divergence.

---

## 1. Route inventory

23 `page.tsx` files → 24 built routes (incl. `/_not-found`). All static except four dynamic
segments. There is **no route grouping, no layout-level auth gate, and no parent gate** — the
"parent surface" is parent-facing only by convention, reachable by typing the URL.

| Route | Surface | Reached from | Backend? | Notes |
|---|---|---|---|---|
| `/` | child | entry | — | Renders `AgeGate`; the age answer decides toddler vs standard |
| `/home` | child | `AppShell` nav | — | Renders `HomeExperience` |
| `/child/select` | child | legacy links | — | Redirect-only: `/` if a child exists, else `/onboarding` |
| `/onboarding` | **parent** | after signup | ✅ `createChild` | Creates the child profile; also writes `demo_child_avatar` |
| `/levels` | child | home | ✅ `listPaths` | World map |
| `/levels/[pathId]` | child | `/levels` | ✅ `listStages` | Stage list |
| `/levels/[pathId]/[stageId]` | child | `/levels/[pathId]` | ✅ `startLearning`, `answerLearning`, `getProgress`, guide | **The main learning loop** |
| `/adventure` | child | legacy links | — | Re-exports `/levels` page directly |
| `/adventure/[pathId]` | child | legacy links | — | `redirect()` to `/levels/[pathId]` |
| `/adventure/[pathId]/[stageId]` | child | legacy links | — | `redirect()` to the levels equivalent |
| `/practice` | child | home | — | Topic cards read from `data/prototype.ts` only |
| `/practice/[topic]` | child | `/practice` | ✅ `startPractice`, `answerPractice`, guide | Practice loop |
| `/rewards` | child | home | ❌ **never** | Stars/badges read from `sessionStorage` |
| `/certificate` | child | home / rewards | ✅ `/progress/{id}/certificate` | Only page calling `api()` directly from `app/` |
| `/toddler` | child | `AgeGate` | ✅ via `ToddlerExperience` | Parallel toddler stack |
| `/word-coach` | child | `/guide` redirect | ❌ **never** | **Self-scoring**, persists to `localStorage` |
| `/sentence-coach` | child | home | ❌ **never** | **Self-scoring**, persists to `localStorage` |
| `/guide` | child | legacy links | — | `redirect()` to `/word-coach` |
| `/parent/profile` | **parent** | home | ✅ `updateChildProfile` | Also edits child age |
| `/parent/progress` | **parent** | home | ✅ `getProgress`, `seedChild` | Exposes the dev seed button |
| `/login` | auth | `/signup` | ✅ `login` (via `AuthForm`) | |
| `/register` | auth | — | ✅ `register` | **Byte-identical duplicate of `/signup`** |
| `/signup` | auth | `/login` | ✅ `register` | |

**Findings**

- **F-1.1** `/register` and `/signup` are the same file content with a different function name.
  One is dead weight.
- **F-1.2** `/guide` and `/adventure/*` are pure redirect shims to other routes — legacy aliases.
- **F-1.3** Three child routes (`/rewards`, `/word-coach`, `/sentence-coach`) never contact the
  backend at all.
- **F-1.4** No auth gate exists at any layer. `/parent/progress` renders for anyone, including
  its `seedChild` dev button.

---

## 2. Network call-site inventory

### 2.1 Through the `api()` helper (21 sites)

`services/api.ts` is the only module that calls `fetch` for backend data. Every call below
routes through it.

| # | Call site | Method | Path | Backend route |
|---:|---|---|---|---|
| 1 | `frontend/services/auth.ts:5` | POST | `/auth/register` | ✅ |
| 2 | `frontend/services/auth.ts:15` | POST | `/auth/login` | ✅ |
| 3 | `frontend/services/child.ts:7` | POST | `/children` | ✅ |
| 4 | `frontend/services/child.ts:18` | GET | `/progress/${childId}` | ✅ |
| 5 | `frontend/services/child.ts:28` | PATCH | `/children/${child_id}` | ✅ |
| 6 | `frontend/services/child.ts:38` | POST | `/dev/seed/${childId}` | ✅ dev-only |
| 7 | `frontend/services/companion.ts:19` | POST | `/companion/session/start` | ✅ **web-only consumer** |
| 8 | `frontend/services/guide.ts:94` | POST | `/agent/guide` | ✅ |
| 9 | `frontend/services/learning.ts:34` | GET | `/learning/paths` | ✅ |
| 10 | `frontend/services/learning.ts:38` | GET | `/learning/paths/${pathId}/stages` | ✅ |
| 11 | `frontend/services/learning.ts:68` | POST | `/learning/start` | ✅ |
| 12 | `frontend/services/learning.ts:99` | POST | `/learning/answer` | ✅ |
| 13 | `frontend/services/practice.ts:15` | GET | `/practice/topics/${childId}` | ✅ |
| 14 | `frontend/services/practice.ts:31` | POST | `/practice/start` | ✅ |
| 15 | `frontend/services/practice.ts:85` | POST | `/practice/answer` | ✅ |
| 16 | `frontend/services/speech.ts:351` | POST | `/speech/normalize` | ✅ |
| 17 | `frontend/services/toddler.ts:6` | POST | `/toddler/mode` | ✅ |
| 18 | `frontend/services/toddler.ts:13` | GET | `/toddler/modules` | ✅ |
| 19 | `frontend/services/toddler.ts:25` | POST | `/toddler/start` | ✅ |
| 20 | `frontend/services/toddler.ts:33` | POST | `/toddler/answer` | ✅ |
| 21 | `frontend/app/certificate/page.tsx:29` | GET | `/progress/${child_id}/certificate` | ✅ **`api()` called from a page, bypassing `services/`** |

### 2.2 Raw `fetch` outside the boundary (2 sites)

| Call site | Target | Why it matters |
|---|---|---|
| `frontend/services/speech.ts:140` | `POST ${API_BASE}/speech/synthesize` | Real backend call with its own `AbortController`; skips `api()`'s timeout, error parsing, and every future auth header. Confirms spec §0.3. |
| `frontend/components/avatar/AIAvatar.tsx:45` | `HEAD ${riveSrc}` | Static-asset feature probe, not a backend call. Still must move behind the boundary for the Phase 1 lint rule. |

### 2.3 What `services/api.ts` actually does (31 lines)

```ts
timeout = path.startsWith("/agent/") ? 8000 : 4500     // line 14 — prefix-coupled
const data = (await response.json()) as T & ApiError;  // line 26 — unguarded
if (!response.ok) throw new Error(data.error?.message ?? "…");  // line 28 — bare Error
```

- No `Authorization` header — the token in `sessionStorage` is **never sent**.
- No retry, no `X-Request-ID`, no `Idempotency-Key`.
- Errors are bare `Error(message)`: `code`, `status` and `request_id` are all discarded, so
  nothing on the client can correlate to a backend log.
- **Line 26 parses JSON before checking `response.ok`** — a 502 HTML error page or an empty
  204 throws a raw `SyntaxError` rather than the intended message.

---

## 3. Every `.catch()` — all 29, classified

The spec counts "21 in `services/`, 4 more in `app/`+`components/`". The raw count is **29
`.catch(` sites**, and they are not all the same kind of thing. Classifying them matters,
because FE Phase 1 says to delete them and **two of them are correct code that should stay**.

**Legend:** 🔴 **FABRICATES** — substitutes invented data for server truth · 🟠 **SWALLOWS** —
hides the error, invents nothing · 🟢 **CORRECT** — surfaces the error to the user ·
⚪ **NON-BACKEND** — promise plumbing or asset probe.

### 3.1 `services/` — 21 sites (spec's count is right; one is not a fallback)

| # | Site | Kind | Substituted payload |
|---:|---|---|---|
| 1 | `services/auth.ts:8` | 🔴 | `{session_token: "local-session-${Date.now()}", user:{id:"local-user", name, email}}` — **registration cannot fail** |
| 2 | `services/auth.ts:18` | 🔴 | Same shape, `name: "Demo Parent"` — **login cannot fail** |
| 3 | `services/child.ts:10` | 🔴 | `makeGuestChild()` spread with `child_id: "local-child-${Date.now()}"`, then `saveChild()` to `sessionStorage` |
| 4 | `services/child.ts:18` | 🔴 | `{child: getChild() ?? makeGuestChild()}` — progress silently comes from local storage |
| 5 | `services/child.ts:31` | 🔴 | Locally-merged child + `saveChild()` |
| 6 | `services/child.ts:38` | 🔴 | `seedFinalDemo(...)` — **fabricates a completed curriculum and an unlocked certificate** |
| 7 | `services/companion.ts:26` | 🔴 | Full `CompanionResponse`: welcome copy, avatar, guidance target, and a `numbers`/stage-1 recommendation |
| 8 | `services/guide.ts:97` | 🔴 | `localGuide(payload)` — a complete templated guide response (arguably the most defensible one) |
| 9 | `services/learning.ts:34` | 🔴 | `pathSummaries` from `data/prototype.ts` |
| 10 | `services/learning.ts:38` | 🔴 | `localStages(pathId)` from `data/prototype.ts` |
| 11 | `services/learning.ts:71` | 🔴 | A whole fabricated learning session with a `local-learning-…` id, registered in a module-level `Map` |
| 12 | `services/learning.ts:102` | 🔴🔴 | **The client grades the child.** See §4.1 |
| 13 | `services/practice.ts:15` | 🔴 | `practiceCards` mapped to `{unlocked: true}` — **every topic unlocked** |
| 14 | `services/practice.ts:34` | 🔴 | Local practice session from `localActivities` |
| 15 | `services/practice.ts:88` | 🔴🔴 | `localPracticeAnswer()` — **client grading.** See §4.2 |
| 16 | `services/speech.ts:159` | ⚪ | `playbackAudio.play().catch(reject)` — audio playback plumbing, **not a fallback** |
| 17 | `services/speech.ts:312` | 🔴 | `localNormalizeSpeech(...)` — client-side transcript resolution |
| 18 | `services/toddler.ts:9` | 🔴 | `{age, learning_mode: age < 3 ? "toddler" : "standard"}` — re-implements the server rule |
| 19 | `services/toddler.ts:13` | 🔴 | A hardcoded four-module list |
| 20 | `services/toddler.ts:28` | 🔴 | `localToddlerStart()` — local session from a 15-activity inline curriculum |
| 21 | `services/toddler.ts:36` | 🔴🔴 | `localToddlerAnswer()` — **client grading + star award.** See §4.3 |

**20 fabricate. 1 (`speech.ts:159`) is unrelated promise plumbing and must not be deleted.**

### 3.2 `app/` and `components/` — 8 sites (spec says 4)

| # | Site | Kind | Behaviour |
|---:|---|---|---|
| 22 | `app/certificate/page.tsx:31` | 🔴 | Builds a certificate from `child.certificate_unlocked` and `child.stars` in `sessionStorage`, incl. a fake `cert_local_${child_id}` id and today's date |
| 23 | `app/levels/page.tsx:21` | 🔴 | `setPaths(pathSummaries)` from `data/prototype.ts` |
| 24 | `app/levels/[pathId]/page.tsx:106` | 🔴 | `setStages(localStages(pathId))` — and line 105 **already seeds local stages before the request even fires** |
| 25 | `app/practice/[topic]/page.tsx:86` | 🟠 | `setLoading(false)` only — the child sees an empty screen with no error and no retry |
| 26 | `app/levels/[pathId]/[stageId]/page.tsx:122` | 🟢 | `setError(message)` + error avatar — **correct; keep** |
| 27 | `app/levels/[pathId]/[stageId]/page.tsx:177` | 🟠 | `.catch(() => undefined)` on a supplementary progress refresh; deliberate and commented, but still silent |
| 28 | `components/avatar/AIAvatar.tsx:49` | ⚪ | `setCanUseRive(false)` — Rive asset feature-detection, not backend data |
| 29 | `components/toddler/ToddlerLesson.tsx:78` | 🟢 | `setError(err.message)` + `setBusy(false)` — **correct; keep** |

**Totals: 23 fabricating fallbacks · 2 silent swallows · 2 correct handlers · 2 non-backend.**

### 3.3 The bigger problem: local paths that are not `.catch()` at all

Deleting all 29 `.catch()` blocks would **not** remove client-side grading, because six code
paths route to local logic **unconditionally**, on an id prefix rather than on failure:

| Site | Condition | Effect |
|---|---|---|
| `services/learning.ts:42` | `child_id === "guest_child" \|\| startsWith("local-child")` | Entire learning session runs locally; the backend is never called |
| `services/practice.ts:22` | same | Local practice session |
| `services/practice.ts:81` | `practice_session_id.startsWith("local-practice-")` | **Local grading**, unconditionally |
| `services/toddler.ts:22` | `child_id === "guest_child" \|\| startsWith("local-child")` | Local toddler session |
| `services/toddler.ts:32` | `session_id.startsWith("local-toddler")` | **Local grading + star award**, unconditionally |
| `services/child.ts:24` | `!session_token \|\| guest \|\| local-child` | Profile edits never reach the server |

And `services/session.ts:46` `getOrCreateGuestChild()` **manufactures a child profile out of
thin air** whenever storage is empty — which is how `guest_child` gets created in the first
place. It is called from 9 pages. **Guest mode is a second, parallel, fully client-side
implementation of the product**, and FE Phase 1's grep-based acceptance test cannot see it.

---

## 4. Client-side correctness, scoring, stars, progress and unlocks

### 4.1 `services/learning.ts:102–178` — `answerLearning()` fallback (the worst offender)

Quoted line by line, as the spec asks:

| Line | Code | What it decides |
|---:|---|---|
| 107 | `const isCorrect = normalizeLocalAnswer(activity.correct_answer, …) === normalizeLocalAnswer(answer, …)` | **Correctness** |
| 108 | `const attempts = isCorrect ? 0 : session.attempts + 1` | **Attempt number** |
| 109 | `const questionChanged = !isCorrect && attempts >= 4` | Question-swap rule |
| 110–114 | `nextIndex = isCorrect ? …+1 : questionChanged ? (…+1) % len : …` | **Step index** |
| 115 | `const complete = isCorrect && nextIndex >= stage.activities.length` | Stage completion |
| 116 | `const starsEarned = isCorrect ? (complete ? stage.star_reward : 1) : 0` | **Stars awarded** |
| 121 | `completedStages = complete ? […progress.completed_stages, stage_number] : …` | Completed stages |
| 123 | `unlockedStages = complete && nextStage ? […, nextStage] : …` | **Level unlock** |
| 124–127 | `allCoreDone = ["numbers","alphabets","colours","shapes"].every(… ≥ 8)` | **Mixed-path unlock** |
| 128 | `finalComplete = session.path_id === "mixed_final" && complete` | **Certificate eligibility** |
| 129–146 | `saveChild({ …, stars: child.stars + starsEarned, rewards: […], mixed_path_unlocked, certificate_unlocked, path_progress: {…} })` | **Writes all of it to `sessionStorage`** |
| 163 | `current_score: complete ? 100 : 0` | Score |

Lines 24–31 (`normalizeLocalAnswer`) are a client re-implementation of the backend's
`answer_normalization_service.py` — including its own number-word map and stop-word list.
The two will drift.

**This directly violates the project's own `CLAUDE.md` rule** ("Do not use an LLM for
deterministic correctness, scoring, stars, unlocking, or certificate eligibility") in spirit:
the decision is not made by an LLM, but it is not made by the server either.

### 4.2 `services/practice.ts:67–78` — `localPracticeAnswer()`

Line 69 computes `isCorrect` by comparing normalized `activity.correct_answer` against the
child's answer. Reached from the `.catch()` at line 88 **and unconditionally** from line 81.

### 4.3 `services/toddler.ts:74–125` — `localToddlerAnswer()`

| Line | Decides |
|---:|---|
| 80 | Correctness: `activity.type === "introduce" \|\| heard === expected \|\| accepted.some(…)` |
| 82–85 | Attempt count and the 4-strikes question swap |
| 105 | `saveChild({ …child, stars: child.stars + 1 })` — **awards a star client-side** |
| 110/118 | `stars_earned: 3` on completion, `1` per correct answer |

### 4.4 `app/word-coach/page.tsx` and `app/sentence-coach/page.tsx`

Two child-facing routes that **never call the backend at all**:

- `app/word-coach/page.tsx:107` — `const nextScore = score + 10; … window.localStorage.setItem(SCORE_KEY, String(nextScore))`
- `app/sentence-coach/page.tsx:141` — identical

Correctness is decided by comparing the speech transcript to the local word/sentence list in
`data/wordCoach.ts` / `data/sentenceCoach.ts`. **Neither route appears anywhere in the
frontend spec** — not in §0.3, not in the §4 migration map, not in any phase.

### 4.5 Elsewhere

- `services/child.ts:11,22` and `services/session.ts:35` each re-implement the age→mode rule
  (`age < 3 ? "toddler" : "standard"`) — four independent copies of one server rule.
- `app/levels/[pathId]/page.tsx:105` seeds `localStages(pathId)` into state **before** the
  request fires, so prototype content renders first even on a healthy backend.
- `app/levels/page.tsx:14` initialises state to `pathSummaries` for the same reason.

---

## 5. Browser storage inventory

**No token is ever sent** — `services/api.ts` sets no `Authorization` header — so the stored
token is XSS-exposed without even being used.

| Site | Key | Op | Contents |
|---|---|---|---|
| `services/session.ts:12` | `demo_session_token` | write | **Session token** |
| `services/session.ts:13` | `demo_user` | write | Parent id, name, **email** |
| `services/session.ts:14` | `demo_guest_active` | remove | |
| `services/session.ts:18` | `demo_session_token` | read | |
| `services/session.ts:22` | `demo_user` | read | `JSON.parse`, unguarded |
| `services/session.ts:27` | `demo_child` | write | **Full child profile**: name, age, stars, progress, unlocks, certificate flag |
| `services/session.ts:42` | `demo_child` | read | `JSON.parse`, unguarded |
| `services/session.ts:50` | `demo_guest_active` | write | |
| `services/session.ts:56` | `demo_guest_active` | read | |
| `services/session.ts:60–63` | all four | remove | `clearSession()` |
| `app/onboarding/page.tsx:28` | `demo_child_avatar` | write | Avatar choice |
| `services/speech.ts:66` | voice provider | read (`localStorage`) | `"elevenlabs"` / `"browser"` |
| `services/speech.ts:72` | voice provider | write (`localStorage`) | |
| `app/word-coach/page.tsx:40,107` | score key | read/write (`localStorage`) | **Child's score** |
| `app/sentence-coach/page.tsx:36,141` | score key | read/write (`localStorage`) | **Child's score** |

**Findings**

- **F-5.1** The session token lives in `sessionStorage` (spec §0.2 rule 3) — and is never used.
- **F-5.2** A child's **display name and age** are persisted to browser storage. Backend §7.2
  requires data minimisation; this is the client-side counterpart nobody has looked at.
- **F-5.3** `JSON.parse` at `session.ts:22` and `:42` is unguarded — corrupt storage throws on
  read and every page calling `getOrCreateGuestChild()` breaks with no boundary to catch it.
- **F-5.4** No audio or drawing data is stored. The §6 privacy requirement is already met there.
- **F-5.5** `README.md:24` documents the `sessionStorage` choice as a deliberate prototype
  shortcut — consistent with `CLAUDE.md`, and honest.

---

## 6. `data/prototype.ts` import map

11 importers across services, pages, and components. Each is a place where curriculum ships
inside the JS bundle.

| Importer | Symbols |
|---|---|
| `services/learning.ts:2` | `localStages`, `pathSummaries` |
| `services/practice.ts:2` | `localActivities`, `practiceCards` |
| `services/child.ts:2` | `makeGuestChild`, `seedFinalDemo` |
| `services/session.ts:4` | `makeGuestChild` |
| `app/levels/page.tsx:7` | `pathSummaries` |
| `app/levels/[pathId]/page.tsx:6` | `learningWorlds`, `linearAdventurePath`, `localStages`, `pathAccents`, `pathSummaries`, `stageTokens` |
| `app/levels/[pathId]/[stageId]/page.tsx:11` | `linearAdventurePath`, `pathSummaries` |
| `app/practice/page.tsx:7` | `practiceCards`, `pathAccents` |
| `app/parent/profile/page.tsx:7` | `pathAccents`, `pathSummaries` |
| `components/shared/AppShell.tsx:7` | `pathAccents`, `pathSummaries` |
| `components/learning/LearningAdventureMap.tsx:6` | `learningWorlds`, `linearAdventurePath`, `pathSummaries` |

**F-6.1** Not all of it is curriculum. `pathAccents`, `learningWorlds`, `stageTokens` and
`linearAdventurePath` are **presentation data** — colours, world names, map geometry. The
backend spec has nowhere to put them. FE Phase 3 says "delete `data/prototype.ts` entirely";
the presentation half needs a new home (a `theme/` module), not deletion. Deciding this before
Phase 3 avoids either losing the visual design or smuggling curriculum back in.

**F-6.2** `services/toddler.ts:41–65` holds a **second** inline curriculum (15 toddler
activities) that is not in `data/prototype.ts` and would survive its deletion.

---

## 7. Component inventory & verdicts

All 30 files under `components/`, one verdict each.

### KEEP (9)

| File | Reason |
|---|---|
| `shared/LargeButton.tsx` | Already `min-h-16` (64 px) — meets §1.4 today |
| `avatar/AvatarFallback.tsx` | Pure presentational fallback |
| `avatar/AvatarMessage.tsx` | Pure presentational |
| `avatar/AvatarControls.tsx` | Mute/replay controls, no data |
| `avatar/avatar.types.ts` | Type-only |
| `avatar/avatar.config.ts` | Static config |
| `voice/SpeechErrorMessage.tsx` | Per-failure-mode gentle copy — exactly what FE Phase 7 asks for |
| `voice/VoiceStateIndicator.tsx` | Listening indicator, presentational |
| `voice/VoiceTranscriptPreview.tsx` | Presentational |

### ADAPT (13)

| File | Reason |
|---|---|
| `avatar/AvatarProvider.tsx` | Avatar state must become derived from `strategy` (§4.6), not pushed by the model |
| `avatar/AvatarDock.tsx` | Becomes the guide dock and gains the hand-raise button (FE Phase 6) |
| `avatar/AIAvatar.tsx` | Raw `fetch` at line 45 must move behind `lib/apiClient.ts` |
| `guide/VisualGuideRenderer.tsx` | Rewrite against the closed action set; `highlight_sequence` → repeated `highlight` |
| `home/HomeExperience.tsx` | Server-backed recommendation card with the six `reason` variants |
| `shared/AppShell.tsx` | Drops `data/prototype.ts`; gains offline banner and error boundary |
| `learning/ActivityCard.tsx` | Server-driven; **and the 🔊 Voice button at line 79 is ~32 px — below the 64 px floor** |
| `learning/LearningQuestion.tsx` | Correctness styling must wait for the server (§3.3) |
| `learning/VoiceLearningSession.tsx` | Same, plus the unified renderer |
| `learning/LearningAdventureMap.tsx` | Keep the map; source progress from the server. Already uses `useReducedMotion` — the only component that does |
| `rewards/CertificateCard.tsx` | Becomes server-backed with a `pending` polling state |
| `toddler/AgeGate.tsx` | Must collect birth year/month, not an exact age (backend §3.1) |
| `voice/VoiceRecorder.tsx` | Post transcript only; keep audio in the browser |

### REPLACE (5)

| File | Reason |
|---|---|
| `practice/PracticeQuestion.tsx` | Merges into the single renderer (FE Phase 4) |
| `practice/VoicePracticeSession.tsx` | Merges into the single session hook set |
| `toddler/ToddlerExperience.tsx` | Becomes a presentation mode on shared components (§4.5) |
| `toddler/ToddlerHome.tsx` | Same |
| `toddler/ToddlerLesson.tsx` | Same — **but its `.catch()` at line 78 is correct error handling and its pattern should be preserved, not stripped** |

### DELETE (3)

| File | Reason |
|---|---|
| `auth/AuthForm.tsx` | Rebuilt on `react-hook-form` + `zod` with real failure states; the fabricated-session path must not survive a refactor |
| `voice/VoiceAnswerButton.tsx` | Superseded by the unified voice control in the merged renderer |
| `voice/VoiceFallbackOptions.tsx` | Tap-fallback behaviour moves into the shared renderer per FE Phase 7 |

**Tally:** KEEP 9 · ADAPT 13 · REPLACE 5 · DELETE 3 = **30**.

---

## 8. Bundle baseline

`npx next build` — clean, exit 0, compiled in 6.6 s, 20 static pages generated.

> **Next.js 16.3 with Turbopack no longer prints the per-route "First Load JS" table**, and
> writes no `app-build-manifest.json`. The per-route figures FE Phase 0 item 8 asks for are
> **not obtainable from `next build` output on this version.** Measured aggregates instead:

| Measure | Value |
|---|---:|
| Client JS chunks | 28 files |
| Total client JS, raw | 1,376 KB |
| **Total client JS, gzipped** | **430 KB** |
| CSS, gzipped | 11.3 KB |
| Largest single chunk (gzip) | 70.1 KB |
| 2nd / 3rd largest (gzip) | 59.6 KB · 42.4 KB |
| Top 5 chunks as share of total | 251 KB of 430 KB (58%) |
| `public/videos` | **2.8 MB** |

**F-8.1** The largest chunk (70.1 KB gz) is already within the §1.3 per-chunk budget (90 KB),
but the top five chunks together (251 KB gz) exceed the 250 KB any-route first-load budget —
if they load together on a route, that route is already over budget on day one.

**F-8.2** `public/videos` is 2.8 MB against a §1.3 per-route image budget of 400 KB. The spec
requires `learning-adventure-theme.mp4` to be lazy and out of the critical path; whether it
currently is could not be determined from build output alone.

**F-8.3 — blocks FE Phase 8.** The §1.3 budgets are written as per-route first-load numbers
and CI is meant to enforce them by "parsing `next build` output". That output no longer
exists. A different mechanism is needed — `@next/bundle-analyzer`, or measuring transferred
bytes per route in Playwright. **Decide this before Phase 8, or the budget is unenforceable.**

---

## 9. Accessibility baseline

> **A full axe scan was not run.** It needs `@axe-core/playwright` plus a Playwright browser
> download — both additions to `package.json`, which FE Phase 0 forbids ("zero source files
> modified"). The static baseline below is what could be established without installing
> anything. **The axe scan remains outstanding** and should be the first task of any phase
> permitted to add dev dependencies:
>
> ```
> npm i -D @axe-core/playwright @playwright/test && npx playwright install chromium
> ```

**Static findings**

| ID | Sev | Finding |
|---|---|---|
| **A-1** | High | **Only one component honours reduced motion.** `useReducedMotion` appears once, in `LearningAdventureMap.tsx:118`. `framer-motion` is used far more widely, and `app/globals.css:2163` has a single `prefers-reduced-motion` block — nowhere near §1.4's "every animation". |
| **A-2** | High | **Touch targets below 64 px.** `learning/ActivityCard.tsx:79` (`px-4 py-2 text-sm`) and `toddler/ToddlerLesson.tsx:291` (`px-5 py-4`) are child-facing controls under the floor. `LargeButton` is compliant; ad-hoc `<button>` elements are not. A repo-wide sweep is needed. |
| **A-3** | Medium | **No visible-focus policy.** No `focus-visible` utilities appear in any component; the parent surface has no verified keyboard path. |
| **A-4** | Medium | **Error text is not announced.** `aria-live` appears on 5 elements, all in the two coach pages and `AvatarDock`. Learning and practice feedback — the copy that actually tells a child whether they were right — is not in a live region. |
| **A-5** | Low | `<html lang="en">` is set (`app/layout.tsx:12`) — correct, and worth keeping when locales arrive. |
| **A-6** | Low | No `<img>` elements exist, so there are no missing-`alt` violations; imagery is emoji and CSS. Emoji used as meaningful content (`🔴`/`🟡`/`🔵` as colour answers in `services/toddler.ts:54–60`) has no text alternative — a screen reader announces the emoji name, which for a colour-matching task may be an answer leak. |

---

## 10. Where the spec and the code disagree

Per FE spec §7 rule 10, reported rather than worked around. **Read before executing FE Phase 1.**

| ID | Spec says | Reality |
|---|---|---|
| **D-1** | "21 silent fallbacks in `services/`" | 21 `.catch()` sites, but **20 are fallbacks**. `services/speech.ts:159` is `playbackAudio.play().catch(reject)` — audio plumbing. Deleting it breaks TTS playback. |
| **D-2** | "4 more in `app/`+`components/`: `app/certificate`, `app/levels`, `AIAvatar`, `ToddlerLesson`" | **8 sites**, and the list is wrong in both directions. Missing: `app/levels/[pathId]/page.tsx:106`, `app/practice/[topic]/page.tsx:86`, `app/levels/[pathId]/[stageId]/page.tsx:177`. Wrongly included: **`ToddlerLesson.tsx:78` is correct error handling** (`setError`), as is `app/levels/[pathId]/[stageId]/page.tsx:122`. |
| **D-3** | `services/auth.ts` has 2 fallbacks (§0.3 table) | Correct — but the file is 22 lines total and **is nothing but those two calls**. "Delete the fallbacks" leaves a 12-line file; worth knowing before planning the diff. |
| **D-4** | FE Phase 1 gate: `grep -rn "catch(() =>"` returns nothing | This grep **misses the client grading entirely**. The six unconditional local paths in §3.3 match on id prefixes, not on failure, and no `.catch()` grep will find them. **The Phase 1 gate as written can pass with client-side grading fully intact.** |
| **D-5** | §0.3 lists client evaluation in `services/learning.ts` only | It is in **three** services — `learning.ts:107`, `practice.ts:69`, `toddler.ts:80` — plus two whole routes (`word-coach`, `sentence-coach`) that score and persist independently. |
| **D-6** | `/word-coach` and `/sentence-coach` | **Absent from the entire spec.** Two child-facing, self-scoring, `localStorage`-persisting routes appear in no migration table and no phase. They need a decision: migrate, or delete. |
| **D-7** | FE Phase 3: "delete `data/prototype.ts` entirely" | ~Half its exports (`pathAccents`, `learningWorlds`, `stageTokens`, `linearAdventurePath`) are **presentation data with no backend home** (§6). Deleting wholesale loses the visual design. |
| **D-8** | FE Phase 0 item 8: per-route bundle sizes from `next build` | Next 16.3 + Turbopack **does not emit them** (§8). The §1.3 budgets need a different enforcement mechanism before Phase 8. |
| **D-9** | §4.4: delete `POST /companion/session/start` and `POST /speech/synthesize` | The **web client is the only consumer of both** (backend audit §6). They cannot be removed backend-side until FE Phase 3 and 7 land. Sequencing dependency, not a conflict. |
| **D-10** | §0.5: cookie-based refresh is "not in the backend spec yet" | Confirmed — `docs/backend-architecture.md` §3.1/§7.4 has no cookie path, and the backend spec text available here is **truncated at Phase 4**, so BE Phases 5–9 cannot be checked at all. **FE Phase 2 is blocked** until this is added and BE Phase 2 ships. |
| **D-11** | `CLAUDE.md`: "No real database, OAuth, payments … or real personal data" | Both specs now require Postgres, verifiable parental consent, and stored child data. The project instructions contradict the specs and need updating alongside Phase 1. |

**Checked and found accurate:** §2.3's claim that the mobile app already uses React Query —
`mobile/package.json:12` pins `@tanstack/react-query` ^5.101.4 and 8 files under `mobile/src`
import it (alongside Zustand for client state). The "one mental model across clients"
rationale holds.

---

## 11. FE Phase 0 acceptance

| Criterion | Status |
|---|---|
| All 21 `.catch()` fallbacks documented with substituted payload | ✅ All **29** documented and classified (§3); 23 fabricate |
| Client-side evaluation in `services/learning.ts` documented line by line | ✅ §4.1, plus two further services and two routes the spec omits |
| Every component has exactly one verdict | ✅ 30 files — KEEP 9, ADAPT 13, REPLACE 5, DELETE 3 |
| Baseline bundle sizes recorded | ⚠️ Aggregates recorded; **per-route figures unobtainable** on Next 16.3 + Turbopack (§8, D-8) |
| Baseline axe violation counts recorded | ❌ **Not run** — requires adding dev dependencies, which this phase forbids (§9). Static baseline provided instead |
| Zero source files modified | ✅ Only `.next/` build output (gitignored) was written |

**Two acceptance criteria are not fully met, both for the same reason:** they require tooling
this phase is not allowed to install. Neither blocks FE Phase 1. Both block FE Phase 8, and
**D-8 in particular needs a decision** — the §1.3 bundle budgets currently have no way to be
measured, let alone enforced in CI.

**The single most important finding is D-4:** FE Phase 1's acceptance gate is a `.catch()`
grep, and the client-side grading does not live behind `.catch()`. Phase 1 can pass its gate
with the child still being graded in the browser. The gate needs to add the §3.3 checks —
`grep -rn "correct_answer" frontend/services` and a sweep for `local-child` / `guest_child` /
`local-practice` / `local-toddler` id-prefix branches.
