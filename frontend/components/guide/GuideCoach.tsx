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
 *   Ask           — the child asks the guide anything, out loud.
 *   Show me       — asks the guide to point at the pictures and count along.
 *
 * Ask replaced a fixed "Give me a hint" button. A hint was the only thing a
 * child was allowed to want, and it was always the same request; what they
 * actually want is to ask the thing they are wondering about - "what is that
 * one?", "why?", "yeh kya hai?". The guide still answers a hint request when
 * that is what they asked for, because now they can ask for it in words.
 *
 * It is a microphone, not a text box, because the children this is for cannot
 * read or type. Everything they say goes through the guide's own safety
 * filtering server-side, and the guide answers questions about the lesson or
 * says, kindly, that it can help with letters and numbers instead.
 *
 * The buttons carry no size of their own: the surface floors in globals.css
 * give every control inside the child shell its 64px (or 96px in `early`)
 * minimum, so nothing here can fall under the floor by being written new.
 */
export function GuideCoach({
  message,
  busy = false,
  onAsk,
  onShowMe,
  disabled,
  isAsking = false
}: {
  message: string;
  busy?: boolean;
  /** Opens the microphone so the child can ask the guide anything. */
  onAsk?: () => void;
  onShowMe?: () => void;
  disabled?: boolean;
  /** True while the microphone is open and waiting for the question. */
  isAsking?: boolean;
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
        {onAsk ? (
          <button
            type="button"
            onClick={onAsk}
            disabled={disabled || busy || isAsking}
            data-testid="guide-ask"
            aria-label={isAsking ? "Listening to your question" : "Ask the guide a question"}
            className={`pressable rounded-full px-5 py-3 text-base font-black text-ink shadow-soft disabled:opacity-50 ${
              isAsking ? "animate-pulse bg-leaf text-white" : "bg-sunshine"
            }`}
          >
            {isAsking ? "🎤 I am listening…" : "🙋 Ask me anything"}
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
