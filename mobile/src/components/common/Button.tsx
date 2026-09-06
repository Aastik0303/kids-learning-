import { useRef } from "react";
import {
  ActivityIndicator,
  Animated,
  Pressable,
  View,
  type PressableProps,
  type ViewStyle,
} from "react-native";

import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { haptics } from "@/services/audio/haptics";

export type ButtonTone = "primary" | "secondary" | "accent" | "quiet" | "danger";
export type ButtonSize = "parent" | "child" | "toddler";

export type ButtonProps = Omit<PressableProps, "style"> & {
  label: string;
  tone?: ButtonTone;
  size?: ButtonSize;
  /** Emoji or glyph shown before the label. */
  icon?: string;
  loading?: boolean;
  fullWidth?: boolean;
  style?: ViewStyle;
};

/**
 * The product's signature control: rounded, chunky, high-contrast, and
 * sized well above the platform minimum because the primary user is two.
 *
 * Press feedback mirrors the web `.pressable` rule — lift on press-in,
 * settle on release — which is a big part of how the app "feels" familiar.
 */
export function Button({
  label,
  tone = "primary",
  size = "child",
  icon,
  loading = false,
  fullWidth = true,
  disabled,
  onPress,
  style,
  ...rest
}: ButtonProps) {
  const theme = useTheme();
  const scale = useRef(new Animated.Value(1)).current;

  const isDisabled = disabled || loading;

  const palette = tonePalette(tone, theme);
  const minHeight = theme.touchTarget[size];

  const animate = (to: number) => {
    if (theme.reduceMotion) return;
    Animated.spring(scale, {
      toValue: to,
      useNativeDriver: true,
      speed: 40,
      bounciness: 6,
    }).start();
  };

  return (
    <Animated.View
      style={[
        { transform: [{ scale }] },
        fullWidth ? { alignSelf: "stretch" } : { alignSelf: "flex-start" },
      ]}
    >
      <Pressable
        {...rest}
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityState={{ disabled: !!isDisabled, busy: loading }}
        disabled={isDisabled}
        onPressIn={() => animate(0.97)}
        onPressOut={() => animate(1)}
        onPress={(event) => {
          haptics.tap();
          onPress?.(event);
        }}
        style={[
          {
            minHeight,
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "center",
            gap: theme.space[2],
            paddingHorizontal: theme.space[5],
            paddingVertical: theme.space[3],
            borderRadius: theme.radius.card,
            backgroundColor: palette.background,
            borderWidth: palette.borderWidth,
            borderColor: palette.border,
            opacity: isDisabled ? 0.55 : 1,
          },
          theme.shadows.float,
          style,
        ]}
      >
        {loading ? (
          <ActivityIndicator color={palette.text} />
        ) : (
          <>
            {icon ? (
              <Text variant={size === "toddler" ? "heading" : "subheading"} color={palette.text}>
                {icon}
              </Text>
            ) : null}
            <Text
              variant={size === "toddler" ? "heading" : "subheading"}
              color={palette.text}
              numberOfLines={2}
              align="center"
              style={{ flexShrink: 1 }}
            >
              {label}
            </Text>
          </>
        )}
      </Pressable>
    </Animated.View>
  );
}

function tonePalette(tone: ButtonTone, theme: ReturnType<typeof useTheme>) {
  switch (tone) {
    case "primary":
      return {
        background: theme.colors.primary,
        text: theme.colors.primaryOn,
        border: "transparent",
        borderWidth: 0,
      };
    case "secondary":
      return {
        background: theme.colors.secondary,
        text: theme.colors.secondaryOn,
        border: "transparent",
        borderWidth: 0,
      };
    case "accent":
      return {
        background: theme.colors.accent,
        text: theme.colors.accentOn,
        border: "transparent",
        borderWidth: 0,
      };
    case "danger":
      return {
        background: theme.colors.danger,
        text: theme.colors.textOnBrand,
        border: "transparent",
        borderWidth: 0,
      };
    case "quiet":
      return {
        background: theme.colors.surface,
        text: theme.colors.text,
        border: theme.colors.border,
        borderWidth: 1,
      };
  }
}
