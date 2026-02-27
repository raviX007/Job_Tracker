# 18. Demo Mode Feature Gating

## What Is It

Feature gating is the practice of conditionally enabling or disabling parts of an application based on some flag. In the Job Tracker, we use an environment variable (`NEXT_PUBLIC_DEMO_MODE`) to create a "demo mode" that lets people browse the application and see real data without being able to modify anything. When demo mode is active, mutation-heavy pages (like outcomes and pipeline) are hidden or disabled, while read-only pages (overview, applications, analytics, tracker, startups) remain fully accessible.

The core mechanism is simple: a boolean check against an environment variable, applied at three different levels of the UI.

```
                     NEXT_PUBLIC_DEMO_MODE = "true"
                              |
              +---------------+---------------+
              |               |               |
         Nav Filtering    Early Return    Button Disabling
         (sidebar.tsx)   (outcomes/page)  (emails/page,
                                           pipeline/page)
```

This is the simplest possible form of feature gating -- no feature flag service, no database lookups, no user role checks. Just an env var compared to the string `"true"`.

---

## Why We Chose This

The Job Tracker is a single-user application. There are no user accounts, no roles, no permissions system. But we needed a way to let people explore a deployed demo instance without accidentally (or intentionally) running the pipeline, deleting emails, or modifying application outcomes.

A full feature flag service (like LaunchDarkly, Unleash, or Flagsmith) would be massive overkill for a single boolean flag in a single-user app. Environment variables are:

1. **Zero cost** -- no external service, no API calls, no SDK.
2. **Zero latency** -- the value is inlined at build time, so checking it is just reading a constant.
3. **Obvious** -- any developer reading the code immediately understands `isDemoMode()`.
4. **Deterministic** -- the same build always behaves the same way. No runtime flag changes that could cause inconsistent states.

The trade-off is that changing demo mode requires a new build. For our use case (one demo deployment, one production deployment), this is perfectly fine.

---

## Real Code Examples from the Codebase

### The Gate Function

**File:** `src/hooks/use-profile.tsx`

```typescript
export function isDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_DEMO_MODE === "true";
}
```

This is the single source of truth. Every file that needs to check demo mode imports this function rather than reading the env var directly. This means if we ever change the mechanism (e.g., switch to a cookie or a server-side check), we only change one line.

### Strategy 1: Nav Item Filtering

**File:** `src/components/layout/sidebar.tsx`

```typescript
const NAV_ITEMS = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/applications", label: "Applications", icon: Briefcase },
  { href: "/outcomes", label: "Update Outcomes", icon: ClipboardCheck, hideInDemo: true },
  { href: "/emails", label: "Cold Emails", icon: Mail },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/tracker", label: "Tracker", icon: Table },
  { href: "/pipeline", label: "Pipeline Runner", icon: Play, hideInDemo: true },
  { href: "/startups", label: "Startup Scout", icon: Rocket },
];

const isDemoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
const filteredItems = isDemoMode
  ? NAV_ITEMS.filter((item) => !item.hideInDemo)
  : NAV_ITEMS;
```

Notice:
- `hideInDemo: true` is a declarative flag on the nav item object, not an imperative `if` check.
- The filtering happens once when the component renders, producing `filteredItems` that the JSX maps over.
- Only two items are hidden: Outcomes and Pipeline Runner. These are the write-heavy pages.
- The sidebar reads the env var directly here instead of calling `isDemoMode()` because it needs the value at module level for the component, and the pattern is straightforward enough.

### Strategy 2: Early Return (Full Page Replacement)

**File:** `src/app/outcomes/page.tsx`

```typescript
const demo = isDemoMode();

if (demo) {
  return (
    <div>
      <PageHeader title="Update Outcomes" subtitle="Track application responses" />
      <Card className="border-blue-200 bg-blue-50">
        <CardContent className="py-6">
          <p className="text-sm text-blue-700">
            Outcome updates are disabled in demo mode. Switch to a live profile to update
            application outcomes and log new applications.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
```

This is a guard clause pattern. The check happens before any hooks that depend on non-demo behavior, and the entire page is replaced with an informational card. The user sees the page header (so they know where they are) but the functional content is swapped with an explanation.

The blue color scheme (`border-blue-200 bg-blue-50 text-blue-700`) signals "informational" rather than "error" (red) or "warning" (amber). It is a deliberate choice: being in demo mode is not an error -- it is an expected state.

### Strategy 3: Button Disabling with Tooltip

**File:** `src/app/emails/page.tsx`

```typescript
const demo = isDemoMode();

{/* Edit button */}
<Button
  variant="outline"
  size="sm"
  onClick={() => { /* ... */ }}
  disabled={demo}
  title={demo ? "Disabled in demo mode" : "Edit email"}
>
  Edit
</Button>

{/* Send button */}
<Button
  size="sm"
  onClick={() => sendMutation.mutate({ emailId: email.id })}
  disabled={demo || (sendMutation.isPending && sendMutation.variables?.emailId === email.id)}
  title={demo ? "Disabled in demo mode" : "Send email"}
>
  Send
</Button>

{/* Delete button */}
<Button
  variant="destructive"
  size="sm"
  disabled={demo || (deleteMutation.isPending && deleteMutation.variables === email.id)}
  title={demo ? "Disabled in demo mode" : "Delete email"}
>
  Delete
</Button>
```

