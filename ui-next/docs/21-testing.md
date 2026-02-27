# Testing — Vitest + React Testing Library

## Overview

The UI uses [Vitest](https://vitest.dev/) as the test runner and [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/) for component tests. Tests run in a `jsdom` environment with the `@testing-library/jest-dom` matchers for DOM assertions.

---

## Setup

### Dependencies

| Package | Purpose |
|---------|---------|
| `vitest` | Test runner (Vite-native, Jest-compatible API) |
| `@testing-library/react` | React component rendering and querying |
| `@testing-library/jest-dom` | Custom DOM matchers (`toBeInTheDocument`, `toHaveTextContent`, etc.) |
| `@testing-library/user-event` | Simulating user interactions (click, type, etc.) |
| `@vitejs/plugin-react` | JSX/TSX transform for tests |
| `jsdom` | Browser environment simulation |

### Config files

- **`vitest.config.ts`** — Test runner config: jsdom environment, setup files, path aliases
- **`src/test/setup.ts`** — Global test setup: jest-dom matchers, DOM cleanup, Recharts mock
- **`src/test/test-utils.tsx`** — Shared `renderWithProviders()` wrapper (QueryClient + ProfileProvider)

The Vitest config mirrors `tsconfig.json`'s `@/*` path alias so imports like `@/components/ui/card` resolve correctly in tests.

---

## Running Tests

```bash
# Single run (CI mode)
npm test

# Watch mode (re-runs on file changes)
npm run test:watch

# With coverage report
npm run test:coverage
```

---

## Test File Conventions

- **Location:** Co-located in `__tests__/` directories next to the source
  - `src/lib/__tests__/utils.test.ts` tests `src/lib/utils.ts`
  - `src/hooks/__tests__/use-profile.test.tsx` tests `src/hooks/use-profile.tsx`
  - `src/app/overview/__tests__/page.test.tsx` tests `src/app/overview/page.tsx`
  - `src/components/__tests__/providers.test.tsx` tests `src/components/providers.tsx`
- **Naming:** `*.test.ts` for pure logic, `*.test.tsx` for components
- **Pattern:** Each `describe` block maps to one function or component

---

## What to Test

### Pure utility functions (highest value)

Functions in `src/lib/utils.ts` are pure (no side effects, no DOM). Test all branches:

```typescript
import { describe, it, expect } from "vitest";
import { scoreColor, formatDate } from "../utils";

describe("scoreColor", () => {
  it("returns emerald for scores >= 80", () => {
    expect(scoreColor(85)).toContain("emerald");
  });
});

describe("formatDate", () => {
  it("returns — for null", () => {
    expect(formatDate(null)).toBe("—");
  });
});
```

### Component rendering

Use React Testing Library to render components and assert on the DOM:

```tsx
import { render, screen } from "@testing-library/react";
import { Providers } from "../providers";

it("renders children", () => {
  render(
    <Providers>
      <div data-testid="child">Hello</div>
    </Providers>,
  );
  expect(screen.getByTestId("child")).toBeInTheDocument();
});
```

### Constants and configuration

Verify shape and values of shared constants to catch accidental deletions:

```typescript
import { DECISIONS, CHART_COLORS } from "../constants";

it("has valid hex colors", () => {
  for (const color of CHART_COLORS) {
    expect(color).toMatch(/^#[0-9a-fA-F]{6}$/);
  }
});
```

### Hook tests

Test custom hooks using `renderHook` from `@testing-library/react`:

```typescript
import { renderHook, act } from "@testing-library/react";
import { useDebouncedValue } from "../use-debounced-value";

it("debounces value changes", () => {
  vi.useFakeTimers();
  const { result, rerender } = renderHook(
    ({ value }) => useDebouncedValue(value, 300),
    { initialProps: { value: "hello" } },
  );
  rerender({ value: "world" });
  expect(result.current).toBe("hello"); // not yet updated
  act(() => vi.advanceTimersByTime(300));
  expect(result.current).toBe("world"); // updated after delay
  vi.useRealTimers();
});
```

### Page-level tests with mocked API

Pages use React Query to fetch data. Mock the API module with `vi.mock("@/lib/api")` and use `renderWithProviders()` to wrap components in QueryClient + ProfileProvider:

```tsx
import { vi, describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";

vi.mock("@/lib/api");
import { getOverviewStats } from "@/lib/api";
import OverviewPage from "../page";

const mockGetOverviewStats = vi.mocked(getOverviewStats);

beforeEach(() => vi.resetAllMocks());

it("renders KPI cards", async () => {
  mockGetOverviewStats.mockResolvedValue({ today_jobs: 42, ... });
  renderWithProviders(<OverviewPage />);
  await waitFor(() => {
    expect(screen.getByText("42")).toBeInTheDocument();
  });
});
```

Key patterns:
- `vi.mock("@/lib/api")` — auto-mocks all exports from the API module
- `vi.mocked(fn)` — casts to typed mock for `.mockResolvedValue()`
- `new Promise(() => {})` — never-resolving promise to test loading states
- `mockRejectedValue(new Error("..."))` — test error states
- `userEvent.setup()` — simulate user interactions (click, type)

---

## CI Integration

Tests run automatically in GitHub Actions (`ui-ci.yml`) between lint and build:

```
git push → UI CI triggers
  → npm ci
  → npm run lint    (ESLint)
  → npm test        (Vitest)
  → npm run build   (Next.js production build)
```

If any test fails, the CI pipeline is blocked.

---

## Current Test Coverage

| Test File | What It Tests | Count |
|-----------|---------------|-------|
| `src/lib/__tests__/utils.test.ts` | `scoreColor`, `scoreBadgeColor`, `decisionColor`, `statusColor`, `formatDate`, `formatDateTime`, `stripAnsi` | 32 |
| `src/lib/__tests__/constants.test.ts` | `DECISIONS`, `EMAIL_STATUSES`, `RESPONSE_TYPES`, `APPLICATION_METHODS`, `CHART_COLORS`, `PIPELINE_SOURCES`, `STARTUP_SOURCES` | 11 |
| `src/components/__tests__/providers.test.tsx` | `Providers` renders children with QueryClient | 2 |
| `src/hooks/__tests__/use-profile.test.tsx` | `ProfileProvider`, `useProfile` (localStorage, context), `isDemoMode` | 7 |
| `src/hooks/__tests__/use-debounced-value.test.ts` | `useDebouncedValue` (timing, custom delay) | 3 |
| `src/app/overview/__tests__/page.test.tsx` | Overview page: loading, KPIs, all-time summary, trends, error/retry, top matches | 7 |
| `src/app/applications/__tests__/page.test.tsx` | Applications page: loading, cards, count, empty state, error, filters, details, table view | 8 |
| `src/app/emails/__tests__/page.test.tsx` | Emails page: loading, email cards, status counts, empty state, error | 5 |
| `src/app/analytics/__tests__/page.test.tsx` | Analytics page: loading, 6 chart cards, error state, empty data | 4 |
| `src/app/tracker/__tests__/page.test.tsx` | Tracker page: loading, table data, empty state, error/retry, export, columns | 6 |
| `src/app/outcomes/__tests__/page.test.tsx` | Outcomes page: loading, update tab, log tab, empty states, error/retry, demo mode | 7 |
| `src/app/pipeline/__tests__/page.test.tsx` | Pipeline page: controls, info tables, demo mode, run trigger, running status | 5 |
| `src/app/startups/__tests__/page.test.tsx` | Startups page: loading, KPI stats, cards, filters, empty state, error/retry | 6 |
| **Total** | | **103** |
