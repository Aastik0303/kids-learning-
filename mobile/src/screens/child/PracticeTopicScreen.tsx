import { useCallback, useEffect, useState } from "react";
import { View } from "react-native";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { useGuide } from "@/ai/GuideProvider";
import { ActivityRenderer } from "@/activities/ActivityRenderer";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { ErrorState, LoadingState } from "@/components/common/StateViews";
import { ProgressBar } from "@/components/common/ProgressBar";
import { Screen } from "@/components/common/Screen";
import { StarRow } from "@/components/common/StarRow";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { ApiError } from "@/services/api/client";
import { practiceApi } from "@/services/api/practiceApi";
import { haptics } from "@/services/audio/haptics";
import { resolveExperienceMode, useChildStore } from "@/store/childStore";
import { useSessionStore } from "@/store/sessionStore";
import { toRenderableActivity, type RenderableActivity } from "@/types/activity";
import type { ActivityFeedback } from "@/activities/types";
import type { ChildStackParamList } from "@/navigation/routes";

/**
 * A practice run: the backend hands back a fixed set of activities, and
 * the child works through them. Same renderer as lessons — practice is a
 * different *source* of activities, not a different UI.
 */
export function PracticeTopicScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ChildStackParamList>>();
  const route = useRoute<RouteProp<ChildStackParamList, "PracticeTopic">>();
  const { topic, title } = route.params;

  const { dispatch, say } = useGuide();
  const child = useChildStore((state) => state.activeChild);
  const isToddler = resolveExperienceMode(child) === "toddler";

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activities, setActivities] = useState<RenderableActivity[]>([]);
  const [index, setIndex] = useState(0);
  const [feedback, setFeedback] = useState<ActivityFeedback | null>(null);
  const [correctCount, setCorrectCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDone, setIsDone] = useState(false);

  const activity = activities[index] ?? null;

  // ── Start ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!child) return;
    let cancelled = false;

    (async () => {
      setIsLoading(true);
      try {
        const response = await practiceApi.start(child.child_id, topic);
        if (cancelled) return;

        const mapped = response.activities.map(toRenderableActivity);
        setSessionId(response.practice_session_id);
        setActivities(mapped);
        setIndex(0);

        useSessionStore.getState().begin({
          kind: "practice",
          sessionId: response.practice_session_id,
          childId: child.child_id,
          pathId: topic,
          stageNumber: 0,
          learningMode: isToddler ? "toddler" : "standard",
        });

        const first = mapped[0];
        if (first) {
          useSessionStore.getState().setActivity(first);
          await dispatch("LESSON_STARTED", { surface: "practice" });
          await say(first.speech || first.prompt);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(
            caught instanceof ApiError
              ? caught.childMessage
              : "We could not start practice. Let us try again!",
          );
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      useSessionStore.getState().end();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [child?.child_id, topic]);

  // ── Answer ────────────────────────────────────────────────────────────
  const submit = useCallback(
    async (answer: string) => {
      if (!sessionId || !activity || isSubmitting) return;

      setIsSubmitting(true);
      useSessionStore.getState().recordAttempt(answer);

      try {
        const response = await practiceApi.answer(sessionId, activity.id, answer);

        setFeedback({
          isCorrect: response.is_correct,
          message: response.feedback,
          hint: response.hint,
          attempt: response.attempt_number,
          questionChanged: response.question_changed,
        });

        if (response.is_correct) {
          haptics.success();
          setCorrectCount((current) => current + 1);
        } else {
          haptics.gentleRetry();
        }

        await dispatch(response.is_correct ? "ANSWER_CORRECT" : "ANSWER_INCORRECT", {
          surface: "practice",
          childAnswer: answer,
        });

        if (response.is_correct) {
          // Give the praise a beat to land before moving on.
          setTimeout(() => advance(), 700);
        }
      } catch (caught) {
        setError(
          caught instanceof ApiError ? caught.childMessage : "We could not send that answer.",
        );
      } finally {
        setIsSubmitting(false);
      }
    },
    // `advance` is stable enough for this flow and including it would
    // recreate the callback on every question.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId, activity, isSubmitting, dispatch],
  );

  const advance = useCallback(() => {
    setFeedback(null);
    setIndex((current) => {
      const next = current + 1;
      if (next >= activities.length) {
        setIsDone(true);
        return current;
      }
      const nextActivity = activities[next];
      if (nextActivity) {
        useSessionStore.getState().setActivity(nextActivity);
        void say(nextActivity.speech || nextActivity.prompt);
      }
      return next;
    });
  }, [activities, say]);

  // ── Render ────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <Screen reserveDockSpace>
        <LoadingState message="Getting practice ready…" />
      </Screen>
    );
  }

  if (error) {
    return (
      <Screen reserveDockSpace>
        <View style={{ gap: theme.space[4] }}>
          <ErrorState message={error} />
          <Button label="Go back" tone="quiet" onPress={() => navigation.goBack()} />
        </View>
      </Screen>
    );
  }

  if (isDone || !activity) {
    return (
      <Screen reserveDockSpace>
        <Card variant="panel" style={{ gap: theme.space[5], alignItems: "center" }}>
          <Text style={{ fontSize: 66 }}>🎉</Text>
          <Text variant="title" align="center">
            Practice finished!
          </Text>
          <Text variant="subheading" align="center" muted>
            You got {correctCount} of {activities.length} right.
          </Text>
          <StarRow earned={correctCount >= activities.length ? 3 : correctCount > 0 ? 2 : 1} animate />
          <Button label="Back to practice" icon="🎯" tone="primary" onPress={() => navigation.goBack()} />
        </Card>
      </Screen>
    );
  }

  return (
    <Screen reserveDockSpace>
      <View style={{ gap: theme.space[5] }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[3] }}>
          <View style={{ flex: 1 }}>
            <Text variant="overline" muted>
              Practice
            </Text>
            <Text variant="subheading">{title}</Text>
          </View>
          <Button
            label="Exit"
            tone="quiet"
            size="parent"
            fullWidth={false}
            onPress={() => navigation.goBack()}
          />
        </View>

        <ProgressBar
          value={activities.length === 0 ? 0 : (index + 1) / activities.length}
          accessibilityLabel="Practice progress"
        />

        <ActivityRenderer
          activity={activity}
          feedback={feedback}
          isSubmitting={isSubmitting}
          isLocked={false}
          isToddlerMode={isToddler}
          onAnswer={(answer) => void submit(answer)}
          onContinue={advance}
          onRepeat={() => void say(activity.speech || activity.prompt)}
        />

        {feedback && !feedback.isCorrect ? (
          <Button label="Skip this one" tone="quiet" onPress={advance} />
        ) : null}
      </View>
    </Screen>
  );
}
