"use client";

import { captureVoiceAnswer } from "@/services/speech";
import type { Activity } from "@/types";
import { VoiceAnswerButton } from "./VoiceAnswerButton";
import type { VoiceInteractionState } from "./VoiceStateIndicator";

const LOW_CONFIDENCE = 0.65;

export function VoiceRecorder({
  sessionId,
  activity,
  state,
  disabled,
  onStateChange,
  onTranscript,
  onSpeechError,
  onVoiceAnswer
}: {
  sessionId: string;
  activity: Activity;
  state: VoiceInteractionState;
  disabled?: boolean;
  onStateChange: (state: VoiceInteractionState) => void;
  onTranscript: (transcript: string) => void;
  onSpeechError: (message: string) => void;
  onVoiceAnswer: (answer: string) => Promise<void> | void;
}) {
  async function record() {
    if (disabled || !["ready_to_listen", "speech_error", "incorrect"].includes(state)) return;

    try {
      onSpeechError("");
      onTranscript("");
      onStateChange("listening");
      const result = await captureVoiceAnswer({
        sessionId,
        activityId: activity.activity_id,
        answerType: activity.type
      });
      onStateChange("transcribing");
      onTranscript(result.transcript);

      if (!result.transcript.trim()) {
        onStateChange("speech_error");
        onSpeechError("I did not hear an answer. Tap the microphone and try again.");
        return;
      }

      if (result.confidence < LOW_CONFIDENCE) {
        onStateChange("speech_error");
        onSpeechError("I did not hear that clearly. Please try again.");
        return;
      }

      onStateChange("evaluating");
      await onVoiceAnswer(result.transcript);
    } catch (error) {
      onStateChange("speech_error");
      const permissionDenied = error instanceof DOMException && ["NotAllowedError", "PermissionDeniedError"].includes(error.name);
      onSpeechError(permissionDenied ? "Microphone permission is off. You can use the answer choices below." : "Voice did not work this time. Please try again.");
    }
  }

  return <VoiceAnswerButton state={state} disabled={disabled} onClick={record} />;
}
