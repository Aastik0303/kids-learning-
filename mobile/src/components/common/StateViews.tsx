import { ActivityIndicator, View } from "react-native";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";

/**
 * Loading, error and empty states. All copy here is child-facing: gentle,
 * short, non-technical, and never blaming the child (spec section 20).
 */

export function LoadingState({ message = "Getting things ready…" }: { message?: string }) {
  const theme = useTheme();
  return (
    <View
      accessibilityRole="progressbar"
      accessibilityLabel={message}
      style={{ alignItems: "center", justifyContent: "center", padding: theme.space[8], gap: theme.space[4] }}
    >
      <Text style={{ fontSize: 48 }}>🐻</Text>
      <ActivityIndicator size="large" color={theme.colors.primary} />
      <Text variant="subheading" align="center" muted>
        {message}
      </Text>
    </View>
  );
}

export type ErrorStateProps = {
  /** Already child-safe copy — pass `ApiError.childMessage`. */
  message?: string;
  onRetry?: () => void;
  retryLabel?: string;
};

export function ErrorState({
  message = "Something went wrong. Let us try again!",
  onRetry,
  retryLabel = "Try again",
}: ErrorStateProps) {
  const theme = useTheme();
  return (
    <Card variant="panel" style={{ gap: theme.space[4], alignItems: "center" }}>
      <Text style={{ fontSize: 44 }}>🌧️</Text>
      <Text variant="subheading" align="center">
        {message}
      </Text>
      {onRetry ? <Button label={retryLabel} icon="🔄" tone="accent" onPress={onRetry} /> : null}
    </Card>
  );
}

export function EmptyState({
  icon = "🌱",
  title,
  subtitle,
}: {
  icon?: string;
  title: string;
  subtitle?: string;
}) {
  const theme = useTheme();
  return (
    <Card variant="lift" style={{ gap: theme.space[2], alignItems: "center" }}>
      <Text style={{ fontSize: 40 }}>{icon}</Text>
      <Text variant="subheading" align="center">
        {title}
      </Text>
      {subtitle ? (
        <Text variant="body" align="center" muted>
          {subtitle}
        </Text>
      ) : null}
    </Card>
  );
}

/** Small rounded label — topic chips, difficulty, lock state. */
export function Pill({
  label,
  tone = "neutral",
  icon,
}: {
  label: string;
  tone?: "neutral" | "success" | "accent" | "locked";
  icon?: string;
}) {
  const theme = useTheme();

  const background =
    tone === "success"
      ? theme.colors.successSoft
      : tone === "accent"
        ? theme.palette.sunLight
        : tone === "locked"
          ? theme.colors.surfaceSunken
          : theme.palette.skyLight;

  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        gap: theme.space[1],
        alignSelf: "flex-start",
        borderRadius: theme.radius.pill,
        paddingHorizontal: theme.space[3],
        paddingVertical: theme.space[1],
        backgroundColor: background,
      }}
    >
      {icon ? <Text variant="caption">{icon}</Text> : null}
      <Text
        variant="caption"
        color={tone === "locked" ? theme.colors.lockedText : theme.colors.text}
      >
        {label}
      </Text>
    </View>
  );
}
