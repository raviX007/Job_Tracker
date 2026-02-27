# 05 - Error Handling Strategy: The 5-Layer Defense

## What Is This?

Error handling in a frontend application is not a single mechanism -- it's a layered system where
each layer catches a different category of failure. Our app has **5 distinct layers**, each handling
errors that the previous layer cannot catch. This document walks through every layer, from the
lowest-level network errors up to the final error boundary that catches rendering failures.

The goal: **the user should never see a white screen.** Every failure state should show a clear
message and, wherever possible, a Retry button to recover without a full page reload.

---

## Why We Chose This Approach

### Alternatives we considered

| Approach | Problem |
|---|---|
| **Global try-catch** -- wrap everything in one big error handler | Can't distinguish between network errors, API errors, and render errors. The error message would always be generic. |
| **Toast notifications** for all errors | Toasts auto-dismiss after a few seconds, so the user might miss the error. Toasts are also not accessible to screen readers by default. Inline errors persist until the problem is fixed. |
| **Let React Query handle everything** | React Query handles data-fetching errors well, but it can't catch render errors (e.g., `undefined.map()` when the API returns an unexpected shape). |
| **5-layer approach** (what we chose) | Each layer handles a specific failure mode with an appropriate message and recovery action. |

### Why we don't use toast notifications

Many apps show errors as toast notifications (small popups that slide in and auto-dismiss). We
intentionally avoid this for error states because:

1. **Toasts auto-dismiss.** If the user is not looking at the screen, they miss the error entirely.
   An inline error card stays visible until the user takes action.
2. **Toasts are not accessible by default.** They require `role="alert"` and proper ARIA attributes
   to be announced by screen readers. Inline content is naturally in the document flow.
3. **Toasts stack.** If three requests fail simultaneously, three toasts overlap. An inline error
   shows one clear message.
4. **Toasts don't have context.** A toast says "Request failed" but the user doesn't know which
   part of the page it relates to. An inline error card appears exactly where the data should be.

---

## How It Works In Our App

### Layer 1: Network Errors (TypeError in api.ts)

**What it catches:** The server is completely unreachable -- it's down, there's no network, or
DNS resolution failed.

When `fetch()` cannot establish a connection at all, it throws a `TypeError` (not a `DOMException`,
not an HTTP error -- a raw `TypeError`). This is the most fundamental failure: the request never
even left the browser.

```typescript
// From src/lib/api.ts — catch block in request()
catch (err) {
  if (err instanceof DOMException && err.name === "AbortError") {
    if (options?.signal?.aborted) throw err;
    throw new Error("Request timed out");
  }
  if (err instanceof TypeError) {
    throw new Error("Cannot reach the API server — is the backend running?");
  }
  throw err;
}
```

**Why `TypeError`?** The Fetch specification defines that network-level failures (DNS failure,
connection refused, CORS preflight failure) throw `TypeError`. This is different from HTTP errors
(which return a `Response` object with `ok: false`).

**The message:** `"Cannot reach the API server -- is the backend running?"` is intentionally
conversational. During development, the most common cause is forgetting to start the FastAPI
backend. In production, it would indicate a server outage.

---

### Layer 2: Timeout Errors (AbortController in api.ts)

**What it catches:** The server accepted the connection but is taking too long to respond.

```typescript
// From src/lib/api.ts — timeout setup
const REQUEST_TIMEOUT_MS = 60_000;

const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
```

After 60 seconds, the `setTimeout` fires, calls `controller.abort()`, and `fetch()` throws an
`AbortError`. Our catch block distinguishes this from external cancellation:

```typescript
if (err instanceof DOMException && err.name === "AbortError") {
  if (options?.signal?.aborted) throw err; // External — silent
  throw new Error("Request timed out");    // Timeout — show to user
}
```

