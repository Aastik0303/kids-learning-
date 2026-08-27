/**
 * Language tags for the two engines that need them: the recogniser and the
 * speaker. Both take BCP-47 ("en-US", "hi-IN") and both fail quietly on
 * anything else — the recogniser by refusing to start, the speaker by reading
 * the text in whatever voice it had. Quiet failure is why this lived as a
 * private helper inside `tts.ts` and the microphone never got one.
 *
 * There is a second job here that is specific to this app. Every line the guide
 * says is English with the taught Hindi letter or word quoted inside it — "This
 * is अ. अ is for अनार." An English voice reading that sentence simply skips the
 * Devanagari, so the child hears "This is. is for." and the one thing the level
 * exists to teach is the one thing they never hear. `segmentByScript` splits
 * such a line into runs so each run can be spoken by a voice that can read it.
 */

/** Devanagari, including the combining vowel signs (matras). */
const DEVANAGARI = /[ऀ-ॿ]/;
const DEVANAGARI_RUN = /[ऀ-ॿ‌‍]+/;

export const DEFAULT_TAG = "en-US";
export const HINDI_TAG = "hi-IN";

/**
 * Child profiles store a display name ("English"), not a tag; the backend
 * sends a bare subtag ("hi") on a topic. Both have to end up as BCP-47.
 */
const BY_NAME: Record<string, string> = {
  english: DEFAULT_TAG,
  en: DEFAULT_TAG,
  hindi: HINDI_TAG,
  hi: HINDI_TAG,
  spanish: "es-ES",
  es: "es-ES",
  french: "fr-FR",
  fr: "fr-FR",
  arabic: "ar-SA",
  ar: "ar-SA",
};

export function languageTag(preferred?: string | null): string {
  const value = (preferred ?? "").trim();
  if (!value) return DEFAULT_TAG;

  const known = BY_NAME[value.toLowerCase()];
  if (known) return known;

  // Already a tag ("en-GB", "hi-IN"). Pass it through untouched.
  if (/^[a-z]{2,3}-[A-Za-z0-9]{2,8}$/i.test(value)) return value;

  // Something we do not recognise. Guessing a tag makes the engine fail; the
  // default at least speaks and listens.
  return DEFAULT_TAG;
}

export function hasDevanagari(text?: string | null): boolean {
  return DEVANAGARI.test(text ?? "");
}

/**
 * The tag to use for one piece of content, decided by what is written in it.
 *
 * This is deliberately driven by the text rather than by the child's profile.
 * A Hindi level teaches अ to a child whose app language is English, and the
 * recogniser has to be listening for Hindi at the moment they say it — the
 * profile would have it listening for English and hearing nothing, which is
 * exactly the bug this replaces.
 */
export function tagForContent(text?: string | null, fallback: string = DEFAULT_TAG): string {
  return hasDevanagari(text) ? HINDI_TAG : fallback;
}

export type ScriptSegment = { text: string; tag: string };

/**
 * Split a mixed line into runs of one script each, in order.
 *
 * "This is अ. अ is for अनार." becomes four runs, alternating English and
 * Hindi. Punctuation and spaces ride along with the run they follow, so
 * nothing is lost and the sentence still sounds like a sentence.
 */
export function segmentByScript(text: string, fallback: string = DEFAULT_TAG): ScriptSegment[] {
  const clean = (text ?? "").trim();
  if (!clean) return [];
  if (!hasDevanagari(clean)) return [{ text: clean, tag: fallback }];

  const segments: ScriptSegment[] = [];
  let buffer = "";
  let bufferIsHindi = DEVANAGARI.test(clean[0] ?? "");

  const flush = () => {
    const piece = buffer.trim();
    if (piece) segments.push({ text: piece, tag: bufferIsHindi ? HINDI_TAG : fallback });
    buffer = "";
  };

  for (const character of clean) {
    // Spaces and punctuation belong to whichever run is open, so a run is only
    // ever broken by a character that is definitely the other script.
    const isHindi = DEVANAGARI_RUN.test(character);
    const isNeutral = !isHindi && !/[A-Za-z0-9]/.test(character);

    if (isNeutral) {
      buffer += character;
      continue;
    }
    if (isHindi !== bufferIsHindi && buffer.trim()) {
      flush();
      bufferIsHindi = isHindi;
    } else {
      bufferIsHindi = isHindi;
    }
    buffer += character;
  }
  flush();

  return segments;
}
