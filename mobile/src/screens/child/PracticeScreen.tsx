import { useEffect } from "react";
import { Pressable, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import { useQuery } from "@tanstack/react-query";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { useGuide } from "@/ai/GuideProvider";
import { Card } from "@/components/common/Card";
import { EmptyState, ErrorState, LoadingState, Pill } from "@/components/common/StateViews";
import { GuideHighlight } from "@/components/common/GuideHighlight";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { practiceApi } from "@/services/api/practiceApi";
import { useChildStore } from "@/store/childStore";
import { classVisual } from "@/theme/colors";
import { haptics } from "@/services/audio/haptics";
import type { ChildStackParamList } from "@/navigation/routes";

/**
 * Practice topics. The backend only unlocks topics the child has actually
 * been introduced to, so nothing here can surface unseen material.
 */
export function PracticeScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ChildStackParamList>>();
  const { dispatch } = useGuide();
  const child = useChildStore((state) => state.activeChild);

  const topics = useQuery({
    queryKey: ["practice", "topics", child?.child_id],
    queryFn: () => practiceApi.topics(child!.child_id),
    enabled: !!child,
  });

  useEffect(() => {
    void dispatch("HOME_OPENED", { surface: "practice" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (topics.isLoading) {
    return (
      <Screen reserveDockSpace>
        <LoadingState message="Finding things to practise…" />
      </Screen>
    );
  }

  if (topics.isError) {
    return (
      <Screen reserveDockSpace>
        <ErrorState message="We could not load practice." onRetry={() => void topics.refetch()} />
      </Screen>
    );
  }

  const list = topics.data ?? [];
  const unlocked = list.filter((topic) => topic.unlocked);

  return (
    <Screen reserveDockSpace>
      <View style={{ gap: theme.space[5] }}>
        <View style={{ gap: theme.space[1] }}>
          <Text variant="title">Practice</Text>
          <Text variant="body" muted>
            Go over the things you have already learned.
          </Text>
        </View>

        {unlocked.length === 0 ? (
          <EmptyState
            icon="🌱"
            title="Nothing to practise yet"
            subtitle="Finish a level first, then come back here."
          />
        ) : null}

        <View style={{ gap: theme.space[3] }}>
          {list.map((topic) => {
            const visual = classVisual(topic.topic);
            const isWeak = child?.weak_skills.includes(topic.topic) ?? false;

            return (
              <GuideHighlight
                key={topic.topic}
                targetId={`practice-${topic.topic}`}
                kind="nav"
                label={`Practice ${topic.title}`}
              >
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={`Practice ${topic.title}${topic.unlocked ? "" : ", locked"}`}
                  accessibilityState={{ disabled: !topic.unlocked }}
                  disabled={!topic.unlocked}
                  onPress={() => {
                    haptics.tap();
                    navigation.navigate("PracticeTopic", {
                      topic: topic.topic,
                      title: topic.title,
                    });
                  }}
                >
                  <Card
                    variant="lift"
                    style={{
                      flexDirection: "row",
                      alignItems: "center",
                      gap: theme.space[3],
                      opacity: topic.unlocked ? 1 : 0.55,
                    }}
                  >
                    <Text style={{ fontSize: 34 }}>{topic.unlocked ? visual.icon : "🔒"}</Text>
                    <View style={{ flex: 1, gap: theme.space[1] }}>
                      <Text variant="subheading">{topic.title}</Text>
                      <View style={{ flexDirection: "row", gap: theme.space[2] }}>
                        {isWeak ? <Pill label="Needs practice" icon="💡" tone="accent" /> : null}
                        {!topic.unlocked ? <Pill label="Locked" tone="locked" /> : null}
                      </View>
                    </View>
                    {topic.unlocked ? <Text style={{ fontSize: 22 }}>👉</Text> : null}
                  </Card>
                </Pressable>
              </GuideHighlight>
            );
          })}
        </View>
      </View>
    </Screen>
  );
}
