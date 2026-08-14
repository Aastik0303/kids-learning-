import type { NavigatorScreenParams } from "@react-navigation/native";

import type { ToddlerModule } from "@/types/domain";

/**
 * Every route in the app, typed. The AI may only navigate to the subset
 * listed in `SAFE_ROUTES` below — see `ai/GuideActionExecutor.ts`.
 */

export type GuestStackParamList = {
  GuestHome: undefined;
  FeatureDemo: { featureId: string };
};

export type AuthStackParamList = {
  Login: undefined;
  SignUp: undefined;
  ChildSelect: undefined;
  ChildSetup: { childId?: string } | undefined;
};

export type ChildStackParamList = {
  ChildTabs: NavigatorScreenParams<ChildTabParamList> | undefined;
  Lesson: {
    pathId: string;
    stageNumber: number;
    /** Toddler lessons run against /toddler instead of /learning. */
    module?: ToddlerModule;
    mode?: "standard" | "toddler";
  };
  ClassDetail: { pathId: string };
  PracticeTopic: { topic: string; title: string };
  Story: { storyId: string };
  SessionRecap: {
    pathId: string;
    stageNumber: number;
    starsEarned: number;
    correctCount: number;
    totalCount: number;
  };
  Certificate: undefined;
};

export type ChildTabParamList = {
  ChildHome: undefined;
  Classes: undefined;
  Practice: undefined;
  Rewards: undefined;
};

export type ParentStackParamList = {
  ParentGate: { redirectTo?: keyof ParentStackParamList } | undefined;
  ParentDashboard: undefined;
  ParentProgress: undefined;
  ParentSettings: undefined;
};

export type RootStackParamList = {
  Guest: NavigatorScreenParams<GuestStackParamList> | undefined;
  Auth: NavigatorScreenParams<AuthStackParamList> | undefined;
  Child: NavigatorScreenParams<ChildStackParamList> | undefined;
  Parent: NavigatorScreenParams<ParentStackParamList> | undefined;
};

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}

/**
 * Routes the guide agent is permitted to open via `open_safe_route`.
 *
 * Deliberately narrow: navigation targets that are safe for a 2-year-old
 * to be moved to unprompted. Auth, parent and any destructive surface are
 * absent by design and cannot be reached by an LLM response.
 */
export const SAFE_ROUTES = {
  child_home: { stack: "Child", screen: "ChildTabs", params: { screen: "ChildHome" } },
  classes: { stack: "Child", screen: "ChildTabs", params: { screen: "Classes" } },
  practice: { stack: "Child", screen: "ChildTabs", params: { screen: "Practice" } },
  rewards: { stack: "Child", screen: "ChildTabs", params: { screen: "Rewards" } },
} as const;

export type SafeRouteId = keyof typeof SAFE_ROUTES;

export function isSafeRoute(value: string | null | undefined): value is SafeRouteId {
  return !!value && Object.prototype.hasOwnProperty.call(SAFE_ROUTES, value);
}
