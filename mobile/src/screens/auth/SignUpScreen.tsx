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

export function SignUpScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<AuthStackParamList>>();

  const register = useAuthStore((state) => state.register);
  const isSubmitting = useAuthStore((state) => state.isSubmitting);
  const error = useAuthStore((state) => state.error);
  const clearError = useAuthStore((state) => state.clearError);
  const pendingIntent = useAuthStore((state) => state.pendingIntent);

  const submit = useCallback(
    async ({ name, email, password }: { name: string; email: string; password: string }) => {
      const ok = await register(name.trim(), email.trim(), password);
      // A brand new account has no children yet — go straight to setup.
      if (ok) navigation.navigate("ChildSetup");
    },
    [register, navigation],
  );

  return (
    <Screen>
      <View style={{ gap: theme.space[6] }}>
        <View style={{ alignItems: "center", gap: theme.space[3] }}>
          <AvatarFace state="happy" size={96} />
          <Text variant="title" align="center">
            Let us get started
          </Text>
          {pendingIntent ? (
            <Pill label={`Next: ${pendingIntent.label}`} icon="➡️" tone="accent" />
          ) : (
            <Text variant="body" align="center" muted>
              Create a grown-up account, then set up your child.
            </Text>
          )}
        </View>

        <AuthForm
          mode="register"
          isSubmitting={isSubmitting}
          error={error}
          onSubmit={(values) => void submit(values)}
        />

        <Button
          label="I already have an account"
          tone="quiet"
          size="parent"
          onPress={() => {
            clearError();
            navigation.navigate("Login");
          }}
        />
      </View>
    </Screen>
  );
}
