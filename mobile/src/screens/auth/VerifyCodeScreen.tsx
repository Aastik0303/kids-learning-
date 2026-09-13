import { useCallback, useEffect, useState } from "react";
import { TextInput, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { AvatarFace } from "@/components/avatar/AvatarFace";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useAuthStore } from "@/store/authStore";
import type { AuthStackParamList } from "@/navigation/routes";

/**
 * The second step of signing in: the code emailed to the account's address.
 *
 * The password proved what the parent knows; this proves they still hold the
 * address the account is on. Three things on the screen and no more - where the
 * code went, a box for it, and a way to ask for another - because this is a
 * phone held one-handed with a toddler already asking for the panda.
 *
 * `textContentType="oneTimeCode"` on iOS and `autoComplete="sms-otp"` on
 * Android are what make it one tap from the notification instead of six taps
 * and a typo.
 */
export function VerifyCodeScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<AuthStackParamList>>();

  const challenge = useAuthStore((state) => state.pendingChallenge);
  const verifyCode = useAuthStore((state) => state.verifyCode);
  const resendCode = useAuthStore((state) => state.resendCode);
  const clearChallenge = useAuthStore((state) => state.clearChallenge);
  const isSubmitting = useAuthStore((state) => state.isSubmitting);
  const error = useAuthStore((state) => state.error);

  const [code, setCode] = useState(challenge?.dev_code ?? "");
  const [note, setNote] = useState<string | null>(null);
  const [waitFor, setWaitFor] = useState(challenge?.resend_after ?? 60);

  // The server owns the cooldown; this only mirrors it, so pressing early is
  // refused by the thing that actually knows.
  useEffect(() => {
    if (waitFor <= 0) return;
    const timer = setInterval(() => setWaitFor((left) => Math.max(0, left - 1)), 1000);
    return () => clearInterval(timer);
  }, [waitFor]);

  const submit = useCallback(async () => {
    const ok = await verifyCode(code);
    if (ok) navigation.navigate("ChildSelect");
  }, [code, navigation, verifyCode]);

  const again = useCallback(async () => {
    const message = await resendCode();
    if (message) {
      setNote(message);
      setWaitFor(useAuthStore.getState().pendingChallenge?.resend_after ?? 60);
      setCode(useAuthStore.getState().pendingChallenge?.dev_code ?? "");
    }
  }, [resendCode]);

  // Landing here with nothing pending means the challenge was cleared under us
  // - a resume, or a sign-in that finished elsewhere. Start again rather than
  // showing a code box for a sign-in that no longer exists.
  if (!challenge) {
    return (
      <Screen>
        <Card variant="panel" style={{ gap: theme.space[4] }}>
          <Text variant="body">That sign-in has expired.</Text>
          <Button label="Sign in again" tone="primary" onPress={() => navigation.navigate("Login")} />
        </Card>
      </Screen>
    );
  }

  return (
    <Screen>
      <View style={{ gap: theme.space[6] }}>
        <View style={{ alignItems: "center", gap: theme.space[3] }}>
          <AvatarFace state="thinking" size={96} />
          <Text variant="title" align="center">
            Check your email
          </Text>
          <Text variant="body" align="center" muted>
            We sent a code to {challenge.email_hint}. It works for the next{" "}
            {Math.round(challenge.expires_in / 60)} minutes.
          </Text>
        </View>

        <Card variant="panel" style={{ gap: theme.space[4] }}>
          <Text variant="label">Your code</Text>
          <TextInput
            value={code}
            onChangeText={(text) => setCode(text.replace(/\D/g, "").slice(0, 6))}
            placeholder="000000"
            placeholderTextColor={theme.colors.textDisabled}
            keyboardType="number-pad"
            // Offered straight from the notification on both platforms.
            textContentType="oneTimeCode"
            autoComplete="sms-otp"
            maxLength={6}
            accessibilityLabel="The six-digit code we emailed you"
            style={{
              minHeight: theme.touchTarget.parent,
              borderRadius: theme.radius.md,
              borderWidth: 2,
              borderColor: theme.colors.borderStrong,
              backgroundColor: theme.colors.surface,
              color: theme.colors.text,
              fontSize: 28,
              fontWeight: "800",
              letterSpacing: 10,
              textAlign: "center",
            }}
          />

          {challenge.dev_code ? (
            <Text variant="caption" muted>
              No mail server is configured on this backend, so the code is filled in for you.
              This never happens in production.
            </Text>
          ) : null}

          {error ? (
            <View
              style={{
                borderRadius: theme.radius.md,
                backgroundColor: theme.colors.dangerSoft,
                padding: theme.space[3],
              }}
            >
              <Text variant="body" color={theme.colors.dangerStrong}>
                {error}
              </Text>
            </View>
          ) : null}

          {note ? (
            <Text variant="caption" muted>
              {note}
            </Text>
          ) : null}

          <Button
            label="Sign in"
            tone="primary"
            size="parent"
            loading={isSubmitting}
            onPress={() => {
              if (code.length >= 4) void submit();
            }}
          />

          <Button
            label={waitFor > 0 ? `Send it again in ${waitFor}s` : "Send it again"}
            tone="quiet"
            onPress={() => {
              if (waitFor <= 0) void again();
            }}
          />

          <Button
            label="Use a different account"
            tone="quiet"
            onPress={() => {
              clearChallenge();
              navigation.navigate("Login");
            }}
          />
        </Card>
      </View>
    </Screen>
  );
}
