# OP-07 — Curriculum Migration: 4 Age Classes

**Goal:** replace the invented path-based prototype curriculum with the real CBSE 2026-27
syllabus, restructured into four age classes, and update the whole frontend to match.
**Blocked by:** Track A step A0 (one source of truth)
**Touches:** `backend/` + `frontend/`

---

## 1. The structural change

| Old | New |
|---|---|
| `numbers` · `alphabets` · `colours` · `shapes` · `mixed_final` — 5 paths × 8 stages | **Play Group · Nursery · LKG · UKG** — 4 classes × subjects × topics |
| `toddler` (under 3) vs `standard` (3+) | 4 age bands → 2 presentation modes |
| `{path}_path.json` in `backend/app/data/` | `backend/app/data/curriculum/manifest.json` + per-subject activity files |

```
Class (age band)
  └── Subject        Maths · English · General Awareness · EVS · Art & Motor
        └── Topic    e.g. "Count to 10", "Capital Letters (A-Z)"
              └── Activity
                    └── Question
```

This is the same `classes → levels → lessons → activities → questions` hierarchy the
backend architecture already specifies. **Subject maps to level, topic maps to lesson.**
Nothing new is invented.

## 2. The four classes

| Class | `class_id` | Age | Mode | Subjects | Topics |
|---|---|---|---|---|---|
| Play Group | `playgroup` | 2–3 | `early` | 5 | 20 |
| Nursery | `nursery` | 3–4 | `early` | 5 | 27 |
| LKG | `lkg` | 4–5 | `standard` | 4 | 20 |
| UKG | `ukg` | 5–6 | `standard` | 6 | 19 |

`toddler` is gone. Play Group replaces it.

## 3. Presentation modes

| Mode | Classes | Touch target | Choices/screen | Text | Idle rungs (s) |
|---|---|---|---|---|---|
| `early` | Play Group, Nursery | 96 px | 2 | none — icon + voice only | 12 / 25 / 40 / 60 / 80 |
| `standard` | LKG, UKG | 64 px | 4 | short words | 8 / 18 / 30 / 45 / 60 |

Two modes, not four. The gap between a 2-year-old and a 4-year-old is an interface problem;
the gap between LKG and UKG is a content problem.

## 4. Hindi

Removed from **Nursery**. Play Group and LKG never had it. **UKG retains its Language
subject** — you asked only for Nursery and Play Group. Confirm before shipping: the
curriculum currently has no Hindi for ages 2–5 and then Hindi at 5–6.

## 5. Age band resolution

Derived on the server from `birth_year` + `birth_month`, never chosen by the client and
never re-asked on every visit:

```python
def resolve_class(age_years: float) -> str:
    if age_years < 3: return "playgroup"
    if age_years < 4: return "nursery"
    if age_years < 5: return "lkg"
    return "ukg"
```

A parent may override to an adjacent class from the parent surface — a bright 3-year-old in
Nursery content, or a 4-year-old who needs Nursery revision. Store the override; never let
the child change it.

---

## 6. Acceptance criteria

**Backend**

- [ ] `backend/app/data/curriculum/manifest.json` is the only curriculum source; the five `*_path.json` files are deleted.
- [ ] A loader validates the manifest on startup and **fails fast** with a named error on a malformed file.
- [ ] All 4 classes, 20 subjects, 86 topics load; counts asserted in a test.
- [ ] No Hindi subject exists under `nursery` — asserted by test.
- [ ] Age → class resolution matches §5 exactly, including boundaries at 3.0, 4.0 and 5.0.
- [ ] Adding a subject or topic requires **only** a manifest edit — zero code changes, demonstrated.
- [ ] Every `activity.type` referenced has a registered evaluator, or the loader rejects the file naming the offending type.
- [ ] `toddler` no longer appears anywhere in the backend — grep-verified.

**Frontend**

- [ ] The age gate is replaced by class selection driven by the manifest, shown once during onboarding.
- [ ] `/toddler` is gone; requesting it redirects to `/adventure`.
- [ ] `services/toddlerGuide.ts`, `services/toddlerVoice.ts`, `components/toddler/ToddlerExperience.tsx`, `ToddlerHome.tsx`, `ToddlerLesson.tsx` are deleted.
- [ ] `data/prototype.ts` is deleted; nothing imports it.
- [ ] The adventure screen shows the child's class → subjects → topics, all from the server.
- [ ] `early` mode enforces 96 px targets and 2 choices; `standard` enforces 64 px and 4 — automated check per mode.
- [ ] A parent can override to an adjacent class; a child cannot.
- [ ] Class, subject and topic names come from the manifest — no hardcoded curriculum strings anywhere, grep-verified.
- [ ] A subject with no authored activities yet renders an honest "coming soon" state, never a crash or an empty screen.

---

## 7. Prompt

> Read `docs/OP-07-curriculum-migration.md`, `backend/app/data/curriculum/README.md`, and
> `backend/app/data/curriculum/manifest.json`. Migrate the curriculum from the invented
> path-based prototype to the real CBSE 2026-27 four-class structure.
>
> **Backend.** Make `manifest.json` the single curriculum source: four classes
> (`playgroup` 2–3, `nursery` 3–4, `lkg` 4–5, `ukg` 5–6), each with subjects → topics →
> subtopics. Map subject to the existing "level" concept and topic to "lesson" so the
> hierarchy in `docs/backend-architecture.md` §3.2 is reused rather than replaced. Write a
> loader that validates the manifest on startup and fails fast with a named error, and that
> rejects any `activity.type` with no registered evaluator. Delete `numbers_path.json`,
> `alphabets_path.json`, `colours_path.json`, `shapes_path.json` and `mixed_final_path.json`.
> Implement age→class resolution exactly as in §5, derived server-side from `birth_year` and
> `birth_month`, with a parent-settable override to an adjacent class only. Remove every trace
> of `toddler` from the backend.
>
> **Frontend.** Replace the age gate with manifest-driven class selection shown once during
> onboarding — age is stored on the child, never re-asked each visit. Delete
> `app/toddler/page.tsx`, `components/toddler/ToddlerExperience.tsx`, `ToddlerHome.tsx`,
> `ToddlerLesson.tsx`, `services/toddlerGuide.ts`, `services/toddlerVoice.ts` and
> `data/prototype.ts`, and redirect `/toddler` to `/adventure`. Render the adventure screen as
> the child's class → subjects → topics, entirely from server data, with **no hardcoded
> curriculum strings anywhere**. Implement the two presentation modes from §3: `early` for
> Play Group and Nursery at 96 px targets, 2 choices per screen and no text — icon and voice
> only; `standard` for LKG and UKG at 64 px, 4 choices and short words. A subject with no
> authored activities must render an honest "coming soon" state, never a crash.
>
> Do not author activity content in this step — the manifest is taxonomy only, and activities
> are a separate per-subject job. Wire the structure, prove it loads, and make the UI render
> it.
>
> Test: all 4 classes, 20 subjects and 86 topics load; no Hindi subject exists under
> `nursery`; age resolution is correct at the 3.0, 4.0 and 5.0 boundaries; adding a topic to
> the manifest surfaces in the UI with zero code changes; `grep -rn "toddler"` returns nothing
> outside changelogs; and each presentation mode enforces its touch-target and choice-count
> limits.
