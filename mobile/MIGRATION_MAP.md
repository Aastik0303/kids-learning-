# Migration Map — Next.js web → React Native mobile

Produced before implementation, per spec section 25. Records what was
**reused**, **adapted**, **replaced**, and **newly created**, plus the
decisions that deviate from the original specification and why.

---

## 1. Reused unchanged

These carried over with no modification. The backend was not touched at all.

| Thing | Source | Notes |
|---|---|---|
| All API contracts | `backend/app/schemas/*.py` | Mirrored 1:1 into `src/types/domain.ts`. No endpoint added, removed or changed. |
| Brand colours | `frontend/tailwind.config.ts`, `app/globals.css` | berry `#d94f70`, leaf `#2f8f6b`, sunshine `#f5b84b`, sky `#4a90c2`, ink `#25313f`, lavender `#8b7bd8` — exact hex values in `src/theme/colors.ts`. |
| World / class identity | `frontend/data/prototype.ts` (`learningWorlds`, `pathAccents`) | Number Kingdom, Alphabet Forest, Colour Garden, Shape Island, plus mascots and rewards → `classVisuals`. |
| Guide agent protocol | `backend/app/schemas/guide.py` | Events, action types, visual action types, strategies — all closed unions preserved verbatim. |
| Deterministic-correctness rule | `CLAUDE.md`, `README.md` | Scoring, stars, unlocking and certificate eligibility remain server-side. Nothing in the app decides them. |
| Answer normalisation | `POST /speech/normalize` | The "tree → three → 3" path is still backend logic, called from `VoiceController`. |

---

## 2. Adapted

Same concept, different mechanics, because the platform demanded it.

| Concept | Web | Mobile | Why |
|---|---|---|---|
| Theme | ~2,100 lines of hand-written CSS | Token modules under `src/theme/` | RN has no cascade, no pseudo-elements, no `clamp()`. Tokens give the same visual result with one source of truth. |
| Responsive | CSS media queries at 640/900px | `useResponsive` + breakpoint buckets | Adds landscape and tablet cases the web build never had. Buckets on the **short edge** so a rotated phone isn't treated as a tablet. |
| Avatar | CSS-drawn bear (`.avatar-face`, `.avatar-ear`, …) | `AvatarFace.tsx`, drawn with RN views | Kept as primitives, not an image, so it scales 56pt→160pt with no assets and each state can animate one feature. |
| Highlight system | `.visual-guide-*` CSS classes with `:nth` delays | `GuideHighlight` + `guideStore.activeHighlights` | Stagger index travels through the store instead of CSS class names. |
| Session storage | `sessionStorage` | `expo-secure-store` (token) + AsyncStorage (rest) | Token treated as a credential now so the production auth swap doesn't also have to move storage. |
| Speech-to-text | Browser `SpeechRecognition` | `@jamsch/expo-speech-recognition` | No web speech API on native. Wrapped in typed outcomes so every failure mode has a tap fallback. |
| Text-to-speech | `speechSynthesis` + ElevenLabs | `expo-speech` + ElevenLabs via `expo-audio` | Device voice is the default; hosted voice is behind a flag because `/speech/synthesize` 503s without an API key. |
| Navigation | Next.js App Router file routes | React Navigation, typed param lists | Per spec section 21. Safe-route allowlist replaces the web's route string check. |
| Auth intent | `sessionStorage` redirect param | `authStore.pendingIntent`, persisted | Survives app kill, not just page reload. |

---

## 3. Replaced

Rebuilt from scratch because the web equivalent didn't generalise.

| Web | Mobile | Reason |
|---|---|---|
| `LearningQuestion.tsx`, `PracticeQuestion.tsx`, `ToddlerLesson.tsx`, `VoiceLearningSession.tsx`, `VoicePracticeSession.tsx` | One `ActivityRenderer` + 8 activity components | Spec section 7 requires one engine, not a screen per question type. Lessons and practice now share the renderer entirely. |
| `app/levels/[pathId]/[stageId]/page.tsx` etc. | One `LessonScreen` | Every activity type renders through the same screen. |
| Scattered `fetch` in 12 service files | `services/api/` with one client | Spec section 18. Adds timeout, exponential-backoff retry, typed `ApiError` with child-safe copy. |
| `AvatarProvider` + `companion.ts` + `guide.ts` + `toddlerGuide.ts` | `ai/` — Provider, EventDispatcher, ActionExecutor, TargetRegistry, guideSchema | Spec sections 9–11. Validation and execution are now separate modules so execution cannot be reached without validation. |
| Browser-only tracing | `DrawingCanvas` + `tracePaths` + `strokeScoring` | Web build had no tracing. Scoring is deterministic geometry, never an LLM call (spec section 14). |

---

## 4. Newly created

Nothing in the web build corresponds to these.

