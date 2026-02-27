# 10 - Design System and Component Patterns

## What Is This?

A design system is the collection of reusable components, patterns, and conventions that
ensure visual consistency across an application. In our project, the design system is
built from three layers:

1. **Design tokens** -- CSS variables in `globals.css` that define colors, radii, and
   spacing
2. **Primitive components** -- Headless Radix UI primitives wrapped with our own styling
3. **Utility patterns** -- Functions like `cn()`, `scoreBadgeColor()`, and responsive
   grid classes that are used everywhere

This document covers each layer, the tools we chose, and why they fit together.

---

## Why We Chose This Approach

### Alternatives considered

| Approach | Why we rejected it |
|---|---|
| **Material UI / Ant Design** | Pre-styled component libraries. They look good out of the box, but customization is painful -- you fight their design opinions. Our app has a specific brand (dark navy + teal accent) that would require deep theme overrides. |
| **Headless UI (Tailwind Labs)** | Good option, but Radix UI has a larger component library and more mature accessibility handling. |
| **Build everything from scratch** | Accessible components (Dialog, Select, Tooltip) are extremely hard to build correctly. Focus traps, keyboard navigation, screen reader announcements, scroll locking -- hundreds of edge cases. Not worth reinventing. |
| **Install shadcn/ui via CLI** | The CLI pulls in components we do not need. By manually copying only what we use, we control the bundle size and understand every line. |

---

## How It Works In Our App

### 1. CVA (class-variance-authority) -- Type-Safe Component Variants

CVA is a tiny library that solves a specific problem: defining component variants with
type safety. Here is our Button component from `src/components/ui/button.tsx`:

```typescript
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  // Base classes applied to ALL buttons
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:     "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:     "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary:   "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost:       "hover:bg-accent/10 hover:text-accent-foreground",
        link:        "text-primary underline-offset-4 hover:underline",
        accent:      "bg-accent text-white hover:bg-accent/90",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm:      "h-9 rounded-md px-3",
        lg:      "h-11 rounded-md px-8",
        icon:    "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);
```

#### How CVA works

`cva()` returns a function. When you call `buttonVariants({ variant: "destructive", size: "sm" })`,
it returns a string of merged CSS classes:

```
"inline-flex items-center ... bg-destructive text-destructive-foreground hover:bg-destructive/90 h-9 rounded-md px-3"
 ^--- base classes ---^     ^--- variant-specific ---^                                           ^--- size-specific ---^
```

#### Why this is better than conditional className strings

Without CVA, you would write:

```typescript
// Error-prone: easy to miss a variant, easy to have conflicting classes
className={cn(
  "inline-flex items-center justify-center ...",
  variant === "default" && "bg-primary text-primary-foreground",
  variant === "destructive" && "bg-destructive text-destructive-foreground",
  variant === "outline" && "border border-input bg-background",
  // ... more variants
  size === "default" && "h-10 px-4 py-2",
  size === "sm" && "h-9 rounded-md px-3",
  // ... more sizes
)}
```

Problems with this approach:
- No TypeScript enforcement -- you could pass `variant="danger"` (typo) and get no error
- Adding a new variant requires finding every conditional branch
- No guarantee that all variants are handled

CVA solves all three: TypeScript extracts valid variant names from the definition, the
structure is declarative, and the `defaultVariants` guarantee there is always a fallback.

#### The `VariantProps` pattern

```typescript
export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}
```

`VariantProps<typeof buttonVariants>` automatically extracts:

```typescript
{
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link" | "accent" | null;
  size?: "default" | "sm" | "lg" | "icon" | null;
}
```

These props are generated from the CVA definition -- you never have to write them
manually or keep them in sync. If you add a new variant to `buttonVariants`, the type
updates automatically.

---

### 2. The `cn()` Utility -- The Most Used Function in the Project

From `src/lib/utils.ts`:

```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

This two-line function composes two libraries:

#### What `clsx` does

`clsx` handles conditional class construction:

```typescript
clsx("base", true && "active", false && "disabled", undefined)
// Result: "base active"
```

It filters out falsy values (`false`, `undefined`, `null`, `0`, `""`), so you can write:

```typescript
cn(
  "flex items-center",
  isExpanded && "rotate-180",
  isObsolete && "opacity-50",
  isSaved && "bg-emerald-50",
)
```

#### What `twMerge` does

`twMerge` resolves Tailwind CSS class conflicts:

```typescript
twMerge("px-4 py-2", "px-6")
// Result: "py-2 px-6"  (px-4 is removed, px-6 wins)

