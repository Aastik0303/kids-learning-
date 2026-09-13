import { useState } from "react";
import { KeyboardAvoidingView, Platform, TextInput, View } from "react-native";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";

export type AuthFormValues = { name: string; email: string; password: string };

export type AuthFormProps = {
  mode: "login" | "register";
  isSubmitting: boolean;
  error: string | null;
  onSubmit: (values: AuthFormValues) => void;
};

/**
 * Parent-facing sign in / sign up. Deliberately plain and dense — this is
 * the one surface an adult uses, and it should feel like a normal form
 * rather than a child's screen.
 */
export function AuthForm({ mode, isSubmitting, error, onSubmit }: AuthFormProps) {
  const theme = useTheme();
  const [values, setValues] = useState<AuthFormValues>({ name: "", email: "", password: "" });
  const [touched, setTouched] = useState(false);

  const isRegister = mode === "register";
  const emailValid = /.+@.+\..+/.test(values.email.trim());
  // Eight, matching the server. A form that accepts four only turns a
  // rejected password into a 422 the parent cannot read.
  const passwordValid = values.password.length >= (isRegister ? 8 : 4);
  const nameValid = !isRegister || values.name.trim().length > 0;
  const canSubmit = emailValid && passwordValid && nameValid && !isSubmitting;

  const field = (
    label: string,
    key: keyof AuthFormValues,
    options: {
      placeholder: string;
      secure?: boolean;
      keyboard?: "email-address" | "default";
      autoComplete?: "email" | "password" | "name" | "new-password";
      invalid?: boolean;
      hint?: string;
    },
  ) => (
    <View style={{ gap: theme.space[1] }}>
      <Text variant="label">{label}</Text>
      <TextInput
        value={values[key]}
        onChangeText={(text) => setValues((current) => ({ ...current, [key]: text }))}
        placeholder={options.placeholder}
        placeholderTextColor={theme.colors.textDisabled}
        secureTextEntry={options.secure}
        keyboardType={options.keyboard ?? "default"}
        autoCapitalize={key === "name" ? "words" : "none"}
        autoCorrect={false}
        autoComplete={options.autoComplete}
        accessibilityLabel={label}
        style={{
          minHeight: theme.touchTarget.parent,
          borderRadius: theme.radius.md,
          borderWidth: 2,
          borderColor:
            touched && options.invalid ? theme.colors.danger : theme.colors.borderStrong,
          backgroundColor: theme.colors.surface,
          paddingHorizontal: theme.space[3],
          color: theme.colors.text,
          fontSize: 16,
          fontWeight: "700",
        }}
      />
      {touched && options.invalid && options.hint ? (
        <Text variant="caption" color={theme.colors.dangerStrong}>
          {options.hint}
        </Text>
      ) : null}
    </View>
  );

  return (
    <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <Card variant="panel" style={{ gap: theme.space[4] }}>
        {isRegister
          ? field("Your name", "name", {
              placeholder: "Parent or carer name",
              autoComplete: "name",
              invalid: !nameValid,
              hint: "Please tell us your name.",
            })
          : null}

        {field("Email", "email", {
          placeholder: "you@example.com",
          keyboard: "email-address",
          autoComplete: "email",
          invalid: !emailValid,
          hint: "That does not look like an email address.",
        })}

        {field("Password", "password", {
          placeholder: isRegister ? "At least 8 characters" : "Your password",
          secure: true,
          autoComplete: isRegister ? "new-password" : "password",
          invalid: !passwordValid,
          hint: isRegister ? "Use at least 8 characters." : "Enter your password.",
        })}

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

        <Button
          label={isRegister ? "Create account" : "Sign in"}
          tone="primary"
          size="parent"
          loading={isSubmitting}
          onPress={() => {
            setTouched(true);
            if (canSubmit) onSubmit(values);
          }}
        />
      </Card>
    </KeyboardAvoidingView>
  );
}
