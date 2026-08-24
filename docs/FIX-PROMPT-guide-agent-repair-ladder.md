# Fix Prompt — guide_agent_service.py repair-ladder bugs

Paste this whole file as one instruction to a coding session (this one or any
other) with `D:\testcase\backend` open. It fixes the 5 problems found in the
code review of `app/services/guide_agent_service.py` and
`app/schemas/guide.py`. Do the tasks in order — task 2 depends on task 1
being done first, and task 3 depends on task 2.

**Context:** the file already implements the T1–T7 task split, the S1–S9
strategy menu, the attempt-aware repair ladder, and `strategies_used`
repeat-avoidance. All of that is correctly *built*. The bug is that
`_validate_model_response()` still contains a pre-redesign override that
throws away everything T3 (the repair ladder) produces before it reaches the
child, and the deterministic fallback it falls back to was never updated to
match the new ladder either. `LLM_PROVIDER=groq` and a real `GROQ_API_KEY`
are set in `.env`, so this is live, not theoretical: every repair turn is
paying for a Groq call whose output is discarded.

---

## Task 1 — Stop discarding T3's model output

**File:** `app/services/guide_agent_service.py`, function
`_validate_model_response`, the `elif teaching_event and payload.question:`
block (currently ~line 1200-1221).

**Root cause:** this block unconditionally overwrites `message` and
`teaching_strategy` with `_question_teaching_message(payload)`'s output for
every event in `REPAIR_EVENTS`, at every attempt count. It predates the T2/T3
redesign — the comment above it explains it was written to stop the model
claiming a wrong answer was right, but it does that by discarding the whole
message rather than checking for that one failure mode.

**Fix:** replace the unconditional overwrite with a narrow safety check.
Trust the model's `message` by default (it already passed schema validation,
the ui_action/visual_action allowlist checks above this block, and
`safe_text`). Only fall back to `_question_teaching_message(payload)` when
the model's message actually fails a check — specifically:

- it appears to assert or imply the answer was correct (reuse or add a
  cheap heuristic: does the message contain praise language — "right",
  "correct", "yes!", "well done" — on an event that is by definition a wrong
  answer? `PRACTICE_ANSWER_CORRECT`/`TOPIC_ANSWER_CORRECT` never reach this
  branch, so any such phrase here is exactly the bug the old code was
  guarding against), or
- `teaching_strategy` came back `None` from `_teaching_strategy_from` (the
  model returned no legal strategy — treat this the same as any other
  malformed response and fall back), or
- the message is empty after `safe_text`/`_words` trimming.

Keep the existing visual_action override logic as-is (it is a legitimate
"fill in a visual the model omitted" fallback, not a full discard). When you
do fall back in one of the three cases above, use the same
`_question_teaching_message(payload)` call as today — that part is fine,
task 2 will fix what it returns for attempt ≥ 4.

**Acceptance check:** call `guide()` with a `PRACTICE_ANSWER_INCORRECT`
payload at `attempt=2` and a stubbed/mocked Groq response containing a
well-formed `teaching_strategy` and a message that does not leak the answer.
Assert the response's `message` equals the model's message, not
`_question_teaching_message`'s. Then run the existing `attempt=1`
second-try-encouragement path unchanged — that override is intentional and
should stay (attempt 1 is bare encouragement by design, not a teaching turn).

---

## Task 2 — Give the deterministic path a real attempt-4 park

**File:** same file, function `_question_teaching_message` (~line 452) and
the `_fallback_guide` INCORRECT ANSWER branch (~line 615).

**Root cause:** `HINT_RESPONSES_ATTEMPT_2`, `_ATTEMPT_3`, `_ATTEMPT_4_PLUS`
are defined but `_pick_hint()` is only ever called with `attempt=1`
anywhere in the file. `_question_teaching_message` has no ceiling — it will
re-explain forever as `attempt` grows, so a stuck child is never parked
when the app falls back to the deterministic path (Groq down, `llm_provider`
not `"groq"`, or the safety net from Task 1 firing).

**Fix:**
1. Add an early return at the top of `_question_teaching_message`: when
   `question.attempt >= 4`, return
   `(random.choice(HINT_RESPONSES_ATTEMPT_4_PLUS), GuideVisualAction(), "re_explain")`
   and do not fall into any of the answer-type branches below it.
2. In `_fallback_guide`'s INCORRECT ANSWER branch, the `else` clause
   currently always calls `_question_teaching_message(payload)` for
   attempt ≥ 2 — after step 1 this now correctly parks at attempt ≥ 4, so no
   further change is needed there, but delete the now-dead
   `HINT_RESPONSES_ATTEMPT_2`/`_ATTEMPT_3` pools and the corresponding
   branches in `_pick_hint` *only if* nothing else is meant to call them —
   check first whether the intent was for `_question_teaching_message` to
   call `_pick_hint` at attempt 2/3 instead of its own answer-type branches
   (either design is defensible; pick one and delete the other's dead code
   rather than leaving both).
