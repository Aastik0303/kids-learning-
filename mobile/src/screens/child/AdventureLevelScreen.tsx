import { View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { Pressable } from "react-native";

import { LevelGames } from "@/components/games/LevelGames";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { standingFor } from "@/screens/child/AdventureSubjectScreen";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useTodayPlan } from "@/features/plan/useTodayPlan";
import { curriculumApi } from "@/services/api/curriculumApi";
import { useChildStore } from "@/store/childStore";
import type { ChildStackParamList } from "@/navigation/routes";

/**
 * A level on the Adventure board, and what it is.
 *
 * This page does not teach and has no way to start a lesson, and that is the
 * design rather than an omission. There is one class - the AI Teacher - which
 * runs one stage per item of today's frozen plan, marks the level done when the
 * stage is through and unlocks the next. Adventure is where a child *sees* that
 * happen. A second way into a lesson here could open a level the schedule had
 * not reached, which is exactly what the schedule exists to prevent.
 *
 * It does one thing besides saying where the level stands, and it is the reason
 * a child would come here at all: it hands the level back as **a game about the
 * thing it teaches**, dealt at random and started straight away. Going back
 * over something is how it stops fading, and playing marks nothing.
 *
 * A locked level keeps its games. Handing them over would be teaching it early
 * through the back door - the same reason the board does not link into a lesson.
 */
export function AdventureLevelScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ChildStackParamList>>();
  const route = useRoute<RouteProp<ChildStackParamList, "AdventureLevel">>();
  const { subjectId, topicId } = route.params;

  const child = useChildStore((state) => state.activeChild);
  const { plannedTopicIds, plan } = useTodayPlan();

  const detail = useQuery({
    queryKey: ["curriculum", "class", child?.child_id],
    queryFn: () => curriculumApi.forChild(child?.child_id as string),
    enabled: Boolean(child?.child_id),
  });

  const subject = detail.data?.subjects.find((one) => one.subject_id === subjectId) ?? null;
  const topic = subject?.topics.find((one) => one.topic_id === topicId) ?? null;
  const progress = child?.subject_progress?.[subjectId];

  const standing = standingFor({
    topic: { topic_id: topicId },
    completed: progress?.completed_topics ?? [],
    unlocked: progress?.unlocked_topics ?? [],
    planned: plannedTopicIds,
    planLoaded: Boolean(plan),
  });

  return (
    <Screen scroll={false} reserveDockSpace>
      <View style={{ flex: 1, gap: theme.space[3] }}>
        <Pressable accessibilityRole="button" onPress={() => navigation.goBack()}>
          <Text variant="label" muted>
            ← Back
          </Text>
        </Pressable>

        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: theme.space[3],
            borderRadius: theme.radius.card,
            backgroundColor: theme.colors.surfaceRaised,
            padding: theme.space[4],
            ...theme.shadows.soft,
          }}
        >
          <Text style={{ fontSize: 40 }}>{topic?.icon ?? "🎈"}</Text>
          <View style={{ flex: 1, gap: theme.space[1] }}>
            <Text variant="heading" numberOfLines={2}>
              {topic?.title ?? "Your level"}
            </Text>
            <Text variant="caption" muted testID="level-standing">
              {standing.icon} {standing.label}
            </Text>
          </View>
          <Text variant="caption" muted>
            ⭐ {topic?.star_reward ?? 0}
          </Text>
        </View>

        {/* Why there is no "start" button here, said plainly rather than left
            as an absence for a grown-up to puzzle over. */}
        <Text variant="body" muted>
          {standing.detail}
        </Text>

        {/* The game. A locked level gets none - the same reason the board does
            not open a lesson from here. */}
        <LevelGames topicId={topicId} locked={standing.locked} />
      </View>
    </Screen>
  );
}
