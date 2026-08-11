export type SentenceWord = {
  text: string;
  hindi: string;
};

export type SentenceLesson = {
  id: string;
  sentence: string;
  hindi: string;
  spokenHindi: string;
  explanation: string;
  emoji: string;
  words: SentenceWord[];
};

export const sentenceLessons: SentenceLesson[] = [
  {
    id: "dog-food",
    sentence: "The dog eats his food.",
    hindi: "कुत्ता अपना खाना खाता है।",
    spokenHindi: "Kutta apna khaana khaata hai.",
    explanation: "A dog is eating its meal.",
    emoji: "🐶🥣",
    words: [
      { text: "The", hindi: "वह" },
      { text: "dog", hindi: "कुत्ता" },
      { text: "eats", hindi: "खाता है" },
      { text: "his", hindi: "अपना" },
      { text: "food", hindi: "खाना" }
    ]
  },
  {
    id: "red-ball",
    sentence: "I see a red ball.",
    hindi: "मुझे एक लाल गेंद दिखती है।",
    spokenHindi: "Mujhe ek laal gend dikhti hai.",
    explanation: "I can see a ball that is red.",
    emoji: "👀🔴",
    words: [
      { text: "I", hindi: "मैं" },
      { text: "see", hindi: "देखता हूँ" },
      { text: "a", hindi: "एक" },
      { text: "red", hindi: "लाल" },
      { text: "ball", hindi: "गेंद" }
    ]
  },
  {
    id: "cat-milk",
    sentence: "The cat drinks milk.",
    hindi: "बिल्ली दूध पीती है।",
    spokenHindi: "Billi doodh peeti hai.",
    explanation: "A cat is drinking milk.",
    emoji: "🐱🥛",
    words: [
      { text: "The", hindi: "वह" },
      { text: "cat", hindi: "बिल्ली" },
      { text: "drinks", hindi: "पीती है" },
      { text: "milk", hindi: "दूध" }
    ]
  },
  {
    id: "play-park",
    sentence: "We play in the park.",
    hindi: "हम पार्क में खेलते हैं।",
    spokenHindi: "Hum park mein khelte hain.",
    explanation: "We are having fun together in the park.",
    emoji: "🛝⚽",
    words: [
      { text: "We", hindi: "हम" },
      { text: "play", hindi: "खेलते हैं" },
      { text: "in", hindi: "में" },
      { text: "the", hindi: "उस" },
      { text: "park", hindi: "पार्क" }
    ]
  },
  {
    id: "blue-book",
    sentence: "This is my blue book.",
    hindi: "यह मेरी नीली किताब है।",
    spokenHindi: "Yeh meri neeli kitaab hai.",
    explanation: "The blue book belongs to me.",
    emoji: "📘👧",
    words: [
      { text: "This", hindi: "यह" },
      { text: "is", hindi: "है" },
      { text: "my", hindi: "मेरी" },
      { text: "blue", hindi: "नीली" },
      { text: "book", hindi: "किताब" }
    ]
  },
  {
    id: "bright-sun",
    sentence: "The sun is bright.",
    hindi: "सूरज चमकीला है।",
    spokenHindi: "Suraj chamkeela hai.",
    explanation: "The sun gives us strong light.",
    emoji: "☀️✨",
    words: [
      { text: "The", hindi: "वह" },
      { text: "sun", hindi: "सूरज" },
      { text: "is", hindi: "है" },
      { text: "bright", hindi: "चमकीला" }
    ]
  },
  {
    id: "bird-fly",
    sentence: "A bird can fly.",
    hindi: "एक चिड़िया उड़ सकती है।",
    spokenHindi: "Ek chidiya ud sakti hai.",
    explanation: "A bird can move through the sky.",
    emoji: "🐦☁️",
    words: [
      { text: "A", hindi: "एक" },
      { text: "bird", hindi: "चिड़िया" },
      { text: "can", hindi: "सकती है" },
      { text: "fly", hindi: "उड़ना" }
    ]
  },
  {
    id: "yellow-flower",
    sentence: "She has a yellow flower.",
    hindi: "उसके पास एक पीला फूल है।",
    spokenHindi: "Uske paas ek peela phool hai.",
    explanation: "The flower she has is yellow.",
    emoji: "👧🌼",
    words: [
      { text: "She", hindi: "वह" },
      { text: "has", hindi: "के पास है" },
      { text: "a", hindi: "एक" },
      { text: "yellow", hindi: "पीला" },
      { text: "flower", hindi: "फूल" }
    ]
  }
];

export function spellSentenceWord(word: string) {
  return word.toUpperCase().replace(/[^A-Z]/g, "").split("");
}
