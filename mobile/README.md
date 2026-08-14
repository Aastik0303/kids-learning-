# Learn Kids — Mobile

React Native (Expo SDK 57) client for the AI Nursery Learning Platform.
Talks to the existing FastAPI backend in `../backend`. No backend contracts
were changed.

See [`MIGRATION_MAP.md`](./MIGRATION_MAP.md) for what was reused, adapted,
replaced and newly built, plus every deviation from the specification.

## Prerequisites

- Node 20+ (verified on 20.19.6)
- The backend running on port 8008
- For a native build: **JDK 17 + Android Studio** (Android) or Xcode
  (iOS). Neither is installed on this machine yet — see *Building* below.

## Run

Start the backend first:

```bash
cd ../backend
python -m uvicorn app.main:app --port 8008
```

Then the app:

```bash
npm install
npx expo start
```

### Reaching the backend from a device

`src/config/env.ts` resolves the API URL automatically:

- Android emulator → `http://10.0.2.2:8008`
- iOS simulator → `http://localhost:8008`
- Physical device → the dev machine's LAN IP, taken from the Expo packager host

Override with `EXPO_PUBLIC_API_BASE_URL` if needed.

> The backend's CORS list must include the origin you connect from.

## Building

This project needs a **development build**, not Expo Go — speech
recognition, secure store and audio are native modules.

```bash
npx expo run:android    # requires JDK 17 + Android SDK
npx expo run:ios        # requires macOS + Xcode
```

No JDK is installed here, so the cloud path avoids the local toolchain
entirely:

```bash
npx eas build --profile development --platform android
```

## Verify

```bash
npx tsc --noEmit                      # strict typecheck
npx expo export --platform android    # full bundle
npx expo-doctor                       # config + peer deps
```

All three currently pass. The app has **not** been run on a device — voice
timing and permissions are unproven until it is.

## Architecture

```
src/
├── app/            providers, bootstrap, root App
├── navigation/     Root / Guest / Auth / Child / Parent navigators
├── screens/        guest · auth · child · parent
├── activities/     ActivityRenderer + one component per activity kind
├── ai/             GuideProvider · EventDispatcher · ActionExecutor
│                   TargetRegistry · guideSchema  ← the safety boundary
├── features/       learning · voice · guide · drawing · tracing · stories
├── components/     common · avatar · cards · responsive
├── services/       api · audio · storage · analytics
├── store/          auth · child · session · guide · audio · ui
├── theme/          colors · typography · spacing · radius · shadows · animations
├── types/          domain (backend mirror) · guide · activity
├── config/         env · featureFlags
└── i18n/           string catalogue
```

### Three rules that shape everything

**1. The LLM never decides correctness.** Scoring, stars, unlocking and
certificate eligibility are backend decisions. Trace accuracy is
deterministic geometry in `strokeScoring.ts`. The AI explains,
encourages and points — it does not grade.

**2. Model output cannot touch the UI directly.** Everything passes
through `ai/guideSchema.ts`, which validates against closed unions and a
live registry of mounted targets. Unknown actions, unregistered targets and
non-allowlisted routes are dropped. Failure degrades to a static line.

**3. The microphone is never open while the avatar speaks.** Enforced in
two places: `audioStore.setListening` refuses to open during speech, and
`VoiceController` holds a settle window after TTS reports done, because
speaker output trails the callback on most devices.

## Adding an activity type

1. Add the kind to `ACTIVITY_KINDS` and `ANSWER_MODE_BY_KIND` in
   `src/types/activity.ts`.
2. Map the backend `type` string in `STANDARD_KIND_MAP`.
3. Build a component taking `ActivityComponentProps`.
4. Add one case to `renderBody()` in `ActivityRenderer.tsx`.

No new screen, no new route.

## Prototype boundaries

Inherited from the parent project and deliberately unchanged: in-memory
backend state, demo auth tokens, no real database, no payments, no
leaderboards. Do not enter real personal data.
