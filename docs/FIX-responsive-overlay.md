# Fix — The Avatar Dock and Nav Are Eating the Mobile Screen

**Symptom:** on a phone, the guide dock covers the page content (Parent Login, the guest
button, the hero heading), and the nav takes up the entire first screen.
**Cause:** a single CSS rule added by the responsive pass. Not a breakpoint problem — which
is why re-running the responsive prompt will not fix it.

---

## 1. The actual cause

`app/globals.css:2280` applies a touch-target floor to **every** button and link on the
child surface:

```css
[data-surface="child"] :is(button, summary, select, [role="button"], a[href]) {
  min-height: var(--touch-child);   /* 64px */
  min-width:  var(--touch-child);   /* 64px */
}
```

The rule is correct in intent. Its blast radius is wrong: `AppShell` wraps the entire page
in `data-surface="child"`, so the floor also hits **app chrome** — the dock's icon buttons
and the nav pills — which were never child learning targets.

### What that does to the dock

`.avatar-control` (`globals.css:1980`) is designed at `2.45rem` = **39.2 px**.
`min-width: 64px` overrides `width: 2.45rem`, so every control becomes 64×64.

On a ~360 px screen:

```
usable width for controls  ≈ 360 − 24 (dock insets) − 18 (padding)
                             − 70 (avatar column) − 12 (grid gap)   ≈ 236 px
four 64px controls + 3 × 12px gaps                                  = 292 px
292 > 236  →  .avatar-controls has flex-wrap: wrap  →  two rows
```

```
2 rows × 64px + 12px gap                    ≈ 140 px
+ .avatar-message (long sentence, ~3 lines) ≈  90 px
+ dock padding                              ≈  18 px
                                            ─────────
dock height                                 ≈ 250 px, position: fixed, full-bleed
```

`AppShell` reserves only `pb-36` = **144 px**. So roughly **106 px of page content sits
underneath the dock** — exactly what the screenshots show.

### What it does to the nav

Six nav pills, each forced to `min-height: 64px`, in a `flex-wrap` container → **three rows**,
about 216 px plus header padding. That is the whole top of the screen before any content.

**One rule, both symptoms.**

---

## 2. The fix — four parts

### 2.1 Scope the touch floor to learning controls, not chrome

The floor exists so a 3-year-old can hit an **answer**. A dock icon button and a nav pill are
navigation chrome, tapped mostly by a parent. Reuse the existing mechanism — the nearest
`data-surface` ancestor wins — by marking chrome as its own surface:

```tsx
<header data-surface="chrome" className="nav-shell …">
<aside data-surface="chrome" className="avatar-dock …">
```

```css
[data-surface="chrome"] :is(button, select, [role="button"], a[href]) {
  min-height: var(--touch-parent);   /* 44px — still WCAG-comfortable */
  min-width:  var(--touch-parent);
}
```

Add `chrome` to the `:not()` exclusion lists on the existing `child` / `toddler` / `parent`
rules so it is not double-matched.

**Do not weaken the 64 px floor for answer controls.** That rule is right. It was just
pointed at the wrong things.

### 2.2 The dock becomes a FAB on mobile

Below `md`, a fixed panel is the wrong shape — it will always compete with content.

| | Collapsed | Expanded |
|---|---|---|
| **< md** | One 64 px circular avatar button, bottom-right, inside the safe area. **No message bubble, no control row.** | Bottom sheet with a backdrop, containing the message, controls, and chat. Page inert behind it. |
| **≥ md** | Current dock, unchanged | Current behaviour |

This removes the coverage problem outright rather than negotiating with it. When the guide
speaks while collapsed, animate the FAB and show a short toast above it — never a
permanently mounted bubble.

### 2.3 The child surface has no nav bar on mobile

This is already the design in `ops/OP-03-entry-flow.md` §5 — it just was not applied. Below
`md`, hide the six nav pills entirely. Keep the logo, the star count, and the parent button.
Navigation happens through the guide and the adventure screen.

A 4-year-old does not use a nav bar. The six pills are desktop chrome.

### 2.4 Stop reserving space with a magic number

`pb-36` is a guess that is now wrong. Measure the dock with a `ResizeObserver`, write it to
`--dock-height`, and use `padding-bottom: calc(var(--dock-height) + var(--safe-bottom) + 1rem)`.
With the FAB in place this collapses to a small, known value on mobile anyway.

