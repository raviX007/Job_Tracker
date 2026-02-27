# Scrapers

All job data enters the system through scrapers. There are six groups registered via the `@scraper` decorator in `scraper/registry.py`:

1. **Aggregators** — Free API-based job aggregators (Jooble, Adzuna, RemoteOK, HiringCafe)
2. **Remote Boards** — Remote-only job boards (Remotive, Jobicy, Himalayas, Arbeitnow)
3. **API Boards** — Key-based API boards (JSearch, CareerJet, TheMuse, FindWork)
4. **ATS Direct** — Direct ATS career pages (Greenhouse, Lever) for dream companies
5. **Startup Scouts** — Early-stage startup sources (HN Hiring, YC Directory, ProductHunt)
6. **JobSpy** — Library-based scraper (Indeed, Naukri, LinkedIn, Glassdoor)

---

## Scraper Architecture

All scrapers are auto-discovered via the `@scraper(name, group)` decorator. Adding a new scraper requires no changes to the pipeline — just decorate the function and it's included.

```
Pipeline → Registry → asyncio.gather(all groups) → Normalize → Dedup → Output
```

### Scraper Registry (`scraper/registry.py`)

| Function | Purpose |
|----------|---------|
| `@scraper(name, group, needs_key)` | Decorator to register a scraper |
| `get_scraper(name)` | Get a single scraper by name |
| `get_group(group)` | Get all scrapers in a group |
| `run_scraper(name, profile, limit)` | Run a single scraper |
| `run_group(group, profile, limit)` | Run all scrapers in a group concurrently |
| `run_all(profile, limit)` | Run all groups concurrently |

---

## Platform Comparison

### Aggregators (`scraper/aggregator_scraper.py`)

| Platform | Method | API Key | Rate Limit | Typical Yield | Best For |
|----------|--------|---------|-----------|---------------|----------|
| RemoteOK | GET API | None | Unlimited | 5-15 relevant | Remote-only jobs |
| Jooble | POST API | Required | 500 req/day | 20-40 per search | Multi-source aggregation |
| Adzuna | GET API | Required | Generous | 10-20 per search | India country search |
| HiringCafe | GET API | None | Unlimited | 50-80 relevant | Structured data, career pages |

### Remote Boards (`scraper/remote_boards.py`)

| Platform | Method | API Key | Rate Limit | Typical Yield | Best For |
|----------|--------|---------|-----------|---------------|----------|
| Remotive | GET API | None | Unlimited | 5-15 relevant | Remote dev/data/devops |
| Jobicy | GET API | None | Unlimited | 5-10 relevant | Remote with skill tags |
| Himalayas | GET API | None | Unlimited | 5-10 relevant | Remote with seniority filter |
| Arbeitnow | GET API | None | Unlimited | 3-8 relevant | European/German remote |

### API Boards (`scraper/api_boards.py`)

| Platform | Method | API Key | Rate Limit | Typical Yield | Best For |
|----------|--------|---------|-----------|---------------|----------|
| JSearch | GET API | RapidAPI key | 500 req/month | 10-30 relevant | Google for Jobs wrapper |
| CareerJet | GET API | Affiliate ID | Generous | 10-20 relevant | India locale search |
| TheMuse | GET API | Optional | Generous | 5-15 relevant | Entry-level focus |
| FindWork | GET API | Token | 50 req/month | 5-10 relevant | Developer jobs (handles 429) |

### ATS Direct (`scraper/ats_direct.py`)

| Platform | Method | API Key | Board Tokens | Typical Yield | Best For |
|----------|--------|---------|-------------|---------------|----------|
| Greenhouse | GET API | None | Per-company board tokens | 5-20 per company | Dream company career pages |
| Lever | GET API | None | Per-company slugs | 5-15 per company | Dream company career pages |

### Startup Scouts (`scraper/startup_scouts.py`)

| Platform | Method | API Key | Rate Limit | Typical Yield | Best For |
|----------|--------|---------|-----------|---------------|----------|
| HN Hiring | Algolia API | None | Generous | 20-50 per thread | Monthly "Who's Hiring" posts |
| YC Directory | Web scrape | None | Gentle | 10-30 per batch | Recent YC batches (1.5 yr) |
| ProductHunt | GraphQL API | None | Generous | 10-20 recent | Launched products with makers |

### JobSpy (`scraper/jobspy_scraper.py`)

| Platform | Method | API Key | Rate Limit | Typical Yield | Best For |
|----------|--------|---------|-----------|---------------|----------|
| Indeed | JobSpy library | None | ~100/call | 50-100 jobs | India + remote roles |
| Naukri | JobSpy library | None | ~50/call | 30-60 jobs | India-specific |
| Glassdoor | JobSpy library | None | ~50/call | 20-40 jobs | Company reviews + jobs |
| LinkedIn | JobSpy library | None | ~50/call | 30-80 jobs | Read-only, no apply |

