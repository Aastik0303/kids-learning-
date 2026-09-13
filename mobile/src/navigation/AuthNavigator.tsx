import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { LoginScreen } from "@/screens/auth/LoginScreen";
import { VerifyCodeScreen } from "@/screens/auth/VerifyCodeScreen";
import { SignUpScreen } from "@/screens/auth/SignUpScreen";
import { ChildSelectScreen } from "@/screens/auth/ChildSelectScreen";
import { ChildSetupScreen } from "@/screens/auth/ChildSetupScreen";
import { useAuthStore } from "@/store/authStore";
import { useChildStore } from "@/store/childStore";
import type { AuthStackParamList } from "@/navigation/routes";

const Stack = createNativeStackNavigator<AuthStackParamList>();

/**
 * Parent-facing auth plus child profile setup.
 *
 * The initial route is computed rather than fixed: a signed-in parent with
 * no child lands on setup, a signed-in parent with children lands on
 * select, and everyone else starts at login. That is what makes a
 * preserved feature intent resume cleanly after the shortest possible path.
 */
export function AuthNavigator() {
  const status = useAuthStore((state) => state.status);
  const children = useChildStore((state) => state.children);

  const initialRoute: keyof AuthStackParamList =
    status === "authenticated" ? (children.length > 0 ? "ChildSelect" : "ChildSetup") : "Login";

  return (
    <Stack.Navigator
      initialRouteName={initialRoute}
      screenOptions={{ headerShown: false, animation: "slide_from_right" }}
    >
      <Stack.Screen name="Login" component={LoginScreen} />
      <Stack.Screen name="VerifyCode" component={VerifyCodeScreen} />
      <Stack.Screen name="SignUp" component={SignUpScreen} />
      <Stack.Screen name="ChildSelect" component={ChildSelectScreen} />
      <Stack.Screen name="ChildSetup" component={ChildSetupScreen} />
    </Stack.Navigator>
  );
}
