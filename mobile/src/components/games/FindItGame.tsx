import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, View } from "react-native";

import { AnswerChoice } from "@/components/curriculum/AnswerChoice";
import { Text } from "@/components/common/Text";
import { useGameVoice } from "@/components/games/useGameVoice";
import { useTheme } from "@/app/providers/ThemeProvider";
import { haptics } from "@/services/audio/haptics";
import type { LevelGame } from "@/types/teacher";

/**
 * Find it! - the question is said out loud and the child taps the right one.
 *
 * The simplest game there is, and the one every level can offer, because it is
 * the shape the syllabus is already written in: a person wrote the question,
 * the choices and which of them is right, and the server decided the answer
 * with `stage.contains_answer` - the same rule the class marks a tap with, so a
 * child can never tap the option the server chose and be told they were wrong.
 *
 * Three things make it a game rather than a test:
 *
 * * **A wrong tap costs nothing.** The button wobbles, the question is said
 *   again, and the child tries once more. No limit, no score, and nothing is
 *   written anywhere - not an attempt, not a star, not a plan movement. Losing
 *   is not possible, which is the point.
 * * **Nobody has to read.** The question is spoken when the round opens and
 *   again on every wrong tap, and every choice is drawn as a picture by
 *   `AnswerChoice` - the same component the class uses, so a button here looks
 *   like the button there.
 * * **The targets are big**, because the child playing this is two.
 */

export type FindItGameProps = {
  game: LevelGame;
  /** Called when the last round is through, so the page can offer another game. */
  onFinished?: () => void;
};

export function FindItGame({ game, onFinished }: FindItGameProps) {
  const theme = useTheme();
  const rounds = game.rounds ?? [];
  const [index, setIndex] = useState(0);
  const [wrong, setWrong] = useState<number | null>(null);
  const [won, setWon] = useState(false);
  const [done, setDone] = useState(false);
  const { say, repeat } = useGameVoice();

  const round = rounds[index];
  const offered = useMemo(() => (round?.options ?? []).map((one) => one.label), [round]);

  // The round says itself when it opens. A game the child chose to start may
  // talk to them.
  useEffect(() => {
    if (round) say(round.ask);
  }, [round, say]);

  const tap = useCallback(
    (choice: number) => {
      if (!round || won) return;
      if (choice !== round.answer) {
        setWrong(choice);
        haptics.gentleRetry();
        // Said again rather than corrected. Being told what it is not teaches
        // nothing; hearing the question once more is another go at it.
        say(round.ask);
        setTimeout(() => setWrong(null), 600);
        return;
      }
      setWrong(null);
      setWon(true);
      haptics.success();
      setTimeout(() => {
        setWon(false);
        if (index + 1 >= rounds.length) {
          setDone(true);
          onFinished?.();
          return;
        }
        setIndex((current) => current + 1);
      }, 1100);
    },
    [round, won, index, rounds.length, say, onFinished],
  );

  if (!rounds.length || !round) return null;
  if (done) return <GameFinish onAgain={() => { setIndex(0); setDone(false); }} />;

  return (
    <View style={{ flex: 1, gap: theme.space[3] }} testID="game-find">
      <GameProgress total={rounds.length} at={index} won={won} />

      <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[3] }}>
        <Text variant="subheading" style={{ flex: 1 }}>
          {round.ask}
        </Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Say it again"
          onPress={repeat}
          style={{
            minHeight: theme.touchTarget.parent,
            minWidth: theme.touchTarget.parent,
            alignItems: "center",
            justifyContent: "center",
            borderRadius: theme.radius.pill,
            backgroundColor: theme.palette.sky,
          }}
        >
          <Text variant="subheading" color={theme.palette.white}>
            🔊
          </Text>
        </Pressable>
      </View>

      <View
        style={{
          flex: 1,
          flexDirection: "row",
          flexWrap: "wrap",
          justifyContent: "center",
          alignContent: "center",
          gap: theme.space[3],
        }}
      >
        {round.options.map((option, position) => (
          <Pressable
            key={`${option.token}-${position}`}
            accessibilityRole="button"
            accessibilityLabel={option.label}
            onPress={() => tap(position)}
            style={{
              minHeight: 112,
              minWidth: "42%",
              flexGrow: 1,
              alignItems: "center",
              justifyContent: "center",
              borderRadius: theme.radius.xl,
              backgroundColor: theme.colors.surface,
              borderWidth: 4,
              borderColor:
                wrong === position
                  ? theme.palette.berry
                  : won && position === round.answer
                    ? theme.palette.leaf
                    : "transparent",
              padding: theme.space[3],
              ...theme.shadows.soft,
            }}
          >
            <AnswerChoice option={option.label} offered={offered} />
          </Pressable>
        ))}
      </View>
    </View>
  );
}

/** Which round of how many, as dots. Nobody here can read "2 of 5". */
export function GameProgress({
  total,
  at,
  won,
}: {
  total: number;
  at: number;
  won?: boolean;
}) {
  const theme = useTheme();
  return (
    <View style={{ flexDirection: "row", gap: theme.space[1], justifyContent: "center" }}>
      {Array.from({ length: total }, (_, index) => (
        <View
          key={index}
          style={{
            width: 12,
            height: 12,
            borderRadius: 6,
            backgroundColor:
              index < at || (won && index === at) ? theme.palette.leaf : theme.inkAlpha.a14,
          }}
        />
      ))}
    </View>
  );
}

/**
 * The end of a game, which is the only thing that ever happens at the end of
 * one: there is no score to show, so this says well done and offers another go.
 */
export function GameFinish({ onAgain }: { onAgain: () => void }) {
  const theme = useTheme();
  return (
    <View style={{ flex: 1, alignItems: "center", justifyContent: "center", gap: theme.space[4] }}>
      <Text style={{ fontSize: 64 }}>🎉</Text>
      <Text variant="heading" align="center">
        All done!
      </Text>
      <Pressable
        accessibilityRole="button"
        onPress={onAgain}
        style={{
          minHeight: theme.touchTarget.child,
          justifyContent: "center",
          borderRadius: theme.radius.xl,
          backgroundColor: theme.palette.leaf,
          paddingHorizontal: theme.space[8],
        }}
      >
        <Text variant="subheading" color={theme.palette.white}>
          🔁 Again
        </Text>
      </Pressable>
    </View>
  );
}
