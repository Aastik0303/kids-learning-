# OP-03 — Entry Flow, Routing & Age Mode

**Goal:** a logged-in child lands **straight in the adventure**. A logged-out visitor sees
the **home / guest** page. Age decides the presentation, and the server decides all of it.
**Blocked by:** OP-02
**Touches:** `backend/` + `frontend/`

---

## 1. The problem

Today the entry flow is client-guessed from `sessionStorage`, and everyone sees the same
front door regardless of whether they are signed in.

| File | Current behaviour |
|---|---|
| `frontend/app/page.tsx` | Renders `<AgeGate />` — the age picker — for **everyone**, logged in or not |
| `frontend/components/toddler/AgeGate.tsx` | Reads `getChild()` from `sessionStorage`; if `age < 3` → `router.replace("/toddler")`, else renders `<HomeExperience />` |
| `frontend/app/login/page.tsx` | **No redirect logic at all** — grep finds no `router.push` |
| `frontend/app/onboarding/page.tsx` | After creating a child → `/toddler` or `/` |

So: a returning parent whose child has been learning for a month still lands on "How old is
our little learner?" — and the answer is re-asked from a store that empties when the tab
closes. Meanwhile a first-time visitor gets no marketing surface at all.

`/toddler` also exists as a **separate route with a parallel component stack**
(`ToddlerExperience`, `ToddlerHome`, `ToddlerLesson`, `toddlerGuide.ts`, `toddlerVoice.ts`).
That duplication is removed here — see §4.

---

## 2. The decision table

This is the whole specification. Everything else implements it.

| Authenticated | Children | Active child | Age band | Lands on |
|---|---|---|---|---|
| No | — | — | — | `/` — **guest home** (showcase, how it works, sign in) |
| Yes | 0 | — | — | `/onboarding` — create first child + consent |
| Yes | ≥1 | none chosen | — | `/child/select` — who is learning today? |
| Yes | ≥1 | chosen | **under 3** | `/adventure` — **toddler presentation** |
| Yes | ≥1 | chosen | **3+** | `/adventure` — **standard presentation** |

Two rules fall out of this:

1. **The age gate stops being a front door.** Age is collected once, during onboarding, and
   stored on the child row. It is never asked again on every visit.
2. **`/adventure` is the only child entry point.** Toddler and standard are the same route
   in different presentations.

### What "straight into the adventure" means precisely

`/adventure` is not a menu. On arrival it shows, in priority order:

1. An **open session** → resume it at the exact server-recorded step
2. Otherwise **today's plan** (see `OP-05-ai-tracking.md`) → the next incomplete item
3. Otherwise the **next recommended lesson** from rules R1–R7

The child sees one obvious thing to do. Not a grid of choices.

---

## 3. Server decides, client obeys

The client must not derive the landing route from local state — that is the bug being
removed. One endpoint returns everything needed:

```
GET /api/v1/session/bootstrap
```

```json
{
  "authenticated": true,
  "user": { "id": "...", "display_name": "..." },
  "children": [{ "id": "...", "display_name": "...", "avatar_key": "..." }],
  "active_child_id": "...",
  "child": { "age_band": "3-5", "experience_mode": "standard", "locale": "en-IN" },
  "landing": { "route": "/adventure", "reason": "resume_session" },
  "open_session_id": "...",
  "plan_id": "..."
}
```

`landing.reason` is one of
`guest · needs_onboarding · needs_child_selection · resume_session · todays_plan · next_lesson`.

The client routes to `landing.route` and never computes it. `reason` drives which greeting
the guide speaks on arrival (OP-04).

### Avoiding the flash

A returning parent must not see the guest home flicker before being redirected — for a
child that reads as the app being broken.

Use **Next.js middleware** to make the coarse decision from the *presence* of the refresh
cookie before any render:

- cookie absent → allow `/`, redirect child routes to `/`
- cookie present → redirect `/` to `/adventure`

Middleware cannot validate the token (it has no access to the signing key at the edge in
this setup) and does not need to — it is a rendering hint, not authorisation. The real
check is the `owned_child` dependency on every API call. Then the client refines the exact
route from `bootstrap`.

**Never treat cookie presence as authentication.** It only decides which skeleton to paint.

---

## 4. Toddler becomes a presentation, not a route

Delete the parallel stack. `resolveExperienceMode(age_band)` returns `"toddler"` or
`"standard"`, and that flag changes **presentation only**, on the same components:

| | Toddler (under 3) | Standard (3+) |
|---|---|---|
| Text | Almost none — icon and voice carry meaning | Short words alongside icons |
| Touch targets | ≥ 96 px | ≥ 64 px |
| Choices per screen | 2 | 2–4 |
| Voice | Always auto-speaks on arrival | Auto-speaks on arrival |
| Pace | Slower; longer idle thresholds | Standard thresholds |
| Activity types | `introduce`, `voice_repeat`, `tap_choice` only | All types |

