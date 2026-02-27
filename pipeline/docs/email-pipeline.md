# Email Pipeline

Handles email discovery, verification, content generation, anti-hallucination validation, and queuing. Emails are composed and saved via the API — never sent automatically unless `EMAIL_SENDING_ENABLED=true`.

There are two email flows:
1. **Main pipeline** — formal cold emails for job applications (HR/recruiter tone)
2. **Startup scout** — peer-to-peer cold emails to founders (developer-to-founder tone)

---

## Email Lifecycle

```mermaid
flowchart TD
    JOB["YES job<br/>routed to cold_email"] --> FIND["1. Find Email<br/>5-strategy chain"]

    FIND --> VERIFY["2. Verify Email<br/>4-layer check"]

    VERIFY --> RESULT{Verification<br/>result?}

    RESULT -->|valid / catch_all| GEN["3. Generate Content"]
    RESULT -->|risky| GEN
    RESULT -->|invalid| SKIP["Skip — bad email"]

    GEN --> COVER["Cover Letter<br/>(150 words max)"]
    GEN --> COLD["Cold Email<br/>(200 words max)"]

    COVER --> VALIDATE["4. Anti-Hallucination<br/>Validator"]
    COLD --> VALIDATE

    VALIDATE --> VALID{Passes<br/>checks?}

    VALID -->|Yes| QUEUE["5. Save to email_queue<br/>status: draft"]
    VALID -->|No| FIX["Flag issues<br/>Regenerate or skip"]

    QUEUE --> ADVANCE["6. Advance status<br/>draft → verified → ready"]

    ADVANCE --> GATE{EMAIL_SENDING<br/>_ENABLED?}

    GATE -->|false| STAY["Stay at 'ready'<br/>Viewable in dashboard"]
    GATE -->|true| SEND["7. Send via Gmail SMTP<br/>Rate limited"]

    SEND --> TRACK["Update status<br/>sent → delivered/bounced"]

    style SKIP fill:#e74c3c,color:#fff
    style STAY fill:#f5a623,color:#fff
    style SEND fill:#27ae60,color:#fff
```

---

## 1. Email Finder

**File:** `emailer/email_finder.py`

5-strategy priority chain — stops at first successful find.

```mermaid
flowchart TD
    INPUT["Company name +<br/>Job URL"] --> S1["Strategy 1: Apollo.io<br/>100 credits/month"]

    S1 -->|Found| DONE[Return email]
    S1 -->|Not found| S2["Strategy 2: Snov.io<br/>50 credits/month"]

    S2 -->|Found| DONE
    S2 -->|Not found| S3["Strategy 3: Hunter.io<br/>25 credits/month"]

    S3 -->|Found| DONE
    S3 -->|Not found| S4["Strategy 4: Company<br/>team page scrape"]

    S4 -->|Found| DONE
    S4 -->|Not found| S5["Strategy 5: Pattern<br/>guess"]

    S5 --> PATTERNS["firstname@company.com<br/>first.last@company.com<br/>hr@company.com<br/>careers@company.com"]

    PATTERNS --> DONE
```

### Strategy Details

| # | Strategy | Source | Free Tier | Speed |
|---|----------|--------|-----------|-------|
| 1 | Apollo.io | API | 100 credits/mo | Fast |
| 2 | Snov.io | API | 50 credits/mo | Fast |
| 3 | Hunter.io | API | 25 credits/mo | Fast |
| 4 | Team page | Web scrape | Unlimited | Medium |
| 5 | Pattern guess | Algorithm | Unlimited | Instant |

### Removed Strategies

| Strategy | Reason |
|----------|--------|
| GitHub commit emails | Violates GitHub Acceptable Use Policies |
| Google dorking | Scraping Google HTML violates ToS |

### Email Patterns Generated

| Pattern | Example |
|---------|---------|
| `firstname@domain` | john@acme.com |
| `first.last@domain` | john.doe@acme.com |
| `firstlast@domain` | johndoe@acme.com |
| `f.last@domain` | j.doe@acme.com |
| `hr@domain` | hr@acme.com |
| `careers@domain` | careers@acme.com |

---

## 2. Email Verifier

