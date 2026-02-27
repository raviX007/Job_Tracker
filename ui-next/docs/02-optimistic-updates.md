# Optimistic Updates

## What Is This?

Optimistic updates are a UI pattern where the interface is updated *immediately* when the user performs an action, *before* the server confirms the result. If the server later reports a failure, the UI rolls back to its previous state. This creates the illusion of zero latency -- the app feels instant, even though the network round trip takes 200-500ms.

This project uses optimistic updates for all 8 mutations across 3 pages: Emails (4 mutations), Tracker (2 mutations), and Outcomes (2 mutations). Every destructive action, every edit, every status change updates the UI in under 16ms (one frame), and rolls back cleanly on failure.

---

## Why We Chose This Approach

### The Problem: Waiting for the Server

Without optimistic updates, a typical delete flow looks like this:

1. User clicks "Delete"
2. UI shows a spinner on the button ("Deleting...")
3. Network request travels to the server (~50-200ms)
4. Server processes the request (~10-50ms)
5. Response travels back (~50-200ms)
6. UI updates -- the item disappears

Total perceived latency: **200-500ms**. That half-second gap between clicking and seeing the result makes the app feel sluggish. In a job tracker where you might delete 10 emails in a row, those half-seconds add up to real frustration.

### The Optimistic Approach

With optimistic updates:

1. User clicks "Delete"
2. UI **immediately** removes the item (0ms perceived latency)
3. Network request fires in the background
4. If the server confirms: done, no further UI changes needed
5. If the server fails: UI rolls the item back into its original position, shows an error

Perceived latency: **0ms**. The app feels native.

### Alternatives Considered

- **Pessimistic updates (wait for server)**: Simpler to implement, but 200-500ms delay per action makes the app feel slow. Unacceptable for a data-heavy dashboard where users perform many rapid actions.
- **Local-first / CRDT**: Overkill for this project. We have a single user and a single backend -- there are no merge conflicts to resolve. The complexity of local-first storage is not justified.
- **Debounced saves (like Google Docs)**: Works for continuous edits but not for discrete actions like delete/send. You cannot "debounce" a delete.

---

## How It Works In Our App

### The 4-Step Pattern

Every mutation in this codebase follows the same 4-step lifecycle provided by React Query's `useMutation`:

```
onMutate  -->  API call  -->  onError / onSuccess  -->  onSettled
```

1. **`onMutate`**: Runs *before* the API call. Cancel in-flight queries, snapshot the current cache, apply the optimistic update, and return the snapshot.
2. **`onError`**: Runs if the API call fails. Roll back the cache to the snapshot.
3. **`onSuccess`**: Runs if the API call succeeds. Show a success message.
4. **`onSettled`**: Runs *always* (success or failure). Invalidate queries to re-sync with server truth.

### Example 1: Email Delete (Removing an Item from a List)

This is the most instructive example. From `emails/page.tsx`:

```tsx
// src/app/emails/page.tsx

const deleteMutation = useMutation({
  mutationFn: (emailId: number) => deleteEmail(emailId),

  onMutate: async (emailId) => {
    // STEP 1: Cancel any in-flight queries for this data
    await queryClient.cancelQueries({
      queryKey: queryKeys.emails(profileId, filterStatus, filterSource),
    });

    // STEP 2: Snapshot the current cache value
    const prev = queryClient.getQueryData<PaginatedResult<EmailQueueItem[]>>(queryKey);

    // STEP 3: Apply the optimistic update (filter out the deleted email)
    if (prev) {
      queryClient.setQueryData<PaginatedResult<EmailQueueItem[]>>(queryKey, {
        ...prev,
        data: prev.data.filter(e => e.id !== emailId),
        totalCount: prev.totalCount - 1,
      });
    }

    // STEP 4: Close the confirmation dialog immediately
    setDeleteDialogId(null);

    // STEP 5: Return the snapshot for potential rollback
    return { prev };
  },

  onError: (_err, _vars, ctx) => {
    // ROLLBACK: Restore the snapshot if the server call failed
    if (ctx?.prev) queryClient.setQueryData(queryKey, ctx.prev);
  },

  onSuccess: () => showSuccess("Email deleted"),

  onSettled: invalidateAll,
});
```

Let's walk through this step by step:

**`onMutate` -- what happens before the network request:**

1. **`cancelQueries`** -- This is critical and often forgotten. Imagine the emails list is currently refetching in the background (maybe the stale time expired). If we apply our optimistic update *while* that refetch is in-flight, the refetch will complete a moment later and overwrite our optimistic update with the old server data (which still includes the deleted email). By cancelling first, we prevent this race condition.

2. **`getQueryData`** -- We take a snapshot of the current cache. This is our insurance policy. If the server call fails, we need to restore exactly this data. The snapshot includes the full paginated result: the array of emails AND the total count.

