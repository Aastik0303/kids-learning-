import { useCallback, useEffect, useMemo, useState } from "react";
import { Pressable, View } from "react-native";

import { GameFinish } from "@/components/games/FindItGame";
import { GamePiece, hasPicture, wordFor } from "@/components/games/GamePiece";
import { Text } from "@/components/common/Text";
import { useGameVoice } from "@/components/games/useGameVoice";
import { useTheme } from "@/app/providers/ThemeProvider";
import { haptics } from "@/services/audio/haptics";
import type { LevelGame } from "@/types/teacher";

/**
 * Find the pairs - the level's own pictures, face down, two taps at a time.
 *
 * The one game here that asks nothing and still teaches: a child turning over
 * the letter A and then the apple beside it is doing exactly what that level is
 * about, and there is no question to get wrong. It is also the game a
 * two-year-old can play with no words at all.
 *
 * What it is made of: the picture tokens the author named in this level's own
 * activities. A token the app has no artwork for is **dropped**, never dealt as
 * a neutral mark - two identical blue diamonds would be a pair a child matches
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

/** How many pairs are dealt. Eight cards is the most a small screen holds
 *  without scrolling, and a memory game you have to scroll is one you cannot
 *  hold in your head. */
const MAX_PAIRS = 4;

function deal(tokens: string[]): Card[] {
  const usable = tokens.filter(hasPicture).slice(0, MAX_PAIRS);
  const cards = usable.flatMap((token, index) => [
    { key: `${token}-${index}-a`, token },
    { key: `${token}-${index}-b`, token },
  ]);
  // Shuffled on every deal, so the pack is different every time the same level
  // is played - the levels themselves are deterministic, and this is the one
  // place where sameness would make the game pointless.
  for (let position = cards.length - 1; position > 0; position -= 1) {
    const swap = Math.floor(Math.random() * (position + 1));
    const here = cards[position];
    const there = cards[swap];
    if (here && there) {
      cards[position] = there;
      cards[swap] = here;
    }
  }
  return cards;
}

export type PairsGameProps = {
  game: LevelGame;
  onFinished?: () => void;
};

export function PairsGame({ game, onFinished }: PairsGameProps) {
  const theme = useTheme();
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
      haptics.success();
      // The thing they found, named. This is the whole vocabulary lesson in the
      // game, and it is the one moment a child is looking straight at it.
      say(wordFor(first.token) || first.token);
      setMatched((current) => [...current, first.token]);
      setTurned([]);
      return;
    }
    const timer = setTimeout(() => setTurned([]), 900);
    return () => clearTimeout(timer);
  }, [turned, cards, say]);

  const done = cards.length > 0 && matched.length * 2 === cards.length;

  useEffect(() => {
    if (done) onFinished?.();
  }, [done, onFinished]);

  const flip = useCallback(
    (card: Card) => {
      if (turned.length >= 2) return;
      if (turned.includes(card.key) || matched.includes(card.token)) return;
      haptics.tap();
      setTurned((current) => [...current, card.key]);
    },
    [turned, matched],
  );

  if (!tokens.length) return null;
  if (done) return <GameFinish onAgain={start} />;

  return (
    <View style={{ flex: 1, gap: theme.space[3] }} testID="game-pairs">
      <Text variant="subheading">Turn over two cards. Do they match?</Text>

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
        {cards.map((card) => {
          const isMatched = matched.includes(card.token);
          const isUp = isMatched || turned.includes(card.key);
          return (
            <Pressable
              key={card.key}
              accessibilityRole="button"
              accessibilityLabel={isUp ? wordFor(card.token) || card.token : "A card, face down"}
              onPress={() => flip(card)}
              testID="pairs-card"
              style={{
                // A square card with soft corners, sized so two fit across a
                // phone: a bigger card is a bigger target, and the child
                // playing this is two.
                width: "44%",
                aspectRatio: 1,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: theme.radius.xxl,
                borderWidth: 4,
                borderColor: isMatched
                  ? theme.palette.leaf
                  : isUp
                    ? theme.palette.sunshine
                    : "transparent",
                backgroundColor: isUp ? theme.colors.surface : theme.palette.sky,
                ...theme.shadows.soft,
              }}
            >
              {isUp ? (
                <GamePiece token={card.token} size="md" quiet />
              ) : (
                <Text style={{ fontSize: 40 }} color={theme.palette.white}>
                  ❔
                </Text>
              )}
            </Pressable>
          );
        })}
      </View>

      <Text variant="label" align="center" color={theme.palette.leaf}>
        {matched.length ? `⭐ ${matched.length} found` : " "}
      </Text>
    </View>
  );
}
