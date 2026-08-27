# AI Nursery Agent Notes

## Source of truth

- Follow `README.md` and, for the AI classroom, the `docs/` family:
  `AI-100-PERCENT-AUTOMATION.md` (what "100% automation" means and its phase
  plan), `AGENT-FLOW.md` (build order and the LangGraph verdict),
  `AI-ARCHITECTURE-DECISIONS.md` (why RLHF was rejected), and
  `TEACHING-GRAPH-SPEC.md` (nodes, edges, contract tests).

## The one rule that never moves

- **Do not use an LLM for deterministic correctness, scoring, stars, unlocking,
  or certificate eligibility.** The branch decision - advance, re-explain,
  simplify, drop to a prerequisite, switch modality, stop kindly - is on the
  same list: `app/conductor/branch.py` is a pure function and may not import
  `app.ai` or `app.services`. "100% AI" means zero manual decisions on the
  *child's* surface — no navigation, no menus, no "next" button — not that a
  model grades anything. The evaluator is pure Python and must not reach
  `app/agents/` or any model client through any import path.
- The same rule binds the learned policy. A reward defined on "the child
  answered correctly" trains a teacher that hands over the answer; that is why
  RLHF was rejected here, and a Q-learning reward built the same way fails
  identically. Rewards are paid by retention probes days later
  (`app/db/repositories/policy.py`) and by nothing else.

## Infrastructure — this project is past the prototype stage

- PostgreSQL is the durable truth. Schema lives in `app/db/models.py`, access in
  `app/db/repositories/`, migrations in `backend/alembic/`. Run them with
  `cd backend && alembic upgrade head`.
- `app/services/mock_storage.py` and `mock_auth.py` are gone. Auth is
  `app/services/auth_service.py` (PBKDF2, `parents` / `auth_sessions`), the
  child's progress ledger is `app/services/child_store.py`, and the attempt log
  is `app/services/history_service.py` writing `attempts`. Do not reintroduce a
  module-level dict as storage; the only ones left are the in-flight lesson and
  practice cursors, which are rebuilt by starting again.
- **A question gets three repairs, and then the class moves on.**
  `branch.MAX_ATTEMPTS_ON_ONE_QUESTION` is 3, and each of the three is a
  different turn: the learned policy picks a strategy it has not spent on this
  question, and the last one simplifies instead of re-explaining
  (`SIMPLIFY_AT_ATTEMPT`). There is no encouragement-only rung any more - a
  child who has just got something wrong hears something new on the very next
  turn. Running out of repairs is `ADVANCE` with reason `attempts_exhausted`:
  the question is let go of, nothing is celebrated or counted right, the skill
  is marked weak, and the lesson carries on. Only a frustrated child or an
  overrunning sitting ends it (`END_KINDLY`).
- The class is conducted server-side. `app/conductor/` decides (state machine,
  Branch Decision Engine, frustration and idle watchers, scaffolding) and
  `app/services/conductor_service.py` holds the state, writes the truth and asks
  the guide for the words. One row in `lesson_states` is the live lesson, and
  `POST /conductor/{child_id}/open` plus `POST /conductor/sessions/{id}/input`
  drive the whole sitting. The client renders a `ConductorDirective` and reports
  what the child did; it decides nothing, including what silence means.
- The **mobile app** drives the conductor: `mobile/src/features/learning/useConductorClass.ts`
  and `screens/child/ClassScreen.tsx`. The hook reads five fields - `speech`,
  `next_input.expects`, `listen`, `auto_advance_in_ms`, `close` - and nothing
  else, which is what stops it quietly growing a second copy of the teaching loop
  the way `useLessonSession` did. It never picks a topic, checks an answer, or
  decides when the microphone opens. Naming a topic says *which* level, never
  *whether* - `plan_service.may_open` still refuses one that is not today's.
  `/learning` and `/practice` remain for the older clients and are marked
  deprecated.
- **The web app does not use the conductor any more.** Its class is the AI
  Teacher (see below): `/` opens it, `/class` redirects to it, and Adventure
  teaches nothing. `frontend/components/curriculum/ConductedClass.tsx` and
  `frontend/lib/useConductorClass.ts` are still in the tree but nothing mounts
  them.
- **Language tags are BCP-47 or nothing.** `services/audio/language.ts` is the
  only place that decides one. A recogniser handed a profile display name
  ("English") refuses to start, silently, and the microphone simply never
  answers - which is exactly how it was broken. The tag follows the *content*:
  a Hindi level asks for `hi-IN` from a child whose profile says English.
  Narration is the other way round - it is English with Devanagari quoted
  inside, so `tts` splits the line by script and speaks each run in a voice
  that can read it. Never hand `speech.language` to the narrator as its base.