**File:** `emailer/verifier.py`

4-layer verification pipeline, each layer progressively more expensive.

```mermaid
flowchart TD
    EMAIL[Email address] --> L1["Layer 1: Regex<br/>Syntax check"]

    L1 -->|Invalid format| INVALID["invalid"]
    L1 -->|Valid format| L2["Layer 2: MX Record<br/>DNS lookup"]

    L2 -->|No MX record| INVALID
    L2 -->|Has MX| L3["Layer 3: Disposable<br/>Domain check"]

    L3 -->|Disposable domain| RISKY["risky"]
    L3 -->|Real domain| L4["Layer 4: API Verify<br/>Hunter.io"]

    L4 -->|verified| VALID["valid"]
    L4 -->|catch_all| CATCHALL["catch_all"]
    L4 -->|not found| UNKNOWN["unknown"]
    L4 -->|API unavailable| UNVERIFIED["unverified"]

    style VALID fill:#27ae60,color:#fff
    style INVALID fill:#e74c3c,color:#fff
    style RISKY fill:#f5a623,color:#fff
```

### Verification Result

```python
{
    "status": "valid",       # valid, invalid, risky, catch_all, unknown, unverified
    "provider": "hunter",    # Which API verified
    "confidence": 0.92,      # 0.0-1.0
    "mx_valid": True,
    "is_disposable": False,
}
```

---

## 3. Cover Letter Generator

**File:** `emailer/cover_letter.py`

| Parameter | Value |
|-----------|-------|
| Model | GPT-4o-mini |
| Max length | 150 words |
| Inputs | Job analysis + profile + ATS keywords |
| Style | Gap-aware, ATS-optimized |
| Prompts | Langfuse template support |

### Prompt Constraints

- Maximum 150 words
- Mention specific skills matching the JD
- Frame the career gap positively (using `gap_framing_for_this_role` from analysis)
- Include relevant ATS keywords naturally
- No fabricated experience, companies, or certifications
- Professional tone, personalized per company

---

## 4. Cold Email Generator (Main Pipeline)

**File:** `emailer/cold_email.py`

Used for standard job applications — targets HR, recruiters, or hiring managers.

| Parameter | Value |
|-----------|-------|
| Model | GPT-4o-mini |
| Max length | 200 words |
| Output | Subject + plain body + HTML body |
| Features | Unsubscribe line, signature from config |
| Prompts | Langfuse template support |

### Cold Email Structure

```
Subject: [Personalized subject line]

Body:
- Hook: Why this company/role caught your attention
- Value prop: Specific skills matching the JD
- Proof: Relevant project or experience
- CTA: Conversation request

Signature:
  Name
  Phone | Email | GitHub

Unsubscribe line: "Reply STOP to opt out"
```

---

## 4b. Startup Cold Email Generator

**File:** `scripts/_startup_analyzer.py` → `generate_startup_cold_email()`

A separate generator for the startup scout pipeline — targets founders and CTOs with peer-to-peer tone.

| Parameter | Value |
|-----------|-------|
| Model | GPT-4o-mini |
| Max length | 150 words |
| Tone | Developer-to-founder (peer, not applicant) |
| Inputs | Startup profile + analysis + source context |

### Key Differences from Main Cold Email

| Aspect | Main Pipeline | Startup Scout |
|--------|--------------|---------------|
| Target | HR / recruiter | Founder / CTO |
| Tone | Professional applicant | Peer developer |
| Reference | Formal JD | Startup description |
| Source mention | Job board | "Saw on HN / YC / ProductHunt" |
| Max words | 200 | 150 |
| Profile data | Job analysis only | Startup profile (funding, tech stack, team size) |

### Startup-Specific Prompt Injections

When a `startup_profile` is available, the prompt includes:
- **Funding stage + amount** — "just raised your seed round"
- **Tech stack overlap** — "your Python/React stack is exactly what I work with"
- **Team size** — "small team of 5 — I can wear multiple hats"
- **Customer status** — "you already have customers — I can help scale"
- **Source context** — "saw your launch on ProductHunt"

---

## 5. Anti-Hallucination Validator

**File:** `emailer/validator.py`

