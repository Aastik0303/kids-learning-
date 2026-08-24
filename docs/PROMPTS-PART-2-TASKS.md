# Saksham IQ — Prompts, Part 2: Per-Task Instructions

**Depends on:** `PROMPTS-PART-1-SYSTEM.md` (the system messages every task
below is sent alongside). Each task replaces the single `_model_instruction()`
function in `guide_agent_service.py`, which today builds one instruction
string for every `GuideEvent` alike. Splitting it by task is the point of
this file: it is what lets four of the seven tasks below **stop calling the
LLM at all**.

Every task states, up front: which `GuideEvent`s route to it, whether it
should call the model, and why.

---

## Task inventory

| # | Task | Events | Call the LLM? |
|---|---|---|---|
| T1 | Welcome & navigation | `APP_OPENED`, `HOME_OPENED`, `ADVENTURE_OPENED`, `TOPIC_OPENED`, `PRACTICE_OPENED` | **No** |
| T2 | Teach: first presentation | `PRACTICE_STARTED`, `TOPIC_STARTED`, `PRACTICE_QUESTION_LOADED`, `TOPIC_QUESTION_LOADED`, `REPEAT_REQUESTED` | Yes |
| T3 | Repair ladder on wrong answer | `PRACTICE_ANSWER_INCORRECT`, `TOPIC_ANSWER_INCORRECT`, `HINT_REQUESTED` | Yes — this is the core task |
| T4 | Celebrate on correct answer | `PRACTICE_ANSWER_CORRECT`, `TOPIC_ANSWER_CORRECT` | **No** |
| T5 | Completion / unlock events | `PRACTICE_COMPLETED`, `TOPIC_COMPLETED`, `TOPIC_UNLOCKED`, `CERTIFICATE_UNLOCKED`, `SUBJECT_COMPLETED` | **No** |
| T6 | Rewards narration | `REWARDS_OPENED` | **No** |
| T7 | Free-form help / question | `GUIDE_HELP_REQUESTED` | Yes |

Three tasks call the model. Four don't. That is the "remove what's useless"
half of this document — not a separate cleanup pass, a direct consequence of
looking at what each event actually needs.

---

## T1 — Welcome & Navigation — **do not call the LLM**

**Fires on:** `APP_OPENED`, `HOME_OPENED`, `ADVENTURE_OPENED`, `TOPIC_OPENED`,
`PRACTICE_OPENED`.

**Why no model call:** `daily_recommendation_service.welcome_message()` and
the per-event branches already in `_fallback_guide()` (lines 471-522)
produce a correct, personalized, instant message — greeting, last-completed
topic, streak framing, all from data already in hand. Nothing about "which
subject is next" or "what to say when the app opens" requires understanding
free text or making a pedagogical judgment call. Routing this to Groq today
costs 300-800ms of latency and a nonzero chance of the model picking an
off-menu `ui_action.target`, in exchange for zero upside: `companion.py`'s
`start_session` already computes `deterministic_message` and only falls back
to it when the model's message is empty, meaning the deterministic answer
was sitting right there the whole time.

**Change made:** `guide()` checks `DETERMINISTIC_EVENTS` before it looks at
`settings.llm_provider`, so these five events take the deterministic path
whatever the provider setting says. Nothing was deleted from
`_fallback_guide` — its welcome/navigation branches were already correct and
are now the only path.

---

## T2 — Teach: First Presentation

**Fires on:** `PRACTICE_STARTED`, `TOPIC_STARTED`, `PRACTICE_QUESTION_LOADED`,
`TOPIC_QUESTION_LOADED`, `REPEAT_REQUESTED` — `FIRST_PRESENTATION_EVENTS` in
the service.

**Why call the model here:** this is the first explanation the child hears
for a concept. `_question_teaching_message()`'s deterministic templates are a
solid floor, but they are the same wording every time an `answer_type`
repeats across the curriculum — a model earns its keep here by varying the
phrasing and picking S1 vs. S2 based on what's actually on screen, never by
inventing new facts.

**Shipped instruction** (`_first_presentation_instruction`):

```
This is the child's first look at this question, or they asked to hear it
again with no wrong answer yet. Use S1_TELL or S2_SHOW only - do not hint
and do not simplify, there is nothing to repair yet. Say what the concept
is in the fewest words, referring to what is actually visible. If
visual_items are present, point at them by name rather than describing
them abstractly, then ask for the answer in one short sentence. Do not
restate the question as your explanation - restating is not teaching. For
a counting activity, count the visible items aloud in order before asking
how many there are altogether. For a trace, write or draw activity, say
where to put the finger and which way to move; do not mention accuracy,
the device measures the gesture and you do not. Set strategy to
"read_question" or "visual_explanation", teaching_strategy to "S1_TELL" or
"S2_SHOW", and next_expected_event to "voice_answer_requested".
```

