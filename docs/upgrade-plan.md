# Learn Kids — Upgrade Plan: Auth, Study Plan, Responsive & Feature Parity

**Companions:** `docs/backend-architecture.md` · `docs/frontend-architecture.md`
**This document does not repeat them.** It adds four workstreams and says exactly where
each one slots into the existing phase gates.
**Version:** 1.0 · 2026-08-13

---

## 0. What you asked for, and where it already lives

| Your ask | Status |
|---|---|
| Scan the repo | **Done** — `docs/backend-audit.md` exists; `docs/frontend-audit.md` is FE Phase 0 |
| Add authentication | **Already specified** — BE Phase 2 + FE Phase 2. See W1 below for the combined run. |
| Connect PostgreSQL | **Already specified** — BE Phase 1 (engine, Alembic) + BE Phase 2 (first tables) |
| Fully mobile-responsive web | **New** → **W2** |
| AI plans the child's study schedule from DB progress | **New** → **W3** |
| Mobile features ported to web, same-to-same | **New** → **W4** |

### Assumptions made (change these if wrong, before anyone starts)

1. The plan is **daily**, not weekly. Regenerated at the first visit each day.
2. **2 adventure levels + 1 practice block** is the default shape, but the plan shrinks to
   fit the parent's daily-minutes goal rather than always forcing 3 blocks.
3. Practice draws from the skills taught in **those two levels**, not a global mix.
4. The plan is **frozen for the day** — a refresh does not reshuffle it. A child who sees
   a different plan every time they reload never builds a routine.
5. **The LLM never picks the lessons.** It writes the day's title and greeting; everything
   about *what* is studied is deterministic. This follows the existing rule in `CLAUDE.md`
   and backend §0.2.
6. Parity means **web catches up to mobile**. `mobile/` is not modified.

### Ordering

```
W1 Auth + Postgres      ← BE Phase 1–2, FE Phase 2      (blocks everything else)
W2 Responsive           ← can start after FE Phase 1    (independent of backend)
W4 Feature parity       ← per-feature, tracks FE Phase 3–7
W3 Study plan           ← needs BE Phase 5 (mastery + recommendations) first
```

**W3 is last for a reason.** A study plan is a composition of mastery and recommendation
data. Building it before those exist means inventing the data it plans against — which is
exactly how you end up with an "AI planner" that is really a random lesson picker.

---

## W1 — Authentication & PostgreSQL

Fully specified already. Nothing new here except the run order.

- **Postgres engine, pooling, Alembic, migrations** → `docs/backend-architecture.md` Phase 1
- **`users`, `refresh_tokens`, `children`, `consent_records`; Argon2id; token rotation with
  family reuse-detection; `owned_child` returning 404** → Phase 2
- **Web token handling** → `docs/frontend-architecture.md` FE Phase 2

**Before starting, settle the one open item:** frontend spec §0.5 — the backend must set
the refresh token as an `HttpOnly; Secure; SameSite=Lax` cookie for web clients, because a
browser has no Keychain. If that is not agreed, the agent will put a 30-day refresh token
in `localStorage` and quietly undo the security work.

> **Prompt — W1**
>
> Execute `docs/backend-architecture.md` Phase 1, then Phase 2, then
> `docs/frontend-architecture.md` FE Phase 2 — in that order, stopping at each gate for
> review. Use the phase prompts written in those documents verbatim; do not improvise a
> combined plan. Before starting FE Phase 2, confirm the backend sets the refresh token as
> an `HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth` cookie when the request carries
> `X-Client: web`, per frontend spec §0.5 — if it does not, implement that on the backend
> first. Never store any token in `localStorage` or `sessionStorage`; if that appears to be
> the only way forward, stop and report instead.

---

## W2 — Full Mobile Responsiveness

### The actual problem

Measured in `frontend/`:

