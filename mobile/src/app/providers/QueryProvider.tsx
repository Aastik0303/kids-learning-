import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { ApiError } from "@/services/api/client";
import { track } from "@/services/analytics/analytics";

/**
 * TanStack Query owns server state (spec section 17); Zustand owns local
 * app/UI/session state. The split is strict — no server payload is copied
 * into a store unless the app genuinely needs to mutate it locally.
 */
export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Curriculum barely changes; child progress is refetched
            // explicitly after a lesson rather than polled.
            staleTime: 5 * 60 * 1000,
            gcTime: 30 * 60 * 1000,
            retry: (failureCount, error) => {
              // Never retry a 404/401 — it will never succeed.
              if (error instanceof ApiError && !error.isRetryable) return false;
              return failureCount < 2;
            },
            retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 5000),
            refetchOnWindowFocus: false,
          },
          mutations: {
            onError: (error) => {
              if (error instanceof ApiError) {
                track("network_error", { kind: error.kind, path: error.code });
              }
            },
          },
        },
      }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
