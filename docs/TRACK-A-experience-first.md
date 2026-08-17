# Track A — Experience First

**No authentication. No database. State stays session-scoped, exactly as it is today.**
**Focus: responsive on every device · a production-grade AI workflow · a website that runs itself.**

Version 1.0 · 2026-08-14
Supersedes the ordering in `EXECUTION.md` **for now**. Nothing in the other docs is wrong —
it is deferred.

---

## 0. The scope decision

| | Status |
|---|---|
| PostgreSQL, migrations, repositories | **Deferred** — `ops/OP-01-database.md` |
| Real auth, tokens, consent | **Deferred** — `ops/OP-02-authentication.md` |
| Backend state | **Unchanged** — in-memory, session-scoped, as it is today |
| Responsive on phone / tablet / desktop | **In scope** — A1 |
| Production-grade AI workflow | **In scope** — A4 |
| Hands-free automation + auto plan + manual choice | **In scope** — A5 |

This is a coherent strategy: prove the *experience* works before investing in persistence.
The AI workflow, the guided flow, and the responsive layout are the hard, differentiated
parts. Auth and Postgres are well-understood work that can slot in later without redesign —
**provided** the rule in §2 holds.

### Be clear-eyed about what session-scoped costs you

Say this out loud once so nobody is surprised later:

- Progress vanishes when the backend restarts or the browser session ends.
- The plan is **per session**, not per day. A multi-day schedule is not possible.
- Weak-skill detection works **within a session** only.
- No streaks — they need consecutive days.
- Certificates do not survive.

**This configuration is a demo, a pilot, and an investor build. It is not shippable to real
families**, because a child whose progress disappears will not come back. That is fine and
expected right now — just do not let it drift into a launch by accident.

---

## 1. What changes because there is no database

The daily plan becomes a **session plan**. Same shape, shorter horizon:

| Daily plan (later) | Session plan (now) |
|---|---|
| Generated once per day, frozen | Generated at session start, frozen for that session |
| Carries over from yesterday | No carry-over |
| Multi-day streaks | None |
| Mastery decays over 60 days | Mastery is per-session, no decay |
| `daily_plans` table | In-memory `SessionPlan` object |

Everything else — the two adventure levels, the practice block drawn from exactly what those
levels taught, the deterministic selection rules — works identically. When Postgres lands,
this becomes a table write and a date key. **Write it as a service with a repository
interface now**, and that migration is an afternoon rather than a rewrite.

---

## 2. The one rule that must not bend

> **The backend is the single source of truth, even though that truth is volatile.**

Volatile is fine. Two sources of truth is not.

Today the browser keeps its own copy in `sessionStorage` and — inside the `.catch()` block in
`services/learning.ts` — grades the child, awards stars, and writes progress. That must go,
**even in this mode**, for three reasons:

1. It is the bug that produces wrong progress.
2. Every step below assumes the server decides; building on a client that also decides means
   building twice.
3. It is precisely the work that makes the later database migration cheap.

So: backend keeps its in-memory store exactly as it is. The frontend stops keeping a parallel
copy and stops deciding anything. One source of truth, just an impermanent one.

---

## 3. Run order

| Step | What | Prompt |
|---|---|---|
| **A0** | One source of truth — API client, delete all 25 fallbacks | §4 |
| **A1** | Mobile + tablet responsive | `ops/OP-06-responsive.md` |
| **A2** | Session plan engine — 2 adventure levels + matching practice | §5 |
| **A3** | Entry flow — straight into the adventure | §6 |
| **A4** | Production-grade AI workflow | §7 |
| **A5** | Hands-free automation, with manual override | §8 |
| **A6** | One activity renderer + missing screens | `upgrade-plan.md` W4b, W4c |
| **A7** | Accessibility, performance, end-to-end | §9 |

A0 first — everything else assumes it. A1 is independent and can run in parallel with
anything. A4 before A5, because automation driven by an unreliable guide is worse than no
automation.

**One step per session.**

---

## 4. Step A0 — One source of truth

**Fixes:** client grading · fabricated logins · 25 silent fallbacks · no error handling

