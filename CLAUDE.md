# AI Nursery Agent Notes

## Source of truth

- Follow `README.md` and, for the AI classroom, the `docs/` family:
  `AI-100-PERCENT-AUTOMATION.md` (what "100% automation" means and its phase
  plan), `AGENT-FLOW.md` (build order and the LangGraph verdict),
  `AI-ARCHITECTURE-DECISIONS.md` (why RLHF was rejected),
  `TEACHING-GRAPH-SPEC.md` (nodes, edges, contract tests), and
  `RETENTION-TESTS.md` (how a taught concept is tested two days later and what
  that pays).

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
  is `app/services/history_service.py` writing `attempts`.
- **A parent's bearer is a signed token, and the row behind it still rules.**
  `app/services/jwt_service.py` mints an HS256 JWT at sign-in, signed with
  `JWT_SECRET` from the environment and pinned to one algorithm, so a forged or
  expired token is refused before a query is made. Its `jti` claim is the
  `auth_sessions` row, and that row is still checked on every request - a
  stateless token cannot be signed out, and sign-out and password reset both
  have to actually end the session here. `JWT_SECRET` has no default: outside
  development an unset key closes sign-in rather than signing with something
  guessable. `AuthResponse` carries the same string as `session_token` (what
  every client already sends back as `X-Demo-Session`) and as
  `access_token` / `token_type` / `expires_in`, and `app/api/deps.py` accepts
  either that header or `Authorization: Bearer`. An opaque token issued before
  this - a bare `auth_sessions` key - is still looked up as one until it
  expires, so nothing already signed in was signed out by the change. Do not reintroduce a
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
  teaches nothing. The web's conductor client has been deleted with the rest of
  the dead code - `ConductedClass.tsx`, `lib/useConductorClass.ts`,
  `services/conductor.ts` and the `Conductor*` types - along with everything
  only it reached (`ActivityView.tsx`, `GuideCoach.tsx`). `/conductor` itself is
  untouched: it is the mobile app's class, and `mobile/` keeps its own client.
  Do not re-add a web conductor client; the AI Teacher is the web's one loop.
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
- **A day is one level from every subject, and that is what a stage counts.**
  `plan_service._candidates` returns exactly one topic per subject - the first
  weak one if the subject has any, otherwise its first unfinished unlocked topic
  - and never two from the same subject, however many of its levels are shaky.
  **Every subject is in every day**: a Play Group child's three are three stages,
  a Nursery or UKG child's six are six. There is no rotation and no sample. There
  used to be both, to share out a three-item cap, and it meant a Nursery child
  met Hindi every other day and EVS every third while their levels sat unlocked
  on the Adventure map. `PLAN_LENGTH` and `graph.MAX_ITEMS` are now only a
  ceiling against a manifest that grows. A longer day is not a longer sitting:
  the plan is frozen and the class resumes at the plan cursor, so a child who
  does two stages and stops picks the rest up later the same day. The AI
  Teacher's stage number is derived from the plan cursor (`plan_index + 1`) and
  never read off a counter, so a sitting cannot go on claiming a stage the day
  does not have.
- **The day's plan is the day's work.** `plan_service.may_open()` is the gate:
  a topic opens if today's frozen plan holds it, or if the child has already
  finished it. Anything else is tomorrow's, including the level the lesson just
  unlocked - unlocking is what a lesson earns, and *when* it is played is the
  plan's to decide. A day holds one level per subject, the subjects rotate by
  day so none is starved, and with no plan at all the gate opens rather than
  locking a child out over infrastructure. Both `/learning/start` and the
  conductor enforce it; refusals are `NOT_TODAYS_PLAN` and are worded for a
  child.
