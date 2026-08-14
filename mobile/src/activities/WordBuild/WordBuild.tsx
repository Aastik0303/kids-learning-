import { useEffect, useMemo, useState } from "react";
import { Pressable, View } from "react-native";

import { Button } from "@/components/common/Button";
import { GuideHighlight } from "@/components/common/GuideHighlight";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { haptics } from "@/services/audio/haptics";
import type { ActivityComponentProps } from "@/activities/types";

/**
 * Build a word from letter tiles.
 *
 * The target word comes from the activity's `word` or `correctAnswer`.
 * Distractor letters are added deterministically (seeded from the word
 * itself) so the same question always presents the same tiles — a child
 * repeating a level should not face a different puzzle each time.
 */
export function WordBuild({
  activity,
  onAnswer,
  feedback,
  isSubmitting,
  isLocked,
  isToddlerMode,
}: ActivityComponentProps) {
  const theme = useTheme();

  const targetWord = (activity.word || activity.correctAnswer || "").toUpperCase();
  const [placed, setPlaced] = useState<string[]>([]);

  useEffect(() => {
    setPlaced([]);
  }, [activity.id]);

  const tiles = useMemo(() => buildTiles(targetWord, isToddlerMode), [targetWord, isToddlerMode]);

  const disabled = isSubmitting || isLocked;
  const isComplete = placed.length === targetWord.length;

  const tileSize = isToddlerMode ? 76 : 62;

  return (
    <View style={{ gap: theme.space[5] }}>
      {/* Slots the child is filling */}
      <View style={{ flexDirection: "row", justifyContent: "center", gap: theme.space[2] }}>
        {Array.from({ length: targetWord.length }, (_, index) => {
          const letter = placed[index];
          return (
            <View
              key={index}
              style={{
                width: tileSize,
                height: tileSize,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: theme.radius.lg,
                borderWidth: 3,
                borderStyle: letter ? "solid" : "dashed",
                borderColor: letter ? theme.colors.accent : theme.colors.borderStrong,
                backgroundColor: letter ? theme.palette.sunLight : theme.colors.surfaceSunken,
              }}
            >
              <Text variant="childAnswer">{letter ?? ""}</Text>
            </View>
          );
        })}
      </View>

      {/* Available letters */}
      <View
        style={{
          flexDirection: "row",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: theme.space[2],
        }}
      >
        {tiles.map((letter, index) => {
          // A tile is spent once it has been used as many times as it appears.
          const usedCount = placed.filter((p) => p === letter).length;
          const availableCount = tiles.filter((t) => t === letter).length;
          const spent = usedCount >= availableCount;

          return (
            <GuideHighlight
              key={`${letter}-${index}`}
              targetId={`letter-${letter}`}
              kind="option"
              label={`Letter ${letter}`}
            >
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`Letter ${letter}`}
                accessibilityState={{ disabled: disabled || spent || isComplete }}
                disabled={disabled || spent || isComplete}
                onPress={() => {
                  haptics.tap();
                  setPlaced((current) => [...current, letter]);
                }}
                style={({ pressed }) => ({
                  width: tileSize,
                  height: tileSize,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: theme.radius.lg,
                  backgroundColor: theme.colors.surface,
                  borderWidth: 2,
                  borderColor: theme.colors.border,
                  opacity: spent ? 0.3 : pressed ? 0.8 : 1,
                  ...theme.shadows.card,
                })}
              >
                <Text variant="childAnswer">{letter}</Text>
              </Pressable>
            </GuideHighlight>
          );
        })}
      </View>

      <View style={{ flexDirection: "row", gap: theme.space[3] }}>
        <View style={{ flex: 1 }}>
          <Button
            label="Undo"
            icon="↩️"
            tone="quiet"
            disabled={placed.length === 0 || disabled}
            onPress={() => setPlaced((current) => current.slice(0, -1))}
          />
        </View>
        <View style={{ flex: 2 }}>
          <Button
            label="Check my word"
            icon="✅"
            tone="primary"
            disabled={!isComplete || disabled}
            onPress={() => onAnswer(placed.join(""), { input: "tap" })}
          />
        </View>
      </View>

      {feedback && !feedback.isCorrect ? (
        <Button label="Start over" tone="quiet" onPress={() => setPlaced([])} />
      ) : null}
    </View>
  );
}

/**
 * Target letters plus a few deterministic distractors, in a stable
 * shuffled order derived from the word.
 */
function buildTiles(word: string, isToddlerMode: boolean): string[] {
  const letters = word.split("");
  if (letters.length === 0) return [];

  const distractorCount = isToddlerMode ? 1 : Math.min(3, Math.max(1, 6 - letters.length));
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

  // Seed from the word so the same question always yields the same tiles.
  let seed = 0;
  for (const character of word) seed += character.charCodeAt(0);

  const distractors: string[] = [];
  for (let i = 0; i < distractorCount; i += 1) {
    const index = (seed * (i + 7) + 11) % alphabet.length;
    const candidate = alphabet[index] ?? "A";
    if (!letters.includes(candidate) && !distractors.includes(candidate)) {
      distractors.push(candidate);
    }
  }

  const pool = [...letters, ...distractors];

  // Deterministic shuffle — same seed, same order, every time.
  for (let i = pool.length - 1; i > 0; i -= 1) {
    const j = (seed * (i + 3)) % (i + 1);
    const a = pool[i];
    const b = pool[j];
    if (a !== undefined && b !== undefined) {
      pool[i] = b;
      pool[j] = a;
    }
  }

  return pool;
}
