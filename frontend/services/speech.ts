"use client";

import { API_BASE, api } from "@/services/api";

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
  error?: string;
};

type WindowWithSpeechRecognition = Window &
  typeof globalThis & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };

export type SpeechTranscription = {
  raw_transcript: string;
  normalized: string;
  resolved_answer: string;
  resolution_confidence: number;
  ambiguous: boolean;
  matched_candidate: string | null;
  input_kind: "answer" | "unresolved" | "empty";
};

export type VoiceProvider = "browser" | "elevenlabs";

const VOICE_PROVIDER_STORAGE_KEY = "child-ai-voice-provider";

export function getVoiceProvider(): VoiceProvider {
  if (typeof window === "undefined") return "browser";
  return window.localStorage.getItem(VOICE_PROVIDER_STORAGE_KEY) === "elevenlabs" ? "elevenlabs" : "browser";
}

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

export function stopSpeech() {
  if (typeof window === "undefined") return;
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

function speakWithBrowser(text: string) {
  return new Promise<void>((resolve) => {
    if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
      resolve();
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
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
  if (getVoiceProvider() === "browser") {
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
      body: JSON.stringify({ text }),
      signal: controller.signal
    });
    if (!response.ok) throw new Error("ElevenLabs voice unavailable");
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

function createSpeechRecognition(language = "en-US") {
  if (!canUseSpeechRecognition()) return null;
  const speechWindow = window as WindowWithSpeechRecognition;
  const Recognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
  if (!Recognition) return null;
  const recognition = new Recognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.maxAlternatives = 3;
  recognition.lang = language;
  return recognition;
}

function listenForTranscript(timeoutMs: number, language = "en-US") {
  return new Promise<BrowserSpeechResult>((resolve) => {
    const recognition = createSpeechRecognition(language);
    if (!recognition) {
      window.setTimeout(() => resolve({ transcript: "", confidence: 0 }), timeoutMs);
      return;
    }

    let settled = false;
    let bufferedTranscript = "";
    let bufferedConfidence = 0;
    const finish = (result: BrowserSpeechResult) => {
      if (settled) return;
      settled = true;
      resolve(result);
    };
    const timer = window.setTimeout(() => {
      recognition.stop();
      window.setTimeout(() => {
        if (!settled) finish({ transcript: bufferedTranscript, confidence: bufferedConfidence || (bufferedTranscript ? 0.75 : 0) });
      }, 300);
    }, timeoutMs);

    recognition.onresult = (event) => {
      const transcriptParts: string[] = [];
      let allFinal = true;
      let confidence = 0;
      for (let index = 0; index < event.results.length; index += 1) {
        const result = event.results[index];
        const alternative = result?.[0];
        if (alternative?.transcript) transcriptParts.push(alternative.transcript.trim());
        confidence = Math.max(confidence, alternative?.confidence ?? 0);
        allFinal = allFinal && Boolean(result?.isFinal);
      }
      bufferedTranscript = transcriptParts.join(" ").trim() || bufferedTranscript;
      bufferedConfidence = Math.max(bufferedConfidence, confidence);
      if (allFinal && bufferedTranscript) {
        window.clearTimeout(timer);
        finish({ transcript: bufferedTranscript, confidence: bufferedConfidence || 0.9 });
      }
    };
    recognition.onerror = (event) => {
      window.clearTimeout(timer);
      finish({ transcript: bufferedTranscript, confidence: bufferedConfidence, error: event.error });
    };
    recognition.onend = () => {
      window.clearTimeout(timer);
      if (!settled) finish({ transcript: bufferedTranscript, confidence: bufferedConfidence || (bufferedTranscript ? 0.75 : 0) });
    };

    try {
      recognition.start();
    } catch {
      window.clearTimeout(timer);
      finish({ transcript: "", confidence: 0 });
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
  language = "en-US"
}: {
  sessionId: string;
  activityId: string;
  answerType: string;
  correctAnswer?: string | null;
  acceptedAnswers?: string[];
  options?: string[];
  timeoutMs?: number;
  language?: string;
}) {
  const browserResult = await listenForTranscript(timeoutMs, language);
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
    options
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

export async function captureSpeechTranscript(timeoutMs = 8000, language = "en-US") {
  if (!canUseSpeechRecognition()) {
    throw new Error("Voice input is not supported in this browser. Type your question instead.");
  }

  const result = await listenForTranscript(timeoutMs, language);
  if (result.error === "not-allowed" || result.error === "service-not-allowed") {
    throw new Error("Microphone permission is off. Allow microphone access or type your question.");
  }
  if (!result.transcript.trim()) {
    throw new Error("I did not hear a question. Please try again or type it below.");
  }
  return result.transcript.trim();
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
