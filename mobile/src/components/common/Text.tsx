import { Text as RNText, type TextProps as RNTextProps, type TextStyle } from "react-native";

import { useTheme } from "@/app/providers/ThemeProvider";
import type { TextVariant } from "@/theme/typography";

export type TextProps = RNTextProps & {
  variant?: TextVariant;
  color?: string;
  align?: TextStyle["textAlign"];
  /** Convenience for the very common "muted secondary line". */
  muted?: boolean;
};

/**
 * Every string in the app renders through here, so breakpoint scaling and
 * OS font-scale clamping are applied uniformly. Raw <Text> is a bug.
 */
export function Text({
  variant = "body",
  color,
  align,
  muted,
  style,
  ...rest
}: TextProps) {
  const theme = useTheme();
  const base = theme.type(variant);

  return (
    <RNText
      {...rest}
      style={[
        base,
        muted ? { color: theme.colors.textSecondary } : null,
        color ? { color } : null,
        align ? { textAlign: align } : null,
        style,
      ]}
    />
  );
}
