# OP-06 — Full Mobile Responsiveness

**Goal:** the web app works properly on a phone, a phone held sideways, a tablet, and a
desktop — with touch targets a 3-year-old can actually hit.
**Blocked by:** nothing. Runs independently of the backend.
**Touches:** `frontend/`

---

## 1. The problem, measured

| Finding | Detail |
|---|---|
| **Desktop-first** | `app/globals.css` has 5 `@media` rules — two real breakpoints, both `max-width` (640px, 900px). Base styles assume a large screen and shrink down. |
| **Two conflicting breakpoint systems** | The CSS uses 640/900. Tailwind uses its defaults (640/768/1024/1280) because `tailwind.config.ts` defines **no** `screens`. They disagree at every width between 768 and 900. |
| **2,172 lines of hand-written CSS** | One file, fixed `px` throughout — `18px` ×11, `22px` ×4, `60px` ×3, `46px` and `44px` ×2 each. No fluid scale. |
| **No safe-area handling** | Zero `env(safe-area-inset-*)`. On a notched phone the fixed avatar dock sits under the notch or home indicator. |
| **No landscape or tablet case** | Nothing distinguishes a rotated phone from a tablet — and a tablet held sideways is the single most common posture for this app. |
| **No `viewport` export** | `app/layout.tsx` sets `metadata` but no `viewport`, so no `viewportFit: "cover"` and no `themeColor`. |
| **Touch targets unenforced** | `44px` appears twice in 2,172 lines. The child surface needs **≥64px**, and toddler mode **≥96px**. |
| **Decorative backdrop always mounted** | `day-sky-backdrop` renders a sun, three clouds and two bird layers on every route including mobile, costing paint budget and risking horizontal overflow. |

---

## 2. Target system

**Mobile-first. `min-width` only. One breakpoint source of truth.**

```ts
// tailwind.config.ts — the ONLY place breakpoints are defined
screens: {
  xs: "380px",   sm: "480px",   md: "768px",   lg: "1024px",   xl: "1280px",
  landscape: { raw: "(orientation: landscape)" },
  short:     { raw: "(max-height: 480px)" },
  motion:    { raw: "(prefers-reduced-motion: no-preference)" },
}
```

**Bucket on the short edge, not width.** A 915×412 phone in landscape is a *phone*.
Bucketing on width alone classifies it as a tablet and hands a 4-year-old a desktop layout.
This is how the mobile app already does it — port `useResponsive` from
`mobile/src/components/responsive/`.

**Fluid type and space.** Replace fixed px with `clamp()` tokens in `theme.extend.fontSize`
and `spacing`. One scale. No per-component magic numbers.

**Viewport and safe areas.**

```tsx
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,          // never lock zoom — WCAG 1.4.4
  viewportFit: "cover",
  themeColor: "#f5b84b",
}
```

`maximumScale: 5` matters: locking zoom fails WCAG 1.4.4, and parents with low vision use
this app too. Apply `env(safe-area-inset-*)` padding to everything fixed — the avatar dock,
the offline banner, any bottom control.

**Touch targets.**

| Surface | Minimum | Gap |
|---|---|---|
| Toddler (under 3) | 96 × 96 px | ≥16 px |
| Child (3+) | 64 × 64 px | ≥12 px |
| Parent | 44 × 44 px | ≥8 px |

**Landscape activity rule.** In `landscape short`, activities go two-column — question left,
answer options right — so answers stay above the fold. A child scrolling mid-question loses
their place, and then loses the thread.

**Decorative layer.** Render `day-sky-backdrop` only at `md:` and above, and only under
`prefers-reduced-motion: no-preference`. It is decoration; it should never cost a phone a
frame.

---

## 3. Device test matrix

| Device | Viewport | Must hold |
|---|---|---|
| iPhone SE | 320×568 | No horizontal scroll; all targets ≥64px |
| iPhone 14 | 390×844 | Safe areas respected; dock clear of the home indicator |
| Pixel 7 | 412×915 | — |
| Phone landscape | 844×390 | Two-column activity; answers above the fold |
| iPad portrait | 768×1024 | Content capped, not stretched |
| iPad landscape | 1024×768 | The primary tablet posture — must be excellent |
| Desktop | 1440×900 | Content capped, not a stretched phone layout |

