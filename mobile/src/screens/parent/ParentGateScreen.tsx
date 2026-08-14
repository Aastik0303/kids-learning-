import { useMemo, useState } from "react";
import { Pressable, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { haptics } from "@/services/audio/haptics";
import { useUiStore } from "@/store/uiStore";
import type { ParentStackParamList } from "@/navigation/routes";

/**
 * Parent gate (spec section 19).
 *
 * A written-word arithmetic challenge: readable by an adult, effectively
 * impossible for a 2–5 year old who cannot yet read number words. This is
 * a child-accident barrier, not a security control — it is not protecting
 * anything sensitive, only preventing a toddler wandering into settings.
 */
export function ParentGateScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ParentStackParamList>>();
  const unlockParent = useUiStore((state) => state.unlockParent);

  const [attempted, setAttempted] = useState(false);

  // A fixed challenge per mount — regenerating on each wrong tap would be
  // needlessly punishing for a parent who simply mis-tapped.
  const challenge = useMemo(() => buildChallenge(), []);

  const answer = (choice: number) => {
    haptics.tap();
    if (choice === challenge.answer) {
      unlockParent();
      navigation.replace("ParentDashboard");
      return;
    }
    setAttempted(true);
  };

  return (
    <Screen>
      <View style={{ gap: theme.space[6], flex: 1, justifyContent: "center" }}>
        <View style={{ alignItems: "center", gap: theme.space[2] }}>
          <Text style={{ fontSize: 48 }}>🔐</Text>
          <Text variant="title" align="center">
            For grown-ups
          </Text>
          <Text variant="body" align="center" muted>
            Answer this to continue.
          </Text>
        </View>

        <Card variant="panel" style={{ gap: theme.space[5] }}>
          <Text variant="heading" align="center">
            {challenge.prompt}
          </Text>

          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: theme.space[3], justifyContent: "center" }}>
            {challenge.options.map((option) => (
              <Pressable
                key={option}
                accessibilityRole="button"
                accessibilityLabel={String(option)}
                onPress={() => answer(option)}
                style={{
                  width: 76,
                  height: 76,
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: theme.radius.lg,
                  borderWidth: 2,
                  borderColor: theme.colors.border,
                  backgroundColor: theme.colors.surface,
                }}
              >
                <Text variant="heading">{option}</Text>
              </Pressable>
            ))}
          </View>

          {attempted ? (
            <Text variant="body" align="center" color={theme.colors.dangerStrong}>
              Not quite. Please try again.
            </Text>
          ) : null}
        </Card>

        <Button label="Back to learning" tone="quiet" size="parent" onPress={() => navigation.goBack()} />
      </View>
    </Screen>
  );
}

const NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];

function buildChallenge(): { prompt: string; answer: number; options: number[] } {
  // Deliberately small operands — this must be trivial for any adult.
  const a = 3 + Math.floor(Math.random() * 5);
  const b = 2 + Math.floor(Math.random() * 4);
  const answer = a + b;

  const options = new Set<number>([answer]);
  while (options.size < 4) {
    const distractor = answer + (Math.floor(Math.random() * 7) - 3);
    if (distractor > 0 && distractor !== answer) options.add(distractor);
  }

  return {
    // Written as words so a pre-reader cannot brute-force it visually.
    prompt: `What is ${NUMBER_WORDS[a]} plus ${NUMBER_WORDS[b]}?`,
    answer,
    options: Array.from(options).sort(() => Math.random() - 0.5),
  };
}