twMerge("text-red-500", "text-blue-500")
// Result: "text-blue-500"  (text-red-500 is removed)
```

Without `twMerge`, both classes would be present in the output, and CSS specificity would
determine which one applies -- often not the one you expect.

#### Why this matters for component design

Consider our Button component:

```typescript
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
```

The `className` prop is passed into `cn()` alongside the variant classes. This means a
parent component can override the button's styles:

```typescript
<Button variant="default" className="h-7 text-xs">Save</Button>
```

The button's default size is `h-10 px-4 py-2`, but `className="h-7"` overrides the
height. Without `twMerge`, the output would be `"... h-10 px-4 py-2 h-7"` and CSS would
apply whichever came last in the stylesheet (unpredictable). With `twMerge`, the output
is `"... px-4 py-2 h-7"` -- `h-10` is removed, `h-7` wins cleanly.

---

### 3. Radix UI Primitives -- Headless, Accessible Components

We use Radix UI for components that require complex accessibility behavior:

| Component | Radix Package | Used In |
|---|---|---|
| Select | `@radix-ui/react-select` | Filters on every page (Applications, Emails, Tracker, Startups, Outcomes) |
| Dialog | `@radix-ui/react-dialog` | Delete confirmation in Emails page |
| Tabs | `@radix-ui/react-tabs` | Applications view toggle, Outcomes tabs, Startups card tabs |
| Tooltip | `@radix-ui/react-tooltip` | Throughout the app for icon explanations |
| Separator | `@radix-ui/react-separator` | Visual dividers in email content, startup cards |
| Slot | `@radix-ui/react-slot` | The `asChild` pattern in Button |

#### What "headless" means

"Headless" means Radix provides **behavior and accessibility**, but zero styling. Our
Dialog component from `src/components/ui/dialog.tsx` shows this:

```typescript
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

const DialogContent = React.forwardRef<
  React.ComponentRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 ...",
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 ...">
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
));
```

Radix handles (all of this for free):
- **Focus trap** -- Tab key cycles within the dialog, cannot escape to background content
- **Escape key** -- Pressing Escape closes the dialog
- **Click outside** -- Clicking the overlay closes the dialog
- **`aria-labelledby`** -- Automatically links DialogTitle to the dialog for screen readers
- **`aria-describedby`** -- Links DialogDescription for screen readers
- **Scroll lock** -- Background content cannot scroll while the dialog is open
- **Portal rendering** -- Dialog content is rendered outside the DOM tree to avoid z-index
  stacking context issues
- **Animation states** -- `data-[state=open]` and `data-[state=closed]` attributes for
  CSS transitions

**Why not build our own Dialog?** Because getting all of the above right is deceptively
difficult. The WAI-ARIA dialog pattern specification has dozens of requirements. A
home-built modal would fail accessibility audits on edge cases like nested focus traps,
iOS VoiceOver navigation, or screen reader announcement timing.

---

### 4. The shadcn/ui Approach -- Own Your Components

shadcn/ui is not a component library you install via `npm install`. It is a collection of
component recipes that you **copy into your project**. This is a fundamental distinction:

| Traditional library (MUI, Ant) | shadcn/ui approach |
|---|---|
| `npm install @mui/material` | Copy component code into `src/components/ui/` |
| Updates via `npm update` | You update manually when you want |
| Customization via theme override API | Direct code modification |
| You depend on their release cycle | You own every line |
| Bundle includes unused components | You only include what you use |

In our project, we manually created these components in `src/components/ui/`:

1. `button.tsx` -- CVA button with 7 variants and 4 sizes
2. `card.tsx` -- Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter
3. `badge.tsx` -- Inline label with variant support
4. `input.tsx` -- Styled HTML input
5. `textarea.tsx` -- Styled HTML textarea
6. `select.tsx` -- Radix Select with custom styling
7. `tabs.tsx` -- Radix Tabs with custom styling
8. `dialog.tsx` -- Radix Dialog with overlay, close button, animations
9. `tooltip.tsx` -- Radix Tooltip with styling
10. `separator.tsx` -- Radix Separator (horizontal/vertical divider)
11. `skeleton.tsx` -- Loading placeholder animation
12. `skeletons.tsx` -- Composite skeleton patterns (SkeletonCard, SkeletonGrid, etc.)
13. `pagination.tsx` -- Page navigation with prev/next buttons
14. `sheet.tsx` -- Radix Dialog variant that slides from the side (mobile sidebar)

Each component is a **thin styled wrapper** around either a Radix primitive or plain HTML
elements. The entire `ui/` directory is roughly 500 lines of code -- small enough to
understand completely, large enough to maintain consistency across 7 pages.

---

### 5. The `asChild` Pattern -- Polymorphic Components

From `src/components/ui/button.tsx`:

```typescript
const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
```

When `asChild` is `false` (the default), `Comp` is `"button"` -- a regular HTML button.
When `asChild` is `true`, `Comp` is `Slot` from Radix, which **merges the Button's props
onto the child element**.

Usage in the Startups page:

```typescript
<Button variant="outline" size="sm" className="h-7 text-xs" asChild>
  <a href={startup.website_url} target="_blank" rel="noopener noreferrer">
    Website
  </a>
