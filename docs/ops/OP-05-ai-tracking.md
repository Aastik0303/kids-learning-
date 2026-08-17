# OP-05 — Per-Child AI Tracking & Scheduled Study Plan

**Goal:** the system knows each individual child — what they know, how fast they work, what
they struggle with — and turns that into a daily study plan: two adventure levels plus
practice of exactly what those levels taught.
**Blocked by:** OP-01, and the session engine (`backend-architecture.md` Phase 4–5)
**Touches:** `backend/` + `frontend/`

---

## 1. The design principle

> The plan is **computed**. The greeting is **generated**.

Which lessons a child does today is a deterministic function of their mastery, their
unlocked levels, their pace, and yesterday's plan. The LLM writes the day's title and one
friendly line — nothing more.

This is not a limitation. A planner whose output changes because a model felt different
today is a planner no parent can trust and no test can verify. Determinism is what makes it
schedulable.

---

## 2. Two new tables

### `skill_mastery` already exists — this is what tracks *knowledge*

Per `(child_id, skill_id)`: EWMA of outcomes with lazy time decay.

```python
def outcome(attempt_index, is_correct):
    if not is_correct:      return 0.0
    if attempt_index == 1:  return 1.0     # knew it
    if attempt_index == 2:  return 0.6     # worked it out
    return 0.3                             # got there eventually

alpha = 0.30 if attempts_total < 5 else 0.15
mastery_raw += alpha * (outcome - mastery_raw)

# decay at read time — no cron, no drift
effective = mastery_raw * (0.5 ** (days_since_last_attempt / 60))
```

Bands: `weak < 0.40` · `learning 0.40–0.749` · `mastered ≥ 0.75 and attempts_total ≥ 4`.

Four consecutive first-try correct answers reaches 0.760 — mastered. Three reaches 0.657 —
not yet. The constants are tuned to exactly that, and the table below is the test fixture:

| Attempt | `mastery_raw` | Band |
|---|---|---|
| 1 | 0.300 | weak |
| 2 | 0.510 | learning |
| 3 | 0.657 | learning |
| 4 | **0.760** | **mastered** |

### `learner_profiles` — new. This tracks *behaviour*, not knowledge

```
child_id PK, avg_session_minutes NUMERIC, avg_attempts_to_correct NUMERIC,
completion_rate NUMERIC, preferred_activity_types TEXT[], best_hour_local SMALLINT,
help_requests_7d INT, abandon_rate_7d NUMERIC, updated_at
```

Recomputed nightly by the worker from `attempts`, `sessions` and `doubts`. **Every field is
a deterministic aggregate — no model involved.** This is what lets the plan adapt to a
child's pace rather than only their correctness, and it is the difference between "adaptive
learning" as a slogan and as a mechanism.

### `daily_plans` — the scheduled plan

```
id, child_id, plan_date DATE, status, items JSONB, target_minutes,
estimated_minutes, copy JSONB, carried_from_plan_id, generated_at, started_at, completed_at
UNIQUE (child_id, plan_date)
```

```json
"items": [
  {"slot":1,"kind":"revise","skill_ids":["letter_B_sound"],"question_count":4,"reason":"weak_skill"},
  {"slot":2,"kind":"adventure","lesson_id":"...","skill_ids":["count_to_5"],"reason":"new_skill"},
  {"slot":3,"kind":"adventure","lesson_id":"...","skill_ids":["count_to_10"],"reason":"new_skill"},
  {"slot":4,"kind":"practice","skill_ids":["count_to_5","count_to_10"],"question_count":6,"source":"seen"}
]
```

---

## 3. Generation — S1 to S6, deterministic and ordered

Runs once per child per day, on the first request for today's plan.