| Finding | Detail |
|---|---|
| **Desktop-first** | `app/globals.css` has 5 `@media` rules — 2 real breakpoints, both `max-width` (640px, 900px). The base styles assume a large screen and shrink down. |
| **Two conflicting breakpoint systems** | The CSS uses 640/900. Tailwind uses its defaults (640/768/1024/1280) because `tailwind.config.ts` defines **no** `screens`. They disagree at every width between 768 and 900. |
| **2,172 lines of hand-written CSS** | One file. Fixed `px` throughout — `18px` ×11, `22px` ×4, `60px` ×3, `46px`/`44px` ×2 each. No fluid scale. |
| **No safe-area handling** | Zero `env(safe-area-inset-*)`. On a notched phone the fixed avatar dock and backdrop will sit under the notch and home indicator. |
| **No landscape or tablet case** | Nothing distinguishes a rotated phone from a tablet. A child holding a tablet sideways is the single most common posture for this app. |
| **No `viewport` export** | `app/layout.tsx` sets `metadata` but no `viewport` — so no `viewportFit: "cover"`, no `themeColor`. |
| **Touch targets not enforced** | `44px` appears twice in 2,172 lines. Backend/frontend spec requires **≥64 px** for child controls. |
| **Decorative backdrop always mounted** | `day-sky-backdrop` with sun, 3 clouds and 2 bird layers renders on every route including mobile, where it costs paint budget and risks horizontal overflow. |

### Target system

**Mobile-first. `min-width` only. One breakpoint source of truth.**

```ts
// tailwind.config.ts — the ONLY place breakpoints are defined
screens: {
  xs: "380px",   // small phone
  sm: "480px",   // large phone
  md: "768px",   // tablet portrait
  lg: "1024px",  // tablet landscape / small laptop
  xl: "1280px",  // desktop
  landscape: { raw: "(orientation: landscape)" },
  short:     { raw: "(max-height: 480px)" },   // phone held sideways
  motion:    { raw: "(prefers-reduced-motion: no-preference)" },
}
```

**Bucket on the short edge**, the way the mobile app does. A 915×412 phone in landscape is
a *phone*, not a tablet — bucketing on width alone gets this wrong and hands a 4-year-old a
desktop layout.

**Fluid type and space.** Replace fixed px with `clamp()` tokens in
`theme.extend.fontSize` / `spacing`. One scale, no per-component magic numbers.

**Safe areas.** `viewportFit: "cover"` plus `env(safe-area-inset-*)` padding on anything
fixed — the avatar dock, any bottom bar, the offline banner.

```tsx
// app/layout.tsx
export const viewport: Viewport = {
  width: "device-width", initialScale: 1, maximumScale: 5,   // never lock zoom
  viewportFit: "cover", themeColor: "#f5b84b",
}
```

`maximumScale: 5` matters — locking zoom fails WCAG 1.4.4 and parents with low vision use
this app too.

**Touch targets.** A `.touch-target` utility enforcing `min-height/min-width: 64px` on the
child surface, 44px on the parent surface, with ≥12px gaps.

**Landscape rule for activities.** In `landscape short`, the activity view goes two-column
— question left, answer options right — so the answers stay above the fold without
scrolling. Scrolling mid-question is how a child loses their place.

**Decorative layer.** `day-sky-backdrop` renders only at `md:` and above, and only when
`prefers-reduced-motion: no-preference`. It is decoration; it should never cost a phone
frame budget.

### Device test matrix (all must pass)

| Device | Viewport | Must hold |
|---|---|---|
| iPhone SE | 320×568 | No horizontal scroll, all targets ≥64px |
| iPhone 14 | 390×844 | Safe areas respected, dock clear of home indicator |
| Pixel 7 | 412×915 | — |
| Phone landscape | 844×390 | Two-column activity, answers above fold |
| iPad portrait | 768×1024 | Not stretched — max content width |
| iPad landscape | 1024×768 | The primary tablet posture; must be excellent |
| Desktop | 1440×900 | Content capped, not a stretched phone layout |

**Hard rule: zero horizontal scroll at any width from 320px up.**

