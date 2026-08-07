"use client";

import { useEffect, useState } from "react";
import { useAvatar } from "@/components/avatar/AvatarProvider";
import { SpeechErrorMessage } from "@/components/voice/SpeechErrorMessage";
import { VoiceFallbackOptions } from "@/components/voice/VoiceFallbackOptions";
import { VoiceRecorder } from "@/components/voice/VoiceRecorder";
import { VoiceStateIndicator, type VoiceInteractionState } from "@/components/voice/VoiceStateIndicator";
import { VoiceTranscriptPreview } from "@/components/voice/VoiceTranscriptPreview";
import type { Activity } from "@/types";

const shapeClass: Record<string, string> = {
  circle: "rounded-full bg-berry",
  square: "rounded-xl bg-sky",
  triangle: "triangle",
  red: "rounded-full bg-berry",
  blue: "rounded-full bg-sky",
  yellow: "rounded-full bg-sunshine",
  green: "rounded-full bg-leaf"
};

const visualEmoji: Record<string, string> = {
  apple: "apple",
  star: "star",
  "one star": "star",
  block: "block",
  red: "red",
  blue: "blue",
  yellow: "yellow",
  green: "green",
  circle: "circle",
  square: "square",
  triangle: "triangle",
  "red circle": "red circle",
  "blue square": "blue square",
  "yellow triangle": "yellow triangle"
};

function VisualItem({ item }: { item: string }) {
  const normalized = item.toLowerCase();
  const label = visualEmoji[normalized] ?? null;
  if (label) {
    return (
      <span className="grid h-20 w-20 place-items-center rounded-3xl bg-white px-2 text-center text-sm font-black capitalize text-ink shadow-soft" aria-label={item}>
        {label}
      </span>
    );
  }
  const simple = normalized.split(" ").at(-1) ?? normalized;
  if (shapeClass[simple]) {
    return <span className={`grid h-20 w-20 place-items-center text-xs font-black text-white shadow-soft ${shapeClass[simple]}`}>{item.includes(" ") ? item.split(" ")[0] : ""}</span>;
  }
  return <span className="grid min-h-20 min-w-20 place-items-center rounded-3xl bg-white px-5 text-base font-black shadow-soft">{item}</span>;
}

export function LearningQuestion({
  activity,
  sessionId,
  guideMessage,
  voiceState,
  onVoiceStateChange,
  onAnswer,
  disabled,
  highlightId,
  visualAnswerFallback = true
}: {
  activity: Activity;
  sessionId: string;
  guideMessage: string;
  voiceState: VoiceInteractionState;
  onVoiceStateChange: (state: VoiceInteractionState) => void;
  onAnswer: (answer: string) => Promise<void> | void;
  disabled?: boolean;
  highlightId?: string | null;
  visualAnswerFallback?: boolean;
}) {
  const { setAvatar, speakMessageAsync } = useAvatar();
  const [transcript, setTranscript] = useState("");
  const [speechError, setSpeechError] = useState("");
  const [speechFailures, setSpeechFailures] = useState(0);
  const [showFallback, setShowFallback] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setTranscript("");
    setSpeechError("");
    setShowFallback(false);
    setSpeechFailures(0);
    onVoiceStateChange("speaking");
    setAvatar({ state: "speaking", message: guideMessage || activity.prompt, animationEffect: "story_transition", durationMs: null });
    speakMessageAsync(guideMessage || activity.prompt).then(() => {
      window.setTimeout(() => {
        if (!cancelled) {
          onVoiceStateChange("ready_to_listen");
          setAvatar({ state: "happy", message: "Tap the microphone and say your answer.", animationEffect: "none", durationMs: null });
        }
      }, 450);
    });
    return () => {
      cancelled = true;
    };
  }, [activity.activity_id, activity.prompt, guideMessage, onVoiceStateChange, setAvatar, speakMessageAsync]);

  function handleSpeechError(message: string) {
    setSpeechError(message);
    if (message) {
      setSpeechFailures((current) => {
        const next = current + 1;
        if (visualAnswerFallback && next >= 2) setShowFallback(true);
        return next;
      });
      setAvatar({ state: "encouraging", message, speak: true, animationEffect: "gentle_hint" });
    }
  }

  return (
    <section data-guide-id="question-area" className={`surface-panel grid gap-5 rounded-[2rem] p-5 sm:p-6 ${highlightId === "question-area" ? "guide-glow" : ""}`}>
      <div className="grid gap-4 rounded-[2rem] bg-[#f7fbff] p-4 sm:grid-cols-[7rem_1fr] sm:items-center">
        <div className="mascot-face min-h-28 rounded-[1.75rem]" />
        <div>
          <p className="text-sm font-black uppercase text-sky">Mini mission</p>
          <h2 className="mt-2 text-3xl font-black leading-tight text-ink sm:text-4xl">{activity.prompt}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-full bg-leaf/10 px-4 py-2 text-sm font-black capitalize text-leaf">{activity.difficulty}</span>
            <span className="rounded-full bg-sunshine/40 px-4 py-2 text-sm font-black text-ink">Reward +1</span>
          </div>
        </div>
      </div>
      {activity.visual_items.length ? (
        <div data-guide-id="counting-object-group" className={`flex min-h-36 flex-wrap items-center justify-center gap-4 rounded-[2rem] border border-sky/10 bg-[#f7fbff] p-5 ${highlightId === "counting-object-group" ? "guide-glow" : ""}`}>
          {activity.visual_items.map((item, index) => (
            <VisualItem key={`${item}-${index}`} item={item} />
          ))}
        </div>
      ) : null}
      <div data-guide-id="voice-answer-area" className={`grid gap-4 rounded-[2rem] bg-sunshine/20 p-5 text-center ${highlightId === "voice-answer-area" || highlightId === "microphone-button" ? "guide-glow" : ""}`}>
        <VoiceStateIndicator state={voiceState} />
        <VoiceRecorder
          sessionId={sessionId}
          activity={activity}
          state={voiceState}
          disabled={disabled || voiceState === "speaking" || voiceState === "re_explaining"}
          onStateChange={onVoiceStateChange}
          onTranscript={setTranscript}
          onSpeechError={handleSpeechError}
          onVoiceAnswer={onAnswer}
        />
        <VoiceTranscriptPreview transcript={transcript} />
        <SpeechErrorMessage message={speechError} />
      </div>
      {visualAnswerFallback && showFallback ? (
        <div className="grid gap-3 rounded-[2rem] border border-sky/10 bg-[#f7fbff] p-4">
          <p className="text-center text-sm font-black uppercase text-sky">Accessibility choices</p>
          <VoiceFallbackOptions options={activity.options} disabled={disabled} onAnswer={onAnswer} />
        </div>
      ) : null}
    </section>
  );
}