---

## Aggregator Scrapers

**File:** `scraper/aggregator_scraper.py`

Four API-based scrapers that run concurrently via `asyncio.gather()`.

### RemoteOK

- **Endpoint:** `GET https://remoteok.com/api`
- **Auth:** None (public API)
- **Response:** JSON array (skip first metadata item)
- **Filtering:** Client-side — checks if job tags overlap with profile skills
- **Best for:** Remote-only dev jobs worldwide

### Jooble

- **Endpoint:** `POST https://jooble.org/api/{api_key}`
- **Auth:** API key (free, 1-3 day approval wait)
- **Request body:** `{ "keywords": "...", "location": "..." }`
- **Rate limit:** 500 requests/day
- **Best for:** Aggregation from 70+ sources

### Adzuna

- **Endpoint:** `GET https://api.adzuna.com/v1/api/jobs/{country}/search/{page}`
- **Auth:** App ID + App Key
- **Parameters:** `what`, `where`, `max_days_old`
- **Country:** `in` (India)
- **Best for:** India-focused searches with seniority filtering

### HiringCafe

- **Endpoint:** `GET https://hiring.cafe/api/search-jobs`
- **Auth:** None (public API)
- **Query:** `searchState` (URL-encoded JSON with filters)
- **Unique features:** Returns structured data including `technical_tools`, `seniority_level`, `min_industry_and_role_yoe`, `job_category`

**HiringCafe filtering:**

| Filter | Logic |
|--------|-------|
| Seniority | Only `entry_level`, `mid_level`, or empty |
| YOE | `min_industry_and_role_yoe` <= 4 (or null) |
| Job category | Whitelist: software development, IT, data, engineering, R&D, product |
| Tool match | `technical_tools` must overlap with profile skills |
| Title match | Only specific tech terms (python, react, django) — excludes generic "engineer"/"developer" |

---

## Remote Board Scrapers

**File:** `scraper/remote_boards.py`

Four remote-only job boards, all free JSON APIs.

### Remotive

- **Endpoint:** `GET https://remotive.com/api/remote-jobs`
- **Categories:** software-dev, data, devops
- **Filtering:** Skill relevance check against profile

### Jobicy

- **Endpoint:** `GET https://jobicy.com/api/v2/remote-jobs`
- **Parameters:** `tag` (python, django, react, etc.)
- **Filtering:** Skill overlap with profile skills

### Himalayas

- **Endpoint:** `GET https://himalayas.app/jobs/api`
- **Filtering:** Seniority filter, skill relevance check

### Arbeitnow

- **Endpoint:** `GET https://www.arbeitnow.com/api/job-board-api`
- **Notes:** European/German focus, Unix timestamps for dates
- **Filtering:** Skill relevance check

---

## API Board Scrapers

**File:** `scraper/api_boards.py`

Four key-based API boards. Require API keys for full access.

### JSearch (RapidAPI)

- **Endpoint:** `GET https://jsearch.p.rapidapi.com/search` via RapidAPI
- **Auth:** RapidAPI key
- **Free tier:** 500 requests/month
- **Notes:** Google for Jobs wrapper, broad coverage

### CareerJet

- **Endpoint:** `GET https://public.api.careerjet.net/search`
- **Auth:** Affiliate ID (env var `CAREERJET_AFFILIATE_ID`)
- **Locale:** `en_IN` (India)

### TheMuse

- **Endpoint:** `GET https://www.themuse.com/api/public/jobs`
- **Auth:** API key (optional)
- **Focus:** Entry-level positions

### FindWork

- **Endpoint:** `GET https://findwork.dev/api/jobs/`
- **Auth:** Bearer token
- **Free tier:** 50 requests/month
- **Notes:** Handles 429 rate limit responses gracefully

---

## ATS Direct Scrapers

**File:** `scraper/ats_direct.py`

Scrape career pages of dream companies directly via public ATS APIs.

### Greenhouse

- **Endpoint:** `GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs`
- **Auth:** None (public board API)
- **Setup:** Board tokens per company (hardcoded defaults with config override)
- **Filtering:** Skill relevance against profile skills

### Lever

- **Endpoint:** `GET https://api.lever.co/v0/postings/{slug}`
- **Auth:** None (public postings API)
- **Setup:** Company slugs (hardcoded defaults with config override)
- **Filtering:** Skill relevance against profile skills

---

## Startup Scouts

**File:** `scraper/startup_scouts.py`

Target early-stage startups (<18 months, <10 people) with no formal JDs. Used by the startup scout pipeline (`scripts/startup_scout.py`), not the main pipeline.

### HN Hiring