- **Guest home** (`GuestHomeScreen`) — the common pre-auth showcase, all 12 features, how-it-works, age preview, parent benefits.
- **Feature demo** (`FeatureDemoScreen`) — scripted, no-backend preview of how the AI teaches. Works with the server down.
- **Hand Raise / Doubt Mode** — `useHandRaise` + `DoubtOverlay`. Pauses without unmounting, so resume is literal.
- **Adaptive experience modes** — toddler vs early learner from one codebase (`resolveExperienceMode`).
- **Parent gate** — written-word arithmetic; readable by an adult, not by a pre-reader.
- **Production reliability** — error boundary, offline banner, session resume, retry, haptics, analytics + crash integration points, feature flags, i18n scaffolding.
- **Trace geometry** — letter/number/shape paths in a 100×100 unit box with even sampling for scoring.
- **Local story content** — `storyContent.ts`, pending a backend `/stories` endpoint.

---

## 5. Deviations from the specification

Flagged explicitly rather than silently absorbed.

### 5.1 Activity type vocabulary needed an adapter

The spec names 12 renderer kinds (`voice_repeat`, `tap_choice`, `image_match`, …).
The backend curriculum emits **18 entirely different strings**:

```
match(29) multiple_choice(16) identify_colour(10) count_objects(10)
mixed(9) identify_shape(9) select_letter(7) select_number(5)
repeat_{shape,number,letter,colour}(4) recognize_{shape,colour}(2)
introduce_{shape,number,letter,colour}(4)
```

Renaming them backend-side would break `answer_resolution_service.py`,
`learning_service.py` and the curriculum JSON. Instead
`resolveActivityKind()` in `src/types/activity.ts` maps backend → renderer
at the boundary. **Backend contracts unchanged**, per spec section 22's
"prefer additive adapters over breaking changes".

Two extra kinds were added beyond the spec's twelve — `introduce` and
`complete` — because the backend genuinely emits them and folding them
into a question type would have meant the guide could not teach before
asking.

### 5.2 Six features have no backend path

`words`, `sentences`, `speaking`, `drawing`, `tracing`, `stories` appear in
the spec's class list but have **no corresponding backend path**. Backend
offers only `numbers`, `alphabets`, `colours`, `shapes`, `mixed_final`.

Handling: they render in the catalog and demo, and `ClassDetailScreen`
shows an honest "practice activity today, full levels coming" state rather
than failing. Adding them later needs new backend paths — not a frontend
change.

### 5.3 `image_match` / `shape_match` / `color_match` share one component

The spec lists them separately. They are the same interaction — tap one of
N options — differing only in presentation, so `TapChoice` takes a
`presentation` prop (`text` / `glyph` / `swatch`). Three near-identical
components would have been duplication, not architecture.

### 5.4 Correct answers deliberately skip the LLM

Spec section 9 lists `ANSWER_CORRECT` as a dispatched event. `CLAUDE.md`
requires that ordinary correct answers use short static praise and
deterministic progression. `shouldCallAgent()` resolves this: the agent is
only consulted on a correct answer if the child needed 2+ attempts — a real
teaching moment. Otherwise praise is instant and local, which also removes
latency from the most time-sensitive moment in the app.

### 5.5 `src/app/` collides with Expo Router

Spec section 21 specifies `src/app/providers/` and `src/app/bootstrap/`.
Expo SDK 57 treats `src/app/` as the Expo Router routes directory and logs
`Using src/app as the root directory for Expo Router` during bundling.

Currently **harmless** — `expo-router` is not a dependency, and the bundle
correctly enters through `index.ts`. Kept the spec's structure. If
`expo-router` is ever added, rename `src/app/` first.

### 5.6 Reanimated installed but Animated used

`react-native-reanimated` is installed and configured. Actual animations
use RN's `Animated` API, and the drawing canvas uses `PanResponder` rather
than Gesture Handler worklets. For a canvas that must never drop a stroke,
the plain JS path has fewer failure modes on the New Architecture. Motion
tokens live in `theme/animations.ts` and every animation checks
`reduceMotion`.

---

## 6. Safety boundary (spec section 10)

The one invariant worth restating:

```
AI response → schema validation → action allowlist → target allowlist
            → GuideActionExecutor → UI
```

- `ai/guideSchema.ts` is the **only** place model output becomes UI intent.
  Every field is checked against a closed union; unknown values are
  discarded, not passed through.
- A target the model names must be **currently registered and mounted**
  (`GuideTargetRegistry`), or it is dropped.
- An action the screen did not offer is rejected even if it is otherwise
  valid.
- `open_safe_route` is checked against `SAFE_ROUTES` **twice** — once in
  validation, again in the executor — so no future caller can reach
  navigation without passing the allowlist.
- Auth, parent and destructive routes are absent from `SAFE_ROUTES` by
  design and are unreachable by any model output.
- Message text is stripped of markup, code and URLs before it can be
  spoken or displayed.
- Failure always degrades to a safe static line. It never throws.

---

## 7. Verification performed

| Check | Result |
|---|---|
| `npx tsc --noEmit` (strict, `noUncheckedIndexedAccess`) | Clean, exit 0 |
| `npx expo export --platform android` | Bundled, 1600 modules, 3.8 MB |
| `npx expo-doctor` | 20/20 checks passed |

**Not** verified: the app has not been run on a device or emulator. No
JDK/Android SDK is installed on this machine, so runtime behaviour —
especially STT permissions, TTS timing and the mic-gating handoff — is
unproven and needs a device pass.
