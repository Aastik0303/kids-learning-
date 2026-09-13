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
- **What may be cached is authored content, and nothing else.**
  `app/services/cache.py` is the one place a cache is built: bounded, optionally
  expiring, and computing a missing value exactly once so a restart is not a
  stampede. The manifest, the syllabus's questions, a level's games and notes,
  a topic's title, the skill graph - files read at boot, the same for every
  child, changing only on deploy. **A child's truth may not be cached**: stars,
  mastery, unlocked topics, today's plan and its cursor are written by the
  request that earned them and read by the next one, and a cache in front of
  them is a star that appears twice or a level refused after it was finished.
  **Nor may a session**: whether the `auth_sessions` row is still open is asked
  on every request on purpose, because a cached "yes" is a sign-out that signed
  nobody out. `child_store`'s map is an identity map and not a cache - it hands
  back the same object the writers mutate, so there is nothing in it to go
  stale. Every content cache **registers how to clear itself**, and
  `reload_curriculum()` empties all of them together: a cache built from the
  previous manifest and left behind is a test answered out of a syllabus that no
  longer exists, and it surfaces as an unrelated failure much later.
- **The network is most of what "slow" means, so the read-only routes are
  conditional and everything is compressed.** `app/api/middleware.py` puts an
  `ETag` on the `/curriculum` family and answers a matching `If-None-Match` with
  304 and no body at all; `Cache-Control` is a minute plus `must-revalidate`, so
  a re-authored syllabus is visible within the minute rather than whenever a
  cache felt like expiring. GZip takes a class detail from 33KB to under 7KB.
  Only authored content may go in `CACHEABLE_PREFIXES` - one child-scoped path
  added there is a class showing yesterday's stars. `Server-Timing` carries the
  server's own milliseconds, so "the class feels slow" is answerable from the
  browser's network panel. The middleware order in `app/main.py` is load-bearing
  twice over: the rate limiter sits **inside** CORS, or a 429 reaches the
  browser without the headers that let it read the refusal and shows up as a
  CORS error instead; and the ETag sits **inside** GZip, or the body is hashed
  after compression and two browsers get two ETags for one answer.
- **Rate limiting is per route class, and it fails open.**
  `app/services/rate_limit.py` is a token bucket - a burst is exactly what a
  page load is, and a fixed window would let a caller spend two windows' worth
  in one second across the boundary. The classes are priced by what they cost
  this account: `auth` is tight because it is the surface worth attacking,
  `speech` and `ai` because each call spends CPU or money, `read` is generous
  because it is cached. **Two buckets are checked**: the caller's own - keyed by
  their bearer token when signed in, because a great many of these families are
  behind carrier-grade NAT where thousands of unrelated people share one
  address and a per-IP limiter would have them taking each other's class
  offline - and a much higher **per-IP ceiling**, which is what stops somebody
  inventing a fresh token to get a fresh bucket. `/health` is never limited: it
  is what the platform polls to decide this instance is alive, and limiting it
  is how a busy server gets restarted for being busy. Anything that goes wrong
  inside the limiter is logged and the request is served - a limiter that breaks
  costs a log line, never a child's lesson. The buckets live in the process, so
  two workers allow roughly twice these numbers; that is deliberate, and the
  alternative is needing Redis up to answer a request at all. The suite sets
  `RATE_LIMIT_ENABLED=0`, because a test file drives a whole morning through one
  client in seconds and is not a caller.
