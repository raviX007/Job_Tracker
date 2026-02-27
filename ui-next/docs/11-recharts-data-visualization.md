# Recharts Data Visualization

## What Is It

Recharts is a composable charting library built on React components and D3.js. Instead of calling imperative drawing APIs, you declare charts using JSX -- `<BarChart>`, `<PieChart>`, `<AreaChart>` -- and Recharts handles SVG rendering, scales, axes, and animations under the hood.

This project uses Recharts to render **7 charts across 2 pages**:

| # | Page | Chart Type | Component(s) Used |
|---|------|-----------|-------------------|
| 1 | Analytics | Stacked Area Chart | `<AreaChart>` + 3 `<Area stackId="1">` |
| 2 | Analytics | Donut Pie Chart | `<PieChart>` + `<Pie innerRadius={60}>` |
| 3 | Analytics | Horizontal Bar Chart | `<BarChart layout="vertical">` |
| 4 | Analytics | Vertical Bar Chart | `<BarChart>` + 2 `<Bar>` |
| 5 | Analytics | Stacked Bar Chart | `<BarChart>` + 3 `<Bar stackId="responses">` |
| 6 | Analytics | Ring (Filled) Pie Chart | `<PieChart>` + `<Pie>` (no `innerRadius`) |
| 7 | Overview | Area Chart (7-day trend) | `<AreaChart>` + 2 `<Area>` |

**Key files:**
- `src/app/analytics/page.tsx` -- 6 charts
- `src/app/overview/page.tsx` -- 1 chart
- `src/lib/constants.ts` -- `CHART_COLORS` array
- `src/app/globals.css` -- `--color-chart-*` CSS variables

---

## Why We Chose This

1. **Declarative & composable** -- Charts are JSX. Adding a tooltip means adding `<Tooltip />`. Adding a legend means adding `<Legend />`. No imperative canvas code.
2. **React-native component model** -- Props, conditional rendering, `.map()` over data -- it all works exactly like every other React component.
3. **Responsive out of the box** -- `<ResponsiveContainer>` watches its parent's width and re-renders the SVG automatically.
4. **Small API surface** -- You can build all 7 charts in this project with ~12 Recharts components. No plugin system or theme engine to learn.
5. **D3 underneath** -- When you need custom formatting (date ticks, percentage labels), D3-scale precision is there, but you rarely touch D3 directly.

---

## Real Code Examples

### 1. ResponsiveContainer -- Responsive Sizing for Every Chart

Every single chart in the project is wrapped in a `<ResponsiveContainer>`:

```tsx
// src/app/analytics/page.tsx (line 126)
<ResponsiveContainer width="100%" height={280}>
  <AreaChart data={dailyTrends}>
    {/* ... */}
  </AreaChart>
</ResponsiveContainer>
```

```tsx
// src/app/overview/page.tsx (line 170)
<ResponsiveContainer width="100%" height={240}>
  <AreaChart data={trends}>
    {/* ... */}
  </AreaChart>
</ResponsiveContainer>
```

**Why:** Recharts renders SVGs with fixed dimensions by default. `ResponsiveContainer` uses a `ResizeObserver` internally to detect the parent's width and passes it down, making the chart fluid. `width="100%"` means "fill the parent", and `height={280}` gives a fixed pixel height so the card doesn't collapse.

---

### 2. Stacked Area Chart -- `stackId="1"`

```tsx
// src/app/analytics/page.tsx (lines 143-169)
<Area
  type="monotone"
  dataKey="jobs_scraped"
  stackId="1"
  stroke={COLORS[0]}
  fill={COLORS[0]}
  fillOpacity={0.6}
  name="Jobs Scraped"
/>
<Area
  type="monotone"
  dataKey="jobs_analyzed"
  stackId="1"
  stroke={COLORS[1]}
  fill={COLORS[1]}
  fillOpacity={0.6}
  name="Jobs Analyzed"
/>
<Area
  type="monotone"
  dataKey="emails_queued"
  stackId="1"
  stroke={COLORS[2]}
  fill={COLORS[2]}
  fillOpacity={0.6}
  name="Emails Queued"
/>
```

