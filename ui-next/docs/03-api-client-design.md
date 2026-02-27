# API Client Design

## What Is This?

The API client is a single file -- `src/lib/api.ts` -- that handles **every** network request the frontend makes. It is 363 lines long and exports 24 functions, but at its core it is built on one generic function: `request<T>()`. Every GET, POST, PUT, and DELETE in the entire application flows through this one function.

This is the single-responsibility principle applied to network concerns: authentication, timeouts, URL construction, error categorization, abort signal handling, and JSON serialization all happen in one place. No page component ever thinks about HTTP headers, timeout logic, or error parsing.

---

## Why We Chose This Approach

### The Problem: Scattered Network Logic

Without a centralized API client, every page would do something like:

```tsx
// BAD -- network logic scattered across every page
async function fetchApplications() {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/applications?profile_id=${profileId}&min_score=0`,
    {
      headers: {
        "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || "",
        "Content-Type": "application/json",
      },
    }
  );
  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail);
  }
  return response.json();
}
```

Problems:
1. **Auth header repeated** in every fetch call across every page.
2. **No timeout** -- if the server hangs, the request hangs forever.
3. **Error handling** is inconsistent -- some pages might parse JSON errors, others might not.
4. **URL construction** is manual and error-prone (forgetting `?` vs `&`).
5. **AbortSignal** handling requires boilerplate every time.

### The Solution: One File, One Concern

`api.ts` solves all of this with a layered architecture:

```
Page Component
    |
    v
Export Function (e.g., getApplications)  <-- type-safe, domain-specific
    |
    v
Helper (get / post / put / del / getWithCount)  <-- HTTP verb abstraction
    |
    v
request<T>()  <-- core engine: auth, timeout, abort, errors
    |
    v
fetch()  <-- browser native
```

### Alternatives Considered

- **Axios**: Popular HTTP client with interceptors. We chose native `fetch` because: (1) Next.js has built-in fetch extensions, (2) Axios adds 13KB to the bundle for features we do not need (progress events, XSRF), and (3) AbortController works natively with fetch but requires extra wiring with Axios.
- **ky / wretch**: Lightweight fetch wrappers. Reasonable choices, but our needs are simple enough that a 50-line `request<T>` function covers everything without adding a dependency.
- **tRPC**: Would give end-to-end type safety from backend to frontend. But it requires a tRPC backend -- our backend is a standard FastAPI REST server. The migration cost is not justified.

---

## How It Works In Our App

### The Core: `request<T>()`

This is the heart of the API client. Every HTTP call flows through here:

```ts
// src/lib/api.ts

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";
const REQUEST_TIMEOUT_MS = 60_000;

function headers(): HeadersInit {
  return {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
  };
}

async function request<T>(
  method: string,
  path: string,
  options?: { params?: Record<string, string | number>; body?: unknown; signal?: AbortSignal },
): Promise<T> {
  let url = `${API_BASE}${path}`;

  if (options?.params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(options.params)) {
      searchParams.set(key, String(value));
    }
    url += `?${searchParams.toString()}`;
  }

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
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    return response.json();
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      if (options?.signal?.aborted) throw err; // External cancellation -- let React Query handle silently
      throw new Error("Request timed out");
    }
    if (err instanceof TypeError) {
      throw new Error("Cannot reach the API server -- is the backend running?");
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
    options?.signal?.removeEventListener("abort", onExternalAbort);
  }
}
```

Let's examine each concern this function handles.

### 1. TypeScript Generics: `request<T>()`

The function signature `request<T>(...): Promise<T>` is a generic function. The type parameter `T` represents the shape of the JSON response. When a caller specifies `T`, TypeScript ensures the return type matches:

```ts
// This tells TypeScript: "the server will return an OverviewStats object"
function getOverviewStats(profileId: number, signal?: AbortSignal): Promise<OverviewStats> {
  return get("/api/overview/stats", { profile_id: profileId }, signal);
}
```

The generic flows through the chain:
- `getOverviewStats` calls `get<OverviewStats>` (inferred from the return type)
- `get` calls `request<OverviewStats>`
- `request` returns `response.json()` which TypeScript trusts to be `OverviewStats`

This means that in the page component:

```tsx
const { data } = useQuery({
  queryKey: queryKeys.overview(profileId),
  queryFn: ({ signal }) => getOverviewStats(profileId, signal),
});
// data is typed as OverviewStats | undefined -- full autocomplete on data.today_jobs, etc.
```

No type casting, no `as unknown`, no runtime validation needed for the happy path.

### 2. Timeout Handling: 60-Second AbortController

```ts
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
```

Every request gets a 60-second timeout. Why 60 seconds?

- This app has an LLM analysis pipeline. When the pipeline runs, some API calls (fetching status, polling for results) can take 30-40 seconds as the backend processes jobs through GPT-4.
- A 10-second timeout would kill legitimate long-running requests.
- A 60-second timeout covers the worst case while still preventing infinite hangs.

Why not rely on the browser's built-in timeout?

- **There is no standard browser fetch timeout.** The Fetch API has no `timeout` option. Some browsers might time out after 2 minutes, others after 5, and there's no consistency across Chrome/Firefox/Safari.
- By using our own AbortController + setTimeout, we get **deterministic, cross-browser timeout behavior**: exactly 60 seconds, every time, on every browser.

The `finally` block ensures the timeout is always cleared, preventing memory leaks:

```ts
finally {
  clearTimeout(timeoutId);
  options?.signal?.removeEventListener("abort", onExternalAbort);
}
```

### 3. Dual AbortSignal Linking

This is the most subtle piece of the API client:

```ts
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