**Hard rule: zero horizontal scroll at any width from 320px up.**

---

## 4. Acceptance criteria

- [ ] Breakpoints exist in exactly one place — `tailwind.config.ts`. Zero raw media queries duplicate a Tailwind breakpoint.
- [ ] `globals.css` is mobile-first: no `max-width` query remains except genuine print and reduced-motion rules.
- [ ] Fixed pixel font sizes and spacing are replaced by `clamp()` tokens; no component carries its own magic numbers.
- [ ] `useResponsive` buckets on the **short edge**; a 844×390 viewport reports as a phone, not a tablet — tested.
- [ ] `viewport` is exported from `app/layout.tsx` with `viewportFit: "cover"` and `maximumScale: 5`. Zoom is **not** locked.
- [ ] Every fixed element respects `env(safe-area-inset-*)`; nothing overlaps a notch or home indicator.
- [ ] Touch targets meet the §2 table per surface — automated check across every route.
- [ ] In `landscape short`, answer options are visible without scrolling — tested.
- [ ] `day-sky-backdrop` does not render below `md:` or under `prefers-reduced-motion: reduce`.
- [ ] **Zero horizontal scroll at 320, 390, 412, 768, 844, 1024 and 1440 px** — Playwright-asserted.
- [ ] All 7 matrix rows pass; screenshots committed to `docs/responsive/`.
- [ ] Zero critical or serious axe violations on every route at mobile width.
- [ ] LCP ≤2.0 s and CLS ≤0.05 on a throttled 4G mid-tier Android profile.

---

## 5. Prompt

> Read `docs/ops/OP-06-responsive.md` and `docs/frontend-architecture.md` §1.4. Convert the
> `frontend/` web app to a genuinely mobile-first responsive layout.
>
> Define breakpoints in exactly one place — `tailwind.config.ts` `screens` — as
> `xs:380 sm:480 md:768 lg:1024 xl:1280` plus raw `landscape`, `short (max-height:480px)` and
> `motion` variants. Rewrite `app/globals.css` — currently 2,172 lines, desktop-first, with
> only `max-width: 640px` and `max-width: 900px` queries — to be mobile-first using
> `min-width` only, and delete every raw media query that duplicates a Tailwind breakpoint.
> Replace fixed pixel sizes with `clamp()`-based fluid type and spacing tokens in
> `theme.extend`.
>
> Add a `useResponsive` hook that buckets on the **short edge**, not width, so a phone in
> landscape is treated as a phone — port the approach from
> `mobile/src/components/responsive/useResponsive.ts` — along with `AdaptiveStack`,
> `ResponsiveGrid` and `Show` helpers.
>
> Add a `viewport` export to `app/layout.tsx` with `width: device-width`, `initialScale: 1`,
> `maximumScale: 5` (never lock zoom — WCAG 1.4.4), `viewportFit: "cover"` and a `themeColor`.
> Apply `env(safe-area-inset-*)` padding to every fixed element including the avatar dock.
> Enforce touch-target minimums per surface: 96×96px in toddler mode, 64×64px on the child
> surface, 44×44px on the parent surface, with the gaps specified in §2.
>
> In `landscape short`, lay activities out in two columns — question left, answers right — so
> answers never require scrolling. Render the `day-sky-backdrop` decorative layer only at
> `md:` and above and only under `prefers-reduced-motion: no-preference`.
>
> Verify with Playwright at 320×568, 390×844, 412×915, 844×390, 768×1024, 1024×768 and
> 1440×900: assert **zero horizontal scroll at every size**, touch targets meeting the
> per-surface minimums, no element overlapping a safe-area inset, and answer options visible
> without scrolling in phone landscape. Run axe at mobile width on every route and reach zero
> critical or serious violations. Commit screenshots to `docs/responsive/`.
