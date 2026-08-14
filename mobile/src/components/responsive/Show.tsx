import type { ReactNode } from "react";

import { useResponsive } from "@/components/responsive/useResponsive";
import type { Breakpoint } from "@/theme/breakpoints";

type ShowProps = {
  children: ReactNode;
  /** Render only at or above this breakpoint. */
  from?: Breakpoint;
  /** Render only below this breakpoint. */
  below?: Breakpoint;
  /** Render only in the given orientation. */
  orientation?: "portrait" | "landscape";
};

/**
 * Declarative breakpoint gate. Preferred over inline ternaries when an
 * entire subtree only exists at some sizes (e.g. the tablet side rail).
 */
export function Show({ children, from, below, orientation }: ShowProps) {
  const responsive = useResponsive();

  if (from && !responsive.atLeast(from)) return null;
  if (below && !responsive.below(below)) return null;
  if (orientation === "landscape" && !responsive.isLandscape) return null;
  if (orientation === "portrait" && responsive.isLandscape) return null;

  return <>{children}</>;
}
