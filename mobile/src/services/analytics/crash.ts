import { env } from "@/config/env";

/**
 * Crash reporting integration point (spec section 20). Same shape as
 * analytics: typed no-op now, real reporter (Sentry, Bugsnag) later.
 */

type CrashReporter = {
  captureException: (error: unknown, context?: Record<string, unknown>) => void;
  addBreadcrumb: (message: string, data?: Record<string, unknown>) => void;
};

let reporter: CrashReporter | null = null;

export function configureCrashReporting(next: CrashReporter): void {
  reporter = next;
}

export function captureException(error: unknown, context?: Record<string, unknown>): void {
  if (reporter) {
    reporter.captureException(error, context);
    return;
  }
  if (env.isDev) {
    console.error("[crash]", error, context ?? {});
  }
}

export function addBreadcrumb(message: string, data?: Record<string, unknown>): void {
  reporter?.addBreadcrumb(message, data);
}
