import { useEffect, useState } from "react";
import { View } from "react-native";

import { Button } from "@/components/common/Button";
import { GuideHighlight } from "@/components/common/GuideHighlight";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useAudioStore } from "@/store/audioStore";
import { useChildStore } from "@/store/childStore";
import { voiceController } from "@/features/voice/VoiceController";
import type { ActivityComponentProps } from "@/activities/types";

/**
 * Listen-to-a-story beat. The guide narrates; the child listens and taps
 * to continue. Nothing is scored.
 *
 * Story text is split into pages so a long passage does not arrive as one
 * unbroken block of TTS a small child cannot follow.
 */
export function StoryListen({ activity, onContinue, isToddlerMode }: ActivityComponentProps) {
  const theme = useTheme();
  const child = useChildStore((state) => state.activeChild);
  const isSpeaking = useAudioStore((state) => state.isSpeaking);

  const pages = splitIntoPages(activity.speech || activity.prompt);
  const [page, setPage] = useState(0);

  useEffect(() => {
    setPage(0);
  }, [activity.id]);

  const currentPage = pages[page] ?? "";
  const isLastPage = page >= pages.length - 1;

  // Narrate each page as it appears.
  useEffect(() => {
    if (!currentPage) return;
    void voiceController.speak(currentPage, child?.preferred_language);
    // Re-narrating on every dependency change would stutter; page is the
    // only trigger that should start speech.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, activity.id]);

  return (
    <View style={{ gap: theme.space[5], alignItems: "center" }}>
      <GuideHighlight targetId="story-page" kind="visual" label="Story page">
        <View
          style={{
            width: "100%",
            minHeight: 180,
            justifyContent: "center",
            borderRadius: theme.radius.card,
            backgroundColor: theme.palette.leafLight,
            padding: theme.space[6],
            ...theme.shadows.card,
          }}
        >
          {activity.glyph ? (
            <Text align="center" style={{ fontSize: 56, marginBottom: theme.space[3] }}>
              {activity.glyph}
            </Text>
          ) : null}
          <Text variant={isToddlerMode ? "childPrompt" : "subheading"} align="center">
            {currentPage}
          </Text>
        </View>
      </GuideHighlight>

      {/* Page dots — a pre-reader's sense of "how much is left". */}
      {pages.length > 1 ? (
        <View style={{ flexDirection: "row", gap: theme.space[2] }}>
          {pages.map((_, index) => (
            <View
              key={index}
              style={{
                width: index === page ? 14 : 9,
                height: index === page ? 14 : 9,
                borderRadius: 999,
                backgroundColor: index <= page ? theme.colors.accent : theme.colors.starTrack,
              }}
            />
          ))}
        </View>
      ) : null}

      <View style={{ width: "100%", gap: theme.space[3] }}>
        <Button
          label="Read it again"
          icon="🔁"
          tone="quiet"
          disabled={isSpeaking}
          onPress={() => void voiceController.speak(currentPage, child?.preferred_language)}
        />
        <Button
          label={isLastPage ? "The end!" : "Next page"}
          icon={isLastPage ? "🎉" : "➡️"}
          tone="primary"
          onPress={() => {
            if (isLastPage) {
              onContinue();
            } else {
              setPage((current) => current + 1);
            }
          }}
        />
      </View>
    </View>
  );
}

/** Two sentences per page keeps each TTS burst short enough to follow. */
function splitIntoPages(text: string): string[] {
  const sentences = text
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);

  if (sentences.length <= 2) return [text.trim()];

  const pages: string[] = [];
  for (let i = 0; i < sentences.length; i += 2) {
    pages.push(sentences.slice(i, i + 2).join(" "));
  }
  return pages;
}
