import type { ReactNode } from "react";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { ErrorBoundary } from "@/app/providers/ErrorBoundary";
import { QueryProvider } from "@/app/providers/QueryProvider";
import { ThemeProvider } from "@/app/providers/ThemeProvider";
import { GuideProvider } from "@/ai/GuideProvider";
import { GuideTargetRegistryProvider } from "@/ai/GuideTargetRegistry";

/**
 * Provider stack. Order matters:
 *
 *   ErrorBoundary          outermost, so it can catch anything below it
 *   GestureHandlerRootView required at the root for gesture handling
 *   SafeAreaProvider       insets must exist before any layout
 *   ThemeProvider          everything visual depends on it
 *   QueryProvider          server state
 *   GuideTargetRegistry    must wrap GuideProvider — the provider reads it
 *   GuideProvider          the AI layer, innermost
 */
export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary>
      <GestureHandlerRootView style={{ flex: 1 }}>
        <SafeAreaProvider>
          <ThemeProvider>
            <QueryProvider>
              <GuideTargetRegistryProvider>
                <GuideProvider>{children}</GuideProvider>
              </GuideTargetRegistryProvider>
            </QueryProvider>
          </ThemeProvider>
        </SafeAreaProvider>
      </GestureHandlerRootView>
    </ErrorBoundary>
  );
}
