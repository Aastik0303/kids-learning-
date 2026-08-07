const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type ApiError = {
  error?: {
    code: string;
    message: string;
  };
};

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const controller = options.signal ? null : new AbortController();
  const timeout = controller
    ? globalThis.setTimeout(() => controller.abort(), path.startsWith("/agent/") ? 2500 : 4500)
    : null;
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    signal: options.signal ?? controller?.signal,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(options.headers ?? {})
    }
  }).finally(() => {
    if (timeout) globalThis.clearTimeout(timeout);
  });
  const data = (await response.json()) as T & ApiError;
  if (!response.ok) {
    throw new Error(data.error?.message ?? "Something went wrong. Let us try again.");
  }
  return data;
}
