import { useCallback } from "react";
import { View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { AuthForm } from "@/screens/auth/AuthForm";
import { AvatarFace } from "@/components/avatar/AvatarFace";
import { Button } from "@/components/common/Button";
import { Pill } from "@/components/common/StateViews";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useAuthStore } from "@/store/authStore";
import type { AuthStackParamList } from "@/navigation/routes";

export function LoginScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<AuthStackParamList>>();

  const login = useAuthStore((state) => state.login);
  const isSubmitting = useAuthStore((state) => state.isSubmitting);
  const error = useAuthStore((state) => state.error);
  const clearError = useAuthStore((state) => state.clearError);
  const pendingIntent = useAuthStore((state) => state.pendingIntent);

  const submit = useCallback(
    async ({ email, password }: { email: string; password: string }) => {
      const result = await login(email.trim(), password);
      // A right password is not necessarily a session any more: where the
      // emailed code is on, the server answers with a challenge and the code
      // screen is what finishes the sign-in.
      if (result === "code-sent") {
        navigation.navigate("VerifyCode");
        return;
      }
      // On success RootNavigator swaps stacks once a child is selected;
      // AuthNavigator's computed initial route handles the middle step.
      if (result === "signed-in") navigation.navigate("ChildSelect");
    },
    [login, navigation],
  );

  return (
    <Screen>
      <View style={{ gap: theme.space[6] }}>
        <View style={{ alignItems: "center", gap: theme.space[3] }}>
          <AvatarFace state="waving" size={96} />
          <Text variant="title" align="center">
            Welcome back
          </Text>

          {/* Tells the parent exactly what they are returning to. */}
          {pendingIntent ? (
            <Pill label={`Next: ${pendingIntent.label}`} icon="➡️" tone="accent" />
          ) : (
            <Text variant="body" align="center" muted>
              Sign in to continue your child's learning.
            </Text>
          )}
        </View>

        <AuthForm
          mode="login"
          isSubmitting={isSubmitting}
          error={error}
          onSubmit={({ email, password }) => void submit({ email, password })}
        />

        <Button
          label="Create a new account"
          tone="quiet"
          size="parent"
          onPress={() => {
            clearError();
            navigation.navigate("SignUp");
          }}
        />
      </View>
    </Screen>
  );
}
