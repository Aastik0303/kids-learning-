import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { GuestHomeScreen } from "@/screens/guest/GuestHomeScreen";
import { FeatureDemoScreen } from "@/screens/guest/FeatureDemoScreen";
import type { GuestStackParamList } from "@/navigation/routes";

const Stack = createNativeStackNavigator<GuestStackParamList>();

/**
 * The public surface. Identical for every visitor — one common home that
 * showcases the whole product before anyone signs in (spec section 2).
 */
export function GuestNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false, animation: "slide_from_right" }}>
      <Stack.Screen name="GuestHome" component={GuestHomeScreen} />
      <Stack.Screen name="FeatureDemo" component={FeatureDemoScreen} />
    </Stack.Navigator>
  );
}
