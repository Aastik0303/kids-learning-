import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { ParentGateScreen } from "@/screens/parent/ParentGateScreen";
import { ParentDashboardScreen } from "@/screens/parent/ParentDashboardScreen";
import { ParentProgressScreen } from "@/screens/parent/ParentProgressScreen";
import { ParentSettingsScreen } from "@/screens/parent/ParentSettingsScreen";
import { useUiStore } from "@/store/uiStore";
import type { ParentStackParamList } from "@/navigation/routes";

const Stack = createNativeStackNavigator<ParentStackParamList>();

/**
 * Parent area, kept structurally separate from child navigation
 * (spec section 19). The gate is the entry point whenever the session is
 * locked, and it re-arms when the app is backgrounded.
 */
export function ParentNavigator() {
  const isUnlocked = useUiStore((state) => state.isParentUnlocked);

  return (
    <Stack.Navigator
      initialRouteName={isUnlocked ? "ParentDashboard" : "ParentGate"}
      screenOptions={{
        headerShown: true,
        headerBackButtonDisplayMode: "minimal",
        animation: "slide_from_right",
      }}
    >
      <Stack.Screen
        name="ParentGate"
        component={ParentGateScreen}
        options={{ title: "For grown-ups", headerShown: false }}
      />
      <Stack.Screen
        name="ParentDashboard"
        component={ParentDashboardScreen}
        options={{ title: "Dashboard" }}
      />
      <Stack.Screen
        name="ParentProgress"
        component={ParentProgressScreen}
        options={{ title: "Progress" }}
      />
      <Stack.Screen
        name="ParentSettings"
        component={ParentSettingsScreen}
        options={{ title: "Settings" }}
      />
    </Stack.Navigator>
  );
}