> **Prompt — A0**
>
> Read `docs/frontend-architecture.md` §0.3 and §3.5, `docs/frontend-audit.md`, and
> `docs/TRACK-A-experience-first.md` §2. **Do not add a database and do not add
> authentication** — the backend keeps its current in-memory session-scoped state.
>
> Make the backend the single source of truth for the session. Create `lib/apiClient.ts` as
> the only place in the web app that calls `fetch`, with a configurable per-call timeout (not
> the current `path.startsWith("/agent/")` prefix hack), exponential-backoff retry for
> timeouts, network errors and 5xx only, parsing of `{error:{code,message,request_id}}` into a
> typed `ApiError` carrying `code`, `status`, `requestId` and a child-safe `childMessage`, a
> generated `X-Request-ID` per request, and an `Idempotency-Key` on every mutating request
> that is reused when the same logical operation is retried.
>
> Then delete every silent fallback — 21 in `frontend/services/` and 4 more in
> `app/certificate`, `app/levels`, `AIAvatar.tsx` and `ToddlerLesson.tsx`. Do not replace them
> with anything; failures must surface. In particular **delete the entire `.catch()` body of
> `answerLearning()` in `services/learning.ts`**, which currently normalizes the answer,
> compares it to `activity.correct_answer`, computes correctness, awards stars and writes
> `path_progress` and `certificate_unlocked` into `sessionStorage`. No browser code may
> compute correctness, score, stars, attempt number, step index or unlock state after this
> step. Delete the fabricated-session fallbacks in `services/auth.ts` too — a failed request
> must show a real error, never `local-session-${Date.now()}`.
>
> Stop mirroring server state in `sessionStorage`. Keep only what genuinely belongs to the
> browser: the active child id and UI preferences. Add React Query for server state, with
> `refetchOnWindowFocus` disabled on the child surface so a session is never interrupted. Add
> an error boundary per route group and a lint rule failing the build on `fetch(` outside
> `lib/apiClient.ts` — this catches the two current offenders, `services/speech.ts:140` and
> `AIAvatar.tsx:45`.
>
> Prove it: `grep -rn "\.catch("` across `services/`, `app/` and `components/` returns no
> fallback results; `grep -rn "correct_answer"` finds nothing outside type definitions; and
> with the backend stopped, every route renders an honest retry state with zero fabricated
> content — walk each route and show it.

---

## 5. Step A2 — Session plan engine

Two adventure levels plus practice of exactly what those levels taught — generated
deterministically, frozen for the session.

**Generation, in order:**

```
S1  REVISE   (max 1, conditional)
    Any skill in this session's mastery with score < 0.40 attempted more than
    10 minutes ago → a 4-question block on it. Skip on a fresh session.

S2  ADVENTURE A
    An open session step if one exists, else the next incomplete lesson in the
    child's current level.

S3  ADVENTURE B
    The lesson after A. If the level ends at A, the first lesson of the next
    unlocked level. If nothing further is unlocked, a revise lesson.

S4  PRACTICE
    skill_ids = union of the skills taught in A and B          ← this is the requirement
    6 questions drawn from questions already attempted in those skills,
    weighted weak ×3, learning ×2, mastered ×1.
    Too few attempted → top up from unseen and mark the block "preview".

S5  FIT
    90 s per adventure activity, 30 s per practice question.
    Trim from the end while the estimate exceeds the target; never below one
    adventure slot. A plan is never empty.

S6  FREEZE
    Held for the whole session. It does not reshuffle on navigation or refresh.
```

Seed the weighted draw from the session id so the same session always yields the same
questions — otherwise it reshuffles and nothing is testable.

