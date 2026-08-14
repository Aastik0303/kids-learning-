import { createNavigationContainerRef } from "@react-navigation/native";

import type { RootStackParamList } from "@/navigation/routes";

/**
 * Imperative navigation handle, used by the guide action executor and the
 * auth intent replay. Screens should still use `useNavigation()`.
 */
export const navigationRef = createNavigationContainerRef<RootStackParamList>();

export function currentRouteName(): string {
  if (!navigationRef.isReady()) return "unknown";
  return navigationRef.getCurrentRoute()?.name ?? "unknown";
}
