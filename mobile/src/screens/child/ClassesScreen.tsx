import { useEffect } from "react";
import { View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import { useQuery } from "@tanstack/react-query";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { useGuide } from "@/ai/GuideProvider";
import { FeatureCard } from "@/components/cards/FeatureCard";
import { ErrorState, LoadingState } from "@/components/common/StateViews";
import { ResponsiveGrid } from "@/components/responsive/ResponsiveGrid";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { learningApi } from "@/services/api/learningApi";
import { FEATURES } from "@/features/catalog";
import { useChildStore } from "@/store/childStore";
import type { ChildStackParamList } from "@/navigation/routes";

/**
 * All classes, driven by the backend's own path list rather than a
 * hardcoded array (spec section 6). Mobile-only features with no backend
 * path are appended so the child still sees the full offering.
 */
export function ClassesScreen() {
  const theme = useTheme();
  const navigation = useNavigation<NativeStackNavigationProp<ChildStackParamList>>();
  const { dispatch } = useGuide();
  const child = useChildStore((state) => state.activeChild);

  const paths = useQuery({
    queryKey: ["learning", "paths"],
    queryFn: () => learningApi.listPaths(),
    staleTime: 30 * 60 * 1000,
  });

  useEffect(() => {
    void dispatch("CLASSES_OPENED", { surface: "home" });
    // Announce once per visit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (paths.isLoading) {
    return (
      <Screen reserveDockSpace>
        <LoadingState message="Opening your classes…" />
      </Screen>
    );
  }

  if (paths.isError) {
    return (
      <Screen reserveDockSpace>
        <ErrorState
          message="We could not load your classes."
          onRetry={() => void paths.refetch()}
        />
      </Screen>
    );
  }

  const backendPaths = paths.data ?? [];
  // Features the mobile app offers that have no backend path yet.
  const localOnly = FEATURES.filter((feature) => feature.pathId === null);

  return (
    <Screen reserveDockSpace>
      <View style={{ gap: theme.space[6] }}>
        <Text variant="title">Classes</Text>

        <ResponsiveGrid columns={{ smallPhone: 1, phone: 2, tablet: 3 }}>
          {backendPaths.map((path) => {
            const progress = child?.path_progress[path.path_id];
            const isComplete = child?.completed_paths.includes(path.path_id) ?? false;
            // The mixed final only opens once every core path is done.
            const isLocked = path.path_id === "mixed_final" && !child?.mixed_path_unlocked;

            return (
              <FeatureCard
                key={path.path_id}
                featureId={path.path_id}
                title={path.title}
                description={path.description}
                locked={isLocked}
                progress={
                  isComplete
                    ? "Finished!"
                    : progress
                      ? `Level ${progress.current_stage} of ${path.total_stages}`
                      : undefined
                }
                onPress={() => {
                  if (isLocked) return;
                  navigation.navigate("ClassDetail", { pathId: path.path_id });
                }}
              />
            );
          })}
        </ResponsiveGrid>

        {localOnly.length > 0 ? (
          <View style={{ gap: theme.space[4] }}>
            <Text variant="title">Fun extras</Text>
            <ResponsiveGrid columns={{ smallPhone: 1, phone: 2, tablet: 3 }}>
              {localOnly.map((feature) => (
                <FeatureCard
                  key={feature.id}
                  featureId={feature.id}
                  title={feature.title}
                  description={feature.description}
                  compact
                  onPress={() => navigation.navigate("ClassDetail", { pathId: feature.id })}
                />
              ))}
            </ResponsiveGrid>
          </View>
        ) : null}
      </View>
    </Screen>
  );
}
