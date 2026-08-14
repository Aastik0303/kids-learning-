import { useEffect } from "react";
import { NavigationContainer, DefaultTheme, type Theme as NavTheme } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { AvatarDock } from "@/components/avatar/AvatarDock";
import { DoubtOverlay } from "@/features/guide/DoubtOverlay";
import { GuestNavigator } from "@/navigation/GuestNavigator";
import { AuthNavigator } from "@/navigation/AuthNavigator";
import { ChildNavigator } from "@/navigation/ChildNavigator";
import { ParentNavigator } from "@/navigation/ParentNavigator";
import { navigationRef } from "@/navigation/navigationRef";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useAuthStore } from "@/store/authStore";
import { useChildStore } from "@/store/childStore";
import type { RootStackParamList } from "@/navigation/routes";

const Stack = createNativeStackNavigator<RootStackParamList>();

/**
 * Root navigation (spec section 21).
 *
 * The guest surface is always mounted first so an unauthenticated visitor
 * gets the full showcase home. Auth, child and parent are pushed on top —
 * which is what allows a preserved feature intent to resume by popping
 * back to exactly where the child was heading.
 *
 * The avatar dock and doubt overlay live *outside* the navigator so the
 * AI companion persists across every child screen change (spec section 8).
 */
export function RootNavigator() {
  const theme = useTheme();
  const status = useAuthStore((state) => state.status);
  const activeChild = useChildStore((state) => state.activeChild);
  const sessionToken = useAuthStore((state) => state.sessionToken);
  const loadChildren = useChildStore((state) => state.loadChildren);

  // Pull the parent's children as soon as we have a validated session.
  useEffect(() => {
    if (status === "authenticated" && sessionToken) {
      void loadChildren(sessionToken);
    }
  }, [status, sessionToken, loadChildren]);

  const isInChildExperience = status === "authenticated" && !!activeChild;

  const navTheme: NavTheme = {
    ...DefaultTheme,
    colors: {
      ...DefaultTheme.colors,
      primary: theme.colors.primary,
      background: theme.colors.background,
      card: theme.colors.surface,
      text: theme.colors.text,
      border: theme.colors.border,
    },
  };

  return (
    <NavigationContainer ref={navigationRef} theme={navTheme}>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        {isInChildExperience ? (
          <>
            <Stack.Screen name="Child" component={ChildNavigator} />
            <Stack.Screen
              name="Parent"
              component={ParentNavigator}
              options={{ presentation: "modal" }}
            />
            {/* Still reachable so a parent can add or switch children. */}
            <Stack.Screen
              name="Auth"
              component={AuthNavigator}
              options={{ presentation: "modal" }}
            />
          </>
        ) : (
          <>
            <Stack.Screen name="Guest" component={GuestNavigator} />
            <Stack.Screen name="Auth" component={AuthNavigator} />
          </>
        )}
      </Stack.Navigator>

      {/* Global AI layer — deliberately outside the navigator. */}
      <AvatarDock visible={isInChildExperience} />
      <DoubtOverlay />
    </NavigationContainer>
  );
}
