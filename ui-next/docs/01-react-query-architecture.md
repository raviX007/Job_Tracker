# React Query Architecture

## What Is This?

React Query (TanStack Query) is a server-state management library for React. In this project, it replaces the traditional `useEffect` + `useState` pattern for fetching data from the backend API. Every single data-fetching operation in the app -- overview stats, application lists, email queues, analytics charts, tracker rows, startup profiles -- goes through React Query's `useQuery` and `useMutation` hooks.

This document explains *why* we chose React Query, *how* it is configured, and *what patterns* emerged from using it across 8 pages with 16 GET endpoints and 8 mutations.

---

## Why We Chose This Approach

### The Problem: Raw `useEffect` + `useState`

Before React Query, a typical data-fetching component looked like this:

```tsx
// THE OLD WAY -- what you would write without React Query
function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getApplications(profileId, filters)
      .then((data) => {
        if (!cancelled) {
          setApplications(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [profileId, filters.min_score, filters.max_score, filters.decision,
      filters.source, filters.search, filters.limit, filters.offset]);

  // ... render using applications, loading, error
}
```

This has **five critical problems**:

1. **Race conditions** -- If the user changes filters quickly, two fetches run concurrently. The second might return before the first, but when the first finally resolves, it overwrites the newer data with stale data. The `cancelled` boolean helps, but it is easy to forget and easy to get wrong.

2. **No caching** -- Every time the user navigates away and comes back, the data is fetched again from scratch. The user sees a loading spinner every single time, even though the data hasn't changed.

3. **Manual loading/error state** -- You need three `useState` calls per page just for the fetch lifecycle. Multiply that by 8 pages and it is 24 useState calls just for boilerplate.

4. **No deduplication** -- If two components on the same page need the same data (e.g., the Overview page fetches stats, trends, AND top matches), each one triggers its own network request independently.

5. **No background updates** -- If data changes on the server while the user is looking at the page, there is no mechanism to refresh it. You would need to add a polling interval or a manual "refresh" button and wire it all up yourself.

### How React Query Solves Each Problem

| Problem | React Query Solution |
|---|---|
| Race conditions | Automatic request cancellation via AbortSignal -- when the query key changes, the previous in-flight request is cancelled |
| No caching | Built-in cache keyed by the query key array; data persists across navigations |
| Manual loading/error | `useQuery` returns `{ data, isLoading, error }` -- one hook, zero boilerplate |
| No deduplication | If two components use the same query key, only one network request fires |
| No background updates | `staleTime`, `refetchOnWindowFocus`, and `invalidateQueries` handle freshness automatically |

### Alternatives We Considered

- **SWR** (by Vercel): Similar to React Query but with a smaller API surface. We chose React Query because it has first-class support for mutations with `onMutate`/`onError`/`onSettled` callbacks, which is essential for our optimistic update pattern.
- **Redux Toolkit Query (RTK Query)**: Would have required pulling in the entire Redux ecosystem. Since our app has almost zero client-side state (filters and UI toggles only), Redux would be overkill.
- **Plain fetch in useEffect**: What we started with. It worked for the first page but became unmanageable at 8 pages with cross-page cache invalidation needs.

---

## How It Works In Our App

### 1. QueryClient Configuration (`providers.tsx`)

The entire app is wrapped in a single `QueryClientProvider`. Here is the exact code:

```tsx
// src/components/providers.tsx
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
```

**Why each setting matters:**

- **`staleTime: 30_000` (30 seconds)** -- Data is considered "fresh" for 30 seconds after it is fetched. During this window, navigating back to a page shows the cached data *instantly* without triggering a new network request. We chose 30 seconds because this is a dashboard app -- job data does not change every second, but it *does* change within minutes as the pipeline processes new jobs. Thirty seconds gives a snappy UX without serving obviously stale data.

- **`retry: 1` (one retry)** -- If a request fails, React Query will retry it once before showing the error. The default is 3 retries with exponential backoff. We reduced it to 1 because: if the backend is down, retrying 3 times just delays showing the error message by ~15 seconds. The user sees a spinner for a long time before learning the API is unreachable. One retry catches transient network blips; anything beyond that is a real outage.

- **`refetchOnWindowFocus: false`** -- By default, React Query refetches all stale queries when the user switches back to the browser tab. This sounds useful, but in practice it causes jarring UI flashes -- you alt-tab back and suddenly all your loading skeletons appear for a moment. For a job tracker dashboard that you keep open alongside other tabs, this is distracting. We disabled it.

**Why `useState(() => new QueryClient())`?**

This is a subtle but important pattern. The QueryClient must be created exactly once, not on every re-render. If you write:

```tsx
// BAD -- creates a new QueryClient on every render, destroying the cache
const queryClient = new QueryClient({ ... });
```

