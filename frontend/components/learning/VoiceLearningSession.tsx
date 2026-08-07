"use client";

import { LearningQuestion } from "@/components/learning/LearningQuestion";
import type { VoiceInteractionState } from "@/components/voice/VoiceStateIndicator";
import type { Activity } from "@/types";

export function VoiceLearningSession({
  activity,
  sessionId,
  guideMessage,
  voiceState,
  onVoiceStateChange,
  onAnswer,
  disabled,
  highlightId
}: {
  activity: Activity;
  sessionId: string;
  guideMessage: string;
  voiceState: VoiceInteractionState;
  onVoiceStateChange: (state: VoiceInteractionState) => void;
  onAnswer: (answer: string) => Promise<void> | void;
  disabled?: boolean;
  highlightId?: string | null;
}) {
  return (
    <LearningQuestion
      activity={activity}
      sessionId={sessionId}
      guideMessage={guideMessage}
      voiceState={voiceState}
      onVoiceStateChange={onVoiceStateChange}
      onAnswer={onAnswer}
      disabled={disabled}
      highlightId={highlightId}
    />
  );
}
