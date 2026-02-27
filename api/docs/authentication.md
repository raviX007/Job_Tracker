# Authentication & CORS

The API has two authentication layers:

1. **API Key** (`X-API-Key` header) — service-to-service auth for the pipeline and dashboard
2. **JWT User Auth** (register/login) — user-facing auth for the dashboard UI

---

## JWT User Authentication

User accounts are stored in the `users` table in PostgreSQL. Passwords are hashed with **bcrypt** and sessions use **JWT tokens**.

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Endpoints

**File:** `api/api/routers/auth.py` (public — no API key required)

| Method | Endpoint | Request Body | Response |
|--------|----------|-------------|----------|
| `POST` | `/api/auth/register` | `{"username": "...", "password": "..."}` | `{"token": "jwt...", "username": "..."}` |
| `POST` | `/api/auth/login` | `{"username": "...", "password": "..."}` | `{"token": "jwt...", "username": "..."}` |

**Validation:**
- Register: username 3-100 chars, password 8-128 chars
- Login: username and password required (min 1 char)

**Error responses:**
- `409` — Username already taken (register)
- `401` — Invalid username or password (login)

### How It Works

**File:** `core/auth.py`

```
Register:  plaintext password → bcrypt.hashpw() → stored in DB
Login:     plaintext password → bcrypt.checkpw() against stored hash
Token:     jwt.encode({sub: user_id, username, iat, exp}, JWT_SECRET, HS256)
```

1. **Register:** Hash password with bcrypt, insert into `users` table, return JWT
2. **Login:** Fetch user by username, verify password with bcrypt, return JWT
3. **Token payload:** `{sub: "<user_id>", username: "<name>", iat: <now>, exp: <now + 24h>}`

### Configuration

```bash
# .env
JWT_SECRET=your-64-char-random-secret    # Required for JWT signing
JWT_EXPIRY_HOURS=24                       # Token lifetime (default: 24h)
```

Generate a secure secret:
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Frontend Flow

The dashboard (`ui-next`) stores the JWT in `localStorage`:

1. User submits login/register form
2. Frontend calls `/api/auth/register` or `/api/auth/login`
3. On success, stores `auth_token` and `auth_username` in `localStorage`
4. All subsequent API requests include `Authorization: Bearer <token>` header
5. On 401 response, frontend redirects to login page

---

## API Key Authentication

All endpoints except `/api/health` and `/api/auth/*` require the `X-API-Key` header.

### How It Works

Defined in `api/deps.py` as `verify_auth` (aliased as `verify_api_key`). Accepts **either** an API key or JWT, with the following priority:

```python
async def verify_auth(request, x_api_key, authorization):
    # 1. API key → allow (also decodes JWT if present for user_id)
    # 2. Bearer JWT → allow (sets request.state.user_id)
    # 3. No API_SECRET_KEY configured → allow all (local dev)
    # 4. Otherwise → 401
```

When the UI sends **both** `X-API-Key` and `Authorization: Bearer <token>`, the API key validates the request **and** the JWT is decoded to populate `request.state.user_id`. This is required for user-scoped endpoints like `/api/profiles/me`.

### Configuration

Set `API_SECRET_KEY` in `.env`:

```bash
# Generate a secure key:
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set in .env:
API_SECRET_KEY=your-generated-key-here
```

### Behavior

| API_SECRET_KEY | Behavior |
|----------------|----------|
| Empty string `""` | Auth disabled — all requests pass (local dev) |
| Non-empty value | Every request must include matching `X-API-Key` header |

### Usage

```bash
# With auth enabled:
curl -H "X-API-Key: your-key" http://localhost:8000/api/overview/stats?profile_id=1

# Health check (never requires auth):
curl http://localhost:8000/api/health
```

### Router-Level Auth

Auth is applied at the `include_router` level in `server.py`. Each router is included with the `verify_auth` dependency, except health and auth routers which are public:

```python
from api.deps import verify_api_key  # alias for verify_auth

# Public routers (no auth)
app.include_router(health.router)
app.include_router(auth.router)

# All other routers require API key or JWT
_auth = [Depends(verify_api_key)]
app.include_router(profiles.router, dependencies=_auth)
app.include_router(overview.router, dependencies=_auth)
app.include_router(applications.router, dependencies=_auth)
# ... all other routers
```

This ensures all endpoints (except health and auth) require a valid API key or JWT without repeating the dependency in each router.

---

## CORS Configuration

Cross-Origin Resource Sharing is configured to allow the Streamlit dashboard to make API calls.

### Configuration

Set `ALLOWED_ORIGINS` in `.env`:

```bash
# Single origin (local dev):
ALLOWED_ORIGINS=http://localhost:8501

# Multiple origins (comma-separated):
ALLOWED_ORIGINS=http://localhost:8501,https://your-app.streamlit.app
```

### Applied Settings

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key", "Accept", "Authorization"],
    expose_headers=["X-Total-Count", "X-Request-ID"],
)
```

- `allow_headers` is explicitly scoped (not `*`) to the headers the API actually uses.
- `expose_headers` makes `X-Total-Count` (pagination) and `X-Request-ID` (error correlation) accessible to browser clients.

### Defaults

If `ALLOWED_ORIGINS` is not set, it defaults to `http://localhost:8501` (local Streamlit).

---

---

## Rate Limiting

Global rate limiting is applied via `slowapi` (60 requests/minute per IP):

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

When the limit is exceeded, the API returns `429 Too Many Requests`.

---

## Request ID Correlation

Every request receives a unique 8-character `request_id` via the `RequestLoggingMiddleware`. This ID is:
- Returned in the `X-Request-ID` response header
- Included in error response bodies (`{"detail": "...", "request_id": "abc12345"}`)
- Logged alongside every request in the server logs

This makes it easy to correlate errors between client and server.

---

## Security Headers

Every API response includes security headers via `SecurityHeadersMiddleware` in `server.py`:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-type sniffing |
| `X-Frame-Options` | `DENY` | Prevents clickjacking via iframes |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Controls referrer information |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Disables unnecessary browser APIs |
| `X-DNS-Prefetch-Control` | `off` | Disables DNS prefetching for privacy |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Forces HTTPS (only added when behind HTTPS/proxy) |

HSTS is conditionally added — only when the request arrives via HTTPS (direct or via `x-forwarded-proto` from a reverse proxy like Render). This prevents issues in local HTTP development.

The frontend (`ui-next/next.config.ts`) has the same set of headers, ensuring consistent protection across both services.

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| API key in transit | Use HTTPS in production (Render enforces this) |
| API key in code | Stored in `.env` (gitignored) or Render env vars |
| API key comparison | Constant-time (`secrets.compare_digest`) to prevent timing attacks |
| Password storage | bcrypt hashing with random salt (never stored in plaintext) |
| JWT secret | Stored in `.env` (gitignored), 48+ byte random secret |
| JWT token lifetime | 24-hour expiry (configurable via `JWT_EXPIRY_HOURS`) |
| CORS too permissive | Only allow specific origins, explicit `allow_headers` |
| Rate limiting | 60 req/min per IP via slowapi |
| Security headers | X-Frame-Options, X-Content-Type-Options, HSTS, Referrer-Policy on all responses |
| Error information leakage | Unhandled exceptions return generic 500 with request_id only (no stack trace) |
