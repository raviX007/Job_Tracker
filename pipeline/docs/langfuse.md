# Langfuse Integration

How the pipeline uses [Langfuse](https://langfuse.com) for prompt management and LLM tracing.

---

## What Langfuse Does Here

Two things:

1. **Prompt Management** — Store prompt templates in Langfuse's UI. Edit them without code changes. Version history, A/B testing, rollback.
2. **Tracing** — Every LLM call is logged to Langfuse automatically. See inputs, outputs, tokens, latency, cost — per job, per run.

Langfuse is **required** for the main pipeline prompts. All prompts are stored in Langfuse — there are no hardcoded fallbacks in the codebase. If Langfuse is unavailable, affected LLM calls return `None` and the pipeline skips those jobs gracefully.

---

## Setup

### 1. Get Langfuse Keys

Sign up at [cloud.langfuse.com](https://cloud.langfuse.com) (free tier). Create a project. Copy the keys from Settings → API Keys.

### 2. Add to `.env`

```bash
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 3. Push Prompts

```bash
python scripts/push_prompts.py
```

This uploads 3 prompt templates to Langfuse:
- `job-analysis` — candidate-JD scoring
- `cold-email` — outreach email generation
- `cover-letter` — cover letter generation

Each prompt is a **chat prompt** (system + user messages) with `{{variable}}` placeholders and a config block (model, temperature, max_tokens).

### 4. Verify

Open [cloud.langfuse.com](https://cloud.langfuse.com) → Prompts. You should see all 3 prompts with the `production` label.

---

## How It Works

### Prompt Management Flow

```
Pipeline starts
    │
    ├─ Fetch "job-analysis" prompt from Langfuse (cached 5 min)
    │   ├─ Found → compile with variables → use Langfuse system + user prompts
    │   └─ Failed → log error, return None → pipeline skips this job
    │
    ├─ Call OpenAI with system + user prompts
    │
    └─ Return result
```

**In code** ([analyzer/llm_analyzer.py](../analyzer/llm_analyzer.py)):

```python
from core.langfuse_client import get_prompt_messages

def build_analysis_prompt(jd, profile):
    template_vars = _build_template_vars(jd, profile)

    result = get_prompt_messages("job-analysis", template_vars)
    if not result:
        logger.error("Failed to fetch 'job-analysis' prompt from Langfuse")
        return None

    system_prompt, user_prompt, config = result
    return system_prompt, user_prompt, config or default_config
```

All three modules (`llm_analyzer.py`, `cold_email.py`, `cover_letter.py`) follow this same pattern — fetch from Langfuse, return `None` on failure.

### What `get_prompt_messages()` Does

1. Calls `langfuse.get_prompt("job-analysis", type="chat", cache_ttl_seconds=300)`
2. Calls `prompt.compile(**variables)` — replaces `{{name}}` with actual values
3. Extracts system and user content from compiled messages
4. Returns `(system_content, user_content, config)` — or `None` if anything fails

Config includes `temperature`, `max_tokens`, `model` — stored alongside the prompt in Langfuse. Changing temperature in the Langfuse UI takes effect within 5 minutes.

### Tracing Flow

```
Pipeline starts
    │
    ├─ OpenAI client is Langfuse-wrapped (auto-traces every call)
    │   └─ from langfuse.openai import AsyncOpenAI  ← drop-in replacement
    │
    ├─ @observe decorator groups related calls into traces
    │   └─ analyze_job() → one trace with the OpenAI call nested inside
    │
    ├─ Pipeline finishes
    │
    └─ flush() → sends all buffered traces to Langfuse
```

**Auto-tracing** ([core/llm.py](../core/llm.py)):

```python
# This import is the only change needed for tracing
from langfuse.openai import AsyncOpenAI   # instead of: from openai import AsyncOpenAI

# Every chat.completions.create() call is now auto-logged
response = await self.openai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages,
    name="job-analysis",       # ← shows up as generation name in Langfuse
)
```

The `name` parameter tags each generation so you can filter by prompt type in the Langfuse dashboard.

**Function-level tracing** ([analyzer/llm_analyzer.py](../analyzer/llm_analyzer.py)):

```python
from core.langfuse_client import observe

@observe(name="job-analysis")
async def analyze_job(jd, profile):
    ...
```

The `@observe` decorator creates a **trace span** that wraps the entire function. The auto-traced OpenAI call inside becomes a child span. Trace names match prompt names for easy correlation. In Langfuse, you see:

```
trace: job-analysis
  └─ generation: job-analysis (OpenAI gpt-4o-mini)
       ├─ input: system + user messages
       ├─ output: JSON response
       ├─ tokens: 1247 in, 342 out
       ├─ latency: 2.1s
       └─ cost: $0.0008
```

**Flushing** ([scripts/dry_run.py](../scripts/dry_run.py)):

```python
from core.langfuse_client import flush

async def main():
    # ... run pipeline ...
    flush()   # ← send all buffered traces before process exits
```

Langfuse batches traces for efficiency. `flush()` at the end ensures nothing is lost when the process exits.

---

## Failure Behavior

Langfuse is required for prompts but the pipeline doesn't crash if it's unavailable:

| Component | If Langfuse Available | If Langfuse Unavailable |
|-----------|----------------------|------------------------|
| `get_prompt_messages()` | Returns Langfuse prompt + config | Returns `None` → caller skips that job/email |
| `from langfuse.openai import AsyncOpenAI` | Auto-traces OpenAI calls | Falls back to `from openai import AsyncOpenAI` |
| `@observe` decorator | Creates trace spans | No-op decorator (function runs normally) |
| `flush()` | Sends buffered traces | Does nothing |

**What happens in practice:** If Langfuse is down, the pipeline logs errors for each prompt fetch failure and skips affected jobs. It won't crash, but it won't analyze or generate emails either. Make sure Langfuse keys are configured correctly.

---

## 3 Managed Prompts

### job-analysis

| Field | Value |
|-------|-------|
| Type | chat (system + user) |
| Config | temp=0.2, max_tokens=1500, json mode |
| Variables | `name`, `degree`, `graduation_year`, `location`, `years`, `gap_explanation`, `skills_text`, `frameworks_text`, `work_history_text`, `projects_text`, `dream_companies`, `jd` |
| Used in | [analyzer/llm_analyzer.py](../analyzer/llm_analyzer.py) |

### cold-email

| Field | Value |
|-------|-------|
| Type | chat (system + user) |
| Config | temp=0.4, max_tokens=600, json mode |
| Variables | `candidate_name`, `company`, `allowed_companies`, `all_skills`, `years`, `graduation_year`, `title`, `recipient_name`, `recipient_role`, `matching_skills`, `cold_email_angle`, `gap_framing`, `project_highlights`, `primary_skills`, `upwork_info`, `recipient_greeting` |
| Used in | [emailer/cold_email.py](../emailer/cold_email.py) |

### cover-letter

| Field | Value |
|-------|-------|
| Type | chat (system + user) |
| Config | temp=0.4, max_tokens=500 |
| Variables | `candidate_name`, `allowed_companies`, `all_skills`, `degree`, `graduation_year`, `years`, `ats_keywords`, `title`, `company`, `matching_skills`, `gap_framing`, `work_context`, `project_context`, `gap_explanation` |
| Used in | [emailer/cover_letter.py](../emailer/cover_letter.py) |

### Startup Prompts (not in Langfuse)

The startup scout pipeline (`scripts/_startup_analyzer.py`) uses two additional prompts that are **hardcoded in the script**, not managed in Langfuse:
- `startup-relevance` — relevance scoring + profile extraction
- `startup-cold-email` — founder outreach email generation

These are traced via `@observe` but their prompt text lives in the Python file. To manage them in Langfuse, add them to `scripts/push_prompts.py` and update `_startup_analyzer.py` to fetch via `get_prompt_messages()`.

---

## Editing Prompts

### In Langfuse UI (recommended)

1. Go to [cloud.langfuse.com](https://cloud.langfuse.com) → Prompts
2. Click on a prompt (e.g. `job-analysis`)
3. Edit the system or user message
4. Click "Save as new version" — old version is preserved
5. The `production` label auto-attaches to the latest version
6. Pipeline picks up the new version within 5 minutes (cache TTL)

No code changes. No redeployment.

### Re-pushing from Code

If you want to push a completely new version from code:

```bash
# Edit the prompt strings in scripts/push_prompts.py
# Then push:
python scripts/push_prompts.py
```

This creates a new version — old versions stay in Langfuse history.

---

## Viewing Traces

### Langfuse Dashboard

Go to [cloud.langfuse.com](https://cloud.langfuse.com) → Traces. You'll see:

- **Every LLM call** with full input/output
- **Token counts** (input + output) per call
- **Latency** per call
- **Cost estimate** per call and total
- **Trace hierarchy** — function span → OpenAI generation nested inside

### Filtering

- By name: `job-analysis`, `cold-email`, `cover-letter`, `startup-relevance`, `startup-cold-email`
- By date range
- By latency (find slow calls)
- By token count (find expensive calls)

### What to Look For

| Signal | What It Means | Action |
|--------|--------------|--------|
| High token count on input | JD text is too long | Check if `jd[:3000]` truncation is working |
| High output tokens | LLM is writing too much | Tighten max_tokens or add word limit to prompt |
| Score inconsistency | Same-ish jobs getting wildly different scores | Lower temperature, add more rubric detail |
| Hallucinated companies | Output mentions companies not in profile | Strengthen anti-hallucination rules in prompt |
| Generic cold emails | "Dear Sir/Madam" appearing | Add better examples or explicit ban list |

---

## Files

| File | Role |
|------|------|
| [core/langfuse_client.py](../core/langfuse_client.py) | Client initialization, `get_prompt_messages()`, `observe`, `flush()` |
| [core/llm.py](../core/llm.py) | Langfuse-wrapped OpenAI client (auto-tracing) |
| [scripts/push_prompts.py](../scripts/push_prompts.py) | Push all 3 prompts to Langfuse |
| [analyzer/llm_analyzer.py](../analyzer/llm_analyzer.py) | Uses `job-analysis` prompt from Langfuse |
| [emailer/cold_email.py](../emailer/cold_email.py) | Uses `cold-email` prompt from Langfuse |
| [emailer/cover_letter.py](../emailer/cover_letter.py) | Uses `cover-letter` prompt from Langfuse |
| [scripts/_startup_analyzer.py](../scripts/_startup_analyzer.py) | Startup prompts (hardcoded, traced but not Langfuse-managed) |
| [scripts/dry_run.py](../scripts/dry_run.py) | Calls `flush()` at end of pipeline run |

---

## Cost

Langfuse cloud free tier: 50k observations/month. A typical pipeline run with 20 jobs = ~20 traces (one per LLM call). Daily runs use ~600/month — well within free tier.

OpenAI costs are tracked per-trace in Langfuse. Filter by date range to see daily/weekly/monthly spend.
