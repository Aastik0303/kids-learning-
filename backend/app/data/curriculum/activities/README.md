# Authored activities

The manifest is taxonomy only. This directory is the content. A subject with no
activities is a valid, incomplete subject — the UI renders it as "coming soon"
rather than failing.

## File layouts

Two are accepted, told apart by their top-level key.

**`<class_id>.json`** — a whole class in one file. This is what `nursery.json`,
`lkg.json` and `ukg.json` use.

```json
{
  "class_id": "nursery",
  "subjects": [
    {
      "subject_id": "nur_maths",
      "topics": [
        {
          "topic_id": "nur_maths_shapes",
          "objective": "Recognise circle, square, triangle, rectangle",
          "intro_message": "Shapes are everywhere! Let us meet them one by one.",
          "delivery": "digital",
          "star_reward": 5,
          "activities": [ … ]
        }
      ]
    }
  ]
}
```

**`<subject_id>.json`** — one subject at a time, for filling gaps incrementally.

```json
{ "subject_id": "pg_maths", "topics": { "pg_maths_colours": [ … ] } }
```

The file name must match the `class_id` or `subject_id` inside it.

## Topic metadata

`objective`, `intro_message`, `star_reward`, `delivery` and `lesson_flow` are
authored with the content rather than the taxonomy, because they describe the
lesson, not the syllabus. `delivery` is one of:

| value | meaning |
|---|---|
| `digital` | fully teachable on screen |
| `hybrid` | the screen introduces it, a physical action completes it |
| `parent_guided` | physical only — the app shows the grown-up a card |

`lesson_flow` decides how much of the topic one lesson plays:

| value | meaning |
|---|---|
| `sample` (default) | keep the teaching cards, sample the questions, vary between visits |
| `complete` | play every activity in order — for a topic that is a designed sequence |

## Activities

```json
{
  "activity_id": "nur_sh_2",
  "type": "select_shape",
  "skill_id": "shape_circle",
  "prompt": "Tap the circle.",
  "visual_items": ["circle", "square"],
  "options": ["circle", "square"],
  "correct_answer": "circle",
  "hint": "The round one with no corners.",
  "difficulty": "very_easy"
}
```

Every `type` must have an evaluator in `app/services/activity_evaluators.py`.
The registry also decides how an activity is answered, which is served to the
client as `answer_kind` so the UI never guesses from the type name:

- **choice** — a closed set of options. Needs `options` and a `correct_answer`
  drawn from them. A `match` activity may name several right answers,
  comma-separated; they are compared as a set, so order does not matter.
- **spoken** — said aloud. No options. Needs a `correct_answer`, or
  `open_ended: true` for prompts like "tell me your name". `accept` lists extra
  spellings that are equally correct, e.g. `["a", "aa", "ay", "ah"]`.
- **presentational** — watched, listened to, traced, or done off-screen. No right
  answer; taking part completes it. `trace` carries `trace_target` and
  `min_accuracy` (judged on the device from the gesture, never by a model).
  `parent_activity` carries a `parent_note` shown to the grown-up.

## What the loader rejects, and why

It fails the server's startup, naming the file and field, when:

- `class_id` / `subject_id` is unknown, or does not match the file name
- a `topic_id` does not belong to that subject
- an `activity_id` is duplicated within a topic
- `type` has no registered evaluator
- a choice activity has no options, no correct answer, or a correct answer that
  is not among its options
- a spoken activity has neither a correct answer nor `open_ended: true`
- an activity offers more choices than the class's experience mode allows
  (`early` = 3, `standard` = 4)

That last rule is why the choice limits are real rather than advisory: an
authoring mistake that would put six options in front of a three-year-old stops
the server instead of reaching a child.

## Deliberately removed subjects

Content for a subject listed in a class's `removed_subject_ids` is skipped with a
log line, not treated as an error. `ukg.json` still contains the Language (Hindi)
subject and `playgroup.json` still contains Motor Skills Development; neither is
ever served, because both subjects were removed by product decision. Deleting the
content is optional — restoring the subject to the manifest is all it would take
to bring it back.

## Coverage

| Class | Subjects | Topics | Activities |
|---|---|---|---|
| Play Group | 3 | 58 | 421 |
| Nursery | 6 | 52 | 585 |
| LKG | 5 | 23 | 98 |
| UKG | 6 | 23 | 118 |

