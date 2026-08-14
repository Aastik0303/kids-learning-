import { useCallback } from "react";
import { Pressable, View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { AvatarFace } from "@/components/avatar/AvatarFace";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { LoadingState, Pill } from "@/components/common/StateViews";
import { Screen } from "@/components/common/Screen";
import { StarRow } from "@/components/common/StarRow";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useAuthStore } from "@/store/authStore";
import { resolveExperienceMode, useChildStore } from "@/store/childStore";
import { haptics } from "@/services/audio/haptics";
import type { ChildProfile } from "@/types/domain";
import type { AuthStackParamList } from "@/navigation/routes";

/**
 * Returning-parent fast path (spec section 3): pick a child and go
 * straight into their experience.
 */
export function ChildSelectScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<AuthStackParamList>>();

  const children = useChildStore((state) => state.children);
  const isLoading = useChildStore((state) => state.isLoading);
  const selectChild = useChildStore((state) => state.selectChild);
  const logout = useAuthStore((state) => state.logout);

  const pick = useCallback(
    async (child: ChildProfile) => {
      haptics.tap();
      // Selecting a child is what flips RootNavigator into the child
      // experience — no explicit navigation needed here.
      await selectChild(child);
    },
    [selectChild],
  );

  if (isLoading && children.length === 0) {
    return (
      <Screen>
        <LoadingState message="Finding your learners…" />
      </Screen>
    );
  }

  return (
    <Screen>
      <View style={{ gap: theme.space[6] }}>
        <View style={{ alignItems: "center", gap: theme.space[3] }}>
          <AvatarFace state="waving" size={92} />
          <Text variant="title" align="center">
            Who is learning today?
          </Text>
        </View>

        <View style={{ gap: theme.space[3] }}>
          {children.map((child) => {
            const mode = resolveExperienceMode(child);
            return (
              <Pressable
                key={child.child_id}
                accessibilityRole="button"
                accessibilityLabel={`Continue as ${child.name}, ${child.stars} stars`}
                onPress={() => void pick(child)}
              >
                <Card variant="lift" style={{ flexDirection: "row", alignItems: "center", gap: theme.space[4] }}>
                  <View
                    style={{
                      width: 64,
                      height: 64,
                      borderRadius: 999,
                      alignItems: "center",
                      justifyContent: "center",
                      backgroundColor: theme.palette.sunLight,
                    }}
                  >
                    <Text style={{ fontSize: 30 }}>{mode === "toddler" ? "🍼" : "🎒"}</Text>
                  </View>

                  <View style={{ flex: 1, gap: theme.space[1] }}>
                    <Text variant="heading">{child.name}</Text>
                    <View style={{ flexDirection: "row", gap: theme.space[2], flexWrap: "wrap" }}>
                      <Pill
                        label={mode === "toddler" ? "Toddler mode" : "Early learner"}
                        tone="accent"
                      />
                      {child.age ? <Pill label={`${child.age} years`} /> : null}
                    </View>
                    <StarRow earned={Math.min(child.stars, 3)} total={3} size={16} />
                  </View>

                  <Text style={{ fontSize: 26 }}>👉</Text>
                </Card>
              </Pressable>
            );
          })}
        </View>

        <Button
          label="Add another child"
          icon="➕"
          tone="quiet"
          size="parent"
          onPress={() => navigation.navigate("ChildSetup")}
        />

        <Button
          label="Sign out"
          tone="quiet"
          size="parent"
          onPress={() => void logout()}
        />
      </View>
    </Screen>
  );
}
