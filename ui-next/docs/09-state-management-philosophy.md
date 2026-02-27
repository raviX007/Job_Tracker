# 09 - State Management Philosophy (Why No Redux)

## What Is This?

State management is arguably the most debated topic in React development. Every team
faces the question: "Should we use Redux? Zustand? MobX? Jotai? Context? Just
`useState`?" This document explains the reasoning behind our choice, which is:
**no state management library at all**. We use React Query for server state, `useState`
for local client state, and React Context for the one piece of shared state we have.

This is not a compromise -- it is a deliberate architectural decision based on
understanding what each type of state actually needs.

---

## Why We Chose This Approach

### The 3 Types of State in Any React App

Before picking a tool, you need to classify your state. Every piece of state in a React
application falls into one of three categories:

| Type | Definition | Examples in our app | Characteristics |
|---|---|---|---|
| **Server state** | Data that lives on the backend and is fetched over the network | Applications, emails, tracker rows, analytics data, overview stats | Asynchronous, cacheable, shared across pages, can become stale |
| **Client state** | UI-only state that exists purely in the browser | Filter values, form inputs, expanded/collapsed flags, current page number | Synchronous, local, user-controlled, never sent to the server |
| **Shared state** | Client state that multiple unrelated components need to read | `profileId` (used by every page to scope API calls) | Needs a distribution mechanism (Context, global store, URL) |

This classification is the foundation of our entire state strategy.

---

### How We Handle Each Type

#### 1. Server State --> React Query

React Query IS our server state manager. Every piece of data from the API flows through
`useQuery` or `useMutation`:

```typescript
// Overview page -- reads 3 endpoints in parallel
const { data: queryData, isLoading: loading } = useQuery({
  queryKey: queryKeys.overview(profileId),
  queryFn: async ({ signal }) => {
    const [stats, trendData, topResult] = await Promise.all([
      getOverviewStats(profileId, signal),
      getDailyTrends(profileId, 7, signal),
      getApplications(profileId, { min_score: 70, decision: "YES", limit: 6 }, signal),
    ]);
    return { stats, trends: trendData, topMatches: topResult.data };
  },
});
```

React Query gives us for free:
- **Caching** -- If you navigate away and back, the cached data shows instantly while a
  background refetch runs
- **Request deduplication** -- If 3 components request the same query key, only 1 network
  request fires
- **Background refetching** -- Stale data is automatically refreshed (configured via
  `staleTime: 30_000` in our providers)
- **Loading / error / success states** -- No manual `isLoading` + `error` + `data` state
  management
- **Automatic retry** -- Failed requests retry once (`retry: 1` in our config)
- **Request cancellation** -- When a component unmounts or query key changes, in-flight
  requests are cancelled via `AbortSignal`

If we had used Redux for server state, we would need to manually implement ALL of the
above. That is exactly what the React community did before React Query existed, and it
led to thousands of lines of reducer/saga/thunk boilerplate that was buggy and hard to
maintain.

#### 2. Client State --> `useState`

Every piece of UI-only state is a simple `useState` call in the component that owns it:

```typescript
// Applications page -- filter state
const [minScore, setMinScore] = useState(0);
const [maxScore, setMaxScore] = useState(100);
const [decision, setDecision] = useState("All");
const [source, setSource] = useState("All");
const [search, setSearch] = useState("");
const [page, setPage] = useState(1);
const [view, setView] = useState<string>("cards");
```

These values are local to the Applications page. No other page needs to know what
filters are active on the Applications page. Therefore, they live where they are used.

#### 3. Shared State --> React Context

We have exactly ONE piece of shared state: `profileId`. It is used by every page to
scope API calls to the current user profile.

```typescript
// From src/hooks/use-profile.tsx
export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileIdState] = useState<number>(1);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = parseInt(stored, 10);
      if (!isNaN(parsed) && parsed > 0) setProfileIdState(parsed);
    }
  }, []);

  const setProfileId = useCallback((id: number) => {
    setProfileIdState(id);
    localStorage.setItem(STORAGE_KEY, String(id));
  }, []);

  return (
    <ProfileContext.Provider value={{ profileId, setProfileId }}>
      {children}
    </ProfileContext.Provider>
  );
}
```

