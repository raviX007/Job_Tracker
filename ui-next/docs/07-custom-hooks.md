# 07 - Custom Hooks Philosophy

## What Is This?

Custom hooks are React's mechanism for extracting **reusable stateful logic** out of
components. They are regular JavaScript functions whose names start with `use` and that
may call other hooks (`useState`, `useEffect`, `useContext`, etc.) internally.

The key distinction: custom hooks share *logic*, not *state*. Two components that call
the same custom hook each get their own independent copy of whatever state lives inside
that hook. This is fundamentally different from a global store where everyone reads the
same value.

In our project we have exactly **two** custom hooks:

| Hook | File | Purpose |
|---|---|---|
| `useDebouncedValue` | `src/hooks/use-debounced-value.ts` | Delays value updates to reduce API calls |
| `useProfile` | `src/hooks/use-profile.tsx` | Reads/writes the current profile ID from Context |

That is deliberate -- we follow a "fewer hooks, better hooks" philosophy explained at
the end of this document.

---

## Why We Chose This Approach

### Alternatives considered

| Approach | Why we rejected it |
|---|---|
| **Inline debounce with `useRef` + `setTimeout`** | Works, but you end up copy-pasting 15 lines every time a search input needs debouncing. One typo in the cleanup and you have a memory leak. |
| **lodash.debounce** | Requires wrapping in `useCallback` + `useRef` to be safe in React. Easy to get wrong (stale closures). Our hook is 22 lines -- no external dependency needed. |
| **Redux / Zustand for profile state** | Massive overkill for a single piece of shared state. React Context does the job with zero extra dependencies. |
| **Passing profileId as a prop everywhere** | Prop drilling through 4+ levels of components. Context eliminates this entirely. |

---

## How It Works In Our App

### 1. `useDebouncedValue` -- Our Most Educational Hook

**The problem:** On the Applications page, typing in the search box fires a new API call
for every keystroke. Type "react developer" -- that is 15 keystrokes, 15 network
requests, 15 times the database runs a `LIKE '%r%'`, `'%re%'`, `'%rea%'`... query. Most
of those responses arrive *after* the next keystroke has already been entered, so they
are immediately thrown away.

**The solution:** Wait until the user *stops typing* for 400ms, then fire one API call.

Here is the exact implementation from `src/hooks/use-debounced-value.ts`:

```typescript
import { useState, useEffect } from "react";

/**
 * Returns a debounced version of the given value.
 * The returned value only updates after `delayMs` milliseconds
 * of inactivity (no new value changes).
 */
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

#### Walk through the lifecycle

Let's trace what happens when a user types "react" in the search box:

1. User types "r" -- `value` changes to `"r"`
2. `useEffect` fires -- starts a 400ms timer
3. User types "e" 100ms later -- `value` changes to `"re"`
4. **Cleanup function** fires for the previous effect -- clears the "r" timer
5. New `useEffect` fires -- starts a fresh 400ms timer for `"re"`
6. User types "a" 80ms later -- same cleanup-and-restart cycle
7. User types "c" 90ms later -- same cycle
8. User types "t" 120ms later -- same cycle
9. User stops typing. 400ms passes with no new keystrokes.
10. `setTimeout` callback fires -- `setDebouncedValue("react")`
11. `debouncedValue` updates -- React Query sees the new value in the query key and fires ONE API request

Result: **1 API call** instead of **5**.

#### How it is used in Applications page

From `src/app/applications/page.tsx`:

```typescript
// The raw search state -- updates on every keystroke
const [search, setSearch] = useState("");

// The debounced version -- only updates 400ms after the user stops typing
const debouncedSearch = useDebouncedValue(search, 400);

// This goes into the query key, so React Query only fetches when
// debouncedSearch changes -- not on every keystroke
const currentFilters: Partial<ApplicationFilters> = {
  min_score: minScore,
  max_score: maxScore,
  decision,
  source,
  search: debouncedSearch,  // <-- debounced, not raw
  limit: pageSize,
  offset: (page - 1) * pageSize,
};

const { data: paginatedResult, isLoading: loading } = useQuery({
  queryKey: queryKeys.applications(profileId, currentFilters),
  queryFn: ({ signal }) => getApplications(profileId, currentFilters, signal),
});
```

**Before the hook existed**, the applications page would have needed something like this
scattered inline:

```typescript
const [search, setSearch] = useState("");
const [debouncedSearch, setDebouncedSearch] = useState("");
const timerRef = useRef<NodeJS.Timeout | null>(null);