3. `next_expected_event` for a parked turn should be the app's
   "move to next question" event, not `"voice_answer_requested"` — check
   what event name the client expects for "stop asking, move on" (the
   companion `next_action`/practice flow will name it) and set it explicitly
   in both the `_fallback_guide` INCORRECT branch and Task 1's fallback path
   when parking.

**Acceptance check:** a payload with `question.attempt=5` on
`PRACTICE_ANSWER_INCORRECT`, with `llm_provider` set to `"none"` (forcing
the deterministic path), returns a message from `HINT_RESPONSES_ATTEMPT_4_PLUS`
and a `next_expected_event` that is not `"voice_answer_requested"`.

---

## Task 3 — Route early-mode repair turns through `_early_mode_guide`-equivalent rendering on the Groq-success path

**File:** same file, `_validate_model_response` and `_early_mode_guide`.

**Root cause:** `_early_mode_guide` (14-word cap, tap-first, emoji) only
runs on the `_fallback_guide` path. On a successful Groq call,
`_validate_model_response` never checks `payload.experience_mode`, so an
early-mode child gets the same 25-word, non-emoji validation as a standard
child whenever Groq succeeds — which, with a live key, is most of the time.

**Fix:** in `_validate_model_response`, after the message is finalized
(post Task 1's logic), when `payload.experience_mode == "early"` apply the
same trim `_words(message, 14)` that `_early_mode_guide` applies, and — if
the model did not already include one — do not fabricate an emoji, but do
enforce the word cap server-side rather than trusting the prompt alone.
Also apply the early-mode teaching_strategy allowlist
(`EARLY_MODE_TEACHING_STRATEGIES`) here explicitly: if `teaching_strategy`
from the model is one of `S3_EXAMPLE`/`S4_STORY`/`S5_CONTRAST`/`S8_PREREQUISITE`
on an early-mode turn, treat it as invalid input the same way
`_teaching_strategy_from` already does for other illegal values (it already
calls `_allowed_teaching_strategies(payload)`, which is early-mode aware —
confirm this path is actually reached for early-mode Groq responses today;
if `_teaching_strategy_from` is already correct, this half of task 3 may
already be done and only the 14-word enforcement is missing).

**Acceptance check:** a `payload.experience_mode == "early"` repair turn
with a mocked Groq response of 22 words gets trimmed to 14 in the returned
`GuideResponse.message`.

---

## Task 4 — Sanity-bound the client-supplied `attempt` field

**File:** `app/schemas/guide.py` (`GuideQuestionContext.attempt`) and/or
`app/services/guide_agent_service.py` (`_ladder_attempt`).

**Root cause:** `attempt` drives the entire repair ladder (rung selection,
legal strategies, the attempt-4 park trigger) but, unlike `strategies_used`
and the answer key, is trusted verbatim from the client. This is lower
severity than tasks 1-3 (it is app UI state, not the answer key), but it is
pedagogically load-bearing enough that a stuck client (attempt stuck at 0,
or a bug that never increments it) silently defeats the escalation ladder.

**Fix — pick the lighter of two options unless you want the heavier one:**
- Lighter: in `_ladder_attempt`, clamp the incoming value:
  `attempt = max(0, min(attempt, 6))` before use, and log (or at least
  comment) that this is a UI-trust boundary, not a security one.
- Heavier: track attempt count server-side the same way `_STRATEGY_LOG`
  tracks strategies (keyed by `session_id, activity_id`), increment it on
  every `PRACTICE_ANSWER_INCORRECT`/`TOPIC_ANSWER_INCORRECT` the server
  processes, and use that instead of `payload.question.attempt`. Do this
  only if the client is not already the authoritative source of attempt
  count for scoring elsewhere — check `activity_evaluators.py` /
  `answer_resolution_service.py` call sites before duplicating this state.

**Acceptance check:** whichever option you pick, a payload with
`question.attempt=999` no longer produces an out-of-range rung — it parks
via Task 2's logic instead of hitting an unhandled branch.

---

## Task 5 — Delete the dead conditional (cleanup, no behavior change)

**File:** same file, `_validate_model_response`, inside the block from
Task 1: `if payload.event != "GUIDE_HELP_REQUESTED":`.

**Root cause:** `GUIDE_HELP_REQUESTED` always returns earlier, from the
dedicated special-case block at the top of `_validate_model_response`
(~line 1137). This branch is therefore never reached by a help-request
event, and the condition is always `True` in practice — it reads as if help
requests still flow through here.

**Fix:** remove the `if` and its `else` (if any), or replace it with a
one-line comment noting that `GUIDE_HELP_REQUESTED` cannot reach this point,
so a future reader is not misled into thinking this is live branching logic.

---

## Order and dependency

Do task 1 before task 2 (task 2's acceptance check assumes task 1 is no
longer masking the deterministic fallback's behavior). Task 3 depends on
task 1 (it modifies the same function, after the model's message is
trusted). Tasks 4 and 5 are independent and can be done in any order,
including before 1-3.