> **Prompt — W2**
>
> Read `docs/frontend-architecture.md` §1.4 and §2, and this document's W2 section. Convert
> the `frontend/` web app to a genuinely mobile-first responsive layout.
>
> Define breakpoints in exactly one place — `tailwind.config.ts` `screens` — as
> `xs:380 sm:480 md:768 lg:1024 xl:1280` plus raw `landscape`, `short (max-height:480px)`
> and `motion` variants. Then rewrite `app/globals.css` (currently 2,172 lines,
> desktop-first, with only `max-width: 640px` and `max-width: 900px` queries) to be
> mobile-first using `min-width` only, and delete every raw media query that duplicates a
> Tailwind breakpoint. Replace fixed pixel sizes with `clamp()`-based fluid type and spacing
> tokens in `theme.extend`; no component may carry its own magic numbers.
>
> Bucket layout decisions on the **short edge**, not width, so a phone in landscape is
> treated as a phone and not a tablet. Add a `useResponsive` hook exposing the current
> bucket and orientation, plus `AdaptiveStack`, `ResponsiveGrid` and `Show` helpers
> mirroring `mobile/src/components/responsive/`.
>
> Add a `viewport` export to `app/layout.tsx` with `width: device-width`, `initialScale: 1`,
> `maximumScale: 5` (never lock zoom — WCAG 1.4.4), `viewportFit: "cover"` and a
> `themeColor`. Apply `env(safe-area-inset-*)` padding to every fixed element including the
> avatar dock and any banner. Add a `.touch-target` utility enforcing 64×64px minimum on the
> child surface and 44×44px on the parent surface with at least 12px gaps, and apply it to
> every interactive control. In `landscape short`, lay activities out in two columns —
> question left, answers right — so answers never require scrolling. Render the
> `day-sky-backdrop` decorative layer only at `md:` and above and only under
> `prefers-reduced-motion: no-preference`.
>
> Verify with Playwright at 320×568, 390×844, 412×915, 844×390, 768×1024, 1024×768 and
> 1440×900: assert **zero horizontal scroll at every size**, every child-facing control at
> least 64×64px, no element overlapping a safe-area inset, and answer options visible
> without scrolling in phone landscape. Commit the screenshots to `docs/responsive/`.

---

## W3 — AI Study Plan Engine

### Design principle

> The plan is **computed**, the greeting is **generated**.

Which lessons a child does today is a deterministic function of their mastery, their
unlocked levels, and yesterday's plan. The LLM writes the day's title and one friendly
line, nothing more. This is the same rule as everywhere else in the system, applied to a
feature that superficially sounds like it needs AI judgement — and does not.

### Data model — one new table

