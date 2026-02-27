# setInterval-Based Long Polling

## What Is It

Long polling is a technique where the client repeatedly asks the server "are you done yet?" at fixed intervals until a job finishes. In this project, the **Pipeline page** uses `setInterval` to poll a status endpoint every 3 seconds after kicking off a long-running backend process.

This is fundamentally different from how the rest of the app fetches data. Every other page uses React Query (`useQuery`) for declarative data fetching with caching, deduplication, and automatic refetching. The Pipeline page cannot use that model because pipeline runs are **fire-and-forget mutations** -- you POST to start a run, receive a `run_id`, then poll a completely different endpoint to track progress.

**Key file:** `src/app/pipeline/page.tsx`

---

## Why We Chose This

### Why Not React Query for This?

React Query's `useQuery` is designed for a simple mental model: given a query key, fetch data, cache it, and refetch when stale. It works beautifully for the other pages:

- **Overview page**: fetch stats, cache them, refetch when the tab is revisited.
- **Applications page**: fetch a paginated list, cache per-page, refetch on filter change.
- **Analytics page**: fetch 6 datasets in parallel, cache them.

But the pipeline workflow breaks this model:

1. **The "data" doesn't exist at query time.** You POST to `/api/pipeline/run` to _create_ a run. There is nothing to cache before the mutation.
2. **The status endpoint is ephemeral.** `GET /api/pipeline/runs/{run_id}` returns real-time status of one specific run. This is not reusable data -- it is transient progress.
3. **Polling must stop on completion.** React Query's `refetchInterval` can poll, but integrating "stop polling when status is completed or failed, then update 5 different state variables, then clear the interval" is more complex than a plain `setInterval`.
4. **Two independent pipelines.** The page runs two completely separate polling loops (main pipeline and startup scout). With React Query, you would need two separate queries with coordinated `refetchInterval` toggling. With `setInterval`, it is straightforward.

### Why `setInterval` Specifically?

- **Simple mental model**: set it, check on each tick, clear it when done.
- **Full control**: we can catch errors silently per tick, update multiple state setters, and clear the interval from inside the callback.
- **No library dependency**: this is a vanilla browser API. No additional abstraction needed.

---

## Real Code Examples

### 1. `useRef` for Interval Handles -- Survives Re-renders

```tsx
// src/app/pipeline/page.tsx (line 127)
const pipelineIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
```

```tsx
// src/app/pipeline/page.tsx (line 136)
const startupIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
```

**Why `useRef` instead of `useState`?**

The interval ID is not rendering state -- you never display it in the UI. If you stored it in `useState`, every `setInterval` call would trigger a re-render, which is wasteful and can cause bugs (re-rendering during an async callback). `useRef` stores a mutable value that:
- **Survives re-renders** -- the `.current` value persists across renders
- **Does not cause re-renders** -- mutating `.current` does not trigger React's reconciliation
- **Is accessible in closures** -- the interval callback and cleanup function can both read/write `intervalRef.current`

---

### 2. `ReturnType<typeof setInterval>` -- Cross-Platform TypeScript

```tsx
const pipelineIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
```

**Why not just `number`?**

In browsers, `setInterval` returns a `number`. In Node.js, it returns a `Timeout` object. Since Next.js code can execute in both environments (SSR on Node, client in browser), using `ReturnType<typeof setInterval>` lets TypeScript infer the correct type for the current platform. This avoids type errors when running tests in Node or during server-side rendering.

---

### 3. Cleanup on Unmount -- Preventing Memory Leaks

```tsx
// src/app/pipeline/page.tsx (lines 139-144)
useEffect(() => {
  return () => {
    if (pipelineIntervalRef.current) clearInterval(pipelineIntervalRef.current);
    if (startupIntervalRef.current) clearInterval(startupIntervalRef.current);
  };
}, []);
```

**How it works:**

- The `useEffect` runs once on mount (empty dependency array `[]`).
- It does nothing on mount -- it only returns a cleanup function.
- When the component unmounts (user navigates away from the Pipeline page), React calls the cleanup function.
- The cleanup clears both intervals, preventing them from firing after the component is gone.

