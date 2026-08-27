"use client";

import { API_BASE, api } from "@/services/api";
import { primeMicrophone, watchVoiceActivity } from "@/services/micStream";

type SpeechRecognitionConstructor = new () => SpeechRecognition;

type SpeechRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionEvent = {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: {
      isFinal: boolean;
      length: number;
      [index: number]: {
        transcript: string;
        confidence: number;
      };
    };
  };
};

type SpeechRecognitionErrorEvent = {
  error: string;
};

type BrowserSpeechResult = {
  transcript: string;
  confidence: number;
  /**
   * The recogniser's runners-up, best first. `maxAlternatives: 3` was already
   * being asked for and only the first was ever read - a child saying "अ" is
   * very often the second alternative, with the recogniser's own favourite
   * being some word it preferred. Throwing these away was throwing away
   * answers.
   */
  alternatives: string[];
  error?: string;
};

type WindowWithSpeechRecognition = Window &
  typeof globalThis & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };

/** Stage 1 of the child speech pipeline — `child_speech_service.py`.
 *
 * Says what the child most likely said, never whether it was right.
 * `retry_suggested` means ask them to say it again; it is not a wrong answer. */
export type ChildSpeechResult = {
  token: string;
  confidence: number;
  status: "resolved" | "needs_enhancement" | "retry" | "empty";
  reason_code: string;
  self_corrected: boolean;
  needs_enhancement: boolean;
  retry_suggested: boolean;
};

export type SpeechTranscription = {
  raw_transcript: string;
  normalized: string;
  resolved_answer: string;
  resolution_confidence: number;
  ambiguous: boolean;
  matched_candidate: string | null;
  input_kind: "answer" | "unresolved" | "empty";
  child_speech?: ChildSpeechResult | null;
};

/**
 * Who is actually speaking.
 *
 * - `edge` — Microsoft Edge's free neural voices, synthesised by our own server
 *   (`POST /speech/synthesize`). **The default.** No key, no cost, and one voice
 *   reads English and Devanagari in the same sentence — which is how this app
 *   narrates Hindi, so a line like "This is कमल" is spoken properly in one
 *   breath instead of being cut into runs and handed to two different voices.
 * - `elevenlabs` — better still, and paid. Used when the server has a key.
 * - `browser` — the machine's own `speechSynthesis`. Kept as the fallback for
 *   when the network or the server is down, never as the first choice: it is a
 *   different robot on every device and on Windows it reads Devanagari as
 *   silence.
 */
export type VoiceProvider = "browser" | "edge" | "elevenlabs";

const VOICE_PROVIDER_STORAGE_KEY = "child-ai-voice-provider";

/** The stored choice, or the free neural voice. */
export function getVoiceProvider(): VoiceProvider {
  if (typeof window === "undefined") return DEFAULT_VOICE_PROVIDER;
  const stored = window.localStorage.getItem(VOICE_PROVIDER_STORAGE_KEY);
  if (stored === "elevenlabs" || stored === "edge" || stored === "browser") return stored;
  return DEFAULT_VOICE_PROVIDER;
}

/**
 * The voice a child gets before anybody chooses one.
 *
 * It is the server's, not the browser's. A real voice with no key and no cost is
 * strictly better than the robot, and this is a nursery app — the guide's voice
 * is most of what a pre-reader actually receives from it.
 */
export const DEFAULT_VOICE_PROVIDER: VoiceProvider = "edge";

export function setVoiceProvider(provider: VoiceProvider) {
  if (typeof window === "undefined") return;
  stopSpeech();
  window.localStorage.setItem(VOICE_PROVIDER_STORAGE_KEY, provider);
}

