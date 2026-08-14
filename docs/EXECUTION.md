# Learn Kids — Execution Runbook

**Scope: `backend/` and `frontend/` only. `mobile/` is frozen.**
**Read this first, before any other doc. It tells you what to run and in what order.**
Version 1.0 · 2026-08-13

---

## 0. Scope

| Track | Status |
|---|---|
| `backend/` | **Active** — FastAPI prototype → production |
| `frontend/` | **Active** — Next.js web app |
| `mobile/` | **Frozen.** Not developed, not migrated, not modified. |

`mobile/` stays in the repo as a **read-only reference implementation**. Several patterns
there are already correct and worth copying into the web app — the live guide target
registry, `shouldCallAgent()`, the double-checked safe-route allowlist, the trace geometry.
Copying *from* it is encouraged. Changing it is not. `git diff --stat mobile/` must stay empty.

Where `docs/upgrade-plan.md` W4 says "port from mobile", read that as "copy the pattern from
the reference", not "keep two clients in sync".

---

## 1. The actual problems, ranked by damage

Not by phase number — by what they cost you if left alone.

| # | Severity | Problem | Where |
|---|---|---|---|
| 0 | 🔴 **Blocker** | **Two copies of the project exist, and you are editing the one that is not running.** The live dev server serves `D:\internship\child_ai\frontend` (PID 23072) while edits land in `D:\testcase\frontend`. Every change looks like it did nothing. | `frontend/next.err.log` |
| 1 | 🔴 **Critical** | **The client grades the child.** Answer is compared to `activity.correct_answer` in the browser, stars are awarded, and `path_progress` / `certificate_unlocked` are written to `sessionStorage`. | `frontend/services/learning.ts` — inside `answerLearning()`'s `.catch()` |
| 2 | 🔴 **Critical** | **Login cannot fail.** A failed request returns `session_token: "local-session-<timestamp>"` and a fabricated user. | `frontend/services/auth.ts` |
| 3 | 🔴 **Critical** | **No real persistence.** All backend state is in-memory; a restart erases every child's progress. | `backend/app/services/mock_storage.py`, `mock_auth.py` |
| 4 | 🟠 High | **25 silent fallbacks** hide every backend failure behind mock data, so bugs never surface. | 21 in `frontend/services/`, 4 in `app/` + `components/` |
| 5 | 🟠 High | **Token in `sessionStorage`, and never actually sent.** No `Authorization` header exists. | `frontend/services/session.ts`, `services/api.ts` |
| 6 | 🟠 High | **Rewards and certificates never call the backend.** Stars come from client state. | `frontend/app/rewards/page.tsx` |
| 7 | 🟠 High | **No idempotency.** A retried answer on a flaky connection double-counts. | everywhere |
| 7b | 🟠 High | **A pre-literate child cannot operate the app unaided.** Text labels, multiple choices per screen, no auto-spoken instruction, no idle recovery. The actual user is 3–5 and cannot read. | child surface, everywhere |
| 7c | 🟠 High | **Entry flow ignores who you are.** `app/page.tsx` renders the age picker for everyone, logged in or not; login has no redirect at all; age routing is guessed from `sessionStorage`. | `app/page.tsx`, `components/toddler/AgeGate.tsx`, `app/login/page.tsx` |
| 8 | 🟡 Medium | **Desktop-first CSS with two conflicting breakpoint systems** — CSS uses 640/900, Tailwind uses its defaults. | `app/globals.css` (2,172 lines), `tailwind.config.ts` |
| 9 | 🟡 Medium | **No versioned API.** 20 prototype routes, none under `/api/v1`. | all of `backend/app/api/` |
| 10 | 🔵 Hygiene | **CRLF line endings** have marked 121 files as modified with 15,118 identical insertions and deletions. | repo-wide |

### The one that surprises people

