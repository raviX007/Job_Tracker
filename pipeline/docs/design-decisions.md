# Design Decisions & Tradeoffs

Every major technical choice in this project was deliberate. This document explains the reasoning, alternatives considered, and tradeoffs accepted.

---

## Two-Stage Filtering (Embedding + LLM)

**Decision:** Filter with a free local embedding model first, then send only passing jobs to the paid LLM.

**Alternatives considered:**

| Approach | Cost | Accuracy | Speed |
|----------|------|----------|-------|
| LLM only (analyze every job) | ~$0.15/run (150 jobs) | Best | Slow (rate limits) |
| Embedding only (no LLM) | Free | Poor (no nuance) | Fast |
| **Embedding + LLM (chosen)** | **~$0.03/run** | **Good** | **Fast** |

**Why two stages:**
- The embedding filter eliminates ~53% of jobs for free. That's ~80 fewer LLM calls per run.
- At $0.001/call, this saves ~$0.08/run or ~$2.40/month on daily runs.
- The embedding model catches obvious mismatches ("Chef Cook" vs a Python developer profile) that don't need GPT's reasoning.
- The LLM then handles nuance the embedding misses: "distributed systems" matching a "microservices" background, or detecting gap-tolerant language in JDs.

**Tradeoff accepted:** ~1 in 50 good jobs gets filtered by the embedding stage (false negative). Acceptable because thousands of new jobs appear weekly.

---

## 20+ Scrapers Instead of Just Indeed/LinkedIn

**Decision:** Scrape from 6 groups (20+ individual sources) rather than relying on 1-2 major platforms.

**Why:**
- **Coverage:** Indeed and LinkedIn have the most jobs, but they're also the most competitive. A job on Remotive or HiringCafe might have 50 applicants vs. 500 on LinkedIn.
- **Freshness:** Aggregators like Adzuna and Jooble surface jobs from company career pages that haven't been posted to major boards yet.
- **Startup access:** Early-stage startups don't post on Indeed. They post on HN "Who's Hiring", YC Directory, and ProductHunt. The startup scout pipeline exists specifically for these.
- **Data quality:** Different sources provide different metadata. Greenhouse/Lever give structured JDs with clear requirements sections. Indeed gives raw text.

**Tradeoff accepted:** More scrapers = more maintenance. When an API changes, that scraper breaks. Mitigated by the `@scraper` decorator pattern — each scraper is isolated and failures don't cascade.

---

## Langfuse for Prompt Management (Not Hardcoded)

**Decision:** Store all LLM prompts in Langfuse, not in the codebase.

**Alternatives considered:**

| Approach | Edit Prompts | Version History | A/B Test | Cost Tracking |
|----------|-------------|-----------------|----------|---------------|
| Hardcoded strings in code | Requires deploy | Via git | No | No |
| `.txt` template files | Requires deploy | Via git | No | No |
| **Langfuse (chosen)** | **Web UI, no deploy** | **Built-in** | **Yes** | **Per-version** |

**Why Langfuse:**
- Prompts are the most-iterated part of the system. Changing "Score 0-100" to "Score 0-100, penalize senior roles" shouldn't require a code commit + deploy.
- A/B testing: run two prompt versions simultaneously and compare LLM output quality.
- Tracing: every LLM call is logged with the exact prompt version, input tokens, output tokens, latency, and cost.
- Rollback: if a new prompt version produces bad results, revert in one click.

**Tradeoff accepted:** External dependency. If Langfuse is down, LLM calls return `None` and the pipeline skips analysis (graceful degradation, not a crash).

---

## API-First Architecture (No Direct DB Access)

**Decision:** The pipeline never connects to the database directly. All reads and writes go through the FastAPI backend.

**Why:**
- **Security:** The pipeline runs on GitHub Actions (public CI). Embedding database credentials in CI secrets is risky. API keys are easier to rotate and scope.
- **Consistency:** Database constraints, validation, and business logic live in one place (the API), not scattered across the pipeline and dashboard.
- **Independence:** The pipeline, API, and dashboard can be deployed and scaled independently. The pipeline doesn't care if the DB is PostgreSQL or SQLite — it just calls `POST /api/jobs`.
- **Testability:** API client tests mock HTTP responses. No database fixtures needed.

