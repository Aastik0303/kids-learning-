import { View } from "react-native";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import { useQuery } from "@tanstack/react-query";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/common/StateViews";
import { LevelNode, type LevelState } from "@/components/cards/LevelNode";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { learningApi } from "@/services/api/learningApi";
import { featureById } from "@/features/catalog";
import { resolveExperienceMode, useChildStore } from "@/store/childStore";
import { classVisual } from "@/theme/colors";
import type { ChildStackParamList } from "@/navigation/routes";

/**
 * Class → levels (spec section 6). Levels come from the backend's stage
 * list, and lock state comes from the child's own path progress — never
 * from an AI decision.
 */
export function ClassDetailScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ChildStackParamList>>();
  const route = useRoute<RouteProp<ChildStackParamList, "ClassDetail">>();
  const { pathId } = route.params;

  const child = useChildStore((state) => state.activeChild);
  const isToddler = resolveExperienceMode(child) === "toddler";
  const visual = classVisual(pathId);
  const localFeature = featureById(pathId);
  // Features without a backend path have no stage list to fetch.
  const hasBackendPath = !localFeature || localFeature.pathId !== null;

  const stages = useQuery({
    queryKey: ["learning", "stages", pathId],
    queryFn: () => learningApi.listStages(pathId),
    enabled: hasBackendPath,
    staleTime: 30 * 60 * 1000,
  });

  const progress = child?.path_progress[pathId];

  if (!hasBackendPath) {
    return (
      <Screen reserveDockSpace>
        <View style={{ gap: theme.space[5] }}>
          <Header visual={visual} onBack={() => navigation.goBack()} />
          <EmptyState
            icon={visual.icon}
            title={`${visual.label} is a practice activity`}
            subtitle="Full levels for this one are coming soon. You can still try it in practice!"
          />
          <Button
            label="Go to practice"
            icon="🎯"
            tone="primary"
            onPress={() => navigation.navigate("ChildTabs", { screen: "Practice" })}
          />
        </View>
      </Screen>
    );
  }

  if (stages.isLoading) {
    return (
      <Screen reserveDockSpace>
        <LoadingState message="Opening the levels…" />
      </Screen>
    );
  }

  if (stages.isError) {
    return (
      <Screen reserveDockSpace>
        <ErrorState message="We could not load these levels." onRetry={() => void stages.refetch()} />
      </Screen>
    );
  }

  const list = stages.data ?? [];
  const currentStage = progress?.current_stage ?? 1;

  return (
    <Screen reserveDockSpace>
      <View style={{ gap: theme.space[5] }}>
        <Header visual={visual} onBack={() => navigation.goBack()} />

        <Card variant="tinted" tint={visual.tint} style={{ gap: theme.space[1] }}>
          <Text variant="overline" muted>
            Your reward
          </Text>
          <Text variant="subheading">{visual.reward}</Text>
        </Card>

        <View style={{ gap: theme.space[3] }}>
          {list.map((stage) => {
            const state = levelStateFor({
              stageNumber: stage.stage_number,
              currentStage,
              completed: progress?.completed_stages ?? [],
              unlocked: progress?.unlocked_stages ?? [1],
            });

            return (
              <LevelNode
                key={stage.stage_id}
                stageNumber={stage.stage_number}
                title={stage.title}
                state={state}
                starReward={stage.star_reward}
                starsEarned={state === "completed" ? stage.star_reward : 0}
                onPress={() =>
                  navigation.navigate("Lesson", {
                    pathId,
                    stageNumber: stage.stage_number,
                    mode: isToddler ? "toddler" : "standard",
                  })
                }
              />
            );
          })}
        </View>
      </View>
    </Screen>
  );
}

function Header({
  visual,
  onBack,
}: {
  visual: ReturnType<typeof classVisual>;
  onBack: () => void;
}) {
  const theme = useTheme();
  return (
    <View style={{ gap: theme.space[3] }}>
      <Button label="Back" icon="←" tone="quiet" fullWidth={false} onPress={onBack} />
      <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[3] }}>
        <Text style={{ fontSize: 46 }}>{visual.icon}</Text>
        <View style={{ flex: 1 }}>
          <Text variant="title">{visual.worldName}</Text>
          <Text variant="body" muted>
            {visual.mascot} is waiting for you
          </Text>
        </View>
      </View>
    </View>
  );
}

/** Lock state is derived from backend progress only. */
function levelStateFor({
  stageNumber,
  currentStage,
  completed,
  unlocked,
}: {
  stageNumber: number;
  currentStage: number;
  completed: number[];
  unlocked: number[];
}): LevelState {
  if (completed.includes(stageNumber)) return "completed";
  if (stageNumber === currentStage) return "current";
  if (unlocked.includes(stageNumber)) return "upcoming";
  return "locked";
}
