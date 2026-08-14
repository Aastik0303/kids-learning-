import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { View } from "react-native";

import { Text } from "@/components/common/Text";
import { ChildHomeScreen } from "@/screens/child/ChildHomeScreen";
import { ClassesScreen } from "@/screens/child/ClassesScreen";
import { ClassDetailScreen } from "@/screens/child/ClassDetailScreen";
import { LessonScreen } from "@/screens/child/LessonScreen";
import { PracticeScreen } from "@/screens/child/PracticeScreen";
import { PracticeTopicScreen } from "@/screens/child/PracticeTopicScreen";
import { RewardsScreen } from "@/screens/child/RewardsScreen";
import { SessionRecapScreen } from "@/screens/child/SessionRecapScreen";
import { CertificateScreen } from "@/screens/child/CertificateScreen";
import { StoryScreen } from "@/screens/child/StoryScreen";
import { useTheme } from "@/app/providers/ThemeProvider";
import { resolveExperienceMode, useChildStore } from "@/store/childStore";
import type { ChildStackParamList, ChildTabParamList } from "@/navigation/routes";

const Stack = createNativeStackNavigator<ChildStackParamList>();
const Tabs = createBottomTabNavigator<ChildTabParamList>();

/**
 * Child tabs. In toddler mode the bar is hidden entirely — a 2-year-old
 * gets one activity at a time and no navigation to get lost in
 * (spec section 4).
 */
function ChildTabs() {
  const theme = useTheme();
  const child = useChildStore((state) => state.activeChild);
  const isToddler = resolveExperienceMode(child) === "toddler";

  return (
    <Tabs.Navigator
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: true,
        tabBarStyle: isToddler
          ? { display: "none" }
          : {
              height: 74,
              paddingBottom: 10,
              paddingTop: 8,
              borderTopWidth: 1,
              borderTopColor: theme.colors.border,
              backgroundColor: theme.whiteAlpha.a96,
            },
        tabBarActiveTintColor: theme.colors.primary,
        tabBarInactiveTintColor: theme.colors.textMuted,
        tabBarLabelStyle: { fontSize: 12, fontWeight: "900" },
      }}
    >
      <Tabs.Screen
        name="ChildHome"
        component={ChildHomeScreen}
        options={{ title: "Home", tabBarIcon: ({ focused }) => <TabIcon icon="🏠" focused={focused} /> }}
      />
      <Tabs.Screen
        name="Classes"
        component={ClassesScreen}
        options={{ title: "Classes", tabBarIcon: ({ focused }) => <TabIcon icon="📚" focused={focused} /> }}
      />
      <Tabs.Screen
        name="Practice"
        component={PracticeScreen}
        options={{ title: "Practice", tabBarIcon: ({ focused }) => <TabIcon icon="🎯" focused={focused} /> }}
      />
      <Tabs.Screen
        name="Rewards"
        component={RewardsScreen}
        options={{ title: "Rewards", tabBarIcon: ({ focused }) => <TabIcon icon="🏆" focused={focused} /> }}
      />
    </Tabs.Navigator>
  );
}

function TabIcon({ icon, focused }: { icon: string; focused: boolean }) {
  return (
    <View style={{ opacity: focused ? 1 : 0.55 }}>
      <Text style={{ fontSize: focused ? 26 : 22 }}>{icon}</Text>
    </View>
  );
}

export function ChildNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false, animation: "slide_from_right" }}>
      <Stack.Screen name="ChildTabs" component={ChildTabs} />
      <Stack.Screen name="ClassDetail" component={ClassDetailScreen} />
      {/* Lessons animate up and own the full screen — no tab bar, no exit
          affordance beyond an explicit, deliberate control. */}
      <Stack.Screen
        name="Lesson"
        component={LessonScreen}
        options={{ animation: "slide_from_bottom", gestureEnabled: false }}
      />
      <Stack.Screen name="PracticeTopic" component={PracticeTopicScreen} />
      <Stack.Screen name="Story" component={StoryScreen} />
      <Stack.Screen
        name="SessionRecap"
        component={SessionRecapScreen}
        options={{ animation: "fade", gestureEnabled: false }}
      />
      <Stack.Screen name="Certificate" component={CertificateScreen} />
    </Stack.Navigator>
  );
}
