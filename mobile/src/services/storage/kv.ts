import AsyncStorage from "@react-native-async-storage/async-storage";

/**
 * Non-secret persistence: selected child, cached curriculum, UI prefs and
 * the resumable lesson pointer.
 *
 * Every read is failure-tolerant on purpose. Storage errors on a child's
 * device should degrade to "no cached value", never to a crash.
 */

const PREFIX = "learnkids.";

export const storageKeys = {
  selectedChildId: `${PREFIX}selected_child_id`,
  cachedChild: `${PREFIX}cached_child`,
  cachedPaths: `${PREFIX}cached_paths`,
  cachedStages: (pathId: string) => `${PREFIX}cached_stages.${pathId}`,
  resumableSession: `${PREFIX}resumable_session`,
  pendingIntent: `${PREFIX}pending_intent`,
  audioPrefs: `${PREFIX}audio_prefs`,
  locale: `${PREFIX}locale`,
  onboardingSeen: `${PREFIX}onboarding_seen`,
} as const;

export const kv = {
  async set(key: string, value: unknown): Promise<void> {
    try {
      await AsyncStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Best-effort cache. A failed write is not worth interrupting play.
    }
  },

  async get<T>(key: string): Promise<T | null> {
    try {
      const raw = await AsyncStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : null;
    } catch {
      return null;
    }
  },

  async remove(key: string): Promise<void> {
    try {
      await AsyncStorage.removeItem(key);
    } catch {
      // Ignore.
    }
  },

  /** Used on sign-out. Leaves device-level prefs (locale, audio) intact. */
  async clearSessionScoped(): Promise<void> {
    await Promise.all([
      kv.remove(storageKeys.selectedChildId),
      kv.remove(storageKeys.cachedChild),
      kv.remove(storageKeys.resumableSession),
      kv.remove(storageKeys.pendingIntent),
    ]);
  },
};
