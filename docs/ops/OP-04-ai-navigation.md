# OP-04 — AI Navigation for Children Who Cannot Read

**Goal:** a 3-year-old who cannot read, has never used a website, and does not know what a
button is can complete a full learning session without adult help.
**Blocked by:** OP-03
**Touches:** `backend/` + `frontend/`

---

## 1. The problem

The app is currently built like a website: text labels, menus, multiple choices per screen,
and an assumption that the user will work out what to do. The actual user is 3 to 5 years
old, pre-literate, and has no model of what a link or a nav bar is.

This is not an accessibility nicety. It is the product. If a child needs a parent sitting
beside them to operate the interface, the product has failed at its core promise.

**The reframe:** the AI guide is not a helper layered on top of the UI. For this user, the
guide **is** the interface. The visual layer is what the guide points at.

---

## 2. Seven design rules

These constrain every child-facing screen.

1. **The guide speaks first, always.** Every screen auto-speaks its instruction on arrival.
   The child never has to work out what this screen is for.
2. **One decision per screen.** Two tappable things for toddlers, at most four for 3+.
   Never a grid of options.
3. **Nothing is text-only.** Every control is icon + colour + voice. Text exists for the
   parent looking over the shoulder — it never carries meaning alone.
4. **The guide moves you on.** After a correct answer the guide says "let's go!" and
   advances. The child is never asked to find "next".
5. **The guide can point.** Highlight, scroll to, and demonstrate — so "tap the circle"
   is accompanied by the circle actually pulsing.
6. **No dead ends.** Every screen has a guide-driven way forward. A stuck child is a bug.
7. **Silence is a failure state.** If nothing has happened for a few seconds, the guide
   re-engages. It never waits indefinitely.

---

## 3. The idle escalation ladder

The core mechanism for rule 6 and 7. Timers reset on any input.

| Elapsed (3+) | Elapsed (toddler) | Guide does | LLM? |
|---|---|---|---|
| 8 s | 12 s | Repeats the instruction, unchanged | **No** — template |
| 18 s | 25 s | Adds the authored hint **and highlights the target** | **No** — template |
| 30 s | 40 s | Re-explains more simply, or drops to a prerequisite | Yes |
| 45 s | 60 s | Offers to do it together — `demo_tap` shows the answer being tapped without submitting | **No** — template |
| 60 s | 80 s | Offers to move on to something easier. Never traps the child. | **No** — template |

Only **one** rung uses the LLM. The rest are templates, which keeps this cheap enough to run
on every screen without touching the AI budget.

The final rung matters most: **a child must always be able to leave a question they cannot
do.** Sitting a pre-schooler in front of an unsolvable problem is how you teach them they
are bad at learning.

---

## 4. First-run tutorial — once per child

A child's very first session opens with a guided walkthrough, driven entirely by the guide:

1. "Hello! I'm here to learn with you." — avatar waves
2. "When I ask something, tap the picture." — `demo_tap` on a sample target
3. "Or press the big button and say it out loud." — highlights the mic, waits for a tap
4. "If you get stuck, press this." — highlights the hand-raise control
5. Straight into the first real activity

Persisted as `children.preferences.tutorial_completed_at`. Shown once, ever. A parent can
replay it from settings. **Never** re-shown automatically — a child who has done it finds
the repetition patronising, and it delays the thing they came for.

---

## 5. The action set

Extends the existing `backend/app/services/guided_navigation_service.py`, which already
defines `APPROVED_ACTIONS` and `APPROVED_GUIDE_TARGETS`. Keep that shape; consolidate the
vocabulary.

```
none · highlight · scroll_to · show_hint · repeat_instruction
start_listening · wait_for_child · demo_tap · play_animation
celebrate · navigate_safe
```

`demo_tap` is the important addition: the guide renders a ghost-finger animation on a target
to show *how* to answer, **without submitting anything**. It teaches the interaction rather
than solving the problem.

### Safe routes — child surface only

```
ALLOWED:  /adventure  /adventure/[levelId]  /practice  /rewards  /story  /certificate
NEVER:    /  /login  /signup  /onboarding  /child/select  /parent/*  any destructive route
```

Checked **twice** — once in schema validation, again in the executor — exactly as the mobile
implementation does. That is why no future caller can reach navigation without passing the
allowlist.

### Target registry

A target is addressable only while its component is **actually mounted**. Requests send the
live registry as `ui.allowed_targets`; the backend validates against that list; the client
re-checks on receipt and drops anything that unmounted in between.

---

## 6. Voice, and what happens when it fails

Voice is the primary input for this age group, and it fails constantly — permissions,
background noise, a child who mumbles, a browser that does not support it.

**Every voice interaction has a tap fallback, always visible.** Not hidden behind "having
trouble?" — visible from the start, because a 4-year-old will not find a disclosure link.

