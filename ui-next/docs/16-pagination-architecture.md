# 16 - Pagination Architecture

## What Is It

Pagination is the pattern of splitting a large dataset into discrete pages and loading only one page at a time. In this codebase, pagination is implemented end-to-end across four layers:

1. **Backend API** -- returns a page of data in the response body and the total count in an `X-Total-Count` HTTP header.
2. **API client** (`getWithCount<T>`) -- reads both the body and the header, returning a typed `PaginatedResult<T>`.
3. **React Query cache** -- each page is cached independently using `[...queryKey, page, pageSize]` composite keys.
4. **Pagination component** -- a reusable UI element that renders Previous/Next buttons and auto-hides when there is only one page.

Four pages in the application use this exact pattern: **Applications**, **Emails**, **Tracker**, and **Startups**.

---

## Why We Chose This

| Concern | Decision | Alternative Rejected |
|---------|----------|---------------------|
| Total count delivery | `X-Total-Count` HTTP header | Envelope response `{ data: [], total: 123 }` -- adds nesting, forces every consumer to unwrap |
| Type safety | Generic `PaginatedResult<T>` | Separate total count queries -- doubles API calls |
| Cache granularity | Per-page cache keys | Single "all data" cache -- refetching one page reloads everything |
| Offset calculation | `(page - 1) * pageSize` in the component | Server-side page numbers -- leaks pagination math into the API |
| UI component | Auto-hiding `<Pagination>` | Always-visible pagination -- confusing when there is only 1 page of results |

### Why header-based pagination?

The API follows a **separation of concerns** principle:

- The **response body** contains the data (the array of applications, emails, etc.). It has one shape, one purpose.
- The **response header** `X-Total-Count` contains metadata about the data (how many total items exist). It is orthogonal to the data itself.

This avoids the "envelope" anti-pattern where every paginated endpoint returns:

```json
{
  "data": [...],
  "total": 1234,
  "page": 1,
  "pageSize": 50
}
```

With the envelope pattern, non-paginated endpoints return raw arrays while paginated ones return objects -- inconsistent. With headers, the body is always an array regardless of whether pagination is used. The `getWithCount<T>` function transparently combines both into a `PaginatedResult<T>` for the client.

---

## Real Code Examples

### PaginatedResult<T> -- the type

**File: `src/lib/types.ts`** (lines 1-6)

```typescript
export interface PaginatedResult<T> {
  data: T;
  totalCount: number;
}
```

This is a generic container. `T` is typically an array type like `Application[]` or `TrackerRow[]`, so `PaginatedResult<Application[]>` means `{ data: Application[], totalCount: number }`.

### getWithCount<T> -- the API client function

**File: `src/lib/api.ts`** (lines 90-139)

```typescript
async function getWithCount<T>(
  path: string,
  params?: Record<string, string | number>,
  signal?: AbortSignal,
): Promise<PaginatedResult<T>> {
  let url = `${API_BASE}${path}`;

  if (params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      searchParams.set(key, String(value));
    }
    url += `?${searchParams.toString()}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  const onExternalAbort = () => controller.abort();
  signal?.addEventListener("abort", onExternalAbort);

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: headers(),
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    const totalCount = parseInt(response.headers.get("X-Total-Count") || "0", 10);
    const data = await response.json();
    return { data, totalCount };
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      if (signal?.aborted) throw err;
      throw new Error("Request timed out");
    }
    if (err instanceof TypeError) {
      throw new Error("Cannot reach the API server — is the backend running?");
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
    signal?.removeEventListener("abort", onExternalAbort);
  }
}
```

### API endpoint functions that use getWithCount

**File: `src/lib/api.ts`**

```typescript
// Applications (line 161)
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

// Email Queue (line 184)
export function getEmailQueue(
  profileId: number,
  status: string = "All",
  source: string = "All",
  limit: number = 50,
  offset: number = 0,
  signal?: AbortSignal,
): Promise<PaginatedResult<EmailQueueItem[]>> {
  return getWithCount("/api/emails/queue", {
    profile_id: profileId, status, source, limit, offset,
  }, signal);
}

