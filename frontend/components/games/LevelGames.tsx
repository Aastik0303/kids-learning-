"use client";

import { useEffect, useMemo, useState } from "react";

import { FindItGame } from "@/components/games/FindItGame";
import { hasPicture } from "@/components/games/GamePiece";
import { PairsGame } from "@/components/games/PairsGame";
import { PopItGame } from "@/components/games/PopItGame";
import { getTopicGames } from "@/services/curriculum";
import type { LevelGame, TopicGames } from "@/types";

/**
 * What a level hands a child: a game about the thing it teaches, dealt at
 * random out of the three the level can offer and started straight away.
 *
 * This is where the level's **notes** used to be — the author's teaching lines,
 * printed and read aloud. Revising by re-reading is a grown-up's skill. A
 * three-year-old goes back over something by playing with it again, so the same
 * authored content is dealt out as three games instead: find it, match the
 * pairs, pop it.
 *
 * Everything that made the notes safe on this page still holds, and it is worth
 * being plain about because a game *looks* like something that ought to be
 * scored:
 *
 * * **Nothing is marked.** No attempt, no probe, no policy episode, no star, no
 *   unlock, no movement of the day's plan. There is no request back to the
 *   server at all once the games have been fetched — everything a child taps
 *   here stays in the browser and is gone when they leave.
 * * **No lesson starts from here.** The class is still the AI Teacher and the
 *   schedule still decides when a level is taught. This is a level the child
 *   has already been given, handed back as something to do.
 * * **No model wrote any of it.** Every question, choice and picture came out of
 *   the syllabus (`app/playground/games.py`), so the same level offers the same
 *   games on every afternoon.
 *
 * A level that authored too little comes back with fewer than three games, and
 * one with nothing playable at all says so plainly rather than showing an empty
 * shelf.
 *
 * **The child never picks which one.** Opening a level deals one of its games at
 * random and starts it. There used to be a shelf of three cards here and it was
 * a menu in front of a three-year-old: choosing between "Find it", "Find the
 * pairs" and "Pop it" is a reading task, and it is the sort of decision this
 * whole app exists to take off the child. Any of the three is about the same
 * level and any of them is a fine way to go back over it, so the app deals one.
 * The two controls that remain are "another one", which rerolls, and the way
 * back to the level - neither is a choice about *what* to play.
 */

export type LevelGamesProps = {
  topicId: string;
  /** A locked level keeps its games, the same reason the map does not link to it. */
  locked?: boolean;
};

/** Whether this game can actually be drawn on a screen.
 *
 *  The server names pictures as asset tokens and the client owns the artwork, so
 *  the last word on "is there anything to show?" is here. A matching pack whose
 *  tokens have no drawings behind them is dropped rather than dealt as a grid of
 *  neutral marks. */
function playable(game: LevelGame): boolean {
  if (game.kind === "pairs") return (game.tokens ?? []).filter(hasPicture).length >= 2;
  return (game.rounds ?? []).length > 0;
}

/**
 * One of them, at random, and preferably not the one just played.
 *
 * The "not this one again" part is why this is not a bare `Math.random()` at the
 * call site: the reroll button is there for a child who has finished a round and
 * wants another go, and handing them the same game back is the button appearing
 * not to work.
 */
function deal(games: LevelGame[], notThisOne?: string | null): string | null {
  if (!games.length) return null;
  const pool = games.length > 1 ? games.filter((game) => game.game_id !== notThisOne) : games;
  const choice = pool[Math.floor(Math.random() * pool.length)] ?? games[0];
  return choice.game_id;
}