</Button>
```

The rendered HTML is:

```html
<a
  href="https://example.com"
  target="_blank"
  rel="noopener noreferrer"
  class="inline-flex items-center justify-center ... border border-input bg-background hover:bg-accent ... h-7 text-xs"
>
  Website
</a>
```

The output is an `<a>` element (not a `<button>`) but with all of Button's styling. This
matters for accessibility:

- **A link should be `<a>`** -- Screen readers announce it as "link," keyboard users can
  follow it with Enter, and browsers handle middle-click/right-click correctly
- **A button should be `<button>`** -- Screen readers announce it as "button," keyboard
  users can activate it with Space or Enter
- **A `<button>` that navigates is wrong** -- It looks like a button but behaves like a
  link, confusing assistive technology

The `asChild` pattern lets you maintain semantic correctness while reusing visual styling.

---

### 6. Consistent Color Mapping Functions

From `src/lib/utils.ts`:

```typescript
export function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-600 bg-emerald-50 border-emerald-200";
  if (score >= 60) return "text-teal-600 bg-teal-50 border-teal-200";
  if (score >= 40) return "text-amber-600 bg-amber-50 border-amber-200";
  return "text-red-600 bg-red-50 border-red-200";
}

export function scoreBadgeColor(score: number): string {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-teal-500";
  if (score >= 40) return "bg-amber-500";
  return "bg-red-500";
}

export function decisionColor(decision: string): string {
  switch (decision) {
    case "YES":    return "bg-emerald-500 text-white";
    case "MAYBE":  return "bg-amber-500 text-white";
    case "MANUAL": return "bg-purple-500 text-white";
    case "NO":     return "bg-red-500 text-white";
    default:       return "bg-gray-400 text-white";
  }
}

export function statusColor(status: string): string {
  switch (status) {
    case "draft":                   return "bg-gray-400 text-white";
    case "verified":                return "bg-blue-500 text-white";
    case "ready":                   return "bg-teal-500 text-white";
    case "queued":                  return "bg-amber-500 text-white";
    case "sent": case "delivered":  return "bg-emerald-500 text-white";
    case "bounced": case "failed":  return "bg-red-500 text-white";
    default:                        return "bg-gray-400 text-white";
  }
}
```

These four functions are used across every page that shows scores, decisions, or
statuses. They are the **single source of truth** for the score-to-color and
status-to-color mappings.

**Why this matters:**

- The Overview page, Applications page, Emails page, Tracker page, Outcomes page, and
  Startups page all show score badges. They all call `scoreBadgeColor(score)`.
- If we want to change the color for scores 80+ from emerald to blue, we change **one
  line** in `utils.ts` and every badge across 6 pages updates.
- Without centralization, each page would have its own color logic, and they would
  inevitably diverge -- "YES" might be green on one page and teal on another.

---

### 7. The Responsive Grid Pattern

Used on every page with card layouts:

```html
<!-- KPI cards on Overview page -->
<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
  <!-- cards -->
</div>

<!-- All-time summary on Overview page -->
<div class="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
  <!-- cards -->
</div>

<!-- Application cards -->
<div class="grid grid-cols-1 gap-4 md:grid-cols-2">
  <!-- cards -->
</div>

<!-- Analytics charts -->
<div class="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
  <!-- charts -->
</div>

<!-- Startup stats -->
<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
  <!-- stat cards -->
</div>
```

The pattern is always:

```
grid-cols-{mobile} sm:grid-cols-{tablet} lg:grid-cols-{desktop}
```

| Breakpoint | Width | Typical column count |
|---|---|---|
| Default (mobile) | < 640px | 1 column |
| `sm` | >= 640px | 2 columns |
| `md` | >= 768px | 2 columns |
| `lg` | >= 1024px | 3-4 columns |
| `xl` | >= 1280px | 4-6 columns |

This ensures the layout works on phones, tablets, and desktops without any JavaScript
resize handlers or media query listeners. Tailwind's responsive prefixes are compile-time
CSS, not runtime code.

---

### 8. Design Token Approach -- Tailwind CSS v4 with `@theme inline`

From `src/app/globals.css`:

```css
@import "tailwindcss";

