# 14 - Production Deployment & Security Headers

## What Is It

Production deployment configuration is the bridge between "it works on my laptop" and "it runs securely in the cloud." In this codebase, two files handle everything:

1. **`next.config.ts`** -- configures the Next.js build output mode and injects HTTP security headers into every response.
2. **`Dockerfile`** -- defines a two-stage Docker build that produces a minimal, non-root production image.

Together they solve three concerns: **small image size** (standalone output + multi-stage build), **security hardening** (HTTP headers + non-root user), and **container compatibility** (listening on all interfaces).

---

## Why We Chose This

| Concern | Decision | Alternative Rejected |
|---------|----------|---------------------|
| Image size | `output: "standalone"` bundles only used dependencies | Default output needs the full `node_modules` (500MB+) |
| Security headers | Declared in `next.config.ts` | Could use middleware or a reverse proxy, but config is simpler and co-located |
| Docker build time | Multi-stage build separates build-time deps from runtime | Single-stage image carries compilers, devDependencies, and source code into production |
| Privilege escalation | Non-root `nextjs` user with UID 1001 | Running as root is the Docker default but violates principle of least privilege |
| Network binding | `HOSTNAME="0.0.0.0"` | Default `localhost` works on bare metal but is unreachable from outside a container |

---

## Real Code Examples

### next.config.ts

**File: `next.config.ts`**

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          { key: "X-DNS-Prefetch-Control", value: "on" },
        ],
      },
    ];
  },
};

export default nextConfig;
```

### Dockerfile

**File: `Dockerfile`**

```dockerfile
FROM node:22-slim AS builder
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app

ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
```

---

## How It Works

### 1. Standalone Output Mode

When `output: "standalone"` is set in the Next.js config, `npm run build` produces a special `.next/standalone/` directory. This directory contains:

- A self-contained `server.js` that can be run with `node server.js` (no `next start` needed).
- Only the `node_modules` files that are actually imported by the application (tree-shaken).
- All compiled server-side code.

What it does **not** include (and must be copied separately):
- `.next/static/` -- client-side JavaScript bundles, CSS, and other static assets.
- `public/` -- images, fonts, and other files served at the root path.

This is why the Dockerfile has three `COPY --from=builder` lines -- each copies one of these three pieces.

The result: a production image that might be 150MB instead of 800MB+, because the full `node_modules` (with devDependencies, TypeScript compiler, ESLint, etc.) is left behind in the builder stage.

### 2. Security Headers -- One by One

The `headers()` function in `next.config.ts` returns an array of header rules. Each rule has a `source` pattern (which routes to apply to) and a list of header key-value pairs.

**`source: "/(.*)"` -- the wildcard pattern:**

This regex matches every single route -- pages, API routes, static files, everything. It means these security headers are applied globally. You do not need to remember to add them to new routes.

**`X-Frame-Options: DENY`:**

Prevents the page from being embedded inside an `<iframe>` on any domain. This blocks **clickjacking attacks** where an attacker overlays your page with a transparent iframe and tricks users into clicking hidden buttons. `DENY` is stricter than `SAMEORIGIN` (which would allow same-domain iframes).

```
Attacker's page:
+-----------------------------------+
| "Click here to win a prize!"      |  <-- visible bait
| +-------------------------------+ |
| | YOUR APP (invisible iframe)   | |  <-- actual click target
| | [Delete Account] button       | |
| +-------------------------------+ |
+-----------------------------------+

With X-Frame-Options: DENY, the browser refuses to load your app in the iframe at all.
```

**`X-Content-Type-Options: nosniff`:**

Tells the browser: "Trust the `Content-Type` header I send you. Do not try to guess the file type by looking at the content." Without this, a browser might take a `.txt` file containing `<script>alert('xss')</script>` and execute it as JavaScript because it "looks like" HTML. This is called **MIME-sniffing** and `nosniff` prevents it entirely.

**`Referrer-Policy: strict-origin-when-cross-origin`:**

Controls what information is sent in the `Referer` header when a user navigates away from your site:

| Navigation Type | What Gets Sent |
|----------------|----------------|
| Same origin (your-app.com/a -> your-app.com/b) | Full URL including path |
| Cross-origin, same protocol (your-app.com -> google.com, both HTTPS) | Origin only (e.g., `https://your-app.com`) |
| HTTPS -> HTTP downgrade | Nothing at all |

This prevents leaking internal URL paths (which might contain sensitive query parameters) to third-party sites while still providing useful analytics data for same-origin navigation.

**`Permissions-Policy: camera=(), microphone=(), geolocation=()`:**