const GUIDE_QUESTION_START = /^(what|why|how|where|when|who|help|explain|repeat|tell me|show me|can you|could you|please)\b/i;
const GUIDE_HELP_PHRASE = /\b(i (?:do not|don't|dont) understand|not understand|need help|help me|confused|say that again|what does|what is|how do)\b/i;

export function hasGuideSpeechIntent(transcript: string) {
  const cleaned = transcript.trim();
  return GUIDE_QUESTION_START.test(cleaned) || GUIDE_HELP_PHRASE.test(cleaned);
}

export function canSpeak() {
  return typeof window !== "undefined" && ("Audio" in window || ("speechSynthesis" in window && "SpeechSynthesisUtterance" in window));
}

let activeAudio: HTMLAudioElement | null = null;
let activeAudioUrl: string | null = null;
let activeRequest: AbortController | null = null;
let finishActiveSpeech: (() => void) | null = null;

/**
 * Bumped by every `stopSpeech` and every new utterance. A mixed line is spoken
 * as several sequential utterances, and cancelling only ends the one actually
 * playing - without this the loop would calmly start the next segment, so a
 * child who moved on would still hear the rest of the previous sentence.
 */
let speechGeneration = 0;


export function stopSpeech() {
  if (typeof window === "undefined") return;
  // Ends the segment loop as well as the utterance that is playing.
  speechGeneration += 1;
  activeRequest?.abort();
  activeRequest = null;
  if (activeAudio) {
    activeAudio.pause();
    activeAudio.removeAttribute("src");
    activeAudio.load();
    activeAudio = null;
  }
  if (activeAudioUrl) {
    URL.revokeObjectURL(activeAudioUrl);
    activeAudioUrl = null;
  }
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  const finish = finishActiveSpeech;
  finishActiveSpeech = null;
  finish?.();
}

/**
 * The language to read a line in, from the line itself.
 *
 * Nursery Hindi is an oral subject — a lesson the child cannot hear is no
 * lesson at all — and a Devanagari sentence handed to an English voice is
 * either silent or gibberish. The text carries its own answer, so nothing has
 * to be threaded through every caller.
 */
function speechLanguage(text: string): string {
  return /[ऀ-ॿ]/.test(text) ? "hi-IN" : "en-US";
}

/**
 * Split a mixed line into runs of one script each, in order.
 *
 * Every line the guide says is English with the taught Hindi letter or word
 * quoted inside it - "This is अ. अ is for अनार." Read as one utterance that
 * line is wrong either way round: an English voice skips the Devanagari
 * entirely, so the child hears "This is. is for." and never hears the one
 * thing the level exists to teach, and a Hindi voice mangles the English.
 *
 * So it is spoken as several utterances, each in a voice that can read it.
 * Spaces and punctuation ride along with the run they follow, so the sentence
 * still sounds like a sentence.
 */
export function segmentByScript(text: string): { text: string; lang: string }[] {
  const clean = (text ?? "").trim();
  if (!clean) return [];
  if (!/[ऀ-ॿ]/.test(clean)) return [{ text: clean, lang: "en-US" }];

  const segments: { text: string; lang: string }[] = [];
  let buffer = "";
  let bufferIsHindi = /[ऀ-ॿ]/.test(clean[0] ?? "");

  const flush = () => {
    const piece = buffer.trim();
    if (piece) segments.push({ text: piece, lang: bufferIsHindi ? "hi-IN" : "en-US" });
    buffer = "";
  };

  for (const character of clean) {
    const isHindi = /[ऀ-ॿ‌‍]/.test(character);
    // Neutral characters - spaces, Latin punctuation, emoji - never break a run.
    if (!isHindi && !/[A-Za-z0-9]/.test(character)) {
      buffer += character;
      continue;
    }
    if (isHindi !== bufferIsHindi && buffer.trim()) flush();
    bufferIsHindi = isHindi;
    buffer += character;
  }
  flush();

  return segments;
}

/**
 * Which language the *recogniser* should be listening in.
 *
 * Decided by what the child is being asked to say, never by their profile. A
 * Hindi level asks अ of a child whose app language is English, and a recogniser
 * set to en-US simply does not hear it - it returns nothing, every time, and
 * the child is left tapping a microphone that never answers. That was the bug.
 *
 * The answer key may be passed in. It is read for its *script* only and never
 * compared against anything, so it cannot steer what is heard.
 */
export function listeningLanguage(...candidates: (string | null | undefined)[]): string {
  return candidates.some((value) => /[ऀ-ॿ]/.test(value ?? "")) ? "hi-IN" : "en-US";
}

async function speakWithBrowser(text: string) {
  // One utterance per script run. A line with no Devanagari in it is a single
  // run, so nothing changes for the English-only lessons.
  const mine = ++speechGeneration;
  for (const segment of segmentByScript(text)) {
    if (mine !== speechGeneration) return;
    await speakSegment(segment.text, segment.lang);
  }
}

function speakSegment(text: string, lang: string) {
  return new Promise<void>((resolve) => {
    if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
      resolve();
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    // A matching installed voice, when there is one. Without this some browsers
    // keep the default English voice even after `lang` is set.
    const voice = window.speechSynthesis
      .getVoices()
      .find((candidate) => candidate.lang?.replace("_", "-").toLowerCase().startsWith(lang.slice(0, 2)));
    if (voice) utterance.voice = voice;
    utterance.rate = 0.9;
    utterance.pitch = 1.12;
    utterance.volume = 1;
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    window.speechSynthesis.speak(utterance);
  });
}

async function playSpeech(text: string) {
  stopSpeech();
  const provider = getVoiceProvider();
  if (provider === "browser") {
    await speakWithBrowser(text);
    return;
  }
  const controller = new AbortController();
  let audio: HTMLAudioElement | null = null;
  let audioUrl: string | null = null;
  let finishThisSpeech: (() => void) | null = null;
  activeRequest = controller;
  try {
    const response = await fetch(`${API_BASE}/speech/synthesize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // The server picks when this is empty — the paid voice if it has a key,
      // the free Edge one otherwise. Naming it here only pins the choice.
      body: JSON.stringify({ text, provider }),
      signal: controller.signal
    });
    if (!response.ok) throw new Error("The server voice is unavailable");
    const blob = await response.blob();
    if (controller.signal.aborted) return;
    audioUrl = URL.createObjectURL(blob);
    activeAudioUrl = audioUrl;
    const playbackAudio = new Audio(audioUrl);
    audio = playbackAudio;
    activeAudio = playbackAudio;
    await new Promise<void>((resolve, reject) => {
      finishThisSpeech = resolve;
      finishActiveSpeech = resolve;
      playbackAudio.onended = () => resolve();
      playbackAudio.onerror = () => reject(new Error("Voice playback failed"));
      playbackAudio.play().catch(reject);
    });
  } catch (error) {
    // The server voice failed — no network, server down, Edge unreachable. Fall
    // back to the machine's own robot rather than leaving the guide mute: a
    // worse voice is a much smaller problem than a silent lesson.
    if (!controller.signal.aborted) await speakWithBrowser(text);
  } finally {
    if (activeRequest === controller) activeRequest = null;
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    if (activeAudioUrl === audioUrl) activeAudioUrl = null;
    if (activeAudio === audio) activeAudio = null;
    if (finishActiveSpeech === finishThisSpeech) finishActiveSpeech = null;
  }
}

export function speakText(text: string, onEnd?: () => void) {
  if (!canSpeak() || !text.trim()) {
    onEnd?.();
    return false;
  }
  void playSpeech(text).finally(() => onEnd?.());
  return true;
}

export function speakTextAsync(text: string) {
  if (!canSpeak() || !text.trim()) return Promise.resolve();
  return playSpeech(text);
}

export function canUseSpeechRecognition() {
  if (typeof window === "undefined") return false;
  const speechWindow = window as WindowWithSpeechRecognition;
  return Boolean(speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition);
}

/**
 * Why `continuous` is on for a one-word answer.
 *
 * With `continuous = false` the browser endpoints the moment it thinks the
 * speaker has stopped, and it decides that from a very short window. A child
 * saying a whole sentence gives it plenty to work with; a child saying "अ" -
 * or "A" - gives it about a third of a second, which it discards as noise and
 * reports as `no-speech`. That is exactly the shape of the bug: sentences were
 * heard and single letters never were.
 *
 * Left open, the engine keeps the audio and gets a result out of it. Nothing
 * runs away, because `listenForTranscript` stops it on its own timer.
 */
function createSpeechRecognition(language = "en-US") {
  if (!canUseSpeechRecognition()) return null;
  const speechWindow = window as WindowWithSpeechRecognition;
  const Recognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
  if (!Recognition) return null;
  const recognition = new Recognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  // More runners-up, because the server is the thing that resolves them: a
  // child saying "A" very often arrives as the recogniser's third guess.
  recognition.maxAlternatives = 5;
  recognition.lang = language;
  return recognition;
}

/**
 * How many times a session that ended with nothing may be reopened.
 *
 * More of them when our own level meter says the child was talking: Chrome
 * hangs up on a voice too quiet for it long before the child's window is up,
 * and giving up at that point tells a child who *did* speak that they said
 * nothing.
 */
const MAX_RESTARTS = 2;
const MAX_RESTARTS_WHEN_HEARD = 4;

/**
 * How long to keep listening after the child has clearly stopped talking.
 *
 * The microphone used to stay open for the whole window - eight seconds - even
 * when a two-year-old had said "A" in the first half second, so every answer
 * felt like it was being ignored. Once something has been heard, this is how
 * long it waits for more before answering, and it is chosen from what was
 * heard rather than being one number for everything:
 *
 * - **A word or two** - which is every answer in this class - settles in
 *   `SILENCE_AFTER_WORD_MS`. There is nothing left to wait for.
 * - **A longer sentence** (a child asking a question of their own) keeps
 *   `SILENCE_AFTER_SPEECH_MS`, because people pause in the middle of those.
 * - **Something the class was already offering** - one of the options on
 *   screen, right or wrong - settles almost at once. This is endpointing, not
 *   marking: the transcript still goes to the server, which is the only thing
 *   that decides what it was.
 */
const SILENCE_AFTER_SPEECH_MS = 1100;
const SILENCE_AFTER_WORD_MS = 600;
const SILENCE_AFTER_EXPECTED_MS = 260;

/** Still talking. Never settle in the middle of a word, however long the pause. */
const VOICE_HOLD_MS = 220;

type ListenOptions = {
  /**
   * What the child has been offered - the options on screen, the thing they
   * were asked to say. Used for endpointing only, never as a verdict: hearing
   * one means they have finished speaking, and the transcript still goes to the
   * server, which is the only thing that decides what it was worth.
   */
  expectedPhrases?: string[];
  /** The live microphone level, for the meter on screen. */
  onLevel?: (level: number) => void;
};

function normalizePhrase(text: string) {
  // Devanagari is spelled out rather than asked for with `\p{L}`, which needs a
  // regex flag this project's TypeScript target does not allow. A Hindi level's
  // options are the reason it has to be kept at all.
  return text.toLowerCase().replace(/[^\w\sऀ-ॿ]/g, " ").replace(/\s+/g, " ").trim();
}

function listenForTranscript(timeoutMs: number, language = "en-US", options: ListenOptions = {}) {
  return new Promise<BrowserSpeechResult>((resolve) => {
    const recognition = createSpeechRecognition(language);
    if (!recognition) {
      window.setTimeout(() => resolve({ transcript: "", confidence: 0, alternatives: [] }), timeoutMs);
      return;
    }

    const expected = new Set(
      (options.expectedPhrases ?? []).map(normalizePhrase).filter((phrase) => phrase.length > 0)
    );

    let settled = false;
    // Set whenever speech arrives; if nothing follows, the turn ends early.
    let quiet: number | undefined;
    let bufferedTranscript = "";
    let bufferedConfidence = 0;
    let bufferedAlternatives: string[] = [];
    let restarts = 0;
    const deadline = Date.now() + timeoutMs;
    // Our own ears, on the warm stream. Independent of the recogniser, and set
    // to a floor well below what it calls speech.
    const voice = watchVoiceActivity(options.onLevel);
    const finish = (result: BrowserSpeechResult) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(quiet);
      voice.stop();
      resolve(result);
    };
    const timer = window.setTimeout(() => {
      // The child's window is up. `onend` must not restart after this.
      restarts = MAX_RESTARTS_WHEN_HEARD;
      recognition.stop();
      window.setTimeout(() => {
        if (!settled) {
          finish({
            transcript: bufferedTranscript,
            confidence: bufferedConfidence || (bufferedTranscript ? 0.75 : 0),
            alternatives: bufferedAlternatives
          });
        }
      }, 300);
    }, timeoutMs);

    /** How long to wait after this transcript before calling it the answer. */
    const quietFor = (transcript: string) => {
      if (expected.has(normalizePhrase(transcript))) return SILENCE_AFTER_EXPECTED_MS;
      return transcript.trim().split(/\s+/).length <= 2 ? SILENCE_AFTER_WORD_MS : SILENCE_AFTER_SPEECH_MS;
    };

    const endAfterQuiet = () => {
      window.clearTimeout(quiet);
      quiet = window.setTimeout(() => {
        if (settled || !bufferedTranscript.trim()) return;
        // Our meter can still hear them. They are mid-sentence, or the
        // recogniser is simply behind - either way, do not answer over them.
        if (voice.speaking() && Date.now() < deadline) {
          endAfterQuiet();
          return;
        }
        restarts = MAX_RESTARTS_WHEN_HEARD;
        recognition.stop();
        finish({
          transcript: bufferedTranscript,
          confidence: bufferedConfidence || 0.75,
          alternatives: bufferedAlternatives
        });
      }, Math.max(quietFor(bufferedTranscript), VOICE_HOLD_MS));
    };

    recognition.onresult = (event) => {
      const transcriptParts: string[] = [];
      let allFinal = true;
      let confidence = 0;
      const runnersUp: string[] = [];
      for (let index = 0; index < event.results.length; index += 1) {
        const result = event.results[index];
        const alternative = result?.[0];
        if (alternative?.transcript) transcriptParts.push(alternative.transcript.trim());
        confidence = Math.max(confidence, alternative?.confidence ?? 0);
        allFinal = allFinal && Boolean(result?.isFinal);
        // Everything after the recogniser's favourite, in its own ranking.
        for (let other = 1; other < (result?.length ?? 0); other += 1) {
          const text = result?.[other]?.transcript?.trim();
          if (text) runnersUp.push(text);
        }
      }
      bufferedTranscript = transcriptParts.join(" ").trim() || bufferedTranscript;
      bufferedConfidence = Math.max(bufferedConfidence, confidence);
      if (runnersUp.length) bufferedAlternatives = runnersUp.slice(0, 4);
      // Something was heard. If nothing else follows it, answer rather than
      // holding the microphone open for the rest of the window - some browsers
      // never mark a short utterance final, and a child who said "A" a second
      // ago has no idea why the app is still listening. Interim results count
      // here, which is most of the delay a child used to feel: the wait after
      // one is short precisely because a one-word answer has nothing left to
      // arrive.
      if (bufferedTranscript) endAfterQuiet();
      if (allFinal && bufferedTranscript) {
        window.clearTimeout(timer);
        recognition.stop();
        finish({
          transcript: bufferedTranscript,
          confidence: bufferedConfidence || 0.9,
          alternatives: bufferedAlternatives
        });
      }
    };
    recognition.onerror = (event) => {
      // "no-speech" is the browser saying it endpointed before it heard a word,
      // which is what it does to a child who says one short letter. Ending the
      // turn on it hands back silence a fraction of a second after the mic
      // opened, long before the child has finished deciding to speak. The
      // child's window is `timeoutMs`, and only a real fault ends it early.
      if (event.error === "no-speech" || event.error === "aborted") return;
      window.clearTimeout(timer);
      finish({
        transcript: bufferedTranscript,
        confidence: bufferedConfidence,
        alternatives: bufferedAlternatives,
        error: event.error
      });
    };

    recognition.onend = () => {
      if (settled) return;
      // Chrome ends the session on its own when it gives up on a short
      // utterance. While the child still has time, start it again rather than
      // reporting silence they were never given a chance to break - bounded, so
      // a genuinely dead recogniser cannot spin. The budget is larger when our
      // own meter heard a voice, because then we know there was something to
      // hear and that it was only too quiet for Chrome.
      const budget = voice.heardVoice() ? MAX_RESTARTS_WHEN_HEARD : MAX_RESTARTS;
      if (!bufferedTranscript && restarts < budget && Date.now() < deadline) {
        restarts += 1;
        try {
          recognition.start();
          return;
        } catch {
          // Could not restart; fall through and report what we have.
        }
      }
      window.clearTimeout(timer);
      finish({
        transcript: bufferedTranscript,
        confidence: bufferedConfidence || (bufferedTranscript ? 0.75 : 0),
        alternatives: bufferedAlternatives
      });
    };

    try {
      recognition.start();
    } catch {
      window.clearTimeout(timer);
      voice.stop();
      finish({ transcript: "", confidence: 0, alternatives: [] });
    }
  });
}

export async function captureVoiceAnswer({
  sessionId,
  activityId,
  answerType,
  correctAnswer,
  acceptedAnswers = [],
  options = [],
  timeoutMs = 6500,
  language,
  onLevel
}: {
  sessionId: string;
  activityId: string;
  answerType: string;
  correctAnswer?: string | null;
  acceptedAnswers?: string[];
  options?: string[];
  timeoutMs?: number;
  language?: string;
  onLevel?: (level: number) => void;
}) {
  // Left to the content when the caller does not insist. See `listeningLanguage`.
  const listenIn =
    language ?? listeningLanguage(correctAnswer, ...acceptedAnswers, ...options);
  // Warm first, so the recogniser starts on an audio device that is already
  // awake and so there is a level to read. Never blocks for long: a microphone
  // that is already open answers immediately, and a refused one answers `null`.
  await primeMicrophone();
  // Only what is on screen. The answer key is deliberately not an endpointing
  // hint - it would make the microphone behave differently for a right answer.
  const browserResult = await listenForTranscript(timeoutMs, listenIn, {
    expectedPhrases: options,
    onLevel
  });
  if (!browserResult.transcript.trim()) {
    if (["not-allowed", "service-not-allowed"].includes(browserResult.error ?? "")) {
      throw new DOMException("Microphone permission is off.", "NotAllowedError");
    }
    if (browserResult.error && !["no-speech", "aborted"].includes(browserResult.error)) {
      throw new Error(`Speech recognition failed: ${browserResult.error}`);
    }
    return localNormalizeSpeech({
      session_id: sessionId,
      activity_id: activityId,
      answer_type: answerType,
      transcript: "",
      confidence: 0,
      correct_answer: correctAnswer,
      accepted_answers: acceptedAnswers,
      options
    });
  }

  return normalizeSpeech({
    session_id: sessionId,
    activity_id: activityId,
    answer_type: answerType,
    transcript: browserResult.transcript,
    confidence: browserResult.confidence,
    correct_answer: correctAnswer,
    accepted_answers: acceptedAnswers,
    options,
    alternatives: browserResult.alternatives
  }).catch(() =>
    localNormalizeSpeech({
      session_id: sessionId,
      activity_id: activityId,
      answer_type: answerType,
      transcript: browserResult.transcript,
      confidence: browserResult.confidence,
      correct_answer: correctAnswer,
      accepted_answers: acceptedAnswers,
      options
    })
  );
}

export async function captureSpeechTranscript(
  timeoutMs = 8000,
  language = "en-US",
  onLevel?: (level: number) => void
) {
  if (!canUseSpeechRecognition()) {
    throw new Error("Voice input is not supported in this browser. Type your question instead.");
  }

  await primeMicrophone();
  const result = await listenForTranscript(timeoutMs, language, { onLevel });
  if (result.error === "not-allowed" || result.error === "service-not-allowed") {
    throw new Error("Microphone permission is off. Allow microphone access or type your question.");
  }
  if (!result.transcript.trim()) {
    throw new Error("I did not hear a question. Please try again or type it below.");
  }
  return result.transcript.trim();
}

/**
 * Open the microphone for a conductor directive and hand back what was heard,
 * raw.
 *
 * Deliberately does **not** call `/speech/normalize`. In a conducted class the
 * server resolves the transcript itself, against state this browser does not
 * have - which attempt this is, what was just taught, whether the utterance was
 * an answer at all. Resolving here first would be the client deciding, and then
 * telling the server about it.
 *
 * Unlike `captureSpeechTranscript` it never throws: silence and a denied
 * microphone are both outcomes the *server* decides the meaning of, so they are
 * reported rather than raised.
 */
export async function captureClassSpeech(options: {
  /** The thing the child is being asked to say, when there is such a thing. */
  expect?: string;
  contextualStrings?: string[];
  /** The topic's language, as the directive gives it ("hi"). */
  language?: string;
  timeoutMs?: number;
  /** The live microphone level, so the screen can show it is being heard. */
  onLevel?: (level: number) => void;
}): Promise<{ transcript: string; confidence: number; alternatives: string[]; blocked: boolean }> {
  if (!canUseSpeechRecognition()) {
    return { transcript: "", confidence: 0, alternatives: [], blocked: true };
  }

  // The language of the thing being said, not of the app: a Hindi level asks
  // अ of a child whose profile says English.
  const listenIn = listeningLanguage(
    options.expect,
    options.language === "hi" ? "अ" : null,
    ...(options.contextualStrings ?? [])
  );

  // Wake the device before the recogniser asks for it - see `micStream`. It is
  // a no-op once the class has primed it, which the class does on the way in.
  await primeMicrophone();

  // The words already on screen are what a child is most likely to say, so
  // hearing one of them means they have finished. It settles the microphone;
  // it never settles the question - the transcript goes to the server exactly
  // as it would have, and the server is what resolves it.
  const result = await listenForTranscript(options.timeoutMs ?? 8000, listenIn, {
    expectedPhrases: [options.expect ?? "", ...(options.contextualStrings ?? [])],
    onLevel: options.onLevel
  });
  const blocked = ["not-allowed", "service-not-allowed"].includes(result.error ?? "");
  return {
    transcript: result.transcript.trim(),
    confidence: result.confidence,
    alternatives: result.alternatives,
    blocked
  };
}

export function normalizeSpeech(payload: {
  session_id: string;
  activity_id: string;
  answer_type: string;
  transcript: string;
  confidence: number;
  correct_answer?: string | null;
  accepted_answers?: string[];
  options?: string[];
  /** The recogniser's runners-up. Only consulted when the first guess fails. */
  alternatives?: string[];
}) {
  return api<SpeechTranscription>("/speech/normalize", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

const numberWords: Record<string, string> = {
  zero: "0",
  oh: "0",
  one: "1",
  won: "1",
  two: "2",
  too: "2",
  to: "2",
  three: "3",
  tree: "3",
  free: "3",
  four: "4",
  for: "4",
  fore: "4",
  five: "5",
  six: "6",
  seven: "7",
  eight: "8",
  ate: "8",
  nine: "9",
  ten: "10"
};

const letterExamples: Record<string, string> = {
  apple: "a",
  ant: "a",
  ball: "b",
  banana: "b",
  cat: "c",
  cup: "c",
  dog: "d",
  door: "d",
  egg: "e",
  fish: "f",
  hat: "h"
};

const colours = new Set(["red", "blue", "yellow", "green", "orange", "purple", "pink", "white", "black", "brown"]);
const shapes = new Set(["circle", "square", "triangle", "rectangle", "star", "diamond", "oval", "heart"]);
const letterLikeTypes = new Set(["select_letter", "introduce_letter", "repeat_letter", "recognize_letter", "repeat_after_me", "recognition", "multiple_choice", "match", "mixed"]);

function cleanSpeech(text: string) {
  return text.toLowerCase().replace(/[^\w\s]/g, " ").replace(/\s+/g, " ").trim();
}

export function extractContextualAnswer(transcript: string, answerType = "", options: string[] = []) {
  const type = answerType.toLowerCase();
  const tokens = cleanSpeech(transcript).split(" ").filter(Boolean);
  const mappedTokens = tokens.map((token) => numberWords[token] ?? token);
  const normalizedOptions = options.map((option) => cleanSpeech(option));
  const numericDomain = ["select_number", "identify_number", "count_objects"].includes(type)
    || (normalizedOptions.length > 0 && normalizedOptions.every((option) => /^\d+$/.test(option)));
  const letterDomain = type.includes("letter")
    || (normalizedOptions.length > 0 && normalizedOptions.every((option) => /^[a-z]$/.test(option)));
  const colourDomain = type.includes("colour") || type.includes("color") || normalizedOptions.some((option) => colours.has(option));
  const shapeDomain = type.includes("shape") || normalizedOptions.some((option) => shapes.has(option));

  if (numericDomain) {
    const numbers = mappedTokens.filter((token) => /^\d+$/.test(token));
    if (numbers.length) return numbers.at(-1) ?? null;
  }
  if (letterDomain) {
    const examples = mappedTokens.map((token) => letterExamples[token]).filter(Boolean);
    if (examples.length) return examples.at(-1) ?? null;
    const letters = mappedTokens.filter((token) => /^[a-z]$/.test(token));
    if (letters.length) return letters.at(-1) ?? null;
  }
  if (colourDomain) {
    const matchedColours = mappedTokens.filter((token) => colours.has(token));
    if (matchedColours.length) return matchedColours.at(-1) ?? null;
  }
  if (shapeDomain) {
    const matchedShapes = mappedTokens.filter((token) => shapes.has(token));
    if (matchedShapes.length) return matchedShapes.at(-1) ?? null;
  }
  return null;
}

function localNormalizeAnswer(transcript: string, answerType = "") {
  const cleaned = cleanSpeech(transcript);
  if (letterLikeTypes.has(answerType) && cleaned.length === 1 && /^[a-z]$/.test(cleaned)) {
    return cleaned;
  }
  const tokens = cleanSpeech(transcript)
    .split(" ")
    .filter((token) => token && !["the", "a", "an", "it", "is", "its", "number", "letter", "colour", "color", "please"].includes(token));
  const mapped = tokens.map((token) => numberWords[token] ?? token);
  if (["select_letter", "multiple_choice", "match", "mixed"].includes(answerType)) {
    const example = mapped.find((token) => letterExamples[token]);
    if (example) return letterExamples[example];
  }
  return mapped.length === 1 ? mapped[0] : mapped.join(" ");
}

function localNormalizeSpeech(payload: {
  session_id: string;
  activity_id: string;
  answer_type: string;
  transcript: string;
  confidence: number;
  correct_answer?: string | null;
  accepted_answers?: string[];
  options?: string[];
}): SpeechTranscription {
  const raw = payload.transcript.trim();
  const normalized = localNormalizeAnswer(raw, payload.answer_type);
  const candidates = [payload.correct_answer, ...(payload.accepted_answers ?? []), ...(payload.options ?? [])]
    .filter((candidate): candidate is string => Boolean(candidate))
    .map((candidate) => ({ raw: candidate, normalized: localNormalizeAnswer(candidate, payload.answer_type) }));
  const rawTokens = new Set(cleanSpeech(raw).split(" ").filter(Boolean));
  const exact = candidates.find((candidate) => candidate.normalized === normalized || rawTokens.has(candidate.normalized));
  const semanticAnswer = extractContextualAnswer(raw, payload.answer_type, payload.options);
  const hasTranscript = Boolean(raw);
  return {
    raw_transcript: raw,
    normalized,
    resolved_answer: exact?.normalized ?? semanticAnswer ?? normalized,
    resolution_confidence: exact ? Math.max(payload.confidence, 0.95) : semanticAnswer ? Math.max(payload.confidence, 0.9) : payload.confidence,
    ambiguous: !hasTranscript || (!exact && !semanticAnswer && payload.confidence < 0.65),
    matched_candidate: exact?.raw ?? null,
    input_kind: !hasTranscript ? "empty" : exact || semanticAnswer ? "answer" : "unresolved"
  };
}
