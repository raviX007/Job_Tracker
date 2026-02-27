# 08 - TypeScript Patterns

## What Is This?

TypeScript is a typed superset of JavaScript that catches bugs at **compile time** rather
than at runtime. In our project, every file is `.ts` or `.tsx` -- there is zero plain
JavaScript. This document covers the specific TypeScript patterns we use, why each one
matters, and how they connect together to form a type-safe data pipeline from the API
layer all the way to the UI.

---

## Why We Chose This Approach

### Alternatives considered

| Approach | Why we rejected it |
|---|---|
| **Plain JavaScript + JSDoc** | JSDoc comments provide some editor hints, but they are not enforced at build time. A wrong field name slips through silently. |
| **TypeScript with `strict: false`** | Defeats the purpose. Without strict mode, `null` and `undefined` flow through unchecked, which is the #1 source of runtime crashes. |
| **Runtime validation (Zod / Yup) only** | Good for API boundaries, but adds bundle size and does not help with internal type safety between components. We get 90% of the benefit from TypeScript alone. |

---

## How It Works In Our App

### 1. Strict Mode

From `tsconfig.json`:

```json
{
  "compilerOptions": {
    "strict": true,
    // ...
  }
}
```

The `"strict": true` flag is a shorthand that enables all of these individual checks:

| Flag | What it catches |
|---|---|
| `noImplicitAny` | You cannot have a variable with an inferred `any` type. Forces explicit typing. |
| `strictNullChecks` | `string` and `string | null` are different types. You must check for `null` before using. |
| `strictFunctionTypes` | Catches contravariance bugs in function parameter types. |
| `strictBindCallApply` | Ensures `bind`, `call`, `apply` have correct argument types. |
| `strictPropertyInitialization` | Class properties must be initialized or declared `undefined`. |
| `noImplicitThis` | `this` must have a known type -- no accidental global `this`. |
| `alwaysStrict` | Emits `"use strict"` in every file. |

**Why it matters:** Without strict mode, a function that returns `Application | null`
would be treated as always returning `Application`. The first time the API returns
`null`, the app crashes with `Cannot read property 'company' of null`. With strict mode,
TypeScript forces you to handle the `null` case at compile time.

---

### 2. Generic API Functions

From `src/lib/api.ts`, the core `request` function:

```typescript
async function request<T>(
  method: string,
  path: string,
  options?: {
    params?: Record<string, string | number>;
    body?: unknown;
    signal?: AbortSignal;
  },
): Promise<T> {
  // ... fetch logic ...
  return response.json();
}
```

And the public `get` wrapper:

```typescript
function get<T>(
  path: string,
  params?: Record<string, string | number>,
  signal?: AbortSignal,
): Promise<T> {
  return request<T>("GET", path, { params, signal });
}
```

#### How the generic flows

When a page calls the API, the generic `<T>` tells TypeScript what shape the response
will have:

```typescript
// In api.ts -- the caller specifies T = OverviewStats
export function getOverviewStats(
  profileId: number,
  signal?: AbortSignal,
): Promise<OverviewStats> {
  return get("/api/overview/stats", { profile_id: profileId }, signal);
}
```

Now when the Overview page calls `getOverviewStats(profileId, signal)`, TypeScript knows
the result is `OverviewStats`, and the page gets full autocomplete on fields like
`data.today_jobs`, `data.total_analyzed`, `data.avg_score`.

If the backend renames `today_jobs` to `jobs_today`, TypeScript will immediately flag
every place in the frontend that references the old name -- at build time, not after
deployment.

#### The error handling pattern

```typescript
} catch (err) {
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

This uses **type narrowing** in catch blocks. TypeScript's `catch (err)` gives `err` the
type `unknown` in strict mode. The `instanceof` checks narrow it to specific error types,
giving us access to `.name` and `.message` properties safely.

---

### 3. `PaginatedResult<T>` -- A Generic Wrapper

From `src/lib/types.ts`:

```typescript
export interface PaginatedResult<T> {
  data: T;
  totalCount: number;
}
```

This single interface serves every paginated endpoint in the app:

```typescript
// Applications page
Promise<PaginatedResult<Application[]>>

// Email queue page
Promise<PaginatedResult<EmailQueueItem[]>>

// Tracker page
Promise<PaginatedResult<TrackerRow[]>>

