# 04 - AbortSignal & Request Cancellation Deep Dive

## What Is This?

AbortSignal is a browser-native API for **cooperative cancellation** of asynchronous operations. In our
app, it solves a very real problem: when a user interacts with the UI faster than the network can
respond, we need a way to tell the browser "never mind, stop that request."

This document explains the full signal chain from React Query down to `fetch()`, how our `api.ts`
module links external and internal abort controllers, and why each design decision was made.

---

## The Problem We Solved

### Problem 1: Race conditions from rapid filter changes

The Applications page has five filter controls (min score, max score, decision, source, search).
Every time a filter value changes, React Query fires a new API request. Consider this sequence:

```
User types "r" in search box   -> Request #1 fires (search="r")
User types "re"                -> Request #2 fires (search="re")
User types "rea"               -> Request #3 fires (search="rea")
User types "reac"              -> Request #4 fires (search="reac")
User types "react"             -> Request #5 fires (search="react")
```

The network does not guarantee FIFO ordering. Request #2 might resolve before Request #5, or
Request #1 might return last. Without cancellation, the UI would show results for "r" (the last
response to arrive), even though the user is looking at "react" in the search box. The UI and the
data are out of sync -- **stale data.**

### Problem 2: Unmounted component updates

When a user navigates from `/applications` to `/overview`, the Applications page unmounts. But if
a fetch was in-flight, its `.then()` callback will still run and try to call `setState` on the
now-unmounted component. In React 17 and earlier, this produced the warning:

```
Warning: Can't perform a React state update on an unmounted component.
```

React 18+ silences this warning, but the problem is still wasteful -- the browser keeps the
connection open, parses the response, and does work that nobody will ever see.

### The solution: Cancel requests the instant they become irrelevant

When the query key changes (because the user changed a filter) or the component unmounts (because
the user navigated away), React Query aborts the previous request. The browser tears down the TCP
connection immediately, saving bandwidth and preventing stale data.

---

## Why We Chose This Approach

### Alternatives we considered

| Approach | Problem |
|---|---|
| **Ignore stale responses** -- let all requests complete, only render the latest | Wastes bandwidth. On mobile or metered connections, this matters. Also, the server still processes all requests. |
| **Debounce all inputs** -- wait 400ms of inactivity before firing | Debouncing helps (and we do it for search), but it does not eliminate the problem. The user can change two different filters 200ms apart, and you still get concurrent requests. |
| **Sequence number / request ID** -- tag each request, ignore responses whose ID is stale | This works for preventing stale renders, but still wastes bandwidth. The browser keeps the connection open. |
| **AbortSignal** -- cancel the request at the network level | Kills the request entirely. No wasted bandwidth, no stale data, no unmounted component warnings. |

We use **debouncing + AbortSignal together**. Debouncing reduces the number of requests fired
(the search box uses a 400ms debounce). AbortSignal handles the remaining cases where concurrent
requests still happen.

---

## How It Works In Our App

### The 3-Layer Signal Chain

Our cancellation system has three layers, each passing the signal deeper:

```
Layer 1: React Query         -> creates the AbortSignal
Layer 2: Page queryFn        -> passes signal to the API function
Layer 3: api.ts request()    -> links external signal to internal AbortController
```

Let's trace through each layer.

---

### Layer 1: React Query Creates the Signal

React Query automatically creates an `AbortController` for every query. When it calls your
`queryFn`, it passes `{ signal }` as part of the context object:

```typescript
// From src/app/applications/page.tsx
const { data: paginatedResult, isLoading: loading, error: queryError, refetch: fetchApplications } = useQuery({
  queryKey: queryKeys.applications(profileId, currentFilters),
  queryFn: ({ signal }) => getApplications(profileId, currentFilters, signal),
});
```

React Query will call `controller.abort()` on this signal when:
- The **query key changes** (e.g., the user changed a filter, so `currentFilters` changed)
- The **component unmounts** (e.g., the user navigated to a different page)
- The **query is manually invalidated** or the cache entry is garbage-collected

The key insight: `queryKey: queryKeys.applications(profileId, currentFilters)` includes the
filters object. When any filter changes, the query key changes, which causes React Query to
abort the in-flight request and start a new one.

---

### Layer 1b: Promise.all with a Single Signal

On pages that make multiple API calls, all requests share the same signal. When React Query
aborts the signal, **all concurrent requests are cancelled together**:

```typescript
// From src/app/overview/page.tsx
queryFn: async ({ signal }) => {
  const [stats, trendData, topResult] = await Promise.all([
    getOverviewStats(profileId, signal),
    getDailyTrends(profileId, 7, signal),
    getApplications(profileId, {
      min_score: 70,
      max_score: 100,
      decision: "YES",
      limit: 6,
    }, signal),
  ]);
  return { stats, trends: trendData, topMatches: topResult.data };
},
```

The analytics page does the same with **six** parallel requests:

```typescript
// From src/app/analytics/page.tsx
queryFn: async ({ signal }) => {
  const [trends, scores, sources, companies, responses, routes] =
    await Promise.all([
      getDailyTrends(profileId, 30, signal),
      getScoreDistribution(profileId, signal),
      getSourceBreakdown(profileId, signal),
      getCompanyTypes(profileId, signal),
      getResponseRates(profileId, signal),
      getRouteBreakdown(profileId, signal),
    ]);
  return { dailyTrends: trends, scoreDistribution: scores, /* ... */ };
},
```

When the user navigates away from `/analytics`, one `abort()` call cancels all six in-flight
fetches. Without this, the browser would keep six connections open doing unnecessary work.

---

### Layer 2: API Functions Accept the Signal

Every GET function in `api.ts` accepts an optional `signal` parameter and passes it through:

```typescript
// From src/lib/api.ts
export function getApplications(
  profileId: number,
  filters: Partial<ApplicationFilters> = {},
  signal?: AbortSignal,
): Promise<PaginatedResult<Application[]>> {
  return getWithCount("/api/applications", {
    profile_id: profileId,
    min_score: filters.min_score ?? 0,
    max_score: filters.max_score ?? 100,
    decision: filters.decision ?? "All",
    source: filters.source ?? "All",
    search: filters.search ?? "",
    limit: filters.limit ?? 50,
    offset: filters.offset ?? 0,
  }, signal);
}
```

The `signal` is optional because some callers (like mutations) don't need cancellation. But every
query-based caller passes it.

---

### Layer 3: api.ts Links External Signal to Internal Controller

This is where the interesting engineering happens. The `request()` function in `api.ts` creates
its **own** AbortController for timeout handling, then links the external signal to it:

```typescript
// From src/lib/api.ts — the core request() function
async function request<T>(
  method: string,
  path: string,
  options?: { params?: Record<string, string | number>; body?: unknown; signal?: AbortSignal },
): Promise<T> {
  // ... URL construction ...

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  // Link external signal (e.g. from React Query) to internal controller
  const onExternalAbort = () => controller.abort();
  options?.signal?.addEventListener("abort", onExternalAbort);

  try {
    const response = await fetch(url, {
      method,
      headers: headers(),
      body: options?.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,  // <-- fetch sees ONLY the internal signal
    });
    // ... response handling ...
  } catch (err) {
    // ... error handling (see below) ...
  } finally {
    clearTimeout(timeoutId);
    options?.signal?.removeEventListener("abort", onExternalAbort);
  }
}
```

#### Why not pass the external signal directly to fetch()?

Because we need **two** reasons to abort:
1. **External cancellation** -- React Query says "stop" (user changed filters / navigated away)
2. **Timeout** -- the request has been running for 60 seconds with no response

If we passed the external signal directly to `fetch()`, we would have no way to implement
timeouts. By creating our own internal controller, we can abort from either source.

#### Why addEventListener instead of AbortSignal.any()?

The modern way to combine signals is `AbortSignal.any([signal1, signal2])`, introduced in
Chrome 116 (August 2023) and Node 20. However:

- **Safari** only added support in Safari 17.4 (March 2024)
- **Firefox** added it in Firefox 124 (March 2024)
- Older browsers and WebViews don't support it at all

The `addEventListener("abort", ...)` pattern works in **every browser that supports
AbortController** (Chrome 66+, Firefox 57+, Safari 12.1+). It's the universally compatible
approach.

```typescript
// What we COULD write with AbortSignal.any() (if we didn't need broad compatibility):
const combinedSignal = AbortSignal.any([
  AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  options?.signal ?? new AbortController().signal,
]);
const response = await fetch(url, { signal: combinedSignal });

// What we ACTUALLY write for compatibility:
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
const onExternalAbort = () => controller.abort();
options?.signal?.addEventListener("abort", onExternalAbort);
// fetch uses controller.signal
```

The tradeoff: our code is ~4 lines longer, but it works everywhere.

---

## Distinguishing Timeout vs External Cancellation

When `fetch()` is aborted, it throws a `DOMException` with `name: "AbortError"`. But we need
to know **why** it was aborted to show the right message:

```typescript
// From src/lib/api.ts — catch block
catch (err) {
  if (err instanceof DOMException && err.name === "AbortError") {
    if (options?.signal?.aborted) throw err; // External cancellation — let React Query handle silently
    throw new Error("Request timed out");    // Internal timeout — show user-facing message
  }
  if (err instanceof TypeError) {
    throw new Error("Cannot reach the API server — is the backend running?");
  }
  throw err;
}
```

The logic:
1. Check if the error is an `AbortError` (any abort, from any source)
2. Check if the **external** signal is aborted (`options?.signal?.aborted`)
   - If yes: this was React Query cancelling the request. Re-throw the raw `AbortError`.
     React Query recognizes `AbortError` and treats it as a **silent cancellation** -- it
     does not set `error` state, does not show an error UI, just quietly moves on.
   - If no: the external signal is NOT aborted, so the abort came from our timeout.
     Throw a user-readable `"Request timed out"` message that the page will display.

