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

type WindowWithSpeechRecognition = Window &
  typeof globalThis & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };

export type SpeechTranscription = {
  transcript: string;
  confidence: number;
  normalized?: string;
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

function recordAudioChunk(stream: MediaStream, timeoutMs: number) {
  return new Promise<Blob>((resolve) => {
    if (!("MediaRecorder" in window)) {
      resolve(new Blob());
      return;
    }
    const chunks: Blob[] = [];
    const recorder = new MediaRecorder(stream);
    const stopTimer = window.setTimeout(() => {
      if (recorder.state !== "inactive") recorder.stop();
    }, timeoutMs);

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = () => {
      window.clearTimeout(stopTimer);
      resolve(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }));
    };
    recorder.start();
  });
}

function listenForTranscript(timeoutMs: number, language = "en-US") {
  return new Promise<SpeechTranscription>((resolve) => {
    const recognition = createSpeechRecognition(language);
    if (!recognition) {
      window.setTimeout(() => resolve({ transcript: "", confidence: 0 }), timeoutMs);
      return;
    }

    let settled = false;
    const finish = (result: SpeechTranscription) => {
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
  timeoutMs = 6500,
  language = "en-US"
}: {
  sessionId: string;
  activityId: string;
  answerType: string;
  timeoutMs?: number;
  language?: string;
}) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const transcriptPromise = listenForTranscript(timeoutMs, language);
  const audioPromise = recordAudioChunk(stream, timeoutMs);
  const [browserResult, audio] = await Promise.all([transcriptPromise, audioPromise]);
  stream.getTracks().forEach((track) => track.stop());

  const form = new FormData();
  form.append("audio", audio, "answer.webm");
  form.append("session_id", sessionId);
  form.append("activity_id", activityId);
  form.append("answer_type", answerType);
  form.append("transcript", browserResult.transcript);
  form.append("confidence", String(browserResult.confidence));

  return transcribeSpeech(form);
}

export function transcribeSpeech(form: FormData) {
  return api<SpeechTranscription>("/speech/transcribe", {
    method: "POST",
    body: form,
    headers: {}
  });
}
