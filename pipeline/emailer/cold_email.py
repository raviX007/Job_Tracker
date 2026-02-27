"""Cold email generator — personalized outreach emails per JD.

Generates subject line + body (plain + HTML) tailored to each job.
Includes unsubscribe line, sender signature, and anti-hallucination rules.
Max 200 words body.

Fetches prompt from Langfuse ("cold-email") at runtime.
Prompt managed in Langfuse — edit via Langfuse UI, push via scripts/push_prompts.py.
"""

from core.langfuse_client import get_prompt_messages, observe
from core.llm import get_llm_client
from core.logger import logger
from core.models import ProfileConfig
from core.utils import plain_to_html


@observe(name="cold-email")
async def generate_cold_email(
    job: dict,
    analysis: dict,
    profile: ProfileConfig,
    recipient_name: str = "",
    recipient_role: str = "",
) -> dict | None:
    """Generate a personalized cold email for a job.

    Returns dict with: subject, body_plain, body_html, or None if failed.
    """
    title = job.get("title", "the role")
    company = job.get("company", "your company")
    matching_skills = analysis.get("matching_skills", [])
    cold_email_angle = analysis.get("cold_email_angle", "")
    gap_framing = analysis.get("gap_framing_for_this_role", "")

    # Build project highlights
    project_highlights = ""
    for proj in profile.experience.gap_projects[:2]:
        project_highlights += f"- {proj.name}"
        if proj.tech:
            project_highlights += f" ({', '.join(proj.tech[:3])})"
        project_highlights += "\n"

    recipient_greeting = f"Hi {recipient_name}," if recipient_name else "Hi,"
    upwork_info = f"Upwork: {profile.experience.work_history[-1].rating}" if profile.experience.work_history and profile.experience.work_history[-1].rating else ""

    # Template variables for Langfuse
    template_vars = {
        "candidate_name": profile.candidate.name,
        "company": company,
        "allowed_companies": ", ".join(profile.anti_hallucination.allowed_companies),
        "all_skills": ", ".join(profile.skills.primary + profile.skills.secondary),
        "years": str(profile.experience.years),
        "graduation_year": str(profile.experience.graduation_year),
        "title": title,
        "recipient_name": recipient_name,
        "recipient_role": recipient_role,
        "matching_skills": ", ".join(matching_skills),
        "cold_email_angle": cold_email_angle,
        "gap_framing": gap_framing,
        "project_highlights": project_highlights,
        "primary_skills": ", ".join(profile.skills.primary[:4]),
        "upwork_info": upwork_info,
        "recipient_greeting": recipient_greeting,
    }

    default_config = {"temperature": 0.4, "max_tokens": 600, "response_format": "json"}

    langfuse_result = get_prompt_messages("cold-email", template_vars)
    if not langfuse_result:
        logger.error("Failed to fetch 'cold-email' prompt from Langfuse")
        return None

    system_prompt, user_prompt, config = langfuse_result
    config = config or default_config

    llm = await get_llm_client()
    result = await llm.call_json(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=config.get("temperature", 0.4),
        max_tokens=config.get("max_tokens", 600),
        name="cold-email",
    )

    if not result or "subject" not in result or "body" not in result:
        logger.warning(f"Cold email generation failed for {title} at {company}")
        return None

    subject = result["subject"].strip()
    body_plain = result["body"].strip()

    # Add resume mention
    body_plain += "\n\nPlease find my resume attached for your reference."

    # Add signature
    signature = profile.cold_email.signature.strip()
    if signature:
        body_plain += f"\n\n{signature}"

    # Add unsubscribe line if configured
    if profile.cold_email.include_unsubscribe:
        body_plain += "\n\n---\nIf this isn't relevant, just let me know and I won't follow up."

    # Generate HTML version
    body_html = plain_to_html(body_plain)

    logger.info(f"Cold email generated for {title} at {company} (subject: {subject[:50]})")

    return {
        "subject": subject,
        "body_plain": body_plain,
        "body_html": body_html,
    }


