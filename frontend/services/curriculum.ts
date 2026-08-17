import { api } from "@/services/api";
import type {
  Activity,
  ChildProfile,
  ClassDetail,
  ClassSummary,
  CurriculumOverview,
  ExperienceMode,
  Subject,
  Topic
} from "@/types";

export function getCurriculum() {
  return api<CurriculumOverview>("/curriculum");
}

export function listClasses() {
  return api<ClassSummary[]>("/curriculum/classes");
}

export function getClass(classId: string) {
  return api<ClassDetail>(`/curriculum/classes/${classId}`);
}

export function getExperienceMode(classId: string) {
  return api<ExperienceMode>(`/curriculum/classes/${classId}/experience`);
}

export function getSubject(subjectId: string) {
  return api<Subject>(`/curriculum/subjects/${subjectId}`);
}

export function getTopic(topicId: string) {
  return api<Topic>(`/curriculum/topics/${topicId}`);
}

export function getTopicActivities(topicId: string) {
  return api<Activity[]>(`/curriculum/topics/${topicId}/activities`);
}

export function getClassForChild(childId: string) {
  return api<ClassDetail>(`/curriculum/children/${childId}/class`);
}

/** Parent surface only. The child app never calls these two. */
export function getClassOptions(childId: string) {
  return api<ClassSummary[]>(`/curriculum/children/${childId}/class-options`);
}

export function setClassOverride(childId: string, session_token: string, class_id: string) {
  return api<ChildProfile>(`/curriculum/children/${childId}/class`, {
    method: "PUT",
    body: JSON.stringify({ session_token, class_id })
  });
}