- **A password is not a sign-in on its own: a code is emailed, and only that
  code mints a session.** `POST /auth/login` checks the password and answers
  with a **challenge** - `otp_required`, a handle, a masked address, and no
  token anywhere in it - deliberately a different shape from `AuthResponse`
  rather than one with empty fields, because a response that merely looked like
  a session is the easiest thing in the world for a client to treat as one.
  `POST /auth/otp/verify` is the only place a token is minted on this path. The
  password proves what a parent knows; the code proves they still hold the
  address the account is on, and this account holds a child's name, birth month
  and whole learning history. **Google sign-in skips it entirely** - Google has
  already proved the address with its own second factor, and a code on top is
  friction that buys nothing.
  Four things hold it up, and each closes something specific. The **account
  throttle is cleared by the code, never by the password**, or whoever holds a
  leaked password could reset the counter at will and grind the second factor
  for as long as they liked. A challenge **dies after `AUTH_OTP_MAX_ATTEMPTS`
  guesses**, because six digits is one of a million only while the guesses are
  few, and a wrong code is counted against the account as well so a fresh
  challenge per guess is not a way round it. **Opening a challenge spends the
  previous one** - two live challenges is two live codes, and the older is
  usually the one an attacker caused to be sent. And "send it again" is behind
  a **cooldown and a ceiling**, or the button is a way to mail a stranger as
  fast as it can be pressed. Unknown, expired, spent and out-of-guesses all
  answer identically; telling them apart would say which handles are real.
  Neither secret is stored as itself: both are **keyed** hashes
  (`security.keyed_hash`, HMAC with `JWT_SECRET`) rather than plain digests,
  because a million SHA-256s is under a second on any laptop and a plain digest
  of a six-digit code would hand a database thief every code in flight.
  The one door out is `AUTH_OTP_ENABLED=0`, which signs in on the password
  alone - for a deployment that cannot send mail. What must never happen is the
  middle case: **an unconfigured mailer in production refuses the sign-in**
  rather than letting it through without the code, because "we could not send
  it so we let them in" is not a fallback, it is the feature being off. Outside
  development the code is never in the response; on a machine with no SMTP it is
  logged and returned so the flow stays completable, and `ENV` is what bolts
  that shut.
- **There is a mailer now, and two messages leave this app.**
  `app/services/mailer.py` sends the sign-in code and the password-reset link
  over SMTP. The port decides the encryption the way every provider documents
  it - 465 implicit TLS, otherwise STARTTLS - and a failed upgrade is a failure
  rather than a quiet fall back to cleartext. It sends **synchronously**: a
  background thread would make sign-in faster and would also make "we could not
  send your code" unsayable, leaving a parent watching a code box for a mail
  that was never coming. Neither message says anything about a child - no name,
  no class, no progress - because mail is the least private thing this system
  touches. The reset flow's old behaviour of handing its token back in the
  response survives only where there is no mailer and only outside production,
  and a send that fails there is swallowed rather than reported: an answer that
  differed on failure would differ only for addresses that exist, which is the
  enumeration hole the identical answer exists to close.
- **A parent signs in with Google or with a password, and both end in the same
  session.** `POST /auth/google` takes the ID token Google's own script produced
  and `app/services/google_auth_service.py` verifies it before it means
  anything: the RS256 signature against Google's published keys, the issuer, a
  **verified** email address, and - the one that matters most - the `aud` claim
  against `GOOGLE_CLIENT_ID`. A Google-signed token only says "this person
  signed into the app named in `aud`", so a verifier that does not pin the
  audience accepts a token minted for somebody else's app and lets whoever runs
  that app be any of their users here. An unset client id turns the feature off
  rather than loosening that check, and `GET /auth/google/config` is what the
  sign-in screen asks before drawing the button, so it never appears where the
  server could not verify the answer. Google is never itself a bearer for this
  API: what comes back is the ordinary `auth_sessions` row and JWT. An account
  is matched on Google's `sub` first, because an email can be changed on the
  Google side and that id cannot; failing that, on a verified email that already
  has an account, which is **linked** rather than duplicated - that is why the
  `email_verified` check is load-bearing and not a formality. A Google-only
  account has `password_hash` NULL, and `verify_password` refuses an empty hash,
  so a blank password is not a way in. The button is Google's own, rendered by
  their script from accounts.google.com: a hand-drawn lookalike is against their
  branding rules and is the shape a phishing page takes. One-tap is deliberately
  off. **Nothing about an identity provider reaches a child's progress** - the
  answer-key boundary is unchanged, and signing in pays no star and unlocks
  nothing.