**`daily_plans`** (table #18)

```
id, child_id (FK), plan_date DATE, status ('pending'|'in_progress'|'completed'|'skipped'),
items JSONB, target_minutes SMALLINT, estimated_minutes SMALLINT,
copy JSONB, carried_from_plan_id, generated_at, started_at, completed_at
UNIQUE (child_id, plan_date)
INDEX (child_id, plan_date DESC)
```

`items`:

```json
[
  { "slot": 1, "kind": "revise",    "skill_ids": ["letter_B_sound"], "question_count": 4,
    "status": "pending", "session_id": null, "reason": "weak_skill" },
  { "slot": 2, "kind": "adventure", "lesson_id": "...", "level_id": "...",
    "skill_ids": ["count_to_5"], "status": "pending", "session_id": null, "reason": "new_skill" },
  { "slot": 3, "kind": "adventure", "lesson_id": "...", "level_id": "...",
    "skill_ids": ["count_to_10"], "status": "pending", "session_id": null, "reason": "new_skill" },
  { "slot": 4, "kind": "practice",  "skill_ids": ["count_to_5", "count_to_10"],
    "question_count": 6, "status": "pending", "source": "seen", "reason": "continue" }
]
```

`copy`: `{ "title": "...", "intro": "...", "generated": true|false, "prompt_version": "..." }`

### Generation algorithm (deterministic, ordered, testable)

Runs once per child per day, on first request for today's plan.

```
INPUT   child, skill_mastery, unlocked_level_ids, yesterday's plan
TARGET  child.preferences.daily_goal_minutes  (default 12)

S1  CARRY-OVER
    If yesterday's plan exists, was for yesterday exactly, and has an
    incomplete adventure item → carry at most ONE into this plan.
    Items older than one day expire silently. Never guilt the child about it.

S2  REVISE BLOCK  (conditional, max 1)
    If recommendation rule R3 fires (any skill effective_mastery < 0.40 and
    last_attempt_at > 12h ago) → prepend a 4-question practice block on that skill.
    Reuse R3. Do not reimplement the weak-skill check.

S3  ADVENTURE SLOTS  (default 2)
    A = R2 if an open session exists, else the next incomplete lesson in the current level
    B = the lesson after A in the same level
        if the level ends at A     → first lesson of the next unlocked level
        if nothing further unlocked → a revise lesson, reason "revise"
    Reuse recommendation rules R1–R7 for both. The planner composes them; it
    does not invent a second progression system.

S4  PRACTICE BLOCK
    skill_ids = union of skills taught in A and B
    6 questions drawn ONLY from questions the child has already attempted in
    those skills, weighted: weak ×3, learning ×2, mastered ×1
    If fewer than 6 seen questions exist → top up from unseen questions in the
    same skills and mark the block source "preview"

S5  FIT TO TIME
    estimate = 90s per adventure activity + 30s per practice question
    While estimate > target_minutes × 1.25: drop from the END
      (practice questions first, then adventure slot B)
    Never drop below one adventure slot. A plan is never empty.

S6  FREEZE
    Persist. Do NOT regenerate on refresh, on re-login, or on navigation.
    Regenerate only on: date rollover, or an explicit parent request (max 1/day).
```

Weighted selection must be **seeded by `(child_id, plan_date)`** so it is reproducible —
the same child on the same day always gets the same questions, and the test suite can
assert exact output. Never call `random()` unseeded.

### What the LLM does (and does not)

| Does | Does not |
|---|---|
| Writes `copy.title` — ≤40 chars | Choose lessons |
| Writes `copy.intro` — ≤120 chars | Choose skills |
| — | Choose question count |
| — | Decide ordering |
| — | Decide completion or rewards |

**Input to the model:** only the display names of the skills already chosen, the child's
age band, and the locale. Nothing else.

**Validation:** length caps · no PII solicitation · no shaming · must not name a skill that
is not in the plan · no URLs. On any failure → template:
`"Today's adventure: {lesson_A_title} and {lesson_B_title}!"`

**Budget:** 1 call per plan per day, counted against the child's daily AI budget. If the
budget is exhausted or the circuit is open, the template is used and nothing about the
plan changes. The plan works perfectly with the LLM permanently switched off.

### Schedule & routine rules (kid-appropriate)

- `preferences.plan_days: [1,2,3,4,5]` — parent-set study days. No plan on off days.
- **No streak-shaming.** A missed day never produces guilt copy. The next plan opens with
  a plain welcome. Streaks are celebrated when present and silent when broken.
- **No countdowns, no deadlines** on the child surface.
- A completed plan shows a celebration and then **stops offering more** — "you're done for
  today!" A child-learning product that always asks for one more is a dark pattern.
- Parent may add an optional "bonus round" after completion; the child is never prompted.

### Endpoints

```
GET   /api/v1/plans/{child_id}/today          → generates on first call, then frozen
GET   /api/v1/plans/{child_id}/history?days=30
POST  /api/v1/plans/{child_id}/regenerate     → parent only, max 1/day
PATCH /api/v1/plans/{child_id}/preferences    → daily_goal_minutes, plan_days
```

Plan item status advances as a side effect of existing session completion — the planner
observes, it does not become a second source of truth about progress.

### Frontend: the child home becomes "Today's Plan"

- Three (or two, or four) cards in a vertical rail on mobile, horizontal on `lg:`.
- **Progressive disclosure:** the next item is full-colour and large; completed items
  collapse to a tick; later items are visible but dimmed. A child should see one obvious
  thing to do, with the shape of the day behind it.
- A progress ring for today's completion, and a streak flame **only when a streak exists**.
- Completed state is a real ending — celebration, then a calm "see you tomorrow".
- Parent dashboard: 30-day completion chart, goal setting, plan-day toggles, regenerate.

> **Prompt — W3 (backend)**
>
> Backend Phase 5 has passed its gate, so mastery and recommendation rules R1–R7 exist.
> Read `docs/backend-architecture.md` §4.3–§4.5 and §5, plus W3 in `docs/upgrade-plan.md`.
> Build the daily study plan engine.
>
> Add one table, `daily_plans`, exactly as specified in W3, with `UNIQUE (child_id,
> plan_date)`. Implement `services/plan_service.py` with the deterministic generator S1–S6
> from W3: carry over at most one incomplete adventure item from **yesterday only**; add a
> revise block by reusing recommendation rule R3 rather than reimplementing the weak-skill
> check; choose two adventure lessons by composing rules R1–R7; build a practice block from
> the union of skills taught in those two lessons, drawing 6 questions the child has already
> attempted, weighted weak ×3 / learning ×2 / mastered ×1, topping up from unseen questions
> and marking the block `"preview"` when there are too few; then fit to
> `preferences.daily_goal_minutes` by dropping from the end, never below one adventure slot.
> Seed the weighted selection with `(child_id, plan_date)` so it is fully reproducible —
> **no unseeded randomness anywhere**. Freeze the plan: it must not regenerate on refresh,
> re-login, or navigation.
>
> The LLM writes only `copy.title` (≤40 chars) and `copy.intro` (≤120 chars), receiving only
> the already-chosen skill display names, the age band and the locale. It must never choose
> lessons, skills, counts, or ordering. Validate the copy for length, shaming language, PII
> solicitation, URLs, and any skill name not present in the plan; on any failure use the
> template `"Today's adventure: {A} and {B}!"`. Budget it to one call per plan per day
> against the child's daily AI budget.
>
> Add `GET /plans/{child_id}/today`, `GET /plans/{child_id}/history`, `POST
> /plans/{child_id}/regenerate` (parent only, max 1/day) and `PATCH
> /plans/{child_id}/preferences` under `/api/v1`. Respect `preferences.plan_days` — generate
> no plan on off days.
>
> Test: the same child on the same date generates a byte-identical plan across 100 runs; a
> plan generated with the LLM disabled is identical except for `copy`; carry-over takes at
> most one item and only from yesterday; time-fitting never produces an empty plan; a
> completed plan does not regenerate; and a child with zero history still receives a valid
> first-day plan.

> **Prompt — W3 (frontend)**
>
> The backend now exposes `/api/v1/plans/*`. Read W3 in `docs/upgrade-plan.md` and
> `docs/frontend-architecture.md` §3.3 and §1.4. Rebuild the child home as "Today's Plan".
>
> Render the plan items as a vertical rail on mobile and horizontal from `lg:` up, using
> progressive disclosure: the next incomplete item is full-colour and large, completed items
> collapse to a tick, later items stay visible but dimmed — the child should see one obvious
> next action with the shape of the day behind it. Add a completion ring for today, and a
> streak flame **only when a streak actually exists**. Read every value from the server; the
> client computes nothing about plan state. When the plan is complete, show a real ending —
> celebration, then a calm "see you tomorrow" — and **do not offer more activities**; any
> bonus round is parent-initiated only. A missed day must produce no guilt copy anywhere.
> Build the parent dashboard view: 30-day completion chart, daily-minutes goal, study-day
> toggles, and a regenerate button limited to once per day. Handle the off-day case with a
> warm rest-day state rather than an empty screen.

---

## W4 — Mobile → Web Feature Parity

`mobile/` is the more complete client. This is web catching up. Nothing in `mobile/` changes.

### Parity matrix

**Screens**

| Mobile | Web today | Verdict |
|---|---|---|
| `GuestHomeScreen` — 12-feature showcase, how-it-works, age preview, parent benefits | — | **BUILD** |
| `FeatureDemoScreen` — scripted preview, works with the server down | — | **BUILD** |
| `ParentGateScreen` — written-word arithmetic gate | — | **BUILD** |
| `ParentDashboardScreen` | partial (`app/parent/profile`) | **BUILD** |
| `ParentSettingsScreen` | — | **BUILD** |
| `ParentProgressScreen` | `app/parent/progress` | **ADAPT** |
| `SessionRecapScreen` | — | **BUILD** |
| `StoryScreen` + `storyContent.ts` | — | **BUILD** |
| `ChildHomeScreen` | `app/home` | **ADAPT** → becomes Today's Plan (W3) |
| `ClassesScreen` / `ClassDetailScreen` | `app/levels`, `app/adventure` | **ADAPT** |
| `LessonScreen` | `app/levels/[pathId]/[stageId]` | **REFACTOR** into one renderer |
| `PracticeScreen` / `PracticeTopicScreen` | `app/practice` | **ADAPT** |
| `RewardsScreen` | `app/rewards` (client-state only) | **REBUILD** (FE Phase 5) |
| `CertificateScreen` | `app/certificate` | **ADAPT** |

**Activities** — mobile has one `ActivityRenderer` + 8 components; web has per-page logic.

| Mobile | Web today | Verdict |
|---|---|---|
| `ActivityRenderer` | scattered across pages | **BUILD** — one renderer, as in FE Phase 4 |
| `TapChoice` (text / glyph / swatch presentations) | partial in `LearningQuestion` | **REFACTOR** |
| `CountObjects` | partial | **REFACTOR** |
| `VoiceRepeat` | `VoiceLearningSession` | **REFACTOR** |
| `WordBuild` | `word-coach` (different concept) | **ADAPT** |
| `Introduce` | — | **BUILD** |
| `StoryListen` | — | **BUILD** |
| `TraceActivity` + `tracePaths` + `strokeScoring` | — | **BUILD** (port geometry as-is) |
| `FreeDraw` + `DrawingCanvas` | — | **BUILD** (Canvas + Pointer Events) |

**Guide / AI**

| Mobile | Web today | Verdict |
|---|---|---|
| `GuideTargetRegistry` (live, mount-aware) | `GUIDE_TARGETS` static const in `services/guide.ts` | **UPGRADE** |
| `guideSchema.ts` validator | inline, partial | **PORT** |
| `GuideActionExecutor` | inline | **PORT** |
| `GuideEventDispatcher` + `guideEvents.ts` | ad hoc calls | **PORT** |
| `DoubtOverlay` + `useHandRaise` | — | **BUILD** (FE Phase 6) |
| `shouldCallAgent()` (`mobile/src/ai/guideEvents.ts:100`) — skip the LLM on a first-try correct answer | — | **PORT** — real cost and latency win |

**Infrastructure**

| Mobile | Web today | Verdict |
|---|---|---|
| `OfflineBanner` | — | **BUILD** |
| `ErrorBoundary` | — | **BUILD** (FE Phase 1) |
| `StateViews` (loading / empty / error) | — | **BUILD** |
| `CelebrationOverlay` | CSS only | **ADAPT** |
| `GuideHighlight` | `VisualGuideRenderer` | **ADAPT** |
| theme tokens (colors, spacing, radius, shadows, typography, animations, breakpoints) | 2,172-line `globals.css` | **REPLACE** (W2) |
| `components/responsive/` | — | **BUILD** (W2) |
| `config/featureFlags.ts` | — | **BUILD** |
| `i18n/strings.ts` | hardcoded copy | **SCAFFOLD** — extract strings, one locale |
| `services/analytics` + `crash` | — | **BUILD** — first-party only, no ad SDK |
| `services/audio/haptics` | — | **ADAPT** — Vibration API, feature-detected |
| `services/audio/stt`, `tts` | `services/speech.ts` | **ADAPT** |
| `services/storage/secureStore`, `kv` | `sessionStorage` | **REPLACE** (FE Phase 2) |
| 6 zustand stores | none | **NOT PORTED** — React Query + context is enough on web |

**Web-only — keep, do not delete**

`sentence-coach` · `word-coach` · the adventure map · the Rive avatar · the day-sky backdrop.
Mobile does not have these. Parity is one-directional.

### Two things worth copying verbatim

1. **`shouldCallAgent()`** — mobile skips the LLM when a child gets it right first try, and
   only consults the agent on a correct answer that took 2+ attempts. That matches backend
   §5.2 and removes latency from the most time-sensitive moment in the app.
2. **The double-checked safe-route allowlist** — mobile validates `open_safe_route` in the
   validator *and* again in the executor. Port that shape exactly; it is the reason no
   future caller can reach navigation without passing the allowlist.

> **Prompt — W4a: shared UI foundation**
>
> Read `docs/upgrade-plan.md` W4 and `docs/frontend-architecture.md` §2. Port the shared UI
> foundation from `mobile/src` to the `frontend/` web app. Build web equivalents of
> `components/common/` — `Button`, `Card`, `Text`, `Screen`, `ProgressBar`, `StarRow`,
> `CelebrationOverlay`, `OfflineBanner`, `StateViews` (loading / empty / error) and
> `GuideHighlight` — and `components/cards/` (`FeatureCard`, `LevelNode`), matching the
> mobile visual language and using the W2 responsive tokens. Add `config/featureFlags.ts`,
> an `i18n/strings.ts` scaffold with every hardcoded child-facing string extracted into it
> for a single locale, first-party `services/analytics` and `crash` modules with **no
> third-party ad or behavioural-tracking SDK**, and a feature-detected haptics helper using
> the Vibration API that degrades silently where unsupported. Do not port the six zustand
> stores — React Query plus context covers this on web. Do not modify anything in `mobile/`.

> **Prompt — W4b: activity renderer and new activity types**
>
> Frontend Phase 4 has passed its gate, so sessions are server-authoritative. Read
> `docs/upgrade-plan.md` W4 and study `mobile/src/activities/`. Build a single
> `ActivityRenderer` for the web that dispatches on activity type, and implement all eight
> activity components as web equivalents of the mobile ones: `TapChoice` with `text` /
> `glyph` / `swatch` presentations (do not build three near-identical components),
> `CountObjects`, `VoiceRepeat`, `WordBuild`, `Introduce`, `StoryListen`, `TraceActivity`
> and `FreeDraw`. Port `mobile/src/features/tracing/tracePaths.ts` and `strokeScoring.ts`
> as-is — the geometry is deterministic and must stay that way, never an LLM call. Build
> `DrawingCanvas` on HTML Canvas with Pointer Events so mouse, touch and stylus all work and
> no stroke is dropped mid-draw; post only `{completed, accuracy}` to the backend. Refactor
> the existing per-page question logic in `app/levels/[pathId]/[stageId]` and the practice
> pages onto this one renderer so learning and practice share it entirely. Every control
> must meet the 64×64px touch-target rule from W2.

> **Prompt — W4c: missing screens**
>
> Read `docs/upgrade-plan.md` W4 and study the corresponding screens in
> `mobile/src/screens/`. Build the web screens that have no equivalent today: a **guest
> home** showcasing the twelve learning features from `mobile/src/features/catalog.ts`
> (the file holds fourteen entries — the last two, `toddler` and `early`, are experience
> modes, not features) with how-it-works, an age preview and parent benefits; a **feature
> demo** that is fully
> scripted and works with the backend down; a **parent gate** using written-word arithmetic
> that an adult can read but a pre-reader cannot; a **parent dashboard** and **parent
> settings**; a **session recap** shown after a lesson completes; and a **story screen**
> driven by `mobile/src/features/stories/storyContent.ts` until a backend stories endpoint
> exists. Six features in the catalog (`words`, `sentences`, `speaking`, `drawing`,
> `tracing`, `stories`) have no backend path — render them honestly with a "practice
> activity today, full levels coming" state exactly as the mobile app does, never a failure.
> Reuse the W4a components throughout; build nothing bespoke that already exists there.

> **Prompt — W4d: guide parity**
>
> Frontend Phase 6 has passed its gate. Read `docs/upgrade-plan.md` W4 and study
> `mobile/src/ai/`. Bring the web guide layer to parity: convert the static `GUIDE_TARGETS`
> constant in `services/guide.ts` into a live, mount-aware `GuideTargetRegistry`; port
> `guideSchema.ts`, `GuideActionExecutor`, `GuideEventDispatcher` and `guideEvents.ts` as
> separate modules so execution is unreachable without validation; and port
> `shouldCallAgent()` so a first-try correct answer never calls the LLM and only a correct
> answer that took 2+ attempts consults the agent. Port the **double-checked** safe-route
> allowlist exactly as mobile implements it — validated once in the schema layer and again
> in the executor — with auth, parent and destructive routes absent from the allowlist.
> Build the hand-raise flow from `mobile/src/features/guide/` (`DoubtOverlay`,
> `useHandRaise`) so it pauses the session without unmounting and resumes the exact step.

---

## Definition of Done (this document only)

**W1**

- [ ] BE Phase 1 + 2 gates passed; FE Phase 2 gate passed.
- [ ] Refresh token in an HttpOnly cookie; zero tokens in browser storage.

**W2**

- [ ] Breakpoints defined in exactly one place; zero duplicated media queries.
- [ ] Zero horizontal scroll at every width from 320px up (Playwright-asserted).
- [ ] Every child-facing control ≥64×64px, automated.
- [ ] Safe-area insets respected on notched devices; zoom not locked.
- [ ] Phone-landscape activity view shows answers without scrolling.
- [ ] All 7 device sizes pass; screenshots in `docs/responsive/`.

**W3**

- [ ] The same child on the same date produces a byte-identical plan across 100 runs.
- [ ] A plan generated with the LLM disabled differs only in `copy`.
- [ ] The plan does not regenerate on refresh, re-login, or navigation.
- [ ] Carry-over takes at most one item, and only from yesterday.
- [ ] A child with no history gets a valid first-day plan.
- [ ] A completed plan ends the day; no "one more" prompt to the child.
- [ ] No guilt copy for a missed day, anywhere, in any state.

**W4**

- [ ] Every matrix row is BUILT, ADAPTED, or explicitly deferred with a reason.
- [ ] One `ActivityRenderer` serves both learning and practice.
- [ ] Trace scoring is deterministic geometry — never an LLM call.
- [ ] `shouldCallAgent()` ported; a first-try correct answer makes zero LLM calls.
- [ ] Safe routes double-checked; auth and parent routes unreachable from model output.
- [ ] Web-only features (`sentence-coach`, `word-coach`, adventure map, Rive avatar) intact.
- [ ] `mobile/` unmodified — `git diff --stat mobile/` is empty.

---

## Appendix — Prompt Order

| # | Prompt | Blocked by |
|---|---|---|
| 1 | W1 — auth + Postgres | — |
| 2 | W2 — responsive | FE Phase 1 |
| 3 | W4a — shared UI foundation | W2 |
| 4 | W4b — activity renderer | FE Phase 4 |
| 5 | W4c — missing screens | W4a |
| 6 | W4d — guide parity | FE Phase 6 |
| 7 | W3 backend — plan engine | BE Phase 5 |
| 8 | W3 frontend — Today's Plan | W3 backend + W4a |

One prompt per session. Never two.
