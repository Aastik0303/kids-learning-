"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AnswerChoice } from "@/components/curriculum/AnswerChoice";
import { GameFinish, GameProgress } from "@/components/games/FindItGame";
import { buzz, useGameVoice } from "@/components/games/useGameVoice";
import type { GameRound, LevelGame } from "@/types";

/**
 * Pop it! — a field of floating bubbles, and only some of them are the answer.
 *
 * The same authored question as the tapping game, asked in the way a small
 * child will actually keep doing: there are **three** of the right one to find
 * rather than one, so the game is a hunt rather than a single decision, and a
 * lucky first tap does not end it.
 *
 * Two decisions here are about the child's hands rather than the content:
 *
 * * **The bubbles bob, they do not fly.** Something crossing the screen has to
 *   be caught, and a two-year-old cannot catch. These drift a few pixels on
 *   their own timing, stay exactly where they are, and wait. The whole field is
 *   a grid underneath, so nothing overlaps and nothing is ever half off the
 *   edge on a small screen. Under `prefers-reduced-motion` they simply hold
 *   still — see `.game-bubble` in `globals.css`.
 * * **A wrong pop is a wobble and nothing else.** No sound of failure, no
 *   counter going down, nothing written anywhere. The bubble is still there to
 *   be tapped again once the child has worked out it is not the one.
 */

const TARGETS_PER_ROUND = 3;
const MAX_BUBBLES = 8;

type Bubble = {
  key: string;
  label: string;
  right: boolean;
  /** Its own bobbing rhythm, so a field of them does not pulse in unison. */
  delay: string;
  duration: string;
};

function fill(round: GameRound): Bubble[] {
  const answer = round.options[round.answer];
  const others = round.options.filter((_, index) => index !== round.answer);
  if (!answer || !others.length) return [];

  const made: Bubble[] = [];
  for (let index = 0; index < TARGETS_PER_ROUND; index += 1) {
    made.push({ key: `right-${index}`, label: answer.label, right: true, delay: "", duration: "" });
  }
  for (let index = 0; made.length < MAX_BUBBLES; index += 1) {
    const option = others[index % others.length];
    made.push({ key: `other-${index}`, label: option.label, right: false, delay: "", duration: "" });
  }

  for (let position = made.length - 1; position > 0; position -= 1) {
    const swap = Math.floor(Math.random() * (position + 1));
    [made[position], made[swap]] = [made[swap], made[position]];
  }

  return made.map((bubble) => ({
    ...bubble,
    delay: `${(Math.random() * 2).toFixed(2)}s`,
    duration: `${(2.6 + Math.random() * 1.8).toFixed(2)}s`
  }));
}

export type PopItGameProps = {
  game: LevelGame;
  onFinished?: () => void;
};

export function PopItGame({ game, onFinished }: PopItGameProps) {
  const rounds = useMemo(
    () => (game.rounds ?? []).filter((round) => round.options.length >= 2),
    [game.rounds]
  );
  const [index, setIndex] = useState(0);
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [popped, setPopped] = useState<string[]>([]);
  const [wrong, setWrong] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const { say, repeat, canSpeak } = useGameVoice();

  const round = rounds[index];

  useEffect(() => {
    if (!round) return;
    setBubbles(fill(round));
    setPopped([]);
    say(round.ask);
  }, [round, say]);

  const left = bubbles.filter((bubble) => bubble.right && !popped.includes(bubble.key)).length;

  // The round is over when the last right one goes. A moment to see it happen,
  // then the next question.
  useEffect(() => {
    if (!round || !bubbles.length || left > 0) return;
    const timer = window.setTimeout(() => {
      if (index + 1 >= rounds.length) {
        setDone(true);
        onFinished?.();
        return;
      }
      setIndex((current) => current + 1);
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [left, bubbles.length, round, index, rounds.length, onFinished]);

  const pop = useCallback(
    (bubble: Bubble) => {
      if (popped.includes(bubble.key)) return;
      if (!bubble.right) {
        setWrong(bubble.key);
        buzz([12, 60, 12]);
        say(round?.ask ?? "");
        window.setTimeout(() => setWrong(null), 600);
        return;
      }
      buzz(22);
      setPopped((current) => [...current, bubble.key]);
    },
    [popped, round, say]
  );

  const again = useCallback(() => {
    setIndex(0);
    setDone(false);
  }, []);

  if (!rounds.length) return null;
  if (done) return <GameFinish onAgain={again} />;

  return (
    <div className="game-body grid gap-4" data-testid="game-pop">
      <GameProgress total={rounds.length} at={index} won={left === 0} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="game-ask text-xl font-black leading-snug text-ink sm:text-2xl">
          {round.ask} <span className="text-ink/50">Pop {TARGETS_PER_ROUND} of them!</span>
        </p>
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

      <ul className="game-grid grid grid-cols-4 gap-2 sm:gap-4">
        {bubbles.map((bubble) => {
          const gone = popped.includes(bubble.key);
          return (
            <li key={bubble.key} className="grid place-items-center">
              {gone ? (
                <span aria-hidden className="game-popped grid aspect-square w-full place-items-center text-4xl">
                  ✨
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => pop(bubble)}
                  aria-label={bubble.label}
                  data-testid="pop-bubble"
                  style={{ animationDelay: bubble.delay, animationDuration: bubble.duration }}
                  className={[
                    "game-bubble grid aspect-square min-h-[5.5rem] w-full touch-manipulation select-none place-items-center rounded-full border-4 bg-white p-2 shadow-soft",
                    wrong === bubble.key ? "game-wobble border-berry/60" : "border-sky/25"
                  ].join(" ")}
                >
                  <AnswerChoice option={bubble.label} offered={round.options.map((one) => one.label)} />
                </button>
              )}
            </li>
          );
        })}
      </ul>

      <p aria-live="polite" className="game-cheer min-h-8 text-lg font-black text-leaf">
        {left === 0 && bubbles.length ? "🎉 All popped!" : ""}
      </p>
    </div>
  );
}
