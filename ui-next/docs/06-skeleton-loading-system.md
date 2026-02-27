# 06 - Skeleton Loading System: Reusable Building Blocks

## What Is This?

Skeleton loading (also called "shimmer loading" or "content placeholders") is a technique where
the loading state of a page shows grey animated rectangles that **match the layout of the final
content**. Instead of a spinning wheel or a blank screen, the user sees the approximate shape of
what's about to appear.

This document covers why skeleton loading is better than spinners, how we consolidated 7 pages
worth of custom skeleton components into 5 reusable building blocks, and the design principle
("composition over configuration") that made it work.

---

## The Problem We Solved

### Before: 7 pages, 7 custom skeletons, ~180 lines of duplicated code

Every page in our app had its own hand-written skeleton component. Each one was 20-50 lines of
JSX that created Card components filled with Skeleton rectangles. Here's what the Tracker page's
skeleton used to look like (reconstructed from the old approach):

```typescript
// BEFORE: TrackerSkeleton was ~43 lines of custom JSX
function TrackerSkeleton() {
  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-primary text-white text-xs uppercase">
              <tr>
                <th className="px-3 py-2.5 text-left">Score</th>
                <th className="px-3 py-2.5 text-left">Decision</th>
                <th className="px-3 py-2.5 text-left">Company</th>
                <th className="px-3 py-2.5 text-left">Title</th>
                <th className="px-3 py-2.5 text-left">Source</th>
                <th className="px-3 py-2.5 text-left">Method</th>
                <th className="px-3 py-2.5 text-left">Platform</th>
                <th className="px-3 py-2.5 text-left">Status</th>
                <th className="px-3 py-2.5 text-left">Notes</th>
                <th className="px-3 py-2.5 text-left">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {Array.from({ length: 8 }).map((_, i) => (
                <tr key={i}>
                  {Array.from({ length: 10 }).map((_, j) => (
                    <td key={j} className="px-3 py-2.5">
                      <Skeleton className="h-5 w-full" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
```

The problems:
1. **Duplication** -- Every page copy-pasted similar structures with slight variations
2. **Inconsistency** -- Different pages used different spacing, padding, and skeleton dimensions
3. **Maintenance burden** -- If we changed the Card component's styling, we had to update every
   skeleton to match
4. **Hard to get right** -- Each new page meant writing another 30+ line skeleton from scratch

### After: 5 building blocks, 1-line compositions

```typescript
// AFTER: TrackerSkeleton is 1 line
function TrackerSkeleton() {
  return <SkeletonTable rows={8} columns={TRACKER_COLUMNS} />;
}
```

The total lines in `skeletons.tsx` is 169. It replaces ~180 lines across 7 pages, with the
added benefit that every skeleton is **consistent** and **configurable**.

---

## Why We Chose This Approach

### Loading states: Spinners vs Blank Screens vs Skeletons

| Approach | Problem |
|---|---|
| **Spinner** (centered loading wheel) | Tells the user "something is loading" but gives no hint about what. The user stares at a spinning circle and has no idea what to expect. When content loads, the entire page appears at once, causing a jarring shift. |
| **Blank screen** (no loading indicator) | The user thinks the app is broken. They might click away or refresh before data arrives. |
| **Progress bar** (linear indicator at top) | Better than a spinner -- it shows progress. But like spinners, it doesn't preview the content layout. When content appears, it's still a sudden shift. |
| **Skeleton loading** | Shows the approximate layout of the final content. The user's brain starts processing the page structure before data arrives. When content loads, elements appear in place (no layout shift). |

### Why skeletons prevent Cumulative Layout Shift (CLS)

**Cumulative Layout Shift (CLS)** is one of Google's **Core Web Vitals** -- metrics that affect
SEO ranking. CLS measures how much visible content shifts during page load. High CLS means
elements jump around as the page loads, which is frustrating and disorienting.

When you use a spinner that gets replaced by content, the transition causes massive layout shift
(CLS score > 0.25, which Google considers "poor"). When you use a skeleton that matches the
content's dimensions, the skeleton-to-content transition causes minimal shift (CLS score ~ 0).

This matters for SEO, but it also matters for UX: users perceive skeleton-loaded pages as
**faster** than spinner-loaded pages, even when the actual load time is identical. This is because
the skeleton gives the brain something to process while waiting.

---

