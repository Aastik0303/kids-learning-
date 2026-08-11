import { api } from "@/services/api";
import { getChild, saveChild } from "@/services/session";
import type { LearningMode, ToddlerModule, ToddlerModuleSummary, ToddlerResponse } from "@/types";

export function resolveLearningMode(age: number) {
  return api<{ age: number; learning_mode: LearningMode }>("/toddler/mode", {
    method: "POST",
    body: JSON.stringify({ age })
  }).catch(() => ({ age, learning_mode: (age < 3 ? "toddler" : "standard") as LearningMode }));
}

export function listToddlerModules() {
  return api<ToddlerModuleSummary[]>("/toddler/modules").catch(() => [
    { module: "alphabets" as const, title: "ABC", icon: "🔤", levels: 2 },
    { module: "numbers" as const, title: "123", icon: "🔢", levels: 1 },
    { module: "colours" as const, title: "Colours", icon: "🎨", levels: 1 },
    { module: "shapes" as const, title: "Shapes", icon: "⭐", levels: 1 }
  ] satisfies ToddlerModuleSummary[]);
}

export function startToddlerLesson(child_id: string, module: ToddlerModule, level = 1, practice = false) {
  if (child_id === "guest_child" || child_id.startsWith("local-child")) {
    return Promise.resolve(localToddlerStart(child_id, module, level));
  }
  return api<ToddlerResponse>("/toddler/start", {
    method: "POST",
    body: JSON.stringify({ child_id, module, level, practice })
  }).catch(() => localToddlerStart(child_id, module, level));
}

export function answerToddlerLesson(session_id: string, answer: string, recognized_speech = answer) {
  if (session_id.startsWith("local-toddler")) return Promise.resolve(localToddlerAnswer(session_id, answer, recognized_speech));
  return api<ToddlerResponse>("/toddler/answer", {
    method: "POST",
    body: JSON.stringify({ session_id, answer, recognized_speech })
  }).catch(() => localToddlerAnswer(session_id, answer, recognized_speech));
}

const localSessions = new Map<string, { child_id: string; module: ToddlerModule; index: number; attempts: number; learned: string[] }>();

const localActivities = {
  alphabets: [
    { activity_id: "local-a-intro", type: "introduce" as const, prompt: "Look! This is A.", speech: "This is A. A is for Apple.", concept: "A", emoji: "🍎", word: "Apple", visual_items: ["A", "🍎"], choices: [], answer: "A", accepted: ["a", "ay", "hey"] },
    { activity_id: "local-a-repeat", type: "repeat_after_me" as const, prompt: "Can you say A?", speech: "Say A.", concept: "A", emoji: "🎤", visual_items: [], choices: [], answer: "A", accepted: ["a", "ay", "hey"] },
    { activity_id: "local-b-find", type: "recognition" as const, prompt: "Can you find B?", speech: "Tap B.", concept: "B", emoji: "🔤", visual_items: [], choices: ["A", "B", "C"], answer: "B", accepted: ["b", "bee"] }
  ],
  numbers: [
    { activity_id: "local-num-1", type: "introduce" as const, prompt: "Look! One apple.", speech: "This is one.", concept: "1", emoji: "🍎", visual_items: ["1", "🍎"], choices: [], answer: "1", accepted: ["1", "one"] },
    { activity_id: "local-num-2", type: "recognition" as const, prompt: "Can you find 2?", speech: "Tap 2.", concept: "2", emoji: "🔢", visual_items: [], choices: ["1", "2", "3"], answer: "2", accepted: ["2", "two", "too"] }
  ],
  colours: [
    { activity_id: "local-red-intro", type: "introduce" as const, prompt: "This is red.", speech: "This is red.", concept: "Red", emoji: "🔴", visual_items: ["🔴"], choices: [], answer: "Red", accepted: ["red"] },
    { activity_id: "local-red-repeat", type: "repeat_after_me" as const, prompt: "Can you say red?", speech: "Say red.", concept: "Red", emoji: "🎤", visual_items: [], choices: [], answer: "Red", accepted: ["red"] },
    { activity_id: "local-red-find", type: "recognition" as const, prompt: "Which one is red?", speech: "Tap red.", concept: "Red", emoji: "🔴", visual_items: [], choices: ["🔴", "🟡", "🔵"], answer: "🔴", accepted: ["red"] },
    { activity_id: "local-yellow-intro", type: "introduce" as const, prompt: "This is yellow.", speech: "Yellow shines like the sun.", concept: "Yellow", emoji: "🟡", visual_items: ["🟡"], choices: [], answer: "Yellow", accepted: ["yellow"] },
    { activity_id: "local-yellow-repeat", type: "repeat_after_me" as const, prompt: "Can you say yellow?", speech: "Say yellow.", concept: "Yellow", emoji: "🎤", visual_items: [], choices: [], answer: "Yellow", accepted: ["yellow"] },
    { activity_id: "local-yellow-find", type: "recognition" as const, prompt: "Which one is yellow?", speech: "Tap yellow.", concept: "Yellow", emoji: "🟡", visual_items: [], choices: ["🔵", "🟡", "🔴"], answer: "🟡", accepted: ["yellow"] },
    { activity_id: "local-blue-intro", type: "introduce" as const, prompt: "This is blue.", speech: "Blue looks like the sky.", concept: "Blue", emoji: "🔵", visual_items: ["🔵"], choices: [], answer: "Blue", accepted: ["blue"] },
    { activity_id: "local-blue-repeat", type: "repeat_after_me" as const, prompt: "Can you say blue?", speech: "Say blue.", concept: "Blue", emoji: "🎤", visual_items: [], choices: [], answer: "Blue", accepted: ["blue"] },
    { activity_id: "local-blue-find", type: "recognition" as const, prompt: "Which one is blue?", speech: "Tap blue.", concept: "Blue", emoji: "🔵", visual_items: [], choices: ["🟡", "🔴", "🔵"], answer: "🔵", accepted: ["blue"] }
  ],
  shapes: [
    { activity_id: "local-star", type: "recognition" as const, prompt: "Can you find the star?", speech: "Tap the star.", concept: "Star", emoji: "⭐", visual_items: [], choices: ["⭕", "⬜", "⭐"], answer: "⭐", accepted: ["star"] }
  ]
};

