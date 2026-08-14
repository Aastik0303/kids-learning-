import { useEffect, useState } from "react";
import { Pressable, View } from "react-native";

import { GuideHighlight } from "@/components/common/GuideHighlight";
import { TapChoice } from "@/activities/TapChoice/TapChoice";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useResponsive } from "@/components/responsive/useResponsive";
import { haptics } from "@/services/audio/haptics";
import type { ActivityComponentProps } from "@/activities/types";

/**
 * Counting activity. The child taps each object to count it — tapping is
 * the counting action, not just decoration — then picks the total.
 *
 * Each object is a separately registered guide target ("count-item-0"),
 * which is what makes `highlight_sequence` work: the AI counts along by
 * lighting up items one at a time, exactly like the web build's staggered
 * `.visual-guide-step-N` animation.
 */
export function CountObjects(props: ActivityComponentProps) {
  const { activity, isToddlerMode, isLocked, isSubmitting } = props;
  const theme = useTheme();
  const { isTablet } = useResponsive();

  const [counted, setCounted] = useState<number[]>([]);

  useEffect(() => {
    setCounted([]);
  }, [activity.id]);

  const items = activity.visualItems;
  const perRow = isTablet ? 5 : items.length > 6 ? 4 : 3;
  const tileSize = isToddlerMode ? 88 : 72;

  const toggle = (index: number) => {
    if (isLocked || isSubmitting) return;
    haptics.tap();
    setCounted((current) =>
      current.includes(index) ? current.filter((i) => i !== index) : [...current, index],
    );
  };

  return (
    <View style={{ gap: theme.space[5] }}>
      {/* The objects being counted */}
      <View
        style={{
          flexDirection: "row",
          flexWrap: "wrap",
          gap: theme.space[3],
          justifyContent: "center",
        }}
      >
        {items.map((item, index) => {
          const order = counted.indexOf(index);
          const isCounted = order !== -1;

          return (
            <GuideHighlight
              key={`${item}-${index}`}
              targetId={`count-item-${index}`}
              kind="visual"
              label={`Object ${index + 1}: ${item}`}
            >
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={
                  isCounted ? `${item}, counted as number ${order + 1}` : `${item}, not counted yet`
                }
                onPress={() => toggle(index)}
                style={({ pressed }) => ({
                  width: tileSize,
                  height: tileSize,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: theme.radius.xl,
                  borderWidth: 3,
                  borderColor: isCounted ? theme.colors.accent : theme.colors.border,
                  backgroundColor: isCounted ? theme.palette.sunLight : theme.colors.surface,
                  opacity: pressed ? 0.8 : 1,
                  ...theme.shadows.soft,
                })}
              >
                <Text style={{ fontSize: tileSize * 0.5 }}>{item}</Text>

                {/* The running count badge — the actual teaching signal. */}
                {isCounted ? (
                  <View
                    style={{
                      position: "absolute",
                      top: -8,
                      right: -8,
                      minWidth: 28,
                      height: 28,
                      borderRadius: 999,
                      alignItems: "center",
                      justifyContent: "center",
                      backgroundColor: theme.colors.accent,
                      ...theme.shadows.soft,
                    }}
                  >
                    <Text variant="label" color={theme.colors.accentOn}>
                      {order + 1}
                    </Text>
                  </View>
                ) : null}
              </Pressable>
            </GuideHighlight>
          );
        })}
      </View>

      {counted.length > 0 ? (
        <Text variant="subheading" align="center" color={theme.colors.secondary}>
          You counted {counted.length}!
        </Text>
      ) : null}

      {/* Answer options — the count itself is still checked by the backend. */}
      <TapChoice {...props} presentation="glyph" />
    </View>
  );
}
