"use client";

/**
 * What the avatar's face is doing.
 *
 * These are *feelings*, not animations: the panda is the only thing on a
 * pre-reader's screen that can react to what just happened, so what it does
 * with its eyebrows carries more of the lesson than any sentence does.
 *
 * Two of them are deliberately never shown for a wrong answer. `sad` and
 * `crying` are for when **the app** has let the child down - the microphone
 * heard nothing, the server did not answer - never as a verdict on a child who
 * has just tried something and missed. A four-year-old who makes the panda cry
 * by getting a letter wrong learns to stop answering.
 *
 * They are two strengths of the same feeling, not synonyms: `sad` is the eyes
 * gone soft and a small frown, worn when something did not work and can be
 * tried again; `crying` is real tears, eyes squeezed shut and a shaking sob,
 * worn when the class itself could not carry on.
 */
export type AvatarState =
  | "idle"
  | "waving"
  | "listening"
  | "thinking"
  | "speaking"
  | "happy"
  | "celebrating"
  | "proud"
  | "curious"
  | "encouraging"
  | "sad"
  | "crying"
  | "storytelling"
  | "sleeping"
  | "error_fallback";

export type AvatarEffect =
  | "star_burst"
  | "confetti"
  | "level_unlock"
  | "reward_chest"
  | "gentle_hint"
  | "story_transition"
  | "certificate_celebration"
  | "sparkle"
  | "bounce"
  | "rainbow"
  | "pulse"
  | "none";

export type AvatarPayload = {
  state: AvatarState;
  message: string;
  speak?: boolean;
  animationEffect?: AvatarEffect | null;
  durationMs?: number | null;
};

export type AvatarContextValue = {
  state: AvatarState;
  message: string;
  effect: AvatarEffect | null;
  isSpeaking: boolean;
  muted: boolean;
  setAvatar: (payload: AvatarPayload) => void;
  resetAvatar: () => void;
  speakMessage: (message?: string) => void;
  speakMessageAsync: (message?: string) => Promise<void>;
  stopSpeaking: () => void;
  toggleMute: () => void;
};