const onExternalAbort = () => controller.abort();
options?.signal?.addEventListener("abort", onExternalAbort);
```

There are TWO reasons a request should be cancelled:

1. **Timeout**: Our internal timer fires after 60 seconds.
2. **External cancellation**: React Query aborts the signal when the user navigates away or the query key changes.

Both need to abort the same `fetch` call. We achieve this by:
- Creating an internal `AbortController` that controls the actual `fetch`.
- Linking the external signal to the internal controller via an event listener.
- When either source aborts, the internal controller.abort() is called, cancelling the fetch.

In the error handler, we distinguish which abort occurred:

```ts
if (err instanceof DOMException && err.name === "AbortError") {
  if (options?.signal?.aborted) throw err;  // External -- let React Query handle silently
  throw new Error("Request timed out");     // Timeout -- show user-facing error
}
```

If the external signal is aborted (React Query did it), we re-throw the DOMException. React Query recognizes this as a cancellation and silently ignores it -- no error toast, no error state.

If the external signal is NOT aborted but we got an AbortError, it must be our timeout. We throw a human-readable "Request timed out" message that the page will display.

### 4. Auth Header Injection

```ts
function headers(): HeadersInit {
  return {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
  };
}
```

Every request automatically includes the `X-API-Key` header. No page component ever needs to know about authentication. If the auth scheme changes tomorrow (e.g., switching from API key to JWT Bearer tokens), we change one function in one file.

The API key comes from `NEXT_PUBLIC_API_KEY` environment variable, loaded at build time. The `NEXT_PUBLIC_` prefix makes it available in client-side code (Next.js convention).

### 5. Error Categorization

The `catch` block handles three distinct error categories:

```ts
catch (err) {
  // 1. AbortError (DOMException) -- request was cancelled
  if (err instanceof DOMException && err.name === "AbortError") {
    if (options?.signal?.aborted) throw err;  // External cancel (React Query)
    throw new Error("Request timed out");     // Our timeout
  }

  // 2. TypeError -- network is unreachable
  if (err instanceof TypeError) {
    throw new Error("Cannot reach the API server -- is the backend running?");
  }

  // 3. Everything else -- HTTP errors from the server
  throw err;
}
```

Why does distinguishing these matter for UX?

| Error Type | Cause | User Message | What the User Should Do |
|---|---|---|---|
| `DOMException` (external) | Navigation / filter change | *Nothing* -- silently swallowed | Nothing -- this is expected behavior |
| `DOMException` (timeout) | Server took > 60s | "Request timed out" | Wait and retry, or check if backend is under load |
| `TypeError` | Network down, CORS, DNS failure | "Cannot reach the API server" | Check if the backend is running |
| HTTP 4xx/5xx | Server returned an error | Error detail from JSON body | Fix the request or report a bug |

Without this categorization, the user would see "Failed to fetch" for both network failures and timeouts, which is unhelpful.

And HTTP errors are handled before the catch block:

```ts
if (!response.ok) {
  const error = await response.json().catch(() => ({ detail: "Unknown error" }));
  throw new Error(error.detail || `API error: ${response.status}`);
}
```

The `.catch(() => ({ detail: "Unknown error" }))` is a safety net: if the server returns a non-JSON error body (e.g., an HTML 502 page from a reverse proxy), we do not crash trying to parse it.

### 6. URL Construction

```ts
let url = `${API_BASE}${path}`;

