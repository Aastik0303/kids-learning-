import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, TextInput, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";

import { TeacherStage } from "@/components/avatar/TeacherStage";
import { TeachingDrawing } from "@/components/blackboard/TeachingDrawing";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { ErrorState } from "@/components/common/StateViews";
import { ScheduleStrip } from "@/components/shared/ScheduleStrip";
import { AnswerChoice } from "@/components/curriculum/AnswerChoice";
import { ClassTrace } from "@/components/class/ClassTrace";
import { MicButton } from "@/features/voice/MicButton";
import { voiceController } from "@/features/voice/VoiceController";
import { useAiTeacherClass, SPEAK_NOW } from "@/features/learning/useAiTeacherClass";
import { avatarMoodForTeacher } from "@/lib/avatarMood";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useAudioStore } from "@/store/audioStore";
import { useUiStore } from "@/store/uiStore";

/**
 * The AI Teacher - the class.
 *
 * The teacher retrieves from the project's own notes, explains in one of nine
 * strategies and asks five questions, and a stage is one level out of today's
 * frozen plan. Finishing one marks that level done on the Adventure board and
 * unlocks the next; finishing the last one ends the day, and the class will not
 * reopen until tomorrow.
 *
 * Every question gets three turns: it is asked, then asked again with a hint -
 * a deeper explanation and two or three things to choose between - and then, if
 * it still has not come, the answer is told and explained and the class moves
 * on. That third turn is not a test and carries no mark.
 *
 * **There is no score on this screen.** No number goes up when the child is
 * right and down when they are not, because a four-year-old still learning what
 * a letter *is* should be watching the letter. What is drawn instead is where
 * they are: which question of the five, and which level of the day.
 *
 * Nothing here decides any of that. The server sends `stage` of `stages_total`,
 * and `day_complete` with `expects: "done"` when the day is over. This screen
 * renders what it is told, which is what stops a relaunch being a way back into
 * a day that is finished.
 *
 * One screen, no scrolling. A two- or three-year-old does not scroll to find
 * the rest of a question: a screen that is cut off simply looks finished, so an
 * answer or a microphone below the fold is, to them, not there at all. The
 * teacher is the one part that stretches; everything else keeps its own height.
 */

/** What each step is called on screen, for the grown-up reading along. */
const STEP_LABELS: Record<string, string> = {
  explain: "👂 Listen",
  say_it: "🗣️ Say it",
  draw: "✏️ Draw it",
  match: "👀 Find it",
  quiz: "🧠 One more",
  /** The check-in the schedule opens with: taught two days ago, asked again. */
  retention: "🧩 Remember",
  /** Every fifth day one subject's level steps aside for one of these. */
  poem: "🎵 Poem",
};

const HINT_LABEL = "💡 Here is a hint";
// The third turn is a story - a real moment, the picture beside it, and the
// name for it last - so the label announces the telling rather than the answer.
// "Here is the answer" over a story whose whole point is that the answer comes
// at the end was the label giving away the ending.
const REVEAL_LABEL = "🔑 Let me show you";

/** Why the microphone did not produce an answer, in words a grown-up can act on. */
const MIC_TROUBLE: Record<string, string> = {
  blocked:
    "The microphone is off. Ask a grown-up to allow it in the phone's settings, then tap it again.",
  unsupported: "This device cannot listen. Tap an answer, or type it with the keyboard button.",
  silence: "I did not hear anything. Tap the microphone and try again.",
};

