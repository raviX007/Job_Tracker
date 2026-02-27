# Database Schema

PostgreSQL database with 8 tables. Schema lives in `db/schema.sql`. Schema changes are tracked via Alembic migrations (raw SQL mode) — see [`migrations.md`](migrations.md).

---

## Entity Relationship

```
profiles ──1:N──→ job_analyses
    │                  │
    │              job_id ←── jobs ──1:1──→ startup_profiles
    │                  │
    ├──1:N──→ applications
    │
    └──1:N──→ email_queue

system_flags (standalone key-value store)
```

---

## Table: `profiles`

One row per user/candidate. Links all per-user data.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `name` | VARCHAR(255) | NOT NULL | Candidate name |
| `email` | VARCHAR(255) | | Candidate email |
| `config_path` | TEXT | NOT NULL | Path to YAML profile config |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Created timestamp |

---

## Table: `jobs`

All scraped jobs. Shared across profiles. Deduplicated by `dedup_key` and `job_url`.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `job_url` | TEXT | UNIQUE | Original job posting URL |
| `aggregator_url` | TEXT | | URL from aggregator (e.g., Jooble link) |
| `source` | VARCHAR(50) | | Platform: naukri, remotive, greenhouse, hn_hiring, etc. |
| `discovered_via` | VARCHAR(50) | | How found: jooble, adzuna, direct_scrape, etc. |
| `title` | VARCHAR(255) | | Job title |
| `company` | VARCHAR(255) | | Company name |
| `location` | VARCHAR(255) | | Location string |
| `is_remote` | BOOLEAN | DEFAULT FALSE | Remote job flag |
| `remote_type` | VARCHAR(30) | | full_remote, hybrid, onsite, remote_country, remote_global |
| `description` | TEXT | | Full job description |
| `salary_min` | INTEGER | | Minimum salary |
| `salary_max` | INTEGER | | Maximum salary |
| `salary_currency` | VARCHAR(10) | | USD, INR, EUR, etc. |
| `date_posted` | DATE | | When the job was posted |
| `date_scraped` | TIMESTAMP | DEFAULT NOW() | When we scraped it |
| `url_verified` | BOOLEAN | DEFAULT TRUE | Whether URL was checked alive |
| `dedup_key` | TEXT | UNIQUE | Composite dedup hash (company+title+location) |
| `is_obsolete` | BOOLEAN | DEFAULT FALSE | Marked as dead/expired |
| `obsolete_at` | TIMESTAMP | | When marked obsolete |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Created timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last updated |

**Indexes:**
- `idx_jobs_company_title` — `(company, title)` for search
- `idx_jobs_source` — `(source)` for filtering
- `idx_jobs_discovered_via` — `(discovered_via)` for analytics
- `idx_jobs_dedup_key` — `(dedup_key)` for fast dedup lookups
- `idx_jobs_date_scraped` — `(date_scraped)` for trend queries

---

## Table: `job_analyses`

Per-user LLM analysis. The same job can be scored differently for different profiles.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `job_id` | INTEGER | FK → jobs(id) CASCADE | Which job |
| `profile_id` | INTEGER | FK → profiles(id) CASCADE | Which user |
| `match_score` | INTEGER | | 0-100 relevance score |
| `embedding_score` | FLOAT | | MiniLM cosine similarity |
| `skills_required` | TEXT[] | | Skills the job requires |
| `skills_matched` | TEXT[] | | Skills user has |
| `skills_missing` | TEXT[] | | Skills user lacks |
| `ats_keywords` | TEXT[] | | ATS-optimized keywords |
| `experience_required` | VARCHAR(50) | | "2-4 years", "entry", etc. |
| `location_compatible` | BOOLEAN | | User can work from this location |
| `remote_compatible` | BOOLEAN | | Remote work aligns |
| `company_type` | VARCHAR(30) | | startup, mnc, service, agency, mid_size |
| `gap_tolerant` | BOOLEAN | | Company likely tolerates career gaps |
| `red_flags` | TEXT[] | | Warning signs |
| `apply_decision` | VARCHAR(20) | | YES, NO, MAYBE, MANUAL |
| `route_action` | VARCHAR(40) | | auto_apply_and_cold_email, cold_email_only, manual_alert |
| `cold_email_angle` | TEXT | | Suggested cold email approach |
| `gap_framing_for_this_role` | TEXT | | How to frame career gaps |
| `cover_letter` | TEXT | | Generated cover letter |
| `analyzed_at` | TIMESTAMP | DEFAULT NOW() | When analyzed |