**Problem #1 lives inside a `.catch()` block.** The client only grades the child *when the
backend call fails*. So deleting the fallbacks (problem #4) removes the grading bug as a
side effect — and that work has **no backend dependency at all**.

That makes it the highest-value *code* change you can make today, before Postgres, before
auth, before anything. It is Step 1 below.

### But fix #0 first, or none of this will appear to work

Problem #0 is not a code defect — it is a workspace defect, and it silently invalidates
every other step. If the server you are looking at is serving a different directory from
the one you are editing, then Step 1 will "not work", Step 2 will "not work", and you will
spend days debugging code that was never loaded. Resolve it before touching anything else.

---

## 2. Run order

Each step names the document and phase that holds its prompt. Copy that prompt verbatim
into a fresh session. **One step per session. Never two.**

| Step | What | Prompt lives in | Blocked by | Fixes |
|---|---|---|---|---|
| **0a** | **One working copy — kill the stale server, pick a canonical directory** | **below, §3** | — | **#0** |
| 0b | Git hygiene + scope freeze | **below, §4** | Step 0a | #10 |
| 1 | Web: API client, delete all 25 fallbacks | `frontend-architecture.md` FE Phase 1 | — | **#1, #2, #4** |
| 2 | Backend: Postgres, config, logging, Docker, CI | `backend-architecture.md` Phase 1 | — | #3 (start) |
| 3 | Web: mobile-first responsive rebuild | `upgrade-plan.md` W2 | Step 1 | #8 |
| 4 | Backend: auth, children, consent, ownership | `backend-architecture.md` Phase 2 | Step 2 | #3 |
| 5 | Web: real auth + parental consent | `frontend-architecture.md` FE Phase 2 | Step 4 + §5 decision | **#5** |
| 6 | Backend: curriculum as data + seeder | `backend-architecture.md` Phase 3 | Step 4 | #9 |
| 7 | Web: curriculum from server, collapse toddler stack | `frontend-architecture.md` FE Phase 3 | Step 6 | #9 |
| 8 | Backend: session engine + deterministic evaluation | `backend-architecture.md` Phase 4 | Step 6 | **#1, #7** |
| 9 | Web: server-authoritative sessions | `frontend-architecture.md` FE Phase 4 | Step 8 | **#1, #7** |
| 10 | Backend: mastery, recommendations, rewards, unlocks | `backend-architecture.md` Phase 5 | Step 8 | #6 |
| 11 | Web: mastery bands, reasons, server rewards | `frontend-architecture.md` FE Phase 5 | Step 10 | **#6** |
| 11a | **Entry flow: login → adventure, logout → home, age → toddler** | `ops/OP-03-entry-flow.md` | Step 5 | **#7c** |
| 11b | **AI navigation for children who cannot read** | `ops/OP-04-ai-navigation.md` | Steps 11a, 16 | **#7b** |
| 12 | Web: shared UI foundation from the reference | `upgrade-plan.md` W4a | Step 3 | — |
| 13 | Web: one activity renderer + 8 activity types | `upgrade-plan.md` W4b | Steps 9, 12 | — |
| 14 | Web: missing screens (guest home, parent gate, recap…) | `upgrade-plan.md` W4c | Step 12 | — |
| 15 | Backend: AI guide, safety, doubts | `backend-architecture.md` Phase 6 | Step 10 | — |
| 16 | Web: guide contract, target registry, hand-raise | `frontend-architecture.md` FE Phase 6 | Step 15 | — |
| 17 | Web: guide parity from the reference | `upgrade-plan.md` W4d | Step 16 | — |
| 18 | Backend: study plan engine | `upgrade-plan.md` W3 (backend) | Step 10 | — |
| 19 | Web: Today's Plan | `upgrade-plan.md` W3 (frontend) | Steps 18, 12 | — |
| 20 | Backend: speech, certificates, worker, storage | `backend-architecture.md` Phase 7 | Step 15 | — |
| 21 | Web: speech, tracing, certificates | `frontend-architecture.md` FE Phase 7 | Step 20 | — |
| 22 | Backend: hardening, load test, chaos, cutover | `backend-architecture.md` Phase 8 | Step 20 | — |
| 23 | Web: CWV, a11y, E2E, cutover | `frontend-architecture.md` FE Phase 8 | Step 22 | — |

### What can run in parallel

**Step 0a comes first, always.** Nothing else can be trusted until you are certain the
server you are looking at is serving the directory you are editing.

After that, steps **1, 2 and 3** have no dependency on each other. If you have the capacity,
run them concurrently — web fallback removal, backend Postgres, and the responsive rebuild
touch different files entirely. From step 4 onward the chain is mostly serial: each web
phase needs its backend phase's gate.

### Where the real risk sits

Steps **8 and 9** are the load-bearing pair. Everything before them is scaffolding;
everything after assumes the server owns truth. If you only get halfway through this list,
get to Step 9.

---

## 3. Step 0a — One working copy

**Do this before anything else. It takes ten minutes and it is currently blocking everything.**

### The evidence

`frontend/next.err.log` says it outright:

```
⨯ Another next dev server is already running.

- Local:        http://localhost:3000
- PID:          23072
- Dir:          D:\internship\child_ai\frontend      ← serving from HERE
```

And `frontend/next.out.log` confirms a second server was pushed onto another port:

```
⚠ Port 3000 is in use by process 23072, using available port 3001 instead.
⚠ We detected multiple lockfiles and selected the directory of
  D:\internship\child_ai\package-lock.json as the root directory.
  Detected additional lockfiles:
    * D:\internship\child_ai\frontend\package-lock.json
```

So there are two checkouts of this project on the machine:

| Copy | Evidence |
|---|---|
| `D:\testcase\` | Holds the `.git` repo and all of `docs/` |
| `D:\internship\child_ai\` | What the running dev server (PID 23072) is actually serving |

This is not a git problem, not a cache problem, and not a Next.js bug. Edits are going to
one directory and the browser is rendering the other.

### The fix

```bat
taskkill /PID 23072 /F

cd /d D:\testcase\frontend
rmdir /s /q .next
npm run dev
```

Open the port the terminal prints. `package.json` currently declares `next dev -p 5000`,
so it will be **5000** — not 3000. The old logs show 3000/3001 because at that time the
script had no `-p` flag.

If `taskkill` reports the PID is gone, find whatever is holding the port:

```bat
netstat -ano | findstr :3000
netstat -ano | findstr :5000
```

### Then pick a canonical copy — and only one

Two checkouts will cause this again within a week, and each time costs twenty minutes of
confusion before anyone thinks to check which directory is being served.

Decide which is real, then **rename the other rather than deleting it**:

```bat
ren D:\internship\child_ai  child_ai_OLD_do_not_use
```

Renaming beats deleting: if it turns out the wrong one was archived, it is one command to
undo, and the rename immediately breaks anything silently depending on the old path — which
is exactly what you want to discover.

**One thing to check before deciding:** all five documents in `docs/` currently live in
`D:\testcase\docs\`. If `D:\internship\child_ai\` turns out to be the real working copy,
copy `docs/` across before archiving. Also confirm which copy has the git history you care
about — `git log --oneline -5` in each.

> **Prompt — Step 0a**
>
> There are two checkouts of this project on this machine and the running Next.js dev server
> is serving the one that is not being edited. `frontend/next.err.log` records
> `Another next dev server is already running — PID 23072, Dir: D:\internship\child_ai\frontend`,
> while the git repository and the `docs/` folder live in `D:\testcase\`.
>
> First, establish the facts without changing anything: for each of `D:\testcase` and
> `D:\internship\child_ai`, report whether it is a git repository, its current branch, the
> last five commits, whether `docs/` exists, and the most recent modification time under
> `frontend/app` and `frontend/services`. Then check what is actually listening on ports
> 3000, 3001 and 5000.
>
> Present a recommendation for which copy should be canonical, based on git history and
> recent edit activity — do not act on it yet, show me the comparison first.
>
> Once I confirm the canonical copy: stop every stray dev server, delete the stale `.next`
> directory in the canonical copy, verify `npm run dev` starts cleanly on the port declared
> in `package.json` and that editing a visible string in `app/home/page.tsx` hot-reloads in
> the browser. Then rename the non-canonical directory with an `_OLD_do_not_use` suffix
> rather than deleting it, after first copying across anything it holds that the canonical
> copy does not — check `docs/` and any `.env.local` in particular. Do not delete any
> directory, and change no application code.

---

## 4. Step 0b — Git hygiene & scope freeze

Five minutes, and it prevents a 15,000-line noise commit that would destroy `git blame`
across the whole repo. Do this before anything else touches a file.

The 121 "modified" files are not modified — every one has identical insertion and deletion
counts because the line endings flipped LF → CRLF. `git diff -w` collapses the entire repo
diff down to two lines in one generated file.

> **Prompt — Step 0b**
>
> This repository has a line-ending problem. `git status` reports 121 modified files with
> 15,118 insertions and 15,118 deletions — the counts are identical because the content did
> not change, only LF → CRLF. Confirm this first by running `git diff -w --stat` and
> checking that it collapses to essentially nothing.
>
> Then fix it permanently: create a `.gitattributes` at the repo root that normalizes text
> files to LF (`* text=auto eol=lf`) with appropriate binary rules for images, fonts, video,
> `.jar`, `.keystore` and the Android/Gradle binaries under `mobile/android/`. Set
> `git config core.autocrlf false` for this repo, run `git add --renormalize .`, and confirm
> `git status` is clean apart from genuinely new files. Do **not** commit unrelated changes
> in the same commit — this must be a single mechanical "normalize line endings" commit.
>
> Also add `mobile/` scope protection: this project is now backend + web only, and `mobile/`
> is a frozen read-only reference. Add a short note at the top of `mobile/README.md` stating
> that the directory is frozen, is retained as a reference implementation, and must not be
> modified. Do not delete it and do not change any code inside it.
>
> Finally, verify `.gitignore` covers `node_modules/`, `.next/`, `.venv/`, `__pycache__/`,
> `.pytest_cache/`, `*.tsbuildinfo`, `next-*.log`, `mobile/android/.gradle/`,
> `mobile/android/app/.cxx/` and `.expo/`. Report anything currently tracked that should not
> be. Change no application code.

---

## 5. The one decision blocking Step 5

Before FE Phase 2 (real auth) can start, someone has to agree this:

> The backend must set the refresh token as an `HttpOnly; Secure; SameSite=Lax;
> Path=/api/v1/auth` cookie when the request carries `X-Client: web`, and read it from that
> cookie on `/refresh`. The access token stays in the JSON body and lives in memory only.

**Why it cannot be skipped:** the backend spec was written assuming a React Native client
with Keychain/Keystore. A browser has no equivalent. Without the cookie, the only place to
put a 30-day refresh token is `localStorage` — which is readable by any XSS and would undo
the entire authentication effort.

It is additive, small, and breaks nothing. Decide it before Step 4 finishes so the backend
work lands in one pass.

---

## 6. Standing rules

These hold for every step in the list.

1. **One step per session.** These prompts are sized for one agent context. Two at once
   produces a shallow pass at both.
2. **Never start a web step before its backend gate passes.** The dependency column is not
   a suggestion — coding against an API that does not exist yet produces confident, wrong code.
3. **Never re-add a fallback.** If a request fails, the user finds out. That is the feature.
4. **Never compute correctness, score, stars, or unlocks in the browser.**
5. **Never put a token in `localStorage` or `sessionStorage`.** If that looks like the only
   way forward, stop and escalate — see §5.
6. **Never modify `mobile/`.** Copy from it freely; change nothing in it.
7. **Never delete prototype code before its replacement is verified.** Implement → migrate
   callers → verify → then remove.
8. **When a spec contradicts the actual repo, stop and report.** Do not silently work around it.

---

## 7. Document map

| Document | What it is |
|---|---|
| **`EXECUTION.md`** | **This file. Start here.** Order, scope, and what blocks what. |
| `backend-architecture.md` | Backend target design + 9 phase prompts |
| `backend-audit.md` | Backend baseline (Phase 0 output) |
| `frontend-architecture.md` | Web target design + 9 phase prompts |
| `frontend-audit.md` | Web baseline (FE Phase 0 output) |
| `upgrade-plan.md` | Responsive (W2), study plan (W3), reference-porting (W4) |
| **`ops/`** | **Per-operation deep dives — six self-contained runnable files** |

### The `ops/` folder

Six operations, each a single self-contained file with its own design, acceptance criteria
and prompt. These expand what the table above summarises in one row, and they add design
that was not previously specified anywhere — entry routing, AI navigation, learner profiles.

| File | Operation |
|---|---|
| `ops/OP-01-database.md` | Advanced PostgreSQL — all 19 tables, connection design, transaction order |
| `ops/OP-02-authentication.md` | Auth, sessions, the web refresh cookie, parental consent |
| `ops/OP-03-entry-flow.md` | Login → adventure · logout → home · age → toddler presentation |
| `ops/OP-04-ai-navigation.md` | AI drives the UI for pre-literate children; idle escalation ladder |
| `ops/OP-05-ai-tracking.md` | Learner profiles + the deterministic daily study plan |
| `ops/OP-06-responsive.md` | Full mobile responsiveness |

If any two documents disagree: `EXECUTION.md` wins on **ordering and scope**, the `ops/`
files win on **design detail for their operation**, and the architecture docs win everywhere
else.