...then every time `Providers` re-renders (which happens whenever its parent re-renders), a brand-new QueryClient is created. The cache is lost. All queries refetch. This is a common mistake that freshers make.

By wrapping it in `useState(() => ...)`, the initializer function runs only once -- on the first render -- and the same instance is reused for every subsequent render. This is the React-idiomatic way to create a singleton within a component.

### 2. The Query Key Factory (`query-keys.ts`)

Every `useQuery` call needs a unique key that identifies what data it represents. Instead of scattering string literals across 8 page files, we centralize all keys in one file:

```ts
// src/lib/query-keys.ts
export const queryKeys = {
  overview: (pid: number) => ["overview", pid] as const,
  dailyTrends: (pid: number, days: number) => ["dailyTrends", pid, days] as const,
  applications: (pid: number, filters: Record<string, unknown>) =>
    ["applications", pid, filters] as const,
  sources: (pid: number) => ["sources", pid] as const,
  emails: (pid: number, status: string, source: string) =>
    ["emails", pid, status, source] as const,
  emailStatuses: (pid: number) => ["emailStatuses", pid] as const,
  emailSources: (pid: number) => ["emailSources", pid] as const,
  appsForUpdate: (pid: number) => ["appsForUpdate", pid] as const,
  analyzedJobs: (pid: number) => ["analyzedJobs", pid] as const,
  analytics: (pid: number) => ["analytics", pid] as const,
  tracker: (pid: number) => ["tracker", pid] as const,
  startups: (pid: number, filters: Record<string, unknown>) =>
    ["startups", pid, filters] as const,
  startupStats: (pid: number) => ["startupStats", pid] as const,
  startupSources: (pid: number) => ["startupSources", pid] as const,
};
```

**Why this pattern exists:**

1. **Single source of truth** -- If you need to change a key structure, you change it in one place. Every page that uses that key automatically picks up the change.

2. **`as const` for type safety** -- The `as const` assertion makes the return type a readonly tuple (`readonly ["applications", number, Record<string, unknown>]`) instead of a generic `(string | number | Record<string, unknown>)[]`. This means TypeScript can catch mistakes like accidentally passing the wrong query key to `invalidateQueries`.

3. **Automatic cache invalidation when parameters change** -- Consider the applications query key:

```ts
queryKeys.applications(1, { min_score: 0, max_score: 100, decision: "All", source: "All" })
// Returns: ["applications", 1, { min_score: 0, max_score: 100, decision: "All", source: "All" }]
```

When the user changes a filter (e.g., sets `decision` to "YES"), the key changes to:

```ts
["applications", 1, { min_score: 0, max_score: 100, decision: "YES", source: "All" }]
```

React Query does a deep equality check on the key. Since the filters object changed, it treats this as a *new* query and fires a fresh request. The old data for `decision: "All"` remains in the cache -- if the user switches back, it loads instantly.

4. **Hierarchical invalidation** -- When a mutation succeeds, we often want to invalidate all queries of a certain type regardless of their filters. For example, after deleting an email:

```ts
queryClient.invalidateQueries({ queryKey: queryKeys.emails(profileId, filterStatus, filterSource) });
```

React Query matches query keys by *prefix*. Since `queryKeys.emails(profileId, filterStatus, filterSource)` returns `["emails", profileId, filterStatus, filterSource]`, any cached query whose key starts with `["emails", profileId, filterStatus, filterSource]` (including those with pagination params appended) will be invalidated.

### 3. How Pages Use `useQuery`

Here is the actual pattern used across every page. From `applications/page.tsx`:

```tsx
// src/app/applications/page.tsx

const currentFilters: Partial<ApplicationFilters> = {
  min_score: minScore,
  max_score: maxScore,
  decision,
  source,
  search: debouncedSearch,
  limit: pageSize,
  offset: (page - 1) * pageSize,
};

const { data: paginatedResult, isLoading: loading, error: queryError, refetch: fetchApplications } = useQuery({
  queryKey: queryKeys.applications(profileId, currentFilters),
  queryFn: ({ signal }) => getApplications(profileId, currentFilters, signal),
});

const applications = paginatedResult?.data ?? [];
const totalCount = paginatedResult?.totalCount ?? 0;
const error = queryError?.message ?? null;
```

That is **5 lines** to get data, loading state, error state, and a refetch function. Compare to the 25+ lines of the useEffect approach shown earlier.

Key things to notice:

- **`queryFn: ({ signal })`** -- React Query passes an AbortSignal to the query function. If the query key changes before this request completes, React Query aborts the signal, which propagates down to the `fetch` call in `api.ts`. No race conditions.

- **`refetch: fetchApplications`** -- The destructured `refetch` function is bound to the error card's "Retry" button. One click re-runs the query.