**How it works:** When multiple `<Area>` components share the same `stackId`, Recharts adds their values vertically. The first area sits on the baseline; the second sits on top of the first; the third on top of both. `fillOpacity={0.6}` makes overlapping regions semi-transparent so you can still see the stacking visually.

---

### 3. Donut Chart -- `innerRadius` Creates the Hole

```tsx
// src/app/analytics/page.tsx (lines 184-201)
<Pie
  data={scoreDistribution}
  dataKey="count"
  nameKey="bracket"
  cx="50%"
  cy="50%"
  innerRadius={60}
  outerRadius={90}
  paddingAngle={2}
  label={renderPercentLabel}
>
  {scoreDistribution.map((_, index) => (
    <Cell
      key={`cell-${index}`}
      fill={COLORS[index % COLORS.length]}
    />
  ))}
</Pie>
```

**How it works:** A `<Pie>` with `innerRadius={60}` and `outerRadius={90}` draws arcs between those two radii, leaving a 60px hole in the center -- that is the "donut". `paddingAngle={2}` adds a 2-degree gap between slices for visual clarity.

---

### 4. Ring Chart (Filled Pie) -- No `innerRadius`

```tsx
// src/app/analytics/page.tsx (lines 342-357)
<Pie
  data={routeBreakdown}
  dataKey="value"
  nameKey="name"
  cx="50%"
  cy="50%"
  outerRadius={90}
  paddingAngle={2}
  label={renderPercentLabel}
>
  {routeBreakdown.map((_, index) => (
    <Cell
      key={`cell-${index}`}
      fill={COLORS[index % COLORS.length]}
    />
  ))}
</Pie>
```

**How it works:** Same `<Pie>` component, but without `innerRadius`. This produces a filled pie (no hole). The only structural difference from the donut chart is the absence of `innerRadius={60}`.

---

### 5. Custom Label Renderer -- `renderPercentLabel`

```tsx
// src/app/analytics/page.tsx (lines 45-53)
function renderPercentLabel({
  name,
  percent,
}: {
  name: string;
  percent: number;
}) {
  return `${name} ${(percent * 100).toFixed(0)}%`;
}
```

Used on both pie charts:
```tsx
<Pie label={renderPercentLabel}>
```

**How it works:** Recharts calls this function for every slice, passing `{ name, value, percent, ... }`. The function returns a string that Recharts renders as an SVG `<text>` element positioned outside the slice. `percent` is a float between 0 and 1, so we multiply by 100 and round.

---

### 6. Cell Coloring -- Per-Slice Colors

```tsx
// src/app/analytics/page.tsx (lines 195-200)
{scoreDistribution.map((_, index) => (
  <Cell
    key={`cell-${index}`}
    fill={COLORS[index % COLORS.length]}
  />
))}
```

**How it works:** By default, a `<Pie>` renders all slices the same color. To give each slice its own color, you `.map()` over the data and render a `<Cell>` child for each entry. `COLORS[index % COLORS.length]` cycles through the palette so you never get an `undefined` fill even if you have more slices than colors.

---

### 7. Horizontal Bar Chart -- `layout="vertical"`

```tsx
// src/app/analytics/page.tsx (lines 222-246)
<BarChart data={sourceBreakdown} layout="vertical">
  <CartesianGrid strokeDasharray="3 3" />
  <XAxis type="number" tick={{ fontSize: 11 }} />
  <YAxis
    type="category"
    dataKey="source"
    tick={{ fontSize: 11 }}
    width={100}
  />
  <Tooltip
    contentStyle={{
      borderRadius: "8px",
      border: "1px solid #e5e7eb",
      fontSize: "12px",
    }}
  />
  <Bar
    dataKey="count"
    fill={COLORS[0]}
    radius={[0, 4, 4, 0]}
    name="Total Jobs"
  />
</BarChart>
```