## How It Works In Our App

### The Foundation: The Skeleton Primitive

Everything is built on a single primitive component from shadcn/ui:

```typescript
// From src/components/ui/skeleton.tsx
import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} {...props} />;
}

export { Skeleton };
```

This is just a `<div>` with three Tailwind classes:
- `animate-pulse` -- the shimmer animation (opacity fades between 100% and 50%)
- `rounded-md` -- rounded corners to match our Card styling
- `bg-muted` -- a neutral grey background

Every building block composes this primitive with different dimensions and layouts.

---

### Building Block 1: SkeletonCard

**Purpose:** A single card with configurable content lines, optional header, and optional avatar.

```typescript
// From src/components/ui/skeletons.tsx
interface SkeletonCardProps {
  lines?: number;
  header?: boolean;
  avatar?: boolean;
  className?: string;
}

export function SkeletonCard({
  lines = 3,
  header = true,
  avatar = false,
  className,
}: SkeletonCardProps) {
  return (
    <Card className={className}>
      {header && (
        <CardHeader className="pb-2">
          <Skeleton className="h-4 w-24" />
        </CardHeader>
      )}
      <CardContent className={cn("space-y-2", !header && "pt-6")}>
        {avatar && (
          <div className="flex items-center gap-3">
            <Skeleton className="h-9 w-9 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-48" />
            </div>
          </div>
        )}
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton
            key={i}
            className={cn("h-4", i === lines - 1 ? "w-3/4" : "w-full")}
          />
        ))}
      </CardContent>
    </Card>
  );
}
```

**Design details:**
- The last line is `w-3/4` (75% width) instead of `w-full`. This makes the skeleton look more
  natural -- real text paragraphs rarely end at the exact right edge.
- The avatar variant renders a circle + two lines (name + subtitle), mimicking the pattern used
  in the Applications page cards.
- `!header && "pt-6"` adds top padding when there's no header, matching the Card component's
  default content spacing.

**Used in:**
- Emails page: `<SkeletonCard lines={2} />` (3 cards in a loop)
- Outcomes page: `<SkeletonCard lines={3} />` and `<SkeletonCard lines={2} />`

```typescript
// From src/app/emails/page.tsx
function EmailsSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-6 w-20 rounded-full" />
        ))}
      </div>
      <Card>
        <CardContent className="flex items-center gap-4 py-4">
          <Skeleton className="h-9 w-40" />
          <Skeleton className="h-9 w-40" />
        </CardContent>
      </Card>
      {Array.from({ length: 3 }).map((_, i) => (
        <SkeletonCard key={i} lines={2} />
      ))}
    </div>
  );
}
```

```typescript
// From src/app/outcomes/page.tsx
function UpdateSkeleton() {
  return (
    <div className="space-y-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <SkeletonCard key={i} lines={3} />
      ))}
    </div>
  );
}
```

---

### Building Block 2: SkeletonGrid

**Purpose:** Renders N cards in a responsive CSS grid. This is a thin wrapper over SkeletonCard
that handles the grid layout.

```typescript
// From src/components/ui/skeletons.tsx
interface SkeletonGridProps {
  count?: number;
  columns?: string;
  cardProps?: Omit<SkeletonCardProps, "className">;
}

export function SkeletonGrid({
  count = 6,
  columns = "grid-cols-1 md:grid-cols-2",
  cardProps,
}: SkeletonGridProps) {
  return (
    <div className={cn("grid gap-4", columns)}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} {...cardProps} />
      ))}
    </div>
  );
}
```

**Design details:**
- `columns` is a string of Tailwind grid classes, not a number. This lets pages specify
  responsive breakpoints: `"grid-cols-1 md:grid-cols-2"` means 1 column on mobile, 2 on
  medium screens.
- `cardProps` is spread onto each SkeletonCard, so you can customize lines, header, and avatar
  for all cards in the grid.

**Used in:**
- Applications page: `<SkeletonGrid count={6} cardProps={{ avatar: true, lines: 1, header: false }} />`
- Overview page: `<SkeletonGrid count={4} cardProps={{ header: false, lines: 2 }} />`
- Startups page: `<SkeletonGrid count={3} columns="grid-cols-1" cardProps={{ header: false, lines: 4 }} />`

```typescript
// From src/app/applications/page.tsx
function ApplicationsSkeleton() {
  return <SkeletonGrid count={6} cardProps={{ avatar: true, lines: 1, header: false }} />;
}
```

