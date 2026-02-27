"""Startup-specific LLM analysis and cold email generation.

Unlike the main job pipeline (which analyzes formal JDs), this module:
1. Does a lightweight relevance check — "Would this startup benefit from this developer?"
2. Generates founder-to-developer cold emails (peer tone, not applicant-to-HR)

Prompts are fetched from Langfuse at runtime. Falls back to hardcoded prompts
if Langfuse is unavailable (see push_prompts.py for the canonical versions).
"""

from core.constants import SOURCE_DISPLAY_NAMES, STARTUP_DESC_TRUNCATE, STARTUP_EMAIL_MAX_WORDS
from core.langfuse_client import get_prompt_messages, observe
from core.llm import get_llm_client
from core.logger import logger
from core.models import ProfileConfig
from core.utils import plain_to_html


def _build_relevance_variables(startup: dict, profile: ProfileConfig) -> dict:
    """Build template variables for the startup-relevance prompt."""
    all_skills = profile.skills.primary + profile.skills.secondary
    if profile.skills.frameworks:
        all_skills += profile.skills.frameworks
    skills_text = ", ".join(all_skills)

    projects_text = ""
    for proj in profile.experience.gap_projects[:2]:
        projects_text += f"- {proj.name}"
        if proj.tech:
            projects_text += f" ({', '.join(proj.tech[:3])})"
        projects_text += "\n"

    return {
        "name": profile.candidate.name,
        "degree": profile.experience.degree,
        "graduation_year": str(profile.experience.graduation_year),
        "skills_text": skills_text,
        "years": str(profile.experience.years),
        "projects_text": projects_text,
        "company": startup.get("company", "Unknown"),
        "source": startup.get("source", "unknown"),
        "description": startup.get("description", "")[:STARTUP_DESC_TRUNCATE],
        "job_url": startup.get("job_url", ""),
    }


def _build_cold_email_variables(
    startup: dict,
    analysis: dict,
    profile: ProfileConfig,
    startup_profile: dict | None = None,
    recipient_name: str = "",
    recipient_role: str = "",
) -> dict:
    """Build template variables for the startup-cold-email prompt."""
    company = startup.get("company", "your company")
    source = startup.get("source", "")
    description = startup.get("description", "")[:1000]
    cold_email_angle = analysis.get("cold_email_angle", "")

    source_display = SOURCE_DISPLAY_NAMES.get(source, source)

    # Build project highlights
    project_highlights = ""
    for proj in profile.experience.gap_projects[:2]:
        project_highlights += f"- {proj.name}"
        if proj.tech:
            project_highlights += f" ({', '.join(proj.tech[:3])})"
        project_highlights += "\n"

    recipient_greeting = f"Hi {recipient_name}," if recipient_name else "Hi,"
    upwork_info = ""
    if profile.experience.work_history and profile.experience.work_history[-1].rating:
        upwork_info = f"Upwork: {profile.experience.work_history[-1].rating}"

    github = profile.candidate.github or ""

    all_skills = profile.skills.primary + profile.skills.secondary
    skills_text = ", ".join(all_skills)

    # Build startup context from profile data
    startup_context = ""
    if startup_profile:
        if startup_profile.get("funding_round") and startup_profile["funding_round"] != "unknown":
            startup_context += f"\n- Funding: {startup_profile['funding_round']}"
            if startup_profile.get("funding_amount"):
                startup_context += f" ({startup_profile['funding_amount']})"
        if startup_profile.get("employee_count"):
            startup_context += f"\n- Team size: {startup_profile['employee_count']} people"
        if startup_profile.get("tech_stack"):
            startup_context += f"\n- Tech stack: {', '.join(startup_profile['tech_stack'])}"
        if startup_profile.get("has_customers"):
            startup_context += "\n- Has customers: Yes"
        if startup_profile.get("yc_batch"):
            startup_context += f"\n- YC Batch: {startup_profile['yc_batch']}"
        if startup_profile.get("age_months") is not None:
            startup_context += f"\n- Age: {startup_profile['age_months']} months"

    return {
        "name": profile.candidate.name,
        "source_display": source_display,
        "allowed_companies": ", ".join(profile.anti_hallucination.allowed_companies),
        "skills_text": skills_text,
        "years": str(profile.experience.years),
        "graduation_year": str(profile.experience.graduation_year),
        "company": company,
        "description": description,
        "startup_context": startup_context or "N/A",
        "recipient_name": recipient_name,
        "recipient_role": recipient_role,
        "cold_email_angle": cold_email_angle,
        "project_highlights": project_highlights,
        "github": github,
        "upwork_info": upwork_info,
        "recipient_greeting": recipient_greeting,
    }


