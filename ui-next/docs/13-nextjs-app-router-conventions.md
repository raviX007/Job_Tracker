# Next.js App Router Conventions

## What Is It

Next.js 15's App Router is a file-system-based routing framework where **folders become URL routes** and **special filenames** (`page.tsx`, `layout.tsx`, `error.tsx`, `loading.tsx`) have built-in behaviors. Instead of manually configuring routes in a router file, you create a folder called `overview/` with a `page.tsx` inside it, and Next.js automatically serves it at `/overview`.

The App Router also introduces a clear Server Component / Client Component boundary. By default, every component is a **Server Component** (rendered on the server, zero client JS). You opt into Client Component behavior by adding `"use client"` at the top of the file.

This project uses the App Router to serve 8 routes, each as a folder under `src/app/`:

```
src/app/
├── layout.tsx          ← Root layout (wraps ALL pages)
├── page.tsx            ← Root page (redirects to /overview)
├── error.tsx           ← Global error boundary
├── globals.css         ← Global styles
├── overview/page.tsx   ← /overview
├── applications/page.tsx ← /applications
├── outcomes/page.tsx   ← /outcomes
├── emails/page.tsx     ← /emails
├── analytics/page.tsx  ← /analytics
├── tracker/page.tsx    ← /tracker
├── pipeline/page.tsx   ← /pipeline
└── startups/page.tsx   ← /startups
```

**Key files:**
- `src/app/layout.tsx` -- Root layout with Metadata, Inter font
- `src/app/page.tsx` -- Server-side redirect to `/overview`
- `src/app/error.tsx` -- Error boundary convention
- `src/components/providers.tsx` -- QueryClientProvider wrapping
- `src/components/layout/app-shell.tsx` -- ProfileProvider placement

---

## Why We Chose This

1. **Zero-config routing** -- No React Router setup, no route arrays, no `<Route path="/overview">`. A folder named `overview` with a `page.tsx` inside it is the route. This eliminates an entire category of configuration and keeps the project structure self-documenting.

2. **Built-in layouts** -- `layout.tsx` wraps all child routes automatically. The sidebar, navigation, and providers are defined once and shared across all 8 pages without a wrapper component in every page file.

3. **Server Components by default** -- The root layout and the redirect page ship zero JavaScript to the client. Only pages that need interactivity (hooks, event handlers) opt in with `"use client"`.

4. **Convention-based error handling** -- `error.tsx` is automatically used as an error boundary for all routes. No manual `<ErrorBoundary>` wrapping needed.

5. **Built-in font optimization** -- `next/font/google` self-hosts fonts at build time, eliminating Flash of Unstyled Text (FOUT) and external network requests to Google Fonts.

---

## Real Code Examples

### 1. Root Layout -- The Shell for Every Page

```tsx
// src/app/layout.tsx (complete file)
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Providers } from "@/components/providers";
import { AppShell } from "@/components/layout/app-shell";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Job Tracker",
  description: "AI-powered job application tracking and pipeline management",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-gray-50 text-gray-800 antialiased`}>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
```

**Key observations:**
- This is a **Server Component** -- no `"use client"` directive. The layout itself does not use hooks or browser APIs.
- It renders the `<html>` and `<body>` tags. In the App Router, the root layout is the only place these tags should appear.
- It runs **once** for the entire application. When users navigate between pages, the layout persists and only `{children}` re-renders. The sidebar, font loading, and provider initialization do not re-execute.
- `import "./globals.css"` loads global styles. In the App Router, CSS imports in `layout.tsx` apply to all child routes.

---

### 2. Metadata Export -- SEO and `<head>` Tags

```tsx
// src/app/layout.tsx (lines 9-13)
export const metadata: Metadata = {
  title: "Job Tracker",
  description: "AI-powered job application tracking and pipeline management",
  icons: { icon: "/favicon.svg" },
};
```

**How it works:**

Next.js collects `metadata` exports from layout and page files and generates the corresponding `<head>` tags:

```html
<head>
  <title>Job Tracker</title>
  <meta name="description" content="AI-powered job application tracking and pipeline management" />
  <link rel="icon" href="/favicon.svg" />