| Failure | Guide says | Child can |
|---|---|---|
| Permission denied | "Let's tap instead!" | Tap — immediately, no dead end |
| Not supported | (never mentions it) | Tap |
| No speech heard | "I didn't hear that. Try again, or tap!" | Retry or tap |
| Too noisy / low confidence | "Let's tap this one!" | Tap |

**The microphone is never open while the guide is speaking.** Enforced in two places — the
audio store refuses to open during speech, and the voice controller holds a settle window
after text-to-speech reports done, because speaker output trails the callback on most
devices. Port this from `mobile/src/features/voice/VoiceController.ts`; it is already
correct there.

---

## 7. What the AI must never do

| Never | Why |
|---|---|
| Decide correctness | Deterministic evaluators own this |
| Award stars, unlock levels, change progress | Server owns this |
| Choose which lesson comes next | Recommendation rules R1–R7 own this |
| Navigate to auth, parent, or destructive routes | Not in the allowlist, checked twice |
| Speak longer than 220 characters | ~12 seconds of speech is a pre-schooler's ceiling |
| Say anything shaming, or ask for personal information | Safety validation rejects it |
| Submit an answer on the child's behalf | `demo_tap` shows; the child still acts |

That last one is a real temptation when a child is stuck, and it must be resisted. Doing it
for them produces a session log full of correct answers by a child who learned nothing.

---

## 8. Acceptance criteria

- [ ] Every child-facing screen auto-speaks its instruction on arrival, within 500 ms of mount.
- [ ] No child screen presents more than 4 tappable choices (2 in toddler mode) — automated count.
- [ ] Every child-facing control has an icon and a voice line; **no control is text-only** — automated check.
- [ ] All five idle rungs fire at the specified thresholds, with toddler thresholds longer — tested with fake timers.
- [ ] Only the third rung calls the LLM; rungs 1, 2, 4 and 5 make **zero** provider calls — asserted with a call counter.
- [ ] Any input resets the idle timer.
- [ ] After the final rung a child can always leave the question — no screen can trap them.
- [ ] The first-run tutorial shows exactly once per child, is replayable from parent settings, and never auto-repeats.
- [ ] `demo_tap` never submits an answer — tested.
- [ ] A guide action naming an unmounted target is dropped client-side even when the backend approved it.
- [ ] `navigate_safe` to `/login`, `/parent/dashboard`, or any auth route is rejected in **both** the validator and the executor — one test each.
- [ ] Every voice failure mode shows a visible tap fallback with no dead end — one test per mode.
- [ ] The microphone never opens while the guide is speaking — tested including the post-TTS settle window.
- [ ] With the LLM provider fully down, a child can still complete an entire session guided by templates alone.
- [ ] Guide speech is capped at 220 characters and truncates on a word boundary.
- [ ] **The end-to-end test is a session completed using voice and taps only, with zero reading required.**

---

## 9. Prompt

> OP-03 is complete, so entry routing is server-driven. Read `docs/ops/OP-04-ai-navigation.md`
> in full, plus `docs/backend-architecture.md` §5 and
> `backend/app/services/guided_navigation_service.py`, which already defines
> `APPROVED_ACTIONS` and `APPROVED_GUIDE_TARGETS` — build on that rather than replacing it.
>
> Make the app usable by a pre-literate 3-year-old with no adult help. Apply the seven rules
> in §2 to every child-facing screen: the guide auto-speaks its instruction within 500 ms of
> mount; no screen offers more than 4 tappable choices, or 2 in toddler mode; no control is
> text-only — every one carries an icon, a colour and a voice line; and the guide advances
> the child after a correct answer rather than making them find "next".
>
> Implement the idle escalation ladder in §3 with the exact thresholds, longer in toddler
> mode, resetting on any input. **Only the third rung may call the LLM** — rungs 1, 2, 4 and
> 5 are deterministic templates. The final rung must always let the child leave a question
> they cannot do.
>
> Consolidate the guide action vocabulary to the closed set in §5 and add `demo_tap`, which
> renders a ghost-finger animation on a target to demonstrate the interaction **without
> submitting an answer**. Implement a live target registry where a target is addressable only
> while mounted, send it as `ui.allowed_targets`, and re-check on receipt. Enforce the child
> safe-route allowlist in **both** the validator and the executor, with `/`, `/login`,
> `/signup`, `/onboarding`, `/child/select` and all `/parent/*` routes absent from it.
>
> Build the first-run tutorial from §4, persisted to `children.preferences.tutorial_completed_at`,
> shown exactly once and replayable only from parent settings.
>
> Give every voice failure mode a visible tap fallback that is present from the start, not
> behind a disclosure. Port the mic-gating from `mobile/src/features/voice/VoiceController.ts`
> so the microphone never opens while the guide is speaking, including the settle window after
> text-to-speech reports done.
>
> Verify with an end-to-end test in which a session is completed using **voice and taps only,
> with zero reading required**, and a second run of the same test with the LLM provider fully
> disabled that still completes on templates alone.
