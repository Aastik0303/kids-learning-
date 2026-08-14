import { Pressable, View } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

import { GuideHighlight } from "@/components/common/GuideHighlight";
import { Text } from "@/components/common/Text";
import { Pill } from "@/components/common/StateViews";
import { useTheme } from "@/app/providers/ThemeProvider";
import { haptics } from "@/services/audio/haptics";
import { classVisual } from "@/theme/colors";

export type FeatureCardProps = {
  /** Matches a `classVisuals` key so colours come from one place. */
  featureId: string;
  title: string;
  description: string;
  /** Shown on the guest home to hint at what the AI does here. */
  aiHint?: string;
  locked?: boolean;
  progress?: string;
  onPress: () => void;
  compact?: boolean;
};

/**
 * The card used for classes on both the guest home and the child's
 * Classes tab. Colours and mascot come from the class's own visual
 * identity, carried over from the web build's `learningWorlds`.
 */
export function FeatureCard({
  featureId,
  title,
  description,
  aiHint,
  locked = false,
  progress,
  onPress,
  compact = false,
}: FeatureCardProps) {
  const theme = useTheme();
  const visual = classVisual(featureId);

  return (
    <GuideHighlight
      targetId={`class-${featureId}`}
      kind="nav"
      label={`${title} class card`}
      style={{ flex: 1 }}
    >
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${title}. ${description}${locked ? ". Locked" : ""}`}
        accessibilityState={{ disabled: locked }}
        onPress={() => {
          haptics.tap();
          onPress();
        }}
        style={({ pressed }) => ({
          borderRadius: theme.radius.card,
          overflow: "hidden",
          borderWidth: 1,
          borderColor: theme.colors.border,
          opacity: locked ? 0.6 : pressed ? 0.9 : 1,
          transform: [{ scale: pressed ? 0.985 : 1 }],
          ...theme.shadows.card,
        })}
      >
        <LinearGradient
          colors={[...visual.gradient]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={{
            minHeight: compact ? 120 : 168,
            gap: theme.space[2],
            backgroundColor: visual.tint,
            padding: theme.space[4],
          }}
        >
          <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[2] }}>
            <Text style={{ fontSize: compact ? 30 : 40 }}>{visual.icon}</Text>
            <Text style={{ fontSize: compact ? 24 : 32 }}>{visual.mascot}</Text>
            {locked ? <Text style={{ fontSize: 20 }}>🔒</Text> : null}
          </View>

          <Text variant={compact ? "subheading" : "heading"} numberOfLines={1}>
            {title}
          </Text>

          <Text variant="body" numberOfLines={2} muted>
            {description}
          </Text>

          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: theme.space[2], marginTop: "auto" }}>
            {aiHint ? <Pill label={aiHint} icon="🐻" tone="accent" /> : null}
            {progress ? <Pill label={progress} tone="success" /> : null}
            {locked ? <Pill label="Locked" tone="locked" icon="🔒" /> : null}
          </View>
        </LinearGradient>
      </Pressable>
    </GuideHighlight>
  );
}
