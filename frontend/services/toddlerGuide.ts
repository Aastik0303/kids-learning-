import { guideAgent, progressContext, setActiveGuideContext } from "@/services/guide";
import type { ChildProfile, GuideEvent, GuideQuestionContext, GuideRequest, ToddlerActivity, ToddlerResponse } from "@/types";

export function toddlerQuestionContext(
  activity: ToddlerActivity,
  module: ToddlerResponse["module"],
  attempt = 0,
  childAnswer?: string
): GuideQuestionContext {
  return {
    activity_id: activity.activity_id,
    topic: module,
    concept: activity.concept,
    learning_objective: activity.speech,
    prompt: activity.prompt,
    answer_type: activity.type,
    options: activity.choices,
    correct_answer: activity.answer ?? activity.concept,
    child_answer: childAnswer ?? null,
    attempt,
    hint: activity.speech,
    visual_items: activity.visual_items,
    accepted_answers: [activity.answer, activity.concept, ...activity.accepted].filter((item): item is string => Boolean(item)),
    recent_answers: childAnswer ? [childAnswer] : [],
    difficulty: "toddler"
  };
}

export function toddlerStateContext(child: ChildProfile, lesson: ToddlerResponse, recognizedSpeech = ""): NonNullable<GuideRequest["toddler"]> {
  const activity = lesson.activity;
  return {
    learning_mode: "toddler",
    age: child.age,
    module: lesson.module,
    level: lesson.level,
    concept: activity?.concept ?? null,
    activity_type: activity?.type ?? null,
    expected_answer: activity?.answer ?? activity?.concept ?? null,
    recognized_speech: recognizedSpeech || lesson.evaluation?.heard || null,
    attempt_count: lesson.attempt_count,
    stars: lesson.total_stars,
    recent_result: lesson.evaluation?.result ?? null
  };
}

export function registerToddlerGuideContext(child: ChildProfile, lesson: ToddlerResponse | null) {
  if (!lesson?.activity) {
    setActiveGuideContext(null);
    return;
  }
  setActiveGuideContext({
    route: "/toddler",
    sessionId: lesson.session_id,
    screen: "toddler_lesson",
    topic: lesson.module,
    learningMode: "toddler",
    question: toddlerQuestionContext(lesson.activity, lesson.module, lesson.attempt_count),
    toddler: toddlerStateContext(child, lesson)
  });
}

export function requestToddlerGuide({
  child,
  lesson,
  event,
  recognizedSpeech = ""
}: {
  child: ChildProfile;
  lesson: ToddlerResponse;
  event: GuideEvent;
  recognizedSpeech?: string;
}) {
  const activity = lesson.activity;
  return guideAgent({
    session_id: lesson.session_id,
    child_id: child.child_id,
    mode: "learning",
    event,
    route: "/toddler",
    screen: "toddler_lesson",
    feature: lesson.module,
    age_group: child.age_group,
    age: child.age,
    learning_mode: "toddler",
    preferred_language: child.preferred_language,
    toddler: toddlerStateContext(child, lesson, recognizedSpeech),
    question: activity ? toddlerQuestionContext(activity, lesson.module, lesson.attempt_count, recognizedSpeech || undefined) : undefined,
    progress: progressContext(child, lesson.module, `Toddler level ${lesson.level}`),
    available_actions: ["highlight", "repeat_instruction", "show_hint"],
    available_targets: ["toddler-activity", "toddler-microphone", "toddler-choices"],
    allowed_visual_targets: activity?.visual_items.map((_, index) => `visual-item-${index}`) ?? []
  });
}
