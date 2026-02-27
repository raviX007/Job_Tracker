# Prompt Engineering

How the pipeline's 3 LLM prompts are structured, why they work, and how to improve them.

---

## The 3 Prompts

| Prompt | Purpose | Output | Model Config |
|--------|---------|--------|-------------|
| `job-analysis` | Score candidate-JD fit | Structured JSON (score, skills, decision) | temp=0.2, max_tokens=1500, json mode |
| `cold-email` | Write outreach email | JSON (subject + body) | temp=0.4, max_tokens=600, json mode |
| `cover-letter` | Write cover letter | Plain text (150 words) | temp=0.4, max_tokens=500 |

Lower temperature (0.2) = more deterministic scoring. Higher temperature (0.4) = more creative writing.

---

## Anatomy of a Prompt

Every prompt has two parts — **system** and **user** — sent as separate messages to the LLM.

### System Prompt = Who You Are + Rules

Sets the LLM's persona, constraints, and output format. Stays the same across calls.

```
You are a job matching analyst. Analyze how well a candidate matches a job description.

CRITICAL RULES:
1. Only reference companies the candidate actually worked at
2. Only mention skills the candidate actually has
3. Don't fabricate experience or credentials
...

Return ONLY valid JSON with no markdown formatting.
```

**Why separate?** The system prompt is cached by most LLM providers. Keeping stable instructions here and variable data in the user prompt saves tokens and money.

### User Prompt = The Actual Input

Contains the variable data for this specific call — candidate profile, job description, recipient name, etc.

```
## CANDIDATE PROFILE
Name: Ravi Raj
Degree: B.Tech CSE (Graduated: 2023)
Location: Jamshedpur
...

## JOB DESCRIPTION
[actual JD text]
```

---

## Techniques Used in This Project

### 1. Role Assignment

**What:** First line tells the LLM who it is.

```
You are an expert job-matching analyst who evaluates candidate-JD fit
for the Indian tech job market.
```

**Why:** Activates domain-specific knowledge and sets tone. "Expert job-matching analyst" performs differently from "helpful assistant."

### 2. Step-by-Step Reasoning (Chain of Thought)

**What:** Tell the LLM to think before answering.

```
## STEP-BY-STEP REASONING (do this internally before scoring)
1. Extract all required skills from the JD
2. For each required skill, check if the candidate has it OR an equivalent
3. Count matching vs missing skills
4. Check experience level compatibility
...
```

**Why:** Without this, the LLM jumps to a score. With it, the model reasons through each factor, producing more accurate and consistent results. Especially important for scoring tasks.

### 3. Structured Output Format

**What:** Define the exact JSON schema you expect.

```
## REQUIRED JSON OUTPUT
{
    "match_score": <integer 0-100>,
    "required_skills": ["skill1", "skill2"],
    "matching_skills": ["skill1", "skill2"],
    ...
}
```

**Why:** Without an explicit schema, the LLM returns inconsistent keys, wrong types, or extra fields. The code parses this JSON directly — if the format drifts, the pipeline breaks.

**Reinforced by:** Using `response_format={"type": "json_object"}` in the API call, which guarantees valid JSON output.

### 4. Scoring Rubric

**What:** Explicit point values for each factor.

```
| Factor | Points |
|--------|--------|
| Each primary skill match | +15 |
| Each secondary skill match | +8 |
| Senior role (5+ years required) | -30 |
| Missing critical required skill | -15 per skill |
```

**Why:** Without a rubric, the LLM assigns arbitrary scores. A 75 from one call might be a 55 from the next. The rubric anchors scoring to measurable factors, making scores comparable across jobs.

### 5. Conceptual Matching Rules

**What:** Teach the LLM to match skills semantically, not literally.

```
## CONCEPTUAL MATCHING
- "Generative AI" → LangChain, LLM, RAG, OpenAI, AI Agents
- "REST APIs" → FastAPI, Django REST, Express.js
- "Cloud" → AWS, GCP, Azure, deployment experience
```

**Why:** JDs say "Generative AI experience required." Candidate profile says "LangChain, LangGraph, RAG." Without this rule, the LLM marks GenAI as missing. With it, the model correctly matches the concept. This single technique improved match scores from ~40% accuracy to ~85%.

### 6. Anti-Hallucination Guards

**What:** Explicit rules about what the LLM must NOT fabricate.

```
## ANTI-HALLUCINATION RULES
1. ONLY mention companies from this list: {{allowed_companies}}
2. ONLY mention skills the candidate actually has: {{all_skills}}
3. NEVER fabricate experience, credentials, client names
4. If years is 0, do NOT write "years of experience"
```

**Why:** LLMs hallucinate. Without guards, the cold email might say "In my 3 years at Google..." for a candidate who never worked at Google with 0 years of experience. By injecting the allowed companies list and skills list directly into the prompt, the model stays grounded.

**Validated by:** The pipeline's `emailer/validator.py` runs post-generation checks — if a forbidden company or skill appears, the email is flagged.

### 7. Few-Shot Examples (Good + Bad)

**What:** Show the LLM what correct output looks like, and what bad output looks like.

