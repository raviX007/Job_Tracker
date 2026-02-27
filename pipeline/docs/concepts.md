# Concepts & Glossary

Plain English explanations of every technical term used in this project. Organized by topic — read the ones you need, skip the ones you know.

---

## The Big Picture

### What is an "agent"?

In AI, an "agent" is a program that acts on its own — it makes decisions, takes actions, and responds to results without someone manually telling it what to do at each step. This project is an "agent" because it scrapes jobs, decides which ones match, writes emails, and sends alerts — all automatically on a schedule.

### What is a "pipeline"?

A pipeline is a series of steps that data flows through, one after another. Like an assembly line in a factory. Raw material (job listings) goes in one end, passes through stations (dedup, filter, analyze, generate email), and finished product (a decision + email in your queue) comes out the other end.

### What is "scraping"?

Scraping means automatically reading a website's content using code instead of a human browser. The program sends the same HTTP request your browser would, gets the HTML (or JSON) back, and extracts the data it needs (job title, company, description, etc.). It's like copying information from a website, but 1000x faster.

---

## Python & Programming Concepts

### What is `async` / `await`?

Normally, Python does one thing at a time. If it's waiting for a response from Indeed's server (which takes ~2 seconds), it sits idle doing nothing.

With `async`, Python can say "I'll wait for Indeed, but while I'm waiting, let me also send a request to Naukri, and HiringCafe, and Jooble." When each response comes back, it processes them. This makes the scraping step ~5x faster because all 8 platforms are fetched in parallel instead of one by one.

**Analogy:** You're cooking dinner. Synchronous = boil water, wait, then chop vegetables, then preheat oven. Async = start boiling water, while it heats up chop vegetables, while those are done preheat the oven. Same tasks, fraction of the time.

### What is `asyncio.gather()`?

A Python function that takes multiple async tasks and runs them all at the same time. In our code:

```python
results = await asyncio.gather(
    scrape_indeed(),     # These all run at the
    scrape_naukri(),     # same time, not one
    scrape_remoteok(),   # after another
    scrape_jooble(),
)
```

### What is `httpx`?

A Python library for making HTTP requests (like a browser would). We use it to call APIs: "Hey Jooble, give me Python jobs in Bengaluru." httpx sends the request, gets the JSON response, and we parse it. It supports async, which is why we use it instead of the more common `requests` library.

### What is Pydantic?

A Python library for data validation. You define what your data should look like:

```python
class Candidate(BaseModel):
    name: str           # Must be a string
    email: str          # Must be a string
    years: int          # Must be a number
```

If someone's config says `years: "five"` instead of `years: 5`, Pydantic catches it immediately and tells you exactly what's wrong. This prevents bugs that would otherwise only show up much later.

### What is YAML?

A file format for configuration, designed to be human-readable. Think of it as a simpler version of JSON:

```yaml
# This is YAML — easy to read and write
candidate:
  name: "Ravi Raj"
  email: "ravi@gmail.com"
  skills:
    - Python
    - Django
    - React
```

The equivalent JSON would need more brackets and quotes. We use YAML for the profile config because it's easier to edit by hand.

### What is a hash?

A function that converts any text into a fixed-length string. Like a fingerprint for data.

```
Input:  "Visa|Python Developer|Bengaluru"
Output: "a3f7b2c1e9d8"  (always the same for the same input)
```

We use hashing for deduplication — instead of comparing full job descriptions (slow), we compare their hashes (instant). If two jobs produce the same hash, they're duplicates.

### What is a decorator?

The `@` symbol before a function in Python. It wraps the function with extra behavior:

```python
@lru_cache        # "Remember the result so you don't compute it twice"
def expensive():
    ...
```

You'll see `@lru_cache` (caching), `@staticmethod`, and others in the code. They're just shortcuts for adding functionality to functions.

---

## AI & Machine Learning Concepts

### What is an LLM?

Large Language Model. A neural network trained on billions of words that can understand and generate text. GPT-4o-mini (by OpenAI) is the LLM we use. When we "call the LLM," we're sending text to OpenAI's servers via their API and getting a response back.

**Cost:** GPT-4o-mini costs about $0.001 per job analyzed (~1500 tokens in, ~500 tokens out). That's about $0.15 per full pipeline run of 150 jobs.

### What is an embedding?

A way to convert text into numbers so that a computer can measure "similarity."

You can't ask a computer "is this job description similar to this resume?" directly — computers don't understand text. But if you convert both texts into lists of numbers (vectors), you can use math to compare them.

```
"Python Django REST API" → [0.12, -0.34, 0.56, ...] (384 numbers)
"Python Flask Web Dev"   → [0.14, -0.30, 0.52, ...] (384 numbers)  ← similar!
"Wind Turbine Engineer"  → [0.89, 0.12, -0.45, ...] (384 numbers)  ← very different
```

Texts with similar meaning produce similar numbers. Texts with different meaning produce different numbers. The embedding model (`all-MiniLM-L6-v2`) is what does this conversion.

