import { ScrollView, View } from "react-native";

import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useTodayPlan } from "@/features/plan/useTodayPlan";

/**
 * Today's schedule, on every screen.
 *
 * The plan is the day's work and the class is built out of it: one stage per
 * planned item, and when the last one is through the day is shut until
 * tomorrow. A rule that shapes the whole sitting cannot live behind a chip the
 * child has to know to tap, so this rides above every screen - the class, the
 * Adventure board, the rewards shelf - and says the same thing on all of them.
 *
 * It is deliberately **not a menu**. Nothing here is tappable: the class opens
 * the next stage by itself and Adventure teaches nothing, so a link would only
 * offer a child a door that does not exist. This says where the day is, and
 * that is all it says.
 *
 * A day has two halves and this shows both. The 🧩 chips are the retention
 * check-ins the scheduler says are due - something taught two days ago, asked
 * again before today's first stage. They come first because that is the order
 * the class asks them in, and they are not counted in the "3/5" on the right: a
 * check-in is not one of the day's levels and answering it moves neither the
 * count nor a star.
 *
 * On a phone the chips scroll sideways rather than wrapping into three rows.
 * The strip is on every screen by rule, so it has to be compact; what it may
 * never do is disappear.
 */
export function ScheduleStrip() {
  const theme = useTheme();
  const { plan, items, retentionTests, complete } = useTodayPlan();

  // Nothing planned is a real answer - a class whose content is still being
  // authored, or a child not signed in yet - and an empty strip would only
  // puzzle. A day with no levels left can still owe a check-in, so both halves
  // are asked before the strip gives up on drawing anything.
  if (!plan || (plan.total === 0 && retentionTests.length === 0)) return null;

  const chip = {
    flexDirection: "row" as const,
    alignItems: "center" as const,
    gap: theme.space[1],
    borderRadius: theme.radius.pill,
    paddingHorizontal: theme.space[3],
    paddingVertical: theme.space[2],
  };

  return (
    <View
      accessibilityLabel="Today's schedule"
      testID="schedule-strip"
      style={{
        flexDirection: "row",
        alignItems: "center",
        gap: theme.space[2],
        borderRadius: theme.radius.xxl,
        backgroundColor: theme.whiteAlpha.a96,
        paddingHorizontal: theme.space[3],
        paddingVertical: theme.space[2],
        ...theme.shadows.card,
      }}
    >
      <Text variant="overline" color={theme.palette.leaf}>
        {complete ? "🎉 Today" : "🗓️ Today"}
      </Text>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={{ flex: 1 }}
        contentContainerStyle={{ gap: theme.space[2], alignItems: "center" }}
      >
        {/* The check-ins first, because that is the order the class asks them
            in: something taught two days ago is remembered before today's new
            thing is taught. They are a different shape from a level chip on
            purpose - no number, no tick - because they are not one of the day's
            stages. */}
        {retentionTests.map((test) => (
          <View
            key={test.test_id}
            testID="schedule-retention"
            style={{ ...chip, backgroundColor: theme.palette.skyLight }}
          >
            <Text variant="caption" color={theme.palette.sky}>
              🧩 {test.title}
            </Text>
          </View>
        ))}

        {items.map((item, index) => (
          <View
            key={item.topic_id}
            style={{
              ...chip,
              backgroundColor: item.done
                ? theme.palette.leafLight
                : item.current
                  ? theme.palette.sunshine
                  : theme.inkAlpha.a08,
            }}
          >
            <Text
              variant="caption"
              color={
                item.done
                  ? theme.palette.leaf
                  : item.current
                    ? theme.palette.ink
                    : theme.colors.textSecondary
              }
            >
              {item.done ? "✅" : item.current ? "▶️" : `${index + 1}`} {item.title}
            </Text>
          </View>
        ))}
      </ScrollView>

      <Text variant="caption" muted>
        {plan.completed}/{plan.total}
      </Text>
    </View>
  );
}
