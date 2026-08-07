"use client";

import { PracticeQuestion } from "@/components/practice/PracticeQuestion";
import type { VoiceInteractionState } from "@/components/voice/VoiceStateIndicator";
import type { Activity } from "@/types";

export function VoicePracticeSession({
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
    <PracticeQuestion
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
