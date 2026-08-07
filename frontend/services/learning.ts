import { api } from "@/services/api";
import { localStages, pathSummaries } from "@/data/prototype";
import { avatarForLearningResult } from "@/services/avatar";
import type { LearningResponse, PathSummary, Stage } from "@/types";
import { getChild, saveChild } from "./session";

const localLearningSessions = new Map<string, { child_id: string; path_id: string; stage_number: number; activity_index: number; attempts: number }>();

const numberWords: Record<string, string> = {
  zero: "0",
  one: "1",
  two: "2",
  three: "3",
  four: "4",
  five: "5",
  six: "6",
  seven: "7",
  eight: "8",
  nine: "9",
  ten: "10"
};

function normalizeLocalAnswer(answer: string) {
  const cleaned = answer.toLowerCase().replace(/[^\w\s]/g, " ").replace(/\s+/g, " ").trim();
  const tokens = cleaned.split(" ").filter((token) => !["the", "a", "an", "it", "is", "its", "number", "letter", "colour", "color", "please"].includes(token));
  const replaced = tokens.map((token) => numberWords[token] ?? token);
  return replaced.length === 1 ? replaced[0] : replaced.join(" ");
}

export function listPaths() {
  return api<PathSummary[]>("/learning/paths").catch(() => pathSummaries);
}

export function listStages(pathId: string) {
  return api<Stage[]>(`/learning/paths/${pathId}/stages`).catch(() => localStages(pathId));
}

export function startLearning(child_id: string, path_id: string, stage_number: number) {
  if (child_id === "guest_child" || child_id.startsWith("local-child")) {
    const stage = localStages(path_id).find((item) => item.stage_number === stage_number) ?? localStages(path_id)[0];
    const session_id = `local-learning-${path_id}-${stage_number}-${Date.now()}`;
    localLearningSessions.set(session_id, { child_id, path_id, stage_number, activity_index: 0, attempts: 0 });
    const tutor_response = stage.intro_message;
    return Promise.resolve({
      session_id,
      child_id,
      path_id,
      stage_number,
      tutor_response,
      activity: stage.activities[0],
      is_correct: null,
      attempt_number: 0,
      feedback: "",
      stars_earned: 0,
      current_score: 0,
      stage_completed: false,
      next_stage_unlocked: false,
      recommended_practice: false,
      complete: false,
      avatar: avatarForLearningResult({ is_correct: null, feedback: "", tutor_response })
    });
  }

  return api<LearningResponse>("/learning/start", {
    method: "POST",
    body: JSON.stringify({ child_id, path_id, stage_number })
  }).catch(() => {
    const stage = localStages(path_id).find((item) => item.stage_number === stage_number) ?? localStages(path_id)[0];
    const session_id = `local-learning-${path_id}-${stage_number}-${Date.now()}`;
    localLearningSessions.set(session_id, { child_id, path_id, stage_number, activity_index: 0, attempts: 0 });
    const tutor_response = stage.intro_message;
    return {
      session_id,
      child_id,
      path_id,
      stage_number,
      tutor_response,
      activity: stage.activities[0],
      is_correct: null,
      attempt_number: 0,
      feedback: "",
      stars_earned: 0,
      current_score: 0,
      stage_completed: false,
      next_stage_unlocked: false,
      recommended_practice: false,
      complete: false,
      avatar: avatarForLearningResult({ is_correct: null, feedback: "", tutor_response })
    };
  });
}

export function answerLearning(session_id: string, answer: string) {
  return api<LearningResponse>("/learning/answer", {
    method: "POST",
    body: JSON.stringify({ session_id, answer })
  }).catch(() => {
    const session = localLearningSessions.get(session_id);
    if (!session) throw new Error("This learning session needs to be started again.");
    const stage = localStages(session.path_id).find((item) => item.stage_number === session.stage_number) ?? localStages(session.path_id)[0];
    const activity = stage.activities[session.activity_index];
    const isCorrect = normalizeLocalAnswer(activity.correct_answer) === normalizeLocalAnswer(answer);
    const attempts = isCorrect ? 0 : session.attempts + 1;
    const nextIndex = isCorrect ? session.activity_index + 1 : session.activity_index;
    const complete = isCorrect && nextIndex >= stage.activities.length;
    const starsEarned = isCorrect ? (complete ? stage.star_reward : 1) : 0;
    const child = getChild();

    if (child && isCorrect) {
      const progress = child.path_progress[session.path_id] ?? { current_stage: 1, completed_stages: [], unlocked_stages: [1], score: 0 };
      const completedStages = complete ? Array.from(new Set([...progress.completed_stages, session.stage_number])) : progress.completed_stages;
      const nextStage = stage.next_stage;
      const unlockedStages = complete && nextStage ? Array.from(new Set([...progress.unlocked_stages, nextStage])) : progress.unlocked_stages;
      const allCoreDone = ["numbers", "alphabets", "colours", "shapes"].every((path) => {
        const pathProgress = path === session.path_id ? { ...progress, completed_stages: completedStages } : child.path_progress[path];
        return pathProgress?.completed_stages.length >= 8;
      });
      const finalComplete = session.path_id === "mixed_final" && complete;
      saveChild({
        ...child,
        stars: child.stars + starsEarned,
        rewards: complete ? Array.from(new Set([...child.rewards, `${stage.title} Badge`])) : child.rewards,
        completed_paths: complete && !stage.next_stage ? Array.from(new Set([...child.completed_paths, session.path_id])) : child.completed_paths,
        mixed_path_unlocked: child.mixed_path_unlocked || allCoreDone,
        certificate_unlocked: child.certificate_unlocked || finalComplete,
        path_progress: {
          ...child.path_progress,
          [session.path_id]: {
            ...progress,
            current_stage: nextStage && complete ? nextStage : session.stage_number,
            completed_stages: completedStages,
            unlocked_stages: unlockedStages,
            score: complete ? 100 : progress.score
          }
        }
      });
    }

    localLearningSessions.set(session_id, { ...session, activity_index: nextIndex, attempts });
    const feedback = isCorrect ? "Wonderful! You earned stars." : "Good try. " + activity.hint;
    const tutor_response = isCorrect ? "Great effort. Let us keep going." : attempts > 1 ? "Let us use a smaller example and try again." : "Almost there. Count slowly.";
    return {
      session_id,
      child_id: session.child_id,
      path_id: session.path_id,
      stage_number: session.stage_number,
      tutor_response,
      activity: complete ? null : stage.activities[nextIndex],
      is_correct: isCorrect,
      attempt_number: attempts,
      feedback,
      stars_earned: starsEarned,
      current_score: complete ? 100 : 0,
      stage_completed: complete,
      next_stage_unlocked: complete && Boolean(stage.next_stage),
      recommended_practice: !isCorrect && attempts >= 3,
      complete,
      avatar: avatarForLearningResult({
        is_correct: isCorrect,
        feedback,
        tutor_response,
        complete,
        next_stage_unlocked: complete && Boolean(stage.next_stage),
        recommended_practice: !isCorrect && attempts >= 3
      })
    };
  });
}