`PRACTICE_STARTED` and `TOPIC_STARTED` can arrive before a question is loaded.
There is nothing to present yet on those turns, so the function returns a
one-sentence "here is what you are about to do" instruction and omits
`teaching_strategy` — a strategy is spent on a question, and there is no
question.

---

## T3 — Repair Ladder on Wrong Answer — the core new-workflow task

**Fires on:** `PRACTICE_ANSWER_INCORRECT`, `TOPIC_ANSWER_INCORRECT`,
`HINT_REQUESTED` — `REPAIR_EVENTS` in the service.

**Why call the model here:** this is the one place "don't move on until the
child gets it, but don't drill them into the ground either" actually has to
be decided turn by turn. Everything else in this document is either a canned
line or a first explanation; this is the only task where the model's choice
of strategy and wording changes based on *how* the child got it wrong.

`_repair_instruction()` builds the instruction from the rung
`_ladder_attempt()` returns, so the model is told the one rung it is on
rather than handed five and asked to locate itself. Rendered at attempt 3:

```
The child answered this question incorrectly. Attempt count on this
question is 3. This is the third attempt and the last turn you re-teach.
Switch how the idea is presented: S4_STORY, S6_DO_TOGETHER or
S7_SENSE_SWITCH. Make it easier and more visual. Set strategy to
"re_explain" and next_expected_event to "voice_answer_requested". Set
teaching_strategy to exactly one of: ['S1_TELL', 'S2_SHOW', 'S3_EXAMPLE',
'S4_STORY', 'S5_CONTRAST', 'S6_DO_TOGETHER', 'S7_SENSE_SWITCH',
'S8_PREREQUISITE', 'S9_PARK']. No strategy has been spent on this question
yet. Read recent_answers and conversation for a pattern before choosing.
If the child keeps confusing this concept with one particular other one,
name that contrast rather than repeating a generic hint. Keep the
diagnosis to yourself: choose the strategy it implies, and never put it in
the message. Never say what the correct answer is, never say "wrong", and
never count the items or give the total for a counting question.
```

The rung sentence and the `strategy` / `next_expected_event` values it names
change per attempt:

| Attempt | Strategies offered | `strategy` | `next_expected_event` |
|---|---|---|---|
| 0-1 | encouragement only, no teaching | `hint` | `voice_answer_requested` |
| 2 | S3_EXAMPLE, S5_CONTRAST (early: S1_TELL, S2_SHOW) | `hint` | `voice_answer_requested` |
| 3 | S4_STORY, S6_DO_TOGETHER, S7_SENSE_SWITCH (early: tell and show) | `re_explain` | `voice_answer_requested` |
| ≥ 4 | S9_PARK, under 14 words | `re_explain` | `wait_for_child` |

**`HINT_REQUESTED` — two deviations from the spec as written, both deliberate.**