Checks all LLM-generated content before saving to queue.

```mermaid
flowchart TD
    CONTENT["Generated<br/>cover letter / email"] --> C1{"Check 1:<br/>Only allowed<br/>companies?"}

    C1 -->|Fail| ISSUE1["Issue: Fabricated<br/>company reference"]
    C1 -->|Pass| C2{"Check 2:<br/>No fabricated<br/>degrees?"}

    C2 -->|Fail| ISSUE2["Issue: Fake<br/>credential"]
    C2 -->|Pass| C3{"Check 3:<br/>No inflated<br/>experience?"}

    C3 -->|Fail| ISSUE3["Issue: Inflated<br/>years"]
    C3 -->|Pass| C4{"Check 4:<br/>Skills exist<br/>in profile?"}

    C4 -->|Fail| ISSUE4["Issue: Non-existent<br/>skill mentioned"]
    C4 -->|Pass| VALID["Content safe<br/>to queue"]

    ISSUE1 --> REJECT["Flag for<br/>regeneration"]
    ISSUE2 --> REJECT
    ISSUE3 --> REJECT
    ISSUE4 --> REJECT

    style VALID fill:#27ae60,color:#fff
    style REJECT fill:#e74c3c,color:#fff
```

### Validation Checks

| Check | What It Catches | Source of Truth |
|-------|----------------|-----------------|
| Company references | "During my time at Google..." (never worked there) | `anti_hallucination.allowed_companies` |
| Degree claims | "My Master's in CS..." (only has B.Tech) | `experience.degree` |
| Experience inflation | "With 5 years of experience..." (has <1 year) | `experience.years` |
| Skill fabrication | "Expert in Kubernetes..." (not in profile) | `skills.primary` + `secondary` + `frameworks` |

---

## 6. Email Queue

All composed emails are saved via `core/api_client.py` → `POST /api/emails/enqueue` to the `email_queue` table in the API backend.

### Status Lifecycle

```mermaid
stateDiagram-v2
    [*] --> draft: Email composed
    draft --> verified: Email address verified
    verified --> ready: Content validated
    ready --> queued: Picked for sending
    queued --> sent: SMTP delivery success
    sent --> delivered: No bounce
    sent --> bounced: Bounce detected
    queued --> failed: SMTP error

    note right of ready
        If EMAIL_SENDING_ENABLED=false,
        emails stay here permanently.
        Viewable in dashboard.
    end note
```

### Queue API Functions (in `core/api_client.py`)

| Function | API Call | Purpose |
|----------|---------|---------|
| `enqueue_email()` | `POST /api/emails/enqueue` | Save composed email (status: draft) |
| `mark_verified()` | `PUT /api/emails/{id}/verify` | Update verification result |
| `advance_to_ready()` | `PUT /api/emails/{id}/advance` | Move verified emails to ready |

---

## 7. Email Sender

**File:** `emailer/sender.py`

Gmail SMTP via `aiosmtplib` (async). Protected by double safety gates.

### Safety Gates

```mermaid
flowchart LR
    READY["Ready email"] --> G1{DRY_RUN?}

    G1 -->|true| LOG1["Log: would send<br/>Don't send"]
    G1 -->|false| G2{EMAIL_SENDING<br/>_ENABLED?}

    G2 -->|false| LOG2["Log: sending disabled<br/>Stay at 'ready'"]
    G2 -->|true| RATE{Within<br/>rate limits?}

    RATE -->|No| WAIT["Queue for later"]
    RATE -->|Yes| SEND["Send via SMTP"]
```

### Rate Limits & Warmup

| Week | Max per Day | Max per Hour | Delay Between |
|------|------------|-------------|---------------|
| 1 | 5 | 3 | 5-10 min |
| 2 | 8 | 5 | 3-7 min |
| 3 | 12 | 6 | 2-5 min |
| 4+ | 15 | 8 | 1-3 min |

### Email Features

| Feature | Detail |
|---------|--------|
| Format | Plain text + HTML |
| Attachment | Static resume PDF |
| Sender | Gmail with app password |
| Tracking | Status updated via API |
| Error handling | Retry count, last error stored |
