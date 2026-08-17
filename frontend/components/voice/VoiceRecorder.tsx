"use client";

import { captureVoiceAnswer, hasGuideSpeechIntent } from "@/services/speech";
import type { Activity } from "@/types";
import { VoiceAnswerButton } from "./VoiceAnswerButton";
import type { VoiceInteractionState } from "./VoiceStateIndicator";

export function VoiceRecorder({
  sessionId,
  activity,
  state,
  disabled,
  onStateChange,
  onTranscript,
  onSpeechError,
  onGuideQuestion,
  onVoiceAnswer
}: {
  sessionId: string;
  activity: Activity;
  state: VoiceInteractionState;
  disabled?: boolean;
  onStateChange: (state: VoiceInteractionState) => void;
  onTranscript: (transcript: string) => void;
  onSpeechError: (message: string) => void;
  onGuideQuestion?: (question: string) => Promise<void> | void;
  onVoiceAnswer: (answer: string) => Promise<void> | void;
}) {
  async function record() {
    if (disabled || !["ready_to_listen", "speech_error", "incorrect"].includes(state)) return;

    let answerToSubmit = "";
    try {
      onSpeechError("");
      onTranscript("");
      onStateChange("listening");
      const result = await captureVoiceAnswer({
        sessionId,
        activityId: activity.activity_id,
        answerType: activity.type,
        // Presentational activities carry no answer key.
        correctAnswer: activity.correct_answer ?? "",
        acceptedAnswers: activity.correct_answer ? [activity.correct_answer, ...(activity.accept ?? [])] : [],
        options: activity.options
      });
      onStateChange("transcribing");
      onTranscript(result.raw_transcript);

      if (!result.raw_transcript.trim()) {
        onStateChange("speech_error");
        onSpeechError("I did not hear anything. Tap the microphone and try again.");
        return;
      }

      if (onGuideQuestion && hasGuideSpeechIntent(result.raw_transcript)) {
        onStateChange("re_explaining");
        await onGuideQuestion(result.raw_transcript.trim());
        return;
      }

      // Only an explicit help request belongs to the guide. Every other
      // non-empty transcript is an answer attempt and must reach the answer
      // evaluator, even when speech normalization labels it unresolved.
      answerToSubmit = result.resolved_answer || result.normalized || result.raw_transcript;

      if (!answerToSubmit) {
        onStateChange("speech_error");
        onSpeechError("I did not hear that clearly. Please try again.");
        return;
      }

      answerToSubmit ||= result.resolved_answer || result.normalized || result.raw_transcript;
    } catch (error) {
      onStateChange("speech_error");
      const permissionDenied = error instanceof DOMException && ["NotAllowedError", "PermissionDeniedError"].includes(error.name);
      onSpeechError(permissionDenied ? "Microphone permission is off. You can use the answer choices below." : "Voice did not work this time. Please try again.");
      return;
    }

    try {
      onStateChange("evaluating");
      await onVoiceAnswer(answerToSubmit);
    } catch {
      onStateChange("speech_error");
      onSpeechError("I heard you, but I could not check it. Try again.");
    }
  }

  return <VoiceAnswerButton state={state} disabled={disabled} onClick={record} />;
}
