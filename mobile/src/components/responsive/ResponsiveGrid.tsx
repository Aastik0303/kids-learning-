import { Children, type ReactNode } from "react";
import { View, type ViewStyle } from "react-native";

import { useResponsiveValue, type ResponsiveValue } from "@/components/responsive/useResponsive";
import { useTheme } from "@/app/providers/ThemeProvider";

type ResponsiveGridProps = {
  children: ReactNode;
  /** Columns per breakpoint, e.g. `{ smallPhone: 1, largePhone: 2, tablet: 3 }`. */
  columns: ResponsiveValue<number>;
  gap?: number;
  style?: ViewStyle;
};

/**
 * Flex-wrap grid with true equal columns. Used for feature cards, class
 * cards and reward tiles, all of which change column count by breakpoint.
 */
export function ResponsiveGrid({ children, columns, gap, style }: ResponsiveGridProps) {
  const theme = useTheme();
  const columnCount = Math.max(1, useResponsiveValue(columns));
  const gutter = gap ?? theme.space[3];
  const items = Children.toArray(children);

  return (
    <View
      style={[
        {
          flexDirection: "row",
          flexWrap: "wrap",
          marginHorizontal: -gutter / 2,
        },
        style,
      ]}
    >
      {items.map((child, index) => (
        <View
          // Grid slots are positional and the list is static per render,
          // so index is a stable key here.
          key={index}
          style={{
            width: `${100 / columnCount}%`,
            paddingHorizontal: gutter / 2,
            marginBottom: gutter,
          }}
        >
          {child}
        </View>
      ))}
    </View>
  );
}
