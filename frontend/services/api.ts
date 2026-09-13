import { clearSession, forgetChild } from "@/services/session";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8008";

type ApiError = {
  error?: {
    code: string;
    message: string;
  };
};

/** Thrown when the server could not be reached at all, as opposed to replying with an error. */
export class ApiUnreachableError extends Error {
  constructor() {
    super(`We could not reach the learning server at ${API_BASE}. Please check that it is running.`);
    this.name = "ApiUnreachableError";
  }
}

/** Thrown when the server replied with an error of its own. Keeps the code it named. */
export class ApiRequestError extends Error {
  readonly code?: string;

  constructor(message: string, code?: string) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
  }
}

/**
 * Codes that mean "what this browser remembers no longer exists on the server".
 *
 * The session outlives the tab now - it is kept in `localStorage` and the token
 * is good for thirty days - so a browser can quite legitimately come back
 * holding a token or a child id that the server has since dropped: a profile
 * deleted, a database rebuilt, a session signed out from another device.
 * Without this, each screen dead-ends on "We could not find that child profile"
 * with no way out but clearing storage by hand.
 */
const STALE_SESSION_CODES: Record<string, string> = {
  // The parent is still signed in; only the child is gone. `/child/select`
  // reloads it, or sends them to set one up.
  INVALID_CHILD: "/child/select",
  // The token itself is dead, so there is nothing left to rebuild from.
  MISSING_SESSION: "/login"
};

function recoverFromStaleSession(code: string) {
  const destination = STALE_SESSION_CODES[code];
  if (!destination || typeof window === "undefined") return;

  if (code === "INVALID_CHILD") forgetChild();
  else clearSession();

  if (window.location.pathname !== destination) window.location.assign(destination);
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const controller = options.signal ? null : new AbortController();
  const timeout = controller
    ? globalThis.setTimeout(
        () => controller.abort(),
        // Sign-in waits on an SMTP handshake, which is seconds rather than
        // milliseconds, and aborting it at 4.5s would leave the parent looking
        // at a failure while the code was already on its way to them.
        path.startsWith("/agent/") ? 8000 : path.startsWith("/auth/") ? 15000 : 4500
      )
    : null;

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: options.signal ?? controller?.signal,
      headers: {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        ...(options.headers ?? {})
      }
    });
  } catch {
    // fetch rejects with a bare "Failed to fetch" for a down server, a refused
    // connection, a CORS rejection and an abort alike. None of those mean
    // anything to a parent, so say the one useful thing instead.
    throw new ApiUnreachableError();
  } finally {
    if (timeout) globalThis.clearTimeout(timeout);
  }

  const data = (await response.json().catch(() => ({}))) as T & ApiError;
  if (!response.ok) {
    const code = data.error?.code;
    if (code) recoverFromStaleSession(code);
    throw new ApiRequestError(data.error?.message ?? "Something went wrong. Let us try again.", code);
  }
  return data;
}