if (options?.params) {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(options.params)) {
    searchParams.set(key, String(value));
  }
  url += `?${searchParams.toString()}`;
}
```

This pattern is deliberately simple:

- `API_BASE` is the server root: `http://localhost:8000`
- `path` is the route: `/api/applications`
- `params` become query string: `?profile_id=1&min_score=0&max_score=100`

The result is always: `http://localhost:8000/api/applications?profile_id=1&min_score=0&max_score=100`

Using `URLSearchParams` automatically handles encoding special characters. `String(value)` converts numbers to strings (URLSearchParams only accepts strings).

The final URL is clean, readable, and easy to debug -- you can copy it from the Network tab and paste it into a browser or curl.

### 7. The `getWithCount<T>()` Pattern

Some API endpoints return paginated data with the total count in a response header. `getWithCount` reads this header:

```ts
// src/lib/api.ts

async function getWithCount<T>(
  path: string,
  params?: Record<string, string | number>,
  signal?: AbortSignal,
): Promise<PaginatedResult<T>> {
  // ... same URL construction and fetch logic ...

  const totalCount = parseInt(response.headers.get("X-Total-Count") || "0", 10);
  const data = await response.json();
  return { data, totalCount };
}
```

Where `PaginatedResult` is:

```ts
// src/lib/types.ts
export interface PaginatedResult<T> {
  data: T;
  totalCount: number;
}
```

Why use a header instead of a wrapper object in the body?

- **Backward compatibility** -- The JSON body contains a clean array of items. Clients that don't need pagination can ignore the header.
- **Standard practice** -- `X-Total-Count` is a widely recognized convention (used by json-server, Strapi, and many REST APIs).
- **Separation of concerns** -- The data payload is pure domain data. Pagination metadata lives in transport-layer headers where it belongs.

Five endpoints use `getWithCount`: applications, email queue, tracker data, startup profiles, and recent pipeline runs.

### 8. Why Mutations Don't Take AbortSignal

Look at the mutation helper functions:

```ts
function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>("POST", path, { body });
}

function put<T>(path: string, body?: unknown): Promise<T> {
  return request<T>("PUT", path, { body });
}

function del<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  return request<T>("DELETE", path, { params });
}
```

Notice: **no `signal` parameter**. Compare with the `get` helper:

```ts
function get<T>(path: string, params?: Record<string, string | number>, signal?: AbortSignal): Promise<T> {
  return request<T>("GET", path, { params, signal });
}
```

This is intentional. GET requests (reads) should be cancellable -- if the user navigates away, there is no point in completing a read that nobody will see. But POST/PUT/DELETE requests (writes) should **always complete**:

- If you navigate away while a delete is in-flight and the request is aborted, the email is half-deleted on the server. The user thinks it is gone (optimistic update removed it) but the server never processed the delete.
- If you abort a PUT while editing, the edit might be partially applied on the server (some databases and APIs are not transactional at this level).

By not passing the AbortSignal, mutations survive navigation. They still have the 60-second timeout (from the internal AbortController), but they cannot be cancelled by React Query's navigation-based abort.

### 9. The Full Export Surface

The file exports 24 domain-specific functions, organized by feature:

```ts
// Overview
export function getOverviewStats(profileId: number, signal?: AbortSignal): Promise<OverviewStats>

// Applications (3 functions)
export function getApplications(profileId: number, filters: ..., signal?: AbortSignal): Promise<PaginatedResult<Application[]>>
export function getSources(profileId: number, signal?: AbortSignal): Promise<string[]>

// Email Queue (7 functions)
export function getEmailQueue(...): Promise<PaginatedResult<EmailQueueItem[]>>
export function getEmailById(emailId: number, signal?: AbortSignal): Promise<EmailQueueItem>
export function getEmailStatuses(...): Promise<EmailStatusCounts>
export function getEmailSources(...): Promise<string[]>
export function updateEmailContent(...): Promise<{ status: string }>
export function deleteEmail(emailId: number): Promise<{ status: string }>
export function deleteAllEmails(profileId: number): Promise<{ deleted: number }>
export function sendEmail(emailId: number): Promise<{ status: string; email_id: number; to: string }>

// Outcomes (3 functions)
export function getApplicationsForUpdate(...): Promise<ApplicationForUpdate[]>
export function getAnalyzedJobsForUpdate(...): Promise<AnalyzedJobForUpdate[]>
export function updateApplicationOutcome(...): Promise<{ status: string }>
export function createApplication(...): Promise<{ status: string }>

// Analytics (6 functions)
export function getDailyTrends(...): Promise<DailyTrend[]>
export function getScoreDistribution(...): Promise<ScoreDistribution[]>
export function getSourceBreakdown(...): Promise<SourceBreakdown[]>
export function getCompanyTypes(...): Promise<CompanyType[]>
export function getResponseRates(...): Promise<ResponseRate[]>
export function getRouteBreakdown(...): Promise<RouteBreakdown>

// Tracker (3 functions)
export function getTrackerData(...): Promise<PaginatedResult<TrackerRow[]>>
export function upsertApplication(...): Promise<{ status: string }>
export function markJobObsolete(jobId: number): Promise<{ status: string; is_obsolete: boolean }>

// Jobs (2 functions)
export function checkJobLink(jobId: number, signal?: AbortSignal): Promise<{ ... }>

// Startup Profiles (3 functions)
export function getStartupProfiles(...): Promise<PaginatedResult<StartupProfile[]>>
export function getStartupProfileStats(...): Promise<StartupProfileStats>
export function getStartupProfileSources(...): Promise<string[]>

// Pipeline (4 functions)
export function runMainPipeline(source: string, limit: number): Promise<PipelineRunResponse>
export function runStartupScout(source: string, limit: number): Promise<PipelineRunResponse>
export function getPipelineRunStatus(runId: string): Promise<PipelineStatusResponse>
export function getRecentPipelineRuns(...): Promise<PipelineStatusResponse[]>
```

Every function:
- Has explicit TypeScript input and return types (no `any`).
- Accepts `signal` on reads, omits it on writes.
- Delegates to the appropriate helper (`get`, `getWithCount`, `post`, `put`, `del`).
- Handles parameter mapping (e.g., converting `ApplicationFilters` to the flat `Record<string, string | number>` that the helper expects).

### 10. How Export Functions Map Parameters

The export functions serve as an adapter layer between TypeScript domain types and the raw API query parameters:

```ts
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

The `??` (nullish coalescing) operators provide defaults for optional fields. This means the caller can pass `{}` and get sensible defaults for every filter. The page component does not need to worry about which defaults the API expects.

---

## The Key Insight

The API client is a **boundary layer**. On one side is the messy, untyped world of HTTP: string URLs, header objects, status codes, JSON parsing. On the other side is the clean, typed world of React components: `Application[]`, `EmailQueueItem`, `OverviewStats`.

The `request<T>()` function is the bridge. It accepts the mess and returns the clean types. Every concern that touches HTTP -- auth, timeouts, abort signals, error parsing, URL construction -- is contained within this one file. If you need to change how the app talks to the server (different auth scheme, different base URL, adding request logging), you change one file and zero pages.

---

## Interview Talking Points

- "All network logic lives in one file: `api.ts`. It exports 24 domain-specific functions, but they all flow through a single generic `request<T>()` function that handles auth, timeout, abort, and error categorization."

- "The `request<T>()` generic ensures type safety from API to component. When `getOverviewStats` returns `Promise<OverviewStats>`, React Query's `data` is automatically typed as `OverviewStats`. No casting, no runtime validation."

- "We use a 60-second timeout via AbortController because the app has LLM-powered analysis that can take 30-40 seconds. A 10-second timeout would kill legitimate requests. We cannot rely on browser timeouts because there is no standard -- Chrome, Firefox, and Safari all behave differently."

- "The dual AbortSignal pattern links React Query's external signal to our internal AbortController. External aborts (navigation) are re-thrown as DOMExceptions that React Query silently ignores. Timeout aborts are converted to user-friendly 'Request timed out' messages. This distinction is critical for UX."

- "Mutation functions (`post`, `put`, `del`) deliberately omit the AbortSignal parameter. A write should always complete -- you do not want a half-deleted email because the user navigated away. Only reads (`get`, `getWithCount`) are cancellable."

- "Error categorization distinguishes three failure modes: DOMException (abort/timeout), TypeError (network unreachable), and HTTP errors (4xx/5xx from the server). Each gets a different user-facing message. Without this, the user would see 'Failed to fetch' for every error, which is useless."

- "`getWithCount<T>()` reads the `X-Total-Count` header for pagination. This keeps the JSON body clean (just an array of items) while providing total count metadata in the transport layer. It is a common REST convention used by json-server, Strapi, and many production APIs."

- "The export functions act as an adapter layer: they convert TypeScript domain types (`ApplicationFilters`) into flat query parameter records, providing sensible defaults with `??` for every optional field. The page component never thinks about URL encoding or default parameter values."
