import { useEffect, useRef } from "react";
import { Animated, View } from "react-native";

import { Button } from "@/components/common/Button";
import { GuideHighlight } from "@/components/common/GuideHighlight";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import type { ActivityComponentProps } from "@/activities/types";

/**
 * The teaching beat: "This is the letter A." No answer is expected.
 *
 * The backend emits these as `introduce_letter` / `introduce_number` /
 * `introduce_colour` / `introduce_shape`, and toddler mode uses them to
 * open every level. Making it a first-class activity kind — rather than
 * folding it into a question — is what lets the guide teach before it asks.
 */
export function Introduce({
  activity,
  onContinue,
  onRepeat,
  isToddlerMode,
  isLocked,
}: ActivityComponentProps) {
  const theme = useTheme();
  const enter = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    enter.setValue(0);
    Animated.spring(enter, {
      toValue: 1,
      useNativeDriver: true,
      bounciness: 12,
      speed: 8,
    }).start();
  }, [activity.id, enter]);

  const glyph = activity.glyph || activity.concept || activity.correctAnswer;

  return (
    <View style={{ gap: theme.space[6], alignItems: "center" }}>
      <GuideHighlight
        targetId="teaching-glyph"
        kind="visual"
        label={`The thing being taught: ${activity.concept}`}
      >
        <Animated.View
          style={{
            minWidth: 180,
            minHeight: 180,
            alignItems: "center",
            justifyContent: "center",
            borderRadius: theme.radius.card,
            backgroundColor: theme.palette.sunLight,
            paddingHorizontal: theme.space[8],
            paddingVertical: theme.space[6],
            ...theme.shadows.float,
            transform: [
              { scale: theme.reduceMotion ? 1 : enter.interpolate({ inputRange: [0, 1], outputRange: [0.7, 1] }) },
            ],
            opacity: theme.reduceMotion ? 1 : enter,
          }}
        >
          <Text style={{ fontSize: isToddlerMode ? 108 : 88, lineHeight: isToddlerMode ? 122 : 100 }}>
            {glyph}
          </Text>
        </Animated.View>
      </GuideHighlight>

      {activity.word ? (
        <Text variant={isToddlerMode ? "toddlerPrompt" : "childPrompt"} align="center">
          {activity.word}
        </Text>
      ) : null}

      <View style={{ width: "100%", gap: theme.space[3] }}>
        <Button label="Say it again" icon="🔁" tone="quiet" onPress={onRepeat} />
        <Button
          label="I am ready!"
          icon="👍"
          tone="primary"
          size={isToddlerMode ? "toddler" : "child"}
          disabled={isLocked}
          onPress={onContinue}
        />
      </View>
    </View>
  );
}

/** Closing celebration beat the toddler curriculum emits as `complete`. */
export function CompleteBeat({ activity, onContinue }: ActivityComponentProps) {
  const theme = useTheme();

  return (
    <View style={{ gap: theme.space[6], alignItems: "center" }}>
      <Text style={{ fontSize: 96 }}>🎉</Text>
      <Text variant="title" align="center">
        {activity.prompt || "You did it!"}
      </Text>
      <Button label="Next" icon="➡️" tone="primary" size="toddler" onPress={onContinue} />
    </View>
  );
}