```
S1  CARRY-OVER
    Yesterday's plan, if it is exactly yesterday's and has an incomplete adventure item
    → carry ONE forward. Older items expire silently, with no guilt copy.

S2  REVISE BLOCK  (max 1, conditional)
    If recommendation rule R3 fires — any skill with effective < 0.40 whose last attempt
    was more than 12 hours ago — prepend a 4-question block on it.
    Reuse R3. Do not reimplement the weak-skill check.

S3  ADVENTURE SLOTS  (2 by default)
    A = open session if one exists (R2), else the next incomplete lesson in the current level
    B = the lesson after A
        level ends at A          → first lesson of the next unlocked level
        nothing further unlocked → a revise lesson, reason "revise"
    Compose rules R1–R7. Do not invent a second progression system.

S4  PRACTICE BLOCK
    skill_ids = union of skills taught in A and B          ← "what the level taught"
    6 questions drawn only from questions already attempted in those skills,
    weighted weak ×3, learning ×2, mastered ×1
    Too few seen questions → top up from unseen, mark source "preview"

S5  FIT TO TIME
    estimate = 90 s per adventure activity + 30 s per practice question
    Target from preferences.daily_goal_minutes, adjusted by learner_profiles.avg_session_minutes
    Drop from the END while estimate > target × 1.25 — practice first, then slot B
    Never drop below one adventure slot. A plan is never empty.

S6  FREEZE
    Persist. Never regenerate on refresh, re-login, or navigation.
    Regenerate only on date rollover, or an explicit parent request (max 1/day).
```

**Seed the weighted selection with `(child_id, plan_date)`.** The same child on the same day
must always get the same questions — otherwise the plan reshuffles on every reload and the
test suite cannot assert anything. No unseeded `random()` anywhere.

---

## 4. What the LLM may and may not do

| May | May not |
|---|---|
| Write `copy.title` — ≤40 chars | Choose lessons |
| Write `copy.intro` — ≤120 chars | Choose skills or question counts |
| — | Decide ordering |
| — | Decide completion, rewards, or unlocks |

**Input:** only the display names of the already-chosen skills, the age band, and the locale.

**Validation:** length caps · no shaming · no PII solicitation · no URLs · must not name a
skill absent from the plan. On any failure → template:
`"Today's adventure: {lesson_A_title} and {lesson_B_title}!"`

**Budget:** one call per plan per day, against the child's daily AI budget. With the LLM
switched off entirely, the plan is byte-identical except for `copy`.

---

## 5. Schedule rules that are about children, not software

- `preferences.plan_days` — parent-set study days. No plan on off days; a warm rest-day
  state, not an empty screen.
- **No streak-shaming.** A missed day produces no guilt copy anywhere, in any state. Streaks
  are celebrated when present and silent when broken.
- **No countdowns or deadlines** on the child surface.
- **A completed plan ends the day.** Celebration, then "see you tomorrow" — and the app
  stops offering more. A children's product that always asks for one more session is a dark
  pattern. Any bonus round is parent-initiated only.

---

## 6. Frontend — the adventure screen is the plan

Per OP-03, `/adventure` is where every logged-in child lands. That screen shows today's plan:

- Vertical rail on mobile, horizontal from `lg:` up.
- **Progressive disclosure:** the next incomplete item is full-colour and large; completed
  items collapse to a tick; later items stay visible but dimmed. One obvious next action,
  with the shape of the day visible behind it.
- A completion ring for today. A streak flame **only when a streak exists**.
- Parent dashboard: 30-day completion chart, daily-minutes goal, study-day toggles,
  regenerate (once daily), and the learner profile in plain language — "works best in
  short bursts", "prefers tapping to speaking".

Every value is read from the server. The client computes nothing about plan state.

---

## 7. Acceptance criteria

- [ ] The same child on the same date produces a **byte-identical plan across 100 runs**.
- [ ] A plan generated with the LLM disabled differs **only** in `copy`.
- [ ] The plan does not regenerate on refresh, re-login, or navigation.
- [ ] Carry-over takes at most one item, and only from yesterday.
- [ ] The practice block's skills are exactly the union of the skills taught in the two adventure slots — tested.
- [ ] Practice questions are drawn from already-attempted questions; the `"preview"` flag appears only when there are too few.
- [ ] Time-fitting never produces an empty plan, and never drops below one adventure slot.
- [ ] A child with zero history receives a valid first-day plan.
- [ ] `learner_profiles` fields are all deterministic aggregates — no model call in the nightly job.
- [ ] Mastery matches the §2 fixture table exactly: four first-try correct answers reach 0.760 and mastered; three reach 0.657 and do not.
- [ ] Decay: `mastery_raw = 0.8` untouched for 60 days yields `effective = 0.400`.
- [ ] No unseeded randomness anywhere in plan generation — grep-verified.
- [ ] A completed plan shows an ending and offers the child nothing further.
- [ ] No guilt copy for a missed day, in any state.
- [ ] `GET /plans/{child_id}/today` responds within 300 ms p95 for a child with 5,000 attempts.

