import type { Activity, ChildProfile, PathSummary, Stage } from "@/types";

export const linearAdventurePath = ["numbers", "alphabets", "colours", "shapes", "mixed_final"] as const;

export const pathAccents: Record<string, { icon: string; tone: string; soft: string; label: string }> = {
  numbers: { icon: "🔢", tone: "bg-sky text-white", soft: "bg-sky/10 text-sky", label: "Numbers" },
  alphabets: { icon: "🔠", tone: "bg-leaf text-white", soft: "bg-leaf/10 text-leaf", label: "Alphabets" },
  colours: { icon: "🌈", tone: "bg-berry text-white", soft: "bg-berry/10 text-berry", label: "Colours" },
  shapes: { icon: "🔺", tone: "bg-sunshine text-ink", soft: "bg-sunshine/20 text-ink", label: "Shapes" },
  mixed_final: { icon: "🏰", tone: "bg-ink text-white", soft: "bg-ink/10 text-ink", label: "Mixed Final" }
};

export const learningWorlds: Record<
  string,
  {
    name: string;
    shortName: string;
    realm: string;
    mascot: string;
    palette: string;
    sky: string;
    land: string;
    route: string;
    decoration: string;
    reward: string;
  }
> = {
  numbers: {
    name: "Number Kingdom",
    shortName: "Numbers",
    realm: "Count towers, apple orchards, and tiny treasure gates.",
    mascot: "🐼",
    palette: "from-sky/20 via-white to-sunshine/20",
    sky: "bg-sky/10",
    land: "bg-[#e8f7dc]",
    route: "bg-sky",
    decoration: "🏰 Castle",
    reward: "🏆 Number Crown"
  },
  alphabets: {
    name: "Alphabet Forest",
    shortName: "ABC",
    realm: "Follow letter leaves through a friendly forest trail.",
    mascot: "🦉",
    palette: "from-leaf/20 via-white to-sky/15",
    sky: "bg-leaf/10",
    land: "bg-[#eaf8ef]",
    route: "bg-leaf",
    decoration: "🌳 Treehouse",
    reward: "🌟 Letter Leaf"
  },
  colours: {
    name: "Colour Garden",
    shortName: "Colours",
    realm: "Collect bright petals and discover gentle colour magic.",
    mascot: "🦋",
    palette: "from-berry/20 via-white to-sunshine/20",
    sky: "bg-berry/10",
    land: "bg-[#fff1f5]",
    route: "bg-berry",
    decoration: "🌈 Rainbow Gate",
    reward: "💎 Garden Gem"
  },
  shapes: {
    name: "Shape Island",
    shortName: "Shapes",
    realm: "Cross bridges between round, pointy, and square islands.",
    mascot: "🐢",
    palette: "from-sunshine/25 via-white to-leaf/15",
    sky: "bg-sunshine/20",
    land: "bg-[#fff6de]",
    route: "bg-sunshine",
    decoration: "🌉 Island Bridge",
    reward: "🎁 Shape Shell"
  },
  mixed_final: {
    name: "Magic Castle",
    shortName: "Final",
    realm: "The final adventure opens after every learning world shines.",
    mascot: "🦄",
    palette: "from-lavender/25 via-white to-sky/20",
    sky: "bg-[#eeeaff]",
    land: "bg-[#f3f0ff]",
    route: "bg-ink",
    decoration: "🪄 Champion Gate",
    reward: "🏅 Explorer Medal"
  }
};

export const pathSummaries: PathSummary[] = [
  { path_id: "numbers", title: "Numbers Path", description: "Count, match, and meet friendly numbers.", total_stages: 8 },
  { path_id: "alphabets", title: "Alphabets Path", description: "Hear, spot, and play with early letters.", total_stages: 8 },
  { path_id: "colours", title: "Colours Path", description: "Find colours in toys, fruit, and pictures.", total_stages: 8 },
  { path_id: "shapes", title: "Shapes Path", description: "Explore circles, squares, triangles, and more.", total_stages: 8 },
  { path_id: "mixed_final", title: "Mixed Final Path", description: "A cheerful review that unlocks the certificate.", total_stages: 3 }
];

