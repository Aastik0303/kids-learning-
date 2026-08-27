/**
 * One request per thing, per moment.
 *
 * Four components on the home screen each ask for the child, the class detail
 * and today's plan on mount — `AppShell`, `HomeExperience`, `AutoOpenGate` and
 * `TodayPlanBlock` all legitimately need them — so opening the app fired the
 * same three GETs three and four times over. The server answered all of them
 * correctly and the screen waited for the slowest.
 *
 * This is the smallest thing that fixes it: calls with the same key share the
 * request that is already in flight, and the answer is held for a moment
 * afterwards so a component that mounts a tick later gets it without asking
 * again. It is deliberately not a general cache — there is no revalidation and
 * no background refresh, and anything that changes what a screen shows calls
 * `invalidate` rather than waiting for a timer.
 */

type Entry = { value: Promise<unknown>; expires: number };

const entries = new Map<string, Entry>();

/** How long a shared answer stays warm. Long enough to cover a render pass. */
export const BRIEFLY_MS = 1500;

/** Curriculum is authored content: it cannot change while the tab is open. */
export const STATIC_MS = 5 * 60 * 1000;

export function shared<T>(key: string, run: () => Promise<T>, ttlMs = BRIEFLY_MS): Promise<T> {
  const now = Date.now();
  const hit = entries.get(key);
  if (hit && hit.expires > now) return hit.value as Promise<T>;

  const value = run();
  entries.set(key, { value, expires: now + ttlMs });
  // A failed request must not be remembered: the next screen to ask should get
  // a real attempt, not the same error handed back for the rest of the minute.
  value.catch(() => entries.delete(key));
  return value;
}

/** Drop everything whose key starts with this. Called when the truth moves. */
export function invalidate(prefix: string) {
  Array.from(entries.keys()).forEach((key) => {
    if (key.startsWith(prefix)) entries.delete(key);
  });
}