export function LevelGames({ topicId, locked = false }: LevelGamesProps) {
  const [games, setGames] = useState<TopicGames | null>(null);
  const [failed, setFailed] = useState(false);
  const [playing, setPlaying] = useState<string | null>(null);

  useEffect(() => {
    if (locked) return;
    let live = true;
    setGames(null);
    setFailed(false);
    setPlaying(null);
    getTopicGames(topicId)
      .then((found) => {
        if (!live) return;
        setGames(found);
        // Straight into a game. The deal happens here rather than during
        // render, which is not a detail: `Math.random()` in a render body gives
        // the server one answer and the browser another, and React would tear
        // the page down and rebuild it on hydration.
        setPlaying(deal((found.games ?? []).filter(playable)));
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [topicId, locked]);

  const shown = useMemo(() => (games?.games ?? []).filter(playable), [games]);
  const open = shown.find((game) => game.game_id === playing) ?? null;

  if (locked) return null;

  if (failed) {
    return (
      <Panel>
        <p className="font-bold text-ink/60">
          The games are having a rest. Try again in a moment.
        </p>
      </Panel>
    );
  }

  if (!games) {
    return (
      <Panel>
        <p className="font-bold text-ink/60">Getting your games ready…</p>
      </Panel>
    );
  }

  if (!shown.length) {
    // Honest, the way the notes were honest about a level with nothing written
    // for it. Inventing a game out of nothing is the one thing this must not do.
    return (
      <Panel>
        <p className="font-bold text-ink/60">
          There are no games for this one yet. Your class will teach it out loud.
        </p>
      </Panel>
    );
  }

  if (open) {
    return (
      // `data-playing` is what turns this into the whole screen on a phone and
      // a tablet (`globals.css`, "A game, on one screen"). A child mid-game
      // needs the board and the way out of it, and nothing else on the level
      // page is any use to them until they are done. From xl: up it stays a
      // panel on the page.
      <section
        data-testid="level-games"
        data-playing="true"
        className="level-games surface-panel grid gap-4 rounded-[2rem] p-5"
      >
        <div className="game-head flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-black text-ink">
            <span aria-hidden>{open.icon}</span> {open.title}
          </h2>
          <div className="flex items-center gap-2">
            {/* Neither of these asks the child *which* game. One deals another
                one, one puts the level page back. */}
            {shown.length > 1 ? (
              <button
                type="button"
                onClick={() => setPlaying(deal(shown, open.game_id))}
                data-testid="another-game"
                className="pressable min-h-16 touch-manipulation rounded-3xl bg-white px-5 py-3 text-lg font-black text-ink/70 shadow-soft"
              >
                🎲 <span className="hidden sm:inline">Another one</span>
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => setPlaying(null)}
              data-testid="leave-game"
              className="pressable min-h-16 touch-manipulation rounded-3xl bg-white px-5 py-3 text-lg font-black text-ink/70 shadow-soft"
            >
              ←<span className="hidden sm:inline"> Back</span>
            </button>
          </div>
        </div>

        {open.kind === "find" ? <FindItGame game={open} /> : null}
        {open.kind === "pairs" ? <PairsGame game={open} /> : null}
        {open.kind === "pop" ? <PopItGame game={open} /> : null}
      </section>
    );
  }

  // Nothing is being played, which now only happens when the child has come
  // back out of a game. One button, and it deals another one - not a shelf of
  // three, which was a menu in front of somebody who cannot read.
  return (
    <section data-testid="level-games" className="level-games surface-panel grid gap-4 rounded-[2rem] p-5">
      <h2 className="text-lg font-black text-ink">🎮 Play with this one</h2>
      <button
        type="button"
        onClick={() => setPlaying(deal(shown))}
        data-testid="play-game"
        className="lift-card pressable grid min-h-[7rem] w-full touch-manipulation select-none justify-items-center gap-1 rounded-[1.75rem] p-4 text-center sm:min-h-[9rem] sm:gap-2 sm:p-6"
      >
        <span aria-hidden className="text-5xl leading-none sm:text-6xl">
          🎲
        </span>
        <span className="text-xl font-black leading-tight text-ink sm:text-2xl">Play a game</span>
      </button>
    </section>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <section data-testid="level-games" className="level-games surface-panel grid gap-3 rounded-[2rem] p-5">
      <h2 className="text-lg font-black text-ink">🎮 Play with this one</h2>
      {children}
    </section>
  );
}