- **The plan carries its own cursor, and a level that was *taught* moves it -
  passing is a different question.** `daily_plan_items.completed_at` says an
  item of today's work is finished, and `learning_service.award_topic_completion`
  writes it **whatever the level scored**, with `playground/service._finish_stage`
  covering the stages that never reach it at all (nothing marked, a topic the
  manifest lost, a level turned unavailable). Passing is what pays the star and
  unlocks the next level; being taught through is what finishes an item of the
  day. Writing the cursor only on a pass is what stopped the whole schedule: the
  levels shipped want 80%, so a small child's ordinary morning left every item
  NULL - `is_day_complete` never became true, `open_session` discarded the
  `day_complete` row and started a clean sitting **on the same level the same
  afternoon**, nothing was ever added to `completed_topics`, and so nothing was
  ever unlocked or scheduled behind it. A level that did not pass is not lost:
  `mark_weak` puts it on the weak list and `_candidates` brings it back tomorrow
  as a `revisit`. The cursor is also not read off the child's lifetime
  `completed_topics`, because the one kind of item the planner freezes *because*
  it is already in that list is a `revisit`, and such a day arrived ticked. A
  `new` item still falls back to the old rule, which is correct for every item
  that is not a revisit.
- **The planner uses no model at all.** `app/ai/planner/` is a LangGraph graph -
  gather, order, freeze - and every node is pure Python. It is run on a timer by
  `app/services/planner_runner.py` and frozen into `daily_plans`, whose `source`
  is always `deterministic`. There *was* a model here, asked for an ordering and
  fenced by a validator that dropped any off-menu, duplicated or malformed
  answer; the fence held and the model went anyway, because ordering a handful of
  known topics is a small decision with a rule that can be read. Do not put one
  back. The order is three rules: **open on something the child will get right**
  (the steadiest level, by the evaluator's own mastery), **meet the shaky levels
  early but never first** (a day must not start with yesterday's struggle), and
  **finish on a win**. A day with nothing shaky in it is left in the class's own
  order, because a routine is what the child is building.
- The teaching policy is wired: `app/services/teaching_policy_service.py`
  chooses a strategy for every teaching turn (with no model configured too),
  `app/services/retention_service.py` schedules and settles the probes that pay
  its reward, and `app/services/plan_service.py` freezes one plan per child per
  day. Anything reaching a language model goes through `app/ai/llm/`.
- **The learned policy is fenced, and the fence is the order of the flow:**
  `candidates -> eligibility filter -> epsilon-greedy -> strategy`.
  `app/policy/eligibility.py` removes what the app's own rules forbid - parking
  early, a spent explanation, a strategy the age band excludes, a prerequisite
  that does not exist, a story for a child who is already close to tears - and
  the selector only ever sees the survivors, so exploration cannot reach a
  strategy the filter removed. The filter never returns nothing: a repeat beats
  a blank turn. `app/policy/leak.py` tells scaffolding and partial clues apart
  from handing the answer over, and only an outright leak sets
  `answer_leak_vetoed`, which costs more reward than a passed probe pays. A
  **teaching** turn - one that explains a thing and then asks about it, which is
  every AI Teacher `match` and `quiz` turn - is judged on the directive frames
  alone ("the answer is X", "tap X"), because naming the thing you are teaching
  is the lesson. Without that distinction one turn in eight was vetoed for
  saying "This is a square", and the table would have learned to stop
  explaining.
- **The hand-written ladder is permanent, and it is the default.**
  `POLICY_MODE` is `shadow` in production: the ladder teaches, the learned
  policy's choice is written beside it, and nothing a child hears changes.
  `on` plus `POLICY_ROLLOUT_FRACTION` walks `0.05 -> 0.10 -> 0.25 -> 0.50 -> 1.0`
  by a stable hash of the child id, so a child does not swap arms mid-sitting.
  `off`, `POST /policy/disable`, and the failure breaker in `app/policy/health.py`
  each send every child back to the ladder without a deploy. A database that
  will not answer is a fallback, never an error on a child's screen. The switch
  is an endpoint so it needs no deploy, which also made it reachable by anybody:
  outside development it wants `POLICY_ADMIN_TOKEN` in an `X-Policy-Token`
  header, and an unset token closes it rather than opening it.
- **A taught concept is tested two days later, and the scheduler decides when.**
  `retention_tests` is the deterministic half of the reward loop:
  one row per teaching episode (`source_teaching_episode_id` is unique - that
  constraint is the whole idempotency of the feature), `due_at =
  episode.taken_at + RETENTION_TEST_DELAY_DAYS`, created by
  `planner_runner.sweep` beside the daily plan because a retention test **is**
  part of the schedule and not a background mechanism of its own. The class
  opens with the due ones (`app/playground/service.py`, the check-in section)
  before today's first stage; the question is a **different** authored question
  about the same concept, picked deterministically out of the syllabus by
  `app/playground/retention.py`, which is what separates transfer from having
  memorised one sentence. `stage.judge` marks it, `app/policy/reward.py` prices
  it from four configurable weights, and
  `db/repositories/retention_tests.settle` pays **the original teaching
  episode's** (state, action) - never the asking of the test, which chooses
  nothing and is nobody's action. Q-learning has no say in when a test happens
  or in what order due tests run; that ordering is a total order over columns
  (`policy.retention.order_key`). A check-in is not a lesson: no strategy is
  spent, no episode is written, nothing reaches `attempts`, the stage tally, the
  plan cursor, a star or an unlock. See `docs/RETENTION-TESTS.md`.
- **A reward is still the probe's and nobody else's, and it is paid once.**
  `policy.pay_episode` is the only function that writes `PolicyEpisode.reward`,
  and both payers go through it - the opportunistic probe and the scheduled
  retention test - so "has this episode already been paid?" is asked in one
  place. An episode with a `reward_resolved_at` is never paid again, whichever
  arrives second. `settle_probe` refuses a probe that already has a `resolved_at`, and reaches
  back only `ATTRIBUTION_WINDOW` days for the episodes it pays, so June's
  retention result cannot be credited to April's teaching. Each episode records
  the question, the rung, the spent count, mastery either side, which arm chose,
  what the other arm would have chosen, the probe's verdict and the Q-value
  before and after - that is what makes a moved table explicable.
  `app/policy/evaluate.py` compares ladder, random and Q-learning by replay over
  those episodes and says "no difference demonstrated" until the evidence clears
  two standard errors. Do not claim the learned policy is better until it does.
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
- **The child asks; the app does not offer a fixed question.** "Ask me
  anything" (a microphone) replaced "Give me a hint": a hint is one of the
  things a child can ask for out loud rather than the only thing they were
  allowed to want. On the web this now lives in `AvatarDock` alone -
  `GuideCoach.tsx` was the lesson panel's copy and went with `ConductedClass`.
  Answers are filtered by `safety_service.safe_text` server-side, so an
  off-topic question comes back as a kind redirection.

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
- **The question a child is asked was written for their class.** On the steps
  where the child chooses - `match` and `quiz` - the question, its answer and its
  choices come from the authored syllabus for that child's own class
  (`app/playground/questions.py`), and the model writes only the explanation that
  leads into it. A topic's title is not a question: "can you show me pre-writing
  strokes?" is a syllabus heading, and a two-year-old cannot show anybody one.
  Retrieval is fenced on `class_id` for the same reason - the nearest passage to
  "letters" in the whole index is often a UKG one - and that fence holds on the
  keyword path while the embedding index is still warming. It is fenced a second
  time on **the question's own skill id** (`agent._about_this_card`): a level
  teaches several things and the notes explain each in a passage of its own, so
  handing the model all of them let it teach whichever it liked - "This is a
  bear, it is big and furry" - under a question that said "Tap the monkey!". The
  level's overview carries no skill id and always stays, and a question whose
  skill has no passage keeps the lot, because teaching from nothing is worse
  than teaching from a neighbour. A topic that authored
  no answerable question falls back to its own subtopics, and only then to the
  title.
- **A question that wants a tap always has something to tap.** `expects: "tap"`
  with an empty `options` is a typing box in front of a child who cannot type,
  which is the turn failing rather than teaching. `agent.ensure_options` repairs
  it - what was already there, then the author's own choices for that answer,
  then the concept's family - and invents nothing when none of those exist.
- **One rule decides which options may be shown and which tap is right.**
  `stage.contains_answer` puts an option on the screen, and `stage.judge` marks a
  tap with the same function. When those two disagreed, a child could tap the
  option the server had chosen as the answer and be told they were wrong; a
  tapped answer is marked by *which button it was*, never by word-matching its
  label. Speech and typing keep the generous word matching. Underscores are
  spaces to `stage.normalise`, because the syllabus writes `standing_line` and a
  child reads "standing line".
- **The class remembers its own sitting.** `playground_turns` has always held
  what was said, what was asked and what came back; nothing read it, so every
  turn was written from nothing and a hint could repeat its own explanation word
  for word. `service._recent_turns` hands the last few turns to the model
  (`agent._sitting_so_far`), and the ask-me-anything answer gets them too. It is
  a **reminder and nothing else**: the step, the strategy and the authored
  question still decide what a turn is, and `stage.judge` still marks in pure
  Python from the authored key. Nothing downstream of a star may read it.
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
  pink draws a red circle as soon as its notes mention red. In Devanagari it is
  the letter **standing on its own** - "स्वर अ आ" teaches अ, and the first
  character of that title is the स of the word for "vowel", which is what the
  board drew on every Hindi level whose author left the colon out.
  **On a card that asks something, the answer decides the concept**
  (`visuals.for_card`), on **all three turns of that question** - the asking,
  the hint and the reveal - and it is applied again in `service._teacher_turn`,
  where the turn leaves the server, so no path through the teacher can put a
  picture on the board that disagrees with the question beside it. A model that
  picks its own visual token is one of those paths: it chose `shape:square`
  while the authored question asked for the circle. A level called "Shapes" has nothing in its title, so
  every one of its cards took whichever shape the notes led with - the circle -
  and "Tap the triangle!" was explained, drawn and illustrated as a circle;
  fixing only the asking left the reveal saying "here is the answer" beside a
  triangle with a ball under it while the answer was the circle. A person wrote
  that answer; the retrieval order is an accident. The notes decide only on the
  explaining step, which has no answer, and when the answer names nothing the
  app can draw.
- **The explanation is said, not printed.** Those three or four sentences are
  for the ear. The web class does not put them on the screen: `speech` is
  narrated and kept only as `sr-only` text for a reader, and what a child looks
  at is the **blackboard** - the one thing this card is teaching, drawn - and
  the **question**, drawn large and the only words on the card. A paragraph of English above a
  two-year-old's question is not something they can read, and it was sitting in
  the one piece of screen they could have used. **The class board does not show
  the everyday examples any more.** It drew two or three of them under the
  concept, and the user asked for them off after they kept arriving beside the
  wrong one - a ball under a square, then under a triangle. What is left on the
  board is the thing being taught and nothing else. The rules below still govern
  `example_items`, which the server still computes and which Adventure's level
  notes still draw, where a child is revising rather than being asked something;
  do not put the strip back on the class board without being asked to.
  `app/playground/examples.py` names that strip: two or three asset tokens out of the `visual_items` the
  author wrote for that very level (`apple` beside Aa, `ball` beside a circle).
  Four rules hold it: an example is never a letter, number, shape, colour or
  writing stroke (those are the lesson's own furniture, not something a child
  has seen for themselves); it is never the answer to the question beside it,
  which is `stage.contains_answer` again, against the key the server is holding
  and the choices already on screen; it **belongs to the concept on the card
  rather than to the level**, because an author who put `circle` and `ball` in
  one activity has said the ball is a picture of the circle, and reading the
  rest of the level for the square card drew that ball beside "tap the square!"
  while the circle was the other choice - an activity that names a concept of
  its own is only read on that concept's card, and one that names none (the four
  balls of a counting level, the apple and ball of a letters level) is the
  level's own picture box; and a concept the author grouped nothing with falls
  back to `examples._CONCEPT_PICTURES`, which is the very everyday example
  `agent.EVERYDAY_EXAMPLES` is already *saying* out loud, as tokens - hand-
  written, closed, only the things the app can draw, and a concept missing from
  it shows nothing rather than an invented example. A Hindi picture word is
  drawn as the Devanagari word with no Roman caption under it.
- **The class teaches at a blackboard, and the board draws itself.**
  `frontend/components/blackboard/` is what the child looks at:
  `chalkArt.ts` holds hand-written stroke coordinates for the tokens the
  syllabus names, `ChalkDrawing.tsx` walks each path along its own length with a
  chalk tip riding the moving end, `ChalkGlyph.tsx` writes a letter or a
  Devanagari word as a wipe (a glyph has no path to walk, and guessing at stroke
  order would teach the wrong one), and `Blackboard.tsx` draws the concept while
  it is being said and each example after it. The point is timing: a finished
  picture that appears the instant the narration starts has been looked at and
  left before the words reach it. The board **adds no content of its own** - it
  draws the `visual_kind` / `visual_value` and `example_items` the server chose
  and filtered - and it never prints the explanation. A token with no
  coordinates keeps its emoji rather than being drawn as a near-miss, which is
  the rule `visualIcon` keeps for अनार.
  `frontend/components/curriculum/ExampleStrip.tsx` still draws the strip on
  Adventure's level pages, and exports the caption both surfaces write.
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
  `history_service`, so mastery and the weak-skill list see the same history.
- **The class is what feeds the learned policy.** Every teaching turn asks
  `teaching_policy_service.decide` for its strategy and writes the episode with
  `commit`, and every marked answer goes through `retention_service.on_attempt`,
  which settles the probe that came due and schedules the next one. Without
  those two calls the whole of `app/policy/` - the rollout, the breaker, the
  leak veto, the offline evaluation - was hanging off `/agent/guide`, which the
  web app no longer reaches: a sitting wrote no episode and no probe, so the
  reward was never paid and the table never moved.
  Two shapes of that wiring are load-bearing. `commit` runs on **the turn's own
  session** (`db.session.session_or`) - a second session opened inside a request
  that already holds one waits out SQLite's whole five-second busy timeout, on
  every turn - while `on_attempt` runs on **its own**, because settling the
  fifth question of a stage calls `award_topic_completion`, which needs the
  write lock the probe would otherwise be holding.
- **The echo is taught and never marked.** `say_it` is asked, hinted and
  revealed like any other step, and `lesson.UNMARKED_STEPS` keeps it out of the
  attempt log and out of the stage's tally. Speech-to-text mishears a
  three-year-old constantly, and a level that failed because a microphone did
  not catch a small voice is the app marking its own hardware. This is the same
  rule `app/conductor/echo.py` has always kept, in the class that pays stars.
  `is_scored` and `is_marked` are different questions: a reveal is not scored
  and still counts against the level, an echo is scored and never counts.
- **Adventure is a progress board, and it shows the whole schedule.**
  `/adventure` and its subject and level pages show what is finished, what
  today's plan holds, what is sleeping until its turn and what is still locked -
  **and the retention check-ins the scheduler says are due**, as a `🧩 Remember`
  badge on the subject card and on the level node, plus a chip in
  `ScheduleStrip`. Whatever the scheduler decides is visible here: a schedule
  the child's grown-up cannot see is one nobody can tell is working. It stays
  status and never a door - nothing on this board starts a lesson or a check-in,
  and no `/learning` - because a second way in could open a level the schedule
  had not reached.
- **A level's page hands its notes back, and says them out loud.**
  `GET /curriculum/topics/{id}/notes` is `app/playground/notes.py`: the level's
  objective and the author's own teaching lines, the everyday pictures beside
  them, and one `speech` string for Edge TTS. It is how a child goes back over
  something so it does not fade, and it is the only thing besides a status the
  map may hand them. Four rules keep it from being a second classroom. **No
  model** - every line was typed by the syllabus author, nothing is retrieved by
  similarity, and the same level reads the same on every afternoon, which is
  what revising needs. **No asking** - the prompt of a card that has an answer
  is the question and is dropped; only its hint survives, and a hint that does
  not name its own subject is given it ("Round, with no corners." ->
  "Circle: round, with no corners.") by `stage.contains_answer`, the same test
  that decides which options may be shown. **Nothing is marked** - no attempt,
  no probe, no episode, no star, no plan movement. **Not for a locked level** -
  a level the child has not been given yet keeps its notes, the same reason the
  map does not link to it. A level whose author wrote nothing says so rather
  than inventing something to fill the space.
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