Key details:
- `disabled={demo}` -- the simplest case, just disable if in demo mode.
- `disabled={demo || deleteMutation.isPending}` -- demo mode OR an in-flight mutation, either one disables the button.
- `title={demo ? "Disabled in demo mode" : "Delete email"}` -- the HTML `title` attribute creates a native browser tooltip on hover, explaining WHY the button is disabled. This is important for accessibility and UX -- a disabled button with no explanation is frustrating.

### Strategy 4: Warning Banner + Button Disabling

**File:** `src/app/pipeline/page.tsx`

```typescript
const demoMode = isDemoMode();

{demoMode && (
  <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
    Pipeline execution is disabled in demo mode.
  </div>
)}

<Button
  variant="accent"
  onClick={handleRunPipeline}
  disabled={demoMode || pipelineStatus === "running"}
>
  {pipelineStatus === "running" ? "Running..." : "Run Pipeline"}
</Button>
```

The pipeline page uses amber (warning) colors because the page IS visible -- you can see the pipeline configuration, the source groups, the steps -- but you cannot execute it. The amber banner appears at the top of the page and the Run button is disabled.

---

## How It Works -- Full Walkthrough

### Step 1: The Environment Variable

In your `.env` file (or deployment platform environment):

```bash
# Demo deployment
NEXT_PUBLIC_DEMO_MODE=true

# Production deployment (or just omit the variable entirely)
NEXT_PUBLIC_DEMO_MODE=false
```

The `NEXT_PUBLIC_` prefix is a Next.js convention. It tells the Next.js compiler to inline this variable into the client-side JavaScript bundle at build time. Without the prefix, the variable would only be available in server-side code (API routes, `getServerSideProps`, middleware).

### Step 2: Build-Time Inlining

When you run `npm run build`, Next.js replaces every occurrence of `process.env.NEXT_PUBLIC_DEMO_MODE` with the literal string value. In the compiled JavaScript, the code becomes:

```javascript
// What you wrote:
export function isDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_DEMO_MODE === "true";
}

// What ships to the browser (demo build):
export function isDemoMode() {
  return "true" === "true";  // always true
}

// What ships to the browser (production build):
export function isDemoMode() {
  return "false" === "true";  // always false
}
```

This means:
- **You cannot change demo mode at runtime.** It is baked into the build.
- **You need separate builds** for demo and production deployments.
- **The check is essentially free** at runtime -- it is a constant boolean comparison that the JavaScript engine can optimize away.

### Step 3: The isDemoMode() Helper

**File:** `src/hooks/use-profile.tsx`

```typescript
export function isDemoMode(): boolean {
  return process.env.NEXT_PUBLIC_DEMO_MODE === "true";
}
```

Why compare to the string `"true"` instead of just using the value as a boolean? Because environment variables are always strings. `process.env.NEXT_PUBLIC_DEMO_MODE` is `"true"` (a string), not `true` (a boolean). The comparison `=== "true"` is the correct way to convert an env var string to a boolean.

### Step 4: Three Gating Strategies Applied

The application uses three different strategies depending on what makes sense for each page:

| Page | Strategy | Why |
|---|---|---|
| **Outcomes** | Early return (full page replacement) | This page is 100% mutations. There is nothing useful to show in read-only mode. |
| **Pipeline** | Banner + button disabling | The page shows useful information (pipeline steps, source groups) even in demo mode. Only the "Run" action needs to be disabled. |
| **Emails** | Button disabling with tooltips | The email list is useful to browse. Only edit/send/delete actions are disabled. |
| **Outcomes, Pipeline** (sidebar) | Nav filtering (`hideInDemo`) | Users should not see nav links to pages they cannot use. |

### Step 5: Which Pages Are Demo-Safe

| Page | Visible in Demo | Mutations Disabled |
|---|---|---|
| Overview | Yes | N/A (no mutations) |
| Applications | Yes | N/A (read-only) |
| Analytics | Yes | N/A (read-only) |
| Tracker | Yes | N/A (read-only) |
| Startups | Yes | N/A (read-only) |
| Emails | Yes | Edit, Send, Delete disabled |
| Outcomes | Hidden (nav + early return) | All mutations blocked |
| Pipeline | Hidden (nav) + banner | Run button disabled |

---

## Interview Talking Points

1. **"We use environment-based feature gating with NEXT_PUBLIC_DEMO_MODE to disable mutations in our demo deployment. It's a single helper function `isDemoMode()` imported wherever needed."** This shows you can make pragmatic architecture choices.

2. **"The NEXT_PUBLIC_ prefix is critical in Next.js. Without it, the env var is only available on the server. With it, the value is inlined at build time and shipped to the browser."** This shows you understand Next.js internals.