Every page consumes it the same way:

```typescript
const { profileId } = useProfile();
```

One context. One hook. One piece of state. That is all the "global state" we need.

---

## Why Redux / Zustand Would Be Overkill

### What Redux adds to a project

To use Redux properly, you need:

1. **Store** -- A centralized state container
2. **Reducers** -- Pure functions that describe state transitions
3. **Actions** -- Objects that describe what happened
4. **Selectors** -- Functions to extract specific data from the store
5. **Middleware** -- For async operations (redux-thunk, redux-saga)

That is 5 new concepts, 5 new file patterns, and a significant learning curve.

### What would Redux actually manage in our app?

Let's go through the possibilities:

| State | Do we need Redux for this? | Why not? |
|---|---|---|
| Applications list | No | React Query already caches it |
| Email queue | No | React Query already caches it |
| Tracker rows | No | React Query already caches it |
| Analytics data | No | React Query already caches it |
| Filter values | No | Local to each page, `useState` is sufficient |
| Form state | No | Local to each page |
| profileId | No | One value, React Context handles it |

**There is literally nothing left for Redux to manage.** The server state is handled by
React Query's cache (which IS a global store -- just one specialized for server state).
The client state is local. The shared state is one value in Context.

### Zustand as a lighter alternative

Zustand is often recommended as a "Redux alternative" with less boilerplate. It is a good
library, but it solves the same problem: sharing client state across components. Since we
only have one piece of shared client state (`profileId`), even Zustand would be adding a
dependency for something React Context already handles natively.

---

## The "Server State Is Not Client State" Insight

This is the most important concept in this document.

**Before React Query existed** (pre-2020), the standard pattern was:

```typescript
// The old way (DO NOT do this)
// 1. Create Redux action
const FETCH_APPLICATIONS = "FETCH_APPLICATIONS";
const FETCH_APPLICATIONS_SUCCESS = "FETCH_APPLICATIONS_SUCCESS";
const FETCH_APPLICATIONS_ERROR = "FETCH_APPLICATIONS_ERROR";

// 2. Create Redux reducer
function applicationsReducer(state, action) {
  switch (action.type) {
    case FETCH_APPLICATIONS: return { ...state, loading: true };
    case FETCH_APPLICATIONS_SUCCESS: return { ...state, loading: false, data: action.payload };
    case FETCH_APPLICATIONS_ERROR: return { ...state, loading: false, error: action.payload };
  }
}

// 3. Create async thunk
function fetchApplications() {
  return async (dispatch) => {
    dispatch({ type: FETCH_APPLICATIONS });
    try {
      const data = await api.getApplications();
      dispatch({ type: FETCH_APPLICATIONS_SUCCESS, payload: data });
    } catch (err) {
      dispatch({ type: FETCH_APPLICATIONS_ERROR, payload: err.message });
    }
  };
}
```

This approach treats API data as if it were client state -- something the frontend
"owns" and manages. But API data is fundamentally different:

| Client state | Server state |
|---|---|
| Created by the user (typing, clicking) | Created by the server (database) |
| The frontend is the source of truth | The backend is the source of truth |
| Never "stale" -- the user just set it | Can become stale immediately after fetch |
| Does not need syncing | Needs constant syncing with the server |
| Does not need caching | Benefits enormously from caching |
| No concept of "loading" or "error" | Always has loading/error/success states |

React Query treats server state as **a cache that needs syncing with a remote source**.
This is fundamentally different from Redux treating it as "data the frontend owns." The
result: React Query handles caching, deduplication, background refetching, stale-while-
revalidate, and error retry out of the box. Redux handles none of these without
significant custom code.

---

## State Colocation Principle

**State should live as close to where it is used as possible.**

This principle drives our entire architecture. Here is the actual state in each page:

### Overview Page (`src/app/overview/page.tsx`)

```
useState calls: 0
```

Everything comes from React Query. The overview page is **pure presentation** -- it
fetches data and renders it. No filters, no forms, no user interactions that need state.

