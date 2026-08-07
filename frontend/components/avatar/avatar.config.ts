"use client";

import type { AvatarEffect, AvatarPayload, AvatarState } from "./avatar.types";

export const AVATAR_CONFIG = {
  name: "Pip",
  species: "cheerful panda",
  rive: {
    src: process.env.NEXT_PUBLIC_RIVE_AVATAR_SRC ?? "",
    stateMachine: "Nursery Buddy",
    stateInput: "State",
    speakingInput: "IsSpeaking",
    effectInput: "Effect"
  },
  defaults: {
    state: "idle" as AvatarState,
    message: "Hi, I am Pip. I am ready when you are.",
    durationMs: 5200
  },
  maxMessageLength: 130
};

export const AVATAR_STATE_INDEX: Record<AvatarState, number> = {
  idle: 0,
  waving: 1,
  listening: 2,
  thinking: 3,
  speaking: 4,
  happy: 5,
  celebrating: 6,
  encouraging: 7,
  storytelling: 8,
  sleeping: 9,
  error_fallback: 10
};

export const AVATAR_EFFECT_INDEX: Record<AvatarEffect, number> = {
  none: 0,
  star_burst: 1,
  confetti: 2,
  level_unlock: 3,
  reward_chest: 4,
  gentle_hint: 5,
  story_transition: 6,
  certificate_celebration: 7,
  sparkle: 1,
  bounce: 2,
  rainbow: 7,
  pulse: 5
};

export function tidyAvatarMessage(message: string) {
  const trimmed = message.replace(/\s+/g, " ").trim();
  if (trimmed.length <= AVATAR_CONFIG.maxMessageLength) return trimmed;
  return `${trimmed.slice(0, AVATAR_CONFIG.maxMessageLength - 1).trim()}...`;
}

export function avatarForPage(page: "home" | "levels" | "practice" | "rewards" | "certificate" | "guide"): AvatarPayload {
  const messages: Record<typeof page, AvatarPayload> = {
    home: { state: "waving", message: "Hello! Choose Practice or continue your adventure.", animationEffect: "none" },
    levels: { state: "happy", message: "Follow the glowing step. Your next adventure is ready.", animationEffect: "level_unlock" },
    practice: { state: "happy", message: "Practice time! Try one small mission at a time.", animationEffect: "none" },
    rewards: { state: "celebrating", message: "Look at all the shiny rewards you are collecting!", animationEffect: "reward_chest" },
    certificate: { state: "celebrating", message: "The final treasure opens when every world is complete.", animationEffect: "certificate_celebration" },
    guide: { state: "listening", message: "Ask me a learning question. I will keep it simple.", animationEffect: "none" }
  };
  return messages[page];
}

export function avatarForLearningResult(result: {
  is_correct: boolean | null;
  feedback: string;
  tutor_response?: string;
  complete?: boolean;
  next_stage_unlocked?: boolean;
  recommended_practice?: boolean;
}): AvatarPayload {
  if (result.complete) {
    return {
      state: "celebrating",
      message: result.feedback || "Level complete. Wonderful work!",
      animationEffect: result.next_stage_unlocked ? "level_unlock" : "confetti",
      speak: false
    };
  }
  if (result.is_correct === true) {
    return {
      state: "celebrating",
      message: result.feedback || "Nice work! Here comes the next one.",
      animationEffect: "star_burst",
      speak: false
    };
  }
  if (result.is_correct === false) {
    return {
      state: result.recommended_practice ? "encouraging" : "thinking",
      message: result.feedback || "Good try. Let us look slowly.",
      animationEffect: "gentle_hint",
      speak: false
    };
  }
  return {
    state: "storytelling",
    message: result.tutor_response || "Let us begin this little learning story.",
    animationEffect: "story_transition",
    speak: false
  };
}

export function avatarForPracticeResult(result: { is_correct: boolean; feedback: string; hint: string | null }): AvatarPayload {
  if (result.is_correct) {
    return { state: "celebrating", message: result.feedback, animationEffect: "star_burst", speak: false };
  }
  return {
    state: "encouraging",
    message: result.hint ? `${result.feedback} ${result.hint}` : result.feedback,
    animationEffect: "gentle_hint",
    speak: false
  };
}