</head>
```

You never write `<head>`, `<title>`, or `<meta>` tags manually. The `Metadata` type from Next.js provides full TypeScript autocompletion for all valid fields (`title`, `description`, `icons`, `openGraph`, `twitter`, `robots`, etc.).

**Why this matters:** Page-level `metadata` exports can override layout-level ones. If `analytics/page.tsx` exported `metadata = { title: "Analytics | Job Tracker" }`, that page would have a different tab title while inheriting the favicon and description from the layout.

---

### 3. `next/font/google` -- Self-Hosted Font, No FOUT

```tsx
// src/app/layout.tsx (line 7)
const inter = Inter({ subsets: ["latin"] });
```

Applied to the body:
```tsx
// src/app/layout.tsx (line 22)
<body className={`${inter.className} bg-gray-50 text-gray-800 antialiased`}>
```

**What happens at build time:**

1. Next.js downloads the Inter font files from Google Fonts during the build.
2. The font files are saved to `.next/static/fonts/` and served from your own domain.
3. `inter.className` generates a unique CSS class (e.g., `__className_a64d72`) that applies `font-family: 'Inter', sans-serif` with the correct `@font-face` declarations.

**Why this matters:**
- **No external network request** -- The browser does not fetch from `fonts.googleapis.com`. The font is served from the same domain as the page.
- **No FOUT (Flash of Unstyled Text)** -- The font is preloaded and available before first paint. Traditional Google Fonts links cause a brief flash where text renders in the fallback font before the custom font loads.
- **Privacy** -- No request is sent to Google's servers at runtime.

---

### 4. Server-Side Redirect -- Zero Client JavaScript

```tsx
// src/app/page.tsx (complete file)
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/overview");
}
```

**How it works:**

This is a **Server Component** (no `"use client"`). When a user visits `/`, Next.js renders this component on the server. The `redirect()` function throws a special `NEXT_REDIRECT` error that Next.js catches and converts into an HTTP 307 redirect response:

```
HTTP/1.1 307 Temporary Redirect
Location: /overview
```

The browser follows the redirect before any JavaScript loads. This is fundamentally different from a client-side redirect like `useRouter().push("/overview")`, which requires:
1. Download the JavaScript bundle
2. Parse and execute it
3. React hydrates
4. The effect/redirect runs
5. Browser navigates

The server-side redirect happens at the HTTP level -- faster, simpler, works with JavaScript disabled, and search engine crawlers handle it correctly.

---

### 5. `error.tsx` Convention -- Automatic Error Boundary

```tsx
// src/app/error.tsx (complete file)
"use client";

import { useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled error:", error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] items-center justify-center p-8">
      <Card className="max-w-md border-red-200 bg-red-50">
        <CardContent className="pt-6 text-center">
          <h2 className="mb-2 text-lg font-semibold text-red-800">
            Something went wrong
          </h2>
          <p className="mb-4 text-sm text-red-700">
            An unexpected error occurred while rendering this page.
          </p>

          {process.env.NODE_ENV === "development" && (
            <pre className="mb-4 max-h-40 overflow-auto rounded-md bg-red-100 p-3
                            text-left text-xs text-red-800">
              {error.message}
            </pre>
          )}

          <Button variant="outline" onClick={reset}>
            Try again
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
```

**How the convention works:**

- Any file named `error.tsx` in the `app/` directory becomes an error boundary for that route segment and all its children.
- `error.tsx` at `src/app/error.tsx` catches errors from **all** pages (it is the root-level error boundary).
- Next.js automatically wraps the route's content in a React Error Boundary that renders this component when an error occurs.

**Props explained:**
- **`error`** -- The thrown Error object. The `digest` property is a hash that Next.js adds for errors that originated on the server. In production, server error messages are stripped for security; `digest` lets you correlate the client error with server logs.
- **`reset`** -- A function that re-renders the route segment. Calling `reset()` clears the error boundary and attempts to render the page again. This is useful for transient errors (e.g., a failed API call that might succeed on retry).

**Why `"use client"`?** Error boundaries are a React feature that requires client-side JavaScript. The error boundary intercepts rendering errors in the browser and must be able to call `useState`/`useEffect` to manage the error state and the reset action.

**Development guard:**
```tsx
{process.env.NODE_ENV === "development" && (
  <pre>{error.message}</pre>
)}
```
This shows the full error message only in development. In production, users see a generic "Something went wrong" message. Error details in production would be a security risk (leaking stack traces, file paths, or internal state).

---

### 6. `"use client"` Directive -- Server vs. Client Components

Files that **use `"use client"`**:
- `src/app/overview/page.tsx` -- uses `useQuery`, `useProfile`, event handlers
- `src/app/analytics/page.tsx` -- uses `useQuery`, `useProfile`
- `src/app/pipeline/page.tsx` -- uses `useState`, `useEffect`, `useRef`, `useCallback`
- `src/app/error.tsx` -- uses `useEffect`, must be client-side (Error Boundaries require it)
- `src/components/providers.tsx` -- uses `useState` for `QueryClient`
- `src/components/layout/app-shell.tsx` -- uses `useState` for mobile menu, `useProfile`

Files that **do NOT use `"use client"`**:
- `src/app/layout.tsx` -- no hooks, no interactivity, pure JSX shell
- `src/app/page.tsx` -- server-side `redirect()`, no client code needed

**The rule is simple:** if a component uses React hooks (`useState`, `useEffect`, `useRef`, etc.), event handlers (`onClick`, `onChange`), or browser APIs (`window`, `document`), it must have `"use client"` at the top. Everything else stays as a Server Component by default.

**Why this matters:**
- Server Components ship **zero JavaScript** to the client. `layout.tsx` and `page.tsx` (the redirect) add nothing to the client bundle.
- Client Components are hydrated on the client and their code is included in the JavaScript bundle.
- The boundary is **per-file**, not per-component. Once you add `"use client"`, everything in that file and its imports (that do not have their own `"use client"`) becomes client-side.

---

### 7. Provider Nesting Order -- Dependency Chain

```tsx
// src/app/layout.tsx (lines 21-26)
<body className={`${inter.className} bg-gray-50 text-gray-800 antialiased`}>
  <Providers>
    <AppShell>{children}</AppShell>
  </Providers>
</body>
```

Where `<Providers>` is:

```tsx
// src/components/providers.tsx (complete file)
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
```

And `<AppShell>` wraps with `<ProfileProvider>`:

```tsx
// src/components/layout/app-shell.tsx (lines 47-53)
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ProfileProvider>
      <AppShellInner>{children}</AppShellInner>
    </ProfileProvider>
  );
}
```

**The nesting order is:**
```
<Providers>                    ← QueryClientProvider (React Query)
  <AppShell>                   ← Exported component
    <ProfileProvider>          ← Profile context
      <AppShellInner>          ← Sidebar + main content area
        {children}             ← The actual page component
      </AppShellInner>
    </ProfileProvider>
  </AppShell>