# ─── Hardcoded Fallback Prompts ──────────────────────────────────────────────
# Used only when Langfuse is unavailable. Canonical versions live in Langfuse
# (pushed via push_prompts.py). Keep these in sync.

_RELEVANCE_SYSTEM_FALLBACK = """You are evaluating an early-stage startup for a developer outreach campaign.

CANDIDATE: {name}, {degree} ({graduation_year})
SKILLS: {skills_text}
EXPERIENCE: {years} years + self-directed AI/ML projects

YOUR TASKS:
1. Assess relevance: Would this startup benefit from hiring this developer?
2. Extract structured metadata about the startup from the description.
3. Generate a specific cold email angle.

RELEVANCE RULES:
1. Be generous — startups with <10 people almost always need developers
2. Focus on skill overlap: does the startup's tech/product area match the candidate's skills?
3. Generate a SPECIFIC cold email angle (not generic "I'm interested")
4. Score 0-100 based on tech relevance and potential impact
5. If the startup clearly has nothing to do with tech, mark as not relevant

SKILL MATCHING RULES (CRITICAL):
- The COMPLETE list of candidate skills is provided above in SKILLS.
- "matching_skills": list skills from the SKILLS list above that are relevant to this startup's tech/product.
- "missing_skills": ONLY list skills the startup needs that are NOT in the SKILLS list above.
- Do NOT mark a skill as missing if it appears anywhere in the candidate's SKILLS list.

EXTRACTION RULES:
1. Extract ONLY what is explicitly stated or strongly implied. Do NOT fabricate.
2. For founding_date: look for "founded in", launch dates. If YC batch "W25" → ~2025-01-15, "S24" → ~2024-06-15.
3. For funding: look for "$Xm raised", "seed round", "pre-seed". If YC batch mentioned → at minimum "pre_seed".
4. For employee_count: look for "team of X", "X employees", "we're X people". Leave null if not stated.
5. For has_customers: look for "customers", "users", "revenue", "ARR", "clients", "paying". True if evidence found.
6. For tech_stack: infer from description ("built with React" → ["React"]). Also infer from product type.
7. For founders: look for signatures, "I'm [name]", "Founder: [name]", maker names.

Return ONLY valid JSON."""

_RELEVANCE_USER_FALLBACK = """STARTUP: {company}
SOURCE: {source}
DESCRIPTION:
{description}
WEBSITE: {job_url}

CANDIDATE PROJECTS:
{projects_text}

Return JSON with keys: relevant, match_score, relevance_reason, cold_email_angle,
founder_name, founder_role, apply_decision, matching_skills, missing_skills,
company_type, gap_tolerant, gap_framing_for_this_role, startup_profile (nested object)."""

_COLD_EMAIL_SYSTEM_FALLBACK = """You are writing a cold email from {name} to the founder/CTO of an early-stage startup.

CRITICAL: This is NOT a job application to HR. This is developer-to-founder outreach.
The startup was found on {source_display} and may not have formal job postings.

TONE:
- Peer-to-peer, respectful but confident
- Brief, specific, no fluff
- Show you understand their product/problem
- Mention 1-2 specific things you could build/improve for them

STRICT RULES:
1. Maximum {max_words} words body (founders are busy)
2. ONLY mention companies from: {allowed_companies}
3. ONLY mention skills the candidate has: {skills_text}
4. NEVER fabricate experience or credentials
5. {years} years experience, graduated {graduation_year}
6. Reference {source_display} as how you found them
7. Include a specific ask (15-min call or trial project)
8. Subject line: short, specific, mentions their company name (max 60 chars)

Return ONLY valid JSON: {{"subject": "...", "body": "..."}}
Body starts with greeting, ends BEFORE signature (signature appended automatically)."""

