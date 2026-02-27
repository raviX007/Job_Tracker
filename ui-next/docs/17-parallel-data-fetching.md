# 17. Parallel Data Fetching with Promise.all in React Query

## What Is It

Parallel data fetching is a pattern where you fire multiple independent API calls simultaneously inside a single React Query `queryFn`, wait for all of them to resolve using `Promise.all`, and then bundle the results into one cache entry. Instead of writing six separate `useQuery` hooks that each manage their own loading and error states, you write one `useQuery` whose `queryFn` fires all six requests at once and returns a single combined object.

This is different from simply calling multiple APIs sequentially (one after another, which wastes time) or using multiple `useQuery` hooks (which each get their own cache key, loading state, and error state). The `Promise.all` approach gives you:

- **True parallelism** -- all network requests leave the browser at the same time.
- **A single cache entry** -- React Query stores the combined result under one key.
- **A single loading/error state** -- the component only needs to handle one `isLoading` and one `error`.

Under the hood, `Promise.all` takes an array of promises, fires them all concurrently, and returns a new promise that resolves with an array of all results (in order) or rejects with the first error encountered.

```typescript
// Conceptual model:
const [a, b, c] = await Promise.all([
  fetchA(),  // starts immediately
  fetchB(),  // starts immediately (does NOT wait for A)
  fetchC(),  // starts immediately (does NOT wait for A or B)
]);
// Total time = max(timeA, timeB, timeC), NOT timeA + timeB + timeC
```

---

## Why We Chose This

In the Job Tracker dashboard, certain pages need several different datasets to render a complete view. The Analytics page, for example, renders six charts (daily trends, score distribution, source breakdown, company types, response rates, route breakdown). Every single one of those charts is useless without the others -- you would never show just "response rates" without "score distribution" on the analytics page.

Because all six datasets are **always needed together**, it makes no sense to manage them independently. Parallel fetching inside a single `queryFn` gives us:

1. **Simpler component code** -- one `isLoading` check instead of six.
2. **Consistent UI** -- either everything loads or nothing does. No partial renders where three charts show data and three show spinners.
3. **Fewer re-renders** -- React Query triggers one state update when all data arrives, not six separate state updates that each cause a re-render.
4. **Cleaner cache invalidation** -- invalidating `queryKeys.analytics(profileId)` refreshes all six datasets. No need to remember to invalidate six separate keys.
5. **No waterfall** -- all requests fire at once. If each request takes 200ms, you wait 200ms total, not 1200ms.

---

## Real Code Examples from the Codebase

### Example 1: Analytics Page -- 6 Parallel Calls

**File:** `src/app/analytics/page.tsx`

```typescript
const { data: queryData, isLoading: loading, error: queryError } = useQuery({
  queryKey: queryKeys.analytics(profileId),
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
    return {
      dailyTrends: trends,
      scoreDistribution: scores,
      sourceBreakdown: sources,
      companyTypes: companies,
      responseRates: responses,
      routeBreakdown: Object.entries(routes).map(([name, value]) => ({ name, value })),
    };
  },
});

const dailyTrends = queryData?.dailyTrends ?? [];
const scoreDistribution = queryData?.scoreDistribution ?? [];
const sourceBreakdown = queryData?.sourceBreakdown ?? [];
const companyTypes = queryData?.companyTypes ?? [];
const responseRates = queryData?.responseRates ?? [];
const routeBreakdown = queryData?.routeBreakdown ?? [];
const error = queryError?.message ?? null;
```

### Example 2: Overview Page -- 3 Parallel Calls

**File:** `src/app/overview/page.tsx`

```typescript
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

const data = queryData?.stats ?? null;
const trends = queryData?.trends ?? [];
const topMatches = queryData?.topMatches ?? [];
const error = queryError?.message ?? null;
```

### Example 3: Startups Page -- 3 Parallel Calls

**File:** `src/app/startups/page.tsx`

```typescript
const { data: queryData, isLoading: loading, error: queryError, refetch: fetchData } = useQuery({
  queryKey: queryKeys.startups(profileId, currentFilters as Record<string, unknown>),
  queryFn: async ({ signal }) => {
    const [profileResult, statsData, sourcesData] = await Promise.all([
      getStartupProfiles(profileId, currentFilters, signal),
      getStartupProfileStats(profileId, signal),
      getStartupProfileSources(profileId, signal),
    ]);
    return {
      startups: profileResult.data,
      totalCount: profileResult.totalCount,
      stats: statsData,
      sources: sourcesData,
    };
  },
});

const startups = queryData?.startups ?? [];
const totalCount = queryData?.totalCount ?? 0;
const stats = queryData?.stats ?? null;
const sources = queryData?.sources ?? [];
const error = queryError?.message ?? null;
```

---

## How It Works -- Full Walkthrough

### Step 1: The queryFn receives a signal

