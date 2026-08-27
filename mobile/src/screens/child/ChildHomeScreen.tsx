import { useCallback, useEffect } from "react";
import { View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { useGuide } from "@/ai/GuideProvider";
import { AvatarFace } from "@/components/avatar/AvatarFace";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { FeatureCard } from "@/components/cards/FeatureCard";
import { GuideHighlight } from "@/components/common/GuideHighlight";
import { ResponsiveGrid } from "@/components/responsive/ResponsiveGrid";
import { Screen } from "@/components/common/Screen";
import { StarRow } from "@/components/common/StarRow";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { featuresForAge } from "@/features/catalog";
import { useRecommendation } from "@/features/learning/useRecommendation";
import { resolveExperienceMode, useChildStore } from "@/store/childStore";
import { useAuthStore } from "@/store/authStore";
import { classVisual } from "@/theme/colors";
import type { ChildStackParamList } from "@/navigation/routes";

/**
 * The logged-in child home (spec section 5).
 *
 * One dominant Continue CTA driven by the AI recommendation, with classes,
 * practice and rewards as secondary. In toddler mode almost all of this
 * collapses: the guide auto-starts and there is nothing else on screen.
 */
export function ChildHomeScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ChildStackParamList>>();
  const { dispatch } = useGuide();

  const child = useChildStore((state) => state.activeChild);
  const refresh = useChildStore((state) => state.refresh);
  const consumePendingIntent = useAuthStore((state) => state.consumePendingIntent);

  const recommendation = useRecommendation(child);
  const isToddler = resolveExperienceMode(child) === "toddler";

  // Greet once on arrival, and refresh the profile so stars are current.
  useEffect(() => {
    void dispatch("HOME_OPENED", { surface: "home" });
    void refresh();
    // Greeting should fire on mount only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Replay a preserved intent from the guest home. This is the last leg of
   * "feature tap → auth → child setup → the thing they actually wanted".
   */
  useEffect(() => {
    const intent = consumePendingIntent();
    if (!intent) return;

    const featureId = (intent.params as { featureId?: string } | undefined)?.featureId;
    if (featureId) {
      navigation.navigate("ClassDetail", { pathId: featureId });
    }
  }, [consumePendingIntent, navigation]);

  /**
   * Open today's class.
   *
   * No topic, no level and no mode are passed, and that is the point: which
   * lesson is played today is decided by the frozen daily plan on the server,
   * and handing it a path from here would be the app choosing. The card above
   * still uses `recommendation` for what it *says*, so the child sees what is
   * coming - but what actually opens is the conductor's own answer.
   */
  const startClass = useCallback(() => {
    navigation.navigate("Class");
  }, [navigation]);

  if (!child) return null;

  const visual = classVisual(recommendation?.pathId);

  // ── Toddler mode: one thing, nothing else ─────────────────────────────
  if (isToddler) {
    return (
      <Screen reserveDockSpace scroll={false}>
        <View style={{ flex: 1, justifyContent: "center", gap: theme.space[8] }}>
          <View style={{ alignItems: "center", gap: theme.space[4] }}>
            <AvatarFace state="waving" size={150} />
            <Text variant="title" align="center">
              Hello {child.name}!
            </Text>
          </View>

          <GuideHighlight targetId="continue-button" kind="control" label="Start learning button">
            <Button
              label="Let us play!"
              icon="🎈"
              tone="primary"
              size="toddler"
              onPress={startClass}
            />
          </GuideHighlight>
        </View>
      </Screen>
    );
  }

  // ── Early learner ─────────────────────────────────────────────────────
  const features = featuresForAge(child.age).filter((feature) => feature.pathId !== null);

  return (
    <Screen reserveDockSpace>
      <View style={{ gap: theme.space[7] }}>
        {/* Greeting + stars */}
        <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[4] }}>
          <AvatarFace state="waving" size={80} />
          <View style={{ flex: 1, gap: theme.space[1] }}>
            <Text variant="title">Hi {child.name}!</Text>
            <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[2] }}>
              <Text variant="body" muted>
                {child.stars} stars
              </Text>
              <StarRow earned={Math.min(child.stars, 3)} total={3} size={18} />
            </View>
          </View>
        </View>

        {/* The dominant CTA — visually primary by design */}
        {recommendation ? (
          <GuideHighlight targetId="continue-button" kind="control" label="Continue learning button">
            <Card
              variant="panel"
              tint={visual.tint}
              style={{ gap: theme.space[4], borderColor: visual.accent, borderWidth: 2 }}
            >
              <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[3] }}>
                <Text style={{ fontSize: 44 }}>{visual.icon}</Text>
                <View style={{ flex: 1 }}>
                  <Text variant="overline" muted>
                    {recommendation.reason}
                  </Text>
                  <Text variant="heading">{recommendation.title}</Text>
                </View>
              </View>
              <Button
                label={recommendation.isNew ? "Start learning" : "Keep going"}
                icon="▶️"
                tone="primary"
                onPress={startClass}
              />
            </Card>
          </GuideHighlight>
        ) : null}

        {/* Classes */}
        <View style={{ gap: theme.space[4] }}>
          <Text variant="title">Your classes</Text>
          <ResponsiveGrid columns={{ smallPhone: 1, phone: 2, tablet: 3 }}>
            {features.map((feature) => {
              const progress = child.path_progress[feature.pathId ?? ""];
              const isComplete = child.completed_paths.includes(feature.pathId ?? "");
              return (
                <FeatureCard
                  key={feature.id}
                  featureId={feature.id}
                  title={feature.title}
                  description={feature.description}
                  compact
                  progress={
                    isComplete
                      ? "Finished!"
                      : progress
                        ? `Level ${progress.current_stage}`
                        : undefined
                  }
                  onPress={() =>
                    navigation.navigate("ClassDetail", { pathId: feature.pathId ?? feature.id })
                  }
                />
              );
            })}
          </ResponsiveGrid>
        </View>

        {/* Secondary areas */}
        <View style={{ flexDirection: "row", gap: theme.space[3] }}>
          <View style={{ flex: 1 }}>
            <Button
              label="Practice"
              icon="🎯"
              tone="secondary"
              onPress={() => navigation.navigate("ChildTabs", { screen: "Practice" })}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Button
              label="Rewards"
              icon="🏆"
              tone="accent"
              onPress={() => navigation.navigate("ChildTabs", { screen: "Rewards" })}
            />
          </View>
        </View>
      </View>
    </Screen>
  );
}