**Constraints:** `UNIQUE(job_id, profile_id)` — one analysis per job per user.

**Indexes:**
- `idx_analyses_profile` — `(profile_id)` for user queries
- `idx_analyses_score` — `(match_score)` for sorting
- `idx_analyses_job_profile` — `(job_id, profile_id)` for lookups

---

## Table: `applications`

Tracks what happened after analysis — did the user apply? What was the response?

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `job_id` | INTEGER | FK → jobs(id) CASCADE | Which job |
| `profile_id` | INTEGER | FK → profiles(id) CASCADE | Which user |
| `method` | VARCHAR(30) | | auto_apply, cold_email, manual_apply, referral, quick_apply |
| `platform` | VARCHAR(50) | | LinkedIn, Naukri, email, etc. |
| `applied_at` | TIMESTAMP | DEFAULT NOW() | When applied |
| `cold_email_sent` | BOOLEAN | DEFAULT FALSE | Was cold email sent |
| `cold_email_to` | VARCHAR(255) | | Recipient email |
| `cold_email_subject` | TEXT | | Email subject |
| `response_received` | BOOLEAN | DEFAULT FALSE | Got any response |
| `response_type` | VARCHAR(30) | | interview, rejection, offer, ghosted |
| `response_date` | TIMESTAMP | | When response received |
| `followup_sent` | BOOLEAN | DEFAULT FALSE | Follow-up email sent |
| `followup_at` | TIMESTAMP | | When follow-up sent |
| `notes` | TEXT | | User notes |

**Constraints:** `UNIQUE(job_id, profile_id, method)` — one application per method per job per user.

**Indexes:**
- `idx_applications_profile` — `(profile_id)`
- `idx_applications_method` — `(method)` for analytics
- `idx_applications_applied_at` — `(applied_at)` for trends

---

## Table: `email_queue`

Cold emails with full lifecycle tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `job_id` | INTEGER | FK → jobs(id) CASCADE | Which job |
| `profile_id` | INTEGER | FK → profiles(id) CASCADE | Which user |
| `recipient_email` | VARCHAR(255) | NOT NULL | Target email address |
| `recipient_name` | VARCHAR(255) | | Contact name |
| `recipient_role` | VARCHAR(255) | | HR, CTO, Engineering Manager, etc. |
| `recipient_source` | VARCHAR(50) | | How found: apollo, hunter, pattern_guess |
| `subject` | TEXT | NOT NULL | Email subject line |
| `body_html` | TEXT | NOT NULL | HTML body |
| `body_plain` | TEXT | NOT NULL | Plain text body |
| `signature` | TEXT | | Email signature |
| `resume_attached` | BOOLEAN | DEFAULT TRUE | Attach resume PDF |
| `email_verified` | BOOLEAN | DEFAULT FALSE | Recipient email verified |
| `email_verification_result` | VARCHAR(30) | | valid, invalid, risky, catch_all, unknown |
| `email_verification_provider` | VARCHAR(30) | | hunter, apollo, smtp_check |
| `verified_at` | TIMESTAMP | | When verified |
| `status` | VARCHAR(30) | DEFAULT 'draft' | Lifecycle status |
| `queued_at` | TIMESTAMP | | When moved to queue |
| `sent_at` | TIMESTAMP | | When actually sent |
| `send_attempt_count` | INTEGER | DEFAULT 0 | Send retry count |
| `last_error` | TEXT | | Last send error message |
| `follow_up_eligible` | BOOLEAN | DEFAULT TRUE | Can send follow-up |
| `follow_up_sent` | BOOLEAN | DEFAULT FALSE | Follow-up sent |
| `follow_up_at` | TIMESTAMP | | When follow-up sent |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Created timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last updated |

