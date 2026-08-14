import { Pressable, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { GuideHighlight } from "@/components/common/GuideHighlight";
import { StarRow } from "@/components/common/StarRow";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { haptics } from "@/services/audio/haptics";

export type LevelState = "current" | "completed" | "upcoming" | "locked";

export type LevelNodeProps = {
  stageNumber: number;
  title: string;
  state: LevelState;
  starsEarned?: number;
  starReward?: number;
  onPress: () => void;
};

/**
 * A single level on the path. Ports the web build's `.map-level-node`
 * states — current glows and is largest, completed is warm, upcoming is
 * faded, locked is grey with a padlock.
 *
 * Size and opacity carry the state so a pre-reader can see where they are
 * without reading a word.
 */
export function LevelNode({
  stageNumber,
  title,
  state,
  starsEarned = 0,
  starReward = 3,
  onPress,
}: LevelNodeProps) {
  const theme = useTheme();
  const isLocked = state === "locked";

  const scale = state === "current" ? 1 : state === "completed" ? 0.97 : state === "upcoming" ? 0.92 : 0.88;

  return (
    <GuideHighlight
      targetId={`level-${stageNumber}`}
      kind="nav"
      label={`Level ${stageNumber}: ${title}`}
      style={{ transform: [{ scale }] }}
    >
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Level ${stageNumber}, ${title}. ${
          isLocked ? "Locked" : state === "completed" ? `Completed with ${starsEarned} stars` : "Ready to play"
        }`}
        accessibilityState={{ disabled: isLocked }}
        disabled={isLocked}
        onPress={() => {
          haptics.tap();
          onPress();
        }}
        style={({ pressed }) => ({
          flexDirection: "row",
          alignItems: "center",
          gap: theme.space[3],
          borderRadius: theme.radius.card,
          backgroundColor:
            state === "current"
              ? theme.whiteAlpha.a96
              : state === "completed"
                ? theme.whiteAlpha.a86
                : theme.whiteAlpha.a58,
          padding: theme.space[3],
          opacity: pressed ? 0.9 : isLocked ? 0.62 : 1,
          borderWidth: state === "current" ? 3 : 1,
          borderColor: state === "current" ? theme.colors.accent : theme.colors.border,
          ...(state === "current" ? theme.shadows.float : theme.shadows.card),
        })}
      >
        {/* The numbered medallion */}
        <View style={{ width: 68, height: 68, borderRadius: 999, overflow: "hidden" }}>
          {state === "current" ? (
            <LinearGradient
              colors={[...theme.gradients.currentNode]}
              style={{ flex: 1, alignItems: "center", justifyContent: "center" }}
            >
              <Text variant="heading" color={theme.colors.textOnBrand}>
                {stageNumber}
              </Text>
            </LinearGradient>
          ) : state === "completed" ? (
            <LinearGradient
              colors={[...theme.gradients.completedNode]}
              style={{ flex: 1, alignItems: "center", justifyContent: "center" }}
            >
              <Text variant="heading">{stageNumber}</Text>
            </LinearGradient>
          ) : (
            <View
              style={{
                flex: 1,
                alignItems: "center",
                justifyContent: "center",
                backgroundColor: isLocked ? theme.colors.locked : theme.palette.skyLight,
              }}
            >
              <Text variant="heading" color={isLocked ? theme.colors.lockedText : theme.colors.text}>
                {isLocked ? "🔒" : stageNumber}
              </Text>
            </View>
          )}
        </View>

        <View style={{ flex: 1, gap: theme.space[1] }}>
          <Text variant="overline" muted>
            Level {stageNumber}
          </Text>
          <Text variant="subheading" numberOfLines={2}>
            {title}
          </Text>
          {state === "completed" ? <StarRow earned={starsEarned} total={starReward} size={18} /> : null}
        </View>

        {state === "current" ? <Text style={{ fontSize: 26 }}>👉</Text> : null}
      </Pressable>
    </GuideHighlight>
  );
}
