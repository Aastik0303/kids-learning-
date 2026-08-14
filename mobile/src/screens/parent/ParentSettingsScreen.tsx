import { useState } from "react";
import { Pressable, Switch, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { env } from "@/config/env";
import { allFlags, isEnabled, setFlag, type FeatureFlag } from "@/config/featureFlags";
import { ageGroupFor, useChildStore } from "@/store/childStore";
import { useAuthStore } from "@/store/authStore";
import { useAudioStore } from "@/store/audioStore";
import type { ParentStackParamList } from "@/navigation/routes";

const AGES = [1, 2, 3, 4, 5, 6] as const;
const LANGUAGES = ["English", "Hindi", "Spanish", "French"] as const;

/**
 * Parent settings (spec section 19): the child's age and language, voice
 * behaviour, and — in development builds — the feature flag panel.
 *
 * Changing age here is significant: it can move the child between toddler
 * and early learner mode, so the consequence is spelled out.
 */
export function ParentSettingsScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ParentStackParamList>>();

  const child = useChildStore((state) => state.activeChild);
  const updateChild = useChildStore((state) => state.updateChild);
  const sessionToken = useAuthStore((state) => state.sessionToken);
  const logout = useAuthStore((state) => state.logout);

  const muted = useAudioStore((state) => state.muted);
  const voiceProvider = useAudioStore((state) => state.voiceProvider);

  // Local mirror so flag switches re-render immediately.
  const [flags, setFlags] = useState(allFlags());

  if (!child) return null;

  const toggleFlag = (flag: FeatureFlag) => {
    setFlag(flag, !isEnabled(flag));
    setFlags(allFlags());
  };

  return (
    <Screen backdrop={false}>
      <View style={{ gap: theme.space[6] }}>
        {/* Child */}
        <Card variant="lift" style={{ gap: theme.space[4] }}>
          <Text variant="heading">{child.name}</Text>

          <View style={{ gap: theme.space[2] }}>
            <Text variant="label">Age</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: theme.space[2] }}>
              {AGES.map((age) => (
                <Pressable
                  key={age}
                  accessibilityRole="button"
                  accessibilityLabel={`Set age to ${age}`}
                  accessibilityState={{ selected: child.age === age }}
                  onPress={() => sessionToken && void updateChild({ sessionToken, age })}
                  style={{
                    width: 52,
                    height: 52,
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: theme.radius.md,
                    borderWidth: child.age === age ? 3 : 1,
                    borderColor: child.age === age ? theme.colors.primary : theme.colors.border,
                    backgroundColor: child.age === age ? theme.colors.successSoft : theme.colors.surface,
                  }}
                >
                  <Text variant="subheading">{age}</Text>
                </Pressable>
              ))}
            </View>
            <Text variant="caption" muted>
              Currently in the {ageGroupFor(child.age ?? 3)} band. Under 3 uses toddler mode,
              which shows one activity at a time and hides navigation.
            </Text>
          </View>

          <View style={{ gap: theme.space[2] }}>
            <Text variant="label">Language</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: theme.space[2] }}>
              {LANGUAGES.map((language) => (
                <Button
                  key={language}
                  label={language}
                  tone={child.preferred_language === language ? "primary" : "quiet"}
                  size="parent"
                  fullWidth={false}
                  onPress={() =>
                    sessionToken && void updateChild({ sessionToken, preferredLanguage: language })
                  }
                />
              ))}
            </View>
          </View>
        </Card>

        {/* Voice */}
        <Card variant="lift" style={{ gap: theme.space[3] }}>
          <Text variant="heading">Voice</Text>

          <SettingRow
            label="Guide speaks out loud"
            hint="Turn off for quiet play."
            value={!muted}
            onChange={() => useAudioStore.getState().toggleMute()}
          />

          <SettingRow
            label="Use the premium voice"
            hint="Needs a voice key on the server. Falls back to the device voice."
            value={voiceProvider === "hosted"}
            onChange={() =>
              useAudioStore.getState().setVoiceProvider(voiceProvider === "hosted" ? "device" : "hosted")
            }
          />
        </Card>

        {/* Dev-only flags */}
        {env.isDev ? (
          <Card variant="flat" style={{ gap: theme.space[2] }}>
            <Text variant="heading">Feature flags</Text>
            <Text variant="caption" muted>
              Development builds only. Not shown in production.
            </Text>
            {(Object.keys(flags) as FeatureFlag[]).map((flag) => (
              <SettingRow
                key={flag}
                label={flag}
                value={flags[flag]}
                onChange={() => toggleFlag(flag)}
              />
            ))}
          </Card>
        ) : null}

        <Card variant="flat" style={{ gap: theme.space[2] }}>
          <Text variant="label">About</Text>
          <Text variant="caption" muted>
            Version {env.appVersion} · API {env.apiBaseUrl}
          </Text>
          <Text variant="caption" muted>
            Prototype build. No real personal data should be entered.
          </Text>
        </Card>

        <Button
          label="Sign out"
          tone="danger"
          size="parent"
          onPress={() => {
            void logout();
            navigation.popToTop();
          }}
        />
      </View>
    </Screen>
  );
}

function SettingRow({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint?: string;
  value: boolean;
  onChange: () => void;
}) {
  const theme = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[3] }}>
      <View style={{ flex: 1 }}>
        <Text variant="body">{label}</Text>
        {hint ? (
          <Text variant="caption" muted>
            {hint}
          </Text>
        ) : null}
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        accessibilityLabel={label}
        trackColor={{ true: theme.colors.primary, false: theme.colors.starTrack }}
      />
    </View>
  );
}