When React Query calls your `queryFn`, it passes a context object that includes an `AbortSignal`. This signal fires if the component unmounts or if the query is cancelled (e.g., the user navigates away).

```typescript
queryFn: async ({ signal }) => {
```

### Step 2: Promise.all fires all requests simultaneously

Each API function receives the `signal` so it can abort if needed. All six calls start at the same time -- the browser sends six HTTP requests in parallel.

```typescript
const [trends, scores, sources, companies, responses, routes] =
  await Promise.all([
    getDailyTrends(profileId, 30, signal),
    getScoreDistribution(profileId, signal),
    getSourceBreakdown(profileId, signal),
    getCompanyTypes(profileId, signal),
    getResponseRates(profileId, signal),
    getRouteBreakdown(profileId, signal),
  ]);
```

The array destructuring `const [trends, scores, ...]` works because `Promise.all` preserves order. The first element of the result array always corresponds to the first promise, regardless of which one resolved first.

### Step 3: Transform data if needed

Before returning, you can transform API responses into the shape your UI needs. The analytics page transforms the route breakdown from an object `{ "direct": 5, "referral": 3 }` into an array `[{ name: "direct", value: 5 }, ...]` that Recharts expects.

```typescript
routeBreakdown: Object.entries(routes).map(([name, value]) => ({ name, value })),
```

This transformation happens once when the data is fetched and is cached by React Query. The component never has to re-transform the data on every render.

### Step 4: Return a typed object

The `queryFn` returns a single object containing all the data. React Query caches this entire object under the query key.

```typescript
return {
  dailyTrends: trends,
  scoreDistribution: scores,
  sourceBreakdown: sources,
  companyTypes: companies,
  responseRates: responses,
  routeBreakdown: Object.entries(routes).map(([name, value]) => ({ name, value })),
};
```

### Step 5: Safe access with nullish coalescing

Before data loads, `queryData` is `undefined`. The nullish coalescing operator `??` provides default empty arrays so the component can always render without null checks scattered through JSX.

```typescript
const dailyTrends = queryData?.dailyTrends ?? [];
const scoreDistribution = queryData?.scoreDistribution ?? [];
```

This is safer than `|| []` because `??` only triggers on `null` or `undefined`, not on falsy values like `0` or `""`.

### Step 6: Single loading and error handling

The component only needs one loading check and one error check:

```typescript
if (loading) {
  return (
    <div>
      <PageHeader title="Analytics" subtitle="Performance charts and trends" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonChart key={i} />
        ))}
      </div>
    </div>
  );
}

if (error) {
  return (
    <div>
      <PageHeader title="Analytics" subtitle="Performance charts and trends" />
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-sm text-red-600">{error}</p>
        </CardContent>
      </Card>
    </div>
  );
}
```

No need for `isLoading1 && isLoading2 && isLoading3 && ...`.

### The Signal Threading Detail

This is critical and easy to miss. React Query provides the `signal` to the `queryFn`, but it does NOT automatically pass it to the functions you call inside. You must manually thread the signal to each individual API call:

```typescript
// CORRECT: signal passed to every call
await Promise.all([
  getDailyTrends(profileId, 30, signal),     // <-- signal
  getScoreDistribution(profileId, signal),    // <-- signal
  getSourceBreakdown(profileId, signal),      // <-- signal
]);

// WRONG: signal not passed -- these calls cannot be cancelled
await Promise.all([
  getDailyTrends(profileId, 30),     // <-- NO signal, request continues even after unmount
  getScoreDistribution(profileId),    // <-- NO signal
  getSourceBreakdown(profileId),      // <-- NO signal
]);
```

If you forget the signal, the API calls will still work, but they cannot be cancelled. This means if the user navigates away before the data loads, the requests continue running, wasting bandwidth and potentially causing state updates on unmounted components.

---

## Interview Talking Points

1. **"We use Promise.all inside React Query's queryFn to batch multiple independent API calls into a single cache entry."** This is the one-sentence summary. It shows you understand both React Query and Promise.all.

2. **"The key insight is that all six datasets on the analytics page are always shown together. They have the same lifecycle -- they load together, refresh together, and error together. Promise.all makes the code match that reality."** This shows you made a deliberate architectural choice, not just a random pattern.

3. **"Promise.all is fail-fast. If any one of the six calls fails, the entire promise rejects and React Query marks the query as errored. We chose this deliberately because showing five charts with one blank error card would be a confusing user experience."** This shows you understand the trade-offs.

4. **"The signal from React Query's queryFn context must be manually threaded to each API call. React Query gives you the signal, but it has no way to know what functions you're calling inside queryFn, so you pass it explicitly."** This is a detail that separates someone who has actually implemented this from someone who just read about it.

5. **"We transform data inside the queryFn before caching -- for example, converting the route breakdown from an object to an array. This means the transformation runs once when data arrives, not on every render."** This shows you think about performance.

