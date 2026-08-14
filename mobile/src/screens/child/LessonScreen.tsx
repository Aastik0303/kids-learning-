import { useCallback, useEffect } from "react";
import { BackHandler, View } from "react-native";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { ActivityRenderer } from "@/activities/ActivityRenderer";
import { Button } from "@/components/common/Button";
import { ErrorState, LoadingState } from "@/components/common/StateViews";
import { ProgressBar } from "@/components/common/ProgressBar";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { AdaptiveStack } from "@/components/responsive/AdaptiveStack";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useResponsive } from "@/components/responsive/useResponsive";
import { useLessonSession } from "@/features/learning/useLessonSession";
import { resolveExperienceMode, useChildStore } from "@/store/childStore";
import { useGuideStore } from "@/store/guideStore";
import { useSessionStore } from "@/store/sessionStore";
import { useUiStore } from "@/store/uiStore";
import { classVisual } from "@/theme/colors";
import type { ChildStackParamList } from "@/navigation/routes";

/**
 * The single lesson screen. Every activity type in the product renders
 * here through ActivityRenderer — there is no per-question screen
 * (spec section 7).
 */
export function LessonScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ChildStackParamList>>();
  const route = useRoute<RouteProp<ChildStackParamList, "Lesson">>();
  const { sideBySideGuide } = useResponsive();

  const { pathId, stageNumber, mode = "standard", module } = route.params;

  const child = useChildStore((state) => state.activeChild);
  const refresh = useChildStore((state) => state.refresh);
  const isPaused = useSessionStore((state) => state.isPaused);
  const isInputLocked = useUiStore((state) => state.isInputLocked);
  const isToddler = resolveExperienceMode(child) === "toddler";

  const onComplete = useCallback(
    (summary: { starsEarned: number; correctCount: number; totalCount: number }) => {
      void refresh();
      useSessionStore.getState().end();
      useGuideStore.getState().clearHighlights();
      navigation.replace("SessionRecap", {
        pathId,
        stageNumber,
        starsEarned: summary.starsEarned,
        correctCount: summary.correctCount,
        totalCount: summary.totalCount,
      });
    },
    [navigation, pathId, stageNumber, refresh],
  );

  const {
    activity,
    feedback,
    isLoading,
    isSubmitting,
    error,
    submitAnswer,
    continueLesson,
    repeatPrompt,
  } = useLessonSession({ pathId, stageNumber, mode, module, onComplete });

  // Android back must not silently drop a child out of a lesson.
  useEffect(() => {
    const subscription = BackHandler.addEventListener("hardwareBackPress", () => {
      leave();
      return true;
    });
    return () => subscription.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const leave = useCallback(() => {
    useSessionStore.getState().end();
    useGuideStore.getState().clearHighlights();
    navigation.goBack();
  }, [navigation]);

  const visual = classVisual(pathId);

  if (isLoading) {
    return (
      <Screen reserveDockSpace>
        <LoadingState message="Getting your lesson ready…" />
      </Screen>
    );
  }

  if (error) {
    return (
      <Screen reserveDockSpace>
        <View style={{ gap: theme.space[4] }}>
          <ErrorState message={error} onRetry={() => navigation.replace("Lesson", route.params)} />
          <Button label="Go back" tone="quiet" onPress={leave} />
        </View>
      </Screen>
    );
  }

  if (!activity) {
    return (
      <Screen reserveDockSpace>
        <LoadingState message="Finding the next question…" />
      </Screen>
    );
  }

  const header = (
    <View style={{ gap: theme.space[3] }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[3] }}>
        <Text style={{ fontSize: 30 }}>{visual.icon}</Text>
        <View style={{ flex: 1 }}>
          <Text variant="overline" muted>
            {visual.label}
          </Text>
          <Text variant="subheading">Level {stageNumber}</Text>
        </View>
        <Button
          label="Exit"
          tone="quiet"
          size="parent"
          fullWidth={false}
          onPress={leave}
        />
      </View>
      <ProgressBar
        value={Math.min(useSessionStore.getState().attempt / 5, 1)}
        accessibilityLabel="Lesson progress"
      />
    </View>
  );

  const body = (
    <ActivityRenderer
      activity={activity}
      feedback={feedback}
      isSubmitting={isSubmitting}
      // Input is locked while the lesson is paused for a doubt.
      isLocked={isInputLocked || isPaused}
      isToddlerMode={isToddler}
      onAnswer={(answer, meta) => void submitAnswer(answer, meta)}
      onContinue={() => void continueLesson()}
      onRepeat={() => void repeatPrompt()}
    />
  );

  return (
    <Screen reserveDockSpace={!sideBySideGuide} scroll>
      <View style={{ gap: theme.space[5] }}>
        {header}
        {/* Landscape and tablets get the activity beside the avatar area;
            the dock positions itself to match (spec section 15). */}
        <AdaptiveStack weights={[3, 2]} direction={sideBySideGuide ? "row" : "column"}>
          {body}
          <View />
        </AdaptiveStack>
      </View>
    </Screen>
  );
}
