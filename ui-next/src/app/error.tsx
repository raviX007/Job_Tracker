"use client";

import { useEffect } from "react";
import * as Sentry from "@sentry/nextjs";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled error:", error);
    Sentry.captureException(error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] items-center justify-center p-8">
      <Card className="max-w-md border-red-200 bg-red-50">
        <CardContent className="pt-6 text-center">
          <h2 className="mb-2 text-lg font-semibold text-red-800">
            Something went wrong
          </h2>
          <p className="mb-4 text-sm text-red-700">
            An unexpected error occurred while rendering this page.
          </p>

          {process.env.NODE_ENV === "development" && (
            <pre className="mb-4 max-h-40 overflow-auto rounded-md bg-red-100 p-3 text-left text-xs text-red-800">
              {error.message}
            </pre>
          )}

          <Button variant="outline" onClick={reset}>
            Try again
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
