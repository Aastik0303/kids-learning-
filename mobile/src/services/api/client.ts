import { env } from "@/config/env";
import type { ApiErrorBody } from "@/types/domain";

/**
 * The single HTTP boundary for the app. Nothing outside `services/api`
 * may call `fetch` directly (spec section 18).
 */

export type ApiErrorKind =
  | "offline"
  | "timeout"
  | "server"
  | "not_found"
  | "unauthorized"
  | "validation"
  | "unknown";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number;
  readonly code: string;
  /** Copy safe to read aloud to a child. Never contains technical detail. */
  readonly childMessage: string;

  constructor(params: {
    kind: ApiErrorKind;
    status: number;
    code: string;
    message: string;
    childMessage?: string;
  }) {
    super(params.message);
    this.name = "ApiError";
    this.kind = params.kind;
    this.status = params.status;
    this.code = params.code;
    this.childMessage = params.childMessage ?? childCopyFor(params.kind);
  }

  /** Retrying a timeout or a 5xx can help; a 404 or 401 never will. */
  get isRetryable(): boolean {
    return this.kind === "offline" || this.kind === "timeout" || this.kind === "server";
  }
}

function childCopyFor(kind: ApiErrorKind): string {
  switch (kind) {
    case "offline":
      return "I cannot hear the internet right now. Let us try again!";
    case "timeout":
      return "That took a long time. Let us try again!";
    case "server":
    case "unknown":
      return "Something went wrong. Let us try again!";
    case "not_found":
      return "I could not find that. Let us go back home.";
    case "unauthorized":
      return "Please ask a grown-up to help you sign in.";
    case "validation":
      return "Let us check that and try again.";
  }
}

function kindForStatus(status: number): ApiErrorKind {
  if (status === 401 || status === 403) return "unauthorized";
  if (status === 404) return "not_found";
  if (status === 422 || status === 400) return "validation";
  if (status >= 500) return "server";
  return "unknown";
}

export type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  /** The parent's session token, sent as `Authorization: Bearer`. */
  sessionToken?: string | null;
  timeoutMs?: number;
  /** Attempts beyond the first. Only applied to retryable failures. */
  retries?: number;
  signal?: AbortSignal;
};

const RETRY_BASE_DELAY_MS = 400;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function performRequest<T>(path: string, options: RequestOptions): Promise<T> {
  const {
    method = "GET",
    body,
    sessionToken,
    timeoutMs = env.requestTimeoutMs,
    signal,
  } = options;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  // Honour an externally supplied signal alongside our timeout.
  const onExternalAbort = () => controller.abort();
  signal?.addEventListener("abort", onExternalAbort);

  let response: Response;
  try {
    response = await fetch(`${env.apiBaseUrl}${path}`, {
      method,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        // The standard bearer shape. It was a bespoke `X-Demo-Session` header
        // from the prototype; the server accepts both, so a build already on
        // somebody's phone goes on working.
        ...(sessionToken ? { Authorization: `Bearer ${sessionToken}` } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch (cause) {
    const aborted = controller.signal.aborted;
    throw new ApiError({
      kind: aborted ? "timeout" : "offline",
      status: 0,
      code: aborted ? "TIMEOUT" : "NETWORK",
      message: aborted ? `Request to ${path} timed out` : `Network request to ${path} failed`,
    });
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", onExternalAbort);
  }

  // 204 and other empty bodies would blow up .json().
  const raw = await response.text();
  const data = (raw ? safeParse(raw) : {}) as T & ApiErrorBody;

  if (!response.ok) {
    throw new ApiError({
      kind: kindForStatus(response.status),
      status: response.status,
      code: data.error?.code ?? "ERROR",
      message: data.error?.message ?? `Request to ${path} failed (${response.status})`,
    });
  }

  return data;
}

function safeParse(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

/**
 * Issue a request, retrying transient failures with exponential backoff.
 * A learning session must survive a flaky connection without the child
 * ever seeing a stack trace (spec section 20).
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  // Only a read is retried unless the caller says otherwise. A timed-out POST
  // has usually *happened* on the server - an answer marked, a sign-in code
  // sent - and sending it again marks that answer against the next question,
  // or opens a new sign-in challenge that kills the code just emailed.
  const method = options.method ?? "GET";
  const attempts = (options.retries ?? (method === "GET" ? 2 : 0)) + 1;
  let lastError: ApiError | null = null;

  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return await performRequest<T>(path, options);
    } catch (error) {
      if (!(error instanceof ApiError) || !error.isRetryable) throw error;
      lastError = error;
      if (attempt < attempts - 1) {
        await delay(RETRY_BASE_DELAY_MS * 2 ** attempt);
      }
    }
  }

  throw (
    lastError ??
    new ApiError({ kind: "unknown", status: 0, code: "UNKNOWN", message: "Request failed" })
  );
}

export const apiClient = {
  get: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "POST", body }),
  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "PATCH", body }),
};

/** Health probe used by the offline banner and bootstrap. */
export async function checkHealth(): Promise<boolean> {
  try {
    await request<{ ok: boolean }>("/health", { timeoutMs: 3000, retries: 0 });
    return true;
  } catch {
    return false;
  }
}