@theme inline {
  --color-background: #ffffff;
  --color-foreground: #0a0a0a;
  --color-card: #ffffff;
  --color-card-foreground: #0a0a0a;
  --color-popover: #ffffff;
  --color-popover-foreground: #0a0a0a;
  --color-primary: #1e3a5f;
  --color-primary-foreground: #f8fafc;
  --color-secondary: #f1f5f9;
  --color-secondary-foreground: #1e3a5f;
  --color-muted: #f1f5f9;
  --color-muted-foreground: #64748b;
  --color-accent: #00d4aa;
  --color-accent-foreground: #0f1b2d;
  --color-destructive: #e74c3c;
  --color-destructive-foreground: #f8fafc;
  --color-border: #e2e8f0;
  --color-input: #e2e8f0;
  --color-ring: #1e3a5f;
  --color-sidebar: #0f1b2d;
  --color-sidebar-foreground: #f0f4f8;
  --color-sidebar-accent: #00d4aa;
  --radius: 0.75rem;
}
```

These CSS variables define our entire color palette. Every Tailwind class like
`bg-primary`, `text-accent`, `border-input` references these variables.

**Why this matters for rebranding:**

If the project needed a different brand (say, a client wants purple instead of navy), you
would change `--color-primary: #1e3a5f` to `--color-primary: #6b21a8` in this one file.
Every component that uses `bg-primary`, `text-primary`, `text-primary-foreground`,
`ring-primary`, etc. would automatically update. No component code changes needed.

The `@theme inline` directive is Tailwind CSS v4's way of defining design tokens. In v3,
this was done in `tailwind.config.js` under `theme.extend.colors`. The v4 approach is
more direct -- the tokens live in CSS where they are used, not in a JavaScript
configuration file.

Our color system:

| Token | Hex | Usage |
|---|---|---|
| `primary` | `#1e3a5f` (dark navy) | Navigation, table headers, default buttons |
| `accent` | `#00d4aa` (teal) | Sidebar highlights, accent buttons, chart color 1 |
| `destructive` | `#e74c3c` (red) | Delete buttons, error states |
| `muted-foreground` | `#64748b` (slate gray) | Secondary text, labels, timestamps |
| `sidebar` | `#0f1b2d` (very dark navy) | Sidebar background |

The pairing convention (`primary` + `primary-foreground`) ensures contrast. When
`bg-primary` is dark navy, `text-primary-foreground` is near-white, so text is always
readable against the background.

---

## The Key Insight

A design system is not about having a lot of components -- it is about having a small
number of well-composed primitives that combine to cover every use case. Our 14 UI
components, 4 color mapping functions, 1 className utility, and a set of CSS variables
produce a visually consistent application across 7 pages. The composition happens at the
page level (combining Card + Badge + Button + Select into a filter bar), not at the
component level (no "FilterBar" component). This keeps the primitives reusable and the
pages readable.

---

## Interview Talking Points

- "We use CVA (class-variance-authority) for type-safe component variants. The Button
  component defines 7 visual variants and 4 sizes, and TypeScript automatically extracts
  those as valid prop values. You cannot pass `variant='danger'` -- only the defined
  variants compile."

- "The `cn()` utility composes `clsx` (conditional class construction) with `twMerge`
  (Tailwind conflict resolution). Without `twMerge`, a parent passing `className='px-6'`
  would not override the component's default `px-4` -- both would be present and CSS
  specificity would determine the winner unpredictably."

- "We use Radix UI for components that need complex accessibility: Dialog, Select, Tabs,
  Tooltip. 'Headless' means Radix provides behavior (focus traps, keyboard nav, ARIA
  attributes) and we provide styling. This gives us full visual control with zero
  accessibility compromise."

- "Following the shadcn/ui approach, we copied 14 components into our project instead of
  installing a library. We own every line of code, can customize freely, and only include
  what we actually use."

- "The `asChild` pattern with Radix's `Slot` component lets our Button render as an `<a>`
  tag when wrapping a link. This maintains semantic HTML -- links should be `<a>`, buttons
  should be `<button>` -- while sharing visual styling."

- "Color mapping functions like `scoreBadgeColor()` and `decisionColor()` are centralized
  in `utils.ts`. Six pages call the same function, so changing the color for score 80+
  means changing one line, not six."

- "Our responsive grid pattern uses Tailwind's breakpoint prefixes:
  `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4` gives us mobile, tablet, and desktop
  layouts with zero JavaScript. It is pure CSS."

- "Tailwind CSS v4's `@theme inline` lets us define our entire color palette as CSS
  variables in `globals.css`. Every `bg-primary`, `text-accent`, `border-input` references
  these variables. A complete rebrand requires changing one file."