export const stageTokens = ["⭐", "🍎", "🏰", "🎈", "🌳", "🌉", "💎", "🏅"];

export const practiceCards = [
  { topic: "numbers", title: "Numbers Practice", icon: "🔢", description: "Count, match, and identify numbers." },
  { topic: "alphabets", title: "Alphabets Practice", icon: "🔠", description: "Spot friendly letters and beginning sounds." },
  { topic: "colours", title: "Colours Practice", icon: "🌈", description: "Pick colours from playful objects." },
  { topic: "shapes", title: "Shapes Practice", icon: "🔺", description: "Find circles, squares, and triangles." },
  { topic: "mixed", title: "Mixed Practice", icon: "🧩", description: "A tiny review across everything learned." }
];

export const localActivities: Record<string, Activity[]> = {
  numbers: [
    {
      activity_id: "numbers_guest_01",
      type: "count_objects",
      prompt: "How many apples are there?",
      visual_items: ["🍎", "🍎", "🍎"],
      options: ["2", "3", "4"],
      correct_answer: "3",
      hint: "Count each apple slowly.",
      difficulty: "easy"
    },
    {
      activity_id: "numbers_guest_02",
      type: "identify_number",
      prompt: "Pick the number 1.",
      visual_items: ["⭐"],
      options: ["1", "2", "5"],
      correct_answer: "1",
      hint: "One means a single thing.",
      difficulty: "easy"
    },
    {
      activity_id: "numbers_guest_03",
      type: "multiple_choice",
      prompt: "Two blocks and one more block make how many?",
      visual_items: ["🧩", "🧩", "🧩"],
      options: ["1", "3", "5"],
      correct_answer: "3",
      hint: "Touch each block: one, two, three.",
      difficulty: "easy"
    }
  ],
  alphabets: [
    {
      activity_id: "alphabets_guest_01",
      type: "identify_letter",
      prompt: "Which letter starts apple?",
      visual_items: ["🍎"],
      options: ["A", "B", "C"],
      correct_answer: "A",
      hint: "Apple begins with the sound A.",
      difficulty: "easy"
    }
  ],
  colours: [
    {
      activity_id: "colours_guest_01",
      type: "select_colour",
      prompt: "Choose red.",
      visual_items: ["🔴", "🔵", "🟡"],
      options: ["Red", "Blue", "Yellow"],
      correct_answer: "Red",
      hint: "Red looks like a strawberry.",
      difficulty: "easy"
    }
  ],
  shapes: [
    {
      activity_id: "shapes_guest_01",
      type: "select_shape",
      prompt: "Choose the circle.",
      visual_items: ["🔴", "🟦", "🔺"],
      options: ["Circle", "Square", "Triangle"],
      correct_answer: "Circle",
      hint: "A circle is round all the way around.",
      difficulty: "easy"
    }
  ],
  mixed: [
    {
      activity_id: "mixed_guest_01",
      type: "simple_mixed_activity",
      prompt: "Select the three red circles.",
      visual_items: ["🔴", "🔴", "🔴"],
      options: ["Three red circles", "Two blue squares", "One yellow triangle"],
      correct_answer: "Three red circles",
      hint: "Look for three round red shapes.",
      difficulty: "easy"
    }
  ]
};

export function localStages(pathId: string): Stage[] {
  const total = pathId === "mixed_final" ? 3 : 8;
  const label = pathAccents[pathId]?.label ?? "Learning";
  return Array.from({ length: total }, (_, index) => {
    const stageNumber = index + 1;
    const moduleType = stageNumber % 4 === 0 ? "story" : stageNumber % 3 === 0 ? "quiz" : stageNumber % 2 === 0 ? "activity" : "tutor";
    return {
      stage_id: `${pathId}_stage_${stageNumber}`,
      path_id: pathId,
      stage_number: stageNumber,
      title: stageNumber === 1 ? `Meet ${label}` : `${label} Stage ${stageNumber}`,
      objective: stageNumber === 1 ? `Start with a gentle ${label.toLowerCase()} activity.` : `Practice a small ${label.toLowerCase()} skill.`,
      module_type: moduleType,
      difficulty: "easy",
      intro_message: `Let us learn ${label.toLowerCase()} together.`,
      passing_score: 80,
      star_reward: pathId === "mixed_final" ? 8 : 5,
      activities: localActivities[pathId === "mixed_final" ? "mixed" : pathId] ?? localActivities.numbers,
      next_stage: stageNumber < total ? stageNumber + 1 : null
    };
  });
}