6. **"If these datasets had different lifetimes -- say, one refreshed every 10 seconds and another was static -- we would use separate useQuery hooks instead. Promise.all is for data that lives and dies together."** This shows you know when NOT to use the pattern.

---

## Common Questions

### Q: What happens if one of the six API calls fails?

`Promise.all` is **fail-fast**. The moment any one promise rejects, the entire `Promise.all` rejects with that error. The other five results (even if they succeeded) are discarded. React Query catches this rejection and sets `queryError` to the failing request's error.

If you want "partial success" (show whatever loaded), you would use `Promise.allSettled` instead, which always resolves and gives you `{ status: "fulfilled", value }` or `{ status: "rejected", reason }` for each promise. We chose not to do this because partial analytics data would be confusing.

### Q: Isn't this slower because we wait for the slowest request?

No, it is faster than any sequential approach. With `Promise.all`, the total wait time equals the slowest individual request. Without it (sequential), the total wait time is the sum of all requests.

```
Promise.all:  Total = max(200ms, 150ms, 300ms, 100ms, 250ms, 180ms) = 300ms
Sequential:   Total = 200 + 150 + 300 + 100 + 250 + 180 = 1180ms
```

The only way to be "faster" than `Promise.all` is to not fetch some of the data at all (which would mean not showing some charts).

### Q: Why not use six separate useQuery hooks?

You could, and it would work. The trade-offs:

| Aspect | Promise.all in one useQuery | Six separate useQuery hooks |
|---|---|---|
| Loading state | Single `isLoading` | Six individual `isLoading` booleans |
| Error state | Single error, all-or-nothing | Individual errors per chart |
| Cache granularity | One cache key | Six cache keys |
| Refetch | One refetch refreshes all | Can refetch charts individually |
| Stale times | Same for all data | Can vary per dataset |
| Code complexity | Simpler component | More verbose |

Use separate hooks when data has different lifetimes, is shared across pages, or when you want independent error/retry per piece.

### Q: What if I want to add a seventh API call later?

Add it to the `Promise.all` array and update the destructuring and return shape:

```typescript
const [trends, scores, sources, companies, responses, routes, newData] =
  await Promise.all([
    getDailyTrends(profileId, 30, signal),
    getScoreDistribution(profileId, signal),
    getSourceBreakdown(profileId, signal),
    getCompanyTypes(profileId, signal),
    getResponseRates(profileId, signal),
    getRouteBreakdown(profileId, signal),
    getNewEndpoint(profileId, signal),  // <-- new
  ]);
return {
  // ... existing fields
  newData,  // <-- new
};
```

Then access it: `const newData = queryData?.newData ?? [];`

### Q: Does the order of promises in Promise.all matter?

The order of execution does not matter -- they all start at the same time. But the **order of results** matches the order of the input array. So `Promise.all([A, B, C])` always gives you `[resultA, resultB, resultC]`, even if B finished before A.

### Q: Why do we transform data in the queryFn instead of in the component?

Because the queryFn runs once per fetch, but the component renders many times. If you transform data during render, the transformation runs on every re-render. By transforming inside `queryFn`, the result is cached already in the right shape.

```typescript
// GOOD: transform once, cache the result
routeBreakdown: Object.entries(routes).map(([name, value]) => ({ name, value })),

// BAD: transform on every render
const routeBreakdown = Object.entries(queryData?.routeBreakdown ?? {}).map(...)
```

### Q: Why `?? []` instead of `|| []`?

The nullish coalescing operator `??` only falls back when the left side is `null` or `undefined`. The logical OR `||` falls back on any falsy value including `0`, `""`, and `false`.

```typescript
const count = queryData?.count ?? 0;   // If count is 0, keeps 0
const count = queryData?.count || 0;   // If count is 0, replaces with 0 (same here, but...)

const name = queryData?.name ?? "default";  // If name is "", keeps ""
const name = queryData?.name || "default";  // If name is "", replaces with "default" (BUG!)
```

For arrays, both work the same since `[]` is truthy, but `??` is the correct semantic choice: "use this default only if the value does not exist yet."

### Q: What about Promise.allSettled vs Promise.all?

| Method | Behavior on failure | Return type |
|---|---|---|
| `Promise.all` | Rejects immediately when any promise rejects (fail-fast) | Array of resolved values |
| `Promise.allSettled` | Always resolves, even if some promises reject | Array of `{ status, value/reason }` objects |

Use `Promise.allSettled` when you want partial results and can handle some data being missing. Use `Promise.all` when all data is required and a partial state would be worse than showing an error.

### Q: How does the browser handle 6 simultaneous requests?

Browsers limit concurrent connections per domain (typically 6 in HTTP/1.1, unlimited in HTTP/2 with multiplexing). Since all six requests go to the same API backend, HTTP/2 handles them efficiently over a single TCP connection. If you were on HTTP/1.1 with exactly 6 requests, they would all fire at once. A 7th would queue until one completes.
