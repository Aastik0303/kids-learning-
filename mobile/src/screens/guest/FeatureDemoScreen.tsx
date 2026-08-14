import { useCallback, useState } from "react";
import { View } from "react-native";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { AvatarFace } from "@/components/avatar/AvatarFace";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Pill } from "@/components/common/StateViews";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { FEATURES, featureById } from "@/features/catalog";
import { classVisual } from "@/theme/colors";
import { tts } from "@/services/audio/tts";
import { useAuthStore } from "@/store/authStore";
import { track } from "@/services/analytics/analytics";
import type { GuestStackParamList, RootStackParamList } from "@/navigation/routes";

type Navigation = NativeStackNavigationProp<GuestStackParamList> &
  NativeStackNavigationProp<RootStackParamList>;

/**
 * A no-signup preview of how the AI teaches one feature (spec section 2).
 *
 * Everything here is scripted and local — no backend, no account. It only
 * has to answer "what will this actually be like for my child?" before a
 * parent commits to creating a profile.
 */
export function FeatureDemoScreen() {
  const theme = useTheme();
  const navigation = useNavigation<Navigation>();
  const route = useRoute<RouteProp<GuestStackParamList, "FeatureDemo">>();
  const setPendingIntent = useAuthStore((state) => state.setPendingIntent);

  const [selectedId, setSelectedId] = useState(route.params?.featureId ?? "alphabets");
  const [spokenLine, setSpokenLine] = useState<string | null>(null);

  const feature = featureById(selectedId) ?? FEATURES[0]!;
  const visual = classVisual(feature.id);
  const script = DEMO_SCRIPTS[feature.interaction];

  const playLine = useCallback(async (line: string) => {
    setSpokenLine(line);
    // Device TTS only — the demo must work with no backend running.
    await tts.speak(line, "device");
    setSpokenLine(null);
  }, []);

  const startForReal = useCallback(() => {
    track("feature_card_tapped", { feature: feature.id, authenticated: false });
    setPendingIntent({
      screen: "Classes",
      params: { featureId: feature.id },
      label: feature.title,
    });
    navigation.navigate("Auth", { screen: "SignUp" });
  }, [feature.id, feature.title, navigation, setPendingIntent]);

  return (
    <Screen>
      <View style={{ gap: theme.space[6] }}>
        <Button
          label="Back"
          icon="←"
          tone="quiet"
          fullWidth={false}
          onPress={() => navigation.goBack()}
        />

        {/* ── Feature picker ─────────────────────────────────────────── */}
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: theme.space[2] }}>
          {FEATURES.map((item) => (
            <Button
              key={item.id}
              label={item.title}
              tone={item.id === feature.id ? "primary" : "quiet"}
              size="parent"
              fullWidth={false}
              onPress={() => setSelectedId(item.id)}
            />
          ))}
        </View>

        {/* ── The demo itself ────────────────────────────────────────── */}
        <Card variant="panel" style={{ gap: theme.space[5] }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[3] }}>
            <Text style={{ fontSize: 42 }}>{visual.icon}</Text>
            <View style={{ flex: 1 }}>
              <Text variant="heading">{feature.title}</Text>
              <Text variant="body" muted>
                {feature.description}
              </Text>
            </View>
          </View>

          <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[3] }}>
            <AvatarFace state={spokenLine ? "speaking" : "idle"} size={76} />
            <View
              style={{
                flex: 1,
                minHeight: 72,
                justifyContent: "center",
                borderRadius: theme.radius.xl,
                backgroundColor: theme.palette.leafLight,
                padding: theme.space[3],
              }}
            >
              <Text variant="body">{spokenLine ?? script.idle}</Text>
            </View>
          </View>

          <View style={{ gap: theme.space[2] }}>
            <Text variant="overline" muted>
              What the guide does
            </Text>
            {script.beats.map((beat) => (
              <View
                key={beat.line}
                style={{ flexDirection: "row", alignItems: "center", gap: theme.space[3] }}
              >
                <Pill label={beat.label} icon={beat.icon} tone="accent" />
                <View style={{ flex: 1 }}>
                  <Button
                    label={`"${beat.line}"`}
                    tone="quiet"
                    size="parent"
                    onPress={() => void playLine(beat.line)}
                  />
                </View>
              </View>
            ))}
          </View>

          <Text variant="caption" muted align="center">
            Tap a line to hear it out loud.
          </Text>
        </Card>

        {feature.pathId === null ? (
          <Card variant="tinted" tint={theme.palette.sunLight} style={{ gap: theme.space[2] }}>
            <Text variant="subheading">Coming to lessons soon</Text>
            <Text variant="body" muted>
              {feature.title} works as a practice activity today. Full lessons for it are
              on the way.
            </Text>
          </Card>
        ) : null}

        <Button label={`Try ${feature.title} for real`} icon="🚀" tone="primary" onPress={startForReal} />
      </View>
    </Screen>
  );
}

/** Scripted previews, one per interaction style. */
const DEMO_SCRIPTS: Record<
  "voice" | "tap" | "draw" | "listen",
  { idle: string; beats: Array<{ icon: string; label: string; line: string }> }
> = {
  voice: {
    idle: "I teach by talking with your child.",
    beats: [
      { icon: "🗣️", label: "Says", line: "This is the letter A. A is for apple." },
      { icon: "👂", label: "Listens", line: "Now you say it. A!" },
      { icon: "🎉", label: "Cheers", line: "Yes! That is right! Well done!" },
    ],
  },
  tap: {
    idle: "I show things and ask your child to pick.",
    beats: [
      { icon: "👀", label: "Shows", line: "Look! Here are three red apples." },
      { icon: "👉", label: "Points", line: "Can you tap the number three?" },
      { icon: "💡", label: "Helps", line: "Let us count together. One, two, three." },
    ],
  },
  draw: {
    idle: "I guide your child's finger along the line.",
    beats: [
      { icon: "🟢", label: "Starts", line: "Start at the green dot." },
      { icon: "✏️", label: "Guides", line: "Now follow the dots all the way down." },
      { icon: "🌟", label: "Praises", line: "Beautiful tracing! You did it!" },
    ],
  },
  listen: {
    idle: "I read gentle little stories out loud.",
    beats: [
      { icon: "📖", label: "Reads", line: "Once upon a time, a little bear found a red balloon." },
      { icon: "❓", label: "Asks", line: "What colour was the balloon?" },
      { icon: "🤗", label: "Warms", line: "That is right. Red! What a good listener." },
    ],
  },
};
