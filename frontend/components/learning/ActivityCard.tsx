"use client";

import { useAvatar } from "@/components/avatar/AvatarProvider";
import type { Activity } from "@/types";

const shapeClass: Record<string, string> = {
  circle: "rounded-full bg-berry",
  square: "rounded-xl bg-sky",
  triangle: "triangle",
  red: "rounded-full bg-berry",
  blue: "rounded-full bg-sky",
  yellow: "rounded-full bg-sunshine",
  green: "rounded-full bg-leaf"
};

const visualEmoji: Record<string, string> = {
  apple: "🍎",
  star: "⭐",
  "one star": "⭐",
  block: "🧩",
  red: "🔴",
  blue: "🔵",
  yellow: "🟡",
  green: "🟢",
  circle: "🔴",
  square: "🟦",
  triangle: "🔺",
  "red circle": "🔴",
  "blue square": "🟦",
  "yellow triangle": "🔺"
};

function VisualItem({ item }: { item: string }) {
  const normalized = item.toLowerCase();
  const emoji = visualEmoji[normalized] ?? (/^[^\x00-\x7F]/.test(item) ? item : null);
  if (emoji) {
    return <span className="grid h-20 w-20 place-items-center rounded-3xl bg-white text-5xl shadow-soft" aria-label={item}>{emoji}</span>;
  }
  const simple = normalized.split(" ").at(-1) ?? normalized;
  if (shapeClass[simple]) {
    return <span className={`grid h-20 w-20 place-items-center text-xs font-black text-white shadow-soft ${shapeClass[simple]}`}>{item.includes(" ") ? item.split(" ")[0] : ""}</span>;
  }
  return <span className="grid min-h-20 min-w-20 place-items-center rounded-3xl bg-white px-5 text-base font-black shadow-soft">{item}</span>;
}

export function ActivityCard({
  activity,
  onAnswer,
  disabled,
  highlightId
}: {
  activity: Activity;
  onAnswer: (answer: string) => void;
  disabled?: boolean;
  highlightId?: string | null;
}) {
  const { setAvatar, speakMessage } = useAvatar();

  function readPrompt() {
    setAvatar({
      state: "speaking",
      message: activity.prompt,
      animationEffect: "none",
      durationMs: 4200
    });
    speakMessage(activity.prompt);
  }

  return (
    <section data-guide-id="question-area" className={`surface-panel grid gap-5 rounded-[2rem] p-5 sm:p-6 ${highlightId === "question-area" ? "guide-glow" : ""}`}>
      <div className="grid gap-4 rounded-[2rem] bg-[#f7fbff] p-4 sm:grid-cols-[7rem_1fr] sm:items-center">
        <div className="mascot-face min-h-28 rounded-[1.75rem]" />
        <div>
          <p className="text-sm font-black uppercase text-sky">🧩 Mini mission</p>
          <h2 className="mt-2 text-3xl font-black leading-tight text-ink sm:text-4xl">{activity.prompt}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="rounded-full bg-leaf/10 px-4 py-2 text-sm font-black capitalize text-leaf">{activity.difficulty}</span>
            <span className="rounded-full bg-sunshine/40 px-4 py-2 text-sm font-black text-ink">⭐ Reward +1</span>
            <button type="button" onClick={readPrompt} className="pressable rounded-full bg-white px-4 py-2 text-sm font-black text-ink shadow-soft">🔊 Voice</button>
          </div>
        </div>
      </div>
      {activity.visual_items.length ? (
        <div data-guide-id="counting-object-group" className={`flex min-h-36 flex-wrap items-center justify-center gap-4 rounded-[2rem] border border-sky/10 bg-[#f7fbff] p-5 ${highlightId === "counting-object-group" ? "guide-glow" : ""}`}>
          {activity.visual_items.map((item, index) => (
            <VisualItem key={`${item}-${index}`} item={item} />
          ))}
        </div>
      ) : null}
      <div data-guide-id="answer-options" className={`grid gap-3 sm:grid-cols-3 ${highlightId === "answer-options" ? "guide-glow" : ""}`}>
        {activity.options.map((option) => (
          <button
            key={option}
            disabled={disabled}
            onClick={() => onAnswer(option)}
            className="pressable min-h-20 rounded-3xl border-2 border-transparent bg-sunshine px-4 py-4 text-xl font-black text-ink shadow-soft transition hover:border-ink/10 disabled:opacity-50"
          >
            {option}
          </button>
        ))}
      </div>
    </section>
  );
}