### What is cosine similarity?

A math formula that measures how similar two lists of numbers are. It returns a value between 0 and 1:

- **1.0** = identical (same direction in 384-dimensional space)
- **0.0** = completely unrelated
- **0.45** = our threshold (anything above this is "similar enough" to warrant a closer look)

Don't worry about the math — just know it's a way to score similarity on a 0-to-1 scale.

### What is a "vector"?

Just a list of numbers. When we say "384-dimensional vector," we mean a list of 384 numbers. Each number captures some aspect of the text's meaning. The embedding model decides what each number represents (it's not human-interpretable — you can't say "position 17 represents Python skill").

### What is sentence-transformers?

A Python library that provides pre-trained embedding models. We use its `all-MiniLM-L6-v2` model — a small (80MB) model that runs locally on your CPU. No internet required after the first download. No API cost.

### What is "hallucination"?

When an LLM generates text that sounds correct but is factually wrong. For example, GPT might write in a cover letter: "During my 3 years at Google..." even though Ravi never worked at Google. The LLM isn't lying — it doesn't "know" facts, it generates text that sounds plausible.

Our anti-hallucination validator catches this by checking every generated text against Ravi's actual profile.

### What is "structured JSON output"?

Instead of asking GPT "analyze this job" and getting free-form text, we tell it: "Return your answer as JSON with exactly these fields: match_score, matching_skills, etc." This means we always get data we can parse programmatically:

```json
{"match_score": 78, "matching_skills": ["Python", "Django"]}
```

Instead of:

```
"I think this job is a good match because the candidate knows Python and Django..."
```

The first version is much easier for code to work with.

### What is ATS?

Applicant Tracking System. Software that companies use to manage job applications. When you apply online, your resume goes into an ATS (like Greenhouse, Lever, or Workday). Many ATS systems scan resumes for keywords — if your resume doesn't contain the right words, it might get auto-rejected before a human sees it.

That's why we extract "ATS keywords" from job descriptions and inject them into cover letters.

### What is RAG?

Retrieval-Augmented Generation. A technique where you first *retrieve* relevant documents from a database, then *generate* an answer using an LLM with those documents as context. Ravi built a RAG project, which means he built a system that searches through documents and uses GPT to answer questions about them.

### What is a "prompt"?

The text you send to an LLM. Like writing a very specific instruction:

```
"You are a job matching analyst. Here is a candidate's profile: [...]
Here is a job description: [...]
Score how well they match on a scale of 0-100.
Return your answer as JSON."
```

A good prompt makes the LLM give useful, structured, accurate responses. A vague prompt gives vague results.

---

## Database Concepts

### What is PostgreSQL?

A database — software for storing and querying structured data. Think of it as a very powerful spreadsheet with tables, rows, and columns. But unlike Excel, it can handle millions of rows, multiple simultaneous users, and complex queries.

We use PostgreSQL to store: all scraped jobs, analysis results, applications, email queue, and system settings.

### What is Neon?

A cloud service that hosts PostgreSQL databases. Their free tier gives you a small database that's always online. It's where our data lives — you don't need to install PostgreSQL on your computer.

**Gotcha:** Neon's free tier disconnects idle connections after a while. That's why we use `pool_pre_ping=True` (check if the connection is alive before using it) and `pool_recycle=300` (create a new connection every 5 minutes).

### What is a connection pool?

Opening a database connection is slow (~200ms). A connection pool keeps several connections open and ready to use. When your code needs the database, it borrows a connection from the pool, uses it, and returns it. This is much faster than opening a new connection every time.

```
Pool: [conn1 (idle), conn2 (in use), conn3 (idle)]
→ Request comes in → borrows conn1 → runs query → returns conn1
```

### What is `asyncpg`?

A Python library for connecting to PostgreSQL asynchronously. While `asyncpg` waits for a query result from the database, Python can do other things (like processing another job). We use this in the pipeline. The dashboard uses `SQLAlchemy` (sync) instead because Streamlit doesn't support async.

### What is SSL?

Secure Sockets Layer. Encryption for data in transit. When we connect to Neon with `ssl="require"`, all data between our computer and the database is encrypted. Anyone intercepting the traffic sees gibberish instead of our job data.

### What is a foreign key (FK)?

A column that points to a row in another table. In our schema:

```
email_queue.job_id → jobs.id    (this email is about THAT job)
email_queue.profile_id → profiles.id  (this email is from THAT user)
```

Foreign keys enforce relationships: you can't create an email for a job that doesn't exist.

### What is an index?

A data structure that makes searching faster. Without an index, finding all jobs from "indeed" means scanning every row in the table. With an index on the `source` column, the database can jump directly to the matching rows — like an index in a book.

We have 14 indexes on commonly-searched columns.

---

## Email & Networking Concepts

### What is a "cold email"?

An unsolicited email to someone you don't know. In job searching, it means emailing a hiring manager or engineer at a company directly, instead of applying through the normal job portal. Cold emails have a higher response rate than portal applications because they bypass the ATS.

