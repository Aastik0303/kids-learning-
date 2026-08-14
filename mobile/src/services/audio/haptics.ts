import * as Haptics from "expo-haptics";
import { Platform } from "react-native";

/**
 * Haptic vocabulary (spec section 20). Small children respond strongly to
 * touch feedback, so every meaningful outcome has a distinct feel.
 *
 * All calls are fire-and-forget and swallow errors: a device without a
 * taptic engine must not throw into a lesson.
 */

const supported = Platform.OS === "ios" || Platform.OS === "android";

function safely(run: () => Promise<void>): void {
  if (!supported) return;
  run().catch(() => undefined);
}

export const haptics = {
  /** Any tap on an answer option or nav card. */
  tap() {
    safely(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light));
  },

  /** Correct answer. */
  success() {
    safely(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success));
  },

  /**
   * Wrong answer — deliberately the *soft* warning, never the error
   * pattern. Being wrong should not feel like a punishment.
   */
  gentleRetry() {
    safely(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Soft));
  },

  /** Stars, level unlock, certificate. */
  celebrate() {
    safely(async () => {
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      await new Promise((resolve) => setTimeout(resolve, 120));
      await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    });
  },

  /** Microphone opening — tells a pre-reader "speak now". */
  listenStart() {
    safely(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium));
  },

  /** Stroke completed on a tracing canvas. */
  strokeComplete() {
    safely(() => Haptics.selectionAsync());
  },
};
