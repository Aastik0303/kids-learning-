import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { View } from "react-native";

import { Text } from "@/components/common/Text";
import { AdventureScreen } from "@/screens/child/AdventureScreen";
import { AdventureSubjectScreen } from "@/screens/child/AdventureSubjectScreen";
import { AdventureLevelScreen } from "@/screens/child/AdventureLevelScreen";
import { AiTeacherScreen } from "@/screens/child/AiTeacherScreen";
import { ChildHomeScreen } from "@/screens/child/ChildHomeScreen";
import { ClassesScreen } from "@/screens/child/ClassesScreen";
import { ClassDetailScreen } from "@/screens/child/ClassDetailScreen";
import { ClassScreen } from "@/screens/child/ClassScreen";
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
 * Child tabs: the class, the board, the shelf.
 *
 * The app opens on **Class** - the AI Teacher - because the child does not pick
 * a lesson. The sitting is already happening, built out of today's frozen plan,
 * one stage per planned level. **Adventure** shows where every level stands and
 * hands back a game about any the child has already been given; it starts
 * nothing. **Rewards** is the shelf.
 *
 * In toddler mode the bar is hidden entirely - a two-year-old gets one thing at
 * a time and no navigation to get lost in.
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
        name="Class"
        component={AiTeacherScreen}
        options={{
          title: "Class",
          tabBarIcon: ({ focused }) => <TabIcon icon="🧑‍🏫" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="Adventure"
        component={AdventureScreen}
        options={{
          title: "Adventure",
          tabBarIcon: ({ focused }) => <TabIcon icon="🗺️" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="Rewards"
        component={RewardsScreen}
        options={{
          title: "Rewards",
          tabBarIcon: ({ focused }) => <TabIcon icon="🏆" focused={focused} />,
        }}
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

      {/* The board's two deeper pages. Status and play, never a lesson. */}
      <Stack.Screen name="AdventureSubject" component={AdventureSubjectScreen} />
      <Stack.Screen name="AdventureLevel" component={AdventureLevelScreen} />

      {/* The older surfaces. Off the tab bar - nothing a child taps reaches
          them - and kept registered so a grown-up's route in still resolves. */}
      <Stack.Screen name="ChildHome" component={ChildHomeScreen} />
      <Stack.Screen name="Classes" component={ClassesScreen} />
      <Stack.Screen name="Practice" component={PracticeScreen} />
      <Stack.Screen name="ClassDetail" component={ClassDetailScreen} />
      <Stack.Screen
        name="ConductedClass"
        component={ClassScreen}
        options={{ animation: "slide_from_bottom", gestureEnabled: false }}
      />
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