export function AiTeacherScreen() {
  const theme = useTheme();
  const {
    turn,
    example,
    busy,
    speaking,
    listening,
    reacting,
    error,
    micNote,
    secondsLeft,
    answer,
    speakAnswer,
    askSomething,
    repeat,
  } = useAiTeacherClass();

  const micPermission = useAudioStore((state) => state.micPermission);
  const canListen = micPermission !== "unavailable";
  const [typingOpen, setTypingOpen] = useState(false);
  const [typed, setTyped] = useState("");

  /**
   * No second avatar. The panda is the whole middle of this screen, and the
   * corner dock beside it would be the same character twice - a three-year-old
   * looks at whichever moved last.
   */
  const setDockHidden = useUiStore((state) => state.setDockHidden);
  useFocusEffect(
    useCallback(() => {
      setDockHidden(true);
      return () => {
        setDockHidden(false);
        // A tab switch does not unmount this screen, so without this the
        // teacher carries on explaining over whatever the child moved to -
        // and the games on the Adventure board speak as well. One voice at a
        // time is the rule everywhere in this app.
        void voiceController.stopAll();
      };
    }, [setDockHidden]),
  );

  useEffect(() => {
    setTyped("");
  }, [turn?.session_id, turn?.questions_asked, turn?.attempt]);

  const stages = turn?.stages_total || 1;
  // How far through this level's five questions the child is. Progress, not a
  // score: it only goes up, and a question the teacher had to answer counts the
  // same as one the child got.
  const perStage = turn?.questions_per_stage ?? 5;
  const done = Math.min(turn?.questions_asked ?? 0, perStage);
  const dayDone = Boolean(turn?.day_complete);
  const reciting = Boolean(turn?.is_poem);
  const revealing = Boolean(turn?.is_reveal);

  /**
   * What the panda's face is doing. A wrong answer makes it *kind*, never sad:
   * sad and crying are for the app's own failures, which here means the
   * microphone that heard nothing and the server that did not answer.
   */
  const mood = avatarMoodForTeacher({
    speaking,
    listening,
    waiting: busy,
    reacting,
    sorry: micNote === "silence",
    failed: Boolean(error),
    turn,
  });

  /**
   * What tells the board this is a new turn and it should be wiped. Every part
   * of a turn that changes what is drawn is in it, the attempt included: a
   * question asked again with a hint draws its picture again rather than
   * leaving the finished one sitting there.
   */
  const boardKey = [
    turn?.session_id ?? "none",
    turn?.topic_id ?? "",
    turn?.step ?? "",
    turn?.step_index ?? 0,
    turn?.questions_asked ?? 0,
    turn?.attempt ?? 1,
    turn?.visual_kind ?? "",
    turn?.visual_value ?? "",
  ].join("|");

  const chip = (background: string, colour: string, label: string, testID?: string) => (
    <View
      testID={testID}
      style={{
        alignSelf: "center",
        borderRadius: theme.radius.pill,
        backgroundColor: background,
        paddingHorizontal: theme.space[4],
        paddingVertical: theme.space[2],
      }}
    >
      <Text variant="label" color={colour} align="center">
        {label}
      </Text>
    </View>
  );

  const wantsAnswer =
    Boolean(turn?.question) &&
    turn?.expects !== "ready" &&
    turn?.expects !== "trace" &&
    !dayDone;

  return (
    <Screen scroll={false} contentStyle={{ paddingBottom: theme.space[4] }}>
      <View style={{ flex: 1, gap: theme.space[3] }}>
        <ScheduleStrip />

        {/* Where the child is in the *day* - not a difficulty they have climbed
            to - and how far through this level's five questions. */}
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: theme.space[3],
            borderRadius: theme.radius.xxl,
            backgroundColor: theme.colors.surfaceRaised,
            paddingHorizontal: theme.space[4],
            paddingVertical: theme.space[3],
            ...theme.shadows.soft,
          }}
        >
          <View style={{ flex: 1 }}>
            <Text variant="overline" color={theme.palette.sky}>
              🧑‍🏫 Today's class
            </Text>
            <Text variant="heading" numberOfLines={1}>
              {dayDone ? "All done for today!" : (turn?.topic_title ?? "Today's lesson")}
            </Text>
          </View>
          <View style={{ alignItems: "flex-end", gap: theme.space[2] }}>
            <Text variant="label">
              🎯 {turn?.stage ?? 1}/{stages}
            </Text>
            {/* The five questions as five dots. A pre-reader cannot read "3 of
                5", and a filled dot is the same fact without a number in it. */}
            {dayDone ? null : (
              <View
                style={{ flexDirection: "row", gap: theme.space[1] }}
                accessibilityLabel={`Question ${Math.min(done + 1, perStage)} of ${perStage}`}
                testID="question-dots"
              >
                {Array.from({ length: perStage }, (_, index) => (
                  <View
                    key={index}
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: 5,
                      backgroundColor:
                        index < done ? theme.palette.leaf : theme.inkAlpha.a14,
                    }}
                  />
                ))}
              </View>
            )}
          </View>
        </View>

        {turn?.step && !dayDone ? (
          <Text variant="overline" align="center" muted>
            {STEP_LABELS[turn.step] ?? turn.step} · step {(turn.step_index ?? 0) + 1} of{" "}
            {turn.steps_total ?? 5}
          </Text>
        ) : null}

        {error ? <ErrorState message={error} /> : null}

        {/* The class card. The teacher is the one thing in it that stretches. */}
        <View
          style={{
            flex: 1,
            gap: theme.space[3],
            alignItems: "center",
            borderRadius: theme.radius.card,
            backgroundColor: theme.colors.surface,
            padding: theme.space[4],
            ...theme.shadows.card,
          }}
        >
          {/* A level finished. This is the only place the Adventure board ever
              moves from, so it is worth the child seeing it happen. */}
          {turn?.topic_completed
            ? chip(
                theme.palette.leafLight,
                theme.palette.leaf,
                `🎉 Level finished${turn.stars_earned ? ` · ⭐ ${turn.stars_earned}` : ""}${
                  turn.next_topic_unlocked ? " · a new level opened" : ""
                }`,
                "level-complete",
              )
            : null}

          {/* What the teacher said about the last answer. Warm either way, and
              with no number after it - there is nothing to add up. */}
          {turn?.feedback
            ? chip(
                turn.is_correct ? theme.palette.leafLight : theme.palette.sunPale,
                turn.is_correct ? theme.palette.leaf : theme.palette.ink,
                turn.feedback,
              )
            : null}

          {/* Which of the question's three turns this is, when it is not the
              first. Named for what the teacher is doing, never for what the
              child did. */}
          {turn?.is_hint || revealing
            ? chip(
                revealing ? theme.palette.skyLight : theme.palette.sunPale,
                revealing ? theme.palette.sky : theme.palette.ink,
                revealing ? REVEAL_LABEL : HINT_LABEL,
                revealing ? "reveal" : "hint",
              )
            : null}

          {/* The teacher, holding what it is teaching. */}
          <TeacherStage state={mood} isSpeaking={speaking}>
            {/* The concept stays mounted underneath the example rather than
                being swapped out for it. Unmounting would restart the chalk
                every time an example came and went, so a letter would be drawn
                from nothing three times inside one explanation. */}
            <View style={[StyleSheet.absoluteFill, { opacity: example ? 0 : 1 }]}>
              {dayDone ? null : (
                <TeachingDrawing
                  visualKind={turn?.visual_kind}
                  visualValue={turn?.visual_value}
                  playKey={boardKey}
                />
              )}
            </View>

            {/* The thing the teacher is naming at this exact moment. A child
                who cannot read hears "apple" with the letter on the board and
                nothing to connect it to, so the letter steps aside for three
                seconds. */}
            {example ? (
              <View
                style={[StyleSheet.absoluteFill, { alignItems: "center", justifyContent: "center" }]}
                testID="spoken-example"
              >
                <Text style={{ fontSize: 54, lineHeight: 60 }}>{example.icon}</Text>
                {/* For the grown-up alongside. The child is listening to the
                    word at this exact moment, which is the point of the timing. */}
                <Text variant="caption" muted style={{ textTransform: "capitalize" }}>
                  {example.word}
                </Text>
              </View>
            ) : null}
          </TeacherStage>

          {/* Said, not shown: the explanation is for the ear. What a child
              looks at is the picture above and the question here, which is all
              they can use. */}
          {busy && !turn ? (
            <Text variant="subheading" align="center" muted>
              Waking the teacher up…
            </Text>
          ) : null}
          {turn?.question ? (
            <Text variant="childPrompt" align="center" numberOfLines={3}>
              {turn.question}
            </Text>
          ) : null}

          {/* The day is over. There is nothing to answer and nothing to open -
              the next lesson is tomorrow's, and the server says so, which is
              why coming back to this screen lands right here again. */}
          {dayDone ? (
            <View style={{ alignItems: "center", gap: theme.space[2] }} testID="day-complete">
              <Text variant="subheading" align="center" muted>
                Come back tomorrow for the next one.
              </Text>
            </View>
          ) : null}

          {/* Explaining is not a question: there is one thing to do, and it is
              to carry on. The button is here for a grown-up - the class moves
              on by itself, because a two-year-old cannot be relied on to press
              anything. */}
          {turn?.expects === "ready" && !dayDone ? (
            <Pressable
              accessibilityRole="button"
              disabled={busy || speaking}
              onPress={() => answer("ready")}
              style={{
                minHeight: theme.touchTarget.child,
                justifyContent: "center",
                borderRadius: theme.radius.xl,
                backgroundColor: theme.palette.leaf,
                paddingHorizontal: theme.space[6],
                opacity: busy || speaking ? 0.5 : 1,
              }}
            >
              <Text variant="subheading" color={theme.palette.white} align="center">
                {reciting ? "🎵 Next bit" : revealing ? "👍 I see - next one" : "👍 Got it"}
                {secondsLeft !== null ? ` (${secondsLeft})` : ""}
              </Text>
            </Pressable>
          ) : null}

          {/* The drawing step. Nothing here is marked: the child draws it, and
              the lesson moves on when they have. */}
          {turn?.expects === "trace" && turn.trace_target ? (
            <ClassTrace
              target={turn.trace_target}
              disabled={busy || speaking}
              onDone={() => answer("done")}
            />
          ) : null}

          {/* What to tap. The server says what was offered; it never says which
              one is right, so nothing here can give the answer away. Each one
              is a picture with its word underneath, because two words a child
              cannot read are the same button twice. */}
          {turn?.options?.length && !dayDone ? (
            <View
              style={{
                flexDirection: "row",
                flexWrap: "wrap",
                justifyContent: "center",
                gap: theme.space[3],
              }}
            >
              {turn.options.map((option) => (
                <Pressable
                  key={option}
                  accessibilityRole="button"
                  accessibilityLabel={option}
                  disabled={busy || speaking}
                  onPress={() => answer(option)}
                  style={{
                    minHeight: theme.touchTarget.child,
                    minWidth: 96,
                    alignItems: "center",
                    justifyContent: "center",
                    borderRadius: theme.radius.xl,
                    backgroundColor: theme.colors.surface,
                    paddingHorizontal: theme.space[4],
                    paddingVertical: theme.space[2],
                    opacity: busy || speaking ? 0.5 : 1,
                    ...theme.shadows.soft,
                  }}
                >
                  <AnswerChoice option={option} offered={turn.options ?? []} />
                </Pressable>
              ))}
            </View>
          ) : null}

          {/* The controls, on one row. Their pictures carry them - the child
              cannot read the words anyway - and the labels are on the
              accessibility side at every size. */}
          {dayDone ? null : (
            <View
              style={{
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "center",
                gap: theme.space[3],
              }}
            >
              <RoundControl
                label="🔊"
                accessibilityLabel="Say it again"
                disabled={!turn || speaking}
                onPress={() => void repeat()}
              />
              {canListen ? (
                <RoundControl
                  label="🙋"
                  accessibilityLabel="Ask me anything"
                  // Not disabled while the teacher is talking: interrupting it
                  // is exactly what this button is for, and the handler stops
                  // the speech itself. Waiting for a long explanation to finish
                  // is indistinguishable from a button that does not work.
                  disabled={!turn || busy || listening}
                  onPress={() => void askSomething()}
                />
              ) : null}
              {canListen && wantsAnswer ? (
                <MicButton onPress={() => void speakAnswer()} disabled={!turn || busy} size="large" />
              ) : null}
              {wantsAnswer ? (
                <RoundControl
                  label="⌨️"
                  accessibilityLabel={typingOpen ? "Hide the typing box" : "Type the answer instead"}
                  onPress={() => setTypingOpen((open) => !open)}
                />
              ) : null}
            </View>
          )}

          {/* What the microphone is doing, in words, because a four-year-old
              cannot tell a pulsing circle from a decoration. */}
          {wantsAnswer ? (
            <Text
              variant="label"
              align="center"
              color={listening ? theme.palette.leaf : theme.colors.textMuted}
            >
              {listening ? "🎤 I am listening…" : speaking ? " " : SPEAK_NOW}
            </Text>
          ) : null}

          {/* Why the microphone did not answer. For the grown-up alongside -
              the child has the options and the typing box either way, so a
              broken microphone never blocks the lesson. */}
          {micNote && !dayDone ? (
            <Text variant="body" align="center" muted testID="mic-note">
              🎤 {MIC_TROUBLE[micNote] ?? ""}
            </Text>
          ) : null}

          {/* Typing is for the grown-up sitting alongside, and for a device
              with no recogniser. It is folded away by default: a permanent
              input and its button is a row the answers need, and it is the one
              control here no child uses. */}
          {typingOpen && wantsAnswer ? (
            <View style={{ flexDirection: "row", gap: theme.space[2], width: "100%" }}>
              <TextInput
                value={typed}
                onChangeText={setTyped}
                placeholder="Type the answer"
                accessibilityLabel="Type the answer"
                editable={!busy}
                onSubmitEditing={() => {
                  if (typed.trim()) answer(typed.trim());
                }}
                style={{
                  flex: 1,
                  minHeight: theme.touchTarget.parent,
                  borderRadius: theme.radius.md,
                  borderWidth: 2,
                  borderColor: theme.colors.border,
                  backgroundColor: theme.colors.surface,
                  paddingHorizontal: theme.space[4],
                  color: theme.colors.text,
                  fontWeight: "700",
                }}
              />
              <Pressable
                accessibilityRole="button"
                disabled={busy || !typed.trim()}
                onPress={() => answer(typed.trim())}
                style={{
                  minHeight: theme.touchTarget.parent,
                  justifyContent: "center",
                  borderRadius: theme.radius.md,
                  backgroundColor: theme.palette.sky,
                  paddingHorizontal: theme.space[5],
                  opacity: busy || !typed.trim() ? 0.5 : 1,
                }}
              >
                <Text variant="label" color={theme.palette.white}>
                  Answer
                </Text>
              </Pressable>
            </View>
          ) : null}
        </View>
      </View>
    </Screen>
  );
}

/** One of the small round controls beside the microphone. */
function RoundControl({
  label,
  accessibilityLabel,
  disabled,
  onPress,
}: {
  label: string;
  accessibilityLabel: string;
  disabled?: boolean;
  onPress: () => void;
}) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      disabled={disabled}
      onPress={onPress}
      style={{
        // Chrome rather than a learning control, so the parent touch floor
        // applies - the room on this screen belongs to the answers.
        minHeight: theme.touchTarget.parent,
        minWidth: theme.touchTarget.parent,
        alignItems: "center",
        justifyContent: "center",
        borderRadius: theme.radius.pill,
        backgroundColor: theme.colors.surface,
        opacity: disabled ? 0.5 : 1,
        ...theme.shadows.soft,
      }}
    >
      <Text variant="subheading">{label}</Text>
    </Pressable>
  );
}
