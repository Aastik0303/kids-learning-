import { useTheme } from "@/app/providers/ThemeProvider";
import { breakpointIndex, type Breakpoint } from "@/theme/breakpoints";

export type ResponsiveValue<T> = T | Partial<Record<Breakpoint, T>>;

function isBreakpointMap<T>(value: ResponsiveValue<T>): value is Partial<Record<Breakpoint, T>> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  return Object.keys(value).some((key) =>
    ["smallPhone", "phone", "largePhone", "tablet", "largeTablet"].includes(key),
  );
}

/**
 * Resolve a responsive value against the active breakpoint, falling back
 * down the scale so `{ phone: 1, tablet: 2 }` still answers on largeTablet.
 */
export function useResponsiveValue<T>(value: ResponsiveValue<T>): T {
  const { breakpoint } = useTheme();

  if (!isBreakpointMap(value)) return value as T;

  const order: Breakpoint[] = ["smallPhone", "phone", "largePhone", "tablet", "largeTablet"];
  const activeIndex = breakpointIndex(breakpoint);

  for (let i = activeIndex; i >= 0; i -= 1) {
    const key = order[i];
    if (key !== undefined) {
      const candidate = value[key];
      if (candidate !== undefined) return candidate;
    }
  }

  // Nothing at or below the active breakpoint — take the nearest above.
  for (let i = activeIndex + 1; i < order.length; i += 1) {
    const key = order[i];
    if (key !== undefined) {
      const candidate = value[key];
      if (candidate !== undefined) return candidate;
    }
  }

  throw new Error("useResponsiveValue received an empty breakpoint map");
}

/** Convenience predicates used throughout layout code. */
export function useResponsive() {
  const theme = useTheme();
  return {
    breakpoint: theme.breakpoint,
    isTablet: theme.isTablet,
    isLandscape: theme.isLandscape,
    isCompact: theme.isCompact,
    width: theme.width,
    height: theme.height,
    atLeast: (name: Breakpoint) => breakpointIndex(theme.breakpoint) >= breakpointIndex(name),
    below: (name: Breakpoint) => breakpointIndex(theme.breakpoint) < breakpointIndex(name),
    /**
     * True when the avatar can sit beside the activity instead of over it
     * (spec section 15: landscape puts the AI area next to the activity).
     */
    sideBySideGuide: theme.isLandscape || theme.isTablet,
  };
}
