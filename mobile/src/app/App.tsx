import { useEffect } from "react";
import { View } from "react-native";
import { StatusBar } from "expo-status-bar";
import * as SplashScreen from "expo-splash-screen";

import { AppProviders } from "@/app/providers/AppProviders";
import { useAppBootstrap } from "@/app/bootstrap/useAppBootstrap";
import { CelebrationOverlay } from "@/components/common/CelebrationOverlay";
import { OfflineBanner } from "@/components/common/OfflineBanner";
import { LoadingState } from "@/components/common/StateViews";
import { RootNavigator } from "@/navigation/RootNavigator";
import { palette } from "@/theme/colors";

// Hold the splash until bootstrap finishes, so a child never sees a
// half-restored session flash past.
void SplashScreen.preventAutoHideAsync();

export default function App() {
  return (
    <AppProviders>
      <AppShell />
      <StatusBar style="dark" />
    </AppProviders>
  );
}

function AppShell() {
  const { isReady } = useAppBootstrap();

  useEffect(() => {
    if (isReady) void SplashScreen.hideAsync();
  }, [isReady]);

  if (!isReady) {
    return (
      <View style={{ flex: 1, backgroundColor: palette.paper, justifyContent: "center" }}>
        <LoadingState message="Waking up your guide…" />
      </View>
    );
  }

  return (
    <View style={{ flex: 1 }}>
      <RootNavigator />
      {/* Both sit above the navigator so they cover every screen. */}
      <OfflineBanner />
      <CelebrationOverlay />
    </View>
  );
}
