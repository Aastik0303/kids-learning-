import { View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import { useQuery } from "@tanstack/react-query";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { LoadingState, Pill } from "@/components/common/StateViews";
import { ProgressBar } from "@/components/common/ProgressBar";
import { ResponsiveGrid } from "@/components/responsive/ResponsiveGrid";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { progressApi } from "@/services/api/progressApi";
import { resolveExperienceMode, useChildStore } from "@/store/childStore";
import { classVisual } from "@/theme/colors";
import type { ParentStackParamList } from "@/navigation/routes";

const CORE_PATHS = ["numbers", "alphabets", "colours", "shapes"] as const;
const STAGES_PER_PATH = 8;

/**
 * Parent dashboard (spec section 19). Information-dense on purpose — this
 * is the one surface built for an adult, so it can carry real detail that
 * would overwhelm a child screen.
 */
export function ParentDashboardScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ParentStackParamList>>();

  const child = useChildStore((state) => state.activeChild);
  const children = useChildStore((state) => state.children);
  const selectChild = useChildStore((state) => state.selectChild);

  const progress = useQuery({
    queryKey: ["progress", child?.child_id],
    queryFn: () => progressApi.get(child!.child_id),
    enabled: !!child,
  });

  if (!child) {
    return (
      <Screen backdrop={false}>
        <LoadingState message="Loading…" />
      </Screen>
    );
  }

  const profile = progress.data?.child ?? child;
  const mode = resolveExperienceMode(profile);

  const completedStages = CORE_PATHS.reduce(
    (total, pathId) => total + (profile.path_progress[pathId]?.completed_stages.length ?? 0),
    0,
  );
  const overall = completedStages / (CORE_PATHS.length * STAGES_PER_PATH);

  return (
    <Screen backdrop={false}>
      <View style={{ gap: theme.space[6] }}>
        {/* Child switcher */}
        {children.length > 1 ? (
          <View style={{ gap: theme.space[2] }}>
            <Text variant="label">Viewing</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: theme.space[2] }}>
              {children.map((candidate) => (
                <Button
                  key={candidate.child_id}
                  label={candidate.name}
                  tone={candidate.child_id === profile.child_id ? "primary" : "quiet"}
                  size="parent"
                  fullWidth={false}
                  onPress={() => void selectChild(candidate)}
                />
              ))}
            </View>
          </View>
        ) : null}

        {/* Summary */}
        <Card variant="lift" style={{ gap: theme.space[3] }}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[3] }}>
            <Text style={{ fontSize: 34 }}>{mode === "toddler" ? "🍼" : "🎒"}</Text>
            <View style={{ flex: 1 }}>
              <Text variant="heading">{profile.name}</Text>
              <View style={{ flexDirection: "row", gap: theme.space[2], marginTop: 4 }}>
                <Pill label={mode === "toddler" ? "Toddler mode" : "Early learner"} tone="accent" />
                {profile.age ? <Pill label={`${profile.age} years`} /> : null}
                <Pill label={profile.preferred_language} />
              </View>
            </View>
          </View>

          <View style={{ gap: theme.space[1] }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <Text variant="label">Overall progress</Text>
              <Text variant="label" muted>
                {Math.round(overall * 100)}%
              </Text>
            </View>
            <ProgressBar value={overall} accessibilityLabel="Overall progress" />
          </View>
        </Card>

        {/* Key numbers */}
        <ResponsiveGrid columns={{ smallPhone: 2, tablet: 4 }}>
          <Metric label="Stars" value={String(profile.stars)} icon="⭐" />
          <Metric label="Levels done" value={String(completedStages)} icon="✅" />
          <Metric label="Classes done" value={String(profile.completed_paths.length)} icon="🏅" />
          <Metric
            label="Certificate"
            value={profile.certificate_unlocked ? "Ready" : "Locked"}
            icon="🎓"
          />
        </ResponsiveGrid>

        {/* Per-class mastery */}
        <View style={{ gap: theme.space[3] }}>
          <Text variant="title">By class</Text>
          {CORE_PATHS.map((pathId) => {
            const visual = classVisual(pathId);
            const pathProgress = profile.path_progress[pathId];
            const done = pathProgress?.completed_stages.length ?? 0;
            return (
              <Card key={pathId} variant="flat" style={{ gap: theme.space[2] }}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[2] }}>
                  <Text style={{ fontSize: 22 }}>{visual.icon}</Text>
                  <Text variant="subheading" style={{ flex: 1 }}>
                    {visual.label}
                  </Text>
                  <Text variant="label" muted>
                    {done} / {STAGES_PER_PATH}
                  </Text>
                </View>
                <ProgressBar
                  value={done / STAGES_PER_PATH}
                  height={10}
                  accessibilityLabel={`${visual.label} progress`}
                />
              </Card>
            );
          })}
        </View>

        {/* Weak skills */}
        {profile.weak_skills.length > 0 ? (
          <Card variant="tinted" tint={theme.palette.sunLight} style={{ gap: theme.space[2] }}>
            <Text variant="subheading">Needs more practice</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: theme.space[2] }}>
              {profile.weak_skills.map((skill) => (
                <Pill key={skill} label={skill} icon="💡" tone="accent" />
              ))}
            </View>
          </Card>
        ) : null}

        <View style={{ gap: theme.space[3] }}>
          <Button
            label="Session history"
            icon="📜"
            tone="secondary"
            size="parent"
            onPress={() => navigation.navigate("ParentProgress")}
          />
          <Button
            label="Settings"
            icon="⚙️"
            tone="quiet"
            size="parent"
            onPress={() => navigation.navigate("ParentSettings")}
          />
        </View>
      </View>
    </Screen>
  );
}

function Metric({ label, value, icon }: { label: string; value: string; icon: string }) {
  const theme = useTheme();
  return (
    <Card variant="flat" style={{ alignItems: "center", gap: theme.space[1], minHeight: 100 }}>
      <Text style={{ fontSize: 22 }}>{icon}</Text>
      <Text variant="heading">{value}</Text>
      <Text variant="caption" muted>
        {label}
      </Text>
    </Card>
  );
}