// Startups page
Promise<PaginatedResult<StartupProfile[]>>
```

**Why this matters:** Without the generic, we would need four separate interfaces:
`PaginatedApplications`, `PaginatedEmails`, `PaginatedTrackerRows`,
`PaginatedStartups` -- all with the same `data` + `totalCount` shape. The generic
eliminates that duplication while preserving full type safety. When you access
`result.data[0]`, TypeScript knows it is an `Application`, not a generic object.

The `getWithCount` function in `api.ts` shows how this generic flows through the API
layer:

```typescript
async function getWithCount<T>(
  path: string,
  params?: Record<string, string | number>,
  signal?: AbortSignal,
): Promise<PaginatedResult<T>> {
  // ...
  const totalCount = parseInt(
    response.headers.get("X-Total-Count") || "0",
    10,
  );
  const data = await response.json();
  return { data, totalCount };
}
```

---

### 4. Query Key Factory with `as const`

From `src/lib/query-keys.ts`:

```typescript
export const queryKeys = {
  overview: (pid: number) => ["overview", pid] as const,
  dailyTrends: (pid: number, days: number) =>
    ["dailyTrends", pid, days] as const,
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

#### What `as const` does

Without `as const`:

```typescript
// Return type: (string | number)[]
const key = ["applications", 1, { search: "react" }];
```

With `as const`:

```typescript
// Return type: readonly ["applications", number, Record<string, unknown>]
const key = ["applications", 1, { search: "react" }] as const;
```

The difference is crucial for React Query. With `as const`:
- TypeScript knows position `[0]` is always the literal string `"applications"`
- TypeScript can distinguish `queryKeys.applications()` from `queryKeys.emails()` at the
  type level
- When you invalidate queries with `queryClient.invalidateQueries({ queryKey: queryKeys.emails(profileId, filterStatus, filterSource) })`,
  TypeScript ensures you pass the right number and types of arguments

Without `as const`, all query keys would have type `(string | number | Record<string, unknown>)[]`
and TypeScript could not catch mismatches.

---

### 5. Interface vs Type

We follow a consistent convention:

**`interface`** for data shapes -- things that represent objects from the API:

```typescript
export interface Application {
  job_id: number;
  title: string;
  company: string;
  location: string | null;
  source: string;
  is_remote: boolean;
  match_score: number;
  apply_decision: string;
  skills_matched: string[];
  skills_missing: string[];
  // ... more fields
}

export interface TrackerRow {
  job_id: number;
  app_id: number | null;
  company: string;
  title: string;
  // ...
}
```

**`type`** for unions, computed types, and aliases:

```typescript
// Index signature type for dynamic shapes
export interface EmailStatusCounts {
  [status: string]: number;
}

// Route breakdown uses the same pattern
export interface RouteBreakdown {
  [route: string]: number;
}
```

**Why `interface` for data shapes?** Interfaces are extendable with `extends`. If we
later need `ApplicationWithEmails`, we can do:

```typescript
interface ApplicationWithEmails extends Application {
  emails: EmailQueueItem[];
}
```

This is not possible with `type` intersection without creating a brand-new type.

---

### 6. Discriminated Patterns in Utility Functions

From `src/lib/utils.ts`:

```typescript
export function scoreBadgeColor(score: number): string {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-teal-500";
  if (score >= 40) return "bg-amber-500";
  return "bg-red-500";
}

export function decisionColor(decision: string): string {
  switch (decision) {
    case "YES": return "bg-emerald-500 text-white";
    case "MAYBE": return "bg-amber-500 text-white";
    case "MANUAL": return "bg-purple-500 text-white";
    case "NO": return "bg-red-500 text-white";
    default: return "bg-gray-400 text-white";
  }
}

export function statusColor(status: string): string {
  switch (status) {
    case "draft": return "bg-gray-400 text-white";
    case "verified": return "bg-blue-500 text-white";
    case "ready": return "bg-teal-500 text-white";
    case "queued": return "bg-amber-500 text-white";
    case "sent": case "delivered": return "bg-emerald-500 text-white";
    case "bounced": case "failed": return "bg-red-500 text-white";
    default: return "bg-gray-400 text-white";
  }
}
```

Each function is the **single source of truth** for its mapping. Every page that shows a
score badge calls `scoreBadgeColor()`. If we decide "80+" should be blue instead of
green, we change one line in one file, and every score badge across 7 pages updates.

The return type `string` here represents Tailwind CSS classes. TypeScript ensures these
functions always return a string, and the `default` cases ensure no input can slip
through without a color.

---

### 7. ButtonProps -- `extends` + `VariantProps` Pattern

From `src/components/ui/button.tsx`:

```typescript
export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}
```

This is an intersection of three things:

1. **`React.ButtonHTMLAttributes<HTMLButtonElement>`** -- All native button attributes:
   `onClick`, `disabled`, `type`, `className`, `aria-label`, etc.
2. **`VariantProps<typeof buttonVariants>`** -- Variant-specific props extracted from the
   CVA definition: `variant` (default, destructive, outline, secondary, ghost, link,
   accent) and `size` (default, sm, lg, icon)
3. **`{ asChild?: boolean }`** -- Our custom prop for the polymorphic component pattern

The result: a single `ButtonProps` type that accepts native HTML button attributes
AND our custom variant/size props AND the asChild flag, with full autocompletion and type
checking for all of them.

Usage in pages:

```typescript
// TypeScript knows all of these are valid props:
<Button
  variant="outline"       // from VariantProps
  size="sm"               // from VariantProps
  onClick={() => refetch()} // from ButtonHTMLAttributes
  disabled={isPending}    // from ButtonHTMLAttributes
  className="h-7"        // from ButtonHTMLAttributes
>
  Retry
</Button>
```

---

### 8. Record Types for Dynamic Shapes

We use `Record<K, V>` when the keys are not known at compile time:

```typescript
// Tracker page: form state keyed by job_id
const [edits, setEdits] = useState<Record<number, RowEdits>>({});

// Outcomes page: form state keyed by app_id
const [outcomeForms, setOutcomeForms] = useState<Record<number, OutcomeForm>>({});

// Email status counts from API
export interface EmailStatusCounts {
  [status: string]: number;  // equivalent to Record<string, number>
}

// Query parameters
params?: Record<string, string | number>
```

`Record<number, RowEdits>` says: "This is an object where any numeric key maps to a
`RowEdits` value." It is more precise than `any` or `object`, but flexible enough for
dynamic keys.

---

### 9. Common TypeScript Patterns Used Throughout

#### Optional chaining (`?.`)

```typescript
const matchedSlice = app.skills_matched?.slice(0, 5) ?? [];
const error = queryError?.message ?? null;
```

If `app.skills_matched` is `null` or `undefined`, the expression short-circuits to
`undefined` instead of throwing `Cannot read property 'slice' of null`.

#### Nullish coalescing (`??`)

```typescript
const applications = paginatedResult?.data ?? [];
const totalCount = paginatedResult?.totalCount ?? 0;
decision: filters.decision ?? "All",
```

`??` returns the right side only when the left side is `null` or `undefined` -- not for
`0`, `""`, or `false`. This is more precise than `||`, which would treat `0` as falsy.

#### Type narrowing in catch blocks

```typescript
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

In strict mode, `err` has type `unknown`. Each `instanceof` check narrows it to a more
specific type, letting us safely access `.name` and `.message`.

#### Const assertions for literal arrays

```typescript
export const DECISIONS = ["All", "YES", "MAYBE", "MANUAL", "NO"] as const;
export const EMAIL_STATUSES = [
  "All", "draft", "verified", "ready", "queued",
  "sent", "delivered", "bounced", "failed",
] as const;
```

Without `as const`, `DECISIONS` would have type `string[]`. With `as const`, it has type
`readonly ["All", "YES", "MAYBE", "MANUAL", "NO"]` -- a tuple of specific literal
strings. This means TypeScript can catch typos like `"YEs"` at compile time.

#### Generic function parameters in page components

From the Startups page:

```typescript
function updateFilter<K extends keyof StartupProfileFilters>(
  key: K,
  value: StartupProfileFilters[K],
) {
  setFilters((prev) => ({ ...prev, [key]: value }));
  setPage(1);
}
```

The generic `K extends keyof StartupProfileFilters` ensures that `key` must be a valid
field name from `StartupProfileFilters`, and `value` must match the type of that specific
field. Calling `updateFilter("source", 42)` would be a compile error because `source` is
a `string`, not a `number`.

---

## The Key Insight

TypeScript in this project is not just about preventing typos. It creates a **typed
pipeline** that flows from the API response type (`interface Application`) through the
API function (`get<Application[]>`) through the React Query cache through the component
props through the utility functions (`scoreBadgeColor(app.match_score)`) all the way to
the rendered JSX. At every step, TypeScript knows the exact shape of the data. If the
backend changes a field, the type breaks at the API boundary, and every downstream usage
is flagged. This is what "type safety" actually means in practice -- not just "no red
squiggles," but a compile-time guarantee that data flows correctly through the entire
application.

---

## Interview Talking Points

- "We use `strict: true` in tsconfig, which enables `strictNullChecks`,
  `noImplicitAny`, and other flags. This catches null-related bugs at compile time
  instead of runtime -- the #1 class of JavaScript errors."

- "Our API functions use generics like `get<T>(path): Promise<T>` so the caller
  specifies the expected response type. This gives full autocomplete and catches field
  name mismatches at build time."

- "`PaginatedResult<T>` is a single generic interface that wraps `data: T` and
  `totalCount: number`. It serves all four paginated endpoints without code duplication."

- "We use `as const` on query key arrays so TypeScript creates readonly tuple types
  instead of `string[]`. This lets React Query (and our code) distinguish between
  different query key shapes at the type level."

- "The `ButtonProps` type intersects native `HTMLButtonElement` attributes with CVA's
  `VariantProps`, giving us type-safe access to both `onClick`/`disabled` and
  `variant`/`size` in a single prop type."

- "We prefer `interface` for API data shapes because they are extendable with `extends`.
  We use `type` for unions and computed types. This is a project convention, not a hard
  rule -- but consistency matters."

- "`Record<number, RowEdits>` gives us type-safe dynamic objects where keys are not
  known at compile time, which is common for form state keyed by database IDs."

- "We use optional chaining `?.` and nullish coalescing `??` extensively. The key
  difference from `||` is that `??` only triggers on `null`/`undefined`, not on `0` or
  empty string, which prevents subtle bugs in numeric fields."
