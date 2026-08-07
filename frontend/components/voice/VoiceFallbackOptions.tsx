"use client";

export function VoiceFallbackOptions({
  options,
  disabled,
  onAnswer
}: {
  options: string[];
  disabled?: boolean;
  onAnswer: (answer: string) => void;
}) {
  return (
    <div data-guide-id="answer-options" className="grid gap-3 sm:grid-cols-3">
      {options.map((option) => (
        <button
          key={option}
          disabled={disabled}
          onClick={() => onAnswer(option)}
          className="pressable min-h-16 rounded-3xl border-2 border-transparent bg-white px-4 py-3 text-lg font-black text-ink shadow-soft transition hover:border-ink/10 disabled:opacity-50"
          type="button"
        >
          {option}
        </button>
      ))}
    </div>
  );
}