**What happens without this?** The interval keeps firing. The `setStatus`, `setMessage`, etc. state setters get called on an unmounted component. In development, React warns you: "Can't perform a React state update on an unmounted component." In production, it silently leaks memory and CPU.

---

### 4. Generalized `pollRun` Callback -- Reused for Both Pipelines

```tsx
// src/app/pipeline/page.tsx (lines 146-177)
const pollRun = useCallback(
  (
    runId: string,
    setStatus: (s: RunStatus) => void,
    setMessage: (m: string) => void,
    setOutput: (o: string) => void,
    setDuration: (d: number | null) => void,
    intervalRef: React.MutableRefObject<ReturnType<typeof setInterval> | null>,
  ) => {
    intervalRef.current = setInterval(async () => {
      try {
        const run = await getPipelineRunStatus(runId);
        setOutput(run.output || "");

        if (run.status === "completed" || run.status === "failed") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          intervalRef.current = null;
          setStatus(run.status === "completed" ? "completed" : "failed");
          setDuration(run.duration_seconds);
          if (run.error) {
            setMessage(run.error);
          } else if (run.status === "completed") {
            setMessage("Pipeline finished successfully");
          }
        }
      } catch {
        // Polling error — don't stop, just skip this tick
      }
    }, POLL_INTERVAL_MS);
  },
  [],
);
```

**Design insight:** Instead of writing two separate polling functions for the main pipeline and startup scout, this single `pollRun` function accepts **setters as parameters**. Each caller passes its own state setters and interval ref:

```tsx
// Main pipeline uses it (line 186):
pollRun(result.run_id, setPipelineStatus, setPipelineMessage,
        setPipelineOutput, setPipelineDuration, pipelineIntervalRef);

// Startup scout uses the same function (line 208):
pollRun(result.run_id, setStartupStatus, setStartupMessage,
        setStartupOutput, setStartupDuration, startupIntervalRef);
```

This is a form of **dependency injection** -- the polling logic is the same, but the "where to write results" is parameterized. It eliminates code duplication without introducing a custom hook (which would be overkill for two callers in the same component).

**Why `useCallback` with `[]`?** The function only depends on `getPipelineRunStatus` (an imported module function) and `POLL_INTERVAL_MS` (a module constant). Neither changes between renders, so the empty dependency array is correct. `useCallback` prevents `pollRun` from being recreated on every render, which matters because `handleRunPipeline` and `handleRunStartup` reference it.

---

### 5. Silent Tick Failure -- Network Resilience

```tsx
} catch {
  // Polling error — don't stop, just skip this tick
}
```

**Why an empty catch?**

When you poll every 3 seconds, a single network timeout or 503 response should not crash the entire polling loop. The empty `catch` means:
- If tick #5 fails (network blip), the interval is still running.
- Tick #6 fires 3 seconds later and tries again.
- The user sees no error -- they just don't get an update for one tick.
- When the network recovers, the next successful tick updates the UI normally.

This is different from a `useQuery` error, where you want to show the user an error state and let them retry. In polling, transient failures are expected and self-healing.

---

### 6. State Machine -- `RunStatus` Type

```tsx
// src/app/pipeline/page.tsx (line 21)
type RunStatus = "idle" | "running" | "completed" | "failed";
```

```tsx
// State initialization:
const [pipelineStatus, setPipelineStatus] = useState<RunStatus>("idle");
```

This is a simple **finite state machine** with 4 states:

```
idle ──(click Run)──> running ──(poll: completed)──> completed
                          │
                          └──(poll: failed)──> failed
```

Every UI decision branches on this type:
- `"idle"`: show nothing (StatusIndicator returns null)
- `"running"`: show blue banner with spinner, disable the Run button
- `"completed"`: show green banner with duration
- `"failed"`: show red banner with error message

The Run button's `disabled` prop checks it:
```tsx
disabled={demoMode || pipelineStatus === "running"}
```

---

### 7. Two Independent Pipelines -- Same Pattern, Separate State