All four classes are authored. Play Group and Nursery carry the most activities,
and deliberately so, for two reasons.

Every topic holds several examples of the same skill — nine colours, six fruits,
four kinds of weather — because the adventure and Practice both draw from the
same topic. With one example per topic, a child would meet the identical
question on both surfaces.

English and Maths go further in both classes and are taught **one at a time**,
through the same steps: the one thing is explained properly, then drawn, then
said out loud, and only then asked about.

| Step | Type | What the child does |
|---|---|---|
| look at it | `introduce_letter` / `introduce_number` | "This is B. Look at it with me — a long line and two tummies." |
| hear it | `introduce_letter` / `introduce_number` | "B says 'buh'. Listen — buh... buh..." |
| use it | `introduce_letter` / `introduce_number` | "buh... ball! B is for ball. ⚽" |
| draw it | `trace` | draws it with a finger on the tracing canvas |
| say it | `repeat_letter` / `repeat_number` | says it into the microphone |
| match it | `match` | matches the letter to its picture, and the picture back to its letter |

Three teaching cards rather than one is the point of the shape: a letter gets
its own card for how it looks, one for how it sounds, and one for a word it
starts, so nothing is explained in passing on the way to a question. Drawing
comes before saying and matching on purpose — a child who has just made the
shape with a finger has something to say it about.

These topics carry `"lesson_flow": "complete"`, so the lesson plays every step
and the level passes only at the end of them. Sampling would drop one of the
steps for some letter, which is not a shorter lesson but a broken method. Every
other topic stays `"sample"` (the default), where the lesson keeps the teaching
cards and samples the questions.

### Play Group

One letter a level and one number a level: twenty-six alphabet topics
(`pg_english_letters_a` … `_z`) and ten counting topics (`pg_maths_number_1` …
`_10`), each unlocking the next. Seven steps per level — three explaining cards,
the drawing, saying it, and two matching questions — so a level is that one
thing explained and checked, and nothing else. The second matching question
counts a different picture (four flowers after four stars) so that four is
learned rather than "the star question".

Two and a half years old is the reason. Three letters in a sitting means a child
meets B while still working out A, and the level ends without either being
learned. A level here is short enough to finish, and the next letter waits until
this one is written.

### Nursery

Nursery meets the whole alphabet again, but as **thirteen levels of two letters**
(`nur_eng_letters_ab` … `_yz`), and a letter means both of its forms:

| Step | What the child does |
|---|---|
| meet it | "This is Aa. Big A and small a are the same letter." |
| hear it | "Aa says 'aa'. A is for apple! 🍎" |
| see how it is made | "Look how we make Aa. Big A — two slanting lines and a belt. Small a is little, like a baby A." |
| draw it | traces **A**, and traces **a** as well for a–j |
| say it | says the sound "aa" into the microphone |
| match it | sees small **a** and taps the capital it belongs to |
| match it again | taps the picture that starts with **A** |

Teaching Aa on one card is the whole point: the published syllabus separates
capitals and small letters by months, but a three-year-old shown "A" and "a"
apart learns two unrelated squiggles. Levels a–j are sixteen steps and k–z are
fourteen, because the syllabus introduces writing for small letters only up to j.

Counting is four levels — 1·2·3, 4·5, 6·7·8, 9·10 — each number explained,
drawn, said and matched before the next one arrives.

**Hindi runs the same method with the writing taken out**, because the published
syllabus is speaking and listening only this year — "Is saal Hindi likhna nahi
hai". Nine levels: six of स्वर (अ आ / इ ई / उ ऊ / ए ऐ / ओ औ / अं अः, paired the
way a child hears them) and three of व्यंजन (क ख / ग घ / ङ). Four steps per
letter — meet it, find it, **find its picture**, say it — with the picture step
standing in for the writing step English has. A test asserts there is no `trace`
activity anywhere in `nur_hindi`, so the no-writing rule cannot be broken by a
later edit.

Hindi answers accept either script: a spoken "अ" and a spoken "a" are the same
answer, because speech recognition may return either.

Every other Nursery topic opens on a teaching card and then carries eight to
twelve examples of the same skill, so a lesson is a short, varying sample and
Practice never repeats the question the adventure just asked.

The counts are asserted in `backend/tests/test_authored_content.py`, so they
cannot drift from the files without a test failing.
