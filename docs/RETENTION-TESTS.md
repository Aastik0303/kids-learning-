# Retention tests: the scheduler asks, the teaching turn is paid

This is the feature that closes the learning-to-teach loop. A concept taught on
Monday is asked about again on Wednesday, with a *different* question about the
same thing, and the result pays the Q-value of **the Monday teaching action** —
not of the asking.

It is deliberately a **scheduler** feature, not a policy one. Q-learning chooses
*how* to teach and is paid for it days later; a policy that could also choose
*when* it is examined would be marking its own homework.

---

## 1. The architecture

Responsibilities, kept apart on purpose. Each box is a module, and no box does
another box's job.

```
                        ┌──────────────────────────────────────────┐
  DAY 1                 │  SCHEDULER  (planner_runner.sweep)       │
                        │  app/services/plan_service.py            │
                        │  app/ai/planner/graph.py                 │
                        │  → today's curriculum work               │
                        └───────────────┬──────────────────────────┘
                                        │ "today = Letter A"
                                        ▼
                        ┌──────────────────────────────────────────┐
                        │  AI TEACHER  (app/playground/service.py) │
                        └───────────────┬──────────────────────────┘
                                        ▼
     ┌────────────────────────────────────────────────────────────────────┐
     │ TEACHING POLICY   app/services/teaching_policy_service.py           │
     │   candidates → eligibility filter → epsilon-greedy → strategy       │
     │   Q-learning picks EXAMPLE for state  teach|low|1|0                 │
     └───────────────┬────────────────────────────────────────────────────┘
                     ▼
     ┌───────────────────────┐   ┌──────────────────┐   ┌────────────────┐
     │ RAG app/playground/   │──▶│ LLM  app/ai/llm/ │──▶│ EDGE TTS       │
     │ rag.py — WHAT content │   │ — HOW it is said │   │ — speaks it    │
     └───────────────────────┘   └──────────────────┘   └────────────────┘
                     │
                     ▼
     ┌────────────────────────────────────────────────────────────────────┐
     │ SAVE TEACHING EPISODE      policy_episodes                          │
     │   child_id · concept_id (skill_id) · state_key · action ·           │
     │   question_ref · taken_at ·  reward = NULL                          │
     └───────────────┬────────────────────────────────────────────────────┘
                     │
                     ▼
     ┌────────────────────────────────────────────────────────────────────┐
     │ SCHEDULE RETENTION TEST    retention_tests    (the sweep, ≥2d later)│
     │   source_teaching_episode_id  UNIQUE   ← the idempotency            │
     │   due_at = episode.taken_at + RETENTION_TEST_DELAY_DAYS             │
     │   status = "pending"                                                │
     └────────────────────────────────────────────────────────────────────┘

  ─────────────────────────────────────────────────────────────────────────

  DAY 3                 ┌──────────────────────────────────────────┐
                        │  SCHEDULER  (planner_runner.sweep)       │
                        │  1. today's normal curriculum work       │
                        │  2. retention tests where due_at <= now  │
                        │     ordered: due_at, concept, id         │
                        └───────────────┬──────────────────────────┘
                                        ▼
     ┌────────────────────────────────────────────────────────────────────┐
     │ AI TEACHER opens with the check-ins, before today's first stage     │
     │   question: app/playground/retention.py — a DIFFERENT authored      │
     │   question about the SAME concept, straight out of the syllabus     │
     └───────────────┬────────────────────────────────────────────────────┘
                     ▼   child answers
     ┌────────────────────────────────────────────────────────────────────┐
     │ DETERMINISTIC JUDGE   app/playground/stage.py :: judge()            │
     │   pure Python, authored key. No model, ever.                        │
     └───────────────┬────────────────────────────────────────────────────┘
                     ▼   pass / fail
     ┌────────────────────────────────────────────────────────────────────┐
     │ REWARD SYSTEM   app/policy/reward.py                                │
     │   pass +1.00 · transfer +0.35 · fail −0.50 · answer leak −1.50      │
     │   (all four configurable)                                           │
     └───────────────┬────────────────────────────────────────────────────┘
                     ▼   credit assignment: source_teaching_episode_id
     ┌────────────────────────────────────────────────────────────────────┐
     │ Q-VALUE UPDATE  app/db/repositories/policy.py :: pay_episode()      │
     │   Q(s,a) ← Q(s,a) + α[ r + γ·max Q(s',a') − Q(s,a) ]   α .15 γ .85  │
     │   s,a are the DAY 1 state and action. Guarded: an episode with a    │
     │   reward_resolved_at is never paid twice.                           │
     └───────────────┬────────────────────────────────────────────────────┘
                     ▼
     ┌────────────────────────────────────────────────────────────────────┐
     │ retention_tests.status = "settled" · result · reward · settled_at   │
     └────────────────────────────────────────────────────────────────────┘

  CURRICULUM PYTHON LOGIC  (learning_service, stage, plan_service)
  — stages, questions, progress, stars, unlocking —
  is NOT on this diagram anywhere below "AI TEACHER opens with the check-ins",
  because a retention test does not touch it.
```

---

## 2. What a retention test may not do

Enforced in `app/playground/service.py`'s check-in section and covered by
`tests/test_retention_tests.py::test_a_check_in_never_touches_the_curriculum`:

| | |
|---|---|
| unlock a level | never — `award_topic_completion` is not called |
| change the curriculum stage | never — `plan_index` and `stage` do not move |
| award stars | never |
| change question progression | never — `questions_asked` and the stage tally do not move |
| replace a curriculum question | never — check-ins run *before* the first stage |
| write to `attempts` | never — so mastery and the weak-skill list are untouched |
| write a `policy_episodes` row | never — the test chooses no strategy |
| modify correctness rules | never — `stage.judge` is the same function |

The one thing it moves is a Q-value.

---

## 3. Shadow mode

Unchanged, and the reason it stays unchanged is the point. `POLICY_MODE=shadow`
means the **hand-written ladder still teaches** and the learned policy's choice
is recorded beside it. Retention tests are asked and settled in shadow exactly
as they are in `on`, because the episode written in shadow carries `arm="shadow"`
and a real `(state, action)` — so the table learns from evidence without a child
ever hearing a decision it made. Nothing here switches production teaching
control to RL; that is still `POLICY_MODE` plus `POLICY_ROLLOUT_FRACTION`.

---

## 4. Settings

| setting | default | what it is |
|---|---|---|
| `RETENTION_TEST_DELAY_DAYS` | `2` | how long after teaching a concept becomes testable |
| `RETENTION_TESTS_PER_SITTING` | `3` | how many due check-ins one sitting opens with |
| `REWARD_RETENTION_PASS` | `1.0` | a passed test |
| `REWARD_TRANSFER_BONUS` | `0.35` | ...asked as a *different* question |
| `PENALTY_RETENTION_FAIL` | `0.5` | a failed test |
| `PENALTY_ANSWER_LEAK` | `1.5` | the teaching turn had handed the answer over |

`GET /policy/retention` echoes all of them back, with how many tests are pending.
