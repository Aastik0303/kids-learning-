import { useEffect, useRef, useState } from "react";
import { AppState, type AppStateStatus } from "react-native";
import NetInfo from "@react-native-community/netinfo";

import { checkHealth } from "@/services/api/client";
import { setAnalyticsContext, track } from "@/services/analytics/analytics";
import { voiceController } from "@/features/voice/VoiceController";
import { useAudioStore } from "@/store/audioStore";
import { useAuthStore } from "@/store/authStore";
import { useChildStore } from "@/store/childStore";
import { useUiStore } from "@/store/uiStore";

/**
 * Cold-start sequence and app lifecycle wiring (spec section 20).
 *
 * Runs once, before the navigator mounts:
 *   1. restore the session token and validate it
 *   2. restore the cached child so an offline start still shows something
 *   3. restore audio preferences
 *   4. probe connectivity
 *
 * Then keeps three lifecycle guarantees for as long as the app is alive:
 *   - going to background stops all audio (a phone must not keep talking
 *     from a pocket) and re-arms the parent gate
 *   - connectivity changes update the offline banner
 *   - returning to foreground re-probes the backend
 */
export function useAppBootstrap() {
  const [isReady, setIsReady] = useState(false);
  const appState = useRef<AppStateStatus>(AppState.currentState);

  // ── Cold start ────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    (async () => {
      const restore = useAuthStore.getState().restore();
      const cachedChild = useChildStore.getState().restoreCached();
      const prefs = useAudioStore.getState().loadPrefs();

      // Auth restore may hit the network; the other two are local.
      await Promise.allSettled([restore, cachedChild, prefs]);
      if (cancelled) return;

      const reachable = await checkHealth();
      if (cancelled) return;

      useUiStore.getState().setBackendReachable(reachable);
      track("app_opened", { cold_start: true });
      setIsReady(true);
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  // ── Analytics context follows the active child ───────────────────────
  useEffect(() => {
    return useChildStore.subscribe((state) => {
      setAnalyticsContext({
        child_id: state.activeChild?.child_id ?? null,
        age_group: state.activeChild?.age_group ?? null,
      });
    });
  }, []);

  // ── Connectivity ─────────────────────────────────────────────────────
  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      const online = state.isConnected !== false;
      useUiStore.getState().setOnline(online);
      // A device with no network cannot reach the backend either.
      if (!online) useUiStore.getState().setBackendReachable(false);
    });
    return unsubscribe;
  }, []);

  // ── Foreground / background ──────────────────────────────────────────
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (next) => {
      const previous = appState.current;
      appState.current = next;

      if (next.match(/inactive|background/)) {
        // Never keep speaking or listening from a pocketed phone.
        void voiceController.stopAll();
        // Re-arm the parent gate so an unattended device is not open.
        useUiStore.getState().lockParent();
        return;
      }

      if (previous.match(/inactive|background/) && next === "active") {
        void checkHealth().then((reachable) => {
          useUiStore.getState().setBackendReachable(reachable);
        });
        // Pull fresh progress in case a sibling device changed it.
        void useChildStore.getState().refresh();
      }
    });

    return () => subscription.remove();
  }, []);

  return { isReady };
}
