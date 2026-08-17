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
| Play Group | `playgroup` | 2–3 | `early` | 3 | 24 |
| Nursery | `nursery` | 3–4 | `early` | 6 | 52 |
| LKG | `lkg` | 4–5 | `standard` | 5 | 23 |
| UKG | `ukg` | 5–6 | `standard` | 6 | 23 |

Play Group's three subjects are a product decision, not the published count —
see section 4a. Nursery's and Play Group's topic counts are levels rather than
published units: a published unit that would be one oversized lesson is split so
one sitting is one idea.

`toddler` is gone. Play Group replaces it.

## 3. Presentation modes

| Mode | Classes | Touch target | Choices/screen | Text | Idle rungs (s) |
|---|---|---|---|---|---|
| `early` | Play Group, Nursery | 96 px | 3 | none — icon + voice only | 12 / 25 / 40 / 60 / 80 |
| `standard` | LKG, UKG | 64 px | 4 | short words | 8 / 18 / 30 / 45 / 60 |

Two modes, not four. The gap between a 2-year-old and a 4-year-old is an interface problem;
the gap between LKG and UKG is a content problem.

## 4. Hindi

Removed from **Nursery** and **UKG**, then restored in both on request: Nursery's
orally, UKG's with writing and matras. Play Group and LKG never published a Hindi
subject. Neither restored class lists one under `removed_subjects` any more — the
mechanism is still there, and still records Play Group's Motor Skills below.
**Decided and shipped.**

## 4a. Play Group teaches three subjects

Play Group ships **English, Early Mathematics and General Awareness** only.
"Motor Skills Development" was removed first, then "Social and Emotional
Learning", "Creative Learning" and "Basic Life Skills" — all four by the same
`removed_subjects` mechanism and for the same reason: each is in the published
syllabus, so a silent deletion would read as an extraction gap. Any authored
activities stay in `activities/playgroup.json` and are skipped at load time, so
restoring a subject is a manifest edit alone. **Decided and shipped.**

## 4b. General Awareness is delivered as short levels

Play Group's six published General Awareness topics are delivered as fourteen
levels of three or four things each — Colours as three levels, Animals as four,
and so on. A level meets each thing one at a time and then checks it, and carries
extra question variants so the adventure and Practice do not repeat each other.
Every published point survives as a subtopic of the level that teaches it, which
is why the class keeps 50 General Awareness subtopics and only the topic count
moved. Same reasoning as Nursery's letter and number levels in section 4.

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

- [x] `backend/app/data/curriculum/manifest.json` is the only curriculum source; the five `*_path.json` files are deleted.
- [x] A loader validates the manifest on startup and **fails fast** with a named error on a malformed file. — `curriculum_service.load_curriculum()` from `main.lifespan`, raising `CurriculumManifestError`.
- [x] All 4 classes, **20** subjects, **98** topics load; counts asserted in a test. — counts moved twice since the plan: UKG's Language subject was removed (§4), and Play Group's Motor Skills Development was removed later by the same mechanism (§4a).
- [x] No Hindi subject exists under `nursery` — asserted by test, and under every other class too.
- [x] Age → class resolution matches §5 exactly, including boundaries at 3.0, 4.0 and 5.0. — parametrised test.
- [x] Adding a subject or topic requires **only** a manifest edit — zero code changes, demonstrated by `test_adding_a_topic_needs_only_a_manifest_edit`.
- [x] Every `activity.type` referenced has a registered evaluator, or the loader rejects the file naming the offending type.
- [x] `toddler` no longer appears anywhere in the backend — grep-verified (only this doc and the curriculum README's changelog table mention it).

**Frontend**

- [x] The age gate is replaced by class selection driven by the manifest, shown once during onboarding. — onboarding asks for a birth month once; the class is resolved server-side and previewed from `/curriculum/classes`.
- [x] `/toddler` is gone; requesting it redirects to `/adventure` (also `/levels`).
- [x] `services/toddlerGuide.ts`, `services/toddlerVoice.ts`, `components/toddler/*` are deleted.
- [x] `data/prototype.ts` is deleted; nothing imports it.
- [x] The adventure screen shows the child's class → subjects → topics, all from the server.
- [x] `early` mode enforces 96 px targets and its choice cap; `standard` enforces 64 px and 4. — the floor is applied by `data-surface` in `globals.css` and `lib/experience.ts`; the choice cap is enforced on both sides, and an over-wide authored activity fails the server's startup. The `early` cap is now 3 rather than 2, see Content status below.
- [x] A parent can override to an adjacent class; a child cannot. — the override needs a parent session token, and the server rejects any non-adjacent target with `CLASS_NOT_ADJACENT`.
- [x] Class, subject and topic names come from the manifest — no hardcoded curriculum strings anywhere, grep-verified.
- [x] A subject with no authored activities yet renders an honest "coming soon" state, never a crash or an empty screen. — the API answers `TOPIC_NOT_READY` rather than pretending.

### Content status

Activity content followed the migration rather than being part of it. All four
classes are authored — 614 activities served — with Play Group filled in last and
carrying 296 of them, several examples per topic so that the adventure and
Practice never hand a child the same question twice. Two things changed as a
result of real content meeting the spec:

- `early` mode now allows **three** choices per screen, not two. A counting question
  with two options is close to a coin flip.
- Environmental Science is grouped into topics per class instead of one catch-all
  topic, so each topic is a real lesson unit. Every published subtopic is preserved,
  which is why the topic count rose from 83 to 88 while subtopics stayed at 381.

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
