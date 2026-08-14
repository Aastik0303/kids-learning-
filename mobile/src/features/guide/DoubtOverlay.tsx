import { Modal, View } from "react-native";

import { AvatarFace } from "@/components/avatar/AvatarFace";
import { Button } from "@/components/common/Button";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useHandRaise } from "@/features/guide/useHandRaise";
import { useAudioStore } from "@/store/audioStore";
import { useGuideStore } from "@/store/guideStore";

/**
 * Hand Raise / Doubt Mode surface (spec section 13).
 *
 * Presented over the paused lesson rather than replacing it — the activity
 * stays mounted underneath, which is what makes "resume the exact step"
 * literal rather than a reload.
 */
export function DoubtOverlay() {
  const theme = useTheme();
  const phase = useGuideStore((state) => state.doubtPhase);
  const message = useGuideStore((state) => state.message);
  const partial = useAudioStore((state) => state.partialTranscript);
  const { resume, explainAgain, listenAgain, cancel } = useHandRaise();

  const isOpen = phase !== "idle";

  const copy = (() => {
    switch (phase) {
      case "asking":
        return { title: "What would you like to ask?", body: "Tap the microphone and tell me." };
      case "listening":
        return { title: "I am listening…", body: partial || "Say your question out loud." };
      case "thinking":
        return { title: "Let me think…", body: "I am finding a good way to explain." };
      case "explaining":
        return { title: "Here you go", body: message };
      case "idle":
        return { title: "", body: "" };
    }
  })();

  return (
    <Modal
      visible={isOpen}
      transparent
      animationType="fade"
      // Android hardware back should close doubt mode, not the lesson.
      onRequestClose={() => void cancel()}
    >
      <View
        style={{
          flex: 1,
          justifyContent: "flex-end",
          backgroundColor: "rgba(37, 49, 63, 0.35)",
        }}
      >
        <View
          style={{
            gap: theme.space[4],
            borderTopLeftRadius: theme.radius.card,
            borderTopRightRadius: theme.radius.card,
            backgroundColor: theme.colors.surface,
            padding: theme.space[5],
            paddingBottom: theme.space[8],
            ...theme.shadows.panel,
          }}
        >
          <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[4] }}>
            <AvatarFace
              state={
                phase === "listening" ? "listening" : phase === "thinking" ? "thinking" : "encouraging"
              }
              size={72}
            />
            <View style={{ flex: 1, gap: theme.space[1] }}>
              <Text variant="heading">{copy.title}</Text>
              <Text variant="body" muted>
                {copy.body}
              </Text>
            </View>
          </View>

          {phase === "asking" ? (
            <Button label="Tap to speak" icon="🎤" tone="accent" onPress={() => void listenAgain()} />
          ) : null}

          {phase === "explaining" ? (
            <View style={{ gap: theme.space[3] }}>
              <Button label="I understand!" icon="👍" tone="primary" onPress={() => void resume()} />
              <Button
                label="Tell me again"
                icon="🔁"
                tone="quiet"
                onPress={() => void explainAgain()}
              />
            </View>
          ) : null}

          {phase !== "explaining" ? (
            <Button label="Go back to my lesson" tone="quiet" onPress={() => void cancel()} />
          ) : null}
        </View>
      </View>
    </Modal>
  );
}
