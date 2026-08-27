import { api } from "@/services/api";
import { invalidate, shared, STATIC_MS } from "@/services/cache";
import type { ChildProfile, ClassDetail, ClassSummary, ExperienceMode, Subject, Topic } from "@/types";

export function listClasses() {
  return api<ClassSummary[]>("/curriculum/classes");
}

export function getExperienceMode(classId: string) {
  return shared(`curriculum:experience:${classId}`, () => api<ExperienceMode>(`/curriculum/classes/${classId}/experience`), STATIC_MS);
}

export function getSubject(subjectId: string) {
  return shared(`curriculum:subject:${subjectId}`, () => api<Subject>(`/curriculum/subjects/${subjectId}`), STATIC_MS);
}

export function getTopic(topicId: string) {
  return shared(`curriculum:topic:${topicId}`, () => api<Topic>(`/curriculum/topics/${topicId}`), STATIC_MS);
}

export function getClassForChild(childId: string) {
  // Not `STATIC_MS`: a parent moving the child up a class changes this, and
  // `setClassOverride` drops it. Sharing it briefly is only about the four
  // components that ask for it on the same render.
  return shared(`curriculum:child-class:${childId}`, () =>
    api<ClassDetail>(`/curriculum/children/${childId}/class`)
  );
}

/** Parent surface only. The child app never calls these two. */
export function getClassOptions(childId: string) {
  return api<ClassSummary[]>(`/curriculum/children/${childId}/class-options`);
}

export function setClassOverride(childId: string, session_token: string, class_id: string) {
  return api<ChildProfile>(`/curriculum/children/${childId}/class`, {
    method: "PUT",
    body: JSON.stringify({ session_token, class_id })
  }).then((child) => {
    // The child now has a different class, so everything read against the old
    // one - the class detail, the subject map - is wrong.
    invalidate("curriculum:");
    invalidate("children");
    return child;
  });
}