**Tradeoff accepted:** Network latency on every DB operation (~50ms per call). Acceptable for a pipeline that runs daily, not real-time.

---

## OpenAI GPT-4o-mini as Sole LLM

**Decision:** Use one model (GPT-4o-mini) for all LLM tasks. No fallbacks, no multi-provider setup.

**Why:**
- GPT-4o-mini handles all three tasks well: structured JSON extraction (job analysis), professional email generation, and cover letter writing.
- At $0.001/job, cost is negligible. Using a cheaper model would save pennies while risking quality.
- Single provider = simpler error handling, one API key, one rate limit to manage, one billing dashboard.

**Tradeoff accepted:** Vendor lock-in to OpenAI. If OpenAI raises prices or degrades quality, switching requires changing `core/llm.py` (~40 lines) and testing. See [LLM Stack Rationale](./llm-stack-rationale.md) for the full analysis of why we don't use LangChain for provider abstraction.

---

## all-MiniLM-L6-v2 for Embeddings

**Decision:** Use a small, local embedding model rather than OpenAI's embedding API.

**Alternatives considered:**

| Model | Size | Cost | Quality |
|-------|------|------|---------|
| OpenAI text-embedding-3-small | API call | $0.02/1M tokens | Best |
| all-MiniLM-L6-v2 (chosen) | 80MB local | Free | Good enough |
| all-mpnet-base-v2 | 420MB local | Free | Better, but slower |

**Why MiniLM:**
- **Cost:** Free vs. ~$0.0001/job for OpenAI embeddings. Over thousands of jobs, this adds up.
- **Speed:** ~50ms per job on CPU. No network latency.
- **Offline:** Works without internet. Pipeline can pre-filter locally before making any API calls.
- **Good enough:** The embedding filter is a coarse pre-filter, not the final decision. It only needs to separate "obviously irrelevant" from "possibly relevant." MiniLM does this well.

**Tradeoff accepted:** Lower quality than OpenAI embeddings. MiniLM has 384 dimensions vs. OpenAI's 1536. It misses some semantic connections (e.g., "MLOps" vs. "model deployment"). The LLM stage catches these.

---

## YAML + Pydantic for Profile Configuration

**Decision:** User profiles are YAML files validated by Pydantic models with 100+ fields.

**Why YAML over JSON/TOML/env vars:**
- **Readability:** YAML is easier to edit by hand than JSON (no trailing commas, comments allowed).
- **Nested structure:** Skills, experience, filters, platform configs — deeply nested config that's painful in flat env vars.
- **Validation:** Pydantic catches errors at load time with exact error messages. "Field `graduation_year` must be between 2015 and 2025" is better than a runtime KeyError.

**Why 100+ fields:**
- The profile drives everything: what to scrape, how to filter, what to put in emails, which companies are "dream companies," what skills to highlight. One config file replaces dozens of hardcoded values.

---

## Async Everything (asyncio + httpx)

**Decision:** The entire pipeline is async, from scraping to API calls to email verification.

**Why:**
- Scraping 20+ sources sequentially takes ~5 minutes. With `asyncio.gather()`, it takes ~45 seconds (limited by the slowest source).
- API calls (save job, save analysis, check dedup) can overlap with processing.
- httpx's async client reuses connections via connection pooling.

**Tradeoff accepted:** Async code is harder to debug (stack traces are less intuitive). Mitigated by structured logging with correlation IDs.

---

## Decorator-Based Scraper Registry

**Decision:** Scrapers register themselves via `@scraper(name="remotive", group="remote_boards")` decorator.

**Why:**
- **Auto-discovery:** Adding a new scraper = writing one function + one decorator. No need to update a central registry or import list.
- **Grouping:** `run_group("remote_boards")` runs all scrapers in that group concurrently. Groups are defined by the decorator, not a separate config.
- **Isolation:** If one scraper fails, `run_scraper()` catches the exception and logs it. Other scrapers continue.

**Tradeoff accepted:** Implicit registration (decorators run at import time). Debugging "why isn't my scraper running?" requires checking the decorator is correct and the module is imported.