**Why 60 seconds?** Some of our analytics endpoints aggregate data across thousands of rows. On
a cold start (no database connection pool yet), these queries can take 10-15 seconds. The 60-second
timeout is generous enough to avoid false positives while still catching genuinely stuck requests.

**Why not use AbortSignal.timeout()?** `AbortSignal.timeout(ms)` is a cleaner API, but it
doesn't let us distinguish timeout from external cancellation. With `setTimeout`, we control
exactly when and why the abort happens.

---

### Layer 3: HTTP Errors (response.ok check in api.ts)

**What it catches:** The server responded, but with an error status code (400, 401, 404, 500, etc.).

```typescript
// From src/lib/api.ts — response handling in request()
if (!response.ok) {
  const error = await response.json().catch(() => ({ detail: "Unknown error" }));
  throw new Error(error.detail || `API error: ${response.status}`);
}
```

This layer does three important things:

1. **Checks `response.ok`** -- This is `true` for status codes 200-299, `false` for everything
   else. Using `response.ok` instead of checking specific status codes means we catch ALL error
   responses.

2. **Parses the JSON error body** -- Our FastAPI backend returns errors in the format
   `{ "detail": "Human-readable message" }`. We try to parse this body to get a meaningful message.

3. **Falls back gracefully** -- If the error body is not valid JSON (e.g., the server returned an
   HTML error page, or a plain text "Internal Server Error"), the `.catch(() => ({ detail: "Unknown error" }))`
   ensures we always have something to display. The fallback message includes the HTTP status code:
   `"API error: 500"`.

**Why parse the error body?** Because our backend sends specific messages like
`"Profile not found"`, `"Invalid email ID"`, `"Rate limit exceeded"`. These are much more useful
than a generic `"HTTP 400"`.

---

### Layer 4: Page-Level Error States (React Query's error property)

**What it catches:** Any error from Layers 1-3 that propagated up through React Query.

When a `queryFn` throws an error, React Query catches it and stores it in the `error` property
of the query result. Every page in our app renders this error with a consistent pattern:

```typescript
// From src/app/overview/page.tsx
const { data: queryData, isLoading: loading, error: queryError, refetch } = useQuery({
  queryKey: queryKeys.overview(profileId),
  queryFn: async ({ signal }) => { /* ... */ },
});

const error = queryError?.message ?? null;

return (
  <div>
    <PageHeader title="Overview" subtitle="Real-time dashboard" />

    {/* Error state */}
    {error && (
      <Card className="mb-6 border-red-200 bg-red-50">
        <CardContent className="flex items-center justify-between py-4">
          <p className="text-sm text-red-700">{error}</p>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            Retry
          </Button>
        </CardContent>
      </Card>
    )}

    {/* Loading state */}
    {loading && <OverviewSkeleton />}

    {/* Loaded content */}
    {!loading && data && (
      <div className="space-y-8">
        {/* ... actual content ... */}
      </div>
    )}
  </div>
);
```

This pattern is **consistent across all 7 pages**: overview, applications, emails, outcomes,
analytics, tracker, and startups. The error card always has:
- Red border and background (`border-red-200 bg-red-50`)
- Red text with the error message
- A "Retry" button that calls `refetch()`

**Why a Retry button?** It gives the user **agency**. Instead of telling them "something went
wrong, refresh the page," we let them retry the specific operation that failed. `refetch()` re-runs
the exact same query with the same parameters. If the failure was transient (a brief network blip,
a temporary server overload), retrying often succeeds immediately.

### How the emails page handles mutation errors

The emails page is more complex because it has both **query** errors (fetching the email list)
and **mutation** errors (saving, sending, or deleting an email). It combines them into a single
error display:

```typescript
// From src/app/emails/page.tsx
const mutationError = saveMutation.error?.message
  || sendMutation.error?.message
  || deleteMutation.error?.message
  || deleteAllMutation.error?.message;
const error = emailsError?.message ?? mutationError ?? null;
```

