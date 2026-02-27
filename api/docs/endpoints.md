# API Endpoints

All endpoints are prefixed with `/api/`. Unless noted, all require the `X-API-Key` header.

All error responses include a `request_id` field for correlation: `{"detail": "...", "request_id": "abc12345"}`.

Rate limit: **60 requests/minute** per IP (returns `429` when exceeded).

---

## System

### `GET /api/health`

Health check. **No authentication required.**

**Response:**
```json
{
  "status": "ok",
  "db": true,
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "pool": {
    "size": 2,
    "free": 1,
    "used": 1,
    "min": 2,
    "max": 10
  }
}
```

| Field | Description |
|-------|-------------|
| `status` | `"ok"` if the server is running |
| `db` | `true` if database query succeeds, `false` otherwise |
| `version` | API version string |
| `uptime_seconds` | Seconds since server startup |
| `pool` | Connection pool stats: current `size`, `free` (idle), `used`, `min`/`max` limits |

Used by Render for uptime monitoring.

---

## Overview

### `GET /api/overview/stats`

Dashboard KPI summary.

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `profile_id` | int | Yes | User profile |

**Response:**
```json
{
    "today_jobs": 15,
    "today_analyzed": 12,
    "today_emails": 5,
    "today_applied": 2,
    "total_jobs": 450,
    "total_analyzed": 380,
    "total_yes": 95,
    "total_emails": 60,
    "jobs_with_emails": 55,
    "avg_score": 62,
    "week_jobs": 45
}
```

---

## Applications

### `GET /api/applications`

Browse analyzed jobs with filters.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `profile_id` | int | Required | User profile |
| `min_score` | int | 0 | Minimum match score |
| `max_score` | int | 100 | Maximum match score |
| `decision` | string | "All" | Filter: All, YES, NO, MAYBE, MANUAL |
| `source` | string | "All" | Filter by job source |
| `search` | string | "" | Search company name or title |
| `limit` | int | 200 | Max results |

**Response:** Array of objects with job + analysis fields:
```json
[{
    "job_id": 1,
    "title": "Backend Developer",
    "company": "Acme Inc",
    "location": "Remote",
    "source": "remotive",
    "is_remote": true,
    "job_url": "https://...",
    "match_score": 85,
    "apply_decision": "YES",
    "skills_matched": ["Python", "FastAPI"],
    "skills_missing": ["Go"],
    "route_action": "cold_email_only",
    "cold_email_angle": "...",
    "cover_letter": "...",
    ...
}]
```

### `GET /api/applications/sources`

Distinct job sources for filter dropdown.

| Param | Type | Required |
|-------|------|----------|
| `profile_id` | int | Yes |

**Response:** `["All", "remotive", "greenhouse", "hn_hiring", ...]`

### `GET /api/applications/for-update`

Applications that have been logged and may need outcome updates.

**Response:** Array with `app_id`, `job_id`, `method`, `applied_at`, `response_type`, `response_date`, `notes`, plus job metadata.

### `GET /api/applications/analyzed-for-update`

Analyzed jobs (YES/MAYBE/MANUAL) that don't have an application logged yet.

**Response:** Array with `job_id`, `title`, `company`, `match_score`, `apply_decision`, `route_action`.

### `POST /api/applications`

Log a new application.

**Body:**
```json
{
    "job_id": 1,
    "profile_id": 1,
    "method": "cold_email",
    "platform": "email"
}
```

Methods: `auto_apply`, `cold_email`, `manual_apply`, `telegram_alert`, `referral`, `quick_apply`

### `POST /api/applications/upsert`

Create or update an application. If `app_id` is provided, updates that record. Otherwise upserts by `(job_id, profile_id, method)`.

**Body:**
```json
{
    "job_id": 1,
    "profile_id": 1,
    "method": "manual",
    "platform": "LinkedIn",
    "response_type": "interview",
    "notes": "Phone screen scheduled",
    "app_id": null
}
```

### `PUT /api/applications/{app_id}/outcome`

Update application response.

**Body:**
```json
{
    "response_type": "interview",
    "response_date": "2026-02-15",
    "notes": "Technical round next week"
}
```

Response types: `interview`, `rejection`, `offer`, `ghosted`

---

## Email Queue

### `GET /api/emails/queue`

List queued emails with filters.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `profile_id` | int | Required | User profile |
| `status` | string | "All" | Filter by status |
| `source` | string | "All" | Filter by job source |

**Response:** Array of emails joined with job + analysis data (title, company, score, source, etc.).

### `GET /api/emails/statuses`

Email count by status.

**Response:**
```json
{
    "draft": 5,
    "verified": 3,
    "ready": 8,
    "sent": 12,
    "delivered": 10,
    "bounced": 1,
    "failed": 0
}
```

### `GET /api/emails/sources`

Distinct job sources that have emails.

