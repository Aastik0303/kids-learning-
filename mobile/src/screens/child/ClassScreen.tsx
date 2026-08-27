import { useCallback, useEffect } from "react";
import { BackHandler, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { ActivityRenderer } from "@/activities/ActivityRenderer";
import { Button } from "@/components/common/Button";
import { ErrorState, LoadingState } from "@/components/common/StateViews";
import { ProgressBar } from "@/components/common/ProgressBar";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { AdaptiveStack } from "@/components/responsive/AdaptiveStack";
import { MicButton } from "@/features/voice/MicButton";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useResponsive } from "@/components/responsive/useResponsive";
import { useConductorClass, type ClassSummary } from "@/features/learning/useConductorClass";
import { useAudioStore } from "@/store/audioStore";
import { useChildStore } from "@/store/childStore";
import { useGuideStore } from "@/store/guideStore";
import { useSessionStore } from "@/store/sessionStore";
import type { ChildStackParamList } from "@/navigation/routes";

/**
 * Today's class, run by the server.
 *
 * This screen is deliberately thin, and that is the whole design. It picks no
 * topic, offers no menu, and has no "next" button — the child opens the app
 * and the class is already happening. Every beat is a directive: what to show,
 * what the guide says, and whether the microphone opens. When the guide has
 * just explained a letter and the server wants it said back, the mic opens by
 * itself and the child simply talks.
 *
 * The one control that is not the activity itself is Exit, which is for the
 * grown-up.
 */
export function ClassScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ChildStackParamList>>();
  const { sideBySideGuide } = useResponsive();

  const refresh = useChildStore((state) => state.refresh);
  const isListening = useAudioStore((state) => state.isListening);
  const partial = useAudioStore((state) => state.partialTranscript);

  const onComplete = useCallback(
    (summary: ClassSummary) => {
      void refresh();
      useSessionStore.getState().end();
      useGuideStore.getState().clearHighlights();
      navigation.replace("SessionRecap", {
        // A class has no path or level to name: the plan chose the topic, and
        // the recap says so rather than inventing "level 0".
        pathId: "",
        stageNumber: 0,
        starsEarned: summary.starsEarned,
        correctCount: 0,
        totalCount: 0,
        fromClass: true,
        closeReason: summary.reason,
      });
    },
    [navigation, refresh],
  );

  const {
    directive,
    activity,
    isLoading,
    isSubmitting,
    error,
    answer,
    speakAnswer,
    repeat,
    clearError,
  } = useConductorClass({ onComplete });

  const leave = useCallback(() => {
    useSessionStore.getState().end();
    useGuideStore.getState().clearHighlights();
    navigation.goBack();
  }, [navigation]);

  useEffect(() => {
    const subscription = BackHandler.addEventListener("hardwareBackPress", () => {
      leave();
      return true;
    });
    return () => subscription.remove();
  }, [leave]);

  if (isLoading) {
    return (
      <Screen reserveDockSpace>
        <LoadingState message="Getting your class ready…" />
      </Screen>
    );
  }

  if (error) {
    return (
      <Screen reserveDockSpace>
        <View style={{ gap: theme.space[4] }}>
          <ErrorState message={error} onRetry={clearError} />
          <Button label="Go back" tone="quiet" onPress={leave} />
        </View>
      </Screen>
    );
  }

  if (!directive) {
    return (
      <Screen reserveDockSpace>
        <LoadingState message="Finding today's lesson…" />
      </Screen>
    );
  }

  const { progress, listen, speech, phase } = directive;

  const header = (
    <View style={{ gap: theme.space[3] }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[3] }}>
        <View style={{ flex: 1 }}>
          <Text variant="overline" muted>
            Today's class
          </Text>
        </View>
        <Button label="Exit" tone="quiet" size="parent" fullWidth={false} onPress={leave} />
      </View>
      {progress.total > 0 ? (
        <ProgressBar
          value={Math.min(progress.filled / progress.total, 1)}
          accessibilityLabel="Class progress"
        />
      ) : null}
    </View>
  );

  /**
   * What the guide is saying, on screen as well as aloud. A pre-reader does
   * not read it, but a grown-up sitting beside them does, and it is what makes
   * the class followable without sound.
   */
  const guideLine = speech.text ? (
    <Text variant="subheading" align="center">
      {speech.text}
    </Text>
  ) : null;

  /**
   * The listening beat. The microphone is already open by the time this shows —
   * the button is here so a child who stayed quiet can start it again, not so
   * they can start it in the first place.
   */
  const listeningPanel = listen.active ? (
    <View style={{ alignItems: "center", gap: theme.space[3] }}>
      {listen.expect ? (
        <View
          style={{
            minWidth: 140,
            alignItems: "center",
            borderRadius: theme.radius.card,
            backgroundColor: theme.palette.sunLight,
            paddingHorizontal: theme.space[8],
            paddingVertical: theme.space[6],
            ...theme.shadows.card,
          }}
        >
          <Text variant="toddlerPrompt" align="center">
            {listen.expect}
          </Text>
        </View>
      ) : null}

      <MicButton onPress={() => void speakAnswer()} disabled={isSubmitting} size="large" />

      <Text variant="body" align="center" muted>
        {isListening ? partial || "I am listening…" : "Say it out loud!"}
      </Text>
    </View>
  ) : null;

  const body = activity ? (
    <ActivityRenderer
      activity={activity}
      feedback={null}
      isSubmitting={isSubmitting}
      isLocked={isSubmitting || listen.active}
      isToddlerMode={directive.presentation.text_density === "none"}
      onAnswer={(value) => answer(value)}
      // There is no "next": the class advances itself. Continue is wired to
      // repeating the line so a stray tap is harmless rather than a decision.
      onContinue={() => void repeat()}
      onRepeat={() => void repeat()}
    />
  ) : null;

  return (
    <Screen reserveDockSpace={!sideBySideGuide} scroll>
      <View style={{ gap: theme.space[5] }} testID={`class-phase-${phase}`}>
        {header}
        {guideLine}
        <AdaptiveStack weights={[3, 2]} direction={sideBySideGuide ? "row" : "column"}>
          <View style={{ gap: theme.space[5] }}>
            {listeningPanel}
            {body}
          </View>
          <View />
        </AdaptiveStack>
      </View>
    </Screen>
  );
}
