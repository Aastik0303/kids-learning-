"use client";

import type { VoiceProvider } from "@/services/speech";

export type AvatarState =
  | "idle"
  | "waving"
  | "listening"
  | "thinking"
  | "speaking"
  | "happy"
  | "celebrating"
  | "encouraging"
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
  voiceProvider: VoiceProvider;
  setAvatar: (payload: AvatarPayload) => void;
  resetAvatar: () => void;
  speakMessage: (message?: string) => void;
  speakMessageAsync: (message?: string) => Promise<void>;
  stopSpeaking: () => void;
  toggleMute: () => void;
  toggleVoiceProvider: () => void;
};
