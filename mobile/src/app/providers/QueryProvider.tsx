import type { ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import { queryClient } from "@/services/queryClient";

/**
 * TanStack Query owns server state (spec section 17); Zustand owns local
 * app/UI/session state. The split is strict - no server payload is copied into
 * a store unless the app genuinely needs to mutate it locally.
 *
 * The client itself lives in `services/queryClient` rather than in this
 * component's state, so code outside the tree can invalidate what it has just
 * made stale - see `announcePlanChanged`, which the class calls when finishing
 * a stage moves the day's plan and the child's stars on the server.
 */
export function QueryProvider({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
