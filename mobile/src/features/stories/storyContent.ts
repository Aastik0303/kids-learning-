import type { RenderableActivity } from "@/types/activity";

/**
 * Local story content.
 *
 * The backend has no story endpoint yet, so these live on the device and
 * flow through the standard ActivityRenderer contract. When a `/stories`
 * API arrives, only the source changes — every consumer already speaks
 * `RenderableActivity`.
 *
 * Copy rules: short sentences, gentle subject matter, no peril, no loss.
 */

export type Story = {
  id: string;
  title: string;
  cover: string;
  minAge: number;
  activities: RenderableActivity[];
};

function page(id: string, text: string, glyph: string): RenderableActivity {
  return {
    id,
    kind: "story_listen",
    answerMode: "none",
    prompt: text,
    speech: text,
    visualItems: [],
    options: [],
    correctAnswer: "",
    acceptedAnswers: [],
    hint: "",
    difficulty: "easy",
    concept: "story",
    glyph,
    source: "local",
  };
}

function question(
  id: string,
  prompt: string,
  options: string[],
  answer: string,
): RenderableActivity {
  return {
    id,
    kind: "tap_choice",
    answerMode: "tap",
    prompt,
    speech: prompt,
    visualItems: [],
    options,
    correctAnswer: answer,
    acceptedAnswers: [answer],
    hint: "Think about the story!",
    difficulty: "easy",
    concept: answer,
    glyph: "❓",
    source: "local",
  };
}

export const STORIES: Story[] = [
  {
    id: "red-balloon",
    title: "The Red Balloon",
    cover: "🎈",
    minAge: 1,
    activities: [
      page(
        "balloon-1",
        "Once there was a little bear. The bear found a big red balloon.",
        "🐻",
      ),
      page("balloon-2", "The balloon floated up and up. The bear laughed and laughed.", "🎈"),
      page("balloon-3", "Then the wind blew. The balloon came right back to the bear.", "🌬️"),
      question("balloon-q", "What colour was the balloon?", ["Red", "Blue", "Green"], "Red"),
      page("balloon-4", "The bear held the balloon tight and walked home. What a happy day!", "🏡"),
    ],
  },
  {
    id: "counting-ducks",
    title: "Five Little Ducks",
    cover: "🦆",
    minAge: 2,
    activities: [
      page("ducks-1", "Five little ducks went out to play. They splashed in the warm blue pond.", "🦆"),
      page("ducks-2", "One duck found a shiny stone. Two ducks found a soft green leaf.", "🪨"),
      question("ducks-q", "How many little ducks were there?", ["Three", "Four", "Five"], "Five"),
      page("ducks-3", "All five ducks swam home together. Quack, quack, quack!", "🌊"),
    ],
  },
  {
    id: "shape-town",
    title: "Shape Town",
    cover: "🔺",
    minAge: 3,
    activities: [
      page("shapes-1", "In Shape Town, the houses are squares. The roofs are triangles.", "🏠"),
      page("shapes-2", "The sun is a big yellow circle. It smiles down on everyone.", "☀️"),
      question(
        "shapes-q",
        "What shape is the sun?",
        ["Circle", "Square", "Triangle"],
        "Circle",
      ),
      page("shapes-3", "Everyone in Shape Town waves goodbye. See you soon!", "👋"),
    ],
  },
];

export function storyById(id: string): Story | undefined {
  return STORIES.find((story) => story.id === id);
}

export function storiesForAge(age: number | null | undefined): Story[] {
  if (age === null || age === undefined) return STORIES;
  return STORIES.filter((story) => story.minAge <= age);
}