- **The class stops and listens.** After the guide has explained a thing, the
  conductor asks the child to say it back into the microphone (`Phase.SAY_IT`,
  `app/conductor/echo.py`) and what comes back decides whether the next thing is
  the drawing or a second, differently-worded explanation from the learned
  policy. Three boundaries hold it: it runs in the subjects that teach an
  alphabet or numbers - English, maths and the two Hindi subjects
  (`echo.subject_speaks`) - and only for **a letter or a number**
  (`echo.is_letter_or_number`), in either script, never a colour, a shape or a
  whole word; it runs on **teaching cards only**, so a microphone is
  never open beside an answer key, and never on a drawing card; and an echo is
  **never scored** - no attempt written, no star moved. It is asked **once per
  sitting**, near the start (`echo.ECHO_ASKS_PER_LESSON`), however many things
  the lesson teaches; an echo that does not land is answered by explaining it
  again in different words and carrying on, never by asking a second time. Judging it is string work over a cleaned
  transcript, never a model.
- **What a child says is not always an answer.** "Pata nahi", the question read
  back, a story about a dog, "I want mumma" - `app/conductor/unexpected.py`
  names each one and says what the class should do, and none of the answers is
  "wrong". An utterance that does not resolve to an answer is never recorded as
  a failed attempt. Anything visible on screen is always an answer and is handed
  straight to the evaluator; the classifier never sees the answer key.
- **A day is one level per subject, and that is what a stage counts.**
  `plan_service._candidates` returns exactly one topic per subject - the first
  weak one if the subject has any, otherwise its first unfinished unlocked topic
  - and never two from the same subject, however many of its levels are shaky. A
  Play Group child has three subjects (English, Maths, General Awareness), so
  their day is those three every day and the class is three stages. Classes with
  more subjects than `app.ai.planner.graph.MAX_ITEMS` rotate by the day number so
  none is starved. The AI Teacher's stage number is derived from the plan cursor
  (`plan_index + 1`) and never read off a counter, so a sitting cannot go on
  claiming a stage the day does not have.
- **The day's plan is the day's work.** `plan_service.may_open()` is the gate:
  a topic opens if today's frozen plan holds it, or if the child has already
  finished it. Anything else is tomorrow's, including the level the lesson just
  unlocked - unlocking is what a lesson earns, and *when* it is played is the
  plan's to decide. A day holds one level per subject, the subjects rotate by
  day so none is starved, and with no plan at all the gate opens rather than
  locking a child out over infrastructure. Both `/learning/start` and the
  conductor enforce it; refusals are `NOT_TODAYS_PLAN` and are worded for a
  child.
- The Planner Agent is a LangGraph graph in `app/ai/planner/`, run on a timer by
  `app/services/planner_runner.py` and frozen into `daily_plans`. It may only
  reorder the candidates `plan_service` computed; an off-menu answer is dropped
  whole and the day stays `deterministic`.
- The teaching policy is wired: `app/services/teaching_policy_service.py`
  chooses a strategy for every teaching turn (with no model configured too),
  `app/services/retention_service.py` schedules and settles the probes that pay
  its reward, and `app/services/plan_service.py` freezes one plan per child per
  day. Anything reaching a language model goes through `app/ai/llm/`.
- Tests run on in-memory SQLite; the models use portable SQLAlchemy types so one
  migration describes both backends.

- **A picture token is an asset name, not a word.** Hindi levels name their
  pictures in Roman - `anar`, `aam`, `imli` - and two things follow. The guide
  must never *say* the token: `explain.spoken_form()` reads the Devanagari back
  out of the author's own prompt, so it says "अनार" and not "anar". And a token
  Unicode has no emoji for must not be mapped to a near-miss - `anar` was the
  apple emoji, so a level teaching अ से अनार showed a child सेब. Those live in
  `frontend/lib/visualIcon.ts`'s `HINDI_PICTURE_WORDS` and render as the word
  until there is real artwork.
- **The child asks; the app does not offer a fixed question.** The lesson's
  guide panel has "Ask me anything" (a microphone) where it used to have "Give
  me a hint". A hint is now one of the things a child can ask for out loud
  rather than the only thing they were allowed to want. Answers are filtered by
  `safety_service.safe_text` server-side, so an off-topic question comes back as
  a kind redirection.

## The AI Teacher is the class

- `app/playground/` is the web app's teaching loop. The directory keeps its
  name, and so does the `/playground/teacher/...` route, because that is where
  this started; nothing about it is a sandbox any more. `rag.py` retrieves from
  `app/data/playground/teacher_notes.md` with free HuggingFace sentence
  embeddings (keyword fallback when the model cannot load), `agent.py` is a
  LangGraph graph - retrieve → choose one of the nine strategies → teach - that
  runs on the big model (`settings.groq_teacher_model`), and `stage.py` marks the
  answer and counts the questions.
