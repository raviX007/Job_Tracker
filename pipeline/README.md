# Job Tracker Pipeline

Scrapes jobs from 20+ sources, scores them with a two-stage filter (embedding + LLM), generates personalized cover letters and cold emails, and saves everything via the [Job Tracker API](../api/). Includes a separate startup scout pipeline for early-stage founder outreach.

> **New here?** Start with the [Walkthrough](docs/walkthrough.md) — it traces one job through the entire system step by step.

---

## Why I Built This

I'm a Python developer with a career gap, applying for jobs in India. Manually searching Naukri, Indeed, LinkedIn, and 5+ other platforms was taking **2 hours per day** for ~10 applications. Most got auto-rejected by ATS filters or were senior roles I wasn't qualified for.

I needed a system that could:
- Check all platforms simultaneously (not one tab at a time)
- Score fit *before* applying (stop wasting applications on bad matches)
- Send cold emails to hiring managers (bypass the ATS black hole)
- Track everything in one dashboard instead of a spreadsheet

**Result:** The pipeline now runs daily via GitHub Actions. In its first week of production, it scraped **179 jobs**, recommended **68** (40% hit rate), and queued **25 cold emails** — with a total LLM cost of **~$0.17**. I spend 10 minutes/day reviewing the dashboard instead of 2 hours searching.