---

## 8. Prompt — backend

> The session engine, mastery and recommendation rules R1–R7 exist. Read
> `docs/ops/OP-05-ai-tracking.md`, plus `docs/backend-architecture.md` §4.3–§4.5 and §5.
>
> Add two tables: `learner_profiles` (per-child behavioural aggregates as specified in §2)
> and `daily_plans` with `UNIQUE (child_id, plan_date)`. Add a nightly worker job that
> recomputes `learner_profiles` from `attempts`, `sessions` and `doubts` — every field a
> deterministic aggregate, **no model call**.
>
> Implement `services/plan_service.py` with the S1–S6 generator in §3 exactly: carry at most
> one incomplete adventure item from yesterday only; add a revise block by **reusing
> recommendation rule R3** rather than reimplementing the weak-skill check; select two
> adventure lessons by composing R1–R7; build the practice block from the **union of skills
> taught in those two lessons**, drawing 6 already-attempted questions weighted weak ×3 /
> learning ×2 / mastered ×1 and marking `"preview"` when topping up from unseen; then fit to
> `daily_goal_minutes` adjusted by `learner_profiles.avg_session_minutes`, dropping from the
> end but never below one adventure slot. **Seed weighted selection with `(child_id,
> plan_date)` — no unseeded randomness anywhere.** Freeze the plan so it never regenerates on
> refresh, re-login or navigation.
>
> The LLM writes only `copy.title` (≤40 chars) and `copy.intro` (≤120 chars) from the
> already-chosen skill display names, age band and locale. Validate for length, shaming, PII
> solicitation, URLs and any skill not in the plan; fall back to
> `"Today's adventure: {A} and {B}!"`. One call per plan per day against the daily AI budget.
>
> Add `GET /plans/{child_id}/today`, `GET /plans/{child_id}/history`,
> `POST /plans/{child_id}/regenerate` (parent only, max 1/day) and
> `PATCH /plans/{child_id}/preferences`. Respect `preferences.plan_days`.
>
> Test: 100 runs producing a byte-identical plan; an LLM-disabled plan differing only in
> `copy`; carry-over limited to one item from yesterday; the practice block's skills matching
> the union of the two adventure lessons; time-fitting never emptying the plan; a zero-history
> child getting a valid plan; the §2 mastery fixture table reproduced exactly; and the 60-day
> decay case yielding 0.400.

## 9. Prompt — frontend

> The backend exposes `/api/v1/plans/*`. Read `docs/ops/OP-05-ai-tracking.md` §6,
> `docs/ops/OP-03-entry-flow.md`, and `docs/frontend-architecture.md` §3.3.
>
> Make `/adventure` render today's plan, since that is where every logged-in child now lands.
> Show plan items as a vertical rail on mobile and horizontal from `lg:` up, with progressive
> disclosure: the next incomplete item full-colour and large, completed items collapsed to a
> tick, later items visible but dimmed — one obvious next action with the day's shape behind
> it. Add a completion ring, and a streak flame **only when a streak exists**. Read every
> value from the server; compute nothing about plan state on the client.
>
> When the plan is complete, show a real ending — celebration, then a calm "see you tomorrow"
> — and **offer the child nothing further**; any bonus round is parent-initiated only. A
> missed day must produce no guilt copy anywhere. Render off days as a warm rest-day state,
> never an empty screen.
>
> Build the parent dashboard: a 30-day completion chart, the daily-minutes goal, study-day
> toggles, a once-daily regenerate button, and the learner profile rendered in plain language
> — "works best in short bursts", "prefers tapping to speaking" — never raw numbers or
> clinical terms.