3. **`setQueryData`** -- We surgically update the cache. We keep the same structure (`PaginatedResult<EmailQueueItem[]>`) but filter out the deleted email from `data` and decrement `totalCount` by 1. The user sees the email vanish instantly.

4. **`setDeleteDialogId(null)`** -- We close the confirmation dialog. This is a UI detail but it matters: the dialog closes *before* the network request completes, making the entire interaction feel snappy.

5. **`return { prev }`** -- The return value from `onMutate` becomes the `ctx` (context) parameter in `onError` and `onSuccess`. This is how we pass the snapshot to the rollback handler.

**`onError` -- what happens if the server rejects the delete:**

```tsx
onError: (_err, _vars, ctx) => {
  if (ctx?.prev) queryClient.setQueryData(queryKey, ctx.prev);
},
```

The snapshot is restored. The email reappears in the list. The user sees it pop back and knows something went wrong. (The combined error display at the top of the page will show the error message.)

**`onSuccess` -- what happens on server confirmation:**

```tsx
onSuccess: () => showSuccess("Email deleted"),
```

A green flash message appears for 3 seconds: "Email deleted". The email is already gone from the UI (it was removed optimistically), so there is no visual change -- just confirmation.

**`onSettled` -- always runs, success or failure:**

```tsx
onSettled: invalidateAll,
```

Where `invalidateAll` is:

```tsx
const invalidateAll = () => {
  queryClient.invalidateQueries({ queryKey: queryKeys.emails(profileId, filterStatus, filterSource) });
  queryClient.invalidateQueries({ queryKey: queryKeys.emailStatuses(profileId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.emailSources(profileId) });
};
```

Even on success, we invalidate all related queries. Why? Because the server might have side effects we do not know about. Deleting an email changes the status counts (the badge bar at the top). It might affect the sources list if that was the last email from a source. By invalidating, we tell React Query: "your cache for these keys is stale -- refetch when someone next accesses them."

The refetch happens silently in the background. The user sees no loading spinner because the optimistic data is already close to the truth.

### Example 2: Tracker Upsert (Updating a Row In-Place)

The Tracker page has an editable spreadsheet. Each row has Save and Obsolete buttons. The upsert mutation updates a row's fields optimistically:

```tsx
// src/app/tracker/page.tsx

const upsertMutation = useMutation({
  mutationFn: (data: {
    job_id: number; profile_id: number; method: string;
    platform: string; response_type: string | null;
    notes: string | null; app_id: number | null;
  }) => upsertApplication(data),

  onMutate: async (data) => {
    const queryKey = [...queryKeys.tracker(profileId), page, pageSize];
    await queryClient.cancelQueries({ queryKey });
    const prev = queryClient.getQueryData<PaginatedResult<TrackerRow[]>>(queryKey);

    if (prev) {
      queryClient.setQueryData<PaginatedResult<TrackerRow[]>>(queryKey, {
        ...prev,
        data: prev.data.map(r => r.job_id === data.job_id ? {
          ...r,
          app_method: data.method,
          app_platform: data.platform,
          response_type: data.response_type,
          app_notes: data.notes,
        } : r),
      });
    }
    return { prev };
  },

  onError: (_err, _vars, ctx) => {
    if (ctx?.prev) {
      queryClient.setQueryData([...queryKeys.tracker(profileId), page, pageSize], ctx.prev);
    }
  },

  onSuccess: (_data, vars) => {
    // Green flash on the saved row
    setSavedRows((prev) => new Set(prev).add(vars.job_id));
    setTimeout(() => {
      setSavedRows((prev) => {
        const next = new Set(prev);
        next.delete(vars.job_id);
        return next;
      });
    }, 1500);
    // Clear local edits for this row
    setEdits((prev) => {
      const next = { ...prev };
      delete next[vars.job_id];
      return next;
    });
  },

  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.tracker(profileId) });
  },
});
```

Notice the key difference from the delete example: **instead of filtering out an item, we map over the array and update the matching row in-place.** The `...r` spread preserves all existing fields (score, company, title, etc.) and overrides only the four editable fields.

The `onSuccess` callback here also includes a visual feedback mechanism: the saved row gets a green background (`bg-emerald-50`) for 1.5 seconds via the `savedRows` Set, providing confirmation that the save landed.

### Example 3: Outcomes Log Mutation (Removing from One List)

The Outcomes page has two tabs: "Update Existing" (modify applications you have already logged) and "Log New Application" (convert analyzed jobs into applications). When you log a job, it should disappear from the "analyzed jobs" list:

```tsx
// src/app/outcomes/page.tsx

const logMutation = useMutation({
  mutationFn: (data: { job_id: number; profile_id: number; method: string; platform: string }) =>
    createApplication(data),

  onMutate: async (data) => {
    await queryClient.cancelQueries({ queryKey: queryKeys.analyzedJobs(profileId) });
    const prev = queryClient.getQueryData<AnalyzedJobForUpdate[]>(queryKeys.analyzedJobs(profileId));

    if (prev) {
      // Optimistically remove the job from the list
      queryClient.setQueryData<AnalyzedJobForUpdate[]>(
        queryKeys.analyzedJobs(profileId),
        prev.filter(j => j.job_id !== data.job_id),
      );
    }
    return { prev };
  },

  onError: (_err, _vars, ctx) => {
    if (ctx?.prev) queryClient.setQueryData(queryKeys.analyzedJobs(profileId), ctx.prev);
  },

  onSuccess: (_data, { job_id }) => {
    setLoggedJobId(job_id);
    setTimeout(() => setLoggedJobId(null), 2000);
  },

  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.appsForUpdate(profileId) });
    queryClient.invalidateQueries({ queryKey: queryKeys.analyzedJobs(profileId) });
  },
});
```

This mutation is interesting because `onSettled` invalidates **two** different query keys: the analyzed jobs list (where the item was removed) AND the applications-for-update list (where a new entry should appear). A single user action ripples across two data sources, and React Query keeps both in sync.

### Example 4: Email Save (In-Place Edit)

Editing an email's subject and body, applied optimistically:

```tsx
// src/app/emails/page.tsx

const saveMutation = useMutation({
  mutationFn: ({ emailId, subject, body }: { emailId: number; subject: string; body: string }) =>
    updateEmailContent(emailId, subject, body),

  onMutate: async ({ emailId, subject, body }) => {
    await queryClient.cancelQueries({ queryKey: queryKeys.emails(profileId, filterStatus, filterSource) });
    const prev = queryClient.getQueryData<PaginatedResult<EmailQueueItem[]>>(queryKey);

    if (prev) {
      queryClient.setQueryData<PaginatedResult<EmailQueueItem[]>>(queryKey, {
        ...prev,
        data: prev.data.map(e => e.id === emailId ? { ...e, subject, body_plain: body } : e),
      });
    }
    cancelEditing();  // Exit edit mode immediately
    return { prev };
  },

  onError: (_err, _vars, ctx) => {
    if (ctx?.prev) queryClient.setQueryData(queryKey, ctx.prev);
  },
  onSettled: invalidateAll,
  onSuccess: () => showSuccess("Email updated"),
});
```

The `cancelEditing()` call inside `onMutate` is another UX detail: the edit form closes *instantly* and the updated subject/body text appears in the read-only view. If the save fails, the old text is restored via rollback (but the form stays closed -- the user would need to re-open it).

---

## All 8 Mutations Listed

| # | Page | Mutation | Optimistic Behavior |
|---|------|----------|-------------------|
| 1 | Emails | `saveMutation` | Update subject/body in-place, close edit form |
| 2 | Emails | `sendMutation` | Set email status to "sent" in-place |
| 3 | Emails | `deleteMutation` | Remove email from list, decrement totalCount |
| 4 | Emails | `deleteAllMutation` | Empty the entire list, set totalCount to 0 |
| 5 | Tracker | `upsertMutation` | Update method/platform/response_type/notes in-place |
| 6 | Tracker | `obsoleteMutation` | Toggle `is_obsolete` flag on the row |
| 7 | Outcomes | `outcomeMutation` | Update response_type/date/notes in-place |
| 8 | Outcomes | `logMutation` | Remove job from analyzed list (moves to applications) |

---

## The Snapshot + Rollback Pattern Explained

The core of every optimistic update is this two-part contract:

```tsx
// In onMutate:
const prev = queryClient.getQueryData(queryKey);  // Take snapshot
queryClient.setQueryData(queryKey, newData);        // Apply optimistic update
return { prev };                                    // Pass snapshot to context

// In onError:
if (ctx?.prev) queryClient.setQueryData(queryKey, ctx.prev);  // Restore snapshot
```

Why does this work? Because `getQueryData` and `setQueryData` operate on React Query's in-memory cache, not on React state. This means:
- The snapshot is a plain JavaScript object -- cheap to store.
- `setQueryData` triggers a synchronous re-render of any component subscribed to that query key.
- The rollback in `onError` is also synchronous -- the UI snaps back in one frame.

**Why we return `{ prev }` as an object, not just `prev`:** Convention. If we later need to pass additional context (e.g., `{ prev, deletedId }`), the shape is already established. It also makes the `ctx?.prev` check self-documenting.

---

## Why `onSettled` Always Invalidates

Even when a mutation succeeds, `onSettled` fires `invalidateQueries`. This seems wasteful -- the optimistic update already applied the correct state, so why refetch?

Three reasons:

1. **Server-side side effects** -- When you delete an email, the server might update status counts, recalculate source distributions, or trigger other cascading changes. Our optimistic update only knew about removing one item from one list. The server knows about everything.

2. **Pagination edge cases** -- If you delete an item on page 1 and there were 51 items total (showing 50 per page), item 51 should now appear on page 1. Our optimistic update just removed an item; it cannot pull item 51 from the server. Invalidation triggers a refetch that fixes this.

3. **Other users / concurrent processes** -- While the user was deleting an email, the pipeline might have added 5 new ones. Invalidation ensures the cache reflects reality.

The invalidation happens in the background. Since the optimistic data is already close to correct, the user sees no loading spinner -- the refetched data silently replaces the cache.

---

## Common Mistakes Freshers Make

### 1. Forgetting to cancel queries first

```tsx
// BAD -- race condition!
onMutate: async (emailId) => {
  const prev = queryClient.getQueryData(queryKey);
  queryClient.setQueryData(queryKey, optimisticData);
  return { prev };
}
```

Without `cancelQueries`, an in-flight background refetch can overwrite your optimistic update milliseconds after you apply it. Always cancel first.

### 2. Forgetting `onSettled`

```tsx
// BAD -- cache goes stale forever!
const deleteMutation = useMutation({
  mutationFn: (id) => deleteEmail(id),
  onMutate: async (id) => { /* optimistic remove */ },
  onError: (err, vars, ctx) => { /* rollback */ },
  onSuccess: () => { showSuccess("Deleted"); },
  // No onSettled -- cache is never re-synced with server
});
```

If you skip `onSettled`, your optimistic data is the *only* truth the UI ever sees. If the server had side effects (changed counts, moved items), the UI will be permanently out of sync until the user manually refreshes.

### 3. Not returning the snapshot from `onMutate`

```tsx
// BAD -- onError has no snapshot to roll back to!
onMutate: async (emailId) => {
  await queryClient.cancelQueries({ queryKey });
  const prev = queryClient.getQueryData(queryKey);
  queryClient.setQueryData(queryKey, optimisticData);
  // Forgot: return { prev };
},
onError: (_err, _vars, ctx) => {
  // ctx is undefined -- cannot roll back!
}
```

Without `return { prev }`, the error handler has no data to restore. The deleted email stays gone in the UI even though the server never actually deleted it.

### 4. Mutating the cache snapshot directly

```tsx
// BAD -- mutates the snapshot in place, making rollback impossible!
onMutate: async (emailId) => {
  const prev = queryClient.getQueryData(queryKey);
  prev.data = prev.data.filter(e => e.id !== emailId);  // Mutates prev!
  queryClient.setQueryData(queryKey, prev);
  return { prev };  // prev is now the *modified* version -- rollback will be wrong
},
```

Always create a new object. Use `filter`, `map`, and spread operators to produce a new array/object. Never mutate the snapshot.

---

## The Key Insight

Optimistic updates are not just a performance trick -- they are a **contract between the frontend and backend**. The frontend promises to show the user the expected result immediately. The backend promises that, if it fails, the error will be catchable and the frontend can undo the optimistic change.

This contract only works when both sides are reliable. In our app, the API client throws structured errors (see the [API Client Design](./03-api-client-design.md) doc), and the rollback handler uses React Query's cache API to restore state atomically. The result is an app that feels instantaneous while remaining fully consistent with server truth.

---

## Interview Talking Points

- "Every mutation in the app follows the same 4-step pattern: onMutate takes a snapshot and applies the optimistic update, onError rolls back, onSuccess shows feedback, and onSettled always invalidates to re-sync with the server."

- "The first thing onMutate does is `cancelQueries`. This prevents a race condition where a background refetch could overwrite the optimistic update. It is the most commonly forgotten step."

- "We return `{ prev }` from onMutate as the context object. This snapshot is a plain JavaScript object stored in closure scope -- cheap to hold and instant to restore on rollback."

- "Even on success, onSettled invalidates all related queries. The server might have side effects we cannot predict: changing status counts, affecting pagination, or reflecting concurrent pipeline runs."

- "The delete mutation also closes the confirmation dialog inside onMutate, before the network request fires. This makes the entire delete flow feel instant -- click confirm, dialog closes, email vanishes, all in one frame."

- "We have 8 mutations across 3 pages, and every single one uses the same snapshot-rollback pattern. This consistency means any developer can read one mutation and understand all 8."

- "The tracker upsert mutation is different from deletes: instead of filtering out an item, it maps over the array and updates the matching row in-place using the spread operator. This preserves all read-only fields while updating only the editable ones."

- "The outcomes logMutation is the most interesting because it invalidates TWO query keys in onSettled: the analyzed-jobs list (where the item was removed) and the applications-for-update list (where a new entry appears). A single action ripples across two data sources."
