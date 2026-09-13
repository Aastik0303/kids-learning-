import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/services/api/client";
import { track } from "@/services/analytics/analytics";

/**
 * The one query client, as a module rather than as component state.
 *
 * TanStack Query owns server state and Zustand owns local state; that split is
 * unchanged. What this adds is a way to *invalidate* from outside the tree,
 * which the class needs: finishing a stage moves the child's stars, the day's
 * plan and the Adventure board all at once, on the server, and the copies every
 * other screen is holding are stale from that moment. The class is not a
 * component those screens can hand a callback to.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Curriculum barely changes; child progress is refetched explicitly after
      // a lesson rather than polled.
      staleTime: 5 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
      retry: (failureCount, error) => {
        // Never retry a 404/401 - it will never succeed.
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
});