3. **"We use three different gating strategies depending on context: nav filtering removes pages from navigation entirely, early returns replace pages with info cards, and button disabling keeps pages browsable but blocks mutations."** This shows you think about UX, not just code.

4. **"We chose env vars over a feature flag service because this is a single-user app with one boolean flag. A feature flag service would add complexity, cost, and latency for zero benefit."** This shows you evaluate tools against actual requirements.

5. **"Disabled buttons always include a `title` attribute explaining why they are disabled. A disabled button with no explanation is a usability antipattern."** This shows attention to UX details.

6. **"The trade-off is that changing demo mode requires a rebuild. For our deployment model (one demo, one production), this is a perfectly acceptable cost."** This shows you understand and can articulate trade-offs.

---

## Common Questions

### Q: Why NEXT_PUBLIC_ and not just DEMO_MODE?

Next.js has a strict security boundary. Environment variables without the `NEXT_PUBLIC_` prefix are **never** exposed to client-side code. This prevents accidentally leaking secrets (like `DATABASE_URL` or `API_SECRET`) to the browser.

The prefix tells Next.js: "Yes, I intentionally want this value in the browser bundle."

```bash
# Available in server-side code ONLY:
DATABASE_URL=postgres://...
API_SECRET=sk-...

# Available in BOTH server and client code:
NEXT_PUBLIC_DEMO_MODE=true
NEXT_PUBLIC_API_BASE=https://api.example.com
```

### Q: What happens if someone navigates directly to /outcomes in demo mode?

The page still works because the early return in `outcomes/page.tsx` catches it. Even though the nav link is hidden, the route still exists. The user sees the page header and an informational card explaining that outcomes are disabled in demo mode.

This is defense in depth: nav filtering prevents casual discovery, and the early return prevents direct URL access.

### Q: Why not use middleware to block demo routes entirely?

You could add Next.js middleware to redirect `/outcomes` and `/pipeline` to `/overview` when in demo mode. We chose not to because:

1. Middleware adds complexity for a simple use case.
2. The early return pattern gives the user a clear message ("this is disabled in demo mode") rather than a mysterious redirect.
3. The pipeline page is actually useful to view in demo mode (you can see pipeline steps and source groups), so a full redirect would hide useful information.

### Q: Is this secure? Can someone bypass demo mode?

No, this is not a security mechanism. It is a UX mechanism. The API endpoints still exist and could be called directly via curl or browser devtools. If you need actual security (preventing unauthorized mutations), you need server-side authentication and authorization.

For the Job Tracker demo, this is fine. The worst someone can do by bypassing demo mode is run the pipeline or delete emails on a demo database that gets reset periodically.

### Q: Why not use React Context for demo mode instead of env vars?

You could wrap the app in a `<DemoModeProvider>` and use `useContext(DemoModeContext)`. But this would:

1. Add unnecessary runtime overhead (context provider, re-renders on context change).
2. Not work for non-component code (the sidebar reads the env var at module level).
3. Suggest the value can change at runtime, which it cannot (it is baked in at build time).

An env var is the right tool because demo mode is a build-time decision, not a runtime decision.

### Q: How do you test demo mode locally?

Add the variable to your `.env.local` file:

```bash
NEXT_PUBLIC_DEMO_MODE=true
```

Then restart the dev server (`npm run dev`). Next.js only reads env files at startup, not on hot reload.

To test both modes, you can also use the command line:

```bash
# Start in demo mode:
NEXT_PUBLIC_DEMO_MODE=true npm run dev

# Start in normal mode:
npm run dev
```

### Q: Why is the sidebar reading the env var directly instead of using isDemoMode()?

**File:** `src/components/layout/sidebar.tsx`

```typescript
const isDemoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
```

This is a minor inconsistency. The sidebar does the same comparison inline instead of importing the `isDemoMode()` helper. In practice, this works identically since the env var is inlined at build time. However, for consistency and maintainability, importing the helper would be slightly better. The reason it exists this way is that the sidebar was written before the helper was centralized.

### Q: What if I need more than just "demo" vs "not demo"?

If you need multiple feature flags (e.g., `ENABLE_BETA_FEATURES`, `ENABLE_ANALYTICS_V2`), the same pattern scales:

```typescript
export function isBetaEnabled(): boolean {
  return process.env.NEXT_PUBLIC_ENABLE_BETA === "true";
}
```

But if you find yourself managing 10+ feature flags, that is when a dedicated feature flag service (LaunchDarkly, Unleash) starts making sense. The crossover point is roughly when you need runtime toggling, gradual rollouts, or A/B testing.

### Q: Why hide nav items instead of showing them as disabled?

Showing a grayed-out nav link that goes nowhere is worse than not showing it at all. The user sees something that looks like it should work, clicks it, and gets confused. By removing the link entirely, the demo user never thinks "why can't I click this?"

The exception is buttons within pages (like the Send button on emails). Those stay visible-but-disabled because the user is already on the page and has context for why the button exists. Removing the button entirely would make the UI look broken.
