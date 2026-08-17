import { api } from "@/services/api";
import { getChild } from "@/services/session";
import type { Activity, ChildProfile, GuideQuestionContext, GuideRequest, GuideResponse } from "@/types";

type ActiveGuideContext = {
  route: string;
  sessionId?: string;
  screen?: string;
  topic?: string;
  experienceMode?: string;
  question?: GuideQuestionContext | null;
};

let activeGuideContext: ActiveGuideContext | null = null;

export function setActiveGuideContext(context: ActiveGuideContext | null) {
  activeGuideContext = context;
}

export const GUIDE_TARGETS = {
  HOME_PRACTICE: "home-practice",
  START_PRACTICE: "start-practice",
  CONTINUE_ADVENTURE: "continue-adventure",
  SUBJECT_CARD: "subject-card",
  TOPIC_CARD: "topic-card",
  ACTIVITY_AREA: "activity-area",
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
  OPEN_SUBJECTS: "open-subjects",
  ADVENTURE_HOME: "adventure-home"
} as const;

const SAFE_GUIDE_TARGETS = new Set<string>(Object.values(GUIDE_TARGETS));

const SECOND_TRY_ENCOURAGEMENTS = [
  "Good try! You can do it. Give it another go!",
  "Almost! Take your time and try once more.",
  "Nice effort! I know you can do this.",
  "So close! Trust yourself and try again.",
  "Keep going! Your next try could be the one.",
  "Great effort! Have another go when you are ready."
];

export function secondTryEncouragement() {
  return SECOND_TRY_ENCOURAGEMENTS[Math.floor(Math.random() * SECOND_TRY_ENCOURAGEMENTS.length)];
}

export function isSafeGuideTarget(targetId: string | null | undefined) {
  return Boolean(targetId && SAFE_GUIDE_TARGETS.has(targetId));
}

export function activityQuestion(activity: Activity, overrides: Partial<NonNullable<GuideRequest["question"]>> = {}): GuideRequest["question"] {
  return {
    activity_id: activity.activity_id,
    topic: activity.type,
    concept: activity.type,
    learning_objective: activity.hint,
    prompt: activity.prompt,
    answer_type: activity.type,
    options: activity.options,
    correct_answer: activity.correct_answer,
    hint: activity.hint,
    visual_items: activity.visual_items,
    // What a writing activity asks the child to draw. Without it the guide can
    // only see the type "trace" and has nothing to name.
    example: activity.trace_target ?? undefined,
    accepted_answers: activity.correct_answer ? [activity.correct_answer, ...(activity.accept ?? [])] : [],
    recent_answers: [],
    difficulty: activity.difficulty,
    attempt: 0,
    ...overrides
  };
}

export function visualTargetsForActivity(activity: Activity) {
  return activity.visual_items.map((_, index) => `visual-item-${index}`);
}

export function progressContext(child: ChildProfile | null, currentSubject?: string | null, currentTopic?: string | null): GuideRequest["progress"] {
  return {
    current_class: child?.class_id ?? null,
    current_subject: currentSubject ?? child?.current_subject_id ?? null,
    current_topic: currentTopic ?? child?.current_topic_id ?? null,
    last_completed_topic: null,
    weak_skills: child?.weak_skills ?? [],
    session_stars: child?.stars ?? 0
  };
}

export function guideAgent(payload: GuideRequest) {
  return api<GuideResponse>("/agent/guide", {
    method: "POST",
    body: JSON.stringify(payload)
  }).catch(() => localGuide(payload));
}