The page maintains completely independent state for each pipeline:

```tsx
// Main pipeline state (lines 121-127)
const [pipelineSource, setPipelineSource] = useState<string>("all");
const [pipelineLimit, setPipelineLimit] = useState<number>(10);
const [pipelineStatus, setPipelineStatus] = useState<RunStatus>("idle");
const [pipelineMessage, setPipelineMessage] = useState("");
const [pipelineOutput, setPipelineOutput] = useState("");
const [pipelineDuration, setPipelineDuration] = useState<number | null>(null);
const pipelineIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

// Startup scout state (lines 130-136)
const [startupSource, setStartupSource] = useState<string>("startup_scout");
const [startupLimit, setStartupLimit] = useState<number>(10);
const [startupStatus, setStartupStatus] = useState<RunStatus>("idle");
const [startupMessage, setStartupMessage] = useState("");
const [startupOutput, setStartupOutput] = useState("");
const [startupDuration, setStartupDuration] = useState<number | null>(null);
const startupIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
```

Both pipelines can run simultaneously because they have separate state variables and separate interval refs. Running the main pipeline does not affect the startup scout's status, output, or polling interval.

---

### 8. StatusIndicator Component -- Conditional Rendering by Status

```tsx
// src/app/pipeline/page.tsx (lines 54-93)
function StatusIndicator({ status, message, duration }: {
  status: RunStatus;
  message: string;
  duration?: number | null;
}) {
  if (status === "idle") return null;

  return (
    <div
      className={cn(
        "mt-4 rounded-lg border px-4 py-3 text-sm",
        status === "running" && "border-blue-200 bg-blue-50 text-blue-700",
        status === "completed" && "border-emerald-200 bg-emerald-50 text-emerald-700",
        status === "failed" && "border-red-200 bg-red-50 text-red-700",
      )}
    >
      <div className="flex items-center gap-2">
        {status === "running" && (
          <svg
            className="h-4 w-4 animate-spin"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10"
                    stroke="currentColor" strokeWidth="4" />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
        )}
        <span className="font-medium">
          {status === "running" && "Pipeline running..."}
          {status === "completed" && "Completed"}
          {status === "failed" && "Failed"}
        </span>
        {duration != null && (
          <span className="text-xs opacity-70">({duration.toFixed(1)}s)</span>
        )}
      </div>
      {message && <p className="mt-1">{message}</p>}
    </div>
  );
}
```

**Key details:**
- Returns `null` for `"idle"` -- no DOM element at all, not just hidden.
- The spinner is a pure SVG with Tailwind's `animate-spin` class -- no external spinner library.
- `cn()` (a `clsx`/`twMerge` utility) conditionally applies color classes based on the current status.
- `duration != null` (loose inequality) catches both `null` and `undefined`, showing the duration badge only when the run has finished.

---

### 9. OutputLog Component -- Auto-Scrolling Terminal Output

```tsx
// src/app/pipeline/page.tsx (lines 96-115)
function OutputLog({ output }: { output: string }) {
  const logRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [output]);

  if (!output) return null;

  return (
    <pre
      ref={logRef}
      className="mt-4 max-h-80 overflow-auto rounded-lg border border-border
                 bg-gray-900 p-4 font-mono text-xs leading-relaxed text-green-400"
    >
      {stripAnsi(output)}
    </pre>
  );
}
```

**How auto-scroll works:**
1. `logRef` is a ref to the `<pre>` DOM element.
2. Every time `output` changes (new poll data arrives), the `useEffect` fires.
3. Setting `scrollTop = scrollHeight` scrolls the container to the bottom, showing the latest log line.
4. `max-h-80` (320px) with `overflow-auto` constrains the log and adds a scrollbar.

**`stripAnsi()`** cleans ANSI escape codes (color codes like `\x1B[32m`) from the backend's raw terminal output:

```tsx
// src/lib/utils.ts (line 71)
export function stripAnsi(str: string): string {
  return str.replace(/\x1B\[[0-9;]*[a-zA-Z]/g, "");
}
```

Without this, the `<pre>` tag would display raw escape sequences like `[32mScraping...[0m` instead of clean text.