- **This is production, and nothing on any surface is a demonstration of
  itself.** There is no seeded demo account, no prefilled credentials on the
  sign-in form, no "this is a prototype" caption and no scripted preview of a
  lesson that the real teacher did not produce - the mobile app's
  `FeatureDemoScreen`, which played a hand-written script with the server down,
  is deleted for that reason: a page that demonstrates a teacher which is not
  the teacher is a promise the product then has to keep. `POST /dev/seed` is a
  development fixture and `app/main.py` does not mount its router outside
  development, because a route that answers 403 in production is still a route
  and still one misread setting away from rewriting a child's ledger. Two
  prototype names survive only for compatibility and are deprecated: the
  `X-Demo-Session` header, which `app/api/deps.py` still accepts because a
  mobile build already on a phone sends it (both clients now send
  `Authorization: Bearer`), and `AuthResponse.session_token`, which those builds
  still read. The web's `demo_*` storage keys are now `saksham.*` and migrate
  themselves on first read, so nobody was signed out by the rename.
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
- **The mobile app is the same class as the web, not a second one.** Its child
  surface is three tabs - **Class**, **Adventure**, **Rewards** - and the app
  opens on the Class, which is the AI Teacher off the same
  `/playground/teacher` endpoints and the same frozen plan
  (`mobile/src/features/learning/useAiTeacherClass.ts`,
  `screens/child/AiTeacherScreen.tsx`). The hook reads the turn and reports what
  the child did; it marks nothing, picks no topic and decides nothing about the
  day. The panda holds the board here too
  (`components/avatar/PandaAvatar.tsx`, `TeacherStage.tsx`), the drawing draws
  itself on it (`components/blackboard/`), the strip shows the day on every
  screen (`components/shared/ScheduleStrip.tsx`), and Adventure is status plus
  the three games - it starts nothing, for the same reason the web's does not.
  Two differences are the platform's rather than the design's: there is no chalk
  tip riding the moving end, because `react-native-svg` cannot give a point
  along a path, and the geometry a line is walked by is measured in JavaScript
  (`blackboard/pathGeometry.ts`) because there is no `getTotalLength` either.