The spec says to treat it as attempt 2 "regardless of
`attempts_on_current`". Taken literally that un-parks a question: a child who
has already missed four times and then taps the hint button would be dragged
back to rung 2 and drilled again, which is the exact thing the park rule
exists to stop. `_ladder_attempt()` returns `max(2, attempt)` instead — never
below a hint, never back down from a park. The reasoning the spec gives (a
child who asks for a hint has already told you encouragement won't help) is
fully served by the floor; only the ceiling changes.

The spec also says attempt ≥ 4 should set `next_expected_event` to "the app's
next-question event". No such event exists: the field is an opaque string to
both clients, and the only values the codebase produces are
`wait_for_child`, `voice_answer_requested` and `button_clicked`. Inventing a
fourth would emit a string neither client understands, so a parked question
sets `wait_for_child`.

---

## T4 — Celebrate on Correct Answer — **do not call the LLM**

**Fires on:** `PRACTICE_ANSWER_CORRECT`, `TOPIC_ANSWER_CORRECT`.

**Why no model call:** `_pick_praise()` already returns a varied, safe,
instant line from `STATIC_PRAISE` — the only pool there is, now that Part 1
§3 settled on English narration everywhere. A model has nothing to add — it was never shown the
answer key, so it cannot comment on *what* was right, only that it was
right, which the deterministic pool already says as well as it can be said.
The only way a model call changes this response is by adding latency or, in
the worst case, hallucinating a comment on an answer it never saw. Sending
this to an LLM is pure downside.

**Change made:** both events are in `DETERMINISTIC_EVENTS`.
`_fallback_guide`'s `PRACTICE_ANSWER_CORRECT` branch was already the entire
correct behaviour; it simply is not sent to Groq first any more.

---

## T5 — Completion / Unlock Events — **do not call the LLM**

**Fires on:** `PRACTICE_COMPLETED`, `TOPIC_COMPLETED`, `TOPIC_UNLOCKED`,
`CERTIFICATE_UNLOCKED`, `SUBJECT_COMPLETED`.

**Why no model call:** same reasoning as T4. These are celebration copy for
events the deterministic layer already fully understands (a topic finished,
a certificate unlocked) — `_fallback_guide` (lines 564-593) already has
correct, specific copy for every one of the five sub-cases. There is no
open-ended understanding required.

**Change made:** all five events are in `DETERMINISTIC_EVENTS`.

---

## T6 — Rewards Narration — **do not call the LLM**

**Fires on:** `REWARDS_OPENED`.

**Why no model call:** it is a stat readout (`"You have {stars} stars"`).
`_fallback_guide`'s existing branch (lines 595-605) is the entire task.

**Change made:** `REWARDS_OPENED` is in `DETERMINISTIC_EVENTS`.

---

## T7 — Free-Form Help / Question

**Fires on:** `GUIDE_HELP_REQUESTED` — `HELP_EVENTS` in the service.

**Why call the model here:** this is the one truly open-ended task in the
whole guide — the child typed or said something in their own words, and
`_help_message()`'s keyword-matching fallback is a floor, not a ceiling. It
cannot handle a question it has no keyword branch for. This is where a real
model earns its call.

**Shipped instruction** (`_help_instruction`):

```
feature is the child's own question or comment, word for word. Answer it
directly and simply, using the recent conversation for context where it
helps. If it is a real question about numbers, letters, colours, shapes,
stories or the current activity, answer it in one or two short sentences.
If it neither answers nor relates to the current question and is not a
request for help, say gently that it does not answer this question yet,
then restate the current question's hint or objective. Never say that you
could not hear or understand clear speech - if it does not fit, say so in
terms of the question, never in terms of the child's speech. If it is
unrelated to learning altogether, redirect to numbers, letters, colours,
shapes, stories or the app in one short sentence, without scolding. Never
give away the answer to the current question, including as background
information: telling a child that a circle has no corners while a round-
versus-cornered question is open is leaking the answer. Set strategy to
"help". Omit teaching_strategy, unless the child asked about the concept
the current question tests, in which case set it to "S1_TELL" or
"S3_EXAMPLE". Set next_expected_event to "wait_for_child".
```

In early mode the concept fallback offers `"S1_TELL" or "S2_SHOW"` instead:
S3_EXAMPLE is not one of the five strategies a Play Group child gets, and the
instruction must not offer a strategy `_teaching_strategy_from()` will drop.

---

## What this buys, concretely

Thirteen of the twenty-three `GuideEvent`s — T1's five, T4's two, T5's five
and T6's one — never needed a model call and are now pinned to the
deterministic path, with no behaviour change on the happy path: only lower
latency and cost, and one fewer place an LLM failure can degrade a response
that was already correct. (The draft's closing paragraph said "seven of
eleven"; the enum has twenty-three events and the table's own four
no-model rows account for thirteen of them.)

The three that stay on the model — T2, T3, T7 — are the three that involve
open-ended understanding or a repair decision. Each now receives only its own
instruction: the single `_model_instruction()` used to send the
`GUIDE_HELP_REQUESTED` paragraph, the hint-after-a-wrong-answer clause and the
voice-practice clause on every turn alike, whether or not any of them applied.

---

## Open: T3's model wording is discarded before it reaches the child

Worth knowing before this ships, because it undercuts T3's premise.

`_validate_model_response()` has a pre-existing override: on
`PRACTICE_ANSWER_INCORRECT`, `TOPIC_ANSWER_INCORRECT` and `HINT_REQUESTED` it
replaces the model's `message` with `_question_teaching_message()`'s
deterministic wording, and Part 1 added a `teaching_strategy: None` alongside
it so the strategy log stays honest about what the child actually heard.

The effect is that **T3 — "the core task" — currently takes nothing from the
model but its `visual_action`.** A verified run: at attempt 2, a model reply of
*"A circle is smooth all the way round, like a wheel."* tagged `S5_CONTRAST`
comes back to the child as *"Look at what is shown. Which one is the circle?"*,
with `teaching_strategy` cleared. Every ladder rung, every never-repeat rule
and every contrast-naming instruction in T3 is inert against the message text.

The override is not accidental. Its comment records why: without it, a model
that was never shown the answer key said *"That's right!"* over a miss the
deterministic grader had already recorded. That is a real failure and the
override is a real fix.

But T4 rejects a model call on exactly this reasoning — "the only way a model
call changes this response is by adding latency" — and that reasoning applies
to T3 as it stands today. Two coherent ways out, and this is a call about how
much the guide trusts the model, so it is left open rather than decided here:

1. **Let T3's wording through, keep a targeted guard.** Drop the blanket
   message override for repair events; instead reject a model message that
   affirms correctness on an INCORRECT event, and fall back to the
   deterministic wording only then. T3's ladder becomes real; the specific
   failure the override was built for stays covered.
2. **Keep the override and stop calling the model on T3.** Move
   `REPAIR_EVENTS` into `DETERMINISTIC_EVENTS` and drive the ladder from
   `_pick_hint()`, which already has a rung per attempt including the
   attempt-4 park pool. Cheaper and faster, but the repair wording stops
   varying with *how* the child got it wrong, which was T3's whole argument.