The `avatar: true` option matches the Applications page layout where each card starts with a
circular score badge next to the company name. The skeleton's circular avatar placeholder
(9x9 rounded-full) matches the actual score circle dimensions exactly.

```typescript
// From src/app/startups/page.tsx
function StartupsSkeleton() {
  return (
    <div className="space-y-6">
      <SkeletonKpiRow count={4} />
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-wrap gap-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-40" />
            ))}
          </div>
        </CardContent>
      </Card>
      <SkeletonGrid count={3} columns="grid-cols-1" cardProps={{ header: false, lines: 4 }} />
    </div>
  );
}
```

---

### Building Block 3: SkeletonTable

**Purpose:** A table skeleton with real column headers and shimmer rows. The headers use the
same styling as the real table, so the transition from skeleton to data is seamless.

```typescript
// From src/components/ui/skeletons.tsx
interface SkeletonTableProps {
  rows?: number;
  columns?: string[] | number;
}

export function SkeletonTable({
  rows = 8,
  columns = 6,
}: SkeletonTableProps) {
  const colArray =
    typeof columns === "number"
      ? Array.from({ length: columns }, (_, i) => `Col ${i + 1}`)
      : columns;

  return (
    <Card>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-primary text-white text-xs uppercase">
              <tr>
                {colArray.map((col) => (
                  <th key={col} className="px-3 py-2.5 text-left">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {Array.from({ length: rows }).map((_, i) => (
                <tr key={i}>
                  {colArray.map((_, j) => (
                    <td key={j} className="px-3 py-2.5">
                      <Skeleton className="h-5 w-full" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
```

**Design details:**
- `columns` accepts either a **number** (generates generic "Col 1", "Col 2" headers) or a
  **string array** (uses the actual column names). When you pass real column names, the skeleton
  header is identical to the loaded table header, so there's zero layout shift on the header row.
- The `thead` uses `bg-primary text-white text-xs uppercase` -- the exact same classes as the
  real Tracker table header. This means the header renders immediately and stays in place; only
  the body transitions from skeletons to data.
- Each skeleton cell is `h-5 w-full`, matching the typical text height in table rows.

**Used in:**
- Tracker page: `<SkeletonTable rows={8} columns={TRACKER_COLUMNS} />`

```typescript
// From src/app/tracker/page.tsx
const TRACKER_COLUMNS = [
  "Score", "Decision", "Company", "Title", "Source",
  "Method", "Platform", "Status", "Notes", "Actions",
];

function TrackerSkeleton() {
  return <SkeletonTable rows={8} columns={TRACKER_COLUMNS} />;
}
```

**Before vs After:**
- Before: The TrackerSkeleton was ~43 lines of hand-written JSX that duplicated the table
  structure, header styling, and row generation.
- After: It's 1 line. The actual column names ("Score", "Decision", etc.) are defined once as a
  constant and shared between the skeleton and the real table.

---

### Building Block 4: SkeletonChart

**Purpose:** A card with an optional title skeleton and a large rectangular skeleton for the
chart area.

```typescript
// From src/components/ui/skeletons.tsx
interface SkeletonChartProps {
  height?: string;
  showTitle?: boolean;
}

export function SkeletonChart({
  height = "h-[280px]",
  showTitle = true,
}: SkeletonChartProps) {
  return (
    <Card>
      {showTitle && (
        <CardHeader>
          <Skeleton className="h-5 w-40" />
        </CardHeader>
      )}
      <CardContent>
        <Skeleton className={cn(height, "w-full rounded-lg")} />
      </CardContent>
    </Card>
  );
}
```

**Design details:**
- The default height `h-[280px]` matches the `height={280}` used in Recharts' `ResponsiveContainer`
  across the Analytics page. This ensures the skeleton and the chart occupy the exact same space.
- `showTitle` is configurable because some chart cards have titles (Analytics page) while others
  don't (Overview page's inline trend chart).
- The skeleton uses `rounded-lg` for slightly more rounded corners than the default `rounded-md`,
  because chart areas tend to have softer shapes.

**Used in:**
- Analytics page: 6 chart skeletons in a grid
- Overview page: 1 chart skeleton for the 7-day trend

```typescript
// From src/app/analytics/page.tsx
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
```