- **A stage is five questions, and there is no score.** The points this loop used
  to keep - +2 right, -1 wrong, ten to finish a stage - are gone, along with the
  `points` and `points_delta` columns and every scoring field in
  `TeacherTurnResponse`. A number that goes up when a four-year-old is right and
  down when they are not teaches them to mind the number. What the child's screen
  shows is where they are: five dots for the five questions, and which level of
  the day. Whether the level passed is still worked out at the end from
  `topic_correct` / `topic_answered` by `award_topic_completion`, which is the
  only thing upstream of a star.
- **Every question gets three turns and nobody is left stuck.** It is asked; a
  wrong answer brings the **hint** - the thing explained again and more deeply,
  ending in a clue, with two or three choices to pick between; a second wrong
  answer brings the **answer**, told and explained, and then the class moves on.
  `lesson.TRIES_PER_QUESTION` is 2 and the third turn is not an asking at all:
  it is `expects: "ready"`, it is never marked, and no attempt is written for it.
  The choices are built in plain Python by `agent.hint_options` - narrowed from
  what the child was already offered, or built from the concept's own family -
  so a hint can never arrive without the answer among its options. A question
  settles once however many turns it took, and five settled questions end the
  stage.
- **The class says hello before it teaches.** `service._class_intro` puts two or
  three lines in front of the first turn of a sitting: what today holds, what is
  starting, and that a tricky question will be helped and then answered. It is
  said once - a reload teaches the step again without re-introducing the class.
- **It marks nothing.** The bot asks the question; `stage.judge` decides whether
  the answer was right, in pure Python. That rule matters more here than it ever
  did in the sandbox, because the verdict now pays stars: a model that both sets
  and marks learns to give the answer away.
- **The explaining turn is three or four sentences with an everyday example in
  them**, in every subject: what the thing is, the same thing said again in
  other words, something the child has seen for themselves, and what to look at
  in the picture. "Pink is a light red colour" is a label, and a label is not a
  lesson. The steps that end in a question stay short so the question is heard
  last. The model is told so in `TEACHER_SYSTEM_PROMPT` and
  `lesson.BRIEFS[EXPLAIN]`; the no-model path reads several sentences out of the
  author's passages and appends one from `agent.EVERYDAY_EXAMPLES`, which is
  hand-written and only covers the colours and shapes the app can draw - a
  concept with no authored example gets none rather than an invented one. The
  picture beside the words is read from the level's **title** first
  (`visuals.from_concept`), and from what comes after its colon, or a level on
  pink draws a red circle as soon as its notes mention red.
- **A stage is one item of today's frozen plan - one subject - and the day is
  all of them.** The schedule is not something the teacher consults - it *is* the
  shape of the sitting. `service.open_session` snapshots `plan_service.todays_plan` into
  `playground_sessions.plan_topics`, teaches them in order, and when the last one
  is through writes `status = "day_complete"`. That row plus
  `plan_service.is_day_complete` is the lock: **the class will not reopen until
  tomorrow's plan exists**, and a reload cannot get past it because the refusal
  is the server's. A sitting whose `plan_date` is not today is yesterday's and is
  closed rather than resumed.
- **Finishing a stage is the only thing that moves the Adventure map.** The
  topic goes to `learning_service.award_topic_completion` - the same
  deterministic scorer the conductor ends a lesson with - out of a score computed
  from that stage's own `topic_correct` / `topic_answered`, where a question the
  teacher had to answer for the child counts as one that did not land. That marks the level
  done, pays the manifest's stars, unlocks the next level and re-checks the
  certificate. Every answered question is written to `attempts` through
  `history_service`, so mastery, the weak-skill list and the policy reward all
  see the same history.
- **Adventure is a progress board.** `/adventure` and its subject and level pages
  show what is finished, what today's plan holds, what is sleeping until its turn
  and what is still locked. Nothing on it starts a lesson - no `ConductedClass`,
  no `/learning` - because a second way in could open a level the schedule had
  not reached.
- **The site opens on the class.** `/` and `/home` send a signed-in child
  straight to `/ai-teacher`; a guest still gets the sign-up hub. The day's plan
  rides above every screen as `components/shared/ScheduleStrip.tsx`.

## Child-facing copy

- Keep it short, gentle, and non-technical.
- Narrate in English in every subject, the Hindi-language ones included: there,
  Hindi is the content being taught, quoted in Devanagari inside an English
  sentence.

## Still off the table

- Payments, leaderboards, and real personal data beyond a parent's email and a
  child's first name and birth month.
- Automated consent. DPDP and COPPA both require an explicit act by a person,
  so `parents.consent_granted_at` is written by the parent surface only.
