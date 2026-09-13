import { useEffect, useMemo, useState } from "react";
import { Pressable, View } from "react-native";
import { useQuery } from "@tanstack/react-query";

import { FindItGame } from "@/components/games/FindItGame";
import { PairsGame } from "@/components/games/PairsGame";
import { PopItGame } from "@/components/games/PopItGame";
import { hasPicture } from "@/components/games/GamePiece";
import { Text } from "@/components/common/Text";
import { LoadingState } from "@/components/common/StateViews";
import { useTheme } from "@/app/providers/ThemeProvider";
import { curriculumApi } from "@/services/api/curriculumApi";
import type { LevelGame } from "@/types/teacher";

/**
 * What a level hands a child: a game about the thing it teaches, dealt at
 * random out of the three the level can offer and started straight away.
 *
 * This is where the level's **notes** used to be - the author's teaching lines,
 * printed and read aloud. Revising by re-reading is a grown-up's skill; a
 * three-year-old goes back over something by playing with it again, so the same
 * authored content is dealt out as games instead.
 *
 * Everything that made the notes safe on this screen still holds, and it is
 * worth being plain about, because a game *looks* like something that ought to
 * be scored:
 *
 * * **Nothing is marked.** No attempt, no probe, no policy episode, no star, no
 *   unlock, no movement of the day's plan. After the one fetch there is no
 *   request back to the server at all - everything a child taps here stays on
 *   the device and is gone when they leave.
 * * **No lesson starts from here.** The class is the AI Teacher and the
 *   schedule decides when a level is taught. This is a level the child has
 *   already been given, handed back as something to do.
 * * **No model wrote any of it.** Every question, choice and picture came out of
 *   the authored syllabus, so the same level offers the same games on every
 *   afternoon.
 *
 * **The child never picks which one.** Opening a level deals one of its games
 * and plays it: three cards to choose between is a menu, and a menu is a
 * reading task in front of a three-year-old. Any of the three is about the same
 * level and any is a fine way to go back over it. The two controls that remain
 * are 🎲, which deals another, and the way back - neither is a choice about
 * *what* to play.
 */

export type LevelGamesProps = {
  topicId: string;
  /** A locked level keeps its games, the same reason the map does not link to it. */
  locked?: boolean;
};

/**
 * Whether this game can actually be drawn on a screen.
 *
 * The server names pictures as asset tokens and the client owns the artwork, so
 * the last word on "is there anything to show?" is here. A matching pack whose
 * tokens have no drawings behind them is dropped rather than dealt as a grid of
 * neutral marks.
 */
function playable(game: LevelGame): boolean {
  if (game.kind === "pairs") return (game.tokens ?? []).filter(hasPicture).length >= 2;
  return (game.rounds ?? []).length > 0;
}

/**
 * One of them, and preferably not the one just played.
 *
 * The "not this one again" part is why this is not a bare random pick at the
 * call site: 🎲 is there for a child who has finished a round and wants another
 * go, and handing them the same game back is the button appearing not to work.
 */
function deal(games: LevelGame[], notThisOne?: string | null): string | null {
  if (!games.length) return null;
  const pool = games.length > 1 ? games.filter((game) => game.game_id !== notThisOne) : games;
  const choice = pool[Math.floor(Math.random() * pool.length)] ?? games[0];
  return choice?.game_id ?? null;
}

export function LevelGames({ topicId, locked = false }: LevelGamesProps) {
  const theme = useTheme();
  const [playing, setPlaying] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["curriculum", "games", topicId],
    queryFn: () => curriculumApi.games(topicId),
    enabled: !locked,
  });

  const shown = useMemo(() => (query.data?.games ?? []).filter(playable), [query.data]);

  // Straight into a game. The deal happens in an effect rather than during
  // render: a random pick in a render body gives a different answer every time
  // React re-runs it, so the game would change under the child's finger.
  useEffect(() => {
    if (!shown.length) return;
    setPlaying((current) => current ?? deal(shown));
  }, [shown]);

  if (locked) return null;

  if (query.isLoading) return <LoadingState message="Getting a game ready…" />;

  if (query.isError || !shown.length) {
    return (
      <View
        style={{
          borderRadius: theme.radius.card,
          backgroundColor: theme.colors.surface,
          padding: theme.space[5],
        }}
      >
        <Text variant="body" muted align="center">
          {query.isError
            ? "The games are having a rest. Try again in a moment."
            : "There is nothing to play here yet."}
        </Text>
      </View>
    );
  }

  const open = shown.find((game) => game.game_id === playing) ?? shown[0];
  if (!open) return null;

  return (
    <View
      style={{
        flex: 1,
        gap: theme.space[3],
        borderRadius: theme.radius.card,
        backgroundColor: theme.colors.surface,
        padding: theme.space[4],
        ...theme.shadows.card,
      }}
      testID="level-games"
    >
      <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[3] }}>
        <Text variant="label" style={{ flex: 1 }}>
          {open.icon} {open.title}
        </Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Another game"
          onPress={() => setPlaying(deal(shown, open.game_id))}
          style={{
            minHeight: theme.touchTarget.parent,
            minWidth: theme.touchTarget.parent,
            alignItems: "center",
            justifyContent: "center",
            borderRadius: theme.radius.pill,
            backgroundColor: theme.colors.surfaceSunken,
          }}
        >
          <Text variant="subheading">🎲</Text>
        </Pressable>
      </View>

      {open.kind === "pairs" ? (
        <PairsGame key={open.game_id} game={open} />
      ) : open.kind === "pop" ? (
        <PopItGame key={open.game_id} game={open} />
      ) : (
        <FindItGame key={open.game_id} game={open} />
      )}
    </View>
  );
}