**How it works:** `layout="vertical"` flips the chart so bars grow horizontally. This requires swapping axis types: `<XAxis type="number">` (values) and `<YAxis type="category" dataKey="source">` (labels). The `width={100}` on YAxis allocates enough space for long source names.

---

### 8. Stacked Bar Chart -- `stackId="responses"`

```tsx
// src/app/analytics/page.tsx (lines 309-327)
<Bar
  dataKey="interviews"
  stackId="responses"
  fill={COLORS[0]}
  name="Interviews"
/>
<Bar
  dataKey="offers"
  stackId="responses"
  fill={COLORS[2]}
  name="Offers"
/>
<Bar
  dataKey="rejections"
  stackId="responses"
  fill={COLORS[3]}
  name="Rejections"
/>
```

**How it works:** Same principle as stacked areas. All three `<Bar>` components share `stackId="responses"`, so their values stack vertically within each group on the X axis. Interviews form the base, offers stack on top, rejections on top of that.

---

### 9. Rounded Bar Corners -- `radius` Prop

For **horizontal** bars (grow left-to-right):
```tsx
// src/app/analytics/page.tsx (line 241)
<Bar dataKey="count" fill={COLORS[0]} radius={[0, 4, 4, 0]} name="Total Jobs" />
```
`radius={[0, 4, 4, 0]}` means: top-left=0, top-right=4, bottom-right=4, bottom-left=0. Since bars grow rightward, only the right side (the "end") gets rounded.

For **vertical** bars (grow bottom-to-top):
```tsx
// src/app/analytics/page.tsx (lines 274-279)
<Bar dataKey="count" fill={COLORS[1]} radius={[4, 4, 0, 0]} name="Total" />
<Bar dataKey="gap_tolerant_count" fill={COLORS[0]} radius={[4, 4, 0, 0]} name="Gap Tolerant" />
```
`radius={[4, 4, 0, 0]}` rounds the top-left and top-right corners, which is the "end" of a vertical bar.

---

### 10. Consistent Tooltip Styling

Every chart uses the same tooltip style:

```tsx
// src/app/analytics/page.tsx (repeated on every chart)
<Tooltip
  contentStyle={{
    borderRadius: "8px",
    border: "1px solid #e5e7eb",
    fontSize: "12px",
  }}
/>
```

**Why:** Recharts' default tooltip has no border radius and uses a plain border. By applying the same `contentStyle` object on every chart, all 7 charts have visually identical tooltip popups. The `#e5e7eb` matches Tailwind's `gray-200`.

---

### 11. Axis Formatting -- `tickFormatter` and `tick`

```tsx
// src/app/analytics/page.tsx (lines 129-133)
<XAxis
  dataKey="date"
  tickFormatter={formatShortDate}
  tick={{ fontSize: 11 }}
/>
```

Where `formatShortDate` is:

```tsx
// src/app/analytics/page.tsx (lines 36-43)
function formatShortDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return dateStr;
  }
}
```

And on the Overview page, an inline `tickFormatter`:

```tsx
// src/app/overview/page.tsx (lines 176-180)
<XAxis
  dataKey="date"
  tick={{ fontSize: 12 }}
  tickFormatter={(v: string) =>
    new Date(v).toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
    })
  }
/>
```

**How it works:** `tickFormatter` receives the raw data value (e.g., `"2025-06-15"`) and returns the display string (e.g., `"Jun 15"`). `tick={{ fontSize: 11 }}` styles the SVG `<text>` elements for the axis labels.

---

### 12. Color Palette -- Unified Across 3 Layers

The same 6 colors appear in three places:

```tsx
// src/app/analytics/page.tsx (line 34)
const COLORS = ["#00d4aa", "#1e3a5f", "#f5a623", "#e74c3c", "#8e44ad", "#3498db"];
```

