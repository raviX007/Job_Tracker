# Walkthrough: Follow One Job from Scrape to Telegram

**Read this first.** This traces a single job posting through the entire system, step by step. By the end you'll understand what every part of the project does and why it exists.

---

## The Setup

Imagine Ravi is looking for a Python developer job in Bengaluru. Instead of manually checking Indeed, Naukri, LinkedIn, and 5 other websites every day, this system does it automatically — every hour, from 9 AM to 10 PM.

Let's follow one specific job: **"Python Developer at Visa, Bengaluru"** as it moves through the system.

---

## Step 1: Scraping — "Go check all the job websites"

**What happens:** The system visits 8 different job platforms and collects every new job posting it finds.

Think of it like hiring 8 assistants, each assigned to one job website. You tell all 8 to go search at the same time (that's what `asyncio.gather()` does — runs things in parallel, not one after another).

```
Assistant 1 (Indeed):     Found 95 jobs
Assistant 2 (Naukri):     Found 54 jobs
Assistant 3 (LinkedIn):   Found 30 jobs
Assistant 4 (Glassdoor):  Found 20 jobs
Assistant 5 (RemoteOK):   Found 12 jobs
Assistant 6 (Jooble):     Found 35 jobs
Assistant 7 (Adzuna):     Found 15 jobs
Assistant 8 (HiringCafe): Found 62 jobs
                          ─────────────
                   Total: 323 jobs found
```

Our Visa job was found by Indeed. Here's what the raw data looks like after the scraper normalizes it (converts it into a standard format):

```python
{
    "title": "Python Developer",
    "company": "Visa",
    "location": "Bengaluru, Karnataka, India",
    "source": "indeed",              # Which website hosts it
    "discovered_via": "jobspy",      # How we found it (the tool we used)
    "description": "We are looking for a Python Developer to join our payments team. Requirements: Python 3+, Django or FastAPI, REST APIs, PostgreSQL. Nice to have: Docker, AWS, microservices experience. 0-3 years experience...",
    "job_url": "https://careers.visa.com/jobs/python-developer-12345",
    "date_posted": "2025-01-14",
    "is_remote": false,
    "salary_min": null,
    "salary_max": null,
}
```

**Why normalize?** Every website returns data in a different format. Indeed calls it "company_name", Naukri calls it "companyName", HiringCafe calls it "company_name_raw". Normalizing means we convert all of them into the same format so the rest of the system doesn't care where the job came from.

**Files:** `scraper/jobspy_scraper.py`, `scraper/aggregator_scraper.py`

---

## Step 2: Dedup — "Have we seen this before?"

**What happens:** Many job websites show the same job. Visa probably posted this role on Indeed AND Naukri AND their own career page. We don't want to analyze it 3 times.

**How it works:** We create a "fingerprint" of each job in two ways:
1. **URL fingerprint** — Clean up the URL (remove tracking junk like `?utm_source=google`) and hash it
2. **Content fingerprint** — Combine `company + title + location` and hash that

If either fingerprint matches something we've already seen (in the database or in this batch), skip it.

```
Before dedup: 323 jobs
After dedup:  261 jobs (62 duplicates removed)
```

Our Visa job's URL is unique and we haven't seen "Visa + Python Developer + Bengaluru" before, so it passes.

**What's a hash?** A hash is like a fingerprint for text. You feed in "Visa|Python Developer|Bengaluru" and get back something like `a3f7b2c1`. The same input always gives the same output. Different input gives a different output. This makes comparing thousands of jobs very fast — just compare fingerprints instead of full text.

**File:** `scraper/dedup.py`

---

## Step 3: Pre-filter — "Is this even worth looking at?"

**What happens:** Before spending any computing power (embedding or LLM), we do 4 quick checks that cost nothing:

```
Check 1: Is it fresh?
  → Posted January 14, today is January 15. That's 1 day old.
  → Our limit is 7 days. ✅ PASS

Check 2: Is the title suspicious?
  → "Python Developer" — not "Senior", "Lead", "QA", "Director"
  → ✅ PASS

Check 3: Is the company blocked?
  → "Visa" is not in our skip list
  → ✅ PASS

Check 4: Does the description mention at least ONE keyword we care about?
  → Scanning for: python, django, fastapi, react, javascript...
  → Found "Python", "Django", "FastAPI"
  → ✅ PASS
```

Jobs that fail any check are skipped immediately. This is where most jobs get filtered out:

```
Before pre-filter: 261 jobs
After pre-filter:   68 jobs (193 filtered out)
  - 89 too old (posted 8+ days ago)
  - 61 wrong title (senior, lead, manager, QA, etc.)
  - 43 no relevant keywords in description
```

**Why?** If a job says "Senior Engineering Manager — 10+ years required" there's no point running an expensive LLM analysis on it. We already know it's not a match.

**File:** `analyzer/freshness_filter.py`

---

## Step 4: Source Router — "Where should we apply?"

**What happens:** We look at the job URL to figure out what action to take.

Our Visa job's URL is `https://careers.visa.com/...` — that's Visa's own career page (not a job board). The system recognizes this:

```
URL: careers.visa.com
→ Not Naukri/Indeed (can't auto-apply)
→ Not LinkedIn (can't auto-apply)
→ It's a company career page
→ Action: cold_email_only (find someone at Visa to email directly)
```

Different URLs get different treatment:

| URL Domain | Action |
|-----------|--------|
| naukri.com, indeed.com | Auto-apply (future) + cold email |
| linkedin.com | Manual alert only (can't automate) |
| careers.visa.com, greenhouse.io | Find HR email, send cold email |
| glassdoor.com | View-only (find the real posting) |

**Why?** You can't apply the same way everywhere. LinkedIn blocks automation. Naukri has an "Easy Apply" button. Company career pages need you to find an actual person to reach out to. The router decides the strategy.

**File:** `scraper/source_router.py`

---

## Step 5: Embedding Filter — "Quick similarity check"

**What happens:** This is the first "smart" filter. It checks how similar Ravi's profile is to the job description using math — no LLM, no API call, completely free and fast.

**How?** (simplified)
1. Take Ravi's skills/experience and convert it into a list of 384 numbers (called a "vector" or "embedding")
2. Take the job description and convert it into another list of 384 numbers
3. Compare the two lists using cosine similarity (a math formula that measures how similar two lists of numbers are — 1.0 = identical, 0.0 = completely different)

```
Ravi's profile → [0.12, -0.34, 0.56, 0.78, ...] (384 numbers)
Visa JD        → [0.15, -0.29, 0.61, 0.72, ...] (384 numbers)

Cosine similarity = 0.67  (pretty similar!)
Threshold = 0.45

0.67 >= 0.45 → ✅ PASS
```

But a "Wind Energy O&M Engineer" job description would produce very different numbers:

```
Wind engineer JD → [0.89, 0.12, -0.45, -0.67, ...]

Cosine similarity = 0.18  (very different)
0.18 < 0.45 → ❌ FILTERED OUT (saved us an LLM call!)
```

```
Before embedding: 68 jobs
After embedding:  31 jobs (37 filtered — too dissimilar)
```

**Why not just use the LLM for everything?** Because calling GPT-4o-mini costs ~$0.001 per job. That's small, but 68 jobs × multiple runs per day adds up. The embedding filter is free (runs locally on your computer) and eliminates jobs that are obviously not relevant. We only spend LLM money on the 31 that look promising.

**What does the model look like?** It's called `all-MiniLM-L6-v2` — an 80MB file that downloads once and runs on your CPU. No GPU needed. It takes ~50ms (0.05 seconds) per job. Think of it as a small brain that understands the "meaning" of text, not just keywords.

**File:** `analyzer/embedding_filter.py`

---

## Step 6: LLM Analysis — "Deep evaluation by GPT"

**What happens:** Now we send the job description + Ravi's profile to GPT-4o-mini and ask: "How well does this person match this job? Give me a detailed breakdown."

The prompt includes:
- Ravi's full skills, work history, projects, degree
- His career gap explanation
- The job description (first 3000 characters)
- Scoring rules (Python match = +15 points, missing critical skill = -15 points, etc.)

GPT returns structured JSON — not free-form text, but a specific format we can parse:

```json
{
    "match_score": 78,
    "required_skills": ["Python", "Django", "FastAPI", "PostgreSQL", "REST APIs"],
    "matching_skills": ["Python", "Django", "FastAPI", "PostgreSQL", "REST APIs"],
    "missing_skills": ["AWS (nice to have)"],
    "ats_keywords": ["microservices", "payments", "API development", "CI/CD"],
    "experience_required": "0-3 years",
    "location_compatible": true,
    "remote_compatible": false,
    "company_type": "mnc",
    "gap_tolerant": true,
    "red_flags": [],
    "apply_decision": "YES",
    "cold_email_angle": "Your payments-focused Python experience and REST API projects directly align with Visa's developer platform team.",
    "gap_framing_for_this_role": "Career gap spent building production-grade Python projects including a RAG system and AI agent — directly relevant to Visa's tech stack.",
    "reasoning": "Strong primary skill match (Python, Django, FastAPI, PostgreSQL). Role is 0-3 years which is fresher-friendly. Visa is an MNC but the posting signals openness to learning. AWS is only nice-to-have, not blocking."
}
```

**Score = 78 → Decision = YES** (threshold is 60 for YES, 40 for MAYBE)

**Why structured JSON?** Because the next steps (cover letter, cold email, routing) need to read these fields programmatically. If GPT returned free-form text like "I think this is a good match because...", we'd have to parse that text to figure out the score, which is fragile and error-prone.

**File:** `analyzer/llm_analyzer.py`

---

## Step 7: Content Generation — "Write the cover letter and cold email"

**What happens:** For every YES job, the system generates:
1. A **cover letter** (max 150 words) — personalized for this specific JD
2. A **cold email** (max 200 words) — to send directly to someone at the company

Both use GPT-4o-mini and are informed by the analysis from Step 6 (matching skills, cold email angle, gap framing).

**Cover letter for our Visa job:**

> Dear Hiring Team,
>
> I'm writing to express my interest in the Python Developer position at Visa. With hands-on experience in Python, Django, FastAPI, and PostgreSQL — the core technologies listed in your requirements — I'm confident I can contribute to your payments platform team.
>
> During my career transition period, I built production-grade projects including a ReAct AI Agent with tool orchestration and a Hybrid Search RAG system using FAISS and Qdrant. At Zelthy, I developed automated case management systems using Django and implemented role-based access control.
>
> I'm particularly drawn to Visa's focus on API development and microservices architecture, areas where my REST API and backend experience directly apply.
>
> I'd welcome the opportunity to discuss how my skills align with your team's needs.

**File:** `emailer/cover_letter.py`, `emailer/cold_email.py`

---

## Step 8: Anti-Hallucination Check — "Did GPT make stuff up?"

**What happens:** LLMs sometimes "hallucinate" — they invent facts that sound right but aren't true. Before saving anything, we check:

```
Check 1: Company references
  → Does the letter mention any company Ravi didn't work at?
  → Mentioned: Zelthy ✅ (he worked there)
  → No fabricated companies. ✅ PASS

Check 2: Degree claims
  → Does it say "Master's" or "PhD"?
  → No, only references relevant to his B.Tech. ✅ PASS

Check 3: Experience inflation
  → Does it claim "5 years of experience"?
  → No. ✅ PASS

Check 4: Skill fabrication
  → Does it mention skills not in Ravi's profile?
  → All mentioned skills (Python, Django, FastAPI, PostgreSQL) are in his config. ✅ PASS
```

If any check fails, the content is flagged and regenerated. We never send a cold email that claims Ravi worked at Google if he didn't.

**File:** `emailer/validator.py`

---

## Step 9: Email Discovery — "Who do we send this to?"

**What happens:** We need an actual email address at Visa. The system tries 7 strategies in order, stopping at the first success:

```
Strategy 1: Apollo.io API → Found "john.doe@visa.com" (Engineering Manager) ✅
(Would have tried Snov.io, Hunter.io, team page scraping, GitHub, Google, pattern guessing if Apollo failed)
```

Then it verifies the email is real:

```
Layer 1: Regex check — is it a valid email format? ✅
Layer 2: MX record  — does visa.com accept email? ✅
Layer 3: Disposable  — is it a throwaway domain? No ✅
Layer 4: API verify  — does this specific address exist? ✅ (confidence: 0.92)
```

**Why verify?** Sending emails to invalid addresses gets your Gmail account flagged as spam. One too many bounces and Google might block your entire account.

**File:** `emailer/email_finder.py`, `emailer/verifier.py`

---

## Step 10: Save to Queue — "Store it, don't send it"

**What happens:** The cold email is saved to the database with status `"ready"`. It is NOT sent yet.

```sql
INSERT INTO email_queue (
    recipient_email: "john.doe@visa.com",
    subject: "Python Developer — Visa (Bengaluru)",
    body_plain: "Hi John, I noticed Visa's payments team...",
    body_html: "<p>Hi John, I noticed Visa's payments team...</p>",
    status: "ready",           -- Composed and verified, waiting to send
    email_verified: true,
    email_verification_result: "valid",
)
```

**Why not send immediately?** Two safety gates:

1. **`DRY_RUN=true`** — When testing, nothing external happens. The system scrapes, analyzes, generates emails, but never sends them. You see everything in the dashboard.

2. **`EMAIL_SENDING_ENABLED=false`** — Even in production, emails stay at "ready" status by default. You have to explicitly flip this to `true` when you're confident the system is working correctly.

This means you can run the entire system for days, review every generated email in the dashboard, and only start actually sending when you trust the output.

**File:** `emailer/queue.py`

---

## Step 11: Telegram Alert — "Hey, check this out!"

**What happens:** Since Visa scored 78 (above 80 threshold? No, but it's a YES), a notification goes to the review Telegram channel. If the score were 85+, it would go to the urgent channel instead.

**Urgent channel message (for score >= 80 or dream companies):**

```
🎯 HIGH MATCH: Python Developer at Visa

Score: 78/100
Skills: Python ✅, Django ✅, FastAPI ✅, PostgreSQL ✅, AWS ❌
Decision: YES
Type: MNC | Gap-tolerant: Yes

🔗 https://careers.visa.com/jobs/python-developer-12345
📧 Cold email queued → john.doe@visa.com
```

There are 3 Telegram channels:
- **Urgent** — High scores, dream companies, errors (real-time)
- **Review** — Batched every 2 hours (MAYBE jobs, email previews)
- **Digest** — Daily summary at 8 PM (today's stats, follow-up reminders)

**Why 3 channels?** If every single job went to one channel, you'd get 30+ messages a day and start ignoring them. Splitting by priority means you only get interrupted for genuinely exciting matches.

**File:** `bot/telegram_handler.py`, `bot/review_queue.py`

---

## Step 12: Dashboard — "See everything in one place"

**What happens:** Open `http://localhost:8501` and see the Streamlit dashboard with 5 pages:

1. **Overview** — Today's numbers: 323 scraped, 31 analyzed by LLM, 8 YES, 4 emails queued
2. **Applications** — Browse all analyzed jobs, filter by score/decision/platform, see matching/missing skills
3. **Update Outcomes** — Mark jobs as "got interview", "rejected", "ghosted" — tracks your response rate
4. **Cold Emails** — See every email in the queue, check who it's going to, read the content before it sends
5. **Analytics** — Charts: which platforms give the best jobs, what scores look like over time, response rates by method

**File:** `dashboard/app.py`, `dashboard/pages/`

---

## The Full Journey — Summary

```
"Python Developer at Visa"

Step 1:  Scraped from Indeed (1 of 323 jobs found across 8 platforms)
Step 2:  Dedup check — never seen before ✅
Step 3:  Pre-filter — fresh, good title, has Python keyword ✅
Step 4:  Route — career page → cold_email_only
Step 5:  Embedding — 0.67 similarity (threshold 0.45) ✅
Step 6:  LLM — score 78, decision YES
Step 7:  Generated cover letter + cold email
Step 8:  Anti-hallucination — no fabrications ✅
Step 9:  Found john.doe@visa.com via Apollo, verified ✅
Step 10: Saved to email_queue (status: ready)
Step 11: Telegram alert sent to review channel
Step 12: Visible in dashboard

Total time: ~3 seconds for this one job
Total cost: ~$0.001 (one GPT-4o-mini call)
```

---

## What Runs When?

The system doesn't run once — it runs on a schedule, every day:

| Time (IST) | What Happens |
|------------|-------------|
| 9:00 AM | First scrape cycle. Scrape all 8 platforms → dedup → filter → analyze → route |
| 10:00 AM | Second scrape cycle (new jobs posted since 9 AM) + follow-up reminders check |
| 11:00 AM - 8:00 PM | Scrape cycle every hour |
| Every 2 hours | Batch review notifications sent to Telegram |
| 8:00 PM | Daily digest: "Today: 172 scraped, 8 YES, 4 emails queued, 1 interview!" |
| 9:00 PM - 10:00 PM | Last scrape cycles of the day |

Everything is controlled by the scheduler (`scheduler/cron.py`) and can be paused with a `/stop` message in Telegram.

---

## Next: Read the Concepts

If any terms were unclear (embedding, cosine similarity, async, SMTP, hashing, etc.), read the **[Concepts & Glossary](concepts.md)** — it explains every technical term used in this project in plain English.

Then pick any doc from the [README](../README.md) to dive deeper into a specific part.