```
## GOOD EXAMPLE
{"subject": "Django + AI background — re: Backend Developer role",
 "body": "Hi Priya,\n\nI came across the Backend Developer role at Razorpay..."}

## BAD EXAMPLE (avoid this)
{"subject": "Job Application",
 "body": "Dear Sir/Madam,\n\nI am writing to express my interest..."}

Why it's bad: Generic opening, no specific role mention, ...
```

**Why:** Telling the LLM "be specific" is vague. Showing it a specific example anchors the style, length, and tone. The bad example with an explanation is equally powerful — it prevents the most common failure modes.

### 8. Self-Check Checklists

**What:** A verification checklist the LLM runs before returning.

```
## SELF-CHECK (verify before returning)
- [ ] Every skill in matching_skills exists in the candidate's profile
- [ ] missing_skills only contains skills with NO equivalent
- [ ] match_score is consistent with the reasoning
- [ ] cold_email_angle doesn't fabricate anything
```

**Why:** Acts as a second pass. The LLM reviews its own output against the checklist, catching errors it would otherwise miss. Measurably reduces hallucinations and inconsistent scoring.

### 9. Template Variables (`{{variable}}`)

**What:** Placeholders in the prompt text, filled at runtime.

```
Name: {{name}}
Degree: {{degree}} (Graduated: {{graduation_year}})
Skills: {{skills_text}}

JOB DESCRIPTION
{{jd}}
```

**Why:** Separates prompt structure from data. The same prompt template works for any candidate and any job. Langfuse manages the templates; the pipeline fills in variables at call time.

---

## Why These Techniques Matter

| Problem | Without Technique | With Technique |
|---------|-------------------|----------------|
| Inconsistent scoring | Same job gets 45 one run, 72 next | Rubric anchors scores to measurable factors |
| Missed skill matches | "GenAI" marked missing despite having LangChain | Conceptual matching catches semantic equivalents |
| Hallucinated experience | "3 years at Google" for someone who never worked there | Anti-hallucination rules + allowed company list |
| Generic cold emails | "Dear Sir/Madam, I am writing to express my interest..." | Good/bad examples anchor tone and specificity |
| Rambling cover letters | 400-word essays with skill dumping | Word limit + format template + self-check |
| Score not matching reasoning | "Strong match" but score is 38 | Chain-of-thought reasoning + self-check |

---

## How to Improve a Prompt

### 1. Read the failures first

Run the pipeline and look at outputs that are wrong — bad scores, hallucinated content, generic emails. The failure mode tells you what to fix.

### 2. Add a rule, not a paragraph

If the LLM keeps using "Dear Sir/Madam":

```
# Bad fix (vague)
"Write in a professional but casual tone appropriate for modern business communication"

# Good fix (specific)
"NEVER use 'Dear Sir/Madam', 'esteemed organization', or 'express my interest'. Start with 'Hi [Name],' or 'Hi,'"
```

### 3. Add examples when rules aren't enough

If the LLM understands the rule but produces mediocre output, add a concrete example of what good looks like. Examples are worth more than paragraphs of instructions.

### 4. Test with edge cases

Run the same prompt against:
- A job that's a perfect match (should score 80+)
- A job that's completely wrong domain (should score <30)
- A senior role (should get -30 penalty)
- A dream company (should be MANUAL regardless of score)

### 5. Edit in Langfuse, not in code

Once prompts are pushed to Langfuse, edit them in the [Langfuse UI](https://cloud.langfuse.com). Changes take effect within 5 minutes (cache TTL). No code changes, no redeployment.

---

## Temperature Guide

| Value | Behavior | Use For |
|-------|----------|---------|
| 0.0-0.2 | Near-deterministic, consistent | Scoring, classification, structured extraction |
| 0.3-0.5 | Slightly creative, still focused | Writing with constraints (emails, cover letters) |
| 0.6-0.8 | Creative, more variation | Open-ended writing, brainstorming |
| 0.9-1.0 | Highly random | Not recommended for production |

This project uses **0.2** for analysis (consistency matters) and **0.4** for writing (creative but not wild).

---

## Common Pitfalls

| Pitfall | Example | Fix |
|---------|---------|-----|
| Vague instructions | "Write a good email" | Be specific: "Max 200 words, start with the role name, include one project detail" |
| No output format | "Analyze this job" | Define exact JSON schema with types and field descriptions |
| Trusting the LLM | Assume scores are always correct | Validate in code: clamp 0-100, check required fields, verify allowed values |
| Prompt too long | 2000-word system prompt | Keep rules tight. If you need examples, use 1 good + 1 bad, not 5. |
| No error handling | Crash if prompt fetch fails | Return `None` gracefully, let the pipeline skip the job |

---

## Files

| File | What It Does |
|------|-------------|
| `analyzer/llm_analyzer.py` | Uses `job-analysis` prompt from Langfuse |
| `emailer/cold_email.py` | Uses `cold-email` prompt from Langfuse |
| `emailer/cover_letter.py` | Uses `cover-letter` prompt from Langfuse |
| `scripts/push_prompts.py` | All 3 prompts pushed to Langfuse |
| `scripts/_startup_analyzer.py` | Startup prompts (hardcoded, not in Langfuse) |
| `emailer/validator.py` | Post-generation anti-hallucination checks |