**Status lifecycle:** `draft → verified → ready → queued → sent → delivered / bounced / failed`

**Indexes:**
- `idx_email_queue_status` — `(status)` for queue processing
- `idx_email_queue_profile` — `(profile_id)` for user queries
- `idx_email_queue_job` — `(job_id)` for job-email lookup

---

## Table: `startup_profiles`

Enriched metadata for startups found via the startup scout pipeline.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | SERIAL | PRIMARY KEY | Auto-increment ID |
| `job_id` | INTEGER | UNIQUE, FK → jobs(id) CASCADE | Links to parent job record |
| `startup_name` | VARCHAR(255) | | Company/startup name |
| `website_url` | TEXT | | Company website |
| `yc_url` | TEXT | | Y Combinator profile URL |
| `ph_url` | TEXT | | ProductHunt profile URL |
| `founding_date` | DATE | | When founded |
| `founding_date_source` | VARCHAR(30) | | yc_batch, ph_launch, llm_inferred |
| `age_months` | INTEGER | | Computed from founding_date |
| `founder_names` | TEXT[] | | Array of founder names |
| `founder_emails` | TEXT[] | | Array of founder emails |
| `founder_roles` | TEXT[] | | Parallel array: CEO, CTO, etc. |
| `employee_count` | INTEGER | | Team size |
| `employee_count_source` | VARCHAR(30) | | yc_directory, llm_inferred |
| `one_liner` | TEXT | | Short product description |
| `product_description` | TEXT | | Detailed description |
| `tech_stack` | TEXT[] | | Technologies used |
| `topics` | TEXT[] | | Industry/domain tags |
| `has_customers` | BOOLEAN | | Evidence of customers |
| `has_customers_evidence` | TEXT | | Supporting text |
| `funding_amount` | VARCHAR(100) | | "$500K", "$2M", etc. |
| `funding_round` | VARCHAR(30) | | pre_seed, seed, series_a, bootstrapped, unknown |
| `funding_date` | DATE | | When funded |
| `funding_source` | VARCHAR(30) | | yc_batch, llm_inferred |
| `source` | VARCHAR(30) | | hn_hiring, yc_directory, producthunt |
| `yc_batch` | VARCHAR(10) | | W25, S24, etc. |
| `ph_launch_date` | DATE | | ProductHunt launch date |
| `ph_votes_count` | INTEGER | | ProductHunt upvotes |
| `ph_maker_info` | TEXT | | Maker data from PH |
| `hn_thread_date` | DATE | | HN "Who's Hiring" thread date |
| `llm_extracted` | BOOLEAN | DEFAULT FALSE | Whether LLM extracted data |
| `llm_extraction_raw` | JSONB | | Full LLM response for debugging |
| `data_completeness` | INTEGER | | 0-100 score based on filled fields |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Created timestamp |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last updated |

**Indexes:**
- `idx_startup_profiles_job_id` — `(job_id)` for joins
- `idx_startup_profiles_source` — `(source)` for filtering
- `idx_startup_profiles_founding_date` — `(founding_date)` for age queries
- `idx_startup_profiles_funding_round` — `(funding_round)` for filtering

---

## Table: `system_flags`

Runtime configuration key-value store.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `key` | VARCHAR(100) | PRIMARY KEY | Flag name |
| `value` | TEXT | NOT NULL | Flag value |
| `updated_at` | TIMESTAMP | DEFAULT NOW() | Last updated |

**Default flags (seeded on creation):**
| Key | Default | Purpose |
|-----|---------|---------|
| `active` | `true` | Master kill switch |
| `naukri` | `true` | Enable Naukri scraping |
| `indeed` | `true` | Enable Indeed scraping |
| `foundit` | `true` | Enable Foundit scraping |
| `cold_email` | `true` | Enable cold email generation |
| `scraping` | `true` | Enable all scraping |
