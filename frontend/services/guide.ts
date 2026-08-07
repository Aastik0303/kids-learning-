import { api } from "@/services/api";
import type { Activity, ChildProfile, GuideRequest, GuideResponse } from "@/types";

export const GUIDE_TARGETS = {
  HOME_PRACTICE: "home-practice",
  START_PRACTICE: "start-practice",
  CONTINUE_ADVENTURE: "continue-adventure",
  CURRENT_LEVEL: "current-level",
  CURRENT_MAP_LEVEL: "current-map-level",
  QUESTION_AREA: "question-area",
  COUNTING_OBJECTS: "counting-object-group",
  ANSWER_OPTIONS: "answer-options",
  VOICE_ANSWER_AREA: "voice-answer-area",
  MICROPHONE_BUTTON: "microphone-button",
  REWARDS_BUTTON: "rewards-button",
  ASK_GUIDE: "ask-guide",
  PARENT_PROFILE: "parent-profile",
  OPEN_CERTIFICATE: "open-certificate",
  MORE_PRACTICE: "more-practice",
  OPEN_LEVELS: "open-levels"
} as const;

const SAFE_GUIDE_TARGETS = new Set<string>(Object.values(GUIDE_TARGETS));

export function isSafeGuideTarget(targetId: string | null | undefined) {
  return Boolean(targetId && SAFE_GUIDE_TARGETS.has(targetId));
}

export function activityQuestion(activity: Activity, overrides: Partial<NonNullable<GuideRequest["question"]>> = {}): GuideRequest["question"] {
  return {
    activity_id: activity.activity_id,
    topic: activity.type,
    concept: activity.type,
    prompt: activity.prompt,
    options: activity.options,
    correct_answer: activity.correct_answer,
    hint: activity.hint,
    attempt: 0,
    ...overrides
  };
}

export function progressContext(child: ChildProfile | null, currentWorld?: string | null, currentLevel?: string | null): GuideRequest["progress"] {
  return {
    current_world: currentWorld ?? child?.current_path ?? null,
    current_level: currentLevel ?? (child?.current_stage ? `Level ${child.current_stage}` : null),
    last_completed_level: null,
    weak_skills: child?.weak_skills ?? [],
    session_stars: child?.stars ?? 0
  };
}

export function guideAgent(payload: GuideRequest) {
  if (payload.child_id === "guest_child" || payload.child_id?.startsWith("local-child")) {
    return Promise.resolve(localGuide(payload));
  }

  return api<GuideResponse>("/agent/guide", {
    method: "POST",
    body: JSON.stringify(payload)
  }).catch(() => localGuide(payload));
}

function localGuide(payload: GuideRequest): GuideResponse {
  const prompt = payload.question?.prompt;
  const wrong = payload.event.endsWith("_ANSWER_INCORRECT") || payload.event === "HINT_REQUESTED";
  const complete = payload.event.endsWith("_COMPLETED") || payload.event === "CERTIFICATE_UNLOCKED";
  const message = wrong
    ? payload.question?.attempt === 2
      ? "Almost there! Count one by one, then say it again."
      : "Good try! Look closely and count slowly."
    : complete
      ? "Wonderful work! Tap the glowing button."
      : prompt
        ? `Look carefully. ${prompt} Say your answer after I finish.`
        : "I am your Little Learning guide. Tap the glowing button.";
  const target = payload.available_targets.find((item) => SAFE_GUIDE_TARGETS.has(item)) ?? null;
  return {
    message,
    strategy: wrong ? "hint" : complete ? "celebrate" : "read_question",
    avatar: { state: wrong ? "encouraging" : complete ? "celebrating" : "speaking", message, speak: true, animationEffect: wrong ? "gentle_hint" : complete ? "confetti" : "none" },
    ui_action: { type: target ? "highlight" : "none", target },
    next_expected_event: wrong ? "answer_submitted" : "wait_for_child"
  };
}