</Providers>
```

**Why order matters:**
- `QueryClientProvider` must be the outermost provider because `useQuery` calls inside `ProfileProvider` or any page need access to the query client.
- `ProfileProvider` must wrap `AppShellInner` because the sidebar uses `useProfile()` to show the current profile, and every page uses `useProfile()` to fetch profile-specific data.
- If you swapped them -- `ProfileProvider` outside `QueryClientProvider` -- then `ProfileProvider` could not use React Query hooks.

**Why `useState(() => new QueryClient(...))`?** This ensures the `QueryClient` is created only once per component lifecycle, not on every render. The lazy initializer `() => new QueryClient(...)` runs only on the first render. Without this, a new `QueryClient` would be created on every render, wiping out all cached data.

---

### 8. `lang="en"` Attribute -- Accessibility and i18n

```tsx
// src/app/layout.tsx (line 21)
<html lang="en">
```

**Why it matters:**
- **Screen readers** use the `lang` attribute to select the correct pronunciation rules. Without it, a screen reader might try to pronounce English text with default (possibly non-English) phonetics.
- **Search engines** use it to understand the page's language for indexing and serving in locale-appropriate search results.
- **Translation tools** (like Google Translate's auto-detect) use it as a hint.
- **Lighthouse/axe audits** flag missing `lang` attributes as accessibility violations.

This is a single attribute, but omitting it fails accessibility audits.

---

### 9. `antialiased` Class -- Font Smoothing

```tsx
// src/app/layout.tsx (line 22)
<body className={`${inter.className} bg-gray-50 text-gray-800 antialiased`}>
```

**What `antialiased` does:**

Tailwind's `antialiased` class applies:
```css
-webkit-font-smoothing: antialiased;
-moz-osx-font-smoothing: grayscale;
```

This tells the browser to use **subpixel antialiasing** on macOS/iOS, making text appear thinner and crisper. Without it, text can look slightly "bold" or "fuzzy" on Retina displays, especially with light-weight fonts like Inter.

This is a standard practice in modern web apps -- nearly every Tailwind project applies `antialiased` to the body.

---

### 10. File-Based Routing -- Folders as Routes

Each folder in `src/app/` automatically becomes a URL route:

| Folder | URL Path | What renders |
|--------|----------|-------------|
| `src/app/overview/` | `/overview` | `overview/page.tsx` |
| `src/app/applications/` | `/applications` | `applications/page.tsx` |
| `src/app/outcomes/` | `/outcomes` | `outcomes/page.tsx` |
| `src/app/emails/` | `/emails` | `emails/page.tsx` |
| `src/app/analytics/` | `/analytics` | `analytics/page.tsx` |
| `src/app/tracker/` | `/tracker` | `tracker/page.tsx` |
| `src/app/pipeline/` | `/pipeline` | `pipeline/page.tsx` |
| `src/app/startups/` | `/startups` | `startups/page.tsx` |

**No router configuration needed.** There is no `routes.ts`, no `<Route>` components, no `createBrowserRouter()`. The file system IS the router.

**Rules:**
- Only files named `page.tsx` are publicly accessible. A `utils.ts` or `components/` folder inside a route folder does not create a route.
- `layout.tsx` in any folder wraps all pages in that folder and its subfolders.
- `error.tsx` in any folder provides an error boundary for that segment.
- `loading.tsx` in any folder shows a loading UI while the page's data is being fetched.

The root `page.tsx` at `src/app/page.tsx` maps to `/`, and its `redirect("/overview")` means visiting the root URL immediately sends the user to the overview page.

---

## How It Works -- Request Lifecycle

Here is what happens when a user visits `https://your-app.com/analytics`:

1. **Next.js resolves the route** -- The URL `/analytics` maps to `src/app/analytics/page.tsx`.

2. **Layout tree is built** -- Next.js composes the layout chain: `src/app/layout.tsx` wraps `src/app/analytics/page.tsx`. If `analytics/layout.tsx` existed, it would be nested between them.

3. **Server Components render** -- `layout.tsx` is a Server Component. It renders the `<html>`, `<body>`, and provider structure on the server. No JavaScript for this component is sent to the client.

4. **Client Components are marked** -- `analytics/page.tsx` has `"use client"`, so Next.js includes it in the client bundle. The server renders its initial HTML (for fast first paint), then the client hydrates it.

5. **Metadata is collected** -- The `metadata` export from `layout.tsx` is used to generate `<head>` tags. If `analytics/page.tsx` also exported metadata, it would be merged/overridden.

6. **Font is loaded** -- The Inter font was already downloaded at build time. `inter.className` applies the font-face CSS. No runtime font fetch occurs.

7. **Providers initialize** -- `QueryClientProvider` creates the query client (once). `ProfileProvider` reads the profile ID from localStorage.

8. **Page renders** -- `AnalyticsPage` runs `useQuery`, which triggers API calls. While loading, skeleton charts are shown. When data arrives, Recharts renders the 6 charts.

9. **Error handling** -- If the page throws during render, `error.tsx` catches it and shows the error UI with a "Try again" button.

---

## Interview Talking Points

1. **"The App Router uses file-system conventions instead of configuration."** -- I do not define routes in a config file. Each folder under `src/app/` with a `page.tsx` is a route. This makes the project structure self-documenting -- you can see all routes by listing the app directory.

2. **"I understand the Server/Client Component boundary."** -- The root layout is a Server Component that ships zero JavaScript. Only files with `"use client"` (pages with hooks, providers with state) are included in the client bundle. This is a deliberate design -- the layout, redirect, and metadata are server-only by default.

