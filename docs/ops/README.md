# Operations Index

One file per operation. Each is self-contained: the problem, the design, measurable
acceptance criteria, and a copy-paste prompt.

**Scope: `backend/` and `frontend/` only. `mobile/` is a frozen read-only reference.**

| File | Operation | Blocked by | Touches |
|---|---|---|---|
| [`OP-01-database.md`](./OP-01-database.md) | Advanced PostgreSQL — every byte of user data persisted | — | backend |
| [`OP-02-authentication.md`](./OP-02-authentication.md) | Real auth, sessions, parental consent | OP-01 | backend + web |
| [`OP-03-entry-flow.md`](./OP-03-entry-flow.md) | Login → adventure · logout → home · age → toddler | OP-02 | backend + web |
| [`OP-04-ai-navigation.md`](./OP-04-ai-navigation.md) | AI drives the UI for children who cannot read | OP-03 | backend + web |
| [`OP-05-ai-tracking.md`](./OP-05-ai-tracking.md) | Per-child learner profile + scheduled study plan | OP-01, session engine | backend + web |
| [`OP-06-responsive.md`](./OP-06-responsive.md) | Full mobile responsiveness | — | web |

## How these relate to the other docs

`../EXECUTION.md` holds the **master run order** across all 24 steps. These OP files are
**deep dives on the six operations you asked about specifically** — they expand what
EXECUTION.md summarises in one row, and they add design that was not previously specified
(entry routing, AI navigation, learner profiles).

Where an OP file and an architecture doc disagree, the OP file is newer and wins.

| Doc | Role |
|---|---|
| `../EXECUTION.md` | Master order and scope. Start there. |
| `../backend-architecture.md` | Backend target design, 9 phases |
| `../frontend-architecture.md` | Web target design, 9 phases |
| `../upgrade-plan.md` | Responsive, study plan, reference-porting |
| **`OP-*.md`** | **Per-operation deep dives — this folder** |

## Order

```
OP-01 database  ──┬──► OP-02 auth ──► OP-03 entry flow ──► OP-04 AI navigation
                  │
                  └──► OP-05 AI tracking (also needs the session engine)

OP-06 responsive ── independent, run any time
```

**One operation per session. Never two.**

## The rules that hold across all six

1. The LLM never decides correctness, scores, stars, unlocks, or which lesson comes next.
2. The client never computes any of those either.
3. Nothing lives in memory on the server or in `sessionStorage` in the browser.
4. Every child-facing control is at least 64×64 px.
5. A child must never reach a screen with no way forward.
6. `mobile/` is never modified.