**Response:** `["remotive", "greenhouse", ...]`

### `PUT /api/emails/{email_id}/content`

Edit email subject and body.

**Body:**
```json
{
    "subject": "Updated subject",
    "body_plain": "Updated body text"
}
```

### `GET /api/emails/{email_id}`

Get a single email by ID. Returns all fields from the email_queue table.

**Response:** Full email object including `id`, `job_id`, `profile_id`, `recipient_email`, `recipient_name`, `recipient_role`, `recipient_source`, `subject`, `body_html`, `body_plain`, `status`, `email_verified`, `email_verification_result`, `email_verification_provider`, `created_at`, etc.

**Error:** `404` if email not found.

### `DELETE /api/emails/{email_id}`

Delete a single email from the queue.

### `DELETE /api/emails`

Bulk delete all emails for a profile.

| Param | Type | Required |
|-------|------|----------|
| `profile_id` | int | Yes |

**Response:** `{"deleted": 15}`

---

## Email Sending

### `POST /api/emails/{email_id}/send`

Send an email via Gmail SMTP. See [email-sending.md](email-sending.md) for details.

**Response (success):**
```json
{ "status": "sent", "email_id": 1, "to": "founder@startup.com" }
```

**Response (failure):**
```json
{ "status": "failed", "email_id": 1, "error": "Connection refused" }
```

---

## Analytics

### `GET /api/analytics/daily-trends`

Daily activity counts.

| Param | Type | Default |
|-------|------|---------|
| `profile_id` | int | Required |
| `days` | int | 30 |

**Response:**
```json
[
    { "date": "2026-02-18", "jobs_scraped": 15, "jobs_analyzed": 12, "emails_queued": 5 },
    ...
]
```

### `GET /api/analytics/score-distribution`

Match score histogram.

**Response:**
```json
[
    { "bracket": "80-100 (High)", "count": 25 },
    { "bracket": "60-79 (Good)", "count": 40 },
    { "bracket": "40-59 (Maybe)", "count": 30 },
    { "bracket": "0-39 (Low)", "count": 15 }
]
```

### `GET /api/analytics/source-breakdown`

Jobs per source platform.

**Response:**
```json
[
    { "source": "remotive", "count": 50, "avg_score": 68, "yes_count": 15 },
    { "source": "greenhouse", "count": 30, "avg_score": 72, "yes_count": 12 },
    ...
]
```

### `GET /api/analytics/company-types`

Jobs by company type.

**Response:**
```json
[
    { "company_type": "startup", "count": 80, "avg_score": 70, "gap_tolerant_count": 45 },
    { "company_type": "mnc", "count": 40, "avg_score": 55, "gap_tolerant_count": 10 },
    ...
]
```

### `GET /api/analytics/response-rates`

Application outcomes by method.

**Response:**
```json
[
    { "method": "cold_email", "total": 20, "responded": 8, "interviews": 3, "rejections": 4, "offers": 1 },
    ...
]
```

### `GET /api/analytics/route-breakdown`

Route action distribution for YES/MAYBE/MANUAL jobs.

**Response:**
```json
{
    "auto_apply_and_cold_email": 15,
    "cold_email_only": 25,
    "manual_alert": 10
}
```

---

## Tracker

### `GET /api/tracker`

Spreadsheet-style view of all actionable jobs (YES/MAYBE/MANUAL).

| Param | Type | Required |
|-------|------|----------|
| `profile_id` | int | Yes |

**Response:** Array with job data + application status:
```json
[{
    "job_id": 1,
    "title": "Backend Dev",
    "company": "Acme",
    "match_score": 85,
    "apply_decision": "YES",
    "skills_matched": ["Python"],
    "skills_missing": ["Go"],
    "app_id": 5,
    "app_method": "cold_email",
    "app_platform": "email",
    "response_type": "interview",
    "app_notes": "...",
    "is_obsolete": false,
    ...
}]
```

---

## Jobs

### `PUT /api/jobs/{job_id}/obsolete`

Toggle a job's obsolete status (dead link / expired posting).

**Response:** `{"job_id": 1, "is_obsolete": true}`

### `GET /api/jobs/{job_id}/check-link`

HTTP HEAD request to verify the job URL is still live.

**Response (live):** `{"job_id": 1, "alive": true, "status_code": 200}`
**Response (dead):** `{"job_id": 1, "alive": false, "status_code": 404}`
**Response (error):** `{"job_id": 1, "alive": false, "error": "Connection timeout"}`

---

## Startup Profiles

### `GET /api/startup-profiles`

