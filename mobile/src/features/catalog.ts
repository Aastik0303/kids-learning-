import type { ToddlerModule } from "@/types/domain";

/**
 * The twelve showcased learning features (spec section 2).
 *
 * `pathId` links a feature to a real backend path where one exists; the rest
 * are flagged here rather than failing at runtime. Nothing on this screen
 * starts a lesson either way - what is taught is today's frozen plan's
 * decision, so every card leads to signing in.
 */

export type FeatureDefinition = {
  id: string;
  title: string;
  description: string;
  /** One line on how the AI teaches this, shown on the guest home. */
  aiHint: string;
  /** Backend `path_id`, when this feature maps to a real class. */
  pathId: string | null;
  /** Toddler module, when this feature exists in the toddler curriculum. */
  toddlerModule: ToddlerModule | null;
  /** Youngest age this is appropriate for. */
  minAge: number;
  /** What the child does in this kind of lesson. */
  interaction: "voice" | "tap" | "draw" | "listen";
};

export const FEATURES: FeatureDefinition[] = [
  {
    id: "alphabets",
    title: "Alphabets",
    description: "Meet every letter from A to Z.",
    aiHint: "I say the letter, you say it back",
    pathId: "alphabets",
    toddlerModule: "alphabets",
    minAge: 1,
    interaction: "voice",
  },
  {
    id: "numbers",
    title: "Numbers",
    description: "Count, spot and name numbers.",
    aiHint: "I count along with you",
    pathId: "numbers",
    toddlerModule: "numbers",
    minAge: 1,
    interaction: "tap",
  },
  {
    id: "shapes",
    title: "Shapes",
    description: "Circles, squares, triangles and more.",
    aiHint: "I point at the right shape",
    pathId: "shapes",
    toddlerModule: "shapes",
    minAge: 2,
    interaction: "tap",
  },
  {
    id: "colours",
    title: "Colours",
    description: "Learn every colour of the rainbow.",
    aiHint: "I show you colours one by one",
    pathId: "colours",
    toddlerModule: "colours",
    minAge: 1,
    interaction: "tap",
  },
  {
    id: "words",
    title: "Words",
    description: "Build your very first words.",
    aiHint: "I help you sound it out",
    pathId: null,
    toddlerModule: null,
    minAge: 3,
    interaction: "tap",
  },
  {
    id: "sentences",
    title: "Sentences",
    description: "Put words together and say them.",
    aiHint: "I read it, then you read it",
    pathId: null,
    toddlerModule: null,
    minAge: 4,
    interaction: "voice",
  },
  {
    id: "speaking",
    title: "Speaking",
    description: "Practise saying things out loud.",
    aiHint: "I listen and cheer you on",
    pathId: null,
    toddlerModule: null,
    minAge: 2,
    interaction: "voice",
  },
  {
    id: "drawing",
    title: "Drawing",
    description: "Draw anything you can imagine.",
    aiHint: "I give you fun things to draw",
    pathId: null,
    toddlerModule: null,
    minAge: 2,
    interaction: "draw",
  },
  {
    id: "tracing",
    title: "Tracing",
    description: "Trace letters, numbers and shapes.",
    aiHint: "I show you where to start",
    pathId: null,
    toddlerModule: null,
    minAge: 2,
    interaction: "draw",
  },
  {
    id: "practice",
    title: "Practice",
    description: "Go over the things you have learned.",
    aiHint: "I pick what you need most",
    pathId: null,
    toddlerModule: null,
    minAge: 3,
    interaction: "tap",
  },
  {
    id: "stories",
    title: "Stories",
    description: "Listen to gentle little stories.",
    aiHint: "I read the story to you",
    pathId: null,
    toddlerModule: null,
    minAge: 1,
    interaction: "listen",
  },
  {
    id: "rewards",
    title: "Rewards",
    description: "Collect stars and win your certificate.",
    aiHint: "I celebrate every win with you",
    pathId: null,
    toddlerModule: null,
    minAge: 1,
    interaction: "tap",
  },
];

export function featureById(id: string): FeatureDefinition | undefined {
  return FEATURES.find((feature) => feature.id === id);
}

/** Features appropriate for a given age, used to tailor the child's home. */
export function featuresForAge(age: number | null | undefined): FeatureDefinition[] {
  if (age === null || age === undefined) return FEATURES;
  return FEATURES.filter((feature) => feature.minAge <= age);
}

/** How the app works, in three beats — shown on the guest home. */
export const HOW_IT_WORKS = [
  {
    icon: "🐻",
    title: "Your guide says hello",
    body: "A friendly teacher greets your child and starts the lesson.",
  },
  {
    icon: "👀",
    title: "It shows and explains",
    body: "The guide points at things, gives examples and reads out loud.",
  },
  {
    icon: "⭐",
    title: "Your child answers",
    body: "By speaking, tapping or drawing — then earns stars.",
  },
] as const;

export const AGE_GROUPS = [
  {
    id: "toddler",
    label: "1 – 3 years",
    title: "Toddler mode",
    body: "One big thing at a time. Voice and tapping only.",
    icon: "🍼",
  },
  {
    id: "early",
    label: "3 – 5 years",
    title: "Early learner",
    body: "Classes, practice and rewards to explore.",
    icon: "🎒",
  },
] as const;

export const PARENT_BENEFITS = [
  { icon: "📊", title: "See real progress", body: "Stars, mastery and weak spots per child." },
  { icon: "🔒", title: "A safe space", body: "No ads, no chat with strangers, no data selling." },
  { icon: "⏱️", title: "You stay in control", body: "Set the age, language and session length." },
  { icon: "🏅", title: "A certificate", body: "Print it when your child finishes every path." },
] as const;