> **Prompt — A2**
>
> Read `docs/ops/OP-05-ai-tracking.md` §3 and `docs/TRACK-A-experience-first.md` §1 and §5.
> Build the **session** plan engine in the existing in-memory backend — **no database, no new
> tables.**
>
> Implement a `SessionPlan` service behind a repository interface (`SessionPlanRepository`)
> with an in-memory implementation, so that swapping to Postgres later is a new
> implementation of that interface and nothing else. Generate the plan with steps S1–S6 in
> §5 exactly: an optional revise block for any skill scoring under 0.40; two adventure
> lessons chosen from the child's current level and progression; and a practice block whose
> skills are **the union of the skills taught in those two adventure lessons**, drawing 6
> already-attempted questions weighted weak ×3 / learning ×2 / mastered ×1, marking
> `"preview"` when topping up from unseen questions. Fit to the target minutes by trimming
> from the end, never below one adventure slot. Seed the weighted draw from the session id so
> generation is reproducible. Freeze the plan for the session — it must not reshuffle on
> navigation or refresh.
>
> Track per-skill mastery in memory for the session using the EWMA and bands from
> `OP-05-ai-tracking.md` §2 — outcome 1.0 / 0.6 / 0.3 / 0.0 by attempt index, alpha 0.30 below
> 5 attempts then 0.15, mastered at ≥0.75 with at least 4 attempts. Skip time decay; there is
> no multi-day horizon yet.
>
> Expose `GET /session/plan`, and a manual override endpoint that lets a specific lesson be
> chosen instead, replacing the plan's next adventure slot without discarding the rest.
>
> Test: the same session id produces an identical plan across 100 runs; the practice block's
> skills exactly equal the union of the two adventure lessons' skills; trimming never empties
> the plan; a fresh child with no history gets a valid plan; and the mastery fixture table
> from `OP-05` §2 reproduces exactly — four first-try correct answers reach 0.760 and
> mastered, three reach 0.657 and do not.

---

## 6. Step A3 — Entry flow without auth

Without accounts, "logged in" becomes "has an active child profile in this session".

| Has active child? | Age | Lands on |
|---|---|---|
| No | — | `/` — guest home: showcase, how it works, start |
| No, but starting | — | `/onboarding` — name + age, once |
| Yes | under 3 | `/adventure` — toddler presentation |
| Yes | 3+ | `/adventure` — standard presentation |

Same shape as `ops/OP-03-entry-flow.md`; the auth check is simply replaced by an
active-child check, so the later swap is one predicate.

> **Prompt — A3**
>
> Read `docs/ops/OP-03-entry-flow.md` and `docs/TRACK-A-experience-first.md` §6. **Do not add
> authentication.** Implement the entry flow using "has an active child profile in this
> session" wherever OP-03 says "authenticated", so that swapping in real auth later changes
> one predicate.
>
> Add a `GET /session/bootstrap` endpoint returning the active child, the resolved
> `experience_mode`, and a `landing` object with the route and a `reason` from the closed set
> `guest · needs_onboarding · resume_session · session_plan · next_lesson`. Route from that
> response on the client and never compute the landing route in the browser.
>
> `app/page.tsx` currently renders `<AgeGate />` for everyone — make it the guest home, shown
> only when there is no active child. Demote `AgeGate` to an onboarding step so age is asked
> once, not on every visit. Collapse the toddler stack: delete `app/toddler/page.tsx`,
> `components/toddler/ToddlerExperience.tsx`, `ToddlerHome.tsx`, `ToddlerLesson.tsx`,
> `services/toddlerGuide.ts` and `services/toddlerVoice.ts`, redirect `/toddler` to
> `/adventure`, and make toddler a presentation mode on the shared components changing text
> density, touch-target size (≥96px vs ≥64px), choice count and pacing. Restructure into
> `(child)` and `(parent)` route groups; the child surface renders **no navigation bar** at
> any breakpoint.
>
> Test every row of the §6 table, and assert `/adventure` resumes an in-progress session at
> the exact step from three different points.

---

## 7. Step A4 — Production-grade AI workflow

"Production-grade" means specific things. All of these are achievable with no database.

