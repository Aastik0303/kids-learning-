"use client";

import { api } from "@/services/api";

type SpeechRecognitionConstructor = new () => SpeechRecognition;

type SpeechRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionEvent = {
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

type BrowserSpeechResult = {
  transcript: string;
  confidence: number;
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
};

export function canSpeak() {
  return typeof window !== "undefined" && "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

export function stopSpeech() {
  if (!canSpeak()) return;
  window.speechSynthesis.cancel();
}

export function speakText(text: string, onEnd?: () => void) {
  if (!canSpeak() || !text.trim()) {
    onEnd?.();
    return false;
  }

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.9;
  utterance.pitch = 1.12;
  utterance.volume = 1;
  utterance.onend = () => onEnd?.();
  utterance.onerror = () => onEnd?.();
  window.speechSynthesis.speak(utterance);
  return true;
}

export function speakTextAsync(text: string) {
  return new Promise<void>((resolve) => {
    const started = speakText(text, resolve);
    if (!started) resolve();
  });
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
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
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
    const finish = (result: BrowserSpeechResult) => {
      if (settled) return;
      settled = true;
      resolve(result);
    };
    const timer = window.setTimeout(() => {
      recognition.stop();
      finish({ transcript: "", confidence: 0 });
    }, timeoutMs);

    recognition.onresult = (event) => {
      const alternative = event.results[0]?.[0];
      window.clearTimeout(timer);
      finish({
        transcript: alternative?.transcript?.trim() ?? "",
        confidence: alternative?.confidence ?? 0.9
      });
    };
    recognition.onerror = () => {
      window.clearTimeout(timer);
      finish({ transcript: "", confidence: 0 });
    };
    recognition.onend = () => {
      window.clearTimeout(timer);
      if (!settled) finish({ transcript: "", confidence: 0 });
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

function cleanSpeech(text: string) {
  return text.toLowerCase().replace(/[^\w\s]/g, " ").replace(/\s+/g, " ").trim();
}

function localNormalizeAnswer(transcript: string) {
  const tokens = cleanSpeech(transcript)
    .split(" ")
    .filter((token) => token && !["the", "a", "an", "it", "is", "its", "number", "letter", "colour", "color", "please"].includes(token));
  const mapped = tokens.map((token) => numberWords[token] ?? token);
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
  const normalized = localNormalizeAnswer(raw);
  const candidates = [payload.correct_answer, ...(payload.accepted_answers ?? []), ...(payload.options ?? [])]
    .filter((candidate): candidate is string => Boolean(candidate))
    .map((candidate) => ({ raw: candidate, normalized: localNormalizeAnswer(candidate) }));
  const exact = candidates.find((candidate) => candidate.normalized === normalized);
  const hasTranscript = Boolean(raw);
  return {
    raw_transcript: raw,
    normalized,
    resolved_answer: exact?.normalized ?? normalized,
    resolution_confidence: exact ? Math.max(payload.confidence, 0.95) : payload.confidence,
    ambiguous: !hasTranscript || (!exact && payload.confidence < 0.65),
    matched_candidate: exact?.raw ?? null
  };
}
