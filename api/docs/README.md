# Job Tracker API — Documentation

Comprehensive documentation for the FastAPI backend — endpoints, database schema, migrations, authentication, email sending, and deployment.

---

## Table of Contents

| Document | Description |
|----------|-------------|
| [architecture.md](architecture.md) | System architecture, modular routers, rate limiting, error handling, async patterns |
| [endpoints.md](endpoints.md) | All 47+ API endpoints — method, path, params, request/response shapes |
| [database.md](database.md) | Full schema — 7 tables, all columns, types, constraints, indexes |
| [migrations.md](migrations.md) | How schema migrations work, adding tables/columns, safe practices |
| [models.md](models.md) | All Pydantic request models with field types and defaults |
| [authentication.md](authentication.md) | API key auth, CORS, rate limiting, security headers, request ID correlation |
| [email-sending.md](email-sending.md) | Gmail SMTP integration, resume attachment, test mode, status lifecycle |
| [deployment.md](deployment.md) | Render deployment, environment variables, health checks, Neon PostgreSQL |
| [logging.md](logging.md) | Structured logging, LOG_FORMAT, Datadog extensibility |
| [linting.md](linting.md) | What linting and formatting are, why they matter, our tools (Ruff, ESLint, Prettier) |
| [pre-commit.md](pre-commit.md) | Pre-commit hooks setup — ruff (Python) + eslint + prettier (Next.js) |
| [integration-tests.md](integration-tests.md) | Multi-endpoint flow tests — pipeline lifecycle, job-to-email |

---

## Quick Reference

### Start the server locally

```bash
cp .env.example .env   # Fill in DATABASE_URL, API_SECRET_KEY
pip install -r requirements.txt
uvicorn api.server:app --host 0.0.0.0 --port 8000
```

### Health check

```bash
curl http://localhost:8000/api/health
# → {"status": "ok", "db": true, "version": "1.0.0", "uptime_seconds": 42, "pool": {"size": 2, ...}}
```

### Authenticated request

```bash
curl -H "X-API-Key: your-key" "http://localhost:8000/api/overview/stats?profile_id=1"
```

---

## Endpoint Groups at a Glance

| Group | Count | Base Path | Purpose |
|-------|-------|-----------|---------|
| System | 1 | `/api/health` | Health check |
| Overview | 1 | `/api/overview/` | Dashboard KPIs |
| Applications | 7 | `/api/applications/` | Browse, create, update applications |
| Emails | 7 | `/api/emails/` | Queue management, get, edit, delete |
| Email Sending | 1 | `/api/emails/{id}/send` | Gmail SMTP dispatch |
| Analytics | 6 | `/api/analytics/` | Trends, distributions, breakdowns |
| Tracker | 1 | `/api/tracker` | Spreadsheet data |
| Jobs | 2 | `/api/jobs/` | Obsolete toggle, link check |
| Startup Profiles | 4 | `/api/startup-profiles/` | Startup metadata CRUD |
| Pipeline Ingestion | 7 | `/api/profiles/`, `/api/jobs`, `/api/analyses/`, `/api/emails/` | Pipeline writes |
| Pipeline Run | 5 | `/api/pipeline/` | Run, callback, poll pipeline runs |
| Dedup | 1 | `/api/jobs/dedup-check` | Bulk duplicate check |