function localToddlerStart(child_id: string, module: ToddlerModule, level: number): ToddlerResponse {
  const session_id = `local-toddler-${module}-${Date.now()}`;
  localSessions.set(session_id, { child_id, module, index: 0, attempts: 0, learned: [] });
  const activity = localActivities[module][0];
  return toddlerResponse(session_id, child_id, module, level, activity, "Hi! 👋 Let's learn.", "happy");
}

function localToddlerAnswer(session_id: string, answer: string, recognized_speech: string): ToddlerResponse {
  const session = localSessions.get(session_id);
  if (!session) throw new Error("Let us start this little lesson again.");
  const activity = localActivities[session.module][session.index];
  const expected = activity.answer ?? activity.concept;
  const heard = (recognized_speech || answer).trim();
  const correct = activity.type === "introduce" || heard === expected || activity.accepted.some((item) => item.toLowerCase() === heard.toLowerCase());
  if (!correct) {
    session.attempts += 1;
    if (session.attempts >= 4) {
      session.attempts = 0;
      session.index = (session.index + 1) % localActivities[session.module].length;
      const nextActivity = localActivities[session.module][session.index];
      return toddlerResponse(session_id, session.child_id, session.module, 1, nextActivity, "Let's try a different little question.", "encouraging", 0, {
        result: "retry",
        confidence: 0,
        expected,
        heard,
        retry: true
      }, false, true);
    }
    return toddlerResponse(session_id, session.child_id, session.module, 1, activity, `Almost! 😊 Let's try ${activity.concept} again.`, "gentle_retry", 0, {
      result: heard ? "retry" : "unclear",
      confidence: 0,
      expected,
      heard,
      retry: true
    });
  }
  session.attempts = 0;
  const child = getChild();
  if (child) saveChild({ ...child, stars: child.stars + 1 });
  session.learned = Array.from(new Set([...session.learned, activity.concept]));
  session.index += 1;
  const next = localActivities[session.module][session.index];
  if (!next) {
    return toddlerResponse(session_id, session.child_id, session.module, 1, null, "Wow! You did it! 🌟", "celebrate", 3, {
      result: "correct",
      confidence: 1,
      expected,
      heard,
      retry: false
    }, true);
  }
  return toddlerResponse(session_id, session.child_id, session.module, 1, next, "Yay! Great job! ⭐", "celebrate", 1, {
    result: "correct",
    confidence: 1,
    expected,
    heard,
    retry: false
  });
}

function toddlerResponse(
  session_id: string,
  child_id: string,
  module: ToddlerModule,
  level: number,
  activity: ToddlerResponse["activity"],
  speech: string,
  emotion: ToddlerResponse["guide"]["emotion"],
  stars_earned = 0,
  evaluation: ToddlerResponse["evaluation"] = null,
  level_completed = false,
  question_changed = false
): ToddlerResponse {
  const child = getChild();
  const session = localSessions.get(session_id);
  return {
    session_id,
    child_id,
    module,
    level,
    activity,
    guide: { speech, emotion, emoji: emotion === "celebrate" ? "⭐" : "😊", action: level_completed ? "complete_level" : "next_activity", repeat: emotion === "gentle_retry", target: activity?.answer ?? null },
    evaluation,
    stars_earned,
    total_stars: child?.stars ?? 0,
    attempt_count: session?.attempts ?? 0,
    completed_activities: session?.learned ?? [],
    level_completed,
    next_level_unlocked: false,
    question_changed,
    learned_concepts: session?.learned ?? [],
    avatar: { state: emotion === "celebrate" ? "celebrating" : emotion === "gentle_retry" ? "encouraging" : "happy", message: speech, speak: true, animationEffect: emotion === "celebrate" ? "star_burst" : "none" }
  };
}
