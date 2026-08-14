import { getLocales } from "expo-localization";

/**
 * Localisation-ready string architecture (spec section 20).
 *
 * Not a full i18n runtime — deliberately. The value now is that every
 * user-facing string has a key and a single lookup path, so swapping in
 * a real library later is a mechanical change rather than a hunt through
 * a hundred components.
 *
 * Child-facing copy rules, which any translation must preserve:
 *   - short sentences a 3-year-old can follow
 *   - warm and encouraging, never blaming
 *   - no technical vocabulary, ever
 */

export type StringKey = keyof typeof en;

const en = {
  // Guide
  "guide.greeting": "Hello! Shall we learn together?",
  "guide.thinking": "Let me think…",
  "guide.listening": "I am listening…",
  "guide.repeat": "Say it again",
  "guide.handRaise": "Raise your hand to ask me something",

  // Feedback
  "feedback.correct": "Yes! That is right!",
  "feedback.tryAgain": "Good try! Let us look again.",
  "feedback.almost": "Almost! Try one more time.",

  // Voice
  "voice.tapToSpeak": "Tap and speak",
  "voice.speakNow": "Speak now!",
  "voice.listenFirst": "Listen first…",
  "voice.notHeard": "I did not hear anything. Try again!",
  "voice.tooQuiet": "That was very quiet. Say it a bit louder!",
  "voice.noPermission": "Ask a grown-up to turn on the microphone.",
  "voice.unavailable": "Let us tap the answer instead.",

  // Errors
  "error.offline": "I cannot hear the internet right now. Let us try again!",
  "error.timeout": "That took a long time. Let us try again!",
  "error.generic": "Something went wrong. Let us try again!",
  "error.notFound": "I could not find that. Let us go back home.",
  "error.crash": "Oops! Let us start again.",

  // Actions
  "action.startLearning": "Start learning",
  "action.keepGoing": "Keep going",
  "action.tryAgain": "Try again",
  "action.next": "Next",
  "action.done": "Done!",
  "action.clear": "Clear",
  "action.undo": "Undo",
  "action.exit": "Exit",
  "action.back": "Back",

  // Rewards
  "reward.starEarned": "You earned a star!",
  "reward.levelComplete": "You did it!",
  "reward.certificate": "Little Learning Explorer",
} as const;

/**
 * Translations. Only `en` is complete; the others exist to prove the
 * lookup path works and to give translators a target shape.
 */
const translations: Record<string, Partial<Record<StringKey, string>>> = {
  en,
  hi: {
    "guide.greeting": "नमस्ते! क्या हम साथ में सीखें?",
    "feedback.correct": "हाँ! यह सही है!",
    "voice.tapToSpeak": "दबाकर बोलें",
    "action.startLearning": "सीखना शुरू करें",
  },
  es: {
    "guide.greeting": "¡Hola! ¿Aprendemos juntos?",
    "feedback.correct": "¡Sí! ¡Es correcto!",
    "voice.tapToSpeak": "Toca y habla",
    "action.startLearning": "Empezar a aprender",
  },
};

function deviceLanguage(): string {
  const locales = getLocales();
  return locales[0]?.languageCode ?? "en";
}

let activeLanguage = deviceLanguage();

/** Map a child's stored language name onto a language code. */
export function setLanguageFromName(name: string | undefined): void {
  if (!name) return;
  const map: Record<string, string> = {
    english: "en",
    hindi: "hi",
    spanish: "es",
    french: "fr",
  };
  activeLanguage = map[name.toLowerCase()] ?? "en";
}

/** Look up a string, falling back to English then to the key itself. */
export function t(key: StringKey): string {
  return translations[activeLanguage]?.[key] ?? en[key] ?? key;
}

export function currentLanguage(): string {
  return activeLanguage;
}
