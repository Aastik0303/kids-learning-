import { Pressable, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { ErrorState, LoadingState } from "@/components/common/StateViews";
import { ScheduleStrip } from "@/components/shared/ScheduleStrip";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useTodayPlan } from "@/features/plan/useTodayPlan";
import { curriculumApi } from "@/services/api/curriculumApi";
import { useChildStore } from "@/store/childStore";
import type { ChildStackParamList } from "@/navigation/routes";
import type { CurriculumTopic } from "@/types/teacher";

/**
 * One subject's levels, as a board of what stands where.
 *
 * Four answers and no fifth: **finished**, **on today's list**, **waiting for
 * its turn**, or **locked**. Three of them are read off the child's own
 * progress and the fourth off today's frozen plan, which is the same pair of
 * sources the schedule strip above reads - so a level cannot say one thing here
 * and another there.
 *
 * A level is tappable, and what opens is the level's page: what it teaches,
 * where it stands, and a game about it. Not a lesson. The class is the AI
 * Teacher and the plan decides when a level is taught; a board that could start
 * one would be able to open a level the schedule had not reached.
 */
export function AdventureSubjectScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ChildStackParamList>>();
  const route = useRoute<RouteProp<ChildStackParamList, "AdventureSubject">>();
  const { subjectId } = route.params;

  const child = useChildStore((state) => state.activeChild);
  const { plannedTopicIds, plan } = useTodayPlan();

  const detail = useQuery({
    queryKey: ["curriculum", "class", child?.child_id],
    queryFn: () => curriculumApi.forChild(child?.child_id as string),
    enabled: Boolean(child?.child_id),
  });

  const subject = detail.data?.subjects.find((one) => one.subject_id === subjectId) ?? null;
  const progress = child?.subject_progress?.[subjectId];

  return (
    <Screen reserveDockSpace>
      <View style={{ gap: theme.space[4] }}>
        <ScheduleStrip />

        <Pressable accessibilityRole="button" onPress={() => navigation.goBack()}>
          <Text variant="label" muted>
            ← All subjects
          </Text>
        </Pressable>

        {detail.isLoading ? <LoadingState message="Getting your levels ready…" /> : null}
        {detail.isError ? <ErrorState message="We could not load that subject." /> : null}

        {subject ? (
          <>
            <View style={{ gap: theme.space[1] }}>
              <Text variant="title">{subject.fun_name ?? subject.title}</Text>
              {subject.fun_name ? (
                <Text variant="overline" muted>
                  {subject.title}
                </Text>
              ) : null}
              {subject.easy_line ? (
                <Text variant="bodyLarge" muted>
                  {subject.easy_line}
                </Text>
              ) : null}
            </View>

            <View style={{ gap: theme.space[3] }}>
              {subject.topics.map((topic, position) => {
                const standing = standingFor({
                  topic,
                  completed: progress?.completed_topics ?? [],
                  unlocked: progress?.unlocked_topics ?? [],
                  planned: plannedTopicIds,
                  planLoaded: Boolean(plan),
                });
                return (
                  <LevelNodeRow
                    key={topic.topic_id}
                    number={position + 1}
                    topic={topic}
                    standing={standing}
                    onOpen={() =>
                      navigation.navigate("AdventureLevel", {
                        subjectId,
                        topicId: topic.topic_id,
                      })
                    }
                  />
                );
              })}
            </View>
          </>
        ) : null}
      </View>
    </Screen>
  );
}

export type LevelStanding = {
  icon: string;
  label: string;
  detail: string;
  locked: boolean;
};

/**
 * Where one level stands.
 *
 * Shared with the level's own page, so the two can never disagree - the page
 * used to work this out for itself and a level could read "on today's list"
 * from the board and "waiting for its turn" once opened.
 *
 * Nothing is called tomorrow's on a guess: a plan that has not arrived yet must
 * not make today's own level look shut, so the "waiting" answer is only given
 * once a plan with something in it has actually been read.
 */
export function standingFor({
  topic,
  completed,
  unlocked,
  planned,
  planLoaded,
}: {
  topic: { topic_id: string };
  completed: string[];
  unlocked: string[];
  planned: Set<string>;
  planLoaded: boolean;
}): LevelStanding {
  if (completed.includes(topic.topic_id)) {
    return { icon: "⭐", label: "Finished", detail: "You have already done this one.", locked: false };
  }
  if (!unlocked.includes(topic.topic_id)) {
    return {
      icon: "🔒",
      label: "Locked",
      detail: "Finish the levels before this one and it will open.",
      locked: true,
    };
  }
  if (planLoaded && planned.size > 0 && !planned.has(topic.topic_id)) {
    return {
      icon: "🌙",
      label: "Waiting for its turn",
      detail: "It is not on today's list. Your class will bring you here.",
      locked: false,
    };
  }
  return {
    icon: "🎈",
    label: "On today's list",
    detail: "Your class is teaching this one today.",
    locked: false,
  };
}

function LevelNodeRow({
  number,
  topic,
  standing,
  onOpen,
}: {
  number: number;
  topic: CurriculumTopic;
  standing: LevelStanding;
  onOpen: () => void;
}) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Level ${number}, ${topic.title}, ${standing.label}`}
      onPress={onOpen}
      style={{
        flexDirection: "row",
        alignItems: "center",
        gap: theme.space[3],
        borderRadius: theme.radius.xl,
        backgroundColor: theme.colors.surface,
        padding: theme.space[4],
        opacity: standing.locked ? 0.6 : 1,
        ...theme.shadows.soft,
      }}
    >
      <Text style={{ fontSize: 34 }}>{topic.icon || "🎈"}</Text>
      <View style={{ flex: 1, gap: theme.space[1] }}>
        <Text variant="subheading">{topic.title}</Text>
        <Text variant="caption" muted>
          {standing.icon} {standing.label}
        </Text>
      </View>
      <Text variant="caption" muted>
        ⭐ {topic.star_reward}
      </Text>
    </Pressable>
  );
}
