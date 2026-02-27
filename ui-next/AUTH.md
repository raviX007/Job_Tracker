# Authentication

The Job Tracker UI uses JWT-based authentication. All dashboard pages are gated behind a login screen — unauthenticated users are redirected to `/login`.

## Architecture

```
Browser ──► Next.js Middleware (cookie check) ──► Dashboard pages
                │                                      │
                │ no cookie → redirect /login           │ API calls with Bearer token
                │                                      ▼
                ▼                                  FastAPI backend
          Login page ──► POST /api/auth/login ──►  (JWT or API key)
```

### Token Storage (Dual Strategy)

The JWT is stored in **two places** to serve different purposes:

| Storage        | Purpose                                                  |
| -------------- | -------------------------------------------------------- |
| **Cookie**     | Read by Next.js middleware (server-side route protection) |
| **localStorage** | Read by the API client (client-side `Authorization` header) |

The cookie is set with `SameSite=Lax` and a 24-hour `max-age`. It is **not** `HttpOnly` because the middleware runs on the Edge Runtime and only checks for the cookie's existence — it does not decode the JWT.

## Key Files

| File | Role |
| ---- | ---- |
| `src/middleware.ts` | Route guard — redirects to `/login` if `auth_token` cookie is missing |
| `src/app/(auth)/login/page.tsx` | Login and registration UI |
| `src/lib/api.ts` | API client — injects `Authorization: Bearer` header, handles 401 |
| `src/components/layout/sidebar.tsx` | Sign-out button — clears all auth state |

## How It Works

### 1. Middleware (`src/middleware.ts`)

Runs on every request before the page renders. It checks for the `auth_token` cookie:

- **Public paths** (`/login`, `/register`) — allowed through without a cookie.
- **Static assets** (`/_next`, `/favicon`, files with extensions) — allowed through.
- **Everything else** — if no `auth_token` cookie exists, the user is redirected to `/login`.

The middleware does **not** decode or validate the JWT. It only checks for the cookie's presence. Actual token validation happens on the backend when API calls are made.

```
matcher: /((?!_next/static|_next/image|favicon\.ico|favicon\.svg).*)
```

### 2. Login Page (`src/app/(auth)/login/page.tsx`)

A full-screen card component that supports both **login** and **registration** modes, toggled via an inline text link.

On form submission:
1. Sends `POST` to `/api/auth/login` (or `/api/auth/register`).
2. Receives `{ token, username }` from the backend.
3. Stores the token:
   - `document.cookie = auth_token=<token>; path=/; max-age=86400; SameSite=Lax`
   - `localStorage.setItem("auth_token", token)`
   - `localStorage.setItem("auth_username", username)`
4. Redirects to `/overview`.

Registration enforces minimum username length (3 chars) and password length (8 chars) via HTML `minLength` attributes.

### 3. API Client (`src/lib/api.ts`)

Every API request includes the JWT in the `Authorization` header:

```ts
headers["Authorization"] = `Bearer ${localStorage.getItem("auth_token")}`;
```

If any API call returns a **401** response:
1. `auth_token` and `auth_username` are removed from localStorage.
2. The `auth_token` cookie is cleared (`max-age=0`).
3. The browser is redirected to `/login`.

This handles JWT expiration — when the 24-hour token expires, the next API call triggers an automatic logout.

### 4. Sign Out (`src/components/layout/sidebar.tsx`)

The sidebar's **Sign Out** button clears all auth state:

```ts
localStorage.removeItem("auth_token");
localStorage.removeItem("auth_username");
localStorage.removeItem("job-tracker-profile-id");
document.cookie = "auth_token=; path=/; max-age=0";
window.location.href = "/login";
```

Uses `window.location.href` (not `router.push`) to force a full page reload, ensuring the middleware runs and no stale state remains.

## Route Groups

The app uses Next.js route groups to apply different layouts:

```
src/app/
├── (auth)/
│   └── login/page.tsx      ← No sidebar, bare layout
├── (dashboard)/
│   ├── layout.tsx           ← Wraps children in AppShell (sidebar + header)
│   ├── overview/page.tsx
│   ├── applications/page.tsx
│   └── ...
└── layout.tsx               ← Root layout (Providers only, no shell)
```

Route groups `(auth)` and `(dashboard)` do not affect URLs — `/login` and `/overview` work as expected.

## Backend Auth (Summary)

The FastAPI backend supports **dual-mode authentication**:

| Method | Header | Use Case |
| ------ | ------ | -------- |
| JWT Bearer | `Authorization: Bearer <token>` | UI requests (from logged-in users) |
| API Key | `X-API-Key: <key>` | Service-to-service requests (pipeline) |

- **POST `/api/auth/register`** — creates a new user account, returns JWT.
- **POST `/api/auth/login`** — validates credentials, returns JWT.
- JWTs are signed with HS256 and expire after 24 hours (configurable via `JWT_EXPIRY_HOURS`).
- Passwords are hashed with bcrypt before storage.

## Environment Variables

| Variable | Where | Purpose |
| -------- | ----- | ------- |
| `NEXT_PUBLIC_API_URL` | `ui-next/.env` | Backend API base URL |
| `JWT_SECRET` | `api/.env` | Secret key for signing JWTs |
| `JWT_EXPIRY_HOURS` | `api/.env` | Token lifetime in hours (default: 24) |
| `API_SECRET_KEY` | `api/.env` | API key for pipeline/service auth |
