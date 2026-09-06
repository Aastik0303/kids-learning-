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
  error_fallback: 10,
  proud: 11,
  curious: 12,
  sad: 13
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

/**
 * What the panda's face is doing during a turn of the AI Teacher.
 *
 * The class is the one screen where a child cannot read anything, so the
 * avatar's face is a channel of its own: it reacts *while the feedback is being
 * said*, and settles into waiting once the talking stops. Splitting it that way
 * matters - a panda that stayed delighted for the whole of the next question
 * would be grinning at a child who is stuck on it.
 *
 * `speaking` is not a feeling and is not returned here. The mouth is driven
 * separately by `isSpeaking`, so the panda can be pleased *and* talking, which
 * is what it is doing most of the time.
 *
 * **A wrong answer never makes it sad.** It makes it kind: concerned eyebrows
 * and a small steady smile. `sad` is reserved for the app's own failures - the
 * microphone that heard nothing, the server that did not answer - because a
 * child who learns that missing a letter upsets the panda learns to stop
 * answering.
 */
export function avatarStateForTeacher(now: {
  speaking: boolean;
  listening: boolean;
  waiting: boolean;
  /** The app let the child down - not the other way round. */
  sorry: boolean;
  turn: {
    is_correct?: boolean | null;
    is_hint?: boolean;
    is_reveal?: boolean;
    is_retention_test?: boolean;
    topic_completed?: boolean;
    day_complete?: boolean;
    expects?: string;
  } | null;
}): AvatarState {
  if (now.sorry) return "sad";
  if (now.listening) return "listening";
  const turn = now.turn;
  if (!turn) return now.waiting ? "thinking" : "idle";
  if (turn.day_complete) return "proud";
  if (now.waiting) return "thinking";

  if (now.speaking) {
    if (turn.topic_completed) return "celebrating";
    if (turn.is_correct === true) return "happy";
    if (turn.is_correct === false) return "encouraging";
    if (turn.is_reveal) return "encouraging";
    if (turn.is_hint) return "thinking";
    if (turn.is_retention_test) return "curious";
    return "storytelling";
  }

  // Finished talking. Now it is the child's turn, and the face says so.
  if (turn.expects === "tap" || turn.expects === "voice") return "curious";
  return "idle";
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
