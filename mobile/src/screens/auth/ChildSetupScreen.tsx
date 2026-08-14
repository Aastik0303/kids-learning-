import { useCallback, useState } from "react";
import { Pressable, TextInput, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { AvatarFace } from "@/components/avatar/AvatarFace";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useAuthStore } from "@/store/authStore";
import { modeForAge, useChildStore } from "@/store/childStore";
import { haptics } from "@/services/audio/haptics";
import type { AuthStackParamList } from "@/navigation/routes";

const AGES = [1, 2, 3, 4, 5, 6] as const;

const LANGUAGES = ["English", "Hindi", "Spanish", "French"] as const;

/**
 * Child profile creation (spec section 3).
 *
 * Collects only what actually changes the experience: nickname, age and
 * language. Age is the important one — it decides toddler vs early
 * learner mode, and the preview below shows the parent what they are
 * choosing before they commit.
 */
export function ChildSetupScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<AuthStackParamList>>();

  const sessionToken = useAuthStore((state) => state.sessionToken);
  const createChild = useChildStore((state) => state.createChild);
  const isLoading = useChildStore((state) => state.isLoading);
  const error = useChildStore((state) => state.error);

  const [name, setName] = useState("");
  const [age, setAge] = useState<number>(3);
  const [language, setLanguage] = useState<string>("English");

  // Preview the mode this age will produce, using the same threshold the
  // app and the backend apply at runtime.
  const previewMode = modeForAge(age);

  const submit = useCallback(async () => {
    if (!sessionToken || !name.trim()) return;
    const child = await createChild({
      sessionToken,
      name: name.trim(),
      age,
      preferredLanguage: language,
    });
    // Success flips RootNavigator into the child experience; the pending
    // intent is replayed by the bootstrap effect there.
    if (!child) return;
  }, [sessionToken, name, age, language, createChild]);

  return (
    <Screen>
      <View style={{ gap: theme.space[6] }}>
        <View style={{ alignItems: "center", gap: theme.space[3] }}>
          <AvatarFace state="encouraging" size={96} />
          <Text variant="title" align="center">
            Who is learning?
          </Text>
          <Text variant="body" align="center" muted>
            Just a nickname is fine — please do not use a real full name.
          </Text>
        </View>

        <Card variant="panel" style={{ gap: theme.space[5] }}>
          {/* Nickname */}
          <View style={{ gap: theme.space[1] }}>
            <Text variant="label">Nickname</Text>
            <TextInput
              value={name}
              onChangeText={setName}
              placeholder="e.g. Bunny"
              placeholderTextColor={theme.colors.textDisabled}
              autoCapitalize="words"
              accessibilityLabel="Child nickname"
              style={{
                minHeight: theme.touchTarget.parent,
                borderRadius: theme.radius.md,
                borderWidth: 2,
                borderColor: theme.colors.borderStrong,
                backgroundColor: theme.colors.surface,
                paddingHorizontal: theme.space[3],
                color: theme.colors.text,
                fontSize: 16,
                fontWeight: "700",
              }}
            />
          </View>

          {/* Age */}
          <View style={{ gap: theme.space[2] }}>
            <Text variant="label">How old are they?</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: theme.space[2] }}>
              {AGES.map((option) => (
                <Pressable
                  key={option}
                  accessibilityRole="button"
                  accessibilityLabel={`${option} years old`}
                  accessibilityState={{ selected: option === age }}
                  onPress={() => {
                    haptics.tap();
                    setAge(option);
                  }}
                  style={{
                    width: 60,
                    height: 60,
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: theme.radius.lg,
                    borderWidth: option === age ? 3 : 1,
                    borderColor: option === age ? theme.colors.primary : theme.colors.border,
                    backgroundColor:
                      option === age ? theme.colors.successSoft : theme.colors.surface,
                  }}
                >
                  <Text variant="heading">{option}</Text>
                </Pressable>
              ))}
            </View>
          </View>

          {/* Language */}
          <View style={{ gap: theme.space[2] }}>
            <Text variant="label">Language</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: theme.space[2] }}>
              {LANGUAGES.map((option) => (
                <Button
                  key={option}
                  label={option}
                  tone={option === language ? "primary" : "quiet"}
                  size="parent"
                  fullWidth={false}
                  onPress={() => setLanguage(option)}
                />
              ))}
            </View>
          </View>

          {/* Mode preview — makes the age decision legible. */}
          <View
            style={{
              gap: theme.space[1],
              borderRadius: theme.radius.md,
              backgroundColor: theme.palette.sunLight,
              padding: theme.space[3],
            }}
          >
            <Text variant="label">
              {previewMode === "toddler" ? "🍼 Toddler mode" : "🎒 Early learner mode"}
            </Text>
            <Text variant="body" muted>
              {previewMode === "toddler"
                ? "One activity at a time. The guide leads everything with voice and big taps."
                : "Classes, practice and rewards to explore, with the guide recommending what is next."}
            </Text>
          </View>

          {error ? (
            <Text variant="body" color={theme.colors.dangerStrong}>
              {error}
            </Text>
          ) : null}

          <Button
            label="Start learning"
            icon="🚀"
            tone="primary"
            loading={isLoading}
            disabled={!name.trim()}
            onPress={() => void submit()}
          />
        </Card>

        <Button label="Back" tone="quiet" size="parent" onPress={() => navigation.goBack()} />
      </View>
    </Screen>
  );
}