Deleted: `app/toddler/page.tsx`, `components/toddler/ToddlerExperience.tsx`,
`ToddlerHome.tsx`, `ToddlerLesson.tsx`, `services/toddlerGuide.ts`, `services/toddlerVoice.ts`.
Kept: `AgeGate.tsx`, but demoted — it is an **onboarding step**, not the root page.

---

## 5. Route groups

```
app/
├── page.tsx                    → guest home (logged out only)
├── (auth)/  login  signup  onboarding
├── (child)/                    → child layout: guide dock, no chrome, no nav bar
│     adventure/  adventure/[levelId]/  practice/  rewards/  story/  certificate/
└── (parent)/                   → parent layout: behind the parent gate
      dashboard/  progress/  settings/
```

**The child surface has no navigation bar.** A 4-year-old does not use a nav bar. Movement
between screens is guide-driven or a single large back-to-adventure control. This is a
deliberate constraint, not an omission — see OP-04.

**Every `(parent)` route sits behind the parent gate** — a written-word arithmetic
challenge an adult can read and a pre-reader cannot. Port the mobile implementation.

---

## 6. Acceptance criteria

- [ ] `GET /api/v1/session/bootstrap` returns the full payload in §3, and `landing.route` is correct for all five rows of the §2 decision table — one test per row.
- [ ] A logged-out visitor at `/` sees the guest home and is never shown the age picker.
- [ ] A logged-in parent with a selected child hitting `/` lands on `/adventure` **with no visible flash** of the guest home.
- [ ] A logged-in parent with zero children lands on `/onboarding`.
- [ ] A logged-in parent with 2+ children and none selected lands on `/child/select`.
- [ ] A child under 3 lands on `/adventure` in toddler presentation; a child 3+ lands on the same route in standard presentation.
- [ ] `/toddler` no longer exists; requesting it redirects to `/adventure`.
- [ ] `toddlerGuide.ts`, `toddlerVoice.ts`, `ToddlerExperience.tsx`, `ToddlerHome.tsx`, `ToddlerLesson.tsx` are all deleted.
- [ ] Arriving at `/adventure` with an open session resumes at the exact server step — tested at three different points.
- [ ] The client never computes the landing route — `grep` finds no age comparison or route decision outside the bootstrap consumer.
- [ ] The child surface renders **no navigation bar** at any breakpoint.
- [ ] Every `(parent)` route is unreachable without passing the parent gate — one test per route.
- [ ] Middleware treats the refresh cookie as a rendering hint only; a forged cookie grants access to no data (the API still 401s).
- [ ] Logout returns to `/` and a back-button press does not restore the child surface.

---

## 7. Prompt

> OP-02 is complete, so real authentication and the refresh cookie exist. Read
> `docs/ops/OP-03-entry-flow.md` in full, plus `docs/frontend-architecture.md` §3.1 and §4.5.
> Rebuild the entry flow so the server decides where every visitor lands.
>
> **Backend:** add `GET /api/v1/session/bootstrap` returning exactly the payload in OP-03 §3
> — authentication state, the parent's children, the active child, that child's `age_band`
> and resolved `experience_mode`, plus a `landing` object holding the route and a `reason`
> from the closed set `guest · needs_onboarding · needs_child_selection · resume_session ·
> todays_plan · next_lesson`. Resolve the landing route entirely server-side using the
> decision table in OP-03 §2, preferring an open session, then today's plan, then the next
> recommended lesson.
>
> **Web:** make `app/page.tsx` the guest home for logged-out visitors only — it currently
> renders `<AgeGate />` for everyone, which is the bug. Route every authenticated visitor
> from `bootstrap.landing.route` and never compute it on the client. Add Next.js middleware
> that redirects based on the **presence** of the refresh cookie so a returning parent never
> sees the guest home flash — treat that presence strictly as a rendering hint, never as
> authentication, and keep the real check on the API's `owned_child` dependency.
>
> Collapse the toddler stack per OP-03 §4: delete `app/toddler/page.tsx`,
> `components/toddler/ToddlerExperience.tsx`, `ToddlerHome.tsx`, `ToddlerLesson.tsx`,
> `services/toddlerGuide.ts` and `services/toddlerVoice.ts`, redirect `/toddler` to
> `/adventure`, and make toddler a presentation mode on the shared components that changes
> text density, touch-target size (≥96px vs ≥64px), choice count and pacing. Demote
> `AgeGate.tsx` to an onboarding step; age is collected once and stored on the child row,
> never re-asked on every visit.
>
> Restructure into `(auth)`, `(child)` and `(parent)` route groups. The child surface must
> render **no navigation bar** at any breakpoint. Put every `(parent)` route behind a parent
> gate using written-word arithmetic, porting the pattern from
> `mobile/src/screens/parent/ParentGateScreen.tsx`.
>
> Test every row of the §2 decision table, assert no guest-home flash for a returning parent,
> assert `/adventure` resumes an open session at the exact step from three different points,
> and assert a forged refresh cookie still yields 401 from the API.