3. **"Provider nesting order matters because of dependency chains."** -- `QueryClientProvider` wraps everything because `useQuery` is used inside `ProfileProvider` and every page. `ProfileProvider` wraps the shell because the sidebar and pages both need the profile ID. Swapping the order would break hooks that depend on the outer provider.

4. **"The `error.tsx` convention replaces manual Error Boundary setup."** -- In React 18, you would wrap routes in `<ErrorBoundary>` components manually. In the App Router, just creating an `error.tsx` file gives you automatic error boundaries with `reset` functionality. The `digest` property on the error lets you correlate client-side errors with server logs in production.

5. **"Font optimization with `next/font` eliminates FOUT and external dependencies."** -- The Inter font is downloaded at build time, self-hosted, and preloaded. Users never see a font flash, and no runtime request goes to Google's CDN. This is a concrete performance and privacy improvement over traditional `<link>` font loading.

6. **"The server-side redirect at the root uses HTTP 307, not client-side routing."** -- When users visit `/`, they get a 307 redirect to `/overview` before any JavaScript loads. This is faster, works without JS, and is correct for SEO (search engines follow 307 redirects).

---

## Common Questions

### Q: Why does `layout.tsx` not have `"use client"` even though it renders `<Providers>` which does?

The layout itself is a Server Component. It renders `<Providers>` as a child, but `Providers` is a separate file with its own `"use client"` directive. Server Components can render Client Components as children -- the boundary is at the file level, not the JSX tree level. The layout's own code (metadata export, font initialization, `<html>`/`<body>` tags) runs on the server with zero client JavaScript.

### Q: What is `error.digest` for?

When an error occurs in a Server Component, Next.js strips the error message for security (to avoid leaking server internals to the client). It replaces it with a short hash called `digest`. You can log this hash on the server and use it to correlate the client-visible error with the full server-side stack trace. For client-side errors, `digest` is undefined because the full error is already available.

### Q: Why use `useState(() => new QueryClient())` instead of creating it outside the component?

Creating the `QueryClient` outside the component would create a **singleton** shared across all requests in a server-rendered environment. During SSR, different users' requests would share the same cache, causing data to leak between users. `useState` with a lazy initializer creates a new `QueryClient` per component instance, which is per-request during SSR and once-per-mount on the client.

### Q: What happens if I put a `layout.tsx` inside the `analytics/` folder?

It would wrap only the analytics page (and any sub-routes of `/analytics/...`). The nesting would be:
```
Root layout → Analytics layout → Analytics page
```
The root sidebar/providers would still be there, and the analytics layout would add analytics-specific UI (e.g., a sub-navigation or filter bar) between the sidebar and the page content.

### Q: Why is `page.tsx` needed? Why not just export from `overview/index.tsx`?

This is a convention of the App Router. `page.tsx` is a **special filename** that tells Next.js "this is a publicly routable page." Other files in the folder (like `components.tsx`, `utils.ts`, or `types.ts`) are private -- they are NOT routable. This prevents accidentally exposing helper files as routes, which was a common issue in the older Pages Router where any file in `pages/` became a route.

### Q: Does navigation between pages re-render the layout?

No. The root layout persists across navigations. When you go from `/overview` to `/analytics`, only the `{children}` inside the layout re-renders. The `<html>`, `<body>`, `<Providers>`, and `<AppShell>` (sidebar, mobile header) stay mounted. This is why the sidebar does not flash or re-animate when you click a nav link -- it is the same component instance.

### Q: What is the difference between `redirect()` in a Server Component and `useRouter().push()` in a Client Component?

| | `redirect()` (Server) | `useRouter().push()` (Client) |
|---|---|---|
| **Where it runs** | Server, during rendering | Client, after hydration |
| **HTTP response** | 307 redirect (no HTML body) | Client-side navigation (no HTTP redirect) |
| **JavaScript required?** | No | Yes |
| **SEO** | Search engines follow 307 | Search engines may not execute JS |
| **Speed** | Immediate (no JS download) | Requires JS bundle to load first |
| **Use case** | Permanent/unconditional redirects | Conditional redirects after user action |

The root `page.tsx` uses `redirect()` because the redirect is unconditional and should happen before any client code runs.
