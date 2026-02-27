"use client";

import { useEffect } from "react";
import * as Sentry from "@sentry/nextjs";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Global error:", error);
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", textAlign: "center" }}>
        <h2>Something went wrong</h2>
        <p>An unexpected error occurred. Please try again.</p>
        <button
          onClick={reset}
          style={{
            marginTop: "1rem",
            padding: "0.5rem 1rem",
            border: "1px solid #ccc",
            borderRadius: "4px",
            cursor: "pointer",
          }}
        >
          Try again
        </button>
      </body>
    </html>
  );
}