```tsx
// src/lib/constants.ts (lines 15-17)
export const CHART_COLORS = [
  "#00d4aa", "#1e3a5f", "#f5a623", "#e74c3c", "#8e44ad", "#3498db",
] as const;
```

```css
/* src/app/globals.css (lines 23-28) */
--color-chart-1: #00d4aa;
--color-chart-2: #1e3a5f;
--color-chart-3: #f5a623;
--color-chart-4: #e74c3c;
--color-chart-5: #8e44ad;
--color-chart-6: #3498db;
```

**Why three layers?**
- `COLORS` in analytics is a local constant for direct `fill={}` props
- `CHART_COLORS` in constants.ts is the shared export used by other pages (overview uses `CHART_COLORS[0]` and `CHART_COLORS[1]`)
- CSS variables allow Tailwind classes like `bg-[var(--color-chart-1)]` if needed

---

### 13. Rotated Tick Labels -- `angle` and `textAnchor`

```tsx
// src/app/analytics/page.tsx (lines 259-264)
<XAxis
  dataKey="company_type"
  tick={{ fontSize: 11 }}
  interval={0}
  angle={-20}
  textAnchor="end"
  height={50}
/>
```

**How it works:** Long category labels like "Fortune 500" or "Mid-size Company" overlap at small screen sizes. `angle={-20}` rotates each tick label 20 degrees counter-clockwise. `textAnchor="end"` anchors the rotated text at its end so labels don't overflow into the chart area. `interval={0}` forces every label to render (by default Recharts may skip some). `height={50}` allocates extra space below the axis so rotated text is not clipped.

---

### 14. Data Transformation -- API Response to Recharts Format

```tsx
// src/app/analytics/page.tsx (line 76)
routeBreakdown: Object.entries(routes).map(([name, value]) => ({ name, value })),
```

**How it works:** The API returns route data as a flat object `{ "LinkedIn": 42, "Indeed": 18, ... }`. Recharts expects an array of objects with consistent keys: `[{ name: "LinkedIn", value: 42 }, ...]`. `Object.entries()` converts the object to `[key, value]` pairs, then `.map()` reshapes each pair into the object format Recharts needs.

---

## How It Works -- End-to-End Walkthrough

Here is the full lifecycle of the Analytics page rendering all 6 charts:

1. **Page mounts** -- `AnalyticsPage` runs `useQuery` which calls 6 API endpoints in parallel via `Promise.all`.

2. **Loading state** -- While the query is pending, 6 `<SkeletonChart />` cards are rendered in a responsive grid.

3. **Data arrives** -- `queryData` is destructured into 6 arrays/objects. The route breakdown data gets transformed from `{ key: value }` to `[{ name, value }]`.

4. **Charts render** -- Each chart is a `<Card>` containing:
   - `<CardHeader>` with a title
   - `<CardContent>` wrapping a `<ResponsiveContainer>` wrapping the actual chart

5. **ResponsiveContainer measures** -- On mount, it reads the parent `<CardContent>` width and passes it to the chart. On window resize, it re-measures.

6. **Recharts builds the SVG** -- For an `<AreaChart>`, this means:
   - Compute X/Y scales from data
   - Render `<CartesianGrid>` (dashed lines)
   - Render `<XAxis>` with formatted ticks
   - Render `<YAxis>` with auto-computed domain
   - Render each `<Area>` as an SVG `<path>` with fill
   - Position `<Tooltip>` (hidden until hover)
   - Render `<Legend>` at the bottom

7. **User interacts** -- Hovering shows the tooltip with `contentStyle` applied. The tooltip auto-positions itself near the cursor and shows values for all data series at that X position.

---

## Interview Talking Points

1. **"I chose Recharts because it follows React's declarative model."** -- You compose charts from JSX components instead of calling drawing APIs. This means React's reconciliation handles updates, and you can use familiar patterns like `.map()`, conditional rendering, and props.

