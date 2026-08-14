import { View } from "react-native";
import { useQuery } from "@tanstack/react-query";

import { Card } from "@/components/common/Card";
import { EmptyState, ErrorState, LoadingState, Pill } from "@/components/common/StateViews";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { progressApi } from "@/services/api/progressApi";
import { useChildStore } from "@/store/childStore";
import type { ActivityAttempt } from "@/types/domain";

/**
 * Attempt-by-attempt history from GET /history/{child_id}, grouped by
 * session so a parent can see how one sitting actually went.
 */
export function ParentProgressScreen() {
  const theme = useTheme();
  const child = useChildStore((state) => state.activeChild);

  const history = useQuery({
    queryKey: ["history", child?.child_id],
    queryFn: () => progressApi.history(child!.child_id),
    enabled: !!child,
  });

  if (history.isLoading) {
    return (
      <Screen backdrop={false}>
        <LoadingState message="Loading history…" />
      </Screen>
    );
  }

  if (history.isError) {
    return (
      <Screen backdrop={false}>
        <ErrorState message="We could not load the history." onRetry={() => void history.refetch()} />
      </Screen>
    );
  }

  const attempts = history.data?.attempts ?? [];

  if (attempts.length === 0) {
    return (
      <Screen backdrop={false}>
        <EmptyState
          icon="📜"
          title="No sessions yet"
          subtitle="Once your child plays a level, it will show up here."
        />
      </Screen>
    );
  }

  const sessions = groupBySession(attempts);

  return (
    <Screen backdrop={false}>
      <View style={{ gap: theme.space[5] }}>
        <Text variant="title">Session history</Text>

        {sessions.map((session) => {
          const correct = session.attempts.filter((attempt) => attempt.is_correct).length;
          const accuracy = correct / session.attempts.length;

          return (
            <Card key={session.sessionId} variant="lift" style={{ gap: theme.space[3] }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: theme.space[2] }}>
                <View style={{ flex: 1 }}>
                  <Text variant="subheading">{session.topic || "Session"}</Text>
                  <Text variant="caption" muted>
                    {formatWhen(session.attempts[0]?.created_at)}
                  </Text>
                </View>
                <Pill
                  label={`${correct}/${session.attempts.length}`}
                  tone={accuracy >= 0.7 ? "success" : "accent"}
                />
              </View>

              <View style={{ gap: theme.space[1] }}>
                {session.attempts.slice(0, 8).map((attempt) => (
                  <View
                    key={attempt.id}
                    style={{ flexDirection: "row", alignItems: "center", gap: theme.space[2] }}
                  >
                    <Text style={{ fontSize: 14 }}>{attempt.is_correct ? "✅" : "❌"}</Text>
                    <Text variant="caption" style={{ flex: 1 }} numberOfLines={1}>
                      {attempt.skill || attempt.topic}
                    </Text>
                    <Text variant="caption" muted numberOfLines={1}>
                      said "{attempt.child_answer}"
                    </Text>
                    {attempt.attempt_number > 1 ? (
                      <Text variant="caption" muted>
                        try {attempt.attempt_number}
                      </Text>
                    ) : null}
                  </View>
                ))}
                {session.attempts.length > 8 ? (
                  <Text variant="caption" muted>
                    + {session.attempts.length - 8} more
                  </Text>
                ) : null}
              </View>
            </Card>
          );
        })}
      </View>
    </Screen>
  );
}

type SessionGroup = { sessionId: string; topic: string; attempts: ActivityAttempt[] };

/** Newest session first, attempts within a session in original order. */
function groupBySession(attempts: ActivityAttempt[]): SessionGroup[] {
  const groups = new Map<string, SessionGroup>();

  for (const attempt of attempts) {
    const existing = groups.get(attempt.session_id);
    if (existing) {
      existing.attempts.push(attempt);
    } else {
      groups.set(attempt.session_id, {
        sessionId: attempt.session_id,
        topic: attempt.topic,
        attempts: [attempt],
      });
    }
  }

  return Array.from(groups.values()).reverse();
}

function formatWhen(iso: string | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