- **`paginatedResult?.data ?? []`** -- Safe fallback while the query is loading.

### 4. Aggregating Multiple API Calls

Some pages need data from multiple endpoints simultaneously. The Overview page, for example, fetches stats, trends, and top matches in a single query function:

```tsx
// src/app/overview/page.tsx

const { data: queryData, isLoading: loading, error: queryError, refetch } = useQuery({
  queryKey: queryKeys.overview(profileId),
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
});
```

The Analytics page does the same with 6 parallel API calls:

```tsx
// src/app/analytics/page.tsx

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
  return { dailyTrends: trends, scoreDistribution: scores, ... };
},
```

All 6 requests fire in parallel via `Promise.all`, and the AbortSignal is shared across all of them -- if the user navigates away, all 6 are cancelled simultaneously.

### 5. The Debounced Search Integration

The Applications page has a search box. Typing fires a new query for every keystroke, which would be wasteful. We combine React Query with our `useDebouncedValue` hook:

```tsx
// src/app/applications/page.tsx

const [search, setSearch] = useState("");
const debouncedSearch = useDebouncedValue(search, 400);

// This filter object includes `debouncedSearch`, not `search`
const currentFilters: Partial<ApplicationFilters> = {
  ...
  search: debouncedSearch,
  ...
};

// The query key includes the debounced value
queryKey: queryKeys.applications(profileId, currentFilters),
```

When the user types "react developer":
1. `search` updates on every keystroke: "r", "re", "rea", "reac", "react", ...
2. `debouncedSearch` only updates 400ms after the last keystroke: "react developer"
3. Since the query key depends on `debouncedSearch`, React Query only fires ONE request for the final value.

This is a clean separation of concerns: the hook handles debouncing, React Query handles fetching and caching, and they compose naturally.

### 6. Appending Pagination to Query Keys

Several pages extend the base query key with pagination parameters:

```tsx
// src/app/emails/page.tsx

const queryKey = [...queryKeys.emails(profileId, filterStatus, filterSource), page, pageSize] as const;

const { data: paginatedEmails, ... } = useQuery({
  queryKey,
  queryFn: ({ signal }) => getEmailQueue(profileId, filterStatus, filterSource, pageSize, (page - 1) * pageSize, signal),
});
```

The spread operator `...queryKeys.emails(...)` takes the base key `["emails", 1, "All", "All"]` and appends `[1, 50]` for page and page size, producing `["emails", 1, "All", "All", 1, 50]`.

This means:
- Page 1 and page 2 have different cache entries (different keys).
- Going back to page 1 loads from cache instantly (30-second stale window).
- Invalidating by the base prefix `queryKeys.emails(profileId, filterStatus, filterSource)` clears ALL pages at once.

---

## The Key Insight

React Query is not just a data-fetching library -- it is a **server-state cache**. The mental model shift is: instead of "fetch data and store it in component state," you think "declare what data you need and let the cache figure out fetching, caching, and freshness."

This inversion of control is what makes the codebase so compact. Each page declares its data dependency with `useQuery` and a key, and React Query handles everything else: when to fetch, when to serve from cache, when to refetch in the background, and when to throw away stale data.

---

## Interview Talking Points

- "We use React Query because it replaces the fragile `useEffect` + `useState` pattern. Without it, every page would need 25+ lines of boilerplate for loading, error, race condition handling, and cache management. With React Query, the same thing takes 5 lines."

- "Our `staleTime` is 30 seconds. This means if you navigate away and come back within 30 seconds, the data loads instantly from cache with zero network requests. This is critical for perceived performance in a dashboard app."

- "We set `retry: 1` instead of the default 3 because if the API server is down, retrying three times with exponential backoff just makes the user wait 15 seconds before seeing an error. One retry catches transient blips; anything more is a real outage."

- "The QueryClient is created inside `useState(() => ...)` to ensure exactly one instance exists for the lifetime of the app. Creating it outside the hook or without the lazy initializer would destroy the cache on every re-render."

- "We have a query key factory in `query-keys.ts` that centralizes all cache keys. This gives us type safety via `as const`, a single source of truth for key shapes, and hierarchical invalidation -- when a mutation succeeds, we can invalidate all queries of a type by matching the key prefix."

- "The debounced search in the Applications page shows how React Query composes with other hooks. `useDebouncedValue` delays the search string by 400ms, and since the query key includes the debounced value, React Query only fires when the user stops typing. Zero extra wiring needed."

- "On the Analytics page, a single `useQuery` call fires 6 API requests in parallel via `Promise.all` and shares the same AbortSignal across all of them. If the user navigates away mid-load, all 6 requests are cancelled. This is practically impossible to implement correctly with raw useEffect."
