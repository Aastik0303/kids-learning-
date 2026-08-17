"use client";

import { useAvatar } from "@/components/avatar/AvatarProvider";

/**
 * The guide's own panel inside a lesson.
 *
 * A lesson used to be silent: the question appeared, and nothing said what it
 * meant. Practice already had a guide that reads the question out, gives a
 * hint after a miss, and points at what to look at — this is that same coach,
 * so an adventure lesson explains itself the way Practice does.
 *
 * Everything a child can ask for is one tap, and each tap is spoken:
 *   Say it again  — repeats the current line, no network involved.
 *   Hint          — asks the guide for one small step, never the answer.
 *   Show me       — asks the guide to point at the pictures and count along.
 *
 * The buttons carry no size of their own: the surface floors in globals.css
 * give every control inside the child shell its 64px (or 96px in `early`)
 * minimum, so nothing here can fall under the floor by being written new.
 */
export function GuideCoach({
  message,
  busy = false,
  onHint,
  onShowMe,
  disabled
}: {
  message: string;
  busy?: boolean;
  onHint?: () => void;
  onShowMe?: () => void;
  disabled?: boolean;
}) {
  const { speakMessage, setAvatar } = useAvatar();
  const line = busy ? "Let me think about this one…" : message;

  if (!line) return null;

  function sayAgain() {
    setAvatar({ state: "speaking", message, animationEffect: "none", durationMs: 4200 });
    speakMessage(message);
  }

  return (
    <section
      data-testid="guide-coach"
      aria-live="polite"
      className="grid gap-3 rounded-[2rem] border-2 border-sky/20 bg-white/85 p-4 sm:p-5"
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className={`grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-sky/10 text-3xl ${busy ? "animate-pulse" : ""}`}
        >
          🦉
        </span>
        <div className="min-w-0">
          <p className="text-xs font-black uppercase tracking-wide text-sky">Your guide</p>
          <p className="text-lg font-black leading-snug text-ink sm:text-xl">{line}</p>
        </div>
      </div>

      <div className="touch-row grid grid-cols-1 gap-2 xs:grid-cols-2 sm:flex sm:flex-wrap">
        <button
          type="button"
          onClick={sayAgain}
          disabled={disabled || busy || !message}
          data-testid="guide-say-again"
          className="pressable rounded-full bg-white px-5 py-3 text-base font-black text-ink shadow-soft disabled:opacity-50"
        >
          🔊 Say it again
        </button>
        {onHint ? (
          <button
            type="button"
            onClick={onHint}
            disabled={disabled || busy}
            data-testid="guide-hint"
            className="pressable rounded-full bg-sunshine px-5 py-3 text-base font-black text-ink shadow-soft disabled:opacity-50"
          >
            💡 Give me a hint
          </button>
        ) : null}
        {onShowMe ? (
          <button
            type="button"
            onClick={onShowMe}
            disabled={disabled || busy}
            data-testid="guide-show-me"
            className="pressable rounded-full bg-sky px-5 py-3 text-base font-black text-white shadow-soft disabled:opacity-50"
          >
            👀 Show me
          </button>
        ) : null}
      </div>
    </section>
  );
}