- **The conductor is still there and is nobody's front door now.**
  `mobile/src/features/learning/useConductorClass.ts` and
  `screens/child/ClassScreen.tsx` are unchanged and still registered, as
  `ConductedClass`; the older picked-lesson screens are registered too. None of
  them is on the tab bar, because each was a second way into a lesson and a
  second way in can open a level the schedule has not reached. `/conductor`,
  `/learning` and `/practice` remain for those clients and are marked
  deprecated. Do not put a lesson entry point back on a tab.
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
- **Every fifth day one subject's level steps aside for a poem.**
  `app/playground/poem.py` holds them, written out in full by a person, and
  `plan_service._with_todays_poem` swaps one in. **The day does not change
  length** - a Nursery child's six stages are still six and one of them is a
  poem - because the class teaches one stage per planned item, so an item added
  is a longer sitting for a three-year-old and an item removed is a subject with
  nothing in its place. Which level steps aside walks by the day
  (`poem.replaced_index`), or the same subject would be the one missed every
  time; it is not lost, because it is still that subject's first weak or
  unfinished topic tomorrow. A poem's `topic_id` is deliberately **not in the
  manifest**, and that single fact is what makes every rule which reads the
  manifest already correct about it: `_award_level` finds no topic and returns
  nothing, so no star is paid, nothing unlocks and no certificate is re-checked;
  no attempt is written; no policy episode is committed and no retention probe
  scheduled, because a poem teaches no skill that could be tested two days
  later. It *does* move the plan cursor - a stage of the day that never finishes
  is a day that never finishes. The planner puts it **last**
  (`graph._is_poem`): a poem is the one stage where nothing can be got wrong, so
  it is "finish on a win" more surely than any level, and it has no mastery, so
  left in the ordinary pool it read as the shakiest thing in the day and was
  pulled to the front. **The class that cannot say one steps over it.** A poem
  has no manifest entry, so the conductor - which teaches whatever today's plan
  points at, by looking it up - answered `MISSING_CURRICULUM` for the whole of a
  poem morning once the day's levels were done, and the cursor then stayed on
  the poem for ever because nothing in that loop can finish one.
  `plan_service.todays_level` is the same cursor with the poems taken out, and
  the conductor closes the day warmly when that is all that is left. Stepping
  over is not finishing: the item stays unfinished and the web class still says
  it. **No model touches a poem** - not to write it, not to
  choose it, not to say it: a nursery rhyme has to be the same words every time
  it comes round, or a child cannot say it along with the teacher the second
  time. Each verse names its own picture by hand out of `visuals.THINGS`, and a
  verse that names nothing draws nothing rather than a near-miss.
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
  answer brings the **answer**, and then the class moves on.
  **That third turn is a story, and the answer is the end of it rather than the
  beginning.** Three beats in one turn: a real moment out of the child's own day
  that names no answer (the samosa on the plate, the wheel on the toy car), then
  the picture beside them - which is being drawn on the board as the words are
  said - to count or trace, and only then, in the very last sentence, what the
  thing is called. It used to open with "The answer is triangle. Let me show you
  why", and a child handed the answer in the first second has no reason left to
  listen to the why, which is what the rest of the turn is. `lesson.REVEAL_BRIEF`
  tells the model the three beats; `agent.REAL_LIFE_SCENES` is the hand-written,
  closed set of scenes for the path with no model, and a concept nobody wrote one
  for falls back to the author's notes rather than to an invented scene.
  `agent.EVERYDAY_EXAMPLES` may **not** serve as the first beat - it is allowed
  to name the thing ("A samosa is a triangle") and the first beat is precisely
  where that may not happen. `agent._closed_with_the_answer` is the guard at the
  other end: the closing sentence is appended unless the telling already finished
  on the answer, because a reveal that talks around it and never says it is the
  one failure this turn exists to prevent. It stays **one** turn - `expects:
  "ready"`, unmarked, one narration - because splitting the beats would change
  how a question settles.
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
  than teaching from a neighbour. **The author's question is in the query on
  every turn, the reveal included.** It used to be dropped there, so a reveal's
  query was the level's title alone: "Tap the brown one" was revealed out of the
  passages on the three primary colours and on sorting, with not one word about
  brown in front of the model, and it filled the gap by talking about a bear
  beside a patch of brown. Two reveals in five were reading somebody else's
  notes. Nothing was being protected by hiding it - a reveal is told the answer
  outright, because it has to say it. A topic that authored
  no answerable question falls back to its own subtopics, and only then to the
  title.
  It is fenced a **third** time, on the card's own concept
  (`agent._notes_about`), because the hand-written teaching notes carry no skill
  id for `_about_this_card` to narrow by: `teacher_notes.md` explains the
  circle, the square, the triangle and the rectangle in one "## Shapes" passage,
  so the whole family reached the model and the circle - the paragraph the
  author wrote first - was the most available thing on the page. A child who got
  "Tap the triangle!" wrong was hinted with a lesson on the circle. The unit is
  a **paragraph**, because a paragraph's examples ("a wheel, a plate, the sun")
  name no shape at all, so dropping lines or sentences leaves the circle's
  examples under the triangle. It only ever removes words - the answer still
  never enters a query - and a passage with no paragraph about this concept is
  left whole, the same rule `_about_this_card` keeps. The concept is the card's
  and it is decided **before a word of the turn is chosen**
  (`agent._card_concept`): reading it off the level's title and correcting the
  *picture* to the answer further down is what left the board saying triangle
  while the words said circle, on the explaining turn as well as on the repairs.
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
- **The examples the teacher *says* are shown while it says them.** An
  explaining turn always reaches for something the child has seen - "A is for
  apple", "round like a ball" - and a child who cannot read hears that word with
  nothing to look at, because the screen is holding the letter. So the letter
  steps aside for three seconds while the example is on the screen, and then
  comes back. `frontend/lib/spokenExamples.ts` finds them, and **no model is
  involved**: the explanation is split into words, each is stripped of
  punctuation and reduced to its singular, and what survives is looked up in
  `visualIcon`'s own closed picture table - a word that table has no picture for
  is not an example, and that is the whole test. Three rules bound it. It reads
  **only the explanation**, never the feedback before it or the question after
  it, because the question is the moment the concept itself has to be on screen.
  It **never illustrates an option**: on a match or a quiz the teacher says the
  answer's name on the way into the question, and a picture of it is the answer
  given away. And two examples may not fall inside one three-second hold, so
  they cannot fight over the screen. Timing is an estimate - Edge TTS returns a
  clip with no word boundaries, so a cue is placed by where its word falls at
  that voice's real rate (`MS_PER_WORD`, about 155 wpm, deliberately faster than
  `readingMs`'s deliberately-slow floor); the three-second hold absorbs the
  drift. The concept underneath is **hidden, not unmounted**, or the chalk would
  redraw itself from nothing every time an example came and went.
- **The teacher holds the picture up.** In the class the panda and the drawing
  are **one** picture: `components/avatar/TeacherStage.tsx` stands the panda in
  its `holding` pose behind a board and lays the lesson's drawing on the board's
  face, with `PandaPaws` painted over the top so the paws close over both. Two
  pictures stacked - a panda, and separately a diagram under it - is one too
  many for a three-year-old, who looks at whichever moved last; held up, the
  face doing the reacting is directly above the thing it is reacting to. It is
  three layers over one square: two SVGs sharing a `viewBox` with the drawing
  placed between them by percentages taken from the same coordinates, so the
  board rect in `AvatarFallback` and `.teacher-display` in `globals.css` are one
  number and move together. The `holding` pose is a single transform on
  `panda-upper`, which is why all fourteen feelings still work inside it
  untouched. **This does not put the old blackboard back**: the frame the user
  had removed was a slate around the whole card, and what came back is a board
  the *teacher* is holding. Do not re-add a frame around the card itself.
