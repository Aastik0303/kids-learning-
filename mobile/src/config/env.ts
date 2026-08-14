import Constants from "expo-constants";
import { Platform } from "react-native";

/**
 * Resolving the API base URL is genuinely awkward on mobile: "localhost"
 * on a physical device or Android emulator does not mean the dev machine.
 *
 *   - Android emulator reaches the host at 10.0.2.2
 *   - iOS simulator shares the host loopback, so localhost is fine
 *   - A physical device needs the dev machine's LAN IP, which Expo already
 *     knows and exposes through the packager host
 */
function inferDevHost(): string | null {
  const hostUri =
    Constants.expoConfig?.hostUri ??
    // Older/alternate manifest shapes still carry it here.
    (Constants.expoGoConfig as { debuggerHost?: string } | undefined)?.debuggerHost;

  if (!hostUri) return null;
  const host = hostUri.split(":")[0];
  return host ?? null;
}

const DEFAULT_PORT = 8008;

function resolveApiBaseUrl(): string {
  const configured = (Constants.expoConfig?.extra as { apiBaseUrl?: string } | undefined)?.apiBaseUrl;
  const fromEnv = process.env.EXPO_PUBLIC_API_BASE_URL;

  // An explicitly configured non-localhost URL always wins (staging, prod).
  const explicit = fromEnv ?? configured;
  if (explicit && !explicit.includes("localhost")) return explicit;

  if (__DEV__) {
    const host = inferDevHost();
    if (host && host !== "localhost" && host !== "127.0.0.1") {
      return `http://${host}:${DEFAULT_PORT}`;
    }
    if (Platform.OS === "android") {
      // Android emulator loopback alias for the host machine.
      return `http://10.0.2.2:${DEFAULT_PORT}`;
    }
  }

  return explicit ?? `http://localhost:${DEFAULT_PORT}`;
}

export const env = {
  apiBaseUrl: resolveApiBaseUrl(),
  isDev: __DEV__,
  appVersion: Constants.expoConfig?.version ?? "0.0.0",
  /** Guide calls hit an LLM and need a longer budget than plain CRUD. */
  requestTimeoutMs: 6000,
  guideTimeoutMs: 12000,
} as const;