This uses short-circuit evaluation (`||`) to find the first non-null error message from any of
the four mutations, then falls back to the query error. The result is displayed in the same
red Card component:

```typescript
{error && (
  <Card className="mb-4 border-red-200 bg-red-50">
    <CardContent className="flex items-center justify-between py-4">
      <p className="text-sm text-red-700">{error}</p>
      <Button variant="outline" size="sm" onClick={() => refetchEmails()}>
        Retry
      </Button>
    </CardContent>
  </Card>
)}
```

**Why combine query + mutation errors?** Because the user doesn't care whether the failure was
in fetching data or saving data -- they just want to know that something went wrong and how to fix
it. One error card is simpler than two.

---

### Layer 5: Error Boundary (app/error.tsx)

**What it catches:** Unhandled errors during **rendering** that none of the above layers caught.

Layers 1-4 handle data-fetching errors. But what about errors that happen during rendering? For
example:
- The API returned `null` where the component expects an array, and `null.map()` throws
- A component accesses `data.stats.total` but `stats` is `undefined`
- A third-party charting library throws an internal error

These errors crash the component tree. Without an error boundary, the entire app goes white.

```typescript
// From src/app/error.tsx
"use client";

import { useEffect } from "react";
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
```

#### Why error.tsx is a Next.js convention

In the Next.js App Router, `error.tsx` is a **special file** that acts as a React Error Boundary
for its route segment. You don't need to manually create an `ErrorBoundary` class component --
Next.js automatically wraps the route segment with one when it detects an `error.tsx` file.

