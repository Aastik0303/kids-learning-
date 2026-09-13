import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, View } from "react-native";

import { AnswerChoice } from "@/components/curriculum/AnswerChoice";
import { GameFinish, GameProgress } from "@/components/games/FindItGame";
import { Text } from "@/components/common/Text";
import { useGameVoice } from "@/components/games/useGameVoice";
import { useTheme } from "@/app/providers/ThemeProvider";
import { haptics } from "@/services/audio/haptics";
import type { GameRound, LevelGame } from "@/types/teacher";

/**
 * Pop it! - a field of bubbles, and only some of them are the answer.
 *
 * The same authored question as the tapping game, asked in the way a small
 * child will actually keep doing: there are **three** of the right one to find
 * rather than one, so the game is a hunt rather than a single decision, and a
 * lucky first tap does not end it.
 *
 * Two decisions here are about the child's hands rather than the content:
 *
 * * **The bubbles stay where they are.** Something crossing the screen has to
 *   be caught, and a two-year-old cannot catch. They sit in a grid and wait.
 * * **A wrong pop is nothing at all.** No sound of failure, no counter going
 *   down, nothing written anywhere. The bubble is still there to be tapped
 *   again once the child has worked out it is not the one.
 */

const TARGETS_PER_ROUND = 3;
const MAX_BUBBLES = 8;

type Bubble = {
  key: string;
  label: string;
  right: boolean;
};

function fill(round: GameRound): Bubble[] {
  const answer = round.options[round.answer];
  const others = round.options.filter((_, index) => index !== round.answer);
  if (!answer || !others.length) return [];

  const made: Bubble[] = [];
  for (let index = 0; index < TARGETS_PER_ROUND; index += 1) {
    made.push({ key: `right-${index}`, label: answer.label, right: true });
  }
  for (let index = 0; made.length < MAX_BUBBLES; index += 1) {
    const option = others[index % others.length];
    if (!option) break;
    made.push({ key: `other-${index}`, label: option.label, right: false });
  }

  for (let position = made.length - 1; position > 0; position -= 1) {
    const swap = Math.floor(Math.random() * (position + 1));
    const here = made[position];
    const there = made[swap];
    if (here && there) {
      made[position] = there;
      made[swap] = here;
    }
  }
  return made;
}

export type PopItGameProps = {
  game: LevelGame;
  onFinished?: () => void;
};

export function PopItGame({ game, onFinished }: PopItGameProps) {
  const theme = useTheme();
  const rounds = useMemo(
    () => (game.rounds ?? []).filter((round) => round.options.length >= 2),
    [game.rounds],
  );
  const [index, setIndex] = useState(0);
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [popped, setPopped] = useState<string[]>([]);
  const [wrong, setWrong] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const { say, repeat } = useGameVoice();

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
    const timer = setTimeout(() => {
      if (index + 1 >= rounds.length) {
        setDone(true);
        onFinished?.();
        return;
      }
      setIndex((current) => current + 1);
    }, 1000);
    return () => clearTimeout(timer);
  }, [left, bubbles.length, round, index, rounds.length, onFinished]);

  const pop = useCallback(
    (bubble: Bubble) => {
      if (popped.includes(bubble.key)) return;
      if (!bubble.right) {
        setWrong(bubble.key);
        haptics.gentleRetry();
        say(round?.ask ?? "");
        setTimeout(() => setWrong(null), 600);
        return;
      }
      haptics.success();
      setPopped((current) => [...current, bubble.key]);
    },
    [popped, round, say],
  );

  if (!rounds.length || !round) return null;
  if (done) return <GameFinish onAgain={() => { setIndex(0); setDone(false); }} />;

  return (
    <View style={{ flex: 1, gap: theme.space[3] }} testID="game-pop">
      <GameProgress total={rounds.length} at={index} won={left === 0} />

      <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[3] }}>
        <Text variant="subheading" style={{ flex: 1 }}>
          {round.ask} <Text variant="body" muted>Pop {TARGETS_PER_ROUND} of them!</Text>
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
          gap: theme.space[2],
        }}
      >
        {bubbles.map((bubble) => {
          const gone = popped.includes(bubble.key);
          return gone ? (
            <View
              key={bubble.key}
              style={{ width: "22%", aspectRatio: 1, alignItems: "center", justifyContent: "center" }}
            >
              <Text style={{ fontSize: 30 }}>✨</Text>
            </View>
          ) : (
            <Pressable
              key={bubble.key}
              accessibilityRole="button"
              accessibilityLabel={bubble.label}
              testID="pop-bubble"
              onPress={() => pop(bubble)}
              style={{
                width: "22%",
                aspectRatio: 1,
                minHeight: 88,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: theme.radius.pill,
                borderWidth: 4,
                borderColor: wrong === bubble.key ? theme.palette.berry : theme.palette.skyLight,
                backgroundColor: theme.colors.surface,
                ...theme.shadows.soft,
              }}
            >
              <AnswerChoice
                option={bubble.label}
                offered={round.options.map((one) => one.label)}
              />
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}
