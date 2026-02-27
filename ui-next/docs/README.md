# Technical Deep Dives -- Job Tracker UI

These docs explain the advanced patterns and design decisions in this Next.js frontend. Written as study notes for understanding the "why" behind each architectural choice.

## Architecture & Data Management
1. [React Query Architecture](./01-react-query-architecture.md) -- Why useQuery/useMutation over raw useEffect
2. [Optimistic Updates](./02-optimistic-updates.md) -- Instant UI with rollback on failure
3. [API Client Design](./03-api-client-design.md) -- Centralized fetch wrapper with timeout + auth

## Request Lifecycle
4. [AbortSignal & Request Cancellation](./04-abort-signal-cancellation.md) -- Cancelling stale requests on navigation
5. [Error Handling Strategy](./05-error-handling-strategy.md) -- 5-layer error handling from network to UI

## UI Patterns
6. [Skeleton Loading System](./06-skeleton-loading-system.md) -- Reusable loading states that prevent layout shift
7. [Custom Hooks](./07-custom-hooks.md) -- useDebouncedValue, useProfile, and the hooks philosophy

## Code Quality
8. [TypeScript Patterns](./08-typescript-patterns.md) -- Generics, discriminated unions, and strict mode
9. [State Management Philosophy](./09-state-management-philosophy.md) -- Why no Redux, server state vs client state
10. [Design System & Component Patterns](./10-design-system-and-component-patterns.md) -- CVA, cn(), Radix UI, and composable components

## Data Visualization & Async Patterns
11. [Recharts Data Visualization](./11-recharts-data-visualization.md) -- 7 charts across 2 pages: area, pie, bar, donut
12. [setInterval Long Polling](./12-setinterval-long-polling.md) -- Pipeline status polling with useRef + useCallback
13. [Parallel Data Fetching](./17-parallel-data-fetching.md) -- Promise.all inside queryFn for batched API calls

## Framework & Deployment
14. [Next.js App Router Conventions](./13-nextjs-app-router-conventions.md) -- Layout, error boundary, fonts, server redirect
15. [Production Deployment & Security](./14-production-deployment-security.md) -- Security headers, standalone build, Docker
16. [Tailwind CSS v4 Migration](./15-tailwind-v4-migration.md) -- @theme inline, no config file, CSS-first tokens

## Infrastructure Patterns
17. [Pagination Architecture](./16-pagination-architecture.md) -- X-Total-Count headers, PaginatedResult<T>, per-page caching
18. [Demo Mode Feature Gating](./18-demo-mode-feature-gating.md) -- NEXT_PUBLIC_ env vars, nav filtering, button disabling
19. [forwardRef & Radix Slot](./19-forwardref-radix-slot.md) -- Polymorphic components with asChild and ComponentRef
20. [Client-Side Excel Export](./20-client-side-excel-export.md) -- Browser-based .xlsx generation with SheetJS

## Testing
21. [Testing](./21-testing.md) -- Vitest + React Testing Library setup, writing tests, CI integration

## Full-Stack Features
22. [View-Only Access Control](./22-view-only-access-control.md) -- Role-based edit/view with JWT, require_editor, and UI disabling
23. [Resume Extraction Pipeline](./23-resume-extraction-pipeline.md) -- PDF/LaTeX → OpenAI vision → structured outputs → auto-save
24. [Global Upload State Management](./24-global-upload-state-management.md) -- React Context for persistent upload state across navigations

## Project Stats
- **37 TypeScript files** across 8 pages, 13 UI components, 6 lib modules, 3 hooks
- **8 mutations** with optimistic updates across 3 pages
- **16 GET functions** with AbortSignal cancellation
- **5 reusable skeleton** building blocks serving 7 pages
- **Zero build errors**, zero unused imports