This distinction is critical. Without it, every time a user changed a filter quickly, they
would see a flash of "Request timed out" error before the new data loaded.

---

## Cleanup: Preventing Memory Leaks

The `finally` block does two things:

```typescript
finally {
  clearTimeout(timeoutId);
  options?.signal?.removeEventListener("abort", onExternalAbort);
}
```

1. **`clearTimeout(timeoutId)`** -- If the request completed successfully before the 60-second
   timeout, we cancel the timer. Without this, the timer would fire after 60 seconds and call
   `controller.abort()` on an already-completed request (harmless but wasteful).

2. **`removeEventListener("abort", onExternalAbort)`** -- If the request completed before
   React Query aborted the signal, we remove our listener. Without this, the listener would
   stay attached to React Query's signal. If React Query later aborts that signal (e.g., during
   garbage collection), it would call `controller.abort()` on our already-completed controller
   (again harmless, but it's a memory leak -- the closure holds a reference to `controller`).

---

## Practical Example: Search with Debounce + AbortSignal

Here's the complete flow when a user types in the Applications search box:

```typescript
// From src/app/applications/page.tsx
const [search, setSearch] = useState("");
const debouncedSearch = useDebouncedValue(search, 400);
```

The `useDebouncedValue` hook (from `src/hooks/use-debounced-value.ts`):

```typescript
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delayMs);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delayMs]);

  return debouncedValue;
}
```

The flow when the user types "react native":

```
t=0ms    User types "r"         -> search="r",      debouncedSearch="" (unchanged)
t=50ms   User types "re"        -> search="re",     debouncedSearch="" (timer restarted)
t=100ms  User types "rea"       -> search="rea",    debouncedSearch="" (timer restarted)
t=150ms  User types "reac"      -> search="reac",   debouncedSearch="" (timer restarted)
t=200ms  User types "react"     -> search="react",  debouncedSearch="" (timer restarted)
t=600ms  400ms of silence       -> debouncedSearch="react" -> queryKey changes -> Request A fires
t=800ms  User types " n"        -> search="react n", debouncedSearch="react" (timer restarted)
                                   queryKey hasn't changed yet, Request A still in flight
t=900ms  User types "na"        -> search="react na", timer restarted
t=1000ms User types "nat"       -> search="react nat", timer restarted
t=1100ms User types "nati"      -> search="react nati", timer restarted
t=1200ms User types "native"    -> search="react native", timer restarted
t=1600ms 400ms of silence       -> debouncedSearch="react native"
                                   -> queryKey changes
                                   -> React Query ABORTS Request A
                                   -> Request B fires (search="react native")
```

Without debouncing, we would have fired 12 requests. With debouncing, we fired 2. With
AbortSignal, Request A was cancelled the instant Request B started, so the UI never shows
stale "react" results.

---

## The Key Insight

AbortSignal is not just about preventing errors -- it's about **resource efficiency and data
correctness**. Every in-flight request holds open a TCP connection, consumes server resources,
and might return data that's already irrelevant. Cancellation means the browser can immediately
reclaim that connection slot (browsers typically allow only 6 concurrent connections per origin),
and the server can stop processing a query whose results nobody wants.

The 3-layer signal chain (React Query -> API function -> request()) gives us **separation of
concerns**: React Query decides **when** to cancel, the API functions provide **the interface**
for cancellation, and `request()` handles **the mechanics** of combining timeout + external
cancellation into a single internal controller.

---

## Interview Talking Points

- "We use AbortSignal for cooperative request cancellation. React Query creates the signal and
  aborts it when the query key changes or the component unmounts. Our api.ts links this external
  signal to an internal AbortController that also handles timeouts."

- "The reason we use addEventListener instead of AbortSignal.any() is browser compatibility.
  AbortSignal.any() only shipped in Chrome 116 and Safari 17.4 in 2024, but addEventListener
  on AbortSignal works in every modern browser back to 2018."

- "We distinguish timeout from external cancellation by checking options.signal.aborted in the
  catch block. If the external signal is aborted, we re-throw the AbortError so React Query
  handles it silently. If it's not, the abort came from our setTimeout, so we throw a
  user-readable 'Request timed out' message."

- "On the overview page, we use Promise.all with a single signal so all three parallel requests
  are cancelled together. The analytics page does the same with six parallel requests. One abort
  cancels everything."

- "The finally block removes the event listener and clears the timeout to prevent memory leaks.
  Without removeEventListener, the closure would keep a reference to the AbortController even
  after the request completes."

- "We combine debouncing with AbortSignal. The search input uses a 400ms debounce to reduce
  request volume, and AbortSignal handles the remaining cases where a new request starts before
  the previous one completes."

- "The REQUEST_TIMEOUT_MS is set to 60 seconds. This is intentionally generous because some
  analytics queries aggregate large datasets on the backend. A shorter timeout would cause
  false failures on legitimate slow queries."
