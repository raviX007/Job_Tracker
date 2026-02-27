# Lessons Learned & Future Improvements

What worked, what didn't, and what I'd do differently with hindsight.

---

## What Worked Well

### Two-Stage Filtering Saves Real Money
The embedding filter eliminates ~53% of jobs before the LLM sees them. At 179 jobs scraped, that's ~95 free rejections vs. ~$0.095 in LLM calls saved per run. Over a month of daily runs, the embedding stage pays for itself by saving ~$2.85 in API costs — which is significant when you're trying to keep total costs under $5/month.

### Langfuse for Prompt Iteration
I changed prompts 15+ times during development. Without Langfuse, each change would have been: edit code → commit → test → deploy. With Langfuse: edit in browser → immediately test. The version history also made it easy to roll back when a "clever" prompt change made the LLM start over-scoring every job.

### DRY_RUN Prevented Real Damage
During development, I accidentally queued 12 cold emails to real companies with a buggy email template. Because DRY_RUN was on by default, none were sent. The `EMAIL_SENDING_ENABLED` flag is a separate safety gate — even if DRY_RUN is off, emails don't send unless explicitly enabled.

### Async Scraping Is 5x Faster
Sequential scraping of 20+ sources: ~5 minutes. With `asyncio.gather()`: ~45 seconds. The bottleneck shifts from "waiting for HTTP responses" to "waiting for the slowest API."

---

## What Was Hard

### Email Discovery Is Unreliable
Finding the right email address for a hiring manager is the weakest link. The 5-strategy chain (Apollo → Snov → Hunter → pattern guess → LinkedIn scrape) has a ~70% success rate. The remaining 30% either have no discoverable email or get a generic `hr@company.com` that goes to a black hole.

**What I'd do differently:** Focus cold emails only on companies where I can find a *named person's* email. Generic `hr@` addresses have near-zero response rates. Better to send 5 targeted emails than 15 generic ones.

### Scraper Maintenance Is Ongoing
APIs change without warning. Jooble changed their response format once, breaking the normalizer. RemoteOK started rate-limiting more aggressively. Each break requires reading the new API response, updating the normalizer function, and adding/updating tests.

**What I'd do differently:** Add integration smoke tests that run weekly against live APIs (not in CI — in a scheduled cron job) to catch API changes early.

### Embedding Threshold Tuning Is Trial-and-Error
The 0.35 cosine similarity threshold was tuned by hand: run 100 jobs, check which ones the embedding rejected, see if any were false negatives. No systematic evaluation. I settled on 0.35 because it had ~1 false negative per 50 jobs, which felt acceptable.

**What I'd do differently:** Create a labeled dataset of 200 jobs (100 relevant, 100 not) and compute precision/recall curves at different thresholds. Pick the threshold that maximizes F1 score, not gut feeling.

---

## What I'd Change If Rebuilding

### 1. Fine-Tune the Embedding Model
**Current:** Generic all-MiniLM-L6-v2 trained on general text.
**Problem:** It doesn't understand job market nuance. "MLOps" and "model deployment" are semantically close but MiniLM scores them lower than expected.
**What I'd do:** Fine-tune on 500 hand-labeled (job_description, relevant/not_relevant) pairs using the `sentence-transformers` training loop. Even 200 labeled pairs would improve domain-specific accuracy.

### 2. Few-Shot Prompting for LLM Analysis
**Current:** Zero-shot prompt with scoring rules in the system message.
**Problem:** The LLM sometimes misinterprets scoring rules. "Fresher-friendly" is supposed to mean 0-2 years experience, but the LLM occasionally marks 3-year roles as fresher-friendly.
**What I'd do:** Add 3-5 example analyses in the prompt (few-shot). Show the LLM: "Here's a job, here's the correct analysis." This anchors the scoring and reduces interpretation drift.

### 3. Integration Tests Against a Staging API
**Current:** 348 unit tests with mocked HTTP responses. Zero integration tests.
**Problem:** Unit tests pass even when the real API is returning 500 errors. I discovered this when the API schema changed and the pipeline silently failed (every `save_job` returned `None`).
**What I'd do:** Add 10-15 integration tests that hit a staging API instance. Run them as a separate CI job (not blocking, but alerting).

### 4. Queue Architecture for Long-Running Tasks
**Current:** The pipeline runs synchronously end-to-end. If the embedding stage crashes halfway, the entire run restarts from scratch.
**Problem:** A full run with 200+ jobs takes ~3 minutes. If it fails at job #180, all progress is lost.
**What I'd do:** Use a task queue (Redis + RQ or Celery) where each job is an independent task. Failures don't affect other jobs, and retries happen at the individual job level.

### 5. Better Cold Email Targeting
**Current:** Cold emails go to anyone we can find at the company.
**Problem:** Emailing `hr@company.com` or a generic recruiter has a low response rate. Engineering managers or team leads are much more likely to respond to a technical candidate.
**What I'd do:** Prioritize finding *engineering manager* or *team lead* emails. Use LinkedIn title data from the email finder to filter recipients by role before generating the email.

---

## Scalability Considerations

### What breaks at 10K jobs/day

| Component | Current Capacity | Bottleneck At | Fix |
|-----------|-----------------|---------------|-----|
| Scraping | ~200 jobs/min (async) | Rate limits at 10K | Distribute across IPs or schedule scrapes in waves |
| Embedding | ~50 jobs/min (CPU) | 10K = 200 min on single CPU | Batch vectorization + GPU, or use OpenAI embeddings API |
| LLM Analysis | ~60 jobs/min (API rate limit) | 10K = 167 min | Batch API calls, or use cheaper model for Stage 1 |
| Database | Neon free tier (25 connections) | 500+ concurrent writes | Upgrade to paid tier or self-hosted PostgreSQL |
| Email verification | ~500 req/month (free tiers) | Day 1 | Paid verification API or in-house MX check |

### Current costs (daily run, ~180 jobs)

| Component | Monthly Cost |
|-----------|-------------|
| OpenAI GPT-4o-mini | ~$2.50 (80 analyzed jobs/day x 30 days x $0.001) |
| Neon PostgreSQL | $0 (free tier: 0.5 GB storage) |
| Render (API hosting) | $0 (free tier) |
| Langfuse | $0 (free tier: 50K observations/month) |
| Email verification APIs | $0 (free tiers combined) |
| **Total** | **~$2.50/month** |

---

## Key Takeaways

1. **Start with the cheapest option that works.** MiniLM + GPT-4o-mini costs < $3/month. Optimize only when it's the actual bottleneck.
2. **Safety gates are not optional.** DRY_RUN saved me from sending bad emails multiple times. Always default to safe mode.
3. **Prompt engineering is iterative.** My first job analysis prompt scored every Python job as 90+. It took 15 iterations to get balanced scoring. Langfuse made this iteration fast.
4. **Test the boundaries, not just the happy path.** The dedup system worked perfectly until two scrapers returned the same job with different URL encodings. Edge cases in URL normalization caught 3 bugs.
5. **Documentation pays for itself.** Writing the walkthrough forced me to simplify the pipeline. If I can't explain a step in plain English, it's too complicated.