---

## 3. Acceptance criteria

- [ ] On a 360×640 viewport, the dock occupies **≤ 15%** of viewport height when collapsed.
- [ ] No page content is ever covered by the dock — assert the hero, the primary call to action, and the parent button are all clickable at 320, 360 and 390 px wide.
- [ ] Collapsed dock on mobile renders **no** message bubble and **no** control row.
- [ ] Expanding the dock shows a backdrop and makes the page behind it inert.
- [ ] Nav pills are not rendered below `md` on the child surface.
- [ ] Answer controls and the mic are still **≥ 64 px** — the floor must not be weakened where it matters. One test per activity type.
- [ ] Chrome controls are ≥ 44 px and no longer forced to 64 px.
- [ ] `.avatar-controls` does not wrap to a second row at any width from 320 px up.
- [ ] Bottom padding is derived from the measured dock height, not a fixed `pb-36`.
- [ ] Zero horizontal scroll at 320, 360, 390, 412, 768 and 1024 px.
- [ ] Nothing overlaps a safe-area inset on a notched profile.
- [ ] Screenshots at 320×568, 390×844 and 844×390 committed to `docs/responsive/` showing content unobstructed.

---

## 4. Prompt

> The mobile layout is broken: the guide dock covers page content and the nav fills the first
> screen. Read `docs/FIX-responsive-overlay.md` for the diagnosis before changing anything —
> this is **not** a breakpoint problem, so do not add media queries hoping to fix it.
>
> The cause is `app/globals.css:2280`, where the 64 px touch-target floor is applied to every
> button and link inside `data-surface="child"`. Because `AppShell` wraps the whole page in
> that surface, the floor also hits app chrome: `.avatar-control` is designed at 2.45rem
> (39 px) and gets forced to 64×64, so four controls plus gaps exceed the dock's width, wrap
> to two rows, and grow the fixed dock to roughly 250 px — while `AppShell` reserves only
> `pb-36` (144 px). The same rule turns six nav pills into three rows.
>
> Fix it in four parts.
>
> **First**, introduce a `chrome` surface. Add `data-surface="chrome"` to the `<header>` in
> `components/shared/AppShell.tsx` and to the `<aside class="avatar-dock">` in
> `components/avatar/AvatarDock.tsx`, and add a matching CSS rule giving chrome controls
> `var(--touch-parent)` (44 px) minimums. Add `chrome` to the `:not()` exclusions on the
> existing `child`, `toddler` and `parent` rules so surfaces do not double-match. **Do not
> weaken the 64 px floor for answer controls, the microphone, or any control a child taps to
> learn** — that rule is correct and must keep applying there.
>
> **Second**, make the dock a floating action button below `md`. Collapsed, it is a single
> 64 px circular avatar button pinned bottom-right inside the safe area, with **no message
> bubble and no control row**. Tapping it opens a bottom sheet with a backdrop that contains
> the message, the controls and the chat, with the page behind it inert. When the guide speaks
> while collapsed, animate the button and show a brief toast above it rather than mounting a
> permanent bubble. At `md` and above, keep the current dock exactly as it is.
>
> **Third**, stop rendering the six nav pills below `md` on the child surface — this is
> already the design in `docs/ops/OP-03-entry-flow.md` §5. Keep the logo, the star count and
> the parent button. Navigation happens through the guide and the adventure screen.
>
> **Fourth**, replace the hard-coded `pb-36` in `AppShell` with a value derived from the dock's
> measured height via a `ResizeObserver` writing to a `--dock-height` custom property, used as
> `padding-bottom: calc(var(--dock-height) + var(--safe-bottom) + 1rem)`.
>
> Verify with Playwright at 320×568, 360×640, 390×844, 412×915, 844×390, 768×1024 and
> 1024×768: the collapsed dock occupies at most 15% of viewport height; the hero, the primary
> call to action and the parent button are all clickable and unobstructed; `.avatar-controls`
> never wraps to a second row; answer controls and the microphone are still at least 64 px in
> every activity type; chrome controls are at least 44 px; there is zero horizontal scroll; and
> nothing overlaps a safe-area inset. Commit before-and-after screenshots to `docs/responsive/`.