// Tracker (line 281)
export function getTrackerData(
  profileId: number,
  limit: number = 50,
  offset: number = 0,
  signal?: AbortSignal,
): Promise<PaginatedResult<TrackerRow[]>> {
  return getWithCount("/api/tracker", {
    profile_id: profileId, limit, offset,
  }, signal);
}

// Startup Profiles (line 314)
export function getStartupProfiles(
  profileId: number,
  filters: Partial<StartupProfileFilters> = {},
  signal?: AbortSignal,
): Promise<PaginatedResult<StartupProfile[]>> {
  return getWithCount("/api/startup-profiles", {
    profile_id: profileId,
    source: filters.source ?? "All",
    funding_round: filters.funding_round ?? "All",
    min_age: filters.min_age ?? 0,
    max_age: filters.max_age ?? 24,
    has_funding: filters.has_funding ?? "All",
    search: filters.search ?? "",
    sort_by: filters.sort_by ?? "match_score",
    limit: filters.limit ?? 50,
    offset: filters.offset ?? 0,
  }, signal);
}
```

### Pagination component

**File: `src/components/ui/pagination.tsx`**

```typescript
"use client";

import { Button } from "@/components/ui/button";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between pt-4">
      <p className="text-sm text-muted-foreground">
        {total.toLocaleString()} total
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </Button>
        <span className="text-sm text-muted-foreground">
          Page {page} of {totalPages}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
```

### Page-level usage -- Tracker page

**File: `src/app/tracker/page.tsx`** (lines 56-65, 470-478)

```typescript
// State
const [page, setPage] = useState(1);
const pageSize = 50;

// Query with per-page cache key
const { data: paginatedResult, isLoading: loading, error: queryError, refetch: fetchData } = useQuery({
  queryKey: [...queryKeys.tracker(profileId), page, pageSize],
  queryFn: ({ signal }) => getTrackerData(profileId, pageSize, (page - 1) * pageSize, signal),
});

// Destructuring the result
const rows = paginatedResult?.data ?? [];
const totalCount = paginatedResult?.totalCount ?? 0;

// In JSX (at the bottom of the component):
{!loading && !error && (
  <Pagination
    page={page}
    pageSize={pageSize}
    total={totalCount}
    onPageChange={setPage}
  />
)}
```

### Page-level usage -- Applications page

**File: `src/app/applications/page.tsx`** (lines 305-306, 326-343, 531-539)

```typescript
// State
const [page, setPage] = useState(1);
const pageSize = 50;

// Filters include offset calculation
const currentFilters: Partial<ApplicationFilters> = {
  min_score: minScore,
  max_score: maxScore,
  decision,
  source,
  search: debouncedSearch,
  limit: pageSize,
  offset: (page - 1) * pageSize,
};

// Query -- filters are part of the cache key
const { data: paginatedResult, isLoading: loading } = useQuery({
  queryKey: queryKeys.applications(profileId, currentFilters),
  queryFn: ({ signal }) => getApplications(profileId, currentFilters, signal),
});

const applications = paginatedResult?.data ?? [];
const totalCount = paginatedResult?.totalCount ?? 0;

// Reset page when filters change
useEffect(() => {
  setPage(1);
}, [minScore, maxScore, decision, source, debouncedSearch]);

// In JSX:
<Pagination
  page={page}
  pageSize={pageSize}
  total={totalCount}
  onPageChange={setPage}
/>
```

### Page-level usage -- Emails page

**File: `src/app/emails/page.tsx`** (lines 81-82, 109-117, 613-618)

```typescript
// State
const [page, setPage] = useState(1);
const pageSize = 50;

// Query key includes filter state AND page
const queryKey = [...queryKeys.emails(profileId, filterStatus, filterSource), page, pageSize] as const;

const { data: paginatedEmails } = useQuery({
  queryKey,
  queryFn: ({ signal }) => getEmailQueue(profileId, filterStatus, filterSource, pageSize, (page - 1) * pageSize, signal),
});

const emails = paginatedEmails?.data ?? [];
const totalCount = paginatedEmails?.totalCount ?? 0;

// In JSX:
<Pagination
  page={page}
  pageSize={pageSize}
  total={totalCount}
  onPageChange={setPage}
