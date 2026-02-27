# Architecture

## System Overview

The Job Tracker API is an async FastAPI backend that sits between the pipeline microservice and the Next.js dashboard. It owns the PostgreSQL database and is the only service with direct DB access.

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Pipeline Service │     │   FastAPI API      │     │  Next.js UI       │
│  (port 8002)      │←──→│  (port 8000)       │←────│  (port 3000)      │
│  scrape, analyze, │     │  (this project)    │     │  (dashboard)      │
│  email gen        │     │                    │     │                    │
└──────────────────┘     └────────┬───────────┘     └──────────────────┘
                                  │
                         ┌────────▼───────────┐
                         │   PostgreSQL        │
                         │   (Neon free tier)  │
                         └────────────────────┘
```

**Data flow:**
- **UI → API → Pipeline Service:** UI triggers pipeline run, API dispatches to pipeline service via `POST /run`
- **Pipeline Service → API (callback):** Reports status updates via `PATCH /api/pipeline/runs/{run_id}/callback`
- **Pipeline → API:** Writes jobs, analyses, emails, startup profiles via POST/PUT endpoints
- **API → Dashboard:** Reads aggregated data via GET endpoints with filters and joins
- **Dashboard → API:** Writes application tracking, email edits, sends via POST/PUT/DELETE

---

## Key Design Patterns

### 1. Async-First

Every database operation, HTTP call, and email send is async:

- **Database:** `asyncpg` with native PostgreSQL binary protocol (not SQLAlchemy)
- **HTTP client:** `httpx.AsyncClient` for job link checks
- **Email:** `aiosmtplib` for non-blocking SMTP delivery

This means the server can handle concurrent requests without blocking on I/O.

### 2. Connection Pooling

```python
pool = await asyncpg.create_pool(
    dsn=DATABASE_URL,
    min_size=2,
    max_size=10,
    ssl="require",                        # Required for Neon
    command_timeout=30,                   # Prevent hung queries
    max_inactive_connection_lifetime=300, # Refresh stale connections
)
```

The pool is created once at app startup (via FastAPI lifespan) and shared across all requests. This prevents exhausting Neon's free-tier connection limits.

- `command_timeout=30` kills any query that takes longer than 30 seconds, preventing hung connections from blocking the pool.
- `max_inactive_connection_lifetime=300` refreshes idle connections every 5 minutes, avoiding stale connections after Neon auto-suspends.

### 3. Idempotent Writes

Most insert operations use `ON CONFLICT DO UPDATE` or `ON CONFLICT DO NOTHING`:

```sql
-- Job insertion (skip if dedup_key exists)
INSERT INTO jobs (...) VALUES (...)
ON CONFLICT (dedup_key) DO NOTHING RETURNING id

