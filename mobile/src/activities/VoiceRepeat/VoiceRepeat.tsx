import { useEffect, useState } from "react";
import { View } from "react-native";

import { Button } from "@/components/common/Button";
import { GuideHighlight } from "@/components/common/GuideHighlight";
import { Text } from "@/components/common/Text";
import { MicButton } from "@/features/voice/MicButton";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useChildStore } from "@/store/childStore";
import { useAudioStore } from "@/store/audioStore";
import { voiceController } from "@/features/voice/VoiceController";
import type { ActivityComponentProps } from "@/activities/types";

/**
 * Speak-the-answer activity. Backs `voice_repeat` and `sentence_repeat`.
 *
 * Always offers a tap fallback: STT fails often enough on children's
 * speech that a voice-only path would strand them. Spec section 12 calls
 * for large, obvious listening/speaking states, which the mic button owns.
 */
export function VoiceRepeat({
  activity,
  onAnswer,
  feedback,
  isSubmitting,
  isLocked,
  isToddlerMode,
  onRepeat,
}: ActivityComponentProps) {
  const theme = useTheme();
  const child = useChildStore((state) => state.activeChild);
  const outcome = useAudioStore((state) => state.lastOutcome);
  const micPermission = useAudioStore((state) => state.micPermission);

  const [showTapFallback, setShowTapFallback] = useState(false);

  // Reset the fallback affordance when the question changes.
  useEffect(() => {
    setShowTapFallback(false);
  }, [activity.id]);

  // Surface the tap path as soon as voice has visibly failed once.
  useEffect(() => {
    if (
      outcome === "no_speech" ||
      outcome === "too_quiet" ||
      outcome === "permission_denied" ||
      outcome === "unavailable" ||
      outcome === "error"
    ) {
      setShowTapFallback(true);
    }
  }, [outcome]);

  const voiceUnavailable = micPermission === "unavailable" || micPermission === "denied";

  const capture = async () => {
    const result = await voiceController.captureAnswer(activity, child?.preferred_language);
    if (!result.transcript.trim()) return;

    // Send the resolved answer when normalisation matched a real
    // candidate, otherwise the raw transcript — the backend does the
    // final deterministic check either way.
    onAnswer(result.isResolved ? result.resolvedAnswer : result.transcript, {
      input: "voice",
      confidence: result.confidence,
      transcript: result.transcript,
    });
  };

  return (
    <View style={{ gap: theme.space[5], alignItems: "center" }}>
      {/* The thing to say, big and central. */}
      <GuideHighlight
        targetId="say-this"
        kind="visual"
        label={`The word to say: ${activity.concept || activity.correctAnswer}`}
      >
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
          <Text variant={isToddlerMode ? "toddlerPrompt" : "childAnswer"} align="center">
            {activity.glyph || activity.concept || activity.correctAnswer}
          </Text>
        </View>
      </GuideHighlight>

      {!voiceUnavailable ? (
        <GuideHighlight targetId="microphone-button" kind="control" label="Microphone button">
          <MicButton onPress={capture} disabled={isSubmitting || isLocked} size={isToddlerMode ? "large" : "medium"} />
        </GuideHighlight>
      ) : null}

      <VoiceStatusLine />

      {/* Tap fallback — always available once voice has struggled. */}
      {(showTapFallback || voiceUnavailable) && activity.options.length > 0 ? (
        <View style={{ width: "100%", gap: theme.space[3] }}>
          <Text variant="label" align="center" muted>
            Or tap your answer
          </Text>
          <View
            style={{
              flexDirection: "row",
              flexWrap: "wrap",
              gap: theme.space[2],
              justifyContent: "center",
            }}
          >
            {activity.options.map((option) => (
              <Button
                key={option}
                label={option}
                tone="quiet"
                fullWidth={false}
                disabled={isSubmitting || isLocked}
                onPress={() => onAnswer(option, { input: "tap" })}
              />
            ))}
          </View>
        </View>
      ) : null}

      <Button label="Say it again" icon="🔁" tone="quiet" fullWidth={false} onPress={onRepeat} />

      {feedback?.hint ? (
        <Text variant="body" align="center" muted>
          {feedback.hint}
        </Text>
      ) : null}
    </View>
  );
}

/** Child-readable status for the current voice attempt. */
function VoiceStatusLine() {
  const theme = useTheme();
  const outcome = useAudioStore((state) => state.lastOutcome);
  const isListening = useAudioStore((state) => state.isListening);
  const partial = useAudioStore((state) => state.partialTranscript);

  if (isListening) {
    return (
      <Text variant="subheading" align="center" color={theme.colors.secondary}>
        {partial || "I am listening…"}
      </Text>
    );
  }

  const copy: Partial<Record<typeof outcome, string>> = {
    no_speech: "I did not hear anything. Try again!",
    too_quiet: "That was very quiet. Say it a bit louder!",
    permission_denied: "Ask a grown-up to turn on the microphone.",
    unavailable: "Let us tap the answer instead.",
    error: "The microphone had trouble. Let us try again.",
  };

  const message = copy[outcome];
  if (!message) return null;

  return (
    <Text variant="body" align="center" muted>
      {message}
    </Text>
  );
}
