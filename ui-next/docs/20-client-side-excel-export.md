# 20. Client-Side Excel Export

## What Is It

The app lets users download spreadsheet files (`.xlsx`) directly from the browser — no server round-trip required. Two pages have an "Export Excel" button:

- **Applications page** → `applications.xlsx` (13 columns: Score, Decision, Company, Title, Source, Location, Remote, Date Posted, Skills Matched, Skills Missing, Company Type, Route, URL)
- **Tracker page** → `tracker.xlsx` (13 columns: Score, Decision, Company, Title, Source, Location, Remote, Method, Platform, Applied At, Response Type, Notes, URL)

The entire export pipeline is **12 lines of code** in a single utility function, powered by the [`xlsx`](https://www.npmjs.com/package/xlsx) library (also known as SheetJS).

---

## Why We Chose This Approach

### Why client-side, not server-side?

| Approach | Pros | Cons |
|----------|------|------|
| **Server-side export** (API returns `.xlsx`) | Works without JS; can handle huge datasets | Adds a new endpoint; server must hold the `xlsx` library; adds latency for the network round-trip |
| **Client-side export** (browser generates `.xlsx`) | Zero backend work; instant response; data is already in memory from React Query cache | Limited by browser memory; requires JS; `xlsx` adds ~200KB to the bundle |
| **CSV download** | Tiny implementation; no library needed | No formatting, no sheet names, poor Excel compatibility with special characters |

We chose **client-side export** because:

1. **The data is already loaded** — React Query has the full page of results in memory. Exporting it means zero additional API calls.
2. **Zero backend changes** — the FastAPI backend doesn't need an export endpoint.
3. **Instant UX** — clicking "Export Excel" triggers an immediate download, no spinner needed.
4. **The dataset is bounded** — pagination limits results to 50 rows per page, well within browser memory.

---

## The Implementation

### The utility function

```typescript
// src/lib/export.ts (complete file — 12 lines)

import * as XLSX from "xlsx";

export function exportToExcel(
  rows: Record<string, unknown>[],
  filename: string,
  sheetName = "Sheet1",
) {
  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, sheetName);
  XLSX.writeFile(wb, filename);
}
```

### How it works, step by step

```
1. json_to_sheet(rows)     → Converts array of objects to a worksheet
                              Object keys become column headers (row 1)
                              Object values become cell values (row 2+)

2. book_new()              → Creates an empty workbook (the .xlsx container)

3. book_append_sheet(wb, ws, "Tracker")
                           → Adds the worksheet to the workbook
                              The third argument becomes the sheet tab name

4. writeFile(wb, "tracker.xlsx")
                           → Serializes the workbook to binary .xlsx format
                              Triggers a browser file download via a Blob URL
                              The user sees a "Save As" dialog or auto-download
```

The key insight: `XLSX.writeFile()` handles the entire browser download mechanism internally — it creates a `Blob`, generates an object URL, creates a hidden `<a>` element, clicks it programmatically, and cleans up. You don't need to manage any of this.

---

## How Each Page Uses It

### Applications page

```typescript
// src/app/applications/page.tsx (lines 345-363)

const handleExport = () => {
  if (applications.length === 0) return;                // Guard: nothing to export
  const rows = applications.map((a) => ({
    Score: a.match_score,
    Decision: a.apply_decision,
    Company: a.company,
    Title: a.title,
    Source: a.source,
    Location: a.location ?? "",                         // Nullish coalescing for clean cells
    Remote: a.is_remote ? "Yes" : "No",                 // Boolean → human-readable string
    "Date Posted": a.date_posted ?? "",
    "Skills Matched": a.skills_matched?.join(", ") ?? "",  // Array → comma-separated string
    "Skills Missing": a.skills_missing?.join(", ") ?? "",
    "Company Type": a.company_type ?? "",
    Route: a.route_action ?? "",
    URL: a.job_url ?? "",
  }));
  exportToExcel(rows, "applications.xlsx", "Applications");
};

// Triggered by a button in the PageHeader
<PageHeader title="Applications" subtitle="Browse analyzed job matches">
  <Button variant="outline" size="sm" onClick={handleExport}>
    Export Excel
  </Button>
</PageHeader>
```

### Tracker page

```typescript
// src/app/tracker/page.tsx (lines 178-196)

onClick={() => {
  if (filteredRows.length === 0) return;                // Uses filteredRows, not raw rows
  const rows = filteredRows.map((r) => ({
    Score: r.match_score,
    Decision: r.apply_decision,
    Company: r.company,
    Title: r.title,
    Source: r.source,
    Location: r.location ?? "",
    Remote: r.is_remote ? "Yes" : "No",
    Method: r.app_method ?? "",                         // Tracker-specific columns
    Platform: r.app_platform ?? "",
    "Applied At": r.applied_at ?? "",
    "Response Type": r.response_type ?? "",
    Notes: r.app_notes ?? "",
    URL: r.job_url ?? "",
  }));
  exportToExcel(rows, "tracker.xlsx", "Tracker");
}}
```

**Key difference:** The Tracker page exports `filteredRows` (which respects the "Show obsolete jobs" checkbox), not the raw `rows` array. This means obsolete jobs are excluded from the export by default — the export reflects what the user sees.

---

## Design Decisions

### 1. Object keys become column headers

```typescript
// This object...
{ Score: 85, Company: "Stripe", "Date Posted": "2024-01-15" }

// ...becomes this row in Excel:
// | Score | Company | Date Posted |
// |  85   | Stripe  | 2024-01-15  |
```

The `json_to_sheet` function uses object keys as column headers automatically. We use human-readable keys (`"Skills Matched"`, not `skills_matched`) so the spreadsheet is immediately usable without renaming columns.

### 2. Data transformation before export

The raw `Application` type has fields like `is_remote: boolean` and `skills_matched: string[]`. These don't display well in Excel, so each page transforms them:

| Raw field | Type | Exported as | Why |
|-----------|------|-------------|-----|
| `is_remote` | `boolean` | `"Yes"` / `"No"` | Excel booleans are confusing (`TRUE`/`FALSE`) |
| `skills_matched` | `string[]` | `"React, TypeScript, Node"` | Arrays can't go in a cell; comma-join is readable |
| `location` | `string \| null` | `""` | `null` would show as empty anyway, but `??` makes it explicit |
| `job_url` | `string \| null` | `""` | Same — empty string instead of `null` |

### 3. No server involvement

The data flow is:

```
React Query cache → .map() transform → exportToExcel() → browser download
     (already loaded)     (instant)        (instant)        (instant)
```

Total time from click to download: **< 50ms** for 50 rows. No loading spinner needed.

### 4. Why `Record<string, unknown>[]`

The function signature uses `Record<string, unknown>[]` instead of a specific type because it's **generic by design**. Both pages pass differently shaped objects (Applications has `Skills Matched`, Tracker has `Method`), so the function accepts any flat object array.

---

## The `xlsx` Library

### Why xlsx (SheetJS)?

| Library | Size | Features | Status |
|---------|------|----------|--------|
| **xlsx / SheetJS** | ~200KB | Read + write `.xlsx`, `.csv`, `.xls`; formatting; streaming | Industry standard, actively maintained |
| `exceljs` | ~400KB | Read + write with more formatting options | Heavier, more features than we need |
| `csv-stringify` | ~10KB | CSV only | No `.xlsx` support |
| Manual CSV | 0KB | Comma-separated text | No sheet names, encoding issues with special chars |

We use `xlsx@^0.18.5`. It's imported as `import * as XLSX from "xlsx"` — the namespace import is required because the library uses a CommonJS-style module structure.

### What `xlsx` handles internally in `writeFile()`

1. Serializes the workbook to the Office Open XML format (`.xlsx` is actually a zip of XML files)
2. Creates a `Blob` with MIME type `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
3. Generates a temporary object URL via `URL.createObjectURL(blob)`
4. Creates a hidden `<a download="filename.xlsx" href="blob:...">` element
5. Programmatically clicks it to trigger the browser's download dialog
6. Revokes the object URL to free memory

All of this happens synchronously in the browser — no web workers, no async, no network.

---

## Interview Talking Points

1. **"Why client-side export?"** — The data is already in the React Query cache. Sending it back to the server just to get a file back would be wasteful. Client-side generation is instant and requires zero backend work.

2. **"How does the browser download work?"** — `XLSX.writeFile()` creates a Blob, generates an object URL, injects a hidden `<a>` tag with the `download` attribute, clicks it programmatically, then cleans up. The `download` attribute tells the browser to save instead of navigate.

3. **"Why not just CSV?"** — CSV has encoding issues with special characters (commas in company names, Unicode), no sheet names, and opens poorly in Excel by default. `.xlsx` is the native Excel format and handles all edge cases.

4. **"What about large datasets?"** — Our pagination caps at 50 rows per page, so memory isn't a concern. For thousands of rows, you'd use `xlsx`'s streaming write mode or move export to the server with `Content-Disposition: attachment` headers.

5. **"Why `Record<string, unknown>[]`?"** — The export function is intentionally generic. Both pages shape their data differently (different columns), so the function accepts any flat object array. The object keys become headers automatically via `json_to_sheet`.

6. **"Why transform data before exporting?"** — Raw types like `boolean` and `string[]` don't display well in spreadsheet cells. We convert `is_remote: true` to `"Yes"` and join arrays with commas for human readability.

---

## Common Questions

**Q: Does the export include ALL data or just the current page?**
A: Just the current page (up to 50 rows). The `applications` and `filteredRows` arrays come from the current React Query cache, which holds one page of results. To export everything, you'd need to fetch all pages first.

**Q: Why does the Tracker use `filteredRows` but Applications uses `applications`?**
A: The Tracker has an "obsolete jobs" toggle that filters rows client-side. Exporting `filteredRows` ensures the spreadsheet matches what the user sees. The Applications page has no client-side filtering (all filters are server-side query params), so `applications` already reflects the filtered view.

**Q: What happens if the user clicks Export with no data?**
A: Both pages guard against this: `if (applications.length === 0) return` and `if (filteredRows.length === 0) return`. The function returns early, and no download is triggered.

**Q: Could we add formatting (bold headers, column widths)?**
A: Yes. `xlsx` supports cell styles, column widths (`ws['!cols']`), and row heights. We kept it minimal because the default output is already usable, and formatting adds complexity without clear user value.

**Q: Does `xlsx` work in all browsers?**
A: Yes. `writeFile()` uses the `Blob` API and `URL.createObjectURL()`, which are supported in all modern browsers (Chrome, Firefox, Safari, Edge). No polyfills needed.

**Q: Why `import * as XLSX` instead of named imports?**
A: The `xlsx` library exports a single namespace object, not individual named exports. The `import * as XLSX` syntax is the standard way to import CommonJS modules that don't have ES module named exports. Tree-shaking still works at the function level within the bundler.