See [Real-World Results](#real-world-results) for detailed metrics, or [Lessons Learned](docs/lessons-learned.md) for what I'd do differently.

---

## How It Works

### Main Pipeline (Formal Job Postings)

```
Scrape (20+ sources) → Dedup → Pre-filter → Embedding (MiniLM) → LLM Analysis (GPT-4o-mini) → Save via API
```

**Example run:** 132 scraped → 90 after dedup → 36 after pre-filter → 17 after embedding → 11 YES, 1 MAYBE, 2 MANUAL, 3 NO

### Startup Scout Pipeline (Early-Stage Startups)

```
Scrape (HN / YC / PH) → Dedup → LLM Relevance + Profile Extraction → Save → Find Emails → Cold Email → Queue
```

Targets early-stage startups with no formal JDs. Extracts founder info, funding, tech stack, and generates peer-to-peer cold emails.

---

## Architecture

This is one of three standalone projects split from the original monorepo:

| Project | Port | Role |
|---------|------|------|
| **pipeline/** (this directory) | `8002` | Pipeline microservice + standalone scripts |
| [api/](../api/) | `8000` | FastAPI backend, PostgreSQL database |
| [ui-next/](../ui-next/) | `3000` | Next.js dashboard |

The pipeline writes to the database exclusively through the API — no direct DB connection.

**Two execution modes:**
- **Microservice (port 8002):** The API dispatches pipeline runs to this service via HTTP. The service reports status back via callbacks. Used when triggered from the UI.
- **Standalone scripts:** `dry_run.py` and `startup_scout.py` run directly from the command line or GitHub Actions. No pipeline server needed.

---

## Setup

### Prerequisites

| Requirement | Version | Notes |
|------------|---------|-------|
| Python | 3.12+ | Required for `X \| Y` union types |
| OpenAI API | GPT-4o-mini | ~$0.001 per job analysis |
| Job Tracker API | Running | Pipeline saves results via API |

### Installation

```bash
# 1. Enter project
cd pipeline

# 2. Create and activate a virtual environment
python3.12 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt   # or requirements.lock for pinned versions

# 4. (Apple Silicon only) Install latest PyTorch
#    Intel Macs get PyTorch 2.2.2 automatically — that's the latest available.
#    Apple Silicon can optionally upgrade:
pip install torch --index-url https://download.pytorch.org/whl/cpu

# 5. Copy env template and fill in your keys
cp .env.example .env
# Edit .env — at minimum set API_BASE_URL, API_SECRET_KEY, and OPENAI_API_KEY

# 6. Validate your profile config (copy example and fill in your details)
cp config/profiles/example_profile.yaml config/profiles/my_profile.yaml
python -c "from core.config_loader import load_and_validate_profile; load_and_validate_profile('config/profiles/my_profile.yaml')"

# 7. Dry run — full pipeline, no side effects
python scripts/dry_run.py --source sample --limit 5
```

> **Intel Mac note (A2141 and older):** PyTorch dropped x86_64 macOS builds after 2.2.2.
> The pinned `transformers<4.48` in `requirements.txt` ensures compatibility.

### Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|----------|----------|-------------|
| `API_BASE_URL` | Yes | FastAPI backend URL (e.g. `http://localhost:8000`) |
| `API_SECRET_KEY` | Yes | Must match the API server's key |
| `OPENAI_API_KEY` | Yes | GPT-4o-mini for analysis + generation |
| `JOOBLE_API_KEY` | No | Jooble aggregator API |
| `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` | No | Adzuna aggregator API |
| `RAPIDAPI_KEY` | No | RapidAPI for JSearch (500 req/month free) |
| `FINDWORK_TOKEN` | No | FindWork.dev API (50 req/month free) |
| `APOLLO_API_KEY` | No | Apollo.io email finder (100 credits/month) |
| `SNOV_USER_ID` + `SNOV_API_SECRET` | No | Snov.io email finder (50 credits/month) |
| `HUNTER_API_KEY` | No | Hunter.io email finder + verification (25 credits/month) |
| `LANGFUSE_PUBLIC_KEY` | Yes | Langfuse prompt management (prompts are fetched from Langfuse) |
| `LANGFUSE_SECRET_KEY` | Yes | Langfuse prompt management |
| `LANGFUSE_HOST` | No | Defaults to `https://cloud.langfuse.com` |
| `LOG_FORMAT` | No | Console log format: `console` (colored, default) or `json` (structured) |
| `LOG_LEVEL` | No | Log level (default: `INFO`) |
| `SENTRY_DSN` | No | Sentry DSN for error monitoring. Empty = disabled (local logs only) |
| `SENTRY_ENVIRONMENT` | No | Sentry environment tag (default: `development`) |
| `SENTRY_TRACES_SAMPLE_RATE` | No | Sentry performance tracing rate (default: `0` = off) |
| `PROFILE_ID` | No | DB profile ID — if set, loads config from API instead of YAML |
| `PROFILE_PATH` | No | Path to YAML profile (fallback when `PROFILE_ID` is unset) |
| `DRY_RUN` | No | `true` (default) — no emails sent, no applications submitted |

---

## Usage

### Pipeline Server (for UI-triggered runs)

When the dashboard triggers a pipeline run, the API dispatches it to this microservice:

```bash
# Start the pipeline server
uvicorn server:app --reload --port 8002
```

The server exposes:
- `GET /health` — health check with active run count
- `POST /run` — accepts `{run_id, pipeline, source, limit}`, returns 202

The server captures stdout from pipeline stages and periodically flushes output to the API via callback, so the UI can display live progress logs.

### Dry Run (Recommended Start)

```bash
# Sample data (no network needed, fastest)
python scripts/dry_run.py --source sample --limit 5

# Live scraping from a single source
python scripts/dry_run.py --source remotive --limit 10
python scripts/dry_run.py --source jooble --limit 10

# Live scraping from a group
python scripts/dry_run.py --source remote_boards --limit 10
python scripts/dry_run.py --source aggregators --limit 10

# Full pipeline — all scrapers
python scripts/dry_run.py --source all --limit 20
```

### Startup Scout

```bash
# Scrape Hacker News "Who's Hiring" threads
python scripts/startup_scout.py --source hn_hiring --limit 20

# Scrape Y Combinator directory (recent batches)
python scripts/startup_scout.py --source yc_directory --limit 20

# Scrape ProductHunt recent launches
python scripts/startup_scout.py --source producthunt --limit 20

# All startup sources
python scripts/startup_scout.py --source startup_scout --limit 30
```

### Scraper Sources

| Group | Scrapers | Auth Required |
|-------|----------|---------------|
| `aggregators` | jooble, adzuna, remoteok, hiringcafe | Jooble + Adzuna keys |
| `remote_boards` | remotive, jobicy, himalayas, arbeitnow | None (free APIs) |
| `api_boards` | jsearch, careerjet, themuse, findwork | RapidAPI / Findwork keys |
| `ats_direct` | greenhouse, lever | None (public APIs) |
| `startup_scout` | hn_hiring, yc_directory, producthunt | None (public APIs) |
| `jobspy` | indeed, naukri, linkedin, glassdoor | None |

### Langfuse Prompt Management

Prompts are managed in [Langfuse](https://cloud.langfuse.com) with versioning and A/B testing. All prompts are stored in Langfuse — no hardcoded prompts in the codebase. Langfuse keys are required.

```bash
# Push/update prompts to Langfuse (one-time setup or when updating prompts)
python scripts/push_prompts.py
```

Three managed prompts: `job-analysis`, `cold-email`, `cover-letter`.

### GitHub Actions

Two workflow files in `.github/workflows/`:

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| **Pipeline CI** | `pipeline-ci.yml` | Push / PR to `main` | Lint (ruff) + tests — skipped if no `pipeline/` files changed |
| **Pipeline Run** | `pipeline.yml` | Daily cron + manual dispatch | Runs the actual pipelines (main at 3 AM UTC, startup scout at 5 AM UTC) |

- **Manual trigger:** Workflow dispatch with `pipeline`, `source`, and `limit` inputs
- Requires GitHub Secrets for API keys

---

## Pipeline Steps

### Main Pipeline

| Step | Component | Cost |
|------|-----------|------|
| 1. Scrape | 20+ sources via `scraper/` | Free |
| 2. Dedup | URL + content hash | Free |
| 3. Pre-filter | Title, skills, freshness | Free |
| 4. Route | URL → action mapping | Free |
| 5. Embedding | all-MiniLM-L6-v2 (local) | Free |
| 6. LLM Analysis | GPT-4o-mini | ~$0.001/job |
| 7. Save | Results saved via API | Free |

### Startup Scout Pipeline

| Step | Component | Cost |
|------|-----------|------|
| 1. Scrape | HN / YC / ProductHunt | Free |
| 2. Dedup | URL + content hash | Free |
| 3. LLM Analysis | Relevance + profile extraction (one call) | ~$0.001/startup |
| 4. Save | Job + analysis + startup profile via API | Free |
| 5. Find Emails | 5-strategy email discovery chain | Free / credits |
| 6. Cold Email | Startup-specific peer-to-peer email | ~$0.0005/email |
| 7. Queue | Save to email_queue via API | Free |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12, asyncio |
| Server | FastAPI + uvicorn (pipeline microservice) |
| LLM | OpenAI GPT-4o-mini |
| Embedding | all-MiniLM-L6-v2 (local, free) |
| Prompt Management | Langfuse (versioned prompts + tracing) |
| HTTP | httpx (async) |
| Scraping | 20+ API/aggregator scrapers + python-jobspy |
| Config | DB-backed (JSONB) via Settings UI + YAML fallback, Pydantic validation (100+ fields) |

---

## Project Structure

```
pipeline/
├── server.py                    # Pipeline microservice (port 8002)
├── config/
│   ├── profiles/               # YAML user profiles (fallback)
│   │   └── example_profile.yaml
│   └── settings.py             # Env var loading (pydantic-settings)
├── core/
│   ├── constants.py            # Centralized thresholds, limits, timeouts
│   ├── config_loader.py        # YAML → Pydantic validation
│   ├── models.py               # All Pydantic models (100+ fields)
│   ├── llm.py                  # OpenAI LLM client (Langfuse traced)
│   ├── langfuse_client.py      # Prompt fetching + tracing
│   ├── api_client.py           # FastAPI backend client (httpx)
│   ├── pipeline.py             # Main pipeline orchestration
│   ├── startup_utils.py        # Startup profile builder (shared)
│   └── logger.py               # Structured logging (JSON + console)
├── scraper/
│   ├── registry.py             # @scraper decorator + auto-discovery
│   ├── source_router.py        # URL → action routing
│   ├── dedup.py                # URL + content dedup
│   ├── utils.py                # Shared scraper utilities
│   ├── aggregator_scraper.py   # Jooble, Adzuna, RemoteOK, HiringCafe
│   ├── remote_boards.py        # Remotive, Jobicy, Himalayas, Arbeitnow
│   ├── api_boards.py           # JSearch, CareerJet, TheMuse, FindWork
│   ├── ats_direct.py           # Greenhouse, Lever (career pages)
│   ├── startup_scouts.py       # HN Hiring, YC Directory, ProductHunt
│   └── jobspy_scraper.py       # Indeed, Naukri, LinkedIn, Glassdoor
├── analyzer/
│   ├── embedding_filter.py     # Stage 1: MiniLM similarity
│   ├── llm_analyzer.py         # Stage 2: GPT-4o-mini analysis
│   ├── freshness_filter.py     # Pre-filter checks
│   ├── jd_preprocessor.py      # JD cleaning for embedding
│   └── ats_keywords.py         # ATS keyword matching
├── emailer/
│   ├── email_finder.py         # 5-strategy email discovery
│   ├── verifier.py             # 4-layer email verification
│   ├── cover_letter.py         # LLM cover letter generation
│   ├── cold_email.py           # LLM cold email generation
│   ├── validator.py            # Anti-hallucination checks
│   └── sender.py               # Gmail SMTP sending
├── scripts/
│   ├── dry_run.py              # Full pipeline test
│   ├── startup_scout.py        # Startup scout pipeline
│   ├── _startup_analyzer.py    # Startup LLM analysis + email generation
│   └── push_prompts.py         # Push prompts to Langfuse
├── tests/                      # 348 tests, 16 test files
│   ├── test_normalizers.py     # All 16 scraper normalizer functions (81 tests)
│   ├── test_api_client.py      # API client: HTTP, retry, all endpoints (46)
│   ├── test_scraper_utils.py   # Shared utilities: HTML, dates, salary, skills (41)
│   ├── test_pipeline.py        # Pipeline orchestration: stages, stats, early exits (28)
│   ├── test_email_finder.py    # Email discovery + patterns (24)
│   ├── test_source_router.py   # URL → action classification (21)
│   ├── test_verifier.py        # Email syntax/MX/disposable (19)
│   ├── test_sender.py          # Warmup + safety gates (19)
│   ├── test_dedup.py           # URL normalization + dedup keys (18)
│   ├── test_validator.py       # Anti-hallucination checks (16)
│   ├── test_registry.py        # Scraper registry + run_scraper error handling (13)
│   ├── test_config_validation.py  # Profile field constraints (9)
│   ├── test_llm.py             # LLM client init, guards, singleton (7)
│   ├── test_config_loader.py   # YAML loading + validation edge cases (5)
│   ├── test_embedding_filter.py # Embedding filter (1)
│   └── fixtures/
│       ├── sample_jds.json     # 10 sample job postings
│       └── sample_profile.yaml # Test profile
├── docs/                       # Documentation (16 files)
└── .github/workflows/
    ├── pipeline-ci.yml         # CI: lint + test on push/PR
    └── pipeline.yml            # Daily GitHub Actions run
```

---

## Testing

```bash
python -m pytest tests/ -v
```

348 tests covering:

| Test File | What | Tests |
|-----------|------|-------|
| `test_normalizers.py` | All 16 scraper normalizers + HN parser + batch converter | 81 |
| `test_api_client.py` | API client: init, context manager, retry, all 12 endpoints, module-level functions | 46 |
| `test_scraper_utils.py` | strip_html, date/salary parsing, skill set, relevance | 41 |
| `test_pipeline.py` | JobPipeline + StartupScoutPipeline: scrape, dedup, prefilter, run, early exits | 28 |
| `test_email_finder.py` | Domain extraction, company guessing, pattern guessing, orchestrator | 24 |
| `test_source_router.py` | Domain extraction, URL→platform classification, job routing | 21 |
| `test_verifier.py` | Email syntax, disposable domains, full pipeline | 19 |
| `test_sender.py` | Warmup schedule, safety gates, counter resets, scraper utils | 19 |
| `test_dedup.py` | URL normalization, tracking param stripping, dedup keys | 18 |
| `test_validator.py` | Anti-hallucination checks (degree, company, experience, skills) | 16 |
| `test_registry.py` | Decorator registration, group lookup, run_scraper error handling | 13 |
| `test_config_validation.py` | Profile YAML validation, field constraints, cross-field validators | 9 |
| `test_llm.py` | LLM client init, call guards, model defaults, singleton | 7 |
| `test_config_loader.py` | YAML loading, missing/invalid/empty file handling | 5 |
| `test_embedding_filter.py` | Embedding filter (placeholder) | 1 |

All tests are pure unit tests — no real API calls, no network access, no LLM costs.

---

## Safety

- **DRY_RUN mode** (default: `true`) — scrapes and analyzes but never sends emails or submits applications
- **Anti-hallucination** — validates all LLM content against the candidate profile
- **Rate limits** — warmup schedule for cold emails (5/day → 15/day over 4 weeks)
- **Dedup** — URL + content hash prevents duplicate processing

See [Safety & Guards](docs/safety.md) for details.

---

## Real-World Results

Data from production runs (Feb 2026):

### Pipeline Funnel

```
Scraped:     179 jobs (20+ sources: Indeed, Adzuna, HiringCafe, Remotive, Greenhouse, ...)
Dedup:       172 unique (7 duplicates removed)
Analyzed:    172 by GPT-4o-mini
  → 68 YES (40% hit rate)
  → 27 MAYBE
  → 77 NO
Emails:      25 cold emails queued, 17 verified, 2 sent
Startups:    4 from HN Hiring, 85% avg match score, 2 founder emails queued
```

### Cost Breakdown

| Component | Monthly Cost |
|-----------|-------------|
| OpenAI GPT-4o-mini (~80 jobs analyzed/day) | ~$2.50 |
| Neon PostgreSQL (free tier) | $0 |
| Render API hosting (free tier) | $0 |
| Langfuse (free tier) | $0 |
| **Total** | **~$2.50/month** |

### Time Saved

| Task | Before (Manual) | After (Automated) |
|------|-----------------|-------------------|
| Search all platforms | ~90 min/day | 0 (runs on cron) |
| Review & shortlist | ~30 min/day | ~10 min/day (dashboard) |
| Write cold emails | ~15 min each | 0 (LLM-generated, human-reviewed) |
| **Total daily effort** | **~2 hours** | **~10 minutes** |

See [Lessons Learned](docs/lessons-learned.md) for what worked, what didn't, and what I'd change.

---

## Dashboard Screenshots

The Streamlit dashboard provides real-time visibility into the pipeline.

| Page | What It Shows |
|------|--------------|
| **Overview** | Today's activity, all-time stats (179 jobs, 68 recommended, 50% avg score), top matches, 7-day trend |
| **Applications** | Browse all 172 analyzed jobs with score/decision/source filters, expandable details |
| **Cold Emails** | 25 emails queued, verification status, subject lines, expandable body preview |
| **Analytics** | Score distribution pie chart, source platform breakdown, daily activity trends |
| **Startup Scout** | 4 startups found, founder info, funding round, tech stack, email status |
| **Pipeline Runner** | One-click pipeline execution with source selector and job limits |

See [Demo & Screenshots](docs/demo.md) for full screenshots of every page.

---

## Documentation

| Doc | Description |
|-----|-------------|
| [Walkthrough](docs/walkthrough.md) | **Start here** — follow one job through the entire system step by step |
| [Demo & Screenshots](docs/demo.md) | Dashboard screenshots from a real production run |
| [Design Decisions](docs/design-decisions.md) | Why two-stage filtering, 20+ scrapers, Langfuse, async, and more |
| [Lessons Learned](docs/lessons-learned.md) | What worked, what didn't, what I'd change, scalability |
| [LLM Stack Rationale](docs/llm-stack-rationale.md) | Why not LangChain / LangGraph — direct SDK + Langfuse |
| [Architecture](docs/architecture.md) | System overview, component interaction, tech stack |
| [Pipeline Flow](docs/pipeline.md) | End-to-end flow, scoring rules, example run |
| [Concepts & Glossary](docs/concepts.md) | Plain English explanations of every technical term |
| [Setup & Installation](docs/setup.md) | Prerequisites, env vars, profile config |
| [Scrapers](docs/scrapers.md) | All 20+ scrapers, dedup, source routing |
| [Analysis Pipeline](docs/analysis.md) | Embedding filter, LLM analyzer, startup analyzer |
| [Email Pipeline](docs/email-pipeline.md) | Email finder, verifier, generator, queue |
| [Database](docs/database.md) | Schema, tables, indexes |
| [Safety & Guards](docs/safety.md) | DRY_RUN, rate limits, anti-hallucination |
| [Aggregator Research](docs/aggregator-research.md) | 22 platforms ranked for integration |
| [Dashboard](docs/dashboard.md) | Streamlit UI — 8 pages, API-based data layer |
| [Prompt Engineering](docs/prompt-engineering.md) | LLM prompt design patterns |
| [Langfuse](docs/langfuse.md) | Prompt versioning + LLM tracing |
| [ML Stack](docs/ml-stack.md) | Embeddings, PyTorch, transformers, sentence-transformers |
| [Telegram & Scheduler](docs/telegram-and-scheduler.md) | Bot commands, alerts, cron jobs |