This means:
- `app/error.tsx` catches errors in ALL pages (it's at the root)
- `app/applications/error.tsx` would catch errors only in the `/applications` route (we don't
  need this granularity, so we only have the root one)

#### Why `reset()` works

The `reset` function is provided by Next.js. It re-renders the route segment **without a full
page reload**. Under the hood, it calls `React.startTransition()` to retry rendering the
component tree. If the error was caused by a transient issue (e.g., a component that crashed on
first render due to stale cache data), the retry might succeed.

If the error is persistent (a genuine bug), clicking "Try again" will crash again and show the
same error boundary. But at least the user has an option to try before resorting to a full page
refresh.

#### Why error details are dev-only

```typescript
{process.env.NODE_ENV === "development" && (
  <pre className="mb-4 max-h-40 overflow-auto rounded-md bg-red-100 p-3 text-left text-xs text-red-800">
    {error.message}
  </pre>
)}
```

In development, seeing the actual error message (`"Cannot read properties of undefined (reading 'map')"`)
is invaluable for debugging. In production, showing stack traces or error messages:
- **Exposes implementation details** -- an attacker could learn about your API structure, database
  schema, or library versions
- **Confuses users** -- technical messages like "TypeError: x is not a function" mean nothing to
  a non-developer
- **Looks unprofessional** -- a clean "Something went wrong" is better UX than a raw stack trace

#### The `digest` property

```typescript
error: Error & { digest?: string };
```

The `digest` is a **hash** that Next.js generates for server-side errors. It's a fingerprint that
you can use to look up the full error details in your server logs, without exposing the actual
error message to the client. If you're using an error tracking service (like Sentry), you would
log this digest alongside the full error.

---

## The 4 UI States Pattern

Every page in our app renders exactly 4 mutually exclusive states. This is a deliberate pattern
that ensures we never show a blank screen:

```
loading  -> Show skeleton
error    -> Show red error card with Retry button
empty    -> Show "No data" message with helpful suggestion
loaded   -> Show the actual content
```

Here's how it looks in practice across different pages:

```typescript
// Applications page (src/app/applications/page.tsx)

{/* Loading */}
{loading && (
  <div className="mt-4">
    <ApplicationsSkeleton />
  </div>
)}

{/* Empty */}
{!loading && !error && applications.length === 0 && (
  <Card>
    <CardContent className="py-12 text-center">
      <p className="text-muted-foreground">No applications found.</p>
      <p className="mt-1 text-xs text-muted-foreground">
        Try adjusting your filters or wait for the pipeline to analyze new jobs.
      </p>
    </CardContent>
  </Card>
)}

{/* Loaded */}
{!loading && !error && applications.length > 0 && (
  <>
    {/* ... cards/table content ... */}
  </>
)}
```

```typescript
// Tracker page (src/app/tracker/page.tsx)

{/* Loading state */}
{loading && <TrackerSkeleton />}

{/* Empty state */}
{!loading && !error && filteredRows.length === 0 && (
  <Card>
    <CardContent className="py-12 text-center">
      <p className="text-sm text-muted-foreground">
        No actionable jobs found
      </p>
    </CardContent>
  </Card>
)}

{/* Data table */}
{!loading && rows.length > 0 && (
  <Card>
    {/* ... table content ... */}
  </Card>
)}
```

The order matters:
1. **Error first** -- displayed above everything else so the user sees it immediately
2. **Loading** -- shown while data is being fetched
3. **Empty** -- shown when the fetch succeeded but returned zero results
4. **Loaded** -- the happy path with actual content

The `!loading && !error && data.length === 0` guard on the empty state is critical. Without the
`!loading` check, the empty state would flash briefly before data loads. Without the `!error`
check, both the error card and the empty state would show simultaneously if the request failed.

---

## The Key Insight

Error handling is not one thing -- it's a layered defense where each layer catches what the
previous layer can't. The layers build on each other:

```
Layer 5: error.tsx       -> catches render crashes (undefined.map())
Layer 4: Page error Card -> catches data-fetching errors from React Query
Layer 3: response.ok     -> catches HTTP errors (400, 500)
Layer 2: setTimeout      -> catches timeouts (server too slow)
Layer 1: TypeError check -> catches network failures (server unreachable)
```

Each layer provides a more specific error message than the one above it. A network error says
"Cannot reach the API server." An HTTP error says the specific detail from the backend. A timeout
says "Request timed out." This specificity helps the user (and the developer) understand exactly
what went wrong.

The Retry pattern at Layer 4 is particularly powerful because most transient errors (network
blips, server restarts) resolve within seconds. Giving the user a Retry button means they can
recover without refreshing the page, losing their filter state, or re-entering form data.

---

## Interview Talking Points

- "We have 5 layers of error handling: network errors (TypeError from fetch), timeouts
  (AbortController after 60 seconds), HTTP errors (response.ok check with JSON error body
  parsing), page-level error states (React Query's error property rendered as an inline card
  with a Retry button), and the error boundary (Next.js error.tsx for render crashes)."

- "We chose inline error cards over toast notifications because toasts auto-dismiss, aren't
  accessible by default, and don't provide context about which part of the page failed. Our
  inline cards persist until the user clicks Retry or the error resolves."

- "The error.tsx file is a Next.js App Router convention. It automatically wraps the route
  segment in a React Error Boundary. The reset() function it receives re-renders the segment
  without a full page reload."

- "Error details are shown only in development mode using process.env.NODE_ENV. In production,
  we show a generic 'Something went wrong' message to avoid exposing implementation details."

- "The emails page combines query errors and mutation errors into a single display using
  short-circuit evaluation. The user sees one error card regardless of whether the failure was
  in fetching or in saving."

- "Every page follows the same 4-state pattern: loading, error, empty, loaded. The guards on
  each state (!loading && !error && data.length === 0) ensure exactly one state is shown at
  any time."

- "The digest property on the error object is a Next.js feature -- it's a hash that lets you
  correlate client-side errors with server-side logs without exposing the actual error message
  to the user."

- "We parse the backend's JSON error body to extract error.detail, which gives us specific
  messages like 'Profile not found' instead of generic 'HTTP 400'. The .catch fallback ensures
  we handle cases where the error body isn't valid JSON."
