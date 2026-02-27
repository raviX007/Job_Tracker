# Logging

Structured logging for the API and pipeline services, controlled by environment variables.

---

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `LOG_FORMAT` | `console` | Console output format: `console` (colored text) or `json` (structured JSON) |
| `LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

Set `LOG_FORMAT=json` in production (Render) for structured log aggregation.

---

## Output Modes

### Console Mode (`LOG_FORMAT=console`)

Colored, human-readable output for local development:

```
10:42:15 [INFO    ] jobbot: Pool created (2 connections)
10:42:15 [INFO    ] jobbot: Tables verified
10:42:16 [INFO    ] jobbot.requests: GET /api/health → 200 (12ms) [a3f1b2c4]
```

Colors: DEBUG (cyan), INFO (green), WARNING (yellow), ERROR (red), CRITICAL (red background).

### JSON Mode (`LOG_FORMAT=json`)

Structured JSON output for production log aggregation:

```json
{
  "timestamp": "2026-02-23T10:42:16.123456+00:00",
  "level": "INFO",
  "service": "job-tracker-api",
  "logger": "jobbot.requests",
  "message": "GET /api/health → 200 (12ms) [a3f1b2c4]",
  "module": "server",
  "function": "dispatch",
  "line": 128,
  "dd.trace_id": "",
  "dd.span_id": ""
}
```

### File Handler

Regardless of `LOG_FORMAT`, a file handler always writes JSON to `logs/jobbot.log`. This ensures structured logs are always available for debugging even in console mode.

---

## Architecture

Both services share the same logging pattern:

| Service | File | `SERVICE_NAME` |
|---------|------|----------------|
| API | `api/core/logger.py` | `job-tracker-api` |
| Pipeline | `pipeline/core/logger.py` | `job-tracker-pipeline` |

### Components

**`JSONFormatter`** — Formats records as single-line JSON with:
- Standard fields: `timestamp`, `level`, `service`, `logger`, `message`, `module`, `function`, `line`
- Datadog APM placeholders: `dd.trace_id`, `dd.span_id`
- Exception info (when present)
- Extra fields: `job_id`, `company`, `platform`, `profile_id`, `action`, `request_id`

**`ConsoleFormatter`** — Colored `HH:MM:SS [LEVEL] logger: message` format.

**`setup_logger(name)`** — Creates a singleton logger with:
- Console handler (format depends on `LOG_FORMAT`)
- File handler (always JSON)
- Idempotent — safe to call multiple times

---

## Extra Fields

Pass context to log entries using the `extra` parameter:

```python
from core.logger import logger

logger.info("Job analyzed", extra={
    "job_id": 42,
    "company": "Acme Corp",
    "profile_id": 1,
    "action": "analyze",
})
```

Supported extra fields:

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | int | Job record ID |
| `company` | str | Company name |
| `platform` | str | Job source platform |
| `profile_id` | int | User profile ID |
| `action` | str | Action being performed |
| `request_id` | str | HTTP request correlation ID |

Extra fields only appear in JSON output (console mode ignores them).

---

## Request Logging

The API includes `RequestLoggingMiddleware` (`api/server.py`) that logs every HTTP request:

- Generates an 8-character `request_id` per request
- Logs method, path, status code, and duration in milliseconds
- Returns the `request_id` in the `X-Request-ID` response header

```
GET /api/overview/stats → 200 (45ms) [a3f1b2c4]
POST /api/pipeline/main/run → 202 (8ms) [e7d2c1a9]
```

---

## Datadog APM Integration

JSON logs include `dd.trace_id` and `dd.span_id` placeholders (empty strings by default). When `ddtrace` is installed and configured, these fields are automatically populated by the Datadog tracer, enabling log-trace correlation.

To enable:

```bash
pip install ddtrace
ddtrace-run uvicorn api.server:app --host 0.0.0.0 --port 8000
```

No code changes required — `ddtrace` patches the logging module automatically.

---

## Sentry Error Monitoring

Sentry provides real-time error alerting, stack traces, and error aggregation. It's **optional** — when `SENTRY_DSN` is not set, all errors fall back to local logs only.

### Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `SENTRY_DSN` | *(empty)* | Sentry project DSN. Empty = Sentry disabled, local logs only |
| `SENTRY_ENVIRONMENT` | `development` | Environment tag (`development`, `production`) |
| `SENTRY_TRACES_SAMPLE_RATE` | `0` | Performance tracing sample rate (`0` = off, `0.1`–`1.0` = on) |

### How It Works

- **`SENTRY_DSN` is set:** Sentry SDK initializes on server startup. Unhandled exceptions are sent to **both** Sentry and local logs. The FastAPI integration automatically adds request context (URL, headers, user agent) to error reports.
- **`SENTRY_DSN` is empty:** Sentry SDK is not initialized. All `sentry_sdk.capture_exception()` calls are safe no-ops. Behavior is identical to before Sentry was added.

### What Gets Captured

| Service | Error Type | Where |
|---------|-----------|-------|
| API | Unhandled exceptions (500s) | `server.py` global exception handler |
| Pipeline | Pipeline execution failures | `_execute_pipeline()` except block |
| Pipeline | Callback retry exhaustion | `_report_status()` after all retries fail |

### Production Setup (Render)

Add these environment variables in the Render dashboard:

```
SENTRY_DSN=https://<key>@<org>.ingest.sentry.io/<project>
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
```

Performance tracing (`SENTRY_TRACES_SAMPLE_RATE`) costs additional Sentry quota. Start with `0` (disabled) or `0.1` (10% of requests) and adjust based on needs.

---

## Key Log Events

| Event | Level | Logger | When |
|-------|-------|--------|------|
| Pool created | INFO | `jobbot` | Server startup |
| Tables verified | INFO | `jobbot` | Server startup |
| HTTP request | INFO | `jobbot.requests` | Every request |
| Email sent | INFO | `jobbot` | After SMTP success |
| Email failed | ERROR | `jobbot` | After SMTP failure |
| API key rejected | WARNING | `jobbot` | Invalid auth attempt |
| Rate limit exceeded | WARNING | `jobbot` | Client hits 60 req/min |
| Stale run reaped | WARNING | `jobbot.pipeline` | Pipeline run timed out |
| Unhandled exception | ERROR | `jobbot` | Unexpected server error |
