import * as Sentry from "@sentry/nextjs";

export async function register() {
  const dsn = process.env.SENTRY_DSN;

  if (dsn) {
    Sentry.init({
      dsn,
      environment: process.env.SENTRY_ENVIRONMENT || "development",
      tracesSampleRate: 0,
      sendDefaultPii: false,
    });
  }
}

export const onRequestError = Sentry.captureRequestError;