- **The picture draws itself, and there is no board around it.**
  `frontend/components/blackboard/` is what the child looks at: `chalkArt.ts`
  holds hand-written stroke coordinates, `ChalkDrawing.tsx` walks each path
  along its own length with the drawing tip riding the moving end,
  `ChalkGlyph.tsx` writes a letter or a Devanagari word as a wipe (a glyph has
  no path to walk, and guessing at stroke order would teach the wrong one), and
  `TeachingDrawing.tsx` draws the one thing the card is about while it is being
  said. The point is timing: a finished picture that appears the instant the
  narration starts has been looked at and left before the words reach it. It
  began as a blackboard - a frame, a slate, white chalk - and the user asked for
  the frame off; the lines are ink now, which is what `ChalkDrawing`'s `tone` is
  for, and they are drawn on the board the teacher holds (above). It **adds no content of its own** - it draws
  the `visual_kind` / `visual_value` the server chose - it never prints the
  explanation, and it shows no everyday examples. A token with no coordinates
  draws nothing rather than a near-miss, the rule `visualIcon` keeps for अनार.
  `frontend/components/curriculum/ExampleStrip.tsx` still draws the strip on
  Adventure's level pages, and exports the caption both surfaces write.
- **A cow is a picture the app may name, and only a person may name it.**
  `visuals.THINGS` is the closed list of everyday tokens `chalkArt.ts` has real
  strokes for, and `thing:cow` is a fifth kind beside letter, number, count,
  shape and colour. It exists because a shapes-and-letters vocabulary left
  forty-two levels - every animal, fruit and vehicle in the syllabus - teaching
  with an empty card. **`parse` does not accept it**: the model can never name a
  thing. The only producer is `visuals.for_card`, out of the answer a person
  wrote in the syllabus, and `visuals.from_concept` out of a level's own title -
  never out of a model's prose, which is what the `things` flag on `_read`
  gates. The client is the second gate: a token it has no strokes for draws
  nothing. `tests/test_playground_teacher.py` reads the TypeScript and fails if
  a name in `THINGS` has no drawing behind it.
  A thing is **not** lesson furniture: `examples._is_lesson_furniture` asks
  whether the concept is a *glyph* kind, because an apple is exactly what an
  example is for.
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
- **A level's page deals one of its games and starts it.** The child never
  chooses which: opening a level picks one of the three at random and plays it,
  because three cards to choose between is a menu and a menu is a reading task
  in front of a three-year-old. Any of the three is about the same level and any
  is a fine way to go back over it. Two controls remain and neither is a choice
  about *what* to play - 🎲 deals another one, ← puts the level page back - and
  the deal happens in the load handler rather than in a render body, because
  `Math.random()` during render gives the server one answer and the browser
  another and React rebuilds the page on hydration.
- **A level's page hands the level back as three games.**
  `GET /curriculum/topics/{id}/games` is `app/playground/games.py`: **Find it!**
  (the author's question, tapped), **Find the pairs** (the level's own pictures,
  face down) and **Pop it!** (three of the right one in a field of bubbles). It
  is how a child goes back over something so it does not fade, and it is the
  only thing besides a status the map may hand them. This replaced the level's
  *notes* - the author's teaching lines, printed and read out - because revising
  by re-reading is a grown-up's skill and this page is for a three-year-old, who
  goes back over a thing by playing with it again. `notes.py` and its endpoint
  are still there and nothing on the web calls them.
  Five rules keep the games from being a second classroom. **No model** - every
  question, choice and picture came out of the authored syllabus through
  `questions.for_topic`, so the same level offers the same three games on every
  afternoon. **The answer shown is the answer marked** - `stage.contains_answer`
  picks which option is right, the same rule the class marks a tap with, and a
  round it cannot resolve to exactly one option is dropped rather than shown.
  **Nothing is marked** - no attempt, no probe, no episode, no star, no plan
  movement, and after the one GET nothing goes back to the server at all.
  **Not for a locked level** - the same reason the map does not link to it.
  **A level that authored too little gets fewer than three**, never an invented
  one, and a token the client has no drawing for is dropped rather than dealt as
  a neutral mark. The games are `frontend/components/games/`, and they are built
  for a two-year-old's hands: every target is at least 5.5rem, a wrong tap is a
  wobble and nothing else, the bubbles bob where they stand rather than crossing
  the screen (nothing has to be *caught*), and the question is spoken because
  nobody playing it can read. **The memory cards are squares and the bubbles
  are circles**, and either shape only holds while its tile is a true square -
  so a playing board's tile is `min(100cqw, 100cqh)` of the cell it sits in
  (`.game-grid > li` is the container that measures it). Asking for
  `height: 100%` against `aspect-ratio: 1 / 1` is **not** a square: the height
  is definite, the ratio then decides only the width, and `max-width` squashes
  that width without giving the height back - which is how eight memory cards
  came out as eight tall blue pills on a phone. The same mistake, in the same
  words, was holding `.class-stage .teacher-stage`, and there it slid the
  board's drawing off the paws holding it, because the panda centres itself
  inside its box and `.teacher-display` is placed by percentages *of the box*.
  Memory cards are two across on a phone for the same reason the targets have a
  floor: four columns of a 390px screen cannot hold a card that big.
