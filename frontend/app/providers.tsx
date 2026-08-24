"use client";

import { AvatarProvider } from "@/components/avatar/AvatarProvider";

/**
 * Everything that belongs to every screen.
 *
 * Today's plan is not mounted here: it rides in the app bar (`AppShell`), where
 * it sits in the row a child already reads for their stars and cannot drift
 * over an activity.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return <AvatarProvider>{children}</AvatarProvider>;
}
