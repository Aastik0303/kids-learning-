import { api } from "@/services/api";
import { localActivities, practiceCards } from "@/data/prototype";
import { avatarForPracticeResult } from "@/services/avatar";
import type { Activity } from "@/types";
import type { AvatarPayload } from "@/components/avatar/avatar.types";

export type PracticeTopic = {
  topic: string;
  title: string;
  unlocked: boolean;
};

export function practiceTopics(childId: string) {
  return api<PracticeTopic[]>(`/practice/topics/${childId}`).catch(() =>
    practiceCards.map((card) => ({ topic: card.topic, title: card.title, unlocked: true }))
  );
}

export function startPractice(child_id: string, topic: string) {
  const localTopic = topic === "mixed_final" ? "mixed" : topic;
  if (child_id === "guest_child" || child_id.startsWith("local-child")) {
    return Promise.resolve({
      practice_session_id: `local-practice-${localTopic}`,
      topic: localTopic,
      activities: localActivities[localTopic] ?? localActivities.mixed,
      selection_reason: "introduced_skills"
    });
  }

  return api<{ practice_session_id: string; topic: string; activities: Activity[] }>("/practice/start", {
    method: "POST",
    body: JSON.stringify({ child_id, topic: localTopic === "mixed" ? "mixed_final" : topic })
  }).catch(() => ({
    practice_session_id: `local-practice-${localTopic}`,
    topic: localTopic,
    activities: localActivities[localTopic] ?? localActivities.mixed,
    selection_reason: "introduced_skills"
  }));
}

export type PracticeAnswerResult = { is_correct: boolean; feedback: string; hint: string | null; avatar?: AvatarPayload | null };

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

function localPracticeAnswer(activity_id: string, answer: string) {
  const activity = Object.values(localActivities).flat().find((item) => item.activity_id === activity_id);
  const isCorrect = normalizeLocalAnswer(activity?.correct_answer ?? "") === normalizeLocalAnswer(answer);
  const result = {
    is_correct: Boolean(isCorrect),
    feedback: isCorrect ? "Wonderful practice. Let us try the next one." : "Good try. Let us try together.",
    hint: isCorrect ? null : activity?.hint ?? "Look at each item slowly."
  };
  return { ...result, avatar: avatarForPracticeResult(result) };
}

export function answerPractice(practice_session_id: string, activity_id: string, answer: string) {
  if (practice_session_id.startsWith("local-practice-")) {
    return Promise.resolve(localPracticeAnswer(activity_id, answer));
  }

  return api<PracticeAnswerResult>("/practice/answer", {
    method: "POST",
    body: JSON.stringify({ practice_session_id, activity_id, answer })
  }).catch(() => localPracticeAnswer(activity_id, answer));
}