- **The site opens on the class.** `/` and `/home` send a signed-in child
  straight to `/ai-teacher`; a guest still gets the sign-up hub. The day's plan
  rides above every screen as `components/shared/ScheduleStrip.tsx`.
- **The panda's face is a channel, and it is read across a room.** The class is
  the one screen where the child cannot read a word, so the verdict has to be
  legible on the avatar: **right** is `celebrating` (grin, cheeks, bounce,
  sparkles), **wrong** is `encouraging`, and `thinking` is worn while the
  teacher works and through every hint. `avatarStateForTeacher` takes a
  `reacting` flag beside `speaking` and the class holds it open for
  `REACTION_MS` after a marked answer, because "Well done!" is under a second
  of audio and the delight used to be over before a three-year-old had looked
  up. Only a *marked* turn starts it - a panda that celebrated its own
  explanations would be congratulating the child for listening. **A wrong
  answer still never makes it sad**: `sad` stays reserved for the app's own
  failures, the microphone that heard nothing and the server that did not
  answer, because a child who learns that missing a letter upsets the panda
  learns to stop answering.
- **On a phone and a tablet the class and a game fit one screen.** The child
  holding the device is two or three and does not scroll to find the rest of
  the question: a screen that is cut off simply looks finished, so an answer or
  a microphone below the fold is, to them, not there at all. `AppShell`'s `fit`
  prop and the "One screen" section at the end of `globals.css` are the whole
  mechanism - below `xl:` the shell is exactly `100dvh` (the cutoff is 1280px,
  because a tablet held sideways is 1024 wide) and the page is a flex
  column in which **one** child stretches (the chalk drawing on a teaching
  card, the board inside a game) while everything else keeps its natural
  height. Playing a game takes the whole screen
  (`.level-games[data-playing="true"]`), because the level page is a page and
  playing a game is not. Two things the room may **not** come out of: the touch
  floors (96px early, 64px child - it comes out of padding, chrome and the
  picture instead) and the schedule strip, which is on every screen by rule and
  is compacted rather than dropped. What did give way on the small screens is
  everything written for the grown-up reading along: the step and strategy
  lines, the words on the control pills, the typing box (folded behind ⌨️,
  which is `chrome` because typing is not a child's control) and the level
  page's syllabus list (a `<details>` below `xl:`), and the line naming the
  turn's strategy, source and retrieval, which is gone from every size - it was
  written for whoever was building this, and `playground_turns` still records
  all three. Nothing else is dropped - it is all one tap away.
  **From `xl:` up the level page flows as it always did, and the class does
  not.** A laptop has the height for most pages and it does not have it for
  this one, so the class is one screen at every width - the same column, with
  none of the squeezing, because up there the header, the strip and the padding
  can keep their sizes. `:has(.class-page)` is what holds the desktop rules off
  the level page, which is the only other `fit` page. The teacher is the child
  that stretches, and that is the point rather than a detail: a bigger avatar
  and everything fitting are the *same* requirement, and sizing the avatar with
  a flat width (`22rem`) is what made them look like opposite ones. The answers
  gave up the room for it - the emoji and the word under it are smaller, the
  button sits exactly on its touch floor rather than a rem above it, and the row
  of them is `repeat(auto-fit, minmax(6rem, 1fr))` rather than two columns flat,
  because a tile cannot be shorter than its floor but three answers need not
  take two rows to say so - and the floors themselves still do not give.

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
