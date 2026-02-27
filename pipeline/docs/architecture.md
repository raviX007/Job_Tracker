# Architecture

High-level system design of the Job Tracker system — a three-project, four-service architecture with API-first communication.

---

## System Overview

```mermaid
graph TB
    subgraph Sources["Job Sources (20+ scrapers)"]
        direction LR
        AGG["Aggregators<br/>HiringCafe, RemoteOK,<br/>Jooble, Adzuna"]
        RB["Remote Boards<br/>Remotive, Jobicy,<br/>Himalayas, Arbeitnow"]
        API_B["API Boards<br/>JSearch, CareerJet,<br/>TheMuse, FindWork"]
        ATS["ATS Direct<br/>Greenhouse, Lever"]
        JS["JobSpy<br/>Indeed, Naukri,<br/>LinkedIn, Glassdoor"]
        SS["Startup Scouts<br/>HN Hiring, YC Directory,<br/>ProductHunt"]
    end

    subgraph Pipeline["Main Processing Pipeline"]
        DD[Dedup<br/>URL + content hash]
        PF[Pre-filter<br/>Title, skill, freshness]
        SR[Source Router<br/>URL → action mapping]
        EF[Embedding Filter<br/>all-MiniLM-L6-v2]
        LA[LLM Analyzer<br/>GPT-4o-mini]
    end

    subgraph StartupPipeline["Startup Scout Pipeline"]
        SA[LLM Relevance<br/>Analyzer]
        SP[Startup Profile<br/>Builder]
        SE[Founder Email<br/>Finder + Generator]
    end

    subgraph Actions["Output Actions"]
        DA[Direct Apply<br/>Portal submission]
        CE[Cold Email<br/>Compose + queue]
        MA[Manual Alert<br/>Telegram review]
    end

    subgraph API["FastAPI Backend (job-tracker-api)"]
        REST["REST API<br/>47+ endpoints"]
        DB[(PostgreSQL<br/>Neon)]
        SMTP["Gmail SMTP<br/>Email sending"]
    end

    subgraph UI["Next.js Dashboard (ui-next)"]
        SL["Dashboard<br/>Overview, Applications,<br/>Emails, Analytics,<br/>Tracker, Pipeline Runner,<br/>Startup Scout"]
    end

    subgraph Notify["Notifications"]
        TG[Telegram Bot<br/>3 channels]
    end

    AGG & RB & API_B & ATS & JS --> DD --> PF --> SR --> EF --> LA
    SS --> SA --> SP --> SE

    LA -->|YES| DA
    LA -->|YES| CE
    LA -->|MAYBE/MANUAL| MA
    LA -->|NO| X[Skip]

    SE --> CE

    DA --> REST
    CE --> REST
    REST --> DB
    REST --> SMTP

    REST --> SL
    MA --> TG
```

---

## Three-Project Architecture

The system is split into three independent projects:

| Project | Port | Purpose | Deployed On |
|---------|------|---------|-------------|
| **pipeline/** | `8002` | Pipeline microservice + standalone scripts | Local / GitHub Actions (scripts only) |
| **api/** | `8000` | FastAPI backend, database, email sending | Render (free tier) |
| **ui-next/** | `3000` | Next.js dashboard | Vercel / local |

### Communication Pattern

```mermaid
flowchart LR
    UI["ui-next<br/>(Next.js)"] -->|REST API| API["api<br/>(FastAPI + asyncpg)"]
    API -->|HTTP POST /run| PIPE["pipeline server<br/>(FastAPI, port 8002)"]
    PIPE -->|PATCH callback| API
    PIPE -->|REST API<br/>(save data)| API
    API -->|asyncpg| DB[(Neon PostgreSQL)]
    API -->|aiosmtplib| GMAIL["Gmail SMTP"]

    style API fill:#2563eb,color:#fff
    style PIPE fill:#059669,color:#fff
```

**Key design decisions:**
- Neither the pipeline nor the dashboard connect to the database directly. All data flows through the FastAPI backend via HTTP.
- The API dispatches pipeline runs to the pipeline microservice via HTTP, not subprocess. The pipeline reports status back via a callback endpoint.
- Pipeline scripts still work standalone (for GitHub Actions cron jobs) — no pipeline server needed.
- Dashboard deploys without DB access

---

## Component Interaction

```mermaid
sequenceDiagram
    participant S as Scheduler
    participant SC as Scrapers (6 groups)
    participant API as FastAPI Backend
    participant AN as Analyzer
    participant LLM as GPT-4o-mini
    participant EM as Email Pipeline
    participant TG as Telegram

    S->>SC: Trigger scrape
    SC->>SC: Run all 6 groups via asyncio.gather()
    SC->>API: Dedup check (POST /api/jobs/dedup-check)
    SC->>API: Save new jobs (POST /api/jobs)
    SC->>AN: Pass deduplicated jobs

    AN->>AN: Pre-filter (title, skills, freshness)
    AN->>AN: Embedding filter (MiniLM, threshold 0.35)
    AN->>LLM: Analyze passed jobs (structured JSON)
    LLM-->>AN: match_score, skills, decision
    AN->>API: Save analyses (POST /api/analyses)

    AN->>EM: YES jobs routed to cold_email
    EM->>EM: Find email, verify, generate content
    EM->>EM: Anti-hallucination check
    EM->>API: Enqueue email (POST /api/emails/enqueue)

    AN->>TG: High-score alerts (urgent channel)
    S->>TG: Batched review queue (every 2h)
    S->>TG: Daily digest (8 PM IST)
```

---

## Startup Scout Pipeline

A separate pipeline for early-stage startups, running independently from the main flow.

```mermaid
sequenceDiagram
    participant SS as Startup Scout
    participant SC as Scrapers (HN/YC/PH)
    participant API as FastAPI Backend
    participant SA as Startup Analyzer
    participant LLM as GPT-4o-mini
    participant EF as Email Finder

    SS->>SC: Scrape startup sources
    SC-->>SS: Raw startup data
    SS->>API: Dedup check
    SS->>SA: Analyze relevance
    SA->>LLM: Relevance + profile extraction (single call)
    LLM-->>SA: match_score + startup_profile metadata
    SS->>API: Save job + analysis + startup_profile
    SS->>SS: Age filter (skip if > 18 months)
    SS->>EF: Find founder emails
    EF-->>SS: Founder email addresses
    SS->>SA: Generate startup cold email
    SA->>LLM: Peer-to-peer email with profile context
    LLM-->>SA: Subject + body
    SS->>API: Enqueue email
```

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Runtime** | Python 3.12, asyncio | Async pipeline execution |
| **Package Manager** | pip | Dependency management |
| **API Backend** | FastAPI + asyncpg | REST API + PostgreSQL |
| **Pipeline Server** | FastAPI + uvicorn | Pipeline microservice (port 8002) |
| **Database** | Neon PostgreSQL | Job storage, analysis results |
| **LLM** | OpenAI GPT-4o-mini | Job analysis, content generation |
| **Embedding** | all-MiniLM-L6-v2 | Local similarity scoring |
| **HTTP** | httpx (async) | API communication, scraping |
| **Scraping** | python-jobspy | Indeed, Naukri, LinkedIn, Glassdoor |
| **Bot** | python-telegram-bot | Command handling, alerts |
| **Dashboard** | Next.js + shadcn/ui + Recharts | Web UI for monitoring |
| **Email** | aiosmtplib (Gmail SMTP) | Cold email delivery |
| **Config** | YAML + Pydantic | Validated profile config |
| **Prompt Management** | Langfuse | Versioned prompts + LLM tracing |
| **Linting** | Ruff | Import sorting, unused imports, code style |
| **Testing** | pytest (348 tests, 16 files) | Unit tests — no API calls, no network |

---

## Data Flow Summary

### Main Pipeline

```mermaid
graph LR
    A[172 scraped] --> B[148 after dedup]
    B --> C[48 after pre-filter]
    C --> D[25 after embedding]
    D --> E[25 LLM analyzed]
    E --> F[8 YES]
    E --> G[5 MAYBE]
    E --> H[12 NO]
    F --> I[4 cold emails]
    F --> J[4 direct apply]
    G --> K[Telegram review]

    style F fill:#27ae60,color:#fff
    style G fill:#f5a623,color:#fff
    style H fill:#e74c3c,color:#fff
```

### Startup Scout Pipeline

```mermaid
graph LR
    A[40 startups scraped] --> B[35 after dedup]
    B --> C[35 LLM analyzed]
    C --> D[12 relevant]
    C --> E[23 not relevant]
    D --> F[8 under 18 months]
    D --> G[4 too old]
    F --> H[5 emails found]
    H --> I[5 cold emails queued]

    style D fill:#27ae60,color:#fff
    style E fill:#e74c3c,color:#fff
    style G fill:#f5a623,color:#fff
```
