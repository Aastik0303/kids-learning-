import { useCallback, useMemo, useState } from "react";
import { View } from "react-native";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { ActivityRenderer } from "@/activities/ActivityRenderer";
import { Button } from "@/components/common/Button";
import { EmptyState } from "@/components/common/StateViews";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { STORIES, storyById } from "@/features/stories/storyContent";
import { resolveExperienceMode, useChildStore } from "@/store/childStore";
import { useGuide } from "@/ai/GuideProvider";
import type { ChildStackParamList } from "@/navigation/routes";

/**
 * Story playback. Stories are local content — the backend has no story
 * endpoint yet, so this reads from `storyContent.ts` and runs through the
 * same ActivityRenderer as everything else.
 */
export function StoryScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ChildStackParamList>>();
  const route = useRoute<RouteProp<ChildStackParamList, "Story">>();
  const { say } = useGuide();

  const child = useChildStore((state) => state.activeChild);
  const isToddler = resolveExperienceMode(child) === "toddler";

  const story = useMemo(() => storyById(route.params.storyId) ?? STORIES[0], [route.params.storyId]);
  const [index, setIndex] = useState(0);

  const advance = useCallback(() => {
    if (!story) return;
    setIndex((current) => {
      const next = current + 1;
      if (next >= story.activities.length) {
        navigation.goBack();
        return current;
      }
      return next;
    });
  }, [story, navigation]);

  if (!story) {
    return (
      <Screen reserveDockSpace>
        <EmptyState icon="📖" title="No story here" subtitle="Let us go back and pick another." />
      </Screen>
    );
  }

  const activity = story.activities[index];
  if (!activity) {
    return (
      <Screen reserveDockSpace>
        <EmptyState icon="📖" title="The end!" />
      </Screen>
    );
  }

  return (
    <Screen reserveDockSpace>
      <View style={{ gap: theme.space[5] }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[3] }}>
          <Text style={{ fontSize: 30 }}>📖</Text>
          <View style={{ flex: 1 }}>
            <Text variant="overline" muted>
              Story
            </Text>
            <Text variant="subheading">{story.title}</Text>
          </View>
          <Button
            label="Exit"
            tone="quiet"
            size="parent"
            fullWidth={false}
            onPress={() => navigation.goBack()}
          />
        </View>

        <ActivityRenderer
          activity={activity}
          feedback={null}
          isSubmitting={false}
          isLocked={false}
          isToddlerMode={isToddler}
          onAnswer={() => advance()}
          onContinue={advance}
          onRepeat={() => void say(activity.speech || activity.prompt)}
        />
      </View>
    </Screen>
  );
}