export function makeGuestChild(): ChildProfile {
  return {
    child_id: "guest_child",
    user_id: "guest",
    name: "Explorer",
    age_group: "Guest",
    age: null,
    learning_mode: "standard",
    preferred_language: "English",
    stars: 0,
    current_path: "numbers",
    current_stage: 1,
    completed_paths: [],
    path_progress: {
      numbers: { current_stage: 1, completed_stages: [], unlocked_stages: [1], score: 0 },
      alphabets: { current_stage: 1, completed_stages: [], unlocked_stages: [1], score: 0 },
      colours: { current_stage: 1, completed_stages: [], unlocked_stages: [1], score: 0 },
      shapes: { current_stage: 1, completed_stages: [], unlocked_stages: [1], score: 0 },
      mixed_final: { current_stage: 1, completed_stages: [], unlocked_stages: [], score: 0 }
    },
    weak_skills: [],
    rewards: ["⭐ Guest Star"],
    mixed_path_unlocked: false,
    certificate_unlocked: false
  };
}

export function seedFinalDemo(child: ChildProfile): ChildProfile {
  const seeded: ChildProfile = {
    ...child,
    stars: Math.max(child.stars, 72),
    completed_paths: ["numbers", "alphabets", "colours", "shapes"],
    mixed_path_unlocked: true,
    rewards: Array.from(new Set([...child.rewards, "🔢 Numbers Badge", "🔠 Alphabets Badge", "🌈 Colours Badge", "🔺 Shapes Badge"])),
    path_progress: {
      ...child.path_progress,
      numbers: { current_stage: 8, completed_stages: [1, 2, 3, 4, 5, 6, 7, 8], unlocked_stages: [1, 2, 3, 4, 5, 6, 7, 8], score: 100 },
      alphabets: { current_stage: 8, completed_stages: [1, 2, 3, 4, 5, 6, 7, 8], unlocked_stages: [1, 2, 3, 4, 5, 6, 7, 8], score: 100 },
      colours: { current_stage: 8, completed_stages: [1, 2, 3, 4, 5, 6, 7, 8], unlocked_stages: [1, 2, 3, 4, 5, 6, 7, 8], score: 100 },
      shapes: { current_stage: 8, completed_stages: [1, 2, 3, 4, 5, 6, 7, 8], unlocked_stages: [1, 2, 3, 4, 5, 6, 7, 8], score: 100 },
      mixed_final: { current_stage: 1, completed_stages: [], unlocked_stages: [1], score: 0 }
    }
  };
  return seeded;
}

export function guideAnswer(question: string): string {
  const normalized = question.toLowerCase();
  if (normalized.includes("practice")) return "Open Practice from the top bar, then choose Numbers, Alphabets, Colours, Shapes, or Mixed Practice.";
  if (normalized.includes("level") || normalized.includes("path") || normalized.includes("stage")) return "Open Levels, choose an unlocked path, and tap the bright current stage.";
  if (normalized.includes("star") || normalized.includes("reward")) return "Stars appear after good effort. Rewards and badges live on the Rewards page.";
  if (normalized.includes("certificate")) return "The certificate unlocks after the Mixed Final Path is completed.";
  if (normalized.includes("parent") || normalized.includes("dashboard")) return "Use Parent Profile in the top-right corner. Parent details appear after sign-up or login.";
  return "I can help you find Practice, Levels, Rewards, the certificate, and the Parent Profile.";
}
