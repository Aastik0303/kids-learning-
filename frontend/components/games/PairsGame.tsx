"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { GameFinish } from "@/components/games/FindItGame";
import { GamePiece, hasPicture, wordFor } from "@/components/games/GamePiece";
import { buzz, useGameVoice } from "@/components/games/useGameVoice";
import type { LevelGame } from "@/types";

/**
 * Find the pairs — the level's own pictures, face down, two taps at a time.
 *
 * The one game here that asks nothing and still teaches: a child turning over
 * the letter A and then the apple beside it is doing exactly what that level is
 * about, and there is no question to get wrong. It is also the game a
 * two-year-old can play with no words at all, which is why it is offered on the
 * levels whose author wrote only two pictures — four cards is a real game at
 * that age.
 *
 * What it is made of: the picture tokens the author named in this level's own
 * activities. A token the app has no artwork for is **dropped**, never dealt as
 * a neutral mark — two identical blue diamonds would be a pair a child matches
 * without seeing anything, and the pack would teach nothing.
 *
 * Nothing is timed, nothing is counted, and a mismatch just turns back over.
 * The only thing that ever happens is the pack running out, which is winning.
 */

type Card = {
  /** Unique per card, so the two halves of a pair are still two cards. */
  key: string;
  token: string;
};

/** How many pairs are dealt. Eight cards is the most that fits a small screen
 *  without scrolling, and a memory game you have to scroll is one you cannot
 *  hold in your head. */
const MAX_PAIRS = 4;

function deal(tokens: string[]): Card[] {
  const usable = tokens.filter(hasPicture).slice(0, MAX_PAIRS);
  const cards = usable.flatMap((token, index) => [
    { key: `${token}-${index}-a`, token },
    { key: `${token}-${index}-b`, token }
  ]);
  // Shuffled on the client, on mount, so the pack is different every time the
  // same level is played — the levels themselves are deterministic, and this is
  // the one place where sameness would make the game pointless.
  for (let position = cards.length - 1; position > 0; position -= 1) {
    const swap = Math.floor(Math.random() * (position + 1));
    [cards[position], cards[swap]] = [cards[swap], cards[position]];
  }
  return cards;
}

export type PairsGameProps = {
  game: LevelGame;
  onFinished?: () => void;
};

export function PairsGame({ game, onFinished }: PairsGameProps) {
  const tokens = useMemo(() => (game.tokens ?? []).filter(hasPicture), [game.tokens]);
  const [cards, setCards] = useState<Card[]>([]);
  const [turned, setTurned] = useState<string[]>([]);
  const [matched, setMatched] = useState<string[]>([]);
  const { say } = useGameVoice();

  const start = useCallback(() => {
    setCards(deal(tokens));
    setTurned([]);
    setMatched([]);
  }, [tokens]);

  useEffect(() => {
    start();
  }, [start]);

  // Two cards up: either they stay up or they both go back. The board is locked
  // while that is being decided, or a fast tapper turns over a third and the
  // pair they had just found flips back under their finger.
  useEffect(() => {
    if (turned.length !== 2) return;
    const [first, second] = turned.map((key) => cards.find((card) => card.key === key));
    if (first && second && first.token === second.token) {
      buzz(24);
      // The thing they found, named. This is the whole vocabulary lesson in the
      // game, and it is the one moment a child is looking straight at it.
      say(wordFor(first.token) || first.token);
      setMatched((current) => [...current, first.token]);
      setTurned([]);
      return;
    }
    const timer = window.setTimeout(() => setTurned([]), 900);
    return () => window.clearTimeout(timer);
  }, [turned, cards, say]);

  const done = cards.length > 0 && matched.length * 2 === cards.length;

  useEffect(() => {
    if (done) onFinished?.();
  }, [done, onFinished]);

  const flip = useCallback(
    (card: Card) => {
      if (turned.length >= 2) return;
      if (turned.includes(card.key) || matched.includes(card.token)) return;
      buzz(10);
      setTurned((current) => [...current, card.key]);
    },
    [turned, matched]
  );

  if (!tokens.length) return null;
  if (done) return <GameFinish onAgain={start} />;

  // Four across once there are more than four cards, at every size. Two across
  // meant eight cards were four rows deep, which is a board a phone has to
  // scroll — and a memory game you cannot see all of at once is one you cannot
  // hold in your head.
  const columns = cards.length <= 4 ? "grid-cols-2" : "grid-cols-4";

  return (
    <div className="game-body grid gap-4" data-testid="game-pairs">
      <p className="game-ask text-xl font-black leading-snug text-ink sm:text-2xl">
        Turn over two cards. Do they match?
      </p>

      <ul className={`game-grid grid ${columns} gap-3 sm:gap-4`}>
        {cards.map((card) => {
          const isMatched = matched.includes(card.token);
          const isUp = isMatched || turned.includes(card.key);
          return (
            <li key={card.key}>
              <button
                type="button"
                onClick={() => flip(card)}
                aria-label={isUp ? wordFor(card.token) || card.token : "A card, face down"}
                aria-pressed={isUp}
                data-testid="pairs-card"
                className={[
                  "grid aspect-square min-h-[6rem] w-full touch-manipulation select-none place-items-center rounded-[1.75rem] border-4 p-3 shadow-soft transition-colors",
                  isMatched ? "border-leaf bg-leaf/10" : "",
                  isUp && !isMatched ? "border-sunshine bg-white" : "",
                  !isUp ? "pressable border-transparent bg-sky text-white" : ""
                ].join(" ")}
              >
                {isUp ? (
                  <GamePiece token={card.token} size="md" quiet />
                ) : (
                  <span aria-hidden className="text-5xl">
                    ❔
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>

      <p aria-live="polite" className="game-cheer min-h-8 text-lg font-black text-leaf">
        {matched.length ? `⭐ ${matched.length} found` : ""}
      </p>
    </div>
  );
}
