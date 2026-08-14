import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

/**
 * Credential-grade storage. The session token lives here rather than in
 * AsyncStorage so it sits in the Keychain / Android Keystore.
 *
 * Note: these are prototype demo tokens today, but treating them as secrets
 * now means the production auth swap does not have to move storage too.
 */

const SESSION_TOKEN_KEY = "learnkids.session_token";

/** SecureStore is unavailable on web; fall back so Expo web still runs. */
const isSupported = Platform.OS !== "web";

const webFallback = new Map<string, string>();

async function setItem(key: string, value: string): Promise<void> {
  if (!isSupported) {
    webFallback.set(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

async function getItem(key: string): Promise<string | null> {
  if (!isSupported) return webFallback.get(key) ?? null;
  try {
    return await SecureStore.getItemAsync(key);
  } catch {
    // A corrupted keychain entry must not brick app start.
    return null;
  }
}

async function removeItem(key: string): Promise<void> {
  if (!isSupported) {
    webFallback.delete(key);
    return;
  }
  try {
    await SecureStore.deleteItemAsync(key);
  } catch {
    // Deleting a missing key is not an error worth surfacing.
  }
}

export const secureStore = {
  saveSessionToken: (token: string) => setItem(SESSION_TOKEN_KEY, token),
  getSessionToken: () => getItem(SESSION_TOKEN_KEY),
  clearSessionToken: () => removeItem(SESSION_TOKEN_KEY),
};
