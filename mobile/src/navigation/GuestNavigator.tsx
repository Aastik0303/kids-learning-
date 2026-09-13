import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { GuestHomeScreen } from "@/screens/guest/GuestHomeScreen";
import type { GuestStackParamList } from "@/navigation/routes";

const Stack = createNativeStackNavigator<GuestStackParamList>();

/**
 * The public surface: one home that says what the app is, and then sign-in.
 *
 * There used to be a second screen here - a scripted preview of how the AI
 * teaches, played entirely on the device with no backend and no account. It is
 * gone. What it showed was written to look like a lesson rather than produced
 * by the one the child would actually get, and a page that demonstrates a
 * teacher that is not the teacher is a promise the product then has to keep.
 * The real class is one sign-up away.
 */
export function GuestNavigator() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false, animation: "slide_from_right" }}>
      <Stack.Screen name="GuestHome" component={GuestHomeScreen} />
    </Stack.Navigator>
  );
}
