"use client";

export type VoiceInteractionState =
  | "idle"
  | "explaining"
  | "speaking"
  | "ready_to_listen"
  | "listening"
  | "transcribing"
  | "evaluating"
  | "correct"
  | "incorrect"
  | "re_explaining"
  | "speech_error"
  | "completed";

const stateCopy: Record<VoiceInteractionState, { label: string; detail: string }> = {
  idle: { label: "Getting ready", detail: "The guide will explain first." },
  explaining: { label: "Guide is explaining", detail: "Listen first." },
  speaking: { label: "Guide is speaking", detail: "Microphone is off." },
  ready_to_listen: { label: "Tap to talk", detail: "Say an answer or ask for help." },
  listening: { label: "Listening", detail: "Say an answer or ask for help." },
  transcribing: { label: "Checking", detail: "Turning speech into words." },
  evaluating: { label: "Checking", detail: "Looking at your answer." },
  correct: { label: "Great job", detail: "That answer is correct." },
  incorrect: { label: "Try again", detail: "The guide will help." },
  re_explaining: { label: "Guide is helping", detail: "Listen, then try again." },
  speech_error: { label: "Try again", detail: "I did not hear that clearly." },
  completed: { label: "Complete", detail: "Moving to the next step." }
};

export function VoiceStateIndicator({ state }: { state: VoiceInteractionState }) {
  const copy = stateCopy[state];
  return (
    <div className="rounded-3xl bg-white px-4 py-3 text-center shadow-soft" aria-live="polite">
      <p className="text-lg font-black text-ink">{copy.label}</p>
      <p className="text-sm font-bold text-ink/60">{copy.detail}</p>
    </div>
  );
}
