import { Pressable, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { ErrorState, LoadingState } from "@/components/common/StateViews";
import { ProgressBar } from "@/components/common/ProgressBar";
import { ScheduleStrip } from "@/components/shared/ScheduleStrip";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useTodayPlan } from "@/features/plan/useTodayPlan";
import { curriculumApi } from "@/services/api/curriculumApi";
import { useChildStore } from "@/store/childStore";
import type { ChildStackParamList, RootStackParamList } from "@/navigation/routes";
import type { CurriculumSubject } from "@/types/teacher";

/**
 * Adventure - the child's class as its subjects. A **progress board**, not a
 * menu.
 *
 * Every card goes to that subject's level map and nothing here starts a lesson.
 * The class is the AI Teacher and the frozen daily plan decides what it
 * teaches, so a card that opened a level would be a second way in, able to
 * reach a level the schedule has not got to yet. The 🗓️ badge is how a child
 * sees whose turn it is, and 🧩 is a level the scheduler says is owed a
 * check-in: whatever the schedule decides is visible here, because a schedule
 * the child's grown-up cannot see is one nobody can tell is working.
 *
 * Names are always shown. A pre-reader should not be *asked to read* to answer
 * a question; that does not mean stripping the labels off a board, which leaves
 * a screen of blank cards neither the child nor the grown-up beside them can
 * use. The icon leads and the word supports it.
 */
export function AdventureScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ChildStackParamList>>();
  // The only way into the grown-up half of the app, and it is deliberately
  // here rather than on the class: a control a parent looks for belongs on
  // the screen a parent reads, not on the one a two-year-old is answering.
  // The gate itself is what keeps a child out of it.
  const root = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const child = useChildStore((state) => state.activeChild);
  const { plannedTopicIds, retentionTopicIds } = useTodayPlan();

  const detail = useQuery({
    queryKey: ["curriculum", "class", child?.child_id],
    queryFn: () => curriculumApi.forChild(child?.child_id as string),
    enabled: Boolean(child?.child_id),
  });

  const totalDone = Object.values(child?.subject_progress ?? {}).reduce(
    (sum, progress) => sum + progress.completed_topics.length,
    0,
  );

  return (
    <Screen reserveDockSpace>
      <View style={{ gap: theme.space[4] }}>
        <ScheduleStrip />

        {detail.isLoading ? <LoadingState message="Getting your subjects ready…" /> : null}
        {detail.isError ? <ErrorState message="We could not load your subjects." /> : null}

        {detail.data ? (
          <>
            <View style={{ gap: theme.space[2] }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[2] }}>
                <View style={{ flex: 1, flexDirection: "row", flexWrap: "wrap", gap: theme.space[2] }}>
                  <Chip label={`${detail.data.code} · ages ${detail.data.min_age}–${detail.data.max_age}`} />
                  <Chip label={`⭐ ${child?.stars ?? 0}`} tone="sun" />
                </View>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="For grown-ups"
                  onPress={() => root.navigate("Parent", { screen: "ParentGate" })}
                  style={{
                    minHeight: theme.touchTarget.parent,
                    minWidth: theme.touchTarget.parent,
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: theme.radius.pill,
                    backgroundColor: theme.whiteAlpha.a86,
                  }}
                >
                  <Text variant="subheading">👪</Text>
                </Pressable>
              </View>
              <Text variant="title">{detail.data.title}</Text>
              <Text variant="bodyLarge" muted>
                {detail.data.subject_count} subjects · {totalDone} of {detail.data.topic_count} levels
                done
              </Text>
            </View>

            <View style={{ gap: theme.space[3] }}>
              {detail.data.subjects.map((subject) => (
                <SubjectCard
                  key={subject.subject_id}
                  subject={subject}
                  done={child?.subject_progress?.[subject.subject_id]?.completed_topics.length ?? 0}
                  isToday={subject.topics.some((topic) => plannedTopicIds.has(topic.topic_id))}
                  hasCheckIn={subject.topics.some((topic) => retentionTopicIds.has(topic.topic_id))}
                  onOpen={() =>
                    navigation.navigate("AdventureSubject", {
                      subjectId: subject.subject_id,
                      title: subject.fun_name ?? subject.title,
                    })
                  }
                />
              ))}
            </View>
          </>
        ) : null}
      </View>
    </Screen>
  );
}

function Chip({ label, tone = "plain" }: { label: string; tone?: "plain" | "sun" }) {
  const theme = useTheme();
  return (
    <View
      style={{
        borderRadius: theme.radius.pill,
        backgroundColor: tone === "sun" ? theme.palette.sunshine : theme.whiteAlpha.a86,
        paddingHorizontal: theme.space[4],
        paddingVertical: theme.space[2],
      }}
    >
      <Text variant="label">{label}</Text>
    </View>
  );
}

function SubjectCard({
  subject,
  done,
  isToday,
  hasCheckIn,
  onOpen,
}: {
  subject: CurriculumSubject;
  done: number;
  isToday: boolean;
  hasCheckIn: boolean;
  onOpen: () => void;
}) {
  const theme = useTheme();
  const percent = subject.topic_count ? done / subject.topic_count : 0;
  const finished = done > 0 && done === subject.topic_count;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${subject.fun_name ?? subject.title}, ${done} of ${subject.topic_count} levels done`}
      onPress={onOpen}
      style={{
        gap: theme.space[3],
        borderRadius: theme.radius.card,
        backgroundColor: theme.colors.surface,
        padding: theme.space[4],
        ...theme.shadows.card,
      }}
    >
      <View style={{ flexDirection: "row", alignItems: "flex-start", gap: theme.space[3] }}>
        <Text style={{ fontSize: 42 }}>{subject.icon}</Text>
        <View style={{ flex: 1, gap: theme.space[1] }}>
          <Text variant="heading">{subject.fun_name ?? subject.title}</Text>
          {subject.easy_line ? (
            <Text variant="body" muted>
              {subject.easy_line}
            </Text>
          ) : null}
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: theme.space[2] }}>
            {/* Status, never a door. Both badges say what the schedule has
                decided; neither of them starts anything. */}
            {isToday ? (
              <Text variant="caption" color={theme.palette.leaf}>
                🗓️ Today
              </Text>
            ) : null}
            {hasCheckIn ? (
              <Text variant="caption" color={theme.palette.sky}>
                🧩 Remember
              </Text>
            ) : null}
            {finished ? (
              <Text variant="caption" color={theme.palette.sunshine}>
                🏆 All done
              </Text>
            ) : null}
          </View>
        </View>
      </View>

      <ProgressBar
        value={percent}
        accessibilityLabel={`${done} of ${subject.topic_count} levels done`}
      />
      <Text variant="caption" muted>
        {done}/{subject.topic_count} levels
      </Text>
    </Pressable>
  );
}