2. **"Every chart is responsive without media queries."** -- `<ResponsiveContainer>` uses `ResizeObserver` internally. We just set `width="100%"` and a fixed `height`, and the SVG scales automatically.

3. **"We maintain design consistency through a shared color palette."** -- The same 6 hex values appear in `COLORS`, `CHART_COLORS`, and CSS custom properties. Every chart references this palette, so changing a brand color updates all charts.

4. **"I used `stackId` to show composition over time."** -- For the activity trend, I wanted to show how scraped, analyzed, and queued jobs add up to total daily activity. `stackId` on `<Area>` and `<Bar>` handles this without manual data aggregation.

5. **"The donut vs. filled pie distinction is just one prop: `innerRadius`."** -- This demonstrates understanding of the Recharts API surface. The Score Distribution (donut) needs a center space for a potential center label; the Route Breakdown (filled pie) uses all available space.

6. **"I transform API data at the query layer, not the component layer."** -- The `Object.entries(routes).map(...)` transformation happens inside `queryFn`, so the component always receives Recharts-ready arrays. This keeps the JSX clean and avoids re-transforming on every render.

---

## Common Questions

### Q: Why use Recharts instead of Chart.js or D3 directly?

**Chart.js** is canvas-based and imperative -- you call `new Chart(ctx, config)`. In React, you need a wrapper like `react-chartjs-2` that bridges the imperative API to React's lifecycle. Recharts is built for React from the ground up, so there is no bridging layer.

**D3 directly** gives you total control but requires managing SVG elements, scales, axes, transitions, and resizing manually. Recharts uses D3 for math but wraps it in React components so you get D3 precision without D3 boilerplate.

### Q: Why is `ResponsiveContainer` needed? Can't I just set width/height on the chart?

You can, but then the chart has fixed pixel dimensions. `<AreaChart width={800} height={280}>` renders exactly 800px wide regardless of screen size. `ResponsiveContainer` reads its parent's actual width and passes it down, making the chart fluid in responsive layouts.

### Q: What does `stackId` actually do?

When multiple series share a `stackId`, Recharts computes cumulative Y values. For series A=10, B=20, C=5 at point X:
- A renders from y=0 to y=10
- B renders from y=10 to y=30
- C renders from y=30 to y=35

Without `stackId`, all three would render from y=0, overlapping each other.

### Q: Why map `<Cell>` components instead of just passing a `colors` array?

Recharts' API requires `<Cell>` children for per-slice coloring. This is a design choice -- it keeps the API composable. You could conditionally style individual slices, add click handlers per slice, or apply different strokes per slice, all by customizing individual `<Cell>` props.

### Q: Why is the color palette duplicated in 3 places?

Each layer serves a different consumer:
- **`COLORS` (local constant)**: Quick access inside the analytics page with no import needed.
- **`CHART_COLORS` (shared export)**: Used by any page that needs chart colors (overview page imports it).
- **CSS variables**: Allows Tailwind utilities and non-Recharts elements (like KPI card borders on the overview page) to reference the same palette.

In a production refactor, you could derive all three from a single source, but for a project of this size, the duplication is minimal and the tradeoff is clarity.

### Q: How does the horizontal bar chart differ from a regular bar chart?

Two changes:
1. Add `layout="vertical"` to `<BarChart>`
2. Swap axis types: `<XAxis type="number">` and `<YAxis type="category" dataKey="source">`

That is it. The `<Bar>` component stays the same. Recharts handles the coordinate flipping internally.

### Q: What happens if there are more data slices than colors in the array?

The modulo operator handles it: `COLORS[index % COLORS.length]`. With 6 colors, index 6 wraps to `COLORS[0]`, index 7 to `COLORS[1]`, and so on. Colors repeat but the chart never breaks.

### Q: Why `fillOpacity={0.6}` on stacked areas but not on bars?

Stacked areas overlap visually because the fill extends from the line down to the previous area. Semi-transparency helps the viewer see all layers. Bars do not overlap (they stack cleanly), so full opacity works fine.