- **Source:** Hacker News monthly "Who's Hiring" threads
- **API:** Algolia HN Search API (no auth)
- **Logic:** Finds latest "Who is Hiring" thread, parses top-level comments for company|location|role format
- **Metadata:** `hn_thread_date`, comment text as description

### YC Directory

- **Source:** Y Combinator company directory
- **API:** Web scrape (Next.js data extraction or HTML fallback)
- **Filters:** Recent batches only (within 1.5 years), team size 1-10
- **Metadata:** `yc_batch`, `yc_url`, `team_size`, `one_liner`, `long_description`, `yc_tags`
- **Batch-to-date:** W25 → 2025-01-15, S24 → 2024-06-15

### ProductHunt

- **Source:** ProductHunt recent launches
- **API:** GraphQL (no auth)
- **Fields:** Posts with name, tagline, description, makers, topics, votesCount
- **Metadata:** `ph_url`, `ph_launch_date`, `ph_votes_count`, `ph_maker_data`, `topics`

---

## JobSpy Scraper

**File:** `scraper/jobspy_scraper.py`

Wraps the `python-jobspy` library which scrapes job portals using HTTP.

### Configuration

Search terms and platforms are driven by the YAML profile:

| Config Field | Used For |
|-------------|----------|
| `skills.primary` | Search terms (e.g., "Python developer", "React developer") |
| `search_preferences.locations` | Location filter |
| `platforms.indeed.enabled` | Enable/disable per platform |
| `matching.max_job_age_days` | Maps to `hours_old` parameter |

### Notes

- Runs sync library in thread pool to avoid blocking the async event loop
- Handles NaN values from DataFrame conversion
- Defers to platform enable flags in profile config

---

## Normalized Job Format

Every scraper outputs this standard dict:

```python
{
    "title": "Software Developer",
    "company": "Acme Corp",
    "location": "Bengaluru, India",
    "source": "indeed",          # Platform that hosts the job
    "discovered_via": "jobspy",  # How we found it
    "description": "Full JD text...",
    "job_url": "https://indeed.com/...",
    "date_posted": "2025-01-15",
    "is_remote": False,
    "salary_min": None,
    "salary_max": None,
    "salary_currency": None,
}
```

Startup scouts add additional fields: `yc_batch`, `yc_url`, `ph_url`, `ph_votes_count`, `ph_maker_data`, `hn_thread_date`, `topics`.

---

## Shared Utilities (`scraper/utils.py`)

| Function | Purpose |
|----------|---------|
| `strip_html(text)` | Remove HTML tags, unescape entities, collapse whitespace |
| `parse_date_iso(date_str)` | Parse ISO 8601 dates (with Z suffix handling) |
| `parse_date_timestamp(ts)` | Unix timestamp → date string |
| `parse_salary_range(salary_str)` | "$60,000 - $80,000" → (60000, 80000) |
| `build_skill_set(profile)` | Combine primary + secondary + generic terms |
| `check_relevance(title, desc, skills)` | Does job mention any candidate skill? |
| `is_short_description(desc)` | Too short to be useful? (< 50 chars) |

---

## Dedup

**File:** `scraper/dedup.py`

Prevents processing the same job twice, even across different scrapers.

### Dedup Strategy

1. **Primary key:** SHA256 hash of normalized URL (stripped of tracking params)
2. **Fallback key:** SHA256 hash of `company|title|location` (catches same job on different sites)
3. **In-batch check:** `seen_keys` set prevents duplicates within a single scrape run

### Stripped URL Parameters

| Category | Parameters |
|----------|-----------|
| UTM tracking | `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content` |
| Click tracking | `fbclid`, `gclid`, `msclkid` |
| Referral | `ref`, `referer`, `referrer` |
| Internal | `from`, `si`, `trackingId` |

---

## Source Router

**File:** `scraper/source_router.py`

Classifies each job by its URL domain and determines the recommended action.

### Domain Classification

| Category | Domains | Action |
|----------|---------|--------|
| Auto-Apply | naukri.com, indeed.com, foundit.com | `auto_apply_and_cold_email` |
| Manual Only | linkedin.com, wellfound.com, internshala.com, instahyre.com | `manual_alert` only |
| ATS Platforms | greenhouse.io, lever.co, workday.com, ashbyhq.com, smartrecruiters.com | `cold_email_only` (find HR) |
| Scrape Only | glassdoor.com, remoteok.com, jooble.org, adzuna.com | View only, find original |
| Unknown | Any other domain | `cold_email_only` (likely career page) |

### Route Action Output

```python
{
    "platform": "greenhouse",
    "action": "cold_email_only",
    "auto_apply": False,
    "cold_email": True,
    "manual_alert": False,
    "needs_redirect_resolution": False,
}
```
