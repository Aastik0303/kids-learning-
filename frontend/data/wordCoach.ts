export type CoachWord = {
  id: string;
  word: string;
  hindi: string;
  spokenHindi: string;
  emoji: string;
};

export const coachWords: CoachWord[] = [
  { id: "apple", word: "Apple", hindi: "सेब", spokenHindi: "seb", emoji: "🍎" },
  { id: "ball", word: "Ball", hindi: "गेंद", spokenHindi: "gend", emoji: "⚽" },
  { id: "cat", word: "Cat", hindi: "बिल्ली", spokenHindi: "billi", emoji: "🐱" },
  { id: "dog", word: "Dog", hindi: "कुत्ता", spokenHindi: "kutta", emoji: "🐶" },
  { id: "sun", word: "Sun", hindi: "सूरज", spokenHindi: "suraj", emoji: "☀️" },
  { id: "moon", word: "Moon", hindi: "चाँद", spokenHindi: "chaand", emoji: "🌙" },
  { id: "water", word: "Water", hindi: "पानी", spokenHindi: "paani", emoji: "💧" },
  { id: "book", word: "Book", hindi: "किताब", spokenHindi: "kitaab", emoji: "📘" },
  { id: "flower", word: "Flower", hindi: "फूल", spokenHindi: "phool", emoji: "🌼" },
  { id: "house", word: "House", hindi: "घर", spokenHindi: "ghar", emoji: "🏠" },
  { id: "tree", word: "Tree", hindi: "पेड़", spokenHindi: "ped", emoji: "🌳" },
  { id: "bird", word: "Bird", hindi: "चिड़िया", spokenHindi: "chidiya", emoji: "🐦" },
  { id: "fish", word: "Fish", hindi: "मछली", spokenHindi: "machhli", emoji: "🐟" },
  { id: "milk", word: "Milk", hindi: "दूध", spokenHindi: "doodh", emoji: "🥛" },
  { id: "friend", word: "Friend", hindi: "दोस्त", spokenHindi: "dost", emoji: "🤝" },
  { id: "happy", word: "Happy", hindi: "खुश", spokenHindi: "khush", emoji: "😊" }
];

export function spellWord(word: string) {
  return word.toUpperCase().split("");
}
