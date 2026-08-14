import { useEffect } from "react";
import { View } from "react-native";

import { CompleteBeat, Introduce } from "@/activities/Introduce/Introduce";
import { CountObjects } from "@/activities/Counting/CountObjects";
import { FreeDraw } from "@/activities/FreeDraw/FreeDraw";
import { StoryListen } from "@/activities/Story/StoryListen";
import { TapChoice } from "@/activities/TapChoice/TapChoice";
import { TraceActivity } from "@/activities/Trace/TraceActivity";
import { VoiceRepeat } from "@/activities/VoiceRepeat/VoiceRepeat";
import { WordBuild } from "@/activities/WordBuild/WordBuild";
import type { ActivityComponentProps } from "@/activities/types";

import { GuideHighlight } from "@/components/common/GuideHighlight";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { track } from "@/services/analytics/analytics";
import { isEnabled } from "@/config/featureFlags";
import type { ActivityKind } from "@/types/activity";

/**
 * ═══ THE ACTIVITY ENGINE (spec section 7) ═══
 *
 *   backend/activity payload
 *          ↓
 *   ActivityRenderer          ← this file
 *          ↓
 *   typed reusable activity component
 *          ↓
 *   child interaction
 *          ↓
 *   backend evaluation
 *          ↓
 *   AI feedback
 *
 * There is exactly one screen for lessons and one for practice. Adding a
 * new activity type means adding a component and one line in the switch —
 * never a new screen or a new route.
 */
export function ActivityRenderer(props: ActivityComponentProps) {
  const { activity, feedback } = props;
  const theme = useTheme();

  // Analytics fires per question, not per render.
  useEffect(() => {
    track("activity_shown", {
      activity_kind: activity.kind,
      path_id: activity.source,
    });
  }, [activity.id, activity.kind, activity.source]);

  return (
    <View style={{ gap: theme.space[5] }}>
      {/* The prompt, shared by every activity type. */}
      <GuideHighlight targetId="question-prompt" kind="visual" label="The question">
        <Text
          variant={props.isToddlerMode ? "toddlerPrompt" : "childPrompt"}
          align="center"
        >
          {activity.prompt}
        </Text>
      </GuideHighlight>

      {renderBody(activity.kind, props)}

      {/* Verdict line. The backend decided this — the renderer only shows it. */}
      {feedback ? (
        <Text
          variant="subheading"
          align="center"
          color={feedback.isCorrect ? theme.colors.success : theme.colors.text}
        >
          {feedback.message}
        </Text>
      ) : null}
    </View>
  );
}

function renderBody(kind: ActivityKind, props: ActivityComponentProps) {
  switch (kind) {
    // ── Spoken ────────────────────────────────────────────────────────
    case "voice_repeat":
    case "sentence_repeat":
      return isEnabled("voiceInput") ? (
        <VoiceRepeat {...props} />
      ) : (
        // Voice disabled by flag — the question still has to be answerable.
        <TapChoice {...props} presentation="glyph" />
      );

    // ── Tap / select ──────────────────────────────────────────────────
    case "tap_choice":
      return <TapChoice {...props} presentation="text" />;
    case "image_match":
      return <TapChoice {...props} presentation="glyph" />;
    case "shape_match":
      return <TapChoice {...props} presentation="glyph" />;
    case "color_match":
      return <TapChoice {...props} presentation="swatch" />;
    case "count_objects":
      return <CountObjects {...props} />;
    case "word_build":
      return isEnabled("wordBuilding") ? (
        <WordBuild {...props} />
      ) : (
        <TapChoice {...props} presentation="text" />
      );

    // ── Draw / trace ──────────────────────────────────────────────────
    case "letter_trace":
    case "shape_trace":
      return isEnabled("tracing") ? (
        <TraceActivity {...props} />
      ) : (
        <Introduce {...props} />
      );
    case "free_draw":
      return isEnabled("freeDraw") ? <FreeDraw {...props} /> : <Introduce {...props} />;

    // ── Narrative / teaching ──────────────────────────────────────────
    case "story_listen":
      return isEnabled("stories") ? <StoryListen {...props} /> : <Introduce {...props} />;
    case "introduce":
      return <Introduce {...props} />;
    case "complete":
      return <CompleteBeat {...props} />;
  }
}
