import type { NavigatorScreenParams } from "@react-navigation/native";

import type { ToddlerModule } from "@/types/domain";

/**
 * Every route in the app, typed. The AI may only navigate to the subset
 * listed in `SAFE_ROUTES` below — see `ai/GuideActionExecutor.ts`.
 */

export type GuestStackParamList = {
  GuestHome: undefined;
};

export type AuthStackParamList = {
  Login: undefined;
  /**
   * The emailed sign-in code. Reached only when `/auth/login` answered with a
   * challenge rather than a session; the challenge itself lives in `authStore`
   * rather than in the route params, because it is a credential in flight and
   * navigation params are held in state that gets serialised and logged.
   */
  VerifyCode: undefined;
  SignUp: undefined;
  ChildSelect: undefined;
  ChildSetup: { childId?: string } | undefined;
};

export type ChildStackParamList = {
  ChildTabs: NavigatorScreenParams<ChildTabParamList> | undefined;
  /**
   * One subject's levels, and one level's own page.
   *
   * Both are **status and play**, never a way into a lesson: the class is the
   * AI Teacher and today's frozen plan decides what it teaches, so a level that
   * could be started from here would open one the schedule had not reached.
   */
  AdventureSubject: { subjectId: string; title?: string };
  AdventureLevel: { subjectId: string; topicId: string };
  /**
   * The older conducted class. Still the server-side loop it always was, and
   * still reachable, but it is no longer the child's way in: the class is the
   * `Class` tab - the AI Teacher - which is the same loop the web runs, off the
   * same frozen plan. Nothing a child taps opens this.
   */
  ConductedClass: undefined;
  /** The older picked-lesson surfaces. Off the tab bar; see `ChildTabs`. */
  ChildHome: undefined;
  Classes: undefined;
  Practice: undefined;
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
    /**
     * Set when the sitting was a conducted class rather than a picked lesson.
     * A class has no "next level" to offer: what is played next is the frozen
     * daily plan's decision, and a level unlocked today is played tomorrow.
     */
    fromClass?: boolean;
    /** Why the class ended, when it was one. */
    closeReason?: string;
  };
  Certificate: undefined;
};

/**
 * What a child sees at the bottom of the screen, and it is deliberately three
 * things rather than five.
 *
 * **Class** is the AI Teacher and it is where the app opens - the sitting is
 * already happening, with no topic to pick and no level to choose.
 * **Adventure** is a progress board: what is finished, what today's plan holds,
 * what is sleeping until its turn, what is still locked, and a game about any
 * level the child has already been given. **Rewards** is the shelf.
 *
 * The older picked-lesson surfaces - a home hub, a list of classes, practice -
 * are off the bar. Not because they stopped working, but because each was a
 * second way into a lesson, and a second way in can open a level the schedule
 * has not reached. They are still in the stack above for a grown-up's route in.
 */
export type ChildTabParamList = {
  Class: undefined;
  Adventure: undefined;
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
  // The ids are the server's and are unchanged; where each one *lands* moved
  // when the class became the app's front door. "child_home" is the class,
  // because that is what a child now opens the app onto, and "classes" is the
  // Adventure board, which is where the levels are.
  child_home: { stack: "Child", screen: "ChildTabs", params: { screen: "Class" } },
  classes: { stack: "Child", screen: "ChildTabs", params: { screen: "Adventure" } },
  practice: { stack: "Child", screen: "ChildTabs", params: { screen: "Rewards" } },
  rewards: { stack: "Child", screen: "ChildTabs", params: { screen: "Rewards" } },
} as const;

export type SafeRouteId = keyof typeof SAFE_ROUTES;

export function isSafeRoute(value: string | null | undefined): value is SafeRouteId {
  return !!value && Object.prototype.hasOwnProperty.call(SAFE_ROUTES, value);
}