| Concern | Requirement |
|---|---|
| Provider abstraction | A `Protocol` with a Groq implementation behind it; a second provider is a new class, not an orchestration change |
| Timeouts | 4 s hard, one retry |
| Circuit breaker | 5 consecutive failures, or >50% errors over 20 calls in 60 s → open 30 s → half-open probe |
| Budget | 12 LLM calls per session; beyond that, templates |
| Policy routing | A first-attempt wrong answer uses the **authored hint**, not the model. A correct answer uses a template. Roughly 60% of naive calls disappear. |
| Structured output | Strict schema; unknown fields rejected |
| Action allowlist | Closed set; anything else dropped |
| Target allowlist | Live registry — only currently-mounted targets |
| Safety validation | No shaming, no PII solicitation, no URLs, ≤220 chars |
| Injection resistance | Child text inserted as a quoted data block, never concatenated into instructions; system policy restated after user content |
| Fallback | Every event has a deterministic template. The product works fully with the LLM switched off. |
| Prompt versioning | Version recorded on every call |
| Observability | Latency, outcome, fallback rate, validation-failure rate, estimated cost — **never prompt or completion text** |
| Red-team suite | ≥100 adversarial cases committed as tests |

> **Prompt — A4**
>
> Read `docs/backend-architecture.md` §5 in full and `docs/TRACK-A-experience-first.md` §7.
> Bring the AI workflow to production quality. **No database is needed for any of this** —
> keep counters and circuit state in memory behind an interface that Redis can implement later.
>
> Restructure the AI layer into `context.py` (builds minimal context from trusted state — age
> band, not age; no child name; no raw content), `policy.py` (decides template vs model),
> `providers/base.py` as a Protocol with `providers/groq.py` behind it, `validate.py`, and
> `templates.py`. Implement the policy table so a **first-attempt wrong answer uses the
> question's authored hint with zero model calls**, a correct answer uses a template, and the
> model is consulted only from the second attempt onward and for doubts.
>
> Enforce a 4-second timeout with one retry, a circuit breaker opening after 5 consecutive
> failures or a >50% error rate across 20 calls in 60 seconds and half-opening after 30
> seconds, and a 12-call budget per session. Validate every response against a strict schema,
> a closed action set, a live target registry, and safety rules covering shaming language, PII
> solicitation, URLs and a 220-character cap — on any failure fall back to a template and
> record the reason. Insert child-supplied text as a quoted data block and restate the system
> policy after it, never concatenating user text into the instruction section. Record
> provider, model, prompt version, latency, outcome and estimated cost — and **never** prompt
> or completion text.
>
> Then write the safety gate: at least 100 committed adversarial tests covering prompt
> injection through doubt text, PII solicitation, hallucinated targets, requests to leave the
> app, expressions of distress, and non-English injection — with **zero** responses that pass
> validation while violating the safety rules. Also prove that with the provider fully
> disabled a child can complete an entire session on templates alone, with zero 5xx.

---

## 8. Step A5 — Hands-free automation, with manual override

The child taps or speaks answers. Nothing else. The app drives itself — but a parent or an
older child can still choose.

**Automatic path (default):**

```
Arrive at /adventure
  → guide auto-speaks the greeting                      (template)
  → session plan item 1 opens automatically
  → guide reads the question aloud, highlights the target
  → child answers by voice or tap
  → correct   → celebrate → auto-advance after ~1.2 s
  → wrong     → idle/attempt ladder (A4 policy)
  → item done → guide announces the next, auto-opens it
  → plan done → celebration, then a calm ending. Nothing more offered.
```

**Idle ladder** — timers reset on any input; toddler thresholds longer:

| 3+ | Toddler | Guide does | Model? |
|---|---|---|---|
| 8 s | 12 s | Repeats the instruction | No |
| 18 s | 25 s | Hint + highlights the target | No |
| 30 s | 40 s | Simpler re-explanation | Yes |
| 45 s | 60 s | `demo_tap` — shows the tap **without submitting** | No |
| 60 s | 80 s | Offers to move on. Never traps the child. | No |