Explicitly disables browser APIs that this application does not need. The empty parentheses `()` mean "no origin is allowed to use this feature." Even if an XSS attack injects JavaScript that calls `navigator.geolocation.getCurrentPosition()`, the browser will deny it.

This follows the **principle of least privilege**: if you do not need the camera, declare that you do not need it, so no one can abuse it.

**`X-DNS-Prefetch-Control: on`:**

This is the one **performance** header (not security). It tells the browser to proactively resolve DNS for any domains linked on the page. If your page contains a link to `https://github.com/some-repo`, the browser will resolve `github.com`'s IP address in the background before the user clicks the link. This shaves off 20-120ms of latency when they do click.

### 3. Two-Stage Docker Build

```
Stage 1: "builder"                    Stage 2: "runner"
+---------------------------+         +---------------------------+
| node:22-slim              |         | node:22-slim              |
| + package.json            |         | + standalone/ (server.js  |
| + node_modules/ (ALL)     |    +--->|   + minimal node_modules) |
| + source code             |    |    | + .next/static/           |
| + .next/ (build output)   |----+    | + public/                 |
| + TypeScript compiler     |         |                           |
| + ESLint, Prettier, etc.  |         | USER: nextjs (UID 1001)   |
+---------------------------+         +---------------------------+
       ~800MB                                 ~150MB
```

**Stage 1 (`builder`):**
- Starts from `node:22-slim` (Debian-based, minimal Node.js image).
- `COPY package.json package-lock.json* ./` -- copies only the dependency manifests first. The `*` after `package-lock.json` makes it optional (does not fail if missing).
- `RUN npm ci` -- installs exact versions from the lockfile. This step is cached by Docker as long as `package.json` and `package-lock.json` do not change. This is a major build-time optimization: changing source code does not re-install dependencies.
- `COPY . .` -- copies the rest of the source code.
- `RUN npm run build` -- runs the Next.js build, which produces `.next/standalone/`, `.next/static/`, and other build artifacts.

**Stage 2 (`runner`):**
- Starts from a fresh `node:22-slim` -- none of the builder's files exist here.
- Creates a non-root user (explained below).
- Copies exactly three things from the builder.
- Sets `NODE_ENV=production` so libraries like React use their production builds.
- Runs `server.js` directly with Node.js (not `npx next start`).

### 4. Non-Root User

```dockerfile
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs
```

This creates:
- A **system group** named `nodejs` with GID 1001.
- A **system user** named `nextjs` with UID 1001, belonging to the `nodejs` group.

The `--system` flag means: no home directory, no login shell, not a real human user. Just a service account.

```dockerfile
USER nextjs
```

Every command after this line (including `CMD`) runs as the `nextjs` user, not as `root`. If an attacker exploits a vulnerability in the application, they can only do what the `nextjs` user can do -- which is very little. They cannot install packages, modify system files, or escalate privileges (in a properly configured container runtime).

**Why UID 1001 specifically?** UID 0 is root. UIDs 1-999 are reserved for system services on most Linux distributions. Starting at 1001 avoids conflicts with any pre-existing system users in the base image.

### 5. The Three Files That Get Copied

```dockerfile
COPY --from=builder /app/.next/standalone ./        # Server + bundled deps
COPY --from=builder /app/.next/static ./.next/static  # Client-side assets
COPY --from=builder /app/public ./public              # Static files (favicon, images)
```

- **`.next/standalone`** contains `server.js` and a pruned `node_modules/` with only production dependencies. This is the application itself.
- **`.next/static`** contains the compiled client-side JavaScript bundles, CSS files, and webpack chunks. These are served by the built-in file server in `server.js`.
- **`public/`** contains static files like `favicon.ico` or images that are served at the root path (`/favicon.ico`, not `/_next/static/favicon.ico`).

### 6. HOSTNAME="0.0.0.0"

```dockerfile
ENV HOSTNAME="0.0.0.0"
```

By default, Next.js listens on `localhost` (127.0.0.1). This works on bare metal because the browser and the server are on the same machine. In a Docker container, `localhost` refers to the container's own loopback interface -- traffic from the host machine or a reverse proxy cannot reach it.

Setting `HOSTNAME="0.0.0.0"` tells the server to listen on **all network interfaces**, which includes the Docker bridge network. This is what makes `docker run -p 3000:3000` actually work.