```typescript
// From src/app/overview/page.tsx (inside OverviewSkeleton)
<SkeletonChart height="h-48" showTitle={false} />
```

The Overview page uses `h-48` (192px) instead of the default `h-[280px]` because its trend chart
is shorter (it uses `height={240}` for the ResponsiveContainer, and the skeleton accounts for
padding differences).

---

### Building Block 5: SkeletonKpiRow

**Purpose:** A row of KPI cards that match the stats/metric layout used on overview and summary
sections.

```typescript
// From src/components/ui/skeletons.tsx
interface SkeletonKpiRowProps {
  count?: number;
  columns?: string;
}

export function SkeletonKpiRow({
  count = 4,
  columns = "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4",
}: SkeletonKpiRowProps) {
  return (
    <div className={cn("grid gap-4", columns)}>
      {Array.from({ length: count }).map((_, i) => (
        <Card key={i}>
          <CardHeader className="pb-2">
            <Skeleton className="h-4 w-24" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-8 w-16" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

**Design details:**
- The header skeleton (`h-4 w-24`) matches the KPI label text size and typical width
  (e.g., "Jobs Scraped", "Avg Score").
- The content skeleton (`h-8 w-16`) matches the large number display (e.g., "1,234"), which
  uses `text-3xl font-bold` in the actual KpiCard component.
- `columns` is a responsive grid string, just like SkeletonGrid. The default `lg:grid-cols-4`
  matches the Overview page's 4-column KPI layout.

**Used in:**
- Overview page: Two KPI rows with different configurations
- Startups page: One KPI row for stats

```typescript
// From src/app/overview/page.tsx (inside OverviewSkeleton)
function OverviewSkeleton() {
  return (
    <div className="space-y-8">
      <SkeletonKpiRow count={4} />
      <SkeletonKpiRow count={6} columns="grid-cols-2 sm:grid-cols-3 lg:grid-cols-6" />
      <SkeletonChart height="h-48" showTitle={false} />
      <SkeletonGrid count={4} cardProps={{ header: false, lines: 2 }} />
    </div>
  );
}
```

This single `OverviewSkeleton` function composes **3 different building blocks** (KpiRow, Chart,
Grid) to match the Overview page's complex layout. The skeleton mirrors the real page:
1. 4 KPI cards (Today's Activity)
2. 6 compact KPI cards (All-Time Summary)
3. 1 trend chart (7-Day Trend)
4. 4 content cards (Top Matches)

---

## The Design Principle: Composition Over Configuration

We could have built one mega-component like `<UniversalSkeleton type="table" rows={8} columns={10} />`
with a massive switch statement inside. Instead, we built 5 small, focused building blocks that
each do **one thing**.

The building blocks are **generic** -- they know nothing about applications, emails, or trackers.
The **composition** is page-specific -- each page's skeleton function combines building blocks
in the layout that matches its content.

```
Building blocks (generic):          Page skeletons (specific):
┌──────────────────┐               ┌────────────────────────────────────┐
│ SkeletonCard     │               │ OverviewSkeleton                   │
│ SkeletonGrid     │    compose    │   = KpiRow + KpiRow + Chart + Grid │
│ SkeletonTable    │ ──────────>   │ TrackerSkeleton                    │
│ SkeletonChart    │               │   = Table(columns=TRACKER_COLUMNS) │
│ SkeletonKpiRow   │               │ ApplicationsSkeleton               │
└──────────────────┘               │   = Grid(avatar=true)              │
                                   │ AnalyticsSkeleton                  │
                                   │   = 6x Chart in a grid             │
                                   └────────────────────────────────────┘