useEffect(() => {
  if (timerRef.current) clearTimeout(timerRef.current);
  timerRef.current = setTimeout(() => {
    setDebouncedSearch(search);
  }, 400);
  return () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  };
}, [search]);
```

That is roughly 15 lines of boilerplate that obscures the page's actual purpose. After
extracting the hook, it becomes a single line:

```typescript
const debouncedSearch = useDebouncedValue(search, 400);
```

#### Why TypeScript generics `<T>`

The hook is defined as `useDebouncedValue<T>(value: T, delayMs = 300): T`. The generic
`<T>` means TypeScript infers the type from whatever you pass in:

```typescript
// T is inferred as string
const debouncedSearch = useDebouncedValue(search, 400);

// T would be inferred as number
const debouncedScore = useDebouncedValue(minScore, 500);

// T would be inferred as { lat: number; lng: number }
const debouncedLocation = useDebouncedValue(coords, 1000);
```

Without the generic, we would need separate hooks for strings, numbers, objects -- or
use `any`, which defeats the purpose of TypeScript.

#### Why the default delay is 300ms

The default `delayMs = 300` is a well-known UX sweet spot:
- Less than 200ms: barely reduces keystrokes -- timer fires before the next key
- 300-500ms: catches most burst typing while feeling responsive
- More than 600ms: feels sluggish -- user thinks the search is broken

We override it to 400ms in our Applications page because the API call involves a
database query with `LIKE` matching, so a slightly longer debounce saves meaningful
server load.

---

### 2. `useProfile` -- React Context Hook

Here is the full implementation from `src/hooks/use-profile.tsx`:

```typescript
"use client";

import {
  createContext, useContext, useState, useEffect, useCallback,
  type ReactNode,
} from "react";

interface ProfileContextValue {
  profileId: number;
  setProfileId: (id: number) => void;
}

const ProfileContext = createContext<ProfileContextValue>({
  profileId: 1,
  setProfileId: () => {},
});

const STORAGE_KEY = "job-tracker-profile-id";

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileIdState] = useState<number>(1);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = parseInt(stored, 10);
      if (!isNaN(parsed) && parsed > 0) {
        setProfileIdState(parsed);
      }
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

export function useProfile() {
  return useContext(ProfileContext);
}

export function isDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_DEMO_MODE === "true";
}
```

#### Why localStorage persistence

The profile selection needs to survive page refreshes. Without localStorage, every time
the user refreshes the browser, the profile resets to `1`. The `useEffect` on mount
reads the saved value, and `setProfileId` writes it on every change.

This is a classic pattern: useState for in-memory state + useEffect for hydration +
localStorage for persistence.

#### Why `useCallback` for `setProfileId`

```typescript
const setProfileId = useCallback((id: number) => {
  setProfileIdState(id);
  localStorage.setItem(STORAGE_KEY, String(id));
}, []);
```

Without `useCallback`, every re-render of `ProfileProvider` creates a new function
reference for `setProfileId`. Since this function is passed through Context, every
consumer component would see a "new" value on every render, potentially triggering
unnecessary re-renders of the entire component tree.

With `useCallback` and an empty dependency array `[]`, the function reference is created
once and stays stable across renders. Components receiving `setProfileId` through
`useProfile()` will not re-render unless `profileId` actually changes.

#### The `createContext` default value pattern

```typescript
const ProfileContext = createContext<ProfileContextValue>({
  profileId: 1,
  setProfileId: () => {},
});
```

The default value `{ profileId: 1, setProfileId: () => {} }` serves two purposes:

1. **Type safety** -- TypeScript knows the shape of the context without requiring
   `| undefined` in the type definition
2. **Graceful fallback** -- If any component accidentally uses `useProfile()` outside
   the `ProfileProvider`, it gets a sensible default instead of crashing

The `() => {}` is a no-op function. It does nothing, but it does not throw either. This
is a defensive programming pattern.

#### Why `isDemoMode()` is a standalone function, not a hook

```typescript
export function isDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_DEMO_MODE === "true";
}
```

This reads an environment variable -- a static value that never changes at runtime.
There is no state, no effects, no context involved. Making it a hook (`useDemoMode`)
would imply it uses React features and must follow the Rules of Hooks, adding confusion
for no benefit. It is exported from the same file purely for convenience, since it is
often used alongside `useProfile()`.

Usage in the Emails page:

```typescript
const { profileId } = useProfile();
const demo = isDemoMode();
```

---

## The Rules of Hooks (and Why They Exist)

React hooks have strict rules that are often asked about in interviews:

### Rule 1: Hooks must start with `use`

This is not just a naming convention -- React's linter plugin (`eslint-plugin-react-hooks`)
uses the `use` prefix to identify hook calls and enforce the other rules. If you name
a hook `getDebouncedValue`, the linter will not catch violations.

### Rule 2: Hooks cannot be called conditionally

```typescript
// WRONG -- breaks on re-renders when condition changes
if (isSearching) {
  const debounced = useDebouncedValue(search, 400);
}