export function askGuideQuestion({
  question,
  route,
  conversation = [],
  sessionId,
  screen,
  activity,
  questionContext,
  experienceMode,
  topic,
  attempt = 0
}: {
  question: string;
  route: string;
  conversation?: NonNullable<GuideRequest["conversation"]>;
  sessionId?: string;
  screen?: string;
  activity?: Activity;
  questionContext?: GuideQuestionContext;
  experienceMode?: string;
  topic?: string;
  attempt?: number;
}) {
  const child = getChild();
  const activeContext = activeGuideContext?.route === route ? activeGuideContext : null;
  const contextualQuestion = activity
    ? activityQuestion(activity, {
        topic: topic ?? activity.type,
        concept: activity.type,
        child_answer: question.trim(),
        recent_answers: [question.trim()],
        attempt
      })
    : questionContext ?? activeContext?.question ?? undefined;
  const earlyMode = (experienceMode ?? activeContext?.experienceMode ?? child?.experience_mode ?? "standard") === "early";
  const contextualTargets = earlyMode
    ? [GUIDE_TARGETS.ACTIVITY_AREA, GUIDE_TARGETS.ANSWER_OPTIONS, GUIDE_TARGETS.MICROPHONE_BUTTON]
    : [GUIDE_TARGETS.COUNTING_OBJECTS, GUIDE_TARGETS.QUESTION_AREA, GUIDE_TARGETS.VOICE_ANSWER_AREA, GUIDE_TARGETS.MICROPHONE_BUTTON];
  return guideAgent({
    session_id: sessionId ?? activeContext?.sessionId ?? `guide_${Date.now()}`,
    child_id: child?.child_id ?? null,
    mode: "help",
    event: "GUIDE_HELP_REQUESTED",
    route,
    screen: screen ?? activeContext?.screen ?? (route === "/guide" ? "guide_help" : "learning_app"),
    feature: question.trim(),
    class_id: child?.class_id ?? null,
    experience_mode: earlyMode ? "early" : "standard",
    preferred_language: child?.preferred_language ?? "English",
    conversation: conversation.slice(-8),
    question: contextualQuestion
      ? { ...contextualQuestion, child_answer: question.trim(), recent_answers: [question.trim()], attempt }
      : undefined,
    progress: progressContext(child, topic ?? activeContext?.topic),
    allowed_visual_targets: contextualQuestion?.visual_items?.map((_, index) => `visual-item-${index}`) ?? [],
    available_actions: contextualQuestion ? ["highlight", "show_hint", "repeat_instruction"] : ["none"],
    available_targets: contextualQuestion ? contextualTargets : []
  });
}

function localTeachingStep(payload: GuideRequest) {
  const question = payload.question;
  const targets = payload.allowed_visual_targets ?? [];
  if (!question) return { message: localHelpMessage(payload.feature, payload), type: "none" as const, targets: [] as string[] };
  const answerType = (question.answer_type ?? question.topic ?? "").toLowerCase();
  const counting = answerType.includes("count") || answerType.includes("number") || /count|how many/i.test(question.prompt);
  if (counting) {
    const firstItem = question.visual_items?.[0] ?? "object";
    const item = /^[\x00-\x7F]+$/.test(firstItem) ? firstItem : "item";
    const numberWords = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];
    const count = question.visual_items?.length ?? 0;
    const sequence = Array.from({ length: count }, (_, index) => numberWords[index + 1] ?? String(index + 1)).join(", ");
    const total = numberWords[count] ?? String(count);
    return {
      message: count ? `Let's count together: ${sequence}. There are ${total}. Watch each ${item} light up.` : "Let's count one item at a time.",
      type: targets.length > 1 ? "highlight_sequence" as const : "pulse" as const,
      targets
    };
  }
  return {
    message: `Let's look together. ${question.hint || question.learning_objective || question.prompt}`,
    type: "highlight" as const,
    targets
  };
}