```

### Why we kept thin wrapper functions in each page

You might wonder: "Why not just inline `<SkeletonTable rows={8} columns={TRACKER_COLUMNS} />`
directly in the page component?" We keep the wrapper functions for two reasons:

1. **Readability** -- `{loading && <TrackerSkeleton />}` is immediately clear about what it does.
   `{loading && <SkeletonTable rows={8} columns={TRACKER_COLUMNS} />}` requires you to understand
   the props to know what it renders.

2. **Complex compositions** -- The OverviewSkeleton combines 4 building blocks. Inlining all of
   that inside the page component's return statement would make the JSX much harder to read.
   Extracting it into a named function keeps the page's render logic clean.

### Why skeleton dimensions matter

If the skeleton is shorter than the real content, the page will "jump" when data loads (content
pushes everything below it down). If the skeleton is taller, the page will "shrink" when data
loads. Both are jarring.

Our building blocks are calibrated to match real content dimensions:
- `SkeletonCard` lines are `h-4` (16px), matching `text-sm` body text
- `SkeletonChart` defaults to `h-[280px]`, matching Recharts' 280px height
- `SkeletonKpiRow` content is `h-8` (32px), matching `text-3xl` number displays
- `SkeletonTable` cells are `h-5` (20px), matching table row text height

When these are calibrated correctly, the skeleton-to-content transition is nearly imperceptible --
grey boxes simply "fill in" with colored text and data, and nothing moves.

---

## Summary of All Skeleton Usages Across Pages

| Page | Skeleton Function | Building Blocks Used |
|---|---|---|
| Overview | `OverviewSkeleton` | `SkeletonKpiRow` x2, `SkeletonChart`, `SkeletonGrid` |
| Applications | `ApplicationsSkeleton` | `SkeletonGrid` (with avatar) |
| Emails | `EmailsSkeleton` | `SkeletonCard` x3 (plus custom pill + filter skeletons) |
| Outcomes | `UpdateSkeleton`, `LogSkeleton` | `SkeletonCard` x4 (3-line), `SkeletonCard` x4 (2-line) |
| Analytics | inline | `SkeletonChart` x6 in a grid |
| Tracker | `TrackerSkeleton` | `SkeletonTable` (with actual column names) |
| Startups | `StartupsSkeleton` | `SkeletonKpiRow`, custom filter skeleton, `SkeletonGrid` |

---

## The Key Insight

Skeleton loading is not just a visual nicety -- it is a **performance optimization** that
affects both perceived speed and measurable Core Web Vitals. By matching the skeleton dimensions
to the final content dimensions, we achieve near-zero Cumulative Layout Shift, which improves
both user experience and SEO ranking.

The 5 building blocks replaced ~180 lines of duplicated skeleton code with ~169 lines of shared,
configurable code. But the real win is not the line count -- it's that every new page can get a
perfectly matching skeleton in 1-3 lines by composing existing building blocks, instead of
writing 30+ lines of custom JSX from scratch.

The pattern is: **generic building blocks + page-specific composition**. The building blocks
handle the "how" (rendering cards, grids, tables, charts). The page skeletons handle the "what"
(which building blocks in what arrangement). This is the same principle as React itself:
small, reusable components composed into larger structures.

---

## Interview Talking Points

- "We have 5 reusable skeleton building blocks: SkeletonCard, SkeletonGrid, SkeletonTable,
  SkeletonChart, and SkeletonKpiRow. Each page composes these into a page-specific skeleton
  that matches its content layout."

- "We chose skeleton loading over spinners because skeletons prevent Cumulative Layout Shift,
  which is a Core Web Vital that Google uses for SEO ranking. Skeletons match the content
  dimensions, so when data loads, nothing moves."

- "The SkeletonTable component accepts either a number or a string array for columns. When you
  pass actual column names like we do on the Tracker page, the skeleton header is identical to
  the real table header, so there's zero header-level layout shift."

- "Before the refactor, we had ~180 lines of duplicated skeleton code across 7 pages. After
  extracting 5 building blocks into skeletons.tsx (169 lines), each page skeleton is 1-5 lines.
  The Tracker skeleton went from ~43 lines to 1 line."

- "We follow 'composition over configuration' -- each building block does one thing, and pages
  compose them. The OverviewSkeleton, for example, combines SkeletonKpiRow, SkeletonChart, and
  SkeletonGrid in one function to match the overview page's complex layout."

- "The base Skeleton primitive from shadcn/ui is just a div with animate-pulse, rounded-md,
  and bg-muted. All 5 building blocks compose this same primitive with different dimensions and
  layouts."

- "Skeleton dimensions are carefully calibrated. SkeletonChart defaults to h-[280px] because
  that's the exact height Recharts uses for ResponsiveContainer. SkeletonKpiRow uses h-8 for
  the value because that matches text-3xl. If these don't match, you get layout shift."

- "We keep thin wrapper functions like TrackerSkeleton in each page file rather than inlining
  the building block calls. This improves readability and allows complex pages like Overview to
  compose multiple building blocks in a named, documented function."
