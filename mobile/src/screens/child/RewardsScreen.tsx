import { useEffect } from "react";
import { View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import { useQuery } from "@tanstack/react-query";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { useGuide } from "@/ai/GuideProvider";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { EmptyState, LoadingState, Pill } from "@/components/common/StateViews";
import { ResponsiveGrid } from "@/components/responsive/ResponsiveGrid";
import { Screen } from "@/components/common/Screen";
import { StarRow } from "@/components/common/StarRow";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { progressApi } from "@/services/api/progressApi";
import { useChildStore } from "@/store/childStore";
import { classVisual } from "@/theme/colors";
import type { ChildStackParamList } from "@/navigation/routes";

/**
 * Stars, collected rewards and the certificate gate.
 *
 * Certificate eligibility is read from the backend, never computed here —
 * `certificate_service.py` owns that decision.
 */
export function RewardsScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ChildStackParamList>>();
  const { dispatch } = useGuide();
  const child = useChildStore((state) => state.activeChild);

  const rewards = useQuery({
    queryKey: ["progress", "rewards", child?.child_id],
    queryFn: () => progressApi.rewards(child!.child_id),
    enabled: !!child,
  });

  const certificate = useQuery({
    queryKey: ["progress", "certificate", child?.child_id],
    queryFn: () => progressApi.certificate(child!.child_id),
    enabled: !!child,
  });

  useEffect(() => {
    void dispatch("REWARDS_OPENED", { surface: "rewards" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (rewards.isLoading) {
    return (
      <Screen reserveDockSpace>
        <LoadingState message="Counting your stars…" />
      </Screen>
    );
  }

  const stars = rewards.data?.stars ?? child?.stars ?? 0;
  const earned = rewards.data?.rewards ?? child?.rewards ?? [];
  const isCertificateReady = certificate.data?.unlocked ?? false;

  return (
    <Screen reserveDockSpace>
      <View style={{ gap: theme.space[6] }}>
        <Text variant="title">Your rewards</Text>

        {/* Star total */}
        <Card variant="panel" style={{ alignItems: "center", gap: theme.space[3] }}>
          <Text style={{ fontSize: 58 }}>⭐</Text>
          <Text variant="display">{stars}</Text>
          <Text variant="subheading" muted>
            stars collected
          </Text>
          <StarRow earned={Math.min(stars, 3)} total={3} size={26} animate />
        </Card>

        {/* Per-class trophies */}
        <View style={{ gap: theme.space[4] }}>
          <Text variant="title">Your trophies</Text>
          {earned.length === 0 ? (
            <EmptyState
              icon="🎁"
              title="No trophies yet"
              subtitle="Finish a whole class to win your first one!"
            />
          ) : (
            <ResponsiveGrid columns={{ smallPhone: 2, tablet: 4 }}>
              {earned.map((reward) => (
                <Card key={reward} variant="tinted" tint={theme.palette.sunLight} style={{ alignItems: "center", gap: theme.space[2], minHeight: 130 }}>
                  <Text style={{ fontSize: 36 }}>🏅</Text>
                  <Text variant="label" align="center">
                    {reward}
                  </Text>
                </Card>
              ))}
            </ResponsiveGrid>
          )}
        </View>

        {/* Classes still to finish */}
        <View style={{ gap: theme.space[4] }}>
          <Text variant="title">Classes</Text>
          <ResponsiveGrid columns={{ smallPhone: 2, tablet: 4 }}>
            {["numbers", "alphabets", "colours", "shapes"].map((pathId) => {
              const visual = classVisual(pathId);
              const done = child?.completed_paths.includes(pathId) ?? false;
              return (
                <Card
                  key={pathId}
                  variant="lift"
                  style={{ alignItems: "center", gap: theme.space[2], minHeight: 140, opacity: done ? 1 : 0.6 }}
                >
                  <Text style={{ fontSize: 32 }}>{done ? visual.icon : "🔒"}</Text>
                  <Text variant="label" align="center">
                    {visual.label}
                  </Text>
                  <Pill label={done ? "Finished" : "In progress"} tone={done ? "success" : "neutral"} />
                </Card>
              );
            })}
          </ResponsiveGrid>
        </View>

        {/* Certificate */}
        <Card
          variant="panel"
          style={{
            gap: theme.space[3],
            alignItems: "center",
            borderWidth: 2,
            borderColor: isCertificateReady ? theme.colors.accent : theme.colors.border,
          }}
        >
          <Text style={{ fontSize: 50 }}>{isCertificateReady ? "🏆" : "🔒"}</Text>
          <Text variant="heading" align="center">
            Saksham IQ Explorer
          </Text>
          <Text variant="body" align="center" muted>
            {isCertificateReady
              ? "You finished everything. Your certificate is ready!"
              : "Finish all four classes and the big final to unlock this."}
          </Text>
          {isCertificateReady ? (
            <Button
              label="See my certificate"
              icon="🎓"
              tone="primary"
              onPress={() => navigation.navigate("Certificate")}
            />
          ) : null}
        </Card>
      </View>
    </Screen>
  );
}