/>
```

### Page-level usage -- Startups page

**File: `src/app/startups/page.tsx`** (lines 77-84, 86-101, 354-359)

```typescript
// State
const [page, setPage] = useState(1);
const pageSize = 50;

// Offset calculated inline
const currentFilters = {
  ...filters,
  limit: pageSize,
  offset: (page - 1) * pageSize,
};

// Query
const { data: queryData } = useQuery({
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

// In JSX:
<Pagination
  page={page}
  pageSize={pageSize}
  total={totalCount}
  onPageChange={setPage}
/>
```

---

## How It Works

### 1. X-Total-Count Header

The backend (FastAPI / Python) sends pagination metadata as an HTTP response header:

```
HTTP/1.1 200 OK
Content-Type: application/json
X-Total-Count: 1234

[{"job_id": 1, "company": "Acme", ...}, ...]
```

The body is a plain JSON array. The total count lives outside the body in a header named `X-Total-Count`. This header name is a widely-used convention (GitHub's API uses it, as do many REST APIs following the JSON API spec guidelines).

In `getWithCount<T>`, the header is extracted with:

```typescript
const totalCount = parseInt(response.headers.get("X-Total-Count") || "0", 10);
```

The `|| "0"` fallback handles the case where the header is missing (e.g., during development or if the backend does not implement pagination for a particular endpoint). The `parseInt(..., 10)` ensures the string is parsed as a base-10 integer.

### 2. getWithCount<T> -- the Generic Function

This function is the central piece of the pagination architecture. It does everything `get<T>` does (URL construction, timeout, abort signal handling, error mapping) plus two extra steps:

1. **Reads the `X-Total-Count` header** from the response before parsing the body.
2. **Returns `{ data, totalCount }`** instead of just `data`.

The function is generic over `T`, so:
- `getWithCount<Application[]>("/api/applications", ...)` returns `Promise<PaginatedResult<Application[]>>`
- `getWithCount<TrackerRow[]>("/api/tracker", ...)` returns `Promise<PaginatedResult<TrackerRow[]>>`
- `getWithCount<EmailQueueItem[]>("/api/emails/queue", ...)` returns `Promise<PaginatedResult<EmailQueueItem[]>>`

TypeScript infers the correct type at each call site, so when you destructure `paginatedResult.data`, you get the correctly typed array.

### 3. PaginatedResult<T>

```typescript
export interface PaginatedResult<T> {
  data: T;
  totalCount: number;
}
```

This is deliberately minimal. It contains exactly two things:
- `data: T` -- the actual payload (usually an array).
- `totalCount: number` -- how many items exist in total across all pages.

It does **not** include `page`, `pageSize`, `totalPages`, or `hasMore`. Those are derived in the component or the Pagination UI. Keeping the API response lean means the server does not need to know anything about the client's pagination preferences -- it just reports "here is the data you asked for, and there are N total items."

### 4. Per-Page Cache Keys

React Query (TanStack Query) uses the `queryKey` to determine cache identity. Each unique key gets its own cache entry, loading state, and refetch timer.

Here is how the Tracker page builds its key:

```typescript
queryKey: [...queryKeys.tracker(profileId), page, pageSize]
// Expands to: ["tracker", 1, 1, 50]  (profileId=1, page=1, pageSize=50)
// Page 2:    ["tracker", 1, 2, 50]
// Page 3:    ["tracker", 1, 3, 50]
```

Each page number creates a different cache key, which means:

1. **Page 1 data is cached while you view page 2.** If you click "Previous" to go back to page 1, React Query serves the cached data instantly (no loading spinner) and refetches in the background.
2. **Changing `profileId` invalidates all pages.** Because `profileId` is part of the key, switching users clears the cache.
3. **`pageSize` is part of the key.** If you changed the page size from 50 to 25, the cache would be separate (though this codebase uses a fixed `pageSize = 50`).

The Applications page takes this further by including filters in the key:

```typescript
queryKey: queryKeys.applications(profileId, currentFilters)
// Expands to: ["applications", 1, { min_score: 0, max_score: 100, decision: "All", ... offset: 0 }]
```

Since `offset` is part of `currentFilters`, each page+filter combination is independently cached.

### 5. Offset Calculation

The API uses **offset-based pagination**: `limit` (how many items per page) and `offset` (how many items to skip).

The UI uses **1-based page numbers** (Page 1, Page 2, Page 3...) because that is what users expect. The conversion:

```typescript
offset = (page - 1) * pageSize
```

| Page (user-facing) | Offset (API parameter) | Items returned |
|----|--------|----------------|
| 1  | 0      | Items 1-50     |
| 2  | 50     | Items 51-100   |
| 3  | 100    | Items 101-150  |

This calculation happens in the component when calling the API function:

```typescript
// Tracker page:
getTrackerData(profileId, pageSize, (page - 1) * pageSize, signal)

// Applications page (via filters object):
offset: (page - 1) * pageSize

// Emails page:
getEmailQueue(profileId, filterStatus, filterSource, pageSize, (page - 1) * pageSize, signal)
```

### 6. Pagination Component Behavior

The `<Pagination>` component receives four props and handles all display logic:

```
page=2, pageSize=50, total=237
                          |
                          v
totalPages = Math.max(1, Math.ceil(237 / 50))  =>  5

+---------------------------------------------------+
| 237 total          [Previous] Page 2 of 5  [Next]  |
+---------------------------------------------------+
```

**Auto-hide behavior:**

```typescript
if (totalPages <= 1) return null;
```

When there are 50 or fewer items, `totalPages` is 1 and the component renders nothing. No unnecessary "Page 1 of 1" clutter. This is why the Pagination component can be included unconditionally in the JSX -- it handles its own visibility.

**Button disable logic:**

```typescript
disabled={page <= 1}     // Previous button -- disabled on page 1
disabled={page >= totalPages}  // Next button -- disabled on last page
```

**Total count formatting:**

```typescript
{total.toLocaleString()} total
```

`toLocaleString()` adds thousands separators, so 1234 becomes "1,234 total" (locale-dependent). This is a UX detail that helps users understand the scale of the data.

### 7. The Four Paginated Endpoints

| Page | API Function | Endpoint | Query Key |
|------|-------------|----------|-----------|
| Applications | `getApplications()` | `/api/applications` | `["applications", pid, filters]` |
| Emails | `getEmailQueue()` | `/api/emails/queue` | `["emails", pid, status, source, page, pageSize]` |
| Tracker | `getTrackerData()` | `/api/tracker` | `["tracker", pid, page, pageSize]` |
| Startups | `getStartupProfiles()` | `/api/startup-profiles` | `["startups", pid, filters]` |

All four follow the same pattern:

```
useState(page) --> queryKey includes page --> queryFn calls getWithCount
      ^                                           |
      |                                           v
  setPage(n)  <-- onPageChange <-- Pagination <-- PaginatedResult
```

The consistency means if you understand how one page works, you understand all four. The only differences are:
- Which API function is called.
- What additional filters are included.
- Whether `page` is appended to an existing query key or embedded in a filters object.

### 8. Filter Reset on Page Change

Both the Applications and Emails pages reset to page 1 when filters change:

```typescript
// Applications page:
useEffect(() => {
  setPage(1);
}, [minScore, maxScore, decision, source, debouncedSearch]);

// Emails page:
const resetPage = () => setPage(1);
// Called inline: onValueChange={(v) => { setFilterStatus(v); resetPage(); }}

// Startups page:
function updateFilter<K extends keyof StartupProfileFilters>(key: K, value: StartupProfileFilters[K]) {
  setFilters((prev) => ({ ...prev, [key]: value }));
  setPage(1);  // Reset page when any filter changes
}
```

This prevents a confusing state where you are on page 5 of "All" applications, change the filter to "Yes" (which might only have 2 pages), and end up on a non-existent page 5 with no results. Resetting to page 1 on filter change is a standard UX pattern.

---

## Interview Talking Points

1. **"We use X-Total-Count headers for pagination metadata instead of wrapping the response in an envelope object."** This shows you understand REST API design principles and the separation between data and metadata.

2. **"The `getWithCount<T>` function is generic -- it reads the total count header and the typed body, returning a `PaginatedResult<T>`. All four paginated endpoints share this single function."** This demonstrates DRY (Don't Repeat Yourself) thinking and TypeScript generics knowledge.

3. **"Each page is independently cached by React Query because the page number is part of the query key."** This shows you understand how cache key identity works in TanStack Query and why it matters for performance (instant back-navigation).

4. **"The Pagination component auto-hides when totalPages is 1, so we can include it unconditionally in the JSX."** This demonstrates component self-management -- the consumer does not need to check whether pagination is needed.

5. **"We convert 1-based page numbers to 0-based offsets with `(page - 1) * pageSize`."** A simple detail, but it shows you understand the difference between user-facing page numbers and API-level skip/offset parameters.

6. **"When filters change, we reset to page 1 to prevent viewing a non-existent page."** This shows you think about edge cases and UX consistency.

7. **"The same pagination pattern -- `useState` for page, `useQuery` with page in the key, `getWithCount` for fetching, `<Pagination>` for UI -- is reused identically across four pages."** Consistency and reusability are key software engineering principles.

---

## Common Questions

### Q: Why not cursor-based pagination?

Cursor-based pagination (using a `next_cursor` token instead of offset/limit) is better for infinite scroll, real-time feeds, or datasets where items are frequently inserted/deleted (which shifts offsets). This application has page-based navigation (Previous/Next buttons with page numbers), infrequently changing data, and a need to jump to specific pages. Offset-based pagination is simpler and sufficient for these requirements.

### Q: Why is `pageSize` hardcoded at 50 instead of being user-configurable?

Simplicity. A configurable page size adds a dropdown, another state variable, and another dimension to the cache key. 50 items is a reasonable default that fits most screens. If needed in the future, adding a `pageSize` dropdown would be straightforward since the architecture already includes `pageSize` in the query key.

### Q: Why does `getWithCount` duplicate code from the `request` function?

It does. The `getWithCount` function has its own URL construction, timeout, and error handling rather than calling the shared `request` helper. This is because `request` calls `response.json()` and returns the result directly -- it never exposes the `Response` object needed to read headers. Rather than refactoring `request` (which would affect all non-paginated endpoints), `getWithCount` implements its own fetch logic. This is a pragmatic tradeoff: some code duplication in exchange for not touching a working abstraction.

### Q: What happens if the server does not send the X-Total-Count header?

The fallback `|| "0"` kicks in:

```typescript
const totalCount = parseInt(response.headers.get("X-Total-Count") || "0", 10);
```

`totalCount` becomes 0, `totalPages` becomes `Math.max(1, Math.ceil(0 / 50))` = 1, and the Pagination component returns `null` (auto-hides). The data still renders normally; you just lose the pagination controls. This makes the system resilient to backend changes.

### Q: Why `Math.max(1, Math.ceil(total / pageSize))` instead of just `Math.ceil`?

`Math.ceil(0 / 50)` is 0. If `totalPages` were 0, the "Page 1 of 0" text would be confusing. `Math.max(1, ...)` ensures there is always at least 1 page, even when the total is 0. This covers the edge case of an empty dataset.

### Q: How does the Pagination component interact with optimistic updates?

In the Emails and Tracker pages, mutations use optimistic updates that modify the cached `PaginatedResult<T>`. For example, deleting an email:

```typescript
// From emails/page.tsx
onMutate: async (emailId) => {
  const prev = queryClient.getQueryData<PaginatedResult<EmailQueueItem[]>>(queryKey);
  if (prev) {
    queryClient.setQueryData<PaginatedResult<EmailQueueItem[]>>(queryKey, {
      ...prev,
      data: prev.data.filter(e => e.id !== emailId),
      totalCount: prev.totalCount - 1,  // Decrement total count
    });
  }
}
```

The optimistic update modifies both `data` (removes the email from the array) and `totalCount` (decrements by 1). This means the Pagination component immediately reflects the change -- if deleting the last item on a page drops `totalPages` below the current page, the user would need to navigate back. The `onSettled` callback refetches to reconcile with the server's actual state.

### Q: Can a user navigate to an arbitrary page number?

Not with the current UI. The Pagination component only supports sequential navigation (Previous/Next). There is no page number input or page number buttons. For the scale of data in this application (hundreds to low thousands of items), sequential navigation is sufficient. If needed, adding page number buttons or a "Go to page" input would only require changes to the Pagination component -- the data fetching layer already supports arbitrary page numbers via the `setPage` callback.
