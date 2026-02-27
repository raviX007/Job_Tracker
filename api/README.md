# Job Tracker API

Async FastAPI backend for the Job Application Agent. Provides a REST API over PostgreSQL (Neon) for storing jobs, analyses, applications, email queues, and startup profiles. Used by both the [pipeline](../pipeline/) and the [dashboard](../ui-next/).

---

## Architecture

| Project | Role |
|---------|------|
| [pipeline/](../pipeline/) | Pipeline microservice + scraping, analysis, email generation |
| **api/** (this directory) | FastAPI backend, PostgreSQL database |
| [ui-next/](../ui-next/) | Next.js dashboard |

```
Pipeline ──writes──→ API ←──reads── Dashboard
                      │
                   PostgreSQL
                    (Neon)
```

> **Detailed documentation:** [`docs/`](docs/README.md) — endpoints, database schema, migrations, auth, email sending, deployment

---

## Setup

### Prerequisites

| Requirement | Version | Notes |
|------------|---------|-------|
| Python | 3.12+ | |
| PostgreSQL | Any | Neon free tier recommended ([neon.tech](https://neon.tech/)) |

### Installation

```bash
# 1. Enter project
cd api

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env template and fill in
cp .env.example .env
# Edit .env — set DATABASE_URL and optionally API_SECRET_KEY

# 4. Start the server
uvicorn api.server:app --reload --port 8000

# 5. (First time) Initialize Alembic migration tracking
alembic stamp head
```

API docs available at: **http://localhost:8000/docs**

Schema is defined in `db/schema.sql`. Migrations are managed via Alembic (raw SQL mode). See [`docs/migrations.md`](docs/migrations.md).

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (e.g. `postgresql://user:pass@host/db?sslmode=require`) |
| `API_SECRET_KEY` | No | API key for authentication. If empty, all requests are allowed (local dev) |
| `JWT_SECRET` | No | Secret key for JWT token signing. Required for user login/register |
| `JWT_EXPIRY_HOURS` | No | JWT token lifetime in hours (default: `24`) |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins (default: `http://localhost:8501`) |
| `GMAIL_ADDRESS` | No | Sender email for cold emails |
| `GMAIL_APP_PASSWORD` | No | Gmail App Password for SMTP |
| `EMAIL_SENDING_ENABLED` | No | `true` to enable email sending |
| `RESUME_PATH` | No | Path to resume PDF to attach to emails |
| `TEST_RECIPIENT_OVERRIDE` | No | Redirect all emails to this address (testing) |
| `PIPELINE_SERVICE_URL` | No | Pipeline microservice URL (default: `http://localhost:8002`) |
| `LOG_FORMAT` | No | Console log format: `console` (colored, default) or `json` (structured) |
| `LOG_LEVEL` | No | Log level (default: `INFO`) |
| `SENTRY_DSN` | No | Sentry DSN for error monitoring. Empty = disabled (local logs only) |
| `SENTRY_ENVIRONMENT` | No | Sentry environment tag (default: `development`) |
| `SENTRY_TRACES_SAMPLE_RATE` | No | Sentry performance tracing rate (default: `0` = off) |

---

## API Endpoints

47+ endpoints organized by function. See [`docs/endpoints.md`](docs/endpoints.md) for full details with request/response shapes.

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check (no auth required) |

### User Authentication (public — no API key required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Create a new user account, returns JWT |
| `POST` | `/api/auth/login` | Authenticate with username + password, returns JWT |

### Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/overview/stats` | Dashboard KPI stats (total jobs, scores, trends) |

### Applications

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/applications` | List applications with filters (source, decision, score range) |
| `GET` | `/api/applications/sources` | Distinct source values for filter dropdowns |
| `GET` | `/api/applications/for-update` | Applications needing outcome updates |
| `GET` | `/api/applications/analyzed-for-update` | Analyzed jobs available for outcome tracking |
| `POST` | `/api/applications` | Create a new application |
| `POST` | `/api/applications/upsert` | Create or update application (idempotent) |
| `PUT` | `/api/applications/{app_id}/outcome` | Update application outcome (interview, rejection, offer, etc.) |

### Emails

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/emails/queue` | Email queue with status filter |
| `GET` | `/api/emails/{email_id}` | Get a single email by ID |
| `GET` | `/api/emails/statuses` | Email count by status |
| `GET` | `/api/emails/sources` | Distinct sources with emails |
| `PUT` | `/api/emails/{email_id}/content` | Update email subject/body |
| `POST` | `/api/emails/{email_id}/send` | Send email via Gmail SMTP with resume |
| `DELETE` | `/api/emails/{email_id}` | Delete a single email |
| `DELETE` | `/api/emails` | Bulk delete emails for a profile |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/analytics/daily-trends` | Jobs scraped and analyzed per day |
| `GET` | `/api/analytics/score-distribution` | Match score histogram |
| `GET` | `/api/analytics/source-breakdown` | Jobs per source |
| `GET` | `/api/analytics/company-types` | Breakdown by company type |
| `GET` | `/api/analytics/response-rates` | Response rates by method |
| `GET` | `/api/analytics/route-breakdown` | Route action distribution |

### Tracker

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/tracker` | Spreadsheet view of all actionable jobs |

### Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| `PUT` | `/api/jobs/{job_id}/obsolete` | Toggle job obsolete status |
| `GET` | `/api/jobs/{job_id}/check-link` | Verify if a job URL is still active |

### Startup Profiles

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/startup-profiles` | List startup profiles with filters |
| `GET` | `/api/startup-profiles/stats` | Summary statistics |
| `GET` | `/api/startup-profiles/sources` | Distinct sources |
| `POST` | `/api/startup-profiles` | Save/upsert startup profile |

### Pipeline (used by job-tracker-pipeline)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/profiles/ensure` | Create or get profile by name |
| `POST` | `/api/jobs` | Save a scraped job |
| `POST` | `/api/analyses` | Save LLM analysis for a job |
| `PUT` | `/api/analyses/cover-letter` | Update cover letter for an analysis |
| `POST` | `/api/emails/enqueue` | Add email to queue |
| `PUT` | `/api/emails/{email_id}/verify` | Update email verification status |
| `PUT` | `/api/emails/{email_id}/advance` | Advance email to next status |
| `POST` | `/api/jobs/dedup-check` | Bulk duplicate check |
| `POST` | `/api/pipeline/main/run` | Trigger main pipeline run (dispatches to pipeline service) |
| `POST` | `/api/pipeline/startup-scout/run` | Trigger startup scout pipeline run |
| `PATCH` | `/api/pipeline/runs/{run_id}/callback` | Callback for pipeline service status updates |
| `GET` | `/api/pipeline/runs` | List recent pipeline runs |
| `GET` | `/api/pipeline/runs/{run_id}` | Poll pipeline run status |

---

## Authentication

Two auth layers:

### 1. User Auth (JWT) — Dashboard login

Users register/login via `/api/auth/register` and `/api/auth/login`. Passwords are hashed with **bcrypt** and stored in the `users` table. On success, the API returns a **JWT token** (HS256, 24h expiry).

```bash
# Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "john", "password": "securepass1"}'
# → {"token": "eyJhbG...", "username": "john"}

# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "john", "password": "securepass1"}'
# → {"token": "eyJhbG...", "username": "john"}
```

The dashboard stores the JWT in `localStorage` and sends it as `Authorization: Bearer <token>` on all requests.

**Env vars:**
```bash
JWT_SECRET=your-64-char-random-secret    # Required
JWT_EXPIRY_HOURS=24                       # Default: 24
```

### 2. API Key — Service-to-service auth

All endpoints except `/api/health` and `/api/auth/*` require an `X-API-Key` header:

```bash
curl -H "X-API-Key: your-secret-key" http://localhost:8000/api/overview/stats?profile_id=1
```

Set the same key in `api/.env`, `pipeline/.env`, and `ui-next/.env.local` as `API_SECRET_KEY`. If `API_SECRET_KEY` is not set, authentication is disabled (for local development). See [`docs/authentication.md`](docs/authentication.md) for details.

---

## Database Schema

7 tables in PostgreSQL (Neon):

| Table | Purpose |
|-------|---------|
| `profiles` | User profiles (one per candidate) |
| `jobs` | All scraped jobs (shared, deduped) |
| `job_analyses` | Per-user per-job LLM analysis results |
| `applications` | Actions taken (applied, emailed, alerted) |
| `email_queue` | Composed emails with status lifecycle |
| `startup_profiles` | Enriched startup metadata (funding, founders, tech stack) |
| `system_flags` | Runtime state (kill switch, platform pauses) |

Schema file: `db/schema.sql` — See [`docs/database.md`](docs/database.md) for full column-level docs.

Schema changes are tracked via Alembic (raw SQL mode). See [`docs/migrations.md`](docs/migrations.md).

---

## Docker

```bash
# Build
docker build -t job-tracker-api .

# Run (using .env file)
docker run -d --name job-tracker-api --env-file .env -p 8000:8000 job-tracker-api

# Verify
curl http://localhost:8000/api/health
# → {"status": "ok", "db": true, "version": "1.0.0", "uptime_seconds": 42, "pool": {"size": 2, ...}}
```

API docs: **http://localhost:8000/docs**

---

## Deployment

### Render (Free Tier)

A `render.yaml` blueprint is included for one-click deployment:

```bash
# Deploy via Render Dashboard
# 1. Connect your GitHub repo
# 2. Render auto-detects render.yaml
# 3. Set DATABASE_URL and ALLOWED_ORIGINS in Render environment
```

Start command: `uvicorn api.server:app --host 0.0.0.0 --port $PORT`
Health check: `/api/health`

See [`docs/deployment.md`](docs/deployment.md) for full deployment guide.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI |
| Server | Uvicorn (ASGI) |
| Database | PostgreSQL (Neon free tier) |
| DB Driver | asyncpg (async connection pooling) |
| Validation | Pydantic v2 |
| Rate Limiting | slowapi (per-IP, 60 req/min default) |
| Email | aiosmtplib (Gmail SMTP) |
| HTTP Client | httpx (for link checks, pipeline dispatch) |
| Migrations | Alembic (raw SQL mode) |
| Logging | Structured JSON + colored console (`LOG_FORMAT` env var) |
| Linting | Ruff + pre-commit hooks |
| Testing | pytest (111 tests — unit + integration) |

---

## Documentation

| Document | Description |
|----------|-------------|
| [`docs/architecture.md`](docs/architecture.md) | System design, async patterns, connection pooling |
| [`docs/endpoints.md`](docs/endpoints.md) | All 47+ endpoints with params and response shapes |
| [`docs/database.md`](docs/database.md) | Full schema — 7 tables, all columns, indexes |
| [`docs/migrations.md`](docs/migrations.md) | How to add tables, columns, indexes safely |
| [`docs/models.md`](docs/models.md) | All Pydantic request models |
| [`docs/authentication.md`](docs/authentication.md) | JWT user auth, API key auth, and CORS |
| [`docs/email-sending.md`](docs/email-sending.md) | Gmail SMTP, resume attachment, test mode |
| [`docs/deployment.md`](docs/deployment.md) | Render, Neon, local dev, Docker |
| [`docs/logging.md`](docs/logging.md) | Structured logging, LOG_FORMAT, Datadog extensibility |
| [`docs/pre-commit.md`](docs/pre-commit.md) | Pre-commit hooks — ruff + eslint |
| [`docs/integration-tests.md`](docs/integration-tests.md) | Multi-endpoint flow tests |

---

## Project Structure

```
api/
├── api/
│   ├── server.py           # FastAPI app setup, middleware, lifespan, router registration
│   ├── models.py           # Pydantic request/response models
│   ├── deps.py             # Shared dependencies (API key auth)
│   ├── helpers.py           # Shared helpers (_rows, _ParamBuilder, _parse_date_or_none)
│   └── routers/            # Modular endpoint groups
│       ├── health.py       # GET /api/health (public, no auth)
│       ├── auth.py         # POST /api/auth/register, /api/auth/login (public, JWT)
│       ├── overview.py     # Dashboard KPI stats
│       ├── applications.py # Application CRUD + filters
│       ├── emails.py       # Email queue + SMTP sending
│       ├── analytics.py    # Charts and trend data
│       ├── tracker.py      # Spreadsheet-style tracker view
│       ├── jobs.py         # Obsolete toggle, link check
│       ├── pipeline.py     # Pipeline dispatch, callback, polling
│       └── startup_profiles.py # Startup metadata CRUD
├── core/
│   ├── auth.py             # JWT token creation/verification, bcrypt password hashing
│   ├── database.py         # asyncpg pool management + table verification
│   └── logger.py           # Structured logging (JSON + console, LOG_FORMAT)
├── db/
│   └── schema.sql          # PostgreSQL schema (8 tables, 19 indexes)
├── alembic/                # Database migrations (raw SQL mode)
│   ├── env.py              # Migration environment (reads DATABASE_URL)
│   └── versions/           # Migration scripts
├── tests/                  # 111 tests (pytest + pytest-cov)
│   ├── conftest.py         # Shared fixtures with mocked DB pool
│   ├── test_*.py           # 14 unit test files
│   └── integration/        # Multi-endpoint flow tests
├── docs/                   # Detailed documentation (12 files)
├── alembic.ini             # Alembic configuration
├── Dockerfile              # Docker container (non-root user)
├── render.yaml             # Render deployment blueprint
├── requirements.txt        # Production dependencies (version ranges)
├── requirements.lock       # Fully pinned lockfile (generated by pip-compile)
├── requirements-dev.txt    # Dev/test dependencies (pytest, ruff, pre-commit)
└── .env.example            # Environment variable template
```
