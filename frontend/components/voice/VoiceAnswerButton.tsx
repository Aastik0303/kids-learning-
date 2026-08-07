"use client";

import type { VoiceInteractionState } from "./VoiceStateIndicator";

const buttonCopy: Partial<Record<VoiceInteractionState, string>> = {
  ready_to_listen: "Mic",
  listening: "Listening",
  transcribing: "Checking",
  evaluating: "Checking",
  speech_error: "Try again",
  incorrect: "Try again",
  re_explaining: "Listen first",
  speaking: "Listen first",
  correct: "Nice"
};

export function VoiceAnswerButton({
  state,
  disabled,
  onClick
}: {
  state: VoiceInteractionState;
  disabled?: boolean;
  onClick: () => void;
}) {
  const active = state === "ready_to_listen" || state === "speech_error" || state === "incorrect";
  const busy = ["listening", "transcribing", "evaluating"].includes(state);
  return (
    <button
      data-guide-id="microphone-button"
      type="button"
      disabled={disabled || !active}
      onClick={onClick}
      className={`pressable mx-auto grid h-28 w-28 place-items-center rounded-full text-xl font-black shadow-soft transition ${
        busy ? "bg-sky text-white" : active ? "bg-leaf text-white" : "bg-white text-ink/50"
      } disabled:cursor-not-allowed disabled:opacity-60`}
      aria-label="Speak your answer"
    >
      {buttonCopy[state] ?? "Mic"}
    </button>
  );
}
