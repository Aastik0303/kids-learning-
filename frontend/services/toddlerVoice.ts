"use client";

import { useCallback, useState } from "react";
import { captureVoiceAnswer, canSpeak, canUseSpeechRecognition, speakTextAsync, stopSpeech, type SpeechTranscription } from "@/services/speech";
import type { ToddlerActivity } from "@/types";

export function useTextToSpeech() {
  const [speaking, setSpeaking] = useState(false);
  const [available] = useState(canSpeak);

  const speak = useCallback(async (text: string) => {
    setSpeaking(true);
    try {
      await speakTextAsync(text);
    } finally {
      setSpeaking(false);
    }
  }, []);

  const stop = useCallback(() => {
    stopSpeech();
    setSpeaking(false);
  }, []);

  return { available, speaking, speak, stop };
}

export function useSpeechRecognition() {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState("");
  const [available] = useState(canUseSpeechRecognition);

  const startListening = useCallback(async (sessionId: string, activity: ToddlerActivity): Promise<SpeechTranscription | null> => {
    setError("");
    setListening(true);
    try {
      return await captureVoiceAnswer({
        sessionId,
        activityId: activity.activity_id,
        answerType: activity.type,
        correctAnswer: activity.answer,
        acceptedAnswers: activity.accepted,
        options: activity.choices,
        timeoutMs: 5200
      });
    } catch (err) {
      const permissionDenied = err instanceof DOMException && ["NotAllowedError", "PermissionDeniedError"].includes(err.name);
      setError(permissionDenied ? "Microphone is off. Tap an answer instead." : "I couldn't hear you. Try again.");
      return null;
    } finally {
      setListening(false);
    }
  }, []);

  return { available, listening, error, startListening, clearError: () => setError("") };
}
