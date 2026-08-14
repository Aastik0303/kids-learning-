import { useEffect, useState } from "react";
import { Pressable, View } from "react-native";

import { GuideHighlight } from "@/components/common/GuideHighlight";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useResponsive } from "@/components/responsive/useResponsive";
import { haptics } from "@/services/audio/haptics";
import type { ActivityComponentProps } from "@/activities/types";

/**
 * Tap-to-answer. Backs `tap_choice`, and — with a different presentation
 * hint — `shape_match`, `color_match` and `image_match`.
 *
 * Every option registers itself as a guide target ("option-triangle"), so
 * the AI can point at one specific choice while explaining.
 */
export type TapChoiceProps = ActivityComponentProps & {
  /** How each option should be drawn. */
  presentation?: "text" | "glyph" | "swatch";
};

export function TapChoice({
  activity,
  onAnswer,
  feedback,
  isSubmitting,
  isLocked,
  isToddlerMode,
  presentation = "text",
}: TapChoiceProps) {
  const theme = useTheme();
  const { isTablet } = useResponsive();

  // Which option this child actually tapped. Tracked here because the
  // backend feedback says whether the answer was right, not which one
  // was chosen — and we need that to colour the right tile.
  const [chosen, setChosen] = useState<string | null>(null);

  // A new question clears the selection.
  useEffect(() => {
    setChosen(null);
  }, [activity.id]);

  const options = activity.options;
  // Toddlers get at most two choices on screen at once.
  const visible = isToddlerMode ? options.slice(0, 2) : options;

  const columns =
    presentation === "text" && !isToddlerMode
      ? isTablet
        ? 2
        : 1
      : visible.length <= 2
        ? 2
        : isTablet
          ? 4
          : 2;

  const disabled = isSubmitting || isLocked;

  return (
    <View
      style={{
        flexDirection: "row",
        flexWrap: "wrap",
        gap: theme.space[3],
        justifyContent: "center",
      }}
    >
      {visible.map((option) => {
        const isChosen = chosen !== null && normalise(option) === normalise(chosen);
        const showWrong = !!feedback && !feedback.isCorrect && isChosen;
        const showCorrect =
          !!feedback?.isCorrect && normalise(option) === normalise(activity.correctAnswer);

        return (
          <GuideHighlight
            key={option}
            targetId={`option-${slug(option)}`}
            kind="option"
            label={`Answer choice ${option}`}
            style={{ width: columns === 1 ? "100%" : `${100 / columns - 3}%` }}
          >
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`Answer ${option}`}
              accessibilityState={{ disabled, selected: isChosen }}
              disabled={disabled}
              onPress={() => {
                haptics.tap();
                setChosen(option);
                onAnswer(option, { input: "tap" });
              }}
              style={({ pressed }) => ({
                minHeight: isToddlerMode
                  ? theme.touchTarget.toddler + 32
                  : theme.touchTarget.child + 16,
                alignItems: "center",
                justifyContent: "center",
                borderRadius: theme.radius.card,
                borderWidth: 3,
                borderColor: showCorrect
                  ? theme.colors.success
                  : showWrong
                    ? theme.colors.danger
                    : theme.colors.border,
                backgroundColor:
                  presentation === "swatch"
                    ? swatchColor(option)
                    : showCorrect
                      ? theme.colors.successSoft
                      : showWrong
                        ? theme.colors.dangerSoft
                        : theme.colors.surface,
                padding: theme.space[4],
                opacity: pressed ? 0.85 : disabled ? 0.6 : 1,
                ...theme.shadows.card,
              })}
            >
              <Text
                variant={
                  presentation === "glyph"
                    ? isToddlerMode
                      ? "toddlerPrompt"
                      : "childAnswer"
                    : isToddlerMode
                      ? "heading"
                      : "subheading"
                }
                align="center"
                // Colour swatches still carry their name in text — a
                // colour-blind child must not be locked out of the answer.
                color={presentation === "swatch" ? readableOn(swatchColor(option)) : undefined}
              >
                {option}
              </Text>
            </Pressable>
          </GuideHighlight>
        );
      })}
    </View>
  );
}

function slug(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

function normalise(value: string): string {
  return value.trim().toLowerCase();
}

/** Maps a colour word to a real colour for `color_match` swatches. */
const SWATCHES: Record<string, string> = {
  red: "#e04a4a",
  blue: "#4a90c2",
  green: "#2f8f6b",
  yellow: "#f5c542",
  orange: "#f08c34",
  purple: "#8b7bd8",
  pink: "#f07ba8",
  brown: "#8b6b45",
  black: "#25313f",
  white: "#ffffff",
  grey: "#9aa4ae",
  gray: "#9aa4ae",
};

function swatchColor(option: string): string {
  return SWATCHES[normalise(option)] ?? "#e8f7ff";
}

/** Pick ink or white text so the label stays legible on any swatch. */
function readableOn(background: string): string {
  const hex = background.replace("#", "");
  if (hex.length !== 6) return "#25313f";
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  // Rec. 601 luma — good enough for a two-way light/dark decision.
  const luma = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luma > 0.6 ? "#25313f" : "#ffffff";
}