---

### 10. `POLL_INTERVAL_MS` Constant

```tsx
// src/app/pipeline/page.tsx (line 52)
const POLL_INTERVAL_MS = 3000;
```

3 seconds is a balance between:
- **Responsiveness**: the user sees updates within 3 seconds of a status change.
- **Server load**: only ~20 requests per minute per active pipeline run.
- **Network efficiency**: not hammering the API on every animation frame.

This is a named constant (not a magic number in the `setInterval` call) so it is easy to find and adjust.

---

### 11. `handleRunPipeline` Flow -- The Complete Lifecycle

```tsx
// src/app/pipeline/page.tsx (lines 179-198)
async function handleRunPipeline() {
  setPipelineStatus("running");
  setPipelineMessage("");
  setPipelineOutput("");
  setPipelineDuration(null);
  try {
    const result = await runMainPipeline(pipelineSource, pipelineLimit);
    pollRun(
      result.run_id,
      setPipelineStatus,
      setPipelineMessage,
      setPipelineOutput,
      setPipelineDuration,
      pipelineIntervalRef,
    );
  } catch (err) {
    setPipelineStatus("failed");
    setPipelineMessage(err instanceof Error ? err.message : "Failed to start pipeline");
  }
}
```

**Step-by-step walkthrough:**

1. **User clicks "Run Pipeline"** -- `handleRunPipeline` is called.
2. **Reset UI** -- Status goes to `"running"`, previous messages/output/duration are cleared.
3. **POST mutation** -- `runMainPipeline(source, limit)` sends a POST request to the backend. The backend starts the pipeline asynchronously and immediately returns `{ run_id: "abc123" }`.
4. **Start polling** -- `pollRun` is called with the `run_id` and all the state setters. Inside, `setInterval` begins firing every 3 seconds.
5. **Each tick** -- `getPipelineRunStatus(runId)` hits `GET /api/pipeline/runs/abc123`. The response contains `{ status, output, error, duration_seconds }`.
6. **Output updates** -- `setOutput(run.output)` updates the OutputLog component, which auto-scrolls.
7. **Terminal condition** -- When `status` is `"completed"` or `"failed"`, the interval is cleared and final state is set.
8. **Catch on POST failure** -- If the initial POST fails (server down, auth error), we skip polling entirely and show the error immediately.

---

## How It Works -- Architecture Diagram

```
User clicks "Run Pipeline"
        │
        v
handleRunPipeline()
        │
        ├── setPipelineStatus("running")     ← UI shows spinner
        │
        ├── await runMainPipeline()          ← POST /api/pipeline/run
        │       │
        │       └── returns { run_id }
        │
        └── pollRun(run_id, setters, ref)
                │
                └── setInterval(async () => {
                        │
                        ├── GET /api/pipeline/runs/{run_id}
                        │
                        ├── setOutput(run.output)    ← OutputLog updates
                        │
                        ├── if completed/failed:
                        │   ├── clearInterval()
                        │   ├── setStatus("completed"|"failed")
                        │   └── setDuration(seconds)
                        │
                        └── catch: skip this tick
                    }, 3000)
```

---

## Interview Talking Points

1. **"I chose setInterval over React Query because the pipeline workflow is fire-and-forget, not cache-and-refetch."** -- React Query excels at caching server state that multiple components share. Pipeline status is ephemeral, single-consumer, and needs to stop polling on a terminal condition. A plain `setInterval` is simpler and more explicit.

2. **"I used `useRef` for the interval handle to avoid unnecessary re-renders."** -- The interval ID is infrastructure, not UI state. Storing it in `useRef` means starting/stopping the interval never triggers React reconciliation.

3. **"The `pollRun` function is parameterized so both pipelines reuse the same logic."** -- Instead of duplicating the polling callback, I pass state setters and the interval ref as arguments. This is dependency injection at the function level -- same pattern, different targets.

4. **"The empty catch block is intentional -- transient network failures should not kill the polling loop."** -- This shows understanding of the difference between "show the user an error" (React Query) and "silently retry" (polling). One bad tick out of 20 is irrelevant.

