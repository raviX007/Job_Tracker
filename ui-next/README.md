# Job Tracker — Next.js Frontend

A modern, responsive web dashboard for the Job Tracker system. This frontend replaces the original Streamlit-based UI with a production-ready Next.js application, providing a faster, more interactive experience for managing automated job search workflows.

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Architecture Overview](#architecture-overview)
- [Tech Stack & Why Each Choice](#tech-stack--why-each-choice)
- [Project Structure](#project-structure)
- [Pages & Features](#pages--features)
- [Design System](#design-system)
- [Data Flow](#data-flow)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Docker Deployment](#docker-deployment)
- [Known Limitations](#known-limitations)

---

## Why This Exists

The original Streamlit dashboard worked well for prototyping but had limitations:

| Problem with Streamlit | How Next.js solves it |
|---|---|
| Full page re-renders on every interaction | React's component model — only affected parts update |
| No URL-based routing (hash fragments only) | App Router with clean `/overview`, `/applications` URLs |
| Limited layout control | Full CSS/Tailwind control over responsive layouts |
| Hard to deploy as a standalone service | Docker-friendly standalone build (`node server.js`) |
| No component reuse between pages | Shared components, hooks, and utilities |

The Streamlit code (`job-tracker/ui/`) is untouched — both UIs can run side by side.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                      Browser                             │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Next.js App (localhost:3000)                       │ │
│  │  ┌──────────┐  ┌──────────────────────────────────┐ │ │
│  │  │ Sidebar   │  │  Page Content                    │ │ │
│  │  │ (nav +    │  │  - Fetches data from API         │ │ │
│  │  │  profile  │  │  - Renders with React + Tailwind │ │ │
│  │  │  selector)│  │  - Client-side state management  │ │ │
│  │  └──────────┘  └──────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────┘ │
│                           │ fetch() with X-API-Key       │
│                           ▼                              │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  FastAPI Backend (localhost:8000)                    │ │
│  │  - 47+ REST endpoints                              │ │
│  │  - API key auth via X-API-Key header               │ │
│  │  - PostgreSQL (Neon) for persistence               │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Key architectural decisions:**

1. **Client-side rendering only** — All pages are `"use client"` components that fetch data via the API. No server-side rendering because the data is private (behind API key auth) and changes frequently, so SSR caching would add complexity without benefit.

2. **React Query for server state** — All data fetching uses `@tanstack/react-query` (`useQuery` with signal cancellation, `useMutation` with optimistic updates and rollback). The only shared client state is `profileId` (via React Context). No global store needed.

3. **API client pattern** — A single `lib/api.ts` file wraps all `fetch()` calls with timeout handling, auth headers, and error messages. Pages import individual functions like `getApplications()` rather than constructing URLs themselves.

---

## Tech Stack & Why Each Choice

| Technology | Version | Why |
|---|---|---|
| **Next.js** | 15 | App Router for file-based routing, standalone output mode for Docker |
| **React** | 19 | Latest stable — needed for Next.js 15 compatibility |
| **TypeScript** | 5.7 (strict) | Catches type mismatches between API responses and UI code at build time |
| **Tailwind CSS** | 4 | Utility-first styling without separate CSS files. v4 uses `@theme inline` instead of `tailwind.config.js` |
| **shadcn/ui** | Manual | Pre-built accessible components (Dialog, Select, Tabs) built on Radix UI primitives. Manually created (not CLI-generated) to control exactly what's included |
| **Radix UI** | Various | Headless UI primitives that handle accessibility (keyboard nav, screen readers, focus traps) |
| **class-variance-authority** | 0.7 | Type-safe component variants (e.g., Button with `default`, `destructive`, `outline` variants) |
| **Recharts** | 2.15 | React-native charting for the Analytics page. Composable API, works well with Tailwind |
| **lucide-react** | 0.460 | Icon library used in sidebar navigation. Tree-shakeable — only imports icons actually used |
| **clsx + tailwind-merge** | 2.1 / 2.5 | The `cn()` utility merges Tailwind classes without conflicts (e.g., `cn("px-4", props.className)` properly handles overrides) |
| **@tanstack/react-query** | 5 | Server state management — automatic caching (30s staleTime), query deduplication, `AbortSignal` cancellation on unmount/key change, and `useMutation` with optimistic updates + rollback on error |

### What's NOT used and why

- **Redux / Zustand** — Overkill for this app. Only one piece of shared state (profileId). Server state is handled by React Query.
- **@tanstack/react-table** — Installed but not used. The tracker table uses plain HTML `<table>` with Tailwind because the table is simple enough that the abstraction overhead isn't worth it.

---

## Project Structure

```
ui-next/
├── src/
│   ├── app/                        # Next.js App Router pages
│   │   ├── layout.tsx              # Root layout — fonts, metadata, AppShell wrapper
│   │   ├── page.tsx                # "/" → redirects to /overview
│   │   ├── globals.css             # Tailwind import + design token definitions
│   │   ├── error.tsx                # Global error boundary (auto-wraps all routes)
│   │   ├── overview/page.tsx       # Dashboard with KPIs, trend chart, top matches
│   │   ├── applications/page.tsx   # Browse analyzed jobs with filters
│   │   ├── outcomes/page.tsx       # Update application outcomes / log new apps
│   │   ├── emails/page.tsx         # Email queue management (CRUD + send)
│   │   ├── analytics/page.tsx      # 6 charts: trends, scores, sources, etc.
│   │   ├── tracker/page.tsx        # Editable spreadsheet-style job tracker
│   │   ├── pipeline/page.tsx       # Pipeline runner info (execution disabled)
│   │   └── startups/page.tsx       # Startup profiles with filters
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── app-shell.tsx       # ProfileProvider + Sidebar + main content area
│   │   │   ├── sidebar.tsx         # Fixed left nav with 8 items + profile selector
│   │   │   └── page-header.tsx     # Reusable page title + section headers
│   │   └── ui/                     # shadcn/ui components (11 total)
│   │       ├── button.tsx          # Variants: default, destructive, outline, accent, ghost
│   │       ├── card.tsx            # Card, CardHeader, CardTitle, CardContent, CardFooter
│   │       ├── badge.tsx           # Variants: default, secondary, destructive, outline
│   │       ├── input.tsx           # Standard text input with focus ring
│   │       ├── textarea.tsx        # Multiline text input
│   │       ├── select.tsx          # Radix-based dropdown select
│   │       ├── tabs.tsx            # Radix-based tab panels
│   │       ├── dialog.tsx          # Modal dialog with overlay
│   │       ├── separator.tsx       # Horizontal/vertical divider
│   │       ├── skeleton.tsx        # Loading placeholder with pulse animation
│   │       ├── skeletons.tsx       # Reusable skeleton building blocks (Card, Grid, Table, Chart, KpiRow)
│   │       ├── pagination.tsx      # Page navigation with prev/next + page count
│   │       └── tooltip.tsx         # Hover tooltip
│   │
│   ├── lib/
│   │   ├── api.ts                  # Fetch-based API client (25+ functions) with AbortSignal support
│   │   ├── types.ts                # TypeScript interfaces matching API responses
│   │   ├── query-keys.ts           # React Query key factory for consistent cache management
│   │   ├── utils.ts                # cn(), scoreColor(), formatDate(), etc.
│   │   ├── constants.ts            # Decisions, statuses, sources, chart colors
│   │   └── export.ts               # Excel export utility (applications + tracker)
│   │
│   └── hooks/
│       ├── use-profile.tsx         # ProfileContext + useProfile() hook
│       └── use-debounced-value.ts  # Generic debounce hook for search inputs
│
├── public/
│   └── favicon.svg                 # Navy + teal app icon
│
├── Dockerfile                      # Multi-stage build for production
├── .env.example                    # Template for environment variables
├── next.config.ts                  # Standalone output + security headers
├── tsconfig.json                   # Strict mode, @/* path alias
├── postcss.config.mjs              # @tailwindcss/postcss plugin
└── eslint.config.mjs               # next/core-web-vitals + typescript rules
```

---

## Pages & Features

### 1. Overview (`/overview`)

**Purpose:** At-a-glance dashboard showing today's activity, historical stats, and top job matches.

**API calls:** `getOverviewStats()`, `getDailyTrends()`, `getApplications()` (for top matches)

**Sections:**
- **Today's Activity** — 4 KPI cards with colored top borders (jobs scraped, analyzed, emails queued, applications)
- **All-Time Summary** — 6 metric cards (total jobs, analyzed, avg score, YES count, emails, this week)
- **7-Day Trend** — Recharts AreaChart showing jobs scraped vs analyzed over the past week
- **Top Matches** — Cards showing highest-scoring YES-decision jobs with score badges, company names, and direct links to job postings

### 2. Applications (`/applications`)

**Purpose:** Browse and filter all analyzed job matches.

**API calls:** `getApplications()`, `getSources()`

**Features:**
- **Filter bar** — Min/max score inputs, decision dropdown, source dropdown, debounced text search (400ms delay to avoid excessive API calls)
- **Card view** — Each application shows score circle, decision badge, skills matched (green) / missing (red), collapsible details section with ATS keywords, company type, cover letter
- **Table view** — Compact sortable table with score, decision, company (linked), title, source, date
- **View toggle** — Tabs to switch between card and table layouts

### 3. Update Outcomes (`/outcomes`)

**Purpose:** Track what happened after applying — log interviews, rejections, offers.

**API calls:** `getApplicationsForUpdate()`, `getAnalyzedJobsForUpdate()`, `updateApplicationOutcome()`, `createApplication()`

**Two tabs:**
- **Update Existing** — For each tracked application, set response type (interview/rejection/offer/ghosted), response date, and notes
- **Log New Application** — For analyzed jobs not yet applied to, select method (auto_apply/cold_email/manual) and platform

**Hidden in demo mode** — Shows an info banner instead.

### 4. Cold Emails (`/emails`)

**Purpose:** Manage the automated cold email queue — review, edit, send, or delete emails.

**API calls:** `getEmailQueue()`, `getEmailStatuses()`, `getEmailSources()`, `updateEmailContent()`, `deleteEmail()`, `deleteAllEmails()`, `sendEmail()`

**Features:**
- **Status summary** — Badge row showing counts per status (ready, sent, etc.)
- **Filters** — Status and source dropdowns
- **Email cards** — Expandable cards showing recipient info, company, match score. Collapsible subject + body content
- **Inline editing** — Edit subject and body directly, save changes
- **Actions** — Send (for ready emails), Delete (with confirmation dialog), Delete All (with confirmation)
- **Demo mode** — Send/Edit/Delete buttons disabled

### 5. Analytics (`/analytics`)

**Purpose:** Visualize job search performance with 6 charts.

**API calls:** All 6 analytics endpoints called in parallel via `Promise.all()`

**Charts (2×3 responsive grid):**
1. **Daily Activity Trend** — Stacked AreaChart (jobs scraped, analyzed, emails queued)
2. **Score Distribution** — Donut PieChart with 4 score brackets (0-39, 40-59, 60-79, 80-100)
3. **Source Breakdown** — Horizontal BarChart showing job count per source
4. **Company Types** — Grouped BarChart (total vs gap-tolerant count per company type)
5. **Response Rates** — Stacked BarChart by method (interviews, offers, rejections)
6. **Route Breakdown** — PieChart showing distribution of cold_email vs manual_alert vs auto_apply

### 6. Application Tracker (`/tracker`)

**Purpose:** Spreadsheet-style view for managing application status across all jobs.

**API calls:** `getTrackerData()`, `upsertApplication()`, `markJobObsolete()`

**Features:**
- **Full-width data table** — Navy header, alternating rows, horizontal scroll on small screens
- **Read-only columns** — Score (badge), Decision (badge), Company (linked), Title, Source
- **Editable columns** — Method (select), Platform (text), Status/Response Type (select), Notes (text)
- **Row actions** — Save (calls upsert API), Mark Obsolete (grays out the row)
- **Obsolete toggle** — Checkbox to show/hide obsolete jobs
- **Visual feedback** — Green highlight flash on successful save, opacity reduction for obsolete rows

### 7. Pipeline Runner (`/pipeline`)

**Purpose:** Information page about the job scraping pipeline. Execution buttons are disabled (backend scripts not yet deployed).

**Sections:**
- **Main Pipeline** — Source selector + limit input (buttons disabled with info banner)
- **Startup Scout** — Same pattern for startup discovery
- **Pipeline Information** — Static reference tables: pipeline steps, source groups with auth requirements, startup scout steps, startup sources

### 8. Startup Scout (`/startups`)

**Purpose:** Discover and browse early-stage startup profiles with rich metadata.

**API calls:** `getStartupProfiles()`, `getStartupProfileStats()`, `getStartupProfileSources()`

**Features:**
- **Stats summary** — 4 KPI cards (total startups, avg completeness, top source count, funded count)
- **Filter bar** — Source, funding round, min/max age (months), search, sort by
- **Startup cards** — Company name (linked), one-liner, founding date, age, employees, funding info, data completeness progress bar
- **Founder section** — Names, roles, email links
- **Tech stack / Topics** — Badge chips
- **External links** — Website, YC Profile, ProductHunt, Job Listing buttons
- **Cold Email tab** — If an email exists for this startup, shows subject + body in a separate tab

---

## Design System

### Color Palette

| Token | Hex | Usage |
|---|---|---|
| `primary` | `#1e3a5f` | Navy — sidebar gradient end, headings, badges |
| `accent` | `#00d4aa` | Teal — active nav highlight, KPI card borders, chart color 1 |
| `sidebar` | `#0f1b2d` | Dark navy — sidebar gradient start |
| `destructive` | `#e74c3c` | Red — delete buttons, error states |
| `chart-3` | `#f5a623` | Amber — warnings, chart color 3 |
| `chart-5` | `#8e44ad` | Purple — chart color 5 |
| `chart-6` | `#3498db` | Blue — chart color 6 |

### Score Color Coding

Scores (0-100) use consistent color coding across all pages:

| Range | Color | Meaning |
|---|---|---|
| 80-100 | Green (`bg-emerald-500`) | Strong match |
| 60-79 | Teal (`bg-teal-500`) | Good match |
| 40-59 | Amber (`bg-amber-500`) | Possible match |
| 0-39 | Red (`bg-red-500`) | Weak match |

### Decision Badge Colors

| Decision | Style |
|---|---|
| YES | Green background |
| MAYBE | Amber background |
| MANUAL | Purple background |
| NO | Red background |

### Layout

- **Sidebar** — Fixed left, 256px wide (`w-64`), full height, navy gradient
- **Content area** — Left margin 256px (`ml-64`), max-width with padding, scrollable
- **Responsive** — Grid layouts adapt: 1 col (mobile) → 2 col (tablet) → 4-6 col (desktop)

---

## Data Flow

```
User interacts with page
        │
        ▼
Page component (e.g., overview/page.tsx)
        │
        ├── useProfile() hook → reads profileId from Context
        │
        ├── useQuery({ queryKey, queryFn: ({ signal }) => ... })
        │       │
        │       ├── React Query checks cache (staleTime: 30s)
        │       │   ├── Cache fresh → return cached data immediately
        │       │   └── Cache stale/missing → call queryFn
        │       │
        │       ▼
        │   lib/api.ts function (e.g., getOverviewStats)
        │       │
        │       ├── Constructs URL: API_BASE + path + query params
        │       ├── Adds headers: X-API-Key, Content-Type
        │       ├── Sets 60-second abort timeout
        │       ├── Links AbortSignal from React Query → cancels on unmount/key change
        │       │
        │       ▼
        │   fetch() → FastAPI backend (localhost:8000)
        │       │
        │       ├── Success → JSON parsed → cache updated → component re-renders
        │       └── Error → error object → component shows error state
        │
        ├── useMutation({ mutationFn, onMutate, onError, onSettled })
        │       │
        │       ├── onMutate: cancel queries → snapshot cache → apply optimistic update
        │       ├── onError: rollback cache to snapshot
        │       ├── onSuccess: show feedback (flash / toast)
        │       └── onSettled: invalidateQueries → refetch fresh data
        │
        └── React re-renders with updated state
```

### Error Handling Strategy

Every page follows the same pattern:

1. **Loading state** — Reusable skeleton building blocks (SkeletonCard, SkeletonGrid, SkeletonTable, SkeletonChart, SkeletonKpiRow) matching each page's layout to prevent layout shift
2. **Error state** — Red-bordered card with error message + Retry button
3. **Empty state** — Neutral card with "No data found" message + suggestion
4. **Loaded state** — Actual content
5. **Error boundary** — `app/error.tsx` catches unhandled render errors at the route level. Shows a "Something went wrong" card with a "Try again" button that re-renders the route segment without a full page reload. Error details are shown only in development mode.

---

## Getting Started

### Prerequisites

- Node.js 22+
- The FastAPI backend running on `localhost:8000`

### Install & Run

```bash
cd job-tracker/ui-next

# Install dependencies
npm install

# Start dev server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) — it redirects to `/overview`.

### Build for Production

```bash
npm run build    # Creates standalone output in .next/
npm run start    # Starts production server on port 3000
```

---

## Environment Variables

Create a `.env` file (see `.env.example`):

```env
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000

# API key matching the backend's API_SECRET_KEY
NEXT_PUBLIC_API_KEY=your-api-key-here

# Set to "true" to hide write operations (outcomes, pipeline, send/delete)
NEXT_PUBLIC_DEMO_MODE=false
```

All variables are prefixed with `NEXT_PUBLIC_` because they're used in client-side code (the browser needs to know the API URL and key).

---

## Docker Deployment

```bash
docker build -t job-tracker-ui .
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=https://your-api.example.com \
  -e NEXT_PUBLIC_API_KEY=your-key \
  job-tracker-ui
```

The Dockerfile uses a multi-stage build:

1. **Builder stage** — `node:22-slim`, installs deps, runs `npm run build`
2. **Runner stage** — Copies only the standalone output (no `node_modules`), runs as non-root `nextjs` user

The standalone output is ~5MB of JS (vs ~200MB with full `node_modules`).

---

## Known Limitations

1. **Pipeline Runner** — Buttons are disabled. The backend pipeline scripts (`dry_run.py`) are not deployed. Run pipeline scripts directly from CLI.

2. **Excel Export** — Export buttons on Applications and Tracker pages use the `xlsx` package to generate `.xlsx` files client-side.

3. **No real-time updates** — React Query caches data with a 30-second staleTime and refetches on window focus, but there's no WebSocket/SSE push. For truly live data, manually refresh or trigger a refetch.

4. **Single profile** — The profile ID selector at the bottom of the sidebar switches between profiles, but there's no profile management (create/delete). Profile IDs must exist in the backend database.

5. **No authentication** — The app relies on the API key in the `.env` file. There's no login page or user sessions. Anyone with access to the URL can view the dashboard.