### 7. Typed Configuration

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // ...
};
```

The `import type` syntax imports only the TypeScript type (not a runtime value). `NextConfig` gives you:

- **Autocomplete** in your editor for all valid Next.js config options (`output`, `images`, `redirects`, `rewrites`, etc.).
- **Type errors** if you misspell an option name or pass the wrong type (e.g., `output: true` instead of `output: "standalone"`).
- **Documentation on hover** -- most editors show the JSDoc comments for each option.

Using `.ts` instead of `.js` for the config file is supported natively by Next.js 15+ and requires no additional setup.

---

## Interview Talking Points

1. **"We use standalone output mode to reduce our Docker image from ~800MB to ~150MB."** This shows you understand the cost of shipping `node_modules` and why tree-shaking at the build level matters for deployment.

2. **"We apply security headers at the framework level in `next.config.ts` rather than in a reverse proxy."** This demonstrates you know there are multiple places to set headers and you chose co-location with the application code for maintainability.

3. **"The two-stage Docker build separates build-time dependencies from runtime."** This is a fundamental Docker pattern. The builder stage has TypeScript, ESLint, and all devDependencies. The runner stage has only what is needed to serve requests.

4. **"We run the container as a non-root user with a specific UID."** This shows security awareness. Many production Kubernetes clusters enforce non-root containers via PodSecurityPolicies or OPA Gatekeeper.

5. **"The `COPY package.json` before `COPY . .` pattern leverages Docker layer caching."** If you only change source code (not dependencies), Docker reuses the cached `npm ci` layer, cutting build times from minutes to seconds.

6. **"We set `HOSTNAME=0.0.0.0` because Docker containers have isolated network namespaces."** This shows you understand container networking. `localhost` inside a container is not the same as `localhost` on the host.

7. **"Each security header addresses a specific attack vector."** Being able to name the attack each header prevents (clickjacking, MIME-sniffing, referrer leakage, API abuse) shows depth beyond just copy-pasting a security checklist.

---

## Common Questions

### Q: Why not use `Content-Security-Policy` (CSP)?

CSP is the most powerful security header but also the most complex. It requires listing every domain your scripts, styles, images, and fonts are loaded from. In a Next.js app with inline styles (from CSS-in-JS or Tailwind), you need `unsafe-inline` or nonce-based CSP, which adds complexity. The headers we have are the "easy wins" -- high security value with zero configuration burden. CSP can be added later as a separate effort.

### Q: Why `npm ci` instead of `npm install`?

`npm ci` (clean install) does three things differently:
1. Deletes `node_modules/` first (clean slate).
2. Installs exact versions from `package-lock.json` (never modifies the lockfile).
3. Fails if `package-lock.json` is out of sync with `package.json`.

This guarantees reproducible builds. `npm install` might update the lockfile, leading to "works on my machine" drift.

### Q: What if I need to serve the app on a different port?

Change `ENV PORT=3000` and `EXPOSE 3000` in the Dockerfile. The `server.js` generated by standalone mode reads the `PORT` environment variable at runtime. You can also override it at `docker run` time: `docker run -e PORT=8080 -p 8080:8080 myapp`.

### Q: Why `node:22-slim` instead of `node:22-alpine`?

Alpine uses `musl` libc instead of `glibc`. Some npm packages with native bindings (like `sharp` for image optimization) have compatibility issues with musl. `slim` is Debian-based with glibc, which has broader compatibility. The size difference is ~30MB (slim ~180MB vs alpine ~150MB), which is negligible compared to the savings from standalone mode.

### Q: Why not use `next start` in the CMD?

`next start` requires the `next` package to be installed (it is a CLI command from `node_modules/.bin/next`). In standalone mode, the `next` package is not in the pruned `node_modules`. The generated `server.js` is a self-contained Node.js script that does not need the `next` CLI at all. Running `node server.js` directly is simpler and has one fewer layer of indirection.

### Q: What is the `package-lock.json*` glob for?

The `*` makes the `COPY` command succeed even if `package-lock.json` does not exist (e.g., if someone uses `yarn` or `pnpm` instead). Without the glob, Docker would fail the build with "file not found." This makes the Dockerfile more portable across package managers, though `npm ci` itself still requires the lockfile to exist.

### Q: Are these headers enough for production?

They are a strong baseline. For a full production hardening, you would also consider:
- `Strict-Transport-Security` (HSTS) -- force HTTPS, usually set at the load balancer / reverse proxy level.
- `Content-Security-Policy` -- restrict which scripts/styles/images can load.
- Rate limiting -- usually handled by an API gateway or reverse proxy (nginx, Cloudflare).
- CORS headers -- if your API is consumed by other domains.

The headers in `next.config.ts` cover the application-level concerns. Infrastructure-level concerns (HSTS, rate limiting) are typically handled by the layer in front of the application.
