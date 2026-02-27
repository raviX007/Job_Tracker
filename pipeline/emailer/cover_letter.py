"""Cover letter generator — LLM-powered, gap-aware, ATS-optimized.

Generates concise (150 words max) cover letters personalized per JD.
Uses the candidate profile, LLM analysis results, and ATS keywords.

Fetches prompt from Langfuse ("cover-letter") at runtime.
Prompt managed in Langfuse — edit via Langfuse UI, push via scripts/push_prompts.py.
"""

from core.langfuse_client import get_prompt_messages, observe
from core.llm import get_llm_client
from core.logger import logger
from core.models import ProfileConfig


@observe(name="cover-letter")
async def generate_cover_letter(
    job: dict,
    analysis: dict,
    profile: ProfileConfig,
) -> str | None:
    """Generate a personalized cover letter for a job.

    Args:
        job: Job dict with title, company, description
        analysis: LLM analysis dict with matching_skills, gap_framing, etc.
        profile: Candidate profile

    Returns:
        Cover letter text (plain text), or None if generation fails.
    """
    title = job.get("title", "the role")
    company = job.get("company", "your company")
    matching_skills = analysis.get("matching_skills", [])
    ats_keywords = analysis.get("ats_keywords", [])
    gap_framing = analysis.get("gap_framing_for_this_role", "")

    # Build work history context
    work_context = ""
    for wh in profile.experience.work_history:
        work_context += f"- {wh.role} at {wh.company} ({wh.duration})"
        if wh.description:
            work_context += f": {wh.description}"
        work_context += "\n"

    # Build project context
    project_context = ""
    for proj in profile.experience.gap_projects:
        project_context += f"- {proj.name}"
        if proj.description:
            project_context += f": {proj.description}"
        project_context += "\n"

    # Template variables for Langfuse
    template_vars = {
        "candidate_name": profile.candidate.name,
        "allowed_companies": ", ".join(profile.anti_hallucination.allowed_companies),
        "all_skills": ", ".join(profile.skills.primary + profile.skills.secondary),
        "degree": profile.experience.degree,
        "graduation_year": str(profile.experience.graduation_year),
        "years": str(profile.experience.years),
        "ats_keywords": ", ".join(ats_keywords[:5]),
        "title": title,
        "company": company,
        "matching_skills": ", ".join(matching_skills),
        "gap_framing": gap_framing,
        "work_context": work_context,
        "project_context": project_context,
        "gap_explanation": profile.experience.gap_explanation,
    }

    default_config = {"temperature": 0.4, "max_tokens": 500}

    langfuse_result = get_prompt_messages("cover-letter", template_vars)
    if not langfuse_result:
        logger.error("Failed to fetch 'cover-letter' prompt from Langfuse")
        return None

    system_prompt, user_prompt, config = langfuse_result
    config = config or default_config

    llm = await get_llm_client()
    result = await llm.call(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=config.get("temperature", 0.4),
        max_tokens=config.get("max_tokens", 500),
        name="cover-letter",
    )

    if not result:
        logger.warning(f"Cover letter generation failed for {title} at {company}")
        return None

    # Basic word count check
    word_count = len(result.split())
    if word_count > 200:
        logger.warning(f"Cover letter too long ({word_count} words), truncating")
        words = result.split()[:180]
        # Find last complete sentence
        text = " ".join(words)
        last_period = text.rfind(".")
        if last_period > 100:
            result = text[:last_period + 1]
        result += f"\n\nBest regards,\n{profile.candidate.name}"

    logger.info(f"Cover letter generated for {title} at {company} ({len(result.split())} words)")
    return result.strip()
