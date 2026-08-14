# Curriculum 2026-27 — CBSE Play Group / Nursery / LKG / UKG

Replaces the old path-based curriculum (`numbers_path.json`, `alphabets_path.json`,
`colours_path.json`, `shapes_path.json`, `mixed_final_path.json`) and the `toddler` mode.

## What changed

| Old model | New model |
|---|---|
| 4 paths + mixed final, each 8 stages | **4 classes by age**, each with subjects → topics |
| `toddler` (under 3) vs `standard` (3+) | **4 age bands**, 2 presentation modes |
| Curriculum invented for the prototype | **CBSE 2026-27 syllabus**, extracted from the source PDFs |

## The four classes

| Class | Age | Mode | Subjects | Topics | Subtopics |
|---|---|---|---|---|---|
| Play Group | 2–3 | `early` | 5 | 20 | 79 |
| Nursery | 3–4 | `early` | 5 | 27 | 114 |
| LKG | 4–5 | `standard` | 4 | 20 | 103 |
| UKG | 5–6 | `standard` | 6 | 19 | 93 |
| **Total** | | | **20** | **86** | **389** |

## Hindi

| Class | Published syllabus | This manifest |
|---|---|---|
| Play Group | No Hindi subject | — nothing to remove |
| Nursery | "Hindi (Oral Introduction)" | **Removed** ✅ |
| LKG | No Hindi subject | — nothing to remove |
| UKG | "Language (Hindi, Bengali, Malayalam…)" | **Retained** |

You asked to remove Hindi from Nursery and Play Group. Play Group never had it, so only
Nursery changed. **UKG still has its Language subject** — say the word and it goes too.
As it stands the curriculum has no Hindi for ages 2–5 and then Hindi at 5–6, which is a
slightly odd progression worth a deliberate decision rather than an accident.

## Age bands

The Play Group PDF states **2.5–3.5 years**. This manifest uses **2–3** so the four bands
are contiguous with no gaps or overlaps:

```
Play Group 2–3  │  Nursery 3–4  │  LKG 4–5  │  UKG 5–6
```

A child's band is derived from `birth_year` + `birth_month` on the server, never chosen by
the client.

## Presentation modes

Two, not four — the difference between a 2-year-old and a 3-year-old is real, but the
difference between LKG and UKG is content, not interface.

| Mode | Classes | Touch target | Choices/screen | Text | Idle rungs (s) |
|---|---|---|---|---|---|
| `early` | Play Group, Nursery | 96 px | 2 | none — icon + voice | 12 / 25 / 40 / 60 / 80 |
| `standard` | LKG, UKG | 64 px | 4 | short words | 8 / 18 / 30 / 45 / 60 |

## What this file is, and is not

`manifest.json` is the curriculum **taxonomy** — the authoritative class / subject / topic /
subtopic tree, faithful to the source PDFs. It is what the seeder consumes.

It does **not** contain activities or questions. Those are authored per topic from the
subtopics — 389 subtopics at roughly 3 activities each is on the order of 1,200 activities,
which is a content-authoring job, not a one-pass generation. Author them subject by subject,
starting with Play Group Maths and Nursery Maths since those unblock the youngest users.

## Files

```
backend/app/data/curriculum/
├── manifest.json        ← the taxonomy (this delivery)
└── activities/          ← authored per subject, added incrementally
    ├── pg_maths.json
    ├── nur_maths.json
    └── …
```