// RIGHT -- always call the hook, conditionally use the result
const debounced = useDebouncedValue(search, 400);
const querySearch = isSearching ? debounced : "";
```

**Why:** React tracks hooks by their call order. If a hook is skipped on one render,
every hook after it shifts position, and React pairs the wrong state with the wrong
hook.

### Rule 3: Hooks must be called at the top level

Not inside loops, not inside nested functions, not inside try/catch blocks. Same reason
as Rule 2 -- React needs a consistent call order.

---

## Why We Did Not Create More Hooks

We intentionally stopped at two hooks. Here is our extraction rule:

**Extract to a custom hook only when:**

1. **The logic is reused across multiple components** -- `useDebouncedValue` is used in
   Applications and could be used in any future page with search. `useProfile` is used
   in every single page.

2. **The logic involves state management that is complex enough to warrant
   encapsulation** -- The debounce logic involves `useState` + `useEffect` + cleanup. That
   is complex enough that inlining it obscures the component's purpose.

3. **Testing the logic in isolation would be valuable** -- `useDebouncedValue` can be
   tested with React Testing Library's `renderHook` utility, verifying timing behavior
   without rendering any UI.

**What we did NOT extract:**

- Filter state in Applications (`minScore`, `maxScore`, `decision`, `source`) -- used by
  exactly one page, simple `useState`, no benefit to extraction
- Edit state in Emails (`editingId`, `editSubject`, `editBody`) -- page-specific, tightly
  coupled to the email card UI
- Form state in Outcomes (`outcomeForms`, `logForms`) -- unique form structure per page,
  would need generics so complex they would be harder to read than the inline code
- Optimistic update patterns -- they vary per mutation (different shapes, different cache
  keys), making a generic hook impractical

The temptation for freshers is to create hooks like `useApplicationFilters`,
`useEmailEditing`, `useTrackerRowEdits`. These would feel "clean" but would actually
hurt readability because you would need to jump to a separate file to understand what
state exists and how it changes. When state is used in exactly one place, keep it in that
one place.

---

## The Key Insight

Custom hooks are about **DRY principles applied to stateful logic**. The same way you
would extract a utility function when you see the same calculation repeated, you extract
a custom hook when you see the same stateful pattern repeated. But just as not every
three-line function deserves to be a utility, not every `useState` + `useEffect` combo
deserves to be a hook. The threshold for extraction should be **reuse + complexity**, not
just "it could be a hook."

---

## Interview Talking Points

- "Custom hooks let you extract reusable stateful logic without changing the component
  hierarchy. They share logic, not state -- each call gets its own independent state."

- "Our `useDebouncedValue` hook reduced 15 lines of inline timer logic to a single line.
  It uses `useEffect` cleanup to cancel pending timers when the value changes, which is
  the classic React cleanup pattern for subscriptions and timers."

- "The TypeScript generic `<T>` makes the hook work with any type -- strings, numbers,
  objects -- without losing type safety. The caller gets the same type back that they
  passed in."

- "We use `useCallback` in our profile context to stabilize the setter function
  reference, preventing unnecessary re-renders of every consumer component."

- "We deliberately limited ourselves to two hooks. Our extraction criteria: the logic
  must be reused, must be complex enough to warrant encapsulation, and must benefit from
  isolated testing. Most page-level state does not meet these criteria."

- "The `createContext` default value pattern provides both TypeScript type information
  and a runtime fallback, which is why the setter is `() => {}` rather than `undefined`."

- "The Rules of Hooks exist because React tracks hooks by call order. Conditional or
  looped hook calls break that ordering guarantee, leading to state mismatches on
  re-render."

- "`isDemoMode()` is a plain function, not a hook, because it reads a static env var.
  Not everything that lives near hooks needs to be a hook -- the `use` prefix should
  signal that React state/effects are involved."
