# Curriculum 2026-27 — CBSE Play Group / Nursery / LKG / UKG

Replaces the old path-based curriculum (`numbers_path.json`, `alphabets_path.json`,
`colours_path.json`, `shapes_path.json`, `mixed_final_path.json`) and the under-3
presentation mode that went with it. See `docs/ops/OP-07-curriculum-migration.md`.

## What changed

| Old model | New model |
|---|---|
| 4 paths + mixed final, each 8 stages | **4 classes by age**, each with subjects → topics |
| two presentation modes chosen by a raw age test | **4 age bands**, 2 presentation modes from this file |
| Curriculum invented for the prototype | **CBSE 2026-27 syllabus**, extracted from the source PDFs |

## The four classes

| Class | Age | Mode | Subjects | Topics | Subtopics |
|---|---|---|---|---|---|
| Play Group | 2–3 | `early` | 3 | 24 | 88 |
| Nursery | 3–4 | `early` | 6 | 52 | 152 |
| LKG | 4–5 | `standard` | 5 | 23 | 103 |
| UKG | 5–6 | `standard` | 6 | 23 | 93 |
| **Total** | | | **20** | **122** | **436** |

Play Group teaches three subjects — English, Early Mathematics and General
Awareness. Its other three published subjects are recorded under
`removed_subjects`, see [Removed Play Group subjects](#removed-play-group-subjects).

Asserted in `backend/tests/test_curriculum.py`, so these numbers cannot drift
from the file without a test failing.

Nursery's 42 topics are 29 published units: its two counting units are delivered
as four number levels and its two letter units as thirteen `Aa` levels — see
[Nursery letters and numbers](#nursery-letters-and-numbers).

## Hindi

| Class | Published syllabus | This manifest |
|---|---|---|
| Play Group | No Hindi subject | — nothing to remove |
| Nursery | "Hindi (Oral Introduction)" | **Taught** — removed once, restored on request |
| LKG | No Hindi subject | — nothing to remove |
| UKG | "Language (Hindi)" | **Taught** — removed once, restored on request |

Hindi is taught in Nursery and UKG. Both were removed by an earlier product
decision and both have since been restored, so neither class lists a Hindi
subject under `removed_subjects` any more. Play Group and LKG never published
one, so there is nothing to record for them.

Nursery Hindi is **oral only**, as published: no writing at all this year. A
Hindi level is *meet it, find it, find its picture, say it* — the English method
with the tracing step taken out. The loader has no idea about any of that; it is
simply what is authored, and a test asserts no `trace` activity exists in
`nur_hindi`.

UKG Hindi is where writing starts, again as published: the full swar and vyanjan,
then the matras applied to them (`क + आ = का`). Its six published points are
delivered as three topics — swar, vyanjan, and the four matra points together —
so one sitting is one idea.

## Removed Play Group subjects

Play Group teaches **English, Early Mathematics and General Awareness** only, by
product decision. Four of its published subjects are not taught:

| Published subject | Recorded as |
|---|---|
| Motor Skills Development | `pg_motor` |
| Social and Emotional Learning | `pg_social` |
| Creative Learning | `pg_creative` |
| Basic Life Skills | `pg_life` |

All four are recorded rather than deleted, for the same reason: each is in the
published syllabus, so a silent deletion would look like an extraction bug. The
`removed_subject_ids` mechanism drops them from every response and skips any
authored content for them with a log line, so restoring one is a manifest edit
and nothing more. The fine and gross motor activities `pg_motor` would serve are
parked in `superseded/` along with the rest of Play Group's pre-2026 content;
the other three never had activities authored.

## Play Group General Awareness

The published syllabus lists General Awareness as six topics — Colours, Animals,
Fruits, Vegetables, Transportation and Weather — each one a list of the things a
child should know. Colours alone is nine colours, Animals is twelve animals.
Delivered literally, one of those is a single lesson of a dozen questions.

They are delivered as **fourteen levels of three or four things each**:

| Published topic | Delivered as |
|---|---|
| Colours | `pg_ga_colors_1` … `_3` — red/blue/yellow, green/orange/purple, pink/black/white |
| Animals | `pg_ga_animals_1` … `_4` — two farm levels, two jungle levels |
| Fruits | `pg_ga_fruits_1`, `_2` |
| Vegetables | `pg_ga_vegetables_1`, `_2` |
| Transportation | `pg_ga_transport_1`, `_2` |
| Weather | `pg_ga_weather` — sunny, rainy, cloudy, windy |

A level meets each of its things one at a time — *this is a cow, the cow says
moo*, then *tap the cow* — and carries three extra question variants on top, so
the adventure and Practice never hand the child the same question. The teaching
cards are deliberately kept under `LESSON_LENGTH`: that is what stops a lesson
sampling one away and asking a two-year-old about something nobody showed them.

Every published point survives as a subtopic of the level that teaches it, so
General Awareness still has its 50 subtopics; only the topic count changed. The
reason is recorded in the `note` on `pg_ga`.

## LKG writing lives in Art

The published LKG syllabus files all writing under English: **Pre-Writing Strokes**
as its own unit, and a "Writing" subtopic inside both Capital Letters and Small
Letters. LKG is delivered with a fifth subject instead, **Art & Writing**, which
holds every one of those:

| Published under | Delivered as |
|---|---|
| English → Pre-Writing Strokes | `lkg_art_strokes` — the same eight strokes |
| English → Capital Letters → Writing | `lkg_art_writing` — "Writing Capital Letters (A-Z)" |
| English → Small Letters → Writing | `lkg_art_writing` — "Writing Small Letters (a-z)" |

The point is that a child finds writing in the same place every time rather than
meeting the tracing canvas as a surprise step inside a reading lesson. English
keeps the letters themselves — identify them, link an object, say the sounds.

The items **moved** rather than being copied, so LKG still has 103 subtopics and
98 activities; only the subject count changed. It is a delivery decision, not a
syllabus change, and the `note` on both subjects records it so a later reader can
tell it from an extraction bug. Asserted in `tests/test_authored_content.py`,
which checks that no `trace` activity exists outside `lkg_art`.

`lkg_art_writing` currently carries a single trace — the letter A, the only one
authored so far. The rest of the alphabet is still to be written.

Children who existed before the move had `lkg_eng_strokes` as their only unlocked
English topic, an id that is now on no subject's board — which drew every English
topic locked and made Practice refuse to start. `child_service.sync_class_progress`
reconciles that on read: ids that left a subject are forgotten, the subject reopens
at its first topic if nothing else is unlocked, and anything still on the board
keeps its completion and score. It is the same read-time repair that lets a class
gain a subject, widened to cover a topic leaving one.

## Presentation fields

Three optional manifest fields decide how a subject or topic looks. All are
optional, so a subject that gives none still renders; the frontend holds no
curriculum names or colours of its own either way.

| Field | On | Meaning |
|---|---|---|
| `fun_name` | subject | The child-facing name — "Number Fun 🔢" for Basic Mathematics. The syllabus `title` stays authoritative and is shown underneath it for the grown-up. |
| `colour` | subject | An exact hex colour for a subject whose brand colour matters more than fitting the `accent` palette. A non-hex value fails the boot. |
| `subtopic_icons` | topic | One emoji per subtopic, in the same order, so a topic card can draw each subtopic beside its own picture. |

`subtopic_icons` is all-or-nothing: a list that does not match the subtopic count
exactly is a fatal manifest error, because a short list would silently pair a
subtopic with the icon belonging to the one before it.

LKG authors all three. The other three classes author none of them yet, and look
exactly as they did.

## Nursery letters and numbers

The published Nursery syllabus lists **Capital Letters (A–Z)** and **Small
Letters (a–z)** as two separate units, and **Count to 5** and **Count to 10** as
two more. Delivered literally, each of those is one enormous topic: 26 letters or
ten numbers in a single lesson.

They are grouped into levels instead, the same way Play Group's are:

| Published unit | Delivered as |
|---|---|
| Capital Letters (A–Z) + Small Letters (a–z) | 13 levels of two letters — `nur_eng_letters_ab` … `_yz` |
| Count to 5 | `nur_maths_count_123`, `nur_maths_count_45` |
| Count to 10 | `nur_maths_count_678`, `nur_maths_count_910` |
| स्वर (अ – अः) | 6 levels of two — `nur_hindi_swar_a_aa` … `_am_ah` |
| व्यंजन (क – ङ) | 3 levels — `nur_hindi_vyanjan_ka_kha`, `_ga_gha`, `_nga` |

A letter level teaches **Aa as one letter**, not a capital now and a small one
months later. Both forms are on the introduction card, and the level asks for
both: find the big A, then match small a back to it. Writing follows the
syllabus exactly — capitals throughout, small letters only for a–j.

Every published subtopic survives the regrouping, and the reason for it is
recorded in the `note` on `nur_english` and `nur_maths`, so a later reader can
tell a delivery decision from an extraction bug.

## Age bands

The Play Group PDF states **2.5–3.5 years**. This manifest uses **2–3** so the four bands
are contiguous with no gaps or overlaps:

```
Play Group 2–3  │  Nursery 3–4  │  LKG 4–5  │  UKG 5–6
```

Contiguity is enforced by the loader: a gap or overlap between bands is a fatal
manifest error, because it would leave some age with no class or two.

A child's band is derived from `birth_year` + `birth_month` on the server, never chosen by
the client. A parent may override to an adjacent class from the parent surface; the
override is always anchored on the age-derived class, so it cannot be walked
further away one step at a time.

## Presentation modes

Two, not four — the difference between a 2-year-old and a 3-year-old is real, but the
difference between LKG and UKG is content, not interface.

| Mode | Classes | Touch target | Choices/screen | Text | Idle rungs (s) |
|---|---|---|---|---|---|
| `early` | Play Group, Nursery | 96 px | 3 | none — icon + voice | 12 / 25 / 40 / 60 / 80 |
| `standard` | LKG, UKG | 64 px | 4 | short words | 8 / 18 / 30 / 45 / 60 |

`early` allows three choices rather than two so a counting question is not a coin
flip: "how many ducks?" needs 2/3/4 to mean anything. `max_choices_per_screen` is
enforced at load time — an authored activity that offers more choices than its
class allows fails the server's startup rather than reaching a child. The touch target is a floor for **learning** controls only — navigation and
app chrome stay at 44 px on purpose.

## What this file is, and is not

`manifest.json` is the curriculum **taxonomy** — the authoritative class / subject / topic /
subtopic tree, faithful to the source PDFs. It is what the loader consumes.

It does **not** contain activities or questions. Those live in `activities/`, keyed
by class or subject — see that directory's README for the format. 901 activities
are served today; Nursery, LKG and UKG are fully authored and Play Group is part
way, see [Play Group is mid-migration](#play-group-is-mid-migration).

Where the published syllabus gives Environmental Science as a single flat list,
the manifest groups it into topics so each one is a real lesson unit rather than
one oversized topic. Every published item survives as a subtopic.

A subject with no authored activities is a valid, incomplete subject. The UI renders it
as an honest "coming soon" state, and the API answers `TOPIC_NOT_READY` rather than
pretending the topic is playable.

## Adding to the curriculum

Adding a class, subject or topic is a manifest edit. No code changes. The loader
validates and the API serves whatever is here, and the frontend holds no
curriculum names of its own.

## Files

```
backend/app/data/curriculum/
├── manifest.json        ← the taxonomy
├── activities/          ← the content, one file per class or per subject
│   ├── README.md        ← the activity file contract
│   ├── playgroup.json   ← 182 served (see Play Group below)
│   ├── nursery.json     ← 503 activities
│   ├── lkg.json         ←  98 activities
│   └── ukg.json         ← 118 activities
└── superseded/          ← parked content, outside the loader's glob
    └── playgroup-pre-2026-taxonomy.json
```

## Play Group is mid-migration

Play Group's manifest entry was re-taxonomised to the published 2026-27 syllabus
and its activities were authored against the previous grouping. General Awareness
has since caught up in full and the three untaught subjects are recorded as
removed, so what is left is English and Early Mathematics:

- Content whose `topic_id` or `subject_id` no longer exists in the manifest
  (`pg_ga_myself`, `pg_ga_school`, `pg_ga_things`, `pg_ga_habits`, and all of
  `pg_evs` and `pg_art`) is parked in `superseded/`. The loader globs
  `activities/*.json` and does not recurse, so nothing there is served. It is
  kept rather than deleted because most of it has an obvious home in the new
  taxonomy; re-home a topic by moving it back under a `topic_id` the manifest
  declares. Leaving it in place was not an option — the loader fails fast on an
  unknown `topic_id`, so it stopped the server from starting at all.
- **English and Early Mathematics are still at the published taxonomy**:
  `pg_eng_letters` is one "Capital Letters (A–E)" topic and `pg_maths_numbers`
  one "Numbers 1 to 5" topic. Neither has been split into the one-thing-at-a-time
  levels the class needs — A to Z three letters a level, and 1 to 10 — and
  `pg_eng_strokes` still has no answerable activity and no `trace_target` on its
  tracing steps. The assertions that describe that finished shape
  (`test_play_group_meets_the_alphabet_one_letter_at_a_time`,
  `test_play_group_counts_one_to_ten_in_order`,
  `test_a_letter_level_teaches_finds_says_and_writes_every_letter`,
  `test_every_writing_step_carries_something_to_trace`,
  `test_every_play_group_topic_has_several_examples_to_practise`) and the
  `tests/test_learning_flow.py` fixture, which authors against
  `pg_maths_number_123`, fail until it is authored.

General Awareness, Nursery, LKG and UKG are unaffected and fully authored.