### Applications Page (`src/app/applications/page.tsx`)

```typescript
const [minScore, setMinScore] = useState(0);        // filter
const [maxScore, setMaxScore] = useState(100);       // filter
const [decision, setDecision] = useState("All");     // filter
const [source, setSource] = useState("All");         // filter
const [search, setSearch] = useState("");             // filter
const [page, setPage] = useState(1);                 // pagination
const [view, setView] = useState<string>("cards");   // UI toggle
```

**7 useState calls** (including `expanded` in each `ApplicationCard` child component).
All are filter/pagination/UI state -- local to this page. No other page cares about what
score range the user selected here.

### Emails Page (`src/app/emails/page.tsx`)

```typescript
const [filterStatus, setFilterStatus] = useState("All");           // filter
const [filterSource, setFilterSource] = useState("All");           // filter
const [page, setPage] = useState(1);                               // pagination
const [editingId, setEditingId] = useState<number | null>(null);   // edit state
const [editSubject, setEditSubject] = useState("");                // edit state
const [editBody, setEditBody] = useState("");                      // edit state
const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set()); // UI
const [deleteDialogId, setDeleteDialogId] = useState<number | null>(null); // UI
const [deleteAllDialogOpen, setDeleteAllDialogOpen] = useState(false);     // UI
const [successMsg, setSuccessMsg] = useState<string | null>(null);         // flash
```

**10 useState calls.** This is the most stateful page -- it handles inline editing,
expansion toggles, confirmation dialogs, and success notifications. All of this is
specific to the email queue interface. Moving any of this to a global store would add
complexity for zero benefit.

### Tracker Page (`src/app/tracker/page.tsx`)

```typescript
const [showObsolete, setShowObsolete] = useState(false);              // filter
const [edits, setEdits] = useState<Record<number, RowEdits>>({});     // form state
const [savedRows, setSavedRows] = useState<Set<number>>(new Set());   // flash state
const [page, setPage] = useState(1);                                  // pagination
```

**4 useState calls.** The `edits` Record tracks in-progress form changes for each table
row, keyed by `job_id`. This is a perfect example of state that should NOT be global --
it is ephemeral form state that is discarded on navigation.

### Analytics Page (`src/app/analytics/page.tsx`)

```
useState calls: 0
```

Like Overview, this is pure presentation. Six charts, all data from React Query.

### Outcomes Page (`src/app/outcomes/page.tsx`)

```typescript
const [outcomeForms, setOutcomeForms] = useState<Record<number, OutcomeForm>>({});  // forms
const [savedAppId, setSavedAppId] = useState<number | null>(null);                  // flash
const [logForms, setLogForms] = useState<Record<number, LogForm>>({});              // forms
const [loggedJobId, setLoggedJobId] = useState<number | null>(null);                // flash
```

**4 useState calls.** Two sets of form state (for the "Update Existing" and "Log New"
tabs) plus two flash-state indicators.

### Startups Page (`src/app/startups/page.tsx`)

```typescript
const [filters, setFilters] = useState<Partial<StartupProfileFilters>>({
  source: "All",
  funding_round: "All",
  min_age: 0,
  max_age: 24,
  has_funding: "All",
  search: "",
  sort_by: "match_score",
  limit: 50,
  offset: 0,
});
const [page, setPage] = useState(1);
```

**2 useState calls.** The `filters` object bundles 9 filter values into a single state
object, which is a pattern we use when filters are numerous and change together.

### The pattern

| Page | useState count | Why |
|---|---|---|
| Overview | 0 | Pure display |
| Applications | 7 | Filters + view toggle |
| Emails | 10 | Filters + editing + dialogs + flash |
| Tracker | 4 | Edits + flash + filter + page |
| Analytics | 0 | Pure display |
| Outcomes | 4 | Forms + flash |
| Startups | 2 | Filters + page |

Notice: the two "dashboard" pages (Overview, Analytics) have zero state. The "interactive"
pages have more. This is the colocation principle at work -- state lives exactly where
the interaction happens.

---

## The "Good Enough" Principle

A common mistake is reaching for complex tools preemptively:

> "We might need global state later, so let's set up Redux now."

This violates YAGNI (You Ain't Gonna Need It). In practice:

1. We started with `useState` for everything
2. We noticed `profileId` was needed across all pages -- moved it to Context
3. We noticed API data management was painful (loading states, caching) -- added React
   Query
4. We have never needed anything more

If a future requirement demands shared client state (e.g., a theme preference, a
notification queue, a shopping cart), we would evaluate at that point. Context might still
be sufficient. If it is not, Zustand would be the first choice for its simplicity. Redux
would only be justified if we had complex state transitions with many interdependent
actions -- something our job tracker is unlikely to need.

**The decision tree:**

```
Is it data from the API?
  --> YES: React Query (useQuery / useMutation)
  --> NO: Is it used by multiple unrelated components?
    --> YES: React Context (if simple) or Zustand (if complex)
    --> NO: useState in the component that uses it
```

That is the entire state management strategy. Three questions, three tools, zero over-
engineering.

---

## How React Query's Cache Functions as a Global Store

A subtlety worth understanding: React Query's cache IS a global store. When the
Applications page fetches `getApplications(profileId, filters)`, the result is stored
in a cache keyed by `["applications", profileId, filters]`. If another component
somewhere in the tree uses the same query key, it reads from the cache instead of making
a new network request.

The `QueryClientProvider` in `src/components/providers.tsx` makes this cache available
to the entire app:

```typescript
export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,   // Data is "fresh" for 30 seconds
            retry: 1,            // Retry failed requests once
            refetchOnWindowFocus: false, // Don't refetch when tab regains focus
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
```

This is functionally equivalent to a Redux store, but specialized:
- Instead of `dispatch(fetchApplications())`, you write `useQuery({ queryKey, queryFn })`
- Instead of a reducer, React Query manages loading/error/success transitions internally
- Instead of manual cache invalidation, React Query provides `invalidateQueries()` with
  smart matching
- Instead of `useSelector(selectApplications)`, you write `useQuery()` and destructure the
  result

The mental model shift: **you are not storing server data in a client store -- you are
maintaining a cache that React Query keeps in sync with the server.**

---

## The Key Insight

The question "should we use Redux?" is the wrong question. The right question is "what
types of state do we have, and what does each type need?" Server state needs caching,
deduplication, and background syncing -- React Query handles this. Client state needs to
be local and fast -- `useState` handles this. Shared state needs distribution -- Context
handles this (for our scale). When you classify state correctly, the tool choice becomes
obvious, and the answer is almost never "one global store for everything."

---

## Interview Talking Points

- "We classify state into three types: server state (API data), client state (UI-only),
  and shared state (cross-component). Each type has different needs, so each type gets a
  different tool."

- "React Query is our server state manager. It handles caching, deduplication, background
  refetching, loading/error states, and request cancellation -- things Redux would require
  hundreds of lines of custom code to replicate."

- "We use `useState` for client state because it is local, synchronous, and simple. Filter
  values, form inputs, and toggle states do not need to be global."

- "Our only shared state is `profileId`, which lives in React Context. One context, one
  hook, zero external dependencies. Redux would add 5 new concepts (store, reducers,
  actions, selectors, middleware) for this single value."

- "The state colocation principle says state should live as close to where it is used as
  possible. Our Overview and Analytics pages have zero `useState` calls -- they are pure
  presentation layers over React Query. The Emails page has 10 -- because that is where
  the editing interactions happen."

- "Before React Query, people put API data in Redux. This treated server data as client
  state, leading to stale data bugs, no request deduplication, and manual cache
  invalidation. React Query fixes this by treating server data as a cache that needs
  syncing with a remote source."

- "We follow YAGNI -- we started with `useState`, extracted `profileId` to Context when
  we saw prop drilling, and added React Query when we needed caching. We have never
  needed anything more. If we did, Zustand would be the next step, not Redux."

- "React Query's `QueryClientProvider` IS effectively a global store -- it caches all
  fetched data and makes it available to any component. The difference from Redux is that
  it is specialized for server state: it knows about staleness, refetching, and request
  lifecycle."
