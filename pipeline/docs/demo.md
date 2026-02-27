# Demo & Screenshots

Real screenshots from a production run. The pipeline scraped 179 jobs across 20+ sources, analyzed 172, and recommended 68 (40% hit rate).

---

## Dashboard Overview

The main dashboard shows today's activity, all-time pipeline stats, and recent top matches.

![Dashboard Overview](screenshots/dashboard-overview.png)

**Key metrics from this run:**
- **179** total jobs scraped from 20+ sources
- **172** passed to LLM analysis (7 filtered by embedding)
- **68** recommended (YES decision) — 40% hit rate
- **25** cold emails queued
- **50%** average match score across all analyzed jobs

The "Recent Top Matches" section shows the highest-scoring jobs with their match scores, matched skills, and source platform.

![Dashboard Top Matches](screenshots/dashboard-top-matches.png)

The 7-day activity trend shows scraping volume and email generation over the week. The spike on Feb 17 corresponds to enabling additional aggregator sources.

---

## Applications Browser

Browse and filter all analyzed jobs with score ranges, decision filters, source platform, and text search.

![Applications Page](screenshots/applications.png)

Each card shows:
- **Match score** (green badge, 0-100)
- **Decision** (YES / MAYBE / MANUAL / NO)
- **Company type** (startup / enterprise)
- **Tags**: Gap Tolerant, Route action, Embedding score
- **Expandable details** with full JD, matched/missing skills, and LLM reasoning

Filters on the left sidebar: Profile ID, Score Range, Decision type, Source Platform, and free-text search by company or title.

---

## Cold Email Queue

Review composed cold emails, verification status, and email content before sending.

![Cold Email Queue](screenshots/cold-emails.png)

**Queue stats from this run:**
- **25** total emails composed
- **17** email addresses verified (68% verification rate)
- **23** ready to send
- **2** already sent

Each email card shows:
- **Status badge** (READY / SENT / FAILED)
- **Subject line** — LLM-generated, personalized to the role
- **Recipient** with verification status
- **Source** — how the email address was found (pattern_guess, snov, apollo)
- **Expandable content** with full email body preview

---

## Analytics

Performance insights with score distribution, source platform breakdown, and daily trends.

![Analytics Page](screenshots/analytics.png)

**Score Distribution** (pie chart):
- 22.1% scored 80-100 (High) — strong matches
- 42.4% scored 60-79 (Good) — worth applying
- 15.7% scored 40-59 (Maybe) — manual review
- 19.8% scored 0-39 (Low) — filtered out

**Source Platform Breakdown** (bar chart): Shows job yield per platform. Indeed and Adzuna lead in volume, while Greenhouse and HiringCafe lead in quality (higher % of recommended jobs).

---

## Startup Scout

Discover early-stage startups from HN Hiring, YC Directory, and ProductHunt.

![Startup Scout Page](screenshots/startup-scout.png)

**Startup metrics from this run:**
- **4** startups discovered (HN Hiring source)
- **85%** average match score (startups are pre-filtered for relevance)
- **2** founder emails queued
- **63%** average profile completeness

Each startup card shows:
- **Match score** + **source badge** (hn_hiring, yc_directory, producthunt)
- **Funding round** (bootstrapped, seed, series A)
- **Email status** (ready, pending)
- **Tech stack** extracted by LLM
- **Founders** with roles
- **Expandable details** with full startup profile

---

## Pipeline Runner

Run pipelines directly from the dashboard with source selection and job limits.

![Pipeline Runner Page](screenshots/pipeline-runner.png)

Two pipelines available:
- **Main Pipeline**: Scrape → Dedup → Pre-filter → Embed → LLM Analyze → Save to DB
- **Startup Scout Pipeline**: Scrape → Dedup → LLM Relevance → Founder Emails → Cold Email

Each pipeline has:
- **Source selector** (All Scrapers, specific group, or individual scraper)
- **Limit control** (jobs per scraper)
- **One-click run** button
- **Pipeline Steps** reference table
- **Source Groups** with scraper details and auth requirements