function localHelpMessage(question: string, payload: GuideRequest) {
  const normalized = question.toLowerCase().trim();
  const arithmetic = normalized.match(/(?:what is|what's|solve)?\s*(\d{1,2})\s*([+\-])\s*(\d{1,2})/);
  if (arithmetic) {
    const left = Number(arithmetic[1]);
    const right = Number(arithmetic[3]);
    const answer = arithmetic[2] === "+" ? left + right : left - right;
    return `${left} ${arithmetic[2] === "+" ? "plus" : "minus"} ${right} is ${answer}.`;
  }
  if (/\b(hi|hello|hey)\b/.test(normalized)) return "Hello! What would you like to learn today?";
  if (normalized.includes("practice")) return "Open Practice, then choose Numbers, Alphabets, Colours, Shapes, or Mixed Practice.";
  if (normalized.includes("level") || normalized.includes("path") || normalized.includes("stage")) return "Open Adventure and tap the bright unlocked level on your learning path.";
  if (normalized.includes("star") || normalized.includes("reward")) return `You have ${payload.progress?.session_stars ?? 0} stars. Open Rewards to see your badges and prizes.`;
  if (normalized.includes("certificate")) return "Your certificate unlocks after you complete the Mixed Final Path.";
  if (normalized.includes("circle")) return "A circle is round all the way around and has no corners.";
  if (normalized.includes("square")) return "A square has four equal sides and four corners.";
  if (normalized.includes("triangle")) return "A triangle has three sides and three corners.";
  if (normalized.includes("alphabet") || normalized.includes("letter")) return "Letters make words. Try asking me about one letter, like: What sound does A make?";
  if (normalized.includes("number") || normalized.includes("count")) return "I can help you count. Tell me which objects or numbers you want to count.";
  if (normalized.includes("colour") || normalized.includes("color")) return "I can help with colours. Ask me about a colour you see.";
  if (normalized.includes("parent") || normalized.includes("login")) return "Tap Parent Login at the top of the screen to open the parent area.";
  if (payload.question?.hint || payload.question?.learning_objective) {
    const asksForHelp = /\b(help|understand|explain|what|why|how|repeat|confused)\b/.test(normalized);
    const prefix = asksForHelp ? "No problem. Let's try together." : "I heard you, but that does not answer this question yet.";
    return `${prefix} ${payload.question.hint || payload.question.learning_objective}`;
  }
  if (payload.question?.prompt) return `No problem. Let's look together. ${payload.question.prompt}`;
  return "I can help with numbers, letters, colours, shapes, and using this app. Ask me one short question.";
}

function localGuide(payload: GuideRequest): GuideResponse {
  const prompt = payload.question?.prompt;
  const wrong = payload.event.endsWith("_ANSWER_INCORRECT") || payload.event === "HINT_REQUESTED";
  const secondTry = payload.event.endsWith("_ANSWER_INCORRECT") && payload.question?.attempt === 1;
  const complete = payload.event.endsWith("_COMPLETED") || payload.event === "CERTIFICATE_UNLOCKED";
  const needsTeachingStep = Boolean(payload.question && !secondTry && (wrong || payload.event === "GUIDE_HELP_REQUESTED"));
  const teachingStep = localTeachingStep(payload);
  const message = payload.event === "GUIDE_HELP_REQUESTED"
    ? needsTeachingStep ? teachingStep.message : localHelpMessage(payload.feature, payload)
    : wrong
    ? secondTry
      ? secondTryEncouragement()
      : payload.question?.attempt === 2
      ? "Almost there! Count one by one, then say it again."
      : "Good try! Look closely and count slowly."
    : complete
      ? "Wonderful work! Tap the glowing button."
      : prompt
        ? `Look carefully. ${prompt} Say your answer after I finish.`
        : "I am your Saksham IQ guide. Tap the glowing button.";
  const target = secondTry
    ? payload.available_targets.find((item) => item !== GUIDE_TARGETS.COUNTING_OBJECTS && SAFE_GUIDE_TARGETS.has(item)) ?? null
    : payload.available_targets.find((item) => SAFE_GUIDE_TARGETS.has(item)) ?? null;
  return {
    message,
    strategy: wrong ? "hint" : complete ? "celebrate" : "read_question",
    avatar: { state: wrong ? "encouraging" : complete ? "celebrating" : "speaking", message, speak: true, animationEffect: wrong ? "gentle_hint" : complete ? "confetti" : "none" },
    ui_action: { type: target ? "highlight" : "none", target },
    visual_action: needsTeachingStep ? { type: teachingStep.type, targets: teachingStep.targets } : { type: "none", targets: [] },
    next_expected_event: wrong ? "answer_submitted" : "wait_for_child"
  };
}
