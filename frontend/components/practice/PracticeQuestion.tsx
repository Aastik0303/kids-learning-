"use client";

import { LearningQuestion } from "@/components/learning/LearningQuestion";
import type { VoiceInteractionState } from "@/components/voice/VoiceStateIndicator";
import type { VisualGuideAction } from "@/components/guide/VisualGuideRenderer";
import type { Activity } from "@/types";

export function PracticeQuestion({
  activity,
  sessionId,
  guideMessage,
  voiceState,
  onVoiceStateChange,
  onAnswer,
  onGuideQuestion,
  disabled,
  highlightId,
  visualAction,
  countGuideEnabled,
  showOptionsWithMicrophone
}: {
  activity: Activity;
  sessionId: string;
  guideMessage: string;
  voiceState: VoiceInteractionState;
  onVoiceStateChange: (state: VoiceInteractionState) => void;
  onAnswer: (answer: string) => Promise<void> | void;
  onGuideQuestion?: (question: string) => Promise<void> | void;
  disabled?: boolean;
  highlightId?: string | null;
  visualAction?: VisualGuideAction;
  countGuideEnabled?: boolean;
  showOptionsWithMicrophone?: boolean;
}) {
  return (
    <LearningQuestion
      activity={activity}
      sessionId={sessionId}
      guideMessage={guideMessage}
      voiceState={voiceState}
      onVoiceStateChange={onVoiceStateChange}
      onAnswer={onAnswer}
      onGuideQuestion={onGuideQuestion}
      disabled={disabled}
      highlightId={highlightId}
      visualAction={visualAction}
      countGuideEnabled={countGuideEnabled}
      showOptionsWithMicrophone={showOptionsWithMicrophone}
    />
  );
}