### What is SMTP?

Simple Mail Transfer Protocol. The standard way computers send email. When our code sends an email, it connects to Gmail's SMTP server (`smtp.gmail.com`), authenticates with your email + password, and hands over the email. Gmail then delivers it.

### What is an "app password"?

Gmail won't let programs log in with your regular password (security risk). Instead, you generate a special "app password" — a 16-character code that only works for SMTP. You need 2-factor authentication enabled to create one.

### What is an MX record?

Mail Exchange record. A DNS entry that says "emails for @visa.com should go to this mail server." When verifying an email, we check if the domain has MX records — if not, the domain doesn't accept email, so the address is definitely fake.

### What is a "warmup schedule"?

If a brand new Gmail account suddenly sends 50 emails in one day, Gmail flags it as spam. A warmup schedule starts slow (5 emails/day in week 1) and gradually increases (15 emails/day by week 4). This builds "sender reputation" with Gmail's spam filters.

### What is rate limiting?

Controlling how fast you do something. If Jooble's API allows 500 requests per day, we track our usage and stop when we hit the limit. If Gmail allows 15 emails per day, we queue extras for tomorrow. This prevents getting banned.

---

## Infrastructure Concepts

### What is `uv`?

A fast Python package manager (like pip, but 10-100x faster). It installs dependencies, manages virtual environments, and runs scripts. When you see `uv run python main.py`, it means "run main.py using the project's virtual environment."

### What is APScheduler?

A Python library for running tasks on a schedule (like cron on Linux). We tell it: "Run the scrape function every hour between 9 AM and 10 PM IST." It handles the timing.

### What is Streamlit?

A Python framework for building web dashboards with minimal code. Instead of writing HTML/CSS/JavaScript, you write Python:

```python
st.title("Job Dashboard")
st.metric("Jobs Today", 172)
st.dataframe(jobs_table)
```

Streamlit converts this into a web page automatically. Great for data dashboards, not for building complex web apps.

### What is Plotly?

A charting library. We use it to create interactive charts in the dashboard — line charts for trends, pie charts for score distribution, bar charts for platform breakdown. Charts are interactive (hover for details, zoom, etc.).

### What is a Telegram bot?

A program that interacts with users through Telegram (a messaging app). You create a bot via Telegram's @BotFather, get a token (like a password), and your code uses that token to send messages and respond to commands. Our bot sends job alerts and accepts commands like `/stop` and `/status`.

### What is a "chat ID"?

Every Telegram user and channel has a unique number. When we send a message, we specify the chat ID to tell Telegram WHERE to send it. We have 3 different chat IDs for urgent, digest, and review channels.

---

## Job Market Terms

### What is a "dream company"?

A company you really want to work at. In the config, you list these companies. Any job from a dream company gets `MANUAL` review status — the system won't auto-skip it even if the score is low, because you want a human to evaluate it.

### What is "gap-tolerant"?

Some companies are more accepting of career gaps (time between graduating and getting a job). Signals include: startup culture, phrases like "we value learning", "self-taught welcome", or explicit 0-2 years experience. Our LLM checks for these signals.

### What is a "fresher"?

Indian term for a recent graduate with little or no work experience. The entire system is optimized for this profile: it boosts scores for fresher-friendly roles and penalizes senior roles.

---

## Quick Reference

| Term | One-line definition |
|------|-------------------|
| Agent | Program that acts autonomously |
| API | Way for programs to talk to each other |
| Async | Run multiple tasks at once instead of one by one |
| ATS | Software companies use to filter resumes |
| Cold email | Email to someone you don't know |
| Cosine similarity | Math formula: how similar are two vectors? (0 to 1) |
| Dedup | Remove duplicates |
| Embedding | Convert text → list of numbers for comparison |
| FK (Foreign Key) | Database column pointing to another table |
| Hallucination | LLM generates plausible but false text |
| Hash | Fingerprint of data (same input → same output) |
| httpx | Python library for HTTP requests (async) |
| Index (DB) | Makes database searches faster |
| LLM | AI that understands and generates text (e.g. GPT-4o-mini) |
| MX record | DNS entry saying where a domain's email goes |
| Normalize | Convert different formats into one standard format |
| Pipeline | Series of steps data flows through |
| Pool (DB) | Pre-opened connections for faster database access |
| Prompt | Instructions sent to an LLM |
| Pydantic | Python library for data validation |
| RAG | Retrieve documents + generate answer with AI |
| Rate limit | Cap on how many times you can call an API |
| Scraping | Reading a website's data using code |
| SMTP | Protocol for sending email |
| SSL | Encryption for data in transit |
| Structured JSON | Data in a specific format that code can parse |
| Token | Unit of text for LLMs (~1 token ≈ 0.75 words) |
| Vector | List of numbers representing meaning |
| Warmup | Gradually increase sending volume to avoid spam filters |
| YAML | Human-readable config file format |