5. **"I guard against memory leaks with cleanup in useEffect."** -- The cleanup function clears both intervals on unmount. Without this, navigating away from the page would leave orphaned intervals trying to set state on unmounted components.

6. **"The RunStatus type acts as a finite state machine that drives all UI decisions."** -- Four states, clear transitions, and every UI element branches on this type. The button disables during "running", the StatusIndicator changes color per state, and the OutputLog only appears when there is output.

---

## Common Questions

### Q: Why not use React Query's `refetchInterval` option?

React Query does support polling via `refetchInterval`. You could write:

```tsx
useQuery({
  queryKey: ["pipeline-run", runId],
  queryFn: () => getPipelineRunStatus(runId),
  refetchInterval: 3000,
  enabled: !!runId,
});
```

The problems:
1. **Stopping the poll** requires setting `refetchInterval` to `false` conditionally, which means storing the "should I poll" flag in state -- adding complexity.
2. **Updating 5 state variables** (`status`, `message`, `output`, `duration`, `intervalRef`) from the query result requires `onSuccess` / `select` / `useEffect` chaining, which is more convoluted than directly calling setters in the interval callback.
3. **Two independent polling loops** would need two `useQuery` hooks with two `refetchInterval` states. Doable, but more complex than two `setInterval` calls sharing one `pollRun` function.

For this use case, the cure is worse than the disease.

### Q: What is `ReturnType<typeof setInterval>` and why not just use `number`?

`setInterval` returns different types depending on the runtime:
- **Browser**: `number` (a numeric handle passed to `clearInterval`)
- **Node.js**: `Timeout` (an object from the `timers` module)

`ReturnType<typeof setInterval>` evaluates to the correct type for the current environment. Since Next.js renders components on both the server (Node) and the client (browser), this avoids TypeScript errors in either environment.

### Q: Could both pipelines run at the same time?

Yes. They have completely separate state variables and separate interval refs. Clicking "Run Pipeline" starts `pipelineIntervalRef`, and clicking "Run Startup Scout" starts `startupIntervalRef`. Both poll independently. If one finishes before the other, only its interval is cleared.

### Q: What if the user navigates away mid-poll and comes back?

When the component unmounts, the cleanup `useEffect` clears both intervals. Polling stops. When the user navigates back, the component remounts fresh with `status: "idle"`. The previous run's status is lost because it was only in local state, not in a cache.

If you needed to restore polling after navigation, you would need to persist the `run_id` (e.g., in URL params or a global store) and check its status on mount.

### Q: Why not use WebSockets or Server-Sent Events instead of polling?

Both would be more efficient for real-time updates:
- **WebSockets**: bidirectional, but requires a WebSocket server, connection management, and reconnection logic.
- **SSE (Server-Sent Events)**: simpler (HTTP-based, server pushes), but requires the backend to support streaming responses.

Polling is the simplest approach that works. The pipeline runs infrequently (maybe a few times per day), so the overhead of 20 requests per minute for 1-2 minutes is negligible. The infrastructure cost of WebSockets or SSE is not justified for this use case.

### Q: What does `stripAnsi` do and why is it needed?

The backend pipeline prints to stdout with ANSI color codes (e.g., `\x1B[32m` for green text). These codes are meaningful in a terminal emulator but render as garbage characters in an HTML `<pre>` tag. `stripAnsi` removes them with a regex:

```tsx
str.replace(/\x1B\[[0-9;]*[a-zA-Z]/g, "")
```

This regex matches the escape character (`\x1B`), followed by `[`, followed by optional numbers and semicolons, followed by a letter (the command). It covers the vast majority of ANSI escape sequences.

### Q: Why is `pollRun` wrapped in `useCallback`?

`pollRun` is referenced by `handleRunPipeline` and `handleRunStartup`. Without `useCallback`, a new `pollRun` function would be created on every render. While this would not break anything in this case (the handlers are not memoized), `useCallback` with `[]` ensures referential stability and signals to future developers that this function has no reactive dependencies.