_COLD_EMAIL_USER_FALLBACK = """STARTUP: {company}
FOUND ON: {source_display}
WHAT THEY DO: {description}
STARTUP DETAILS: {startup_context}
RECIPIENT: {recipient_name} ({recipient_role})
COLD EMAIL ANGLE: {cold_email_angle}

CANDIDATE HIGHLIGHTS:
- Key skills: {skills_text}
- Recent projects:
{project_highlights}- GitHub: {github}
{upwork_info}

Write the cold email as JSON: {{"subject": "...", "body": "..."}}
Body starts with "{recipient_greeting}" """


# ─── Main Functions ──────────────────────────────────────────────────────────


@observe(name="startup-relevance")
async def analyze_startup_relevance(startup: dict, profile: ProfileConfig) -> dict | None:
    """Lightweight LLM analysis — is this startup relevant for this developer?

    Returns analysis dict or None if failed/irrelevant.
    """
    company = startup.get("company", "Unknown")
    variables = _build_relevance_variables(startup, profile)

    # Try Langfuse first, fall back to hardcoded
    result = get_prompt_messages("startup-relevance", variables)
    if result:
        system_prompt, user_prompt, config = result
    else:
        system_prompt = _RELEVANCE_SYSTEM_FALLBACK.format(**variables)
        user_prompt = _RELEVANCE_USER_FALLBACK.format(**variables)
        config = {}

    llm = await get_llm_client()
    analysis = await llm.call_json(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=config.get("temperature", 0.3),
        max_tokens=config.get("max_tokens", 1200),
        name="startup-relevance",
    )

    if not analysis:
        logger.warning(f"Startup analysis failed for {company}")
        return None

    if not analysis.get("relevant", False):
        logger.info(f"Startup '{company}' not relevant: {analysis.get('relevance_reason', 'N/A')}")
        return None

    logger.info(f"Startup '{company}' → score={analysis.get('match_score', 0)}, "
                f"decision={analysis.get('apply_decision', '?')}")
    return analysis


@observe(name="startup-cold-email")
async def generate_startup_cold_email(
    startup: dict,
    analysis: dict,
    profile: ProfileConfig,
    startup_profile: dict | None = None,
    recipient_name: str = "",
    recipient_role: str = "",
) -> dict | None:
    """Generate a cold email for startup founder outreach.

    Different from standard cold_email.py:
    - No formal JD to reference
    - Target is founder/CTO, not HR
    - Peer-to-peer tone
    - References how the candidate found them (HN, YC, PH)
    - Focus on "I can help build" rather than "I want to apply"
    """
    company = startup.get("company", "your company")
    variables = _build_cold_email_variables(
        startup, analysis, profile, startup_profile,
        recipient_name, recipient_role,
    )

    # Try Langfuse first, fall back to hardcoded
    result = get_prompt_messages("startup-cold-email", variables)
    if result:
        system_prompt, user_prompt, config = result
    else:
        fallback_vars = {**variables, "max_words": STARTUP_EMAIL_MAX_WORDS}
        system_prompt = _COLD_EMAIL_SYSTEM_FALLBACK.format(**fallback_vars)
        user_prompt = _COLD_EMAIL_USER_FALLBACK.format(**variables)
        config = {}

    llm = await get_llm_client()
    email_result = await llm.call_json(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=config.get("temperature", 0.4),
        max_tokens=config.get("max_tokens", 600),
        name="startup-cold-email",
    )

    if not email_result or "subject" not in email_result or "body" not in email_result:
        logger.warning(f"Startup cold email generation failed for {company}")
        return None

    subject = email_result["subject"].strip()
    body_plain = email_result["body"].strip()

    # Add resume mention
    body_plain += "\n\nPlease find my resume attached for your reference."

    # Add signature
    signature = profile.cold_email.signature.strip()
    if signature:
        body_plain += f"\n\n{signature}"

    # Add unsubscribe line
    if profile.cold_email.include_unsubscribe:
        body_plain += "\n\n---\nIf this isn't relevant, just let me know and I won't follow up."

    # Generate HTML version
    body_html = plain_to_html(body_plain)

    logger.info(f"Startup cold email generated for {company} (subject: {subject[:50]})")

    return {
        "subject": subject,
        "body_plain": body_plain,
        "body_html": body_html,
    }
