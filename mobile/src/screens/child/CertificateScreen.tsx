import { View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import { useQuery } from "@tanstack/react-query";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { EmptyState, LoadingState } from "@/components/common/StateViews";
import { Screen } from "@/components/common/Screen";
import { StarRow } from "@/components/common/StarRow";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { progressApi } from "@/services/api/progressApi";
import { useChildStore } from "@/store/childStore";
import type { ChildStackParamList } from "@/navigation/routes";

/**
 * The Little Learning Explorer certificate.
 *
 * Whether it is unlocked is entirely the backend's call. This screen
 * renders the award; it never decides eligibility.
 */
export function CertificateScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ChildStackParamList>>();
  const child = useChildStore((state) => state.activeChild);

  const certificate = useQuery({
    queryKey: ["progress", "certificate", child?.child_id],
    queryFn: () => progressApi.certificate(child!.child_id),
    enabled: !!child,
  });

  if (certificate.isLoading) {
    return (
      <Screen reserveDockSpace>
        <LoadingState message="Getting your certificate…" />
      </Screen>
    );
  }

  const data = certificate.data;

  if (!data?.unlocked) {
    return (
      <Screen reserveDockSpace>
        <View style={{ gap: theme.space[4] }}>
          <EmptyState
            icon="🔒"
            title="Not yet!"
            subtitle="Finish every class and the big final to earn your certificate."
          />
          <Button label="Back" tone="quiet" onPress={() => navigation.goBack()} />
        </View>
      </Screen>
    );
  }

  return (
    <Screen reserveDockSpace>
      <View style={{ gap: theme.space[5] }}>
        <Card
          variant="panel"
          style={{
            alignItems: "center",
            gap: theme.space[4],
            borderWidth: 4,
            borderColor: theme.colors.accent,
            paddingVertical: theme.space[8],
          }}
        >
          <Text style={{ fontSize: 60 }}>🎓</Text>
          <Text variant="overline" muted>
            Certificate of achievement
          </Text>
          <Text variant="title" align="center">
            {data.title}
          </Text>

          <View style={{ height: 1, alignSelf: "stretch", backgroundColor: theme.colors.divider }} />

          <Text variant="body" muted>
            Awarded to
          </Text>
          <Text variant="display" align="center">
            {data.child_name ?? child?.name ?? "Little Explorer"}
          </Text>

          <StarRow earned={3} total={3} size={32} animate />

          <Text variant="body" align="center" muted>
            {data.celebration_line}
          </Text>

          {data.completion_date ? (
            <Text variant="caption" muted>
              {data.completion_date}
            </Text>
          ) : null}

          <Text variant="caption" muted>
            {data.stars_earned} stars earned
          </Text>
        </Card>

        <Button label="Back to rewards" icon="🏆" tone="primary" onPress={() => navigation.goBack()} />
      </View>
    </Screen>
  );
}