**Manual path (always available, never in the child's way):**

- A single "choose something else" control on the adventure screen — one tap, opens the
  world/level picker.
- The parent surface can pick a specific lesson, which replaces the plan's next adventure
  slot without discarding the rest.
- An auto-advance toggle in parent settings: on by default; off makes the child tap "next".
- Manual choice never breaks the plan — it substitutes into it.

**The rule:** automatic is the default and needs no discovery. Manual is one tap away and
needs no explanation.

> **Prompt — A5**
>
> A4 is complete, so the guide is reliable. Read `docs/ops/OP-04-ai-navigation.md` and
> `docs/TRACK-A-experience-first.md` §8. Make the website run itself for a pre-literate child,
> while keeping manual choice one tap away.
>
> Implement the automatic path in §8: on arriving at `/adventure` the guide auto-speaks within
> 500 ms and the first plan item opens with no interaction; the guide reads each question aloud
> and highlights the relevant target; a correct answer celebrates and auto-advances after about
> 1.2 seconds; finishing an item announces and auto-opens the next; finishing the plan shows a
> celebration and a calm ending and **offers the child nothing further**.
>
> Implement the idle escalation ladder with the exact thresholds in §8, longer in toddler mode,
> resetting on any input. **Only the third rung may call the model** — the rest are templates.
> Add a `demo_tap` action that renders a ghost-finger animation on a target to show the
> interaction **without submitting an answer**. The final rung must always let a child leave a
> question they cannot do.
>
> Apply the guided-flow rules: no child screen offers more than 4 tappable choices (2 in
> toddler mode); no control is text-only — every one carries an icon, a colour and a voice
> line; the child surface has no navigation bar. Give every voice failure mode a visible tap
> fallback present from the start, not behind a disclosure, and port the mic-gating from
> `mobile/src/features/voice/VoiceController.ts` so the microphone never opens while the guide
> is speaking, including the settle window after speech ends.
>
> Add the manual path: a single "choose something else" control on the adventure screen opening
> the world and level picker; a parent-surface lesson picker that substitutes into the plan's
> next adventure slot without discarding the rest; and an auto-advance toggle in parent
> settings, on by default.
>
> Verify with an end-to-end test that completes a full session using **voice and taps only,
> with zero reading and zero navigation**, and a second run with the model provider disabled
> that still completes on templates alone. Add a third test that exercises the manual path and
> asserts the plan substitutes rather than resets.

---

## 9. Step A7 — Accessibility, performance, end-to-end

> **Prompt — A7**
>
> Read `docs/frontend-architecture.md` §1 and `docs/ops/OP-06-responsive.md` §4. Harden the
> experience. Meet LCP ≤2.0 s, INP ≤150 ms and CLS ≤0.05 on a throttled 4G mid-tier Android
> profile, and keep first-load JS on the child home under 180 KB gzipped with a CI check that
> fails on regression. Reach **zero critical and zero serious axe violations** on every route
> at mobile width. Enforce touch targets of 96×96px in toddler mode, 64×64px on the child
> surface and 44×44px on the parent surface, with an automated check. Honour
> `prefers-reduced-motion` in every animation, keep nothing flashing above 3 Hz, and never lock
> zoom. Provide full keyboard traversal with visible focus on the parent surface.
>
> Write Playwright end-to-end coverage for: onboarding → adventure → answer → guide →
> practice → rewards; hands-free completion with zero navigation; the manual override path;
> resume after refresh; and chaos runs with the backend down, the backend slow at 3 seconds,
> and the guide provider unavailable — asserting **no fabricated content** in any of them.
> Commit the Lighthouse, axe and responsive screenshots to `docs/`.

---

## 10. What must still hold, even here

1. The client never computes correctness, score, stars, or unlocks.
2. No silent fallback to local mock data. A failure is visible.
3. The model never decides correctness, progression, or rewards.
4. Model output never reaches the UI without schema, action, target and safety validation.
5. No child-facing control smaller than 64 px.
6. A child is never trapped on a screen with no way forward.
7. No behavioural tracking SDK, no ad SDK.
8. `mobile/` is never modified.

---

## 11. When auth and the database land

Nothing here gets thrown away, provided §2 held:

| Track A | Becomes |
|---|---|
| In-memory backend store | Postgres repositories — the interface is already there |
| `SessionPlanRepository` in-memory impl | A `daily_plans` table write |
| Session-scoped mastery | The `skill_mastery` table, plus 60-day decay |
| Active-child predicate | The real `authenticated` check — one predicate |
| In-memory circuit and budget counters | Redis |
| Session plan | Daily plan, with carry-over and streaks |

That is the whole point of writing services behind interfaces now. Skip that, and this
becomes a rewrite instead of a migration.
