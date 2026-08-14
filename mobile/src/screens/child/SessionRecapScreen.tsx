import { useEffect } from "react";
import { View } from "react-native";
import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { useGuide } from "@/ai/GuideProvider";
import { AvatarFace } from "@/components/avatar/AvatarFace";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { Screen } from "@/components/common/Screen";
import { StarRow } from "@/components/common/StarRow";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { haptics } from "@/services/audio/haptics";
import { useChildStore } from "@/store/childStore";
import { classVisual } from "@/theme/colors";
import type { ChildStackParamList } from "@/navigation/routes";

/**
 * End-of-lesson recap (spec section 23). Celebration first, numbers
 * second — the point is that the child feels the win.
 */
export function SessionRecapScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ChildStackParamList>>();
  const route = useRoute<RouteProp<ChildStackParamList, "SessionRecap">>();
  const { pathId, stageNumber, starsEarned, correctCount, totalCount } = route.params;

  const { dispatch } = useGuide();
  const child = useChildStore((state) => state.activeChild);
  const visual = classVisual(pathId);

  useEffect(() => {
    haptics.celebrate();
    void dispatch("LESSON_COMPLETED", { surface: "lesson" });
    // Fire the celebration exactly once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const nextStage = stageNumber + 1;

  return (
    <Screen reserveDockSpace>
      <View style={{ gap: theme.space[6] }}>
        <Card variant="panel" style={{ alignItems: "center", gap: theme.space[4] }}>
          <AvatarFace state="celebrating" size={130} />
          <Text variant="display" align="center">
            You did it!
          </Text>
          <StarRow earned={Math.max(starsEarned, 1)} total={3} size={40} animate />
          <Text variant="subheading" align="center" muted>
            {visual.label} — level {stageNumber}
          </Text>
        </Card>

        {/* The numbers, kept small and secondary. */}
        <Card variant="lift" style={{ flexDirection: "row", justifyContent: "space-around" }}>
          <Stat label="Right" value={String(correctCount)} icon="✅" />
          <Stat label="Tried" value={String(totalCount)} icon="🎯" />
          <Stat label="Stars" value={String(starsEarned)} icon="⭐" />
        </Card>

        <View style={{ gap: theme.space[3] }}>
          <Button
            label="Next level"
            icon="▶️"
            tone="primary"
            onPress={() =>
              navigation.replace("Lesson", {
                pathId,
                stageNumber: nextStage,
                mode: child?.learning_mode === "toddler" ? "toddler" : "standard",
              })
            }
          />
          <Button
            label="See my rewards"
            icon="🏆"
            tone="accent"
            onPress={() => navigation.navigate("ChildTabs", { screen: "Rewards" })}
          />
          <Button
            label="Back home"
            icon="🏠"
            tone="quiet"
            onPress={() => navigation.navigate("ChildTabs", { screen: "ChildHome" })}
          />
        </View>
      </View>
    </Screen>
  );
}

function Stat({ label, value, icon }: { label: string; value: string; icon: string }) {
  const theme = useTheme();
  return (
    <View style={{ alignItems: "center", gap: theme.space[1] }}>
      <Text style={{ fontSize: 24 }}>{icon}</Text>
      <Text variant="heading">{value}</Text>
      <Text variant="caption" muted>
        {label}
      </Text>
    </View>
  );
}
