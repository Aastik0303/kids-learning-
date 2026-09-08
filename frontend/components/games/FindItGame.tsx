"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AnswerChoice } from "@/components/curriculum/AnswerChoice";
import { buzz, useGameVoice } from "@/components/games/useGameVoice";
import type { LevelGame } from "@/types";

/**
 * Find it! — the question is said out loud and the child taps the right one.
 *
 * The simplest game there is, and the one every level can offer, because it is
 * the shape the syllabus is already written in: a person wrote the question,
 * the choices and which of them is right, and the server decided the answer
 * with `stage.contains_answer` — the same rule the class marks a tap with.
 *
 * Three things make it a game rather than a test:
 *
 * * **A wrong tap costs nothing.** The button wobbles, the question is said
 *   again, and the child tries once more. There is no limit, no score, and
 *   nothing is written anywhere — not an attempt, not a star, not a plan
 *   movement. Losing is not possible, which is the point.
 * * **Nobody has to read.** The question is spoken when the round opens and
 *   again on every wrong tap, and every choice is drawn as a picture by
 *   `AnswerChoice` — the same component the class uses, so a button here looks
 *   like the button there.
 * * **The targets are big.** Every choice is at least 7rem tall with a whole
 *   finger of space around it, because the child playing this is two.
 */

export type FindItGameProps = {
  game: LevelGame;
  /** Shown when the last round is through, so the page can offer another game. */
  onFinished?: () => void;
};

export function FindItGame({ game, onFinished }: FindItGameProps) {
  const rounds = game.rounds ?? [];
  const [index, setIndex] = useState(0);
  const [wrong, setWrong] = useState<number | null>(null);
  const [won, setWon] = useState(false);
  const [done, setDone] = useState(false);
  const { say, repeat, canSpeak } = useGameVoice();

  const round = rounds[index];
  const offered = useMemo(() => (round?.options ?? []).map((one) => one.label), [round]);

  // The round says itself when it opens. A game the child chose to start may
  // talk to them; a page they merely navigated to may not, which is why the
  // notes needed a button and this does not.
  useEffect(() => {
    if (round) say(round.ask);
  }, [round, say]);

  const tap = useCallback(
    (choice: number) => {
      if (!round || won) return;
      if (choice !== round.answer) {
        setWrong(choice);
        buzz([12, 60, 12]);
        // Said again rather than corrected. Being told what it is not teaches
        // nothing; hearing the question once more is another go at it.
        say(round.ask);
        window.setTimeout(() => setWrong(null), 600);
        return;
      }

      setWrong(null);
      setWon(true);
      buzz(26);
      window.setTimeout(() => {
        setWon(false);
        if (index + 1 >= rounds.length) {
          setDone(true);
          onFinished?.();
          return;
        }
        setIndex((current) => current + 1);
      }, 1100);
    },
    [round, won, index, rounds.length, say, onFinished]
  );

  const again = useCallback(() => {
    setIndex(0);
    setWon(false);
    setDone(false);
  }, []);

  if (!rounds.length) return null;

  if (done) {
    return <GameFinish onAgain={again} />;
  }

  return (
    // `game-body` / `game-grid` / `game-cheer` are what let this fill a phone
    // screen exactly rather than run off the bottom of one: the question and
    // the cheer keep their height, the board takes the rest, and every choice
    // is a tile cut out of the room its row has. See "A game, on one screen"
    // in globals.css; on a laptop none of it applies.
    <div className="game-body grid gap-4" data-testid="game-find">
      <GameProgress total={rounds.length} at={index} won={won} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="game-ask text-xl font-black leading-snug text-ink sm:text-2xl">{round.ask}</p>
        {canSpeak ? (
          <button
            type="button"
            onClick={repeat}
            aria-label="Say it again"
            className="pressable min-h-16 touch-manipulation rounded-3xl bg-sky px-5 py-3 text-lg font-black text-white shadow-soft"
          >
            🔊 Again
          </button>
        ) : null}
      </div>

      <ul data-shape="wide" className="game-grid grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3">
        {round.options.map((option, position) => {
          const isWrong = wrong === position;
          const isRight = won && position === round.answer;
          return (
            <li key={`${option.token}-${position}`}>
              <button
                type="button"
                onClick={() => tap(position)}
                aria-label={option.label}
                data-testid="game-choice"
                className={[
                  "pressable grid min-h-[7rem] w-full touch-manipulation select-none place-items-center rounded-[1.75rem] bg-white p-4 shadow-soft",
                  "border-4 transition-colors",
                  isRight ? "border-leaf bg-leaf/10" : "",
                  isWrong ? "game-wobble border-berry/60" : "",
                  !isRight && !isWrong ? "border-transparent" : ""
                ].join(" ")}
              >
                <AnswerChoice option={option.label} offered={offered} />
              </button>
            </li>
          );
        })}
      </ul>

      {/* One line, and it only ever cheers. A wrong tap says nothing at all —
          the wobble is the whole of the feedback, and the question comes back
          in the child's ear a moment later. */}
      <p aria-live="polite" className="game-cheer min-h-8 text-lg font-black text-leaf">
        {won ? "🎉 Yes! That's it!" : ""}
      </p>
    </div>
  );
}

/** Five dots for five rounds — where you are, never how well you did. */
export function GameProgress({ total, at, won }: { total: number; at: number; won?: boolean }) {
  return (
    <ul className="flex items-center gap-2" aria-label={`Round ${at + 1} of ${total}`}>
      {Array.from({ length: total }).map((_, position) => (
        <li
          key={position}
          aria-hidden
          className={[
            "h-3 w-3 rounded-full transition-colors sm:h-4 sm:w-4",
            position < at || (won && position === at) ? "bg-leaf" : "",
            position === at && !won ? "bg-sunshine" : "",
            position > at ? "bg-ink/15" : ""
          ].join(" ")}
        />
      ))}
    </ul>
  );
}

/** The end of a game: a cheer and a way to play it again. Nothing is totted up. */
export function GameFinish({ onAgain }: { onAgain: () => void }) {
  return (
    <div className="grid justify-items-center gap-4 py-6 text-center" data-testid="game-finish">
      <span aria-hidden className="text-7xl">
        🎉
      </span>
      <p className="text-2xl font-black text-ink">You did it!</p>
      <button
        type="button"
        onClick={onAgain}
        className="pressable min-h-16 touch-manipulation rounded-3xl bg-leaf px-7 py-4 text-xl font-black text-white shadow-soft"
      >
        ▶️ Play again
      </button>
    </div>
  );
}
