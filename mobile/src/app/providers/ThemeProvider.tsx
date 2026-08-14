import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { AccessibilityInfo, useWindowDimensions } from "react-native";

import { buildTheme, type Theme } from "@/theme/theme";

const ThemeContext = createContext<Theme | null>(null);

/**
 * Single source of viewport truth. Every layout decision in the app reads
 * from here — nothing calls `Dimensions.get()` directly, which is what
 * makes rotation and split-screen work without a remount.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const { width, height, fontScale } = useWindowDimensions();
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    let alive = true;
    AccessibilityInfo.isReduceMotionEnabled()
      .then((enabled) => {
        if (alive) setReduceMotion(enabled);
      })
      .catch(() => {
        // Non-fatal: default to full motion if the query fails.
      });

    const sub = AccessibilityInfo.addEventListener("reduceMotionChanged", setReduceMotion);
    return () => {
      alive = false;
      sub.remove();
    };
  }, []);

  const theme = useMemo(
    () => buildTheme({ width, height, fontScale, reduceMotion }),
    [width, height, fontScale, reduceMotion],
  );

  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>;
}

export function useTheme(): Theme {
  const theme = useContext(ThemeContext);
  if (!theme) {
    throw new Error("useTheme must be used inside <ThemeProvider>");
  }
  return theme;
}
