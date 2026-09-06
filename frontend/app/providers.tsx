"use client";

import dynamic from "next/dynamic";
import { AvatarProvider } from "@/components/avatar/AvatarProvider";

/**
 * Dev only, and lazily so it is a chunk the browser never asks for in a
 * production build rather than dead code sitting in the shared bundle. The
 * condition is a literal Next replaces at build time, so the whole import is
 * dropped unless somebody sets `NEXT_PUBLIC_RESPONSIVE_SWITCHER=1` on a staging
 * build on purpose. `ssr: false` because it reads `window` on mount.
 */
const showSwitcher =
  process.env.NODE_ENV !== "production" || process.env.NEXT_PUBLIC_RESPONSIVE_SWITCHER === "1";

const ResponsiveSwitcher = showSwitcher
  ? dynamic(() => import("@/components/dev/ResponsiveSwitcher").then((m) => m.ResponsiveSwitcher), {
      ssr: false
    })
  : () => null;

/**
 * Everything that belongs to every screen.
 *
 * Today's plan is not mounted here: it rides in the app bar (`AppShell`), where
 * it sits in the row a child already reads for their stars and cannot drift
 * over an activity.
 *
 * `ResponsiveSwitcher` is the one exception to "everything here is for the
 * child": it is a testing overlay that renders nothing at all in a production
 * build, and nothing inside its own frame. It is mounted here rather than in
 * `AppShell` so it is reachable on the screens with no app bar: the guest hub,
 * onboarding, and the class itself.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <AvatarProvider>
      {children}
      <ResponsiveSwitcher />
    </AvatarProvider>
  );
}