List startup profiles with filters. Joins with jobs, job_analyses, and email_queue.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `profile_id` | int | Required | User profile |
| `source` | string | "All" | hn_hiring, yc_directory, producthunt |
| `funding_round` | string | "All" | pre_seed, seed, series_a, bootstrapped, unknown |
| `min_age` | int | 0 | Minimum age in months |
| `max_age` | int | 24 | Maximum age in months |
| `has_funding` | string | "All" | All, Yes, No |
| `search` | string | "" | Search by startup name |
| `sort_by` | string | "match_score" | match_score, founding_date, data_completeness, age |
| `limit` | int | 200 | Max results |

**Response:** Array of startup profiles with analysis and email data.

### `GET /api/startup-profiles/stats`

Summary statistics.

**Response:**
```json
{
    "total": 50,
    "avg_score": 72,
    "with_emails": 30,
    "avg_completeness": 65,
    "by_source": { "hn_hiring": 20, "yc_directory": 15, "producthunt": 15 },
    "by_funding": { "pre_seed": 25, "seed": 10, "unknown": 15 }
}
```

### `GET /api/startup-profiles/sources`

Distinct source values.

**Response:** `["hn_hiring", "producthunt", "yc_directory"]`

### `POST /api/startup-profiles`

Save or update a startup profile (upserts by `job_id`).

**Body:** See [models.md](models.md#savestartupprofilerequest) for the full field list.

**Response:** `{"startup_profile_id": 1}`

---

## Pipeline Ingestion

These endpoints are called by the scraping pipeline (not the dashboard).

### `POST /api/profiles/ensure`

Get or create a user profile.

**Body:** `{"name": "...", "email": "...", "config_path": "..."}`
**Response:** `{"profile_id": 1}`

### `POST /api/jobs`

Save a scraped job. Returns `null` job_id if the dedup_key already exists.

**Body:** See [models.md](models.md#savejob) for fields.
**Response:** `{"job_id": 1}` or `{"job_id": null}`

### `POST /api/jobs/dedup-check`

Bulk check for existing URLs and dedup keys.

**Body:** `{"urls": ["..."], "dedup_keys": ["..."]}`
**Response:** `{"existing_keys": [...], "existing_urls": [...]}`

### `POST /api/analyses`

Save LLM analysis (upserts by `job_id + profile_id`).

**Body:** See [models.md](models.md#saveanalysis) for fields.
**Response:** `{"analysis_id": 1}`

### `PUT /api/analyses/cover-letter`

Update cover letter for an existing analysis.

**Body:** `{"job_id": 1, "profile_id": 1, "cover_letter": "..."}`

### `POST /api/emails/enqueue`

Queue a cold email.

**Body:** See [models.md](models.md#enqueueemail) for fields.
**Response:** `{"email_id": 1}`

### `PUT /api/emails/{email_id}/verify`

Mark email as verified.

**Body:** `{"verification_result": "valid", "verification_provider": "hunter"}`

### `PUT /api/emails/{email_id}/advance`

Advance email status to `ready`.

---

## Pipeline Orchestration

The API dispatches pipeline runs to the **Pipeline Service** (a separate FastAPI microservice on port 8002) via HTTP. The pipeline service reports status back via a callback endpoint.

### `POST /api/pipeline/main/run`

Start the main scraping pipeline. Dispatches to the pipeline microservice and returns immediately.

**Body:**
```json
{ "source": "remote_boards", "limit": 10 }
```

**Response (202):** `{"run_id": "abc-123", "status": "queued"}`

The UI polls `GET /api/pipeline/runs/{run_id}` to track progress.

### `POST /api/pipeline/startup-scout/run`

Start the startup scout pipeline. Same dispatch mechanism as above.

**Body:**
```json
{ "source": "hn_hiring", "limit": 20 }
```

**Response (202):** `{"run_id": "def-456", "status": "queued"}`

### `PATCH /api/pipeline/runs/{run_id}/callback`

Callback endpoint used by the pipeline service to report status updates. Not intended for direct use.

**Body:**
```json
{
  "status": "completed",
  "output": "[1/8] Scraping...\n[2/8] Dedup...",
  "duration_seconds": 45.2,
  "error": null,
  "started_at": true
}
```

All fields are optional — only non-null fields are applied. Sets `finished_at = NOW()` automatically when status is `completed` or `failed`.

### `GET /api/pipeline/runs`

List recent pipeline runs, newest first.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `pipeline` | string | null | Filter by type: `main` or `startup_scout` |
| `limit` | int | 20 | Max results (1-100) |

### `GET /api/pipeline/runs/{run_id}`

Poll a specific pipeline run by run_id. Used by the UI to track progress.

**Response:**
```json
{
  "run_id": "abc-123",
  "pipeline": "main",
  "status": "running",
  "source": "remote_boards",
  "limit": 10,
  "output": "[1/8] Scraping...",
  "duration_seconds": null,
  "error": null,
  "created_at": "2026-02-23T10:00:00Z",
  "started_at": "2026-02-23T10:00:01Z",
  "finished_at": null
}
```