-- Analysis upsert (update score if re-analyzed)
INSERT INTO job_analyses (...) VALUES (...)
ON CONFLICT (job_id, profile_id) DO UPDATE SET ...
```

This makes the pipeline safe to re-run without creating duplicates.

### 4. Raw SQL (No ORM)

All queries are hand-written SQL executed via asyncpg. This gives:
- Full control over query plans and joins
- No ORM overhead or query generation
- Direct use of PostgreSQL-specific features (TEXT[], JSONB, LATERAL joins)

### 5. Modular Router Architecture

Endpoints are organized into focused router modules under `api/routers/`. Each module owns a single feature area (e.g., `analytics.py`, `emails.py`, `pipeline.py`). The main `api/server.py` is a slim orchestrator (~130 lines) that configures middleware, exception handlers, rate limiting, and includes the routers.

```python
# server.py — router registration with auth
app.include_router(health.router)                        # public
_auth = [Depends(verify_api_key)]
app.include_router(applications.router, dependencies=_auth)
app.include_router(emails.router, dependencies=_auth)
# ... all other routers with _auth
```

### 6. Rate Limiting

Global rate limiting via `slowapi` (60 requests/minute per IP). Applied automatically to all endpoints. The health endpoint is naturally excluded from auth but still rate-limited.

```python
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
```

### 7. Global Error Handling

All unhandled exceptions are caught and returned with a `request_id` for correlation:

- **HTTPException:** Returns `{ "detail": "...", "request_id": "abc12345" }`
- **Unhandled Exception:** Logs full traceback with request_id, returns generic 500

Every request gets a unique 8-character `request_id` via the `RequestLoggingMiddleware`, also returned in the `X-Request-ID` response header.

### 8. Type Safety

- **Request validation:** Pydantic v2 models in `api/models.py`
- **Response shaping:** `_rows()` helper converts asyncpg Records to JSON-safe dicts
- **Date handling:** `_parse_date_or_none()` safely parses ISO dates

---

## Module Responsibilities

| Module | File | Purpose |
|--------|------|---------|
| FastAPI app | `api/server.py` | App setup, middleware, lifespan, rate limiting, router registration |
| Auth dependency | `api/deps.py` | `verify_api_key` — constant-time API key validation |
| Shared helpers | `api/helpers.py` | `_rows`, `_ParamBuilder`, `_parse_date_or_none` |
| Request models | `api/models.py` | Pydantic models for POST/PUT bodies |
| Health router | `api/routers/health.py` | `GET /api/health` — public, no auth |
| Overview router | `api/routers/overview.py` | Dashboard KPI stats |
| Applications router | `api/routers/applications.py` | 7 application CRUD endpoints |
| Emails router | `api/routers/emails.py` | 10 email queue + SMTP sending endpoints |
| Analytics router | `api/routers/analytics.py` | 6 analytics/chart endpoints |
| Tracker router | `api/routers/tracker.py` | Spreadsheet-style tracker view |
| Jobs router | `api/routers/jobs.py` | Obsolete toggle, link check |
| Pipeline router | `api/routers/pipeline.py` | Pipeline write endpoints + orchestration (dispatch to pipeline service, callback, polling) |
| Startup Profiles router | `api/routers/startup_profiles.py` | 4 startup metadata CRUD endpoints |
| DB pool | `core/database.py` | Connection pool creation, table verification |
| Logging | `core/logger.py` | Structured logging — JSON or colored console (`LOG_FORMAT` env var), Datadog-extensible |
| Schema | `db/schema.sql` | DDL for all 7 tables + indexes |

---

## Request Lifecycle

```
Client Request
    │
    ▼
CORS Middleware (check origin)
    │
    ▼
RequestLoggingMiddleware (assign request_id, log method/path/status/duration)
    │
    ▼
Rate Limiter (slowapi — 60 req/min per IP)
    │
    ▼
verify_api_key() dependency (check X-API-Key header; skipped for /api/health)
    │
    ▼
Endpoint handler (in api/routers/*.py)
    │
    ├── Acquire connection from pool
    ├── Execute SQL query
    ├── Release connection back to pool
    │
    ▼
_rows() → JSON response + X-Request-ID header
```

If an unhandled exception occurs, the global exception handler catches it, logs the traceback with the `request_id`, and returns a 500 response with the `request_id` for correlation.

---

## Lifespan Management

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    pool = await init_db_pool(DATABASE_URL)
    await verify_tables(pool)     # Check all required tables exist
    app.state.pool = pool
    # Mark orphaned pipeline runs (from prior crash/restart) as failed
    # Start background reaper to timeout stale runs (>15 min)
    reaper = asyncio.create_task(_reap_stale_runs(pool))
    yield
    # Shutdown
    reaper.cancel()
    await pool.close()
```

Schema changes are tracked via Alembic migrations (`alembic upgrade head`). See [`migrations.md`](migrations.md).

The DB pool is available as `request.app.state.pool` in every endpoint.

A background reaper task runs every 60 seconds to mark pipeline runs stuck in `queued` or `running` for longer than 15 minutes (configurable via `PIPELINE_TIMEOUT_MINUTES`) as `failed`. This catches cases where the pipeline service crashes without sending a callback.
