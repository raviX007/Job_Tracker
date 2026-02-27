"""LLM Analyzer — deep job analysis with GPT-4o-mini.

Stage 2 filter: only called for jobs that pass the embedding filter.
Returns structured JSON with match_score, skills analysis, gap framing,
cold email angle, and apply decision.

Fetches prompt from Langfuse ("job-analysis") at runtime.
Prompt managed in Langfuse — edit via Langfuse UI, push via scripts/push_prompts.py.
"""


from core.langfuse_client import get_prompt_messages, observe
from core.llm import get_llm_client
from core.logger import logger
from core.models import ProfileConfig


def _build_template_vars(jd: str, profile: ProfileConfig) -> dict:
    """Build all template variables for the job-analysis prompt."""
    skills_text = ", ".join(profile.skills.primary + profile.skills.secondary)
    frameworks_text = ", ".join(profile.skills.frameworks) if profile.skills.frameworks else "None"

    work_history_text = ""
    for wh in profile.experience.work_history:
        work_history_text += f"- {wh.role} at {wh.company} ({wh.duration})"
        if wh.tech:
            work_history_text += f" [{', '.join(wh.tech)}]"
        if wh.description:
            work_history_text += f"\n  {wh.description}"
        work_history_text += "\n"
        for proj in wh.projects:
            work_history_text += f"  - {proj.name}"
            if proj.description:
                work_history_text += f": {proj.description}"
            work_history_text += "\n"

    projects_text = ""
    for proj in profile.experience.gap_projects:
        projects_text += f"- {proj.name}"
        if proj.tech:
            projects_text += f" [{', '.join(proj.tech)}]"
        if proj.description:
            projects_text += f": {proj.description}"
        projects_text += "\n"

    return {
        "name": profile.candidate.name,
        "degree": profile.experience.degree,
        "graduation_year": str(profile.experience.graduation_year),
        "location": profile.candidate.location,
        "years": str(profile.experience.years),
        "gap_explanation": profile.experience.gap_explanation,
        "skills_text": skills_text,
        "frameworks_text": frameworks_text,
        "work_history_text": work_history_text,
        "projects_text": projects_text,
        "dream_companies": ", ".join(profile.dream_companies[:5]) if profile.dream_companies else "None specified",
        "jd": jd[:3000],
    }


def build_analysis_prompt(jd: str, profile: ProfileConfig) -> tuple[str, str, dict] | None:
    """Build the system prompt and user prompt for JD analysis.

    Fetches prompt from Langfuse ("job-analysis").
    Returns: (system_prompt, user_prompt, config) or None if unavailable.
    """
    template_vars = _build_template_vars(jd, profile)
    default_config = {"temperature": 0.2, "max_tokens": 1500, "response_format": "json"}

    result = get_prompt_messages("job-analysis", template_vars)
    if not result:
        logger.error("Failed to fetch 'job-analysis' prompt from Langfuse")
        return None

    system_prompt, user_prompt, config = result
    return system_prompt, user_prompt, config or default_config


@observe(name="job-analysis")
async def analyze_job(jd: str, profile: ProfileConfig) -> dict | None:
    """Run LLM analysis on a job description.

    Returns the structured analysis dict, or None if the LLM call fails.
    """
    prompt_result = build_analysis_prompt(jd, profile)
    if not prompt_result:
        return None
    system_prompt, user_prompt, config = prompt_result
    llm = await get_llm_client()

    result = await llm.call_json(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=config.get("temperature", 0.2),
        max_tokens=config.get("max_tokens", 1500),
        name="job-analysis",
    )

    if not result:
        logger.warning("LLM analysis returned no result")
        return None

    # Validate required fields
    required_fields = [
        "match_score", "required_skills", "matching_skills",
        "missing_skills", "apply_decision",
    ]
    for field in required_fields:
        if field not in result:
            logger.warning(f"LLM analysis missing required field: {field}")
            return None

    # Clamp match_score to 0-100
    try:
        result["match_score"] = max(0, min(100, int(result["match_score"])))
    except (ValueError, TypeError):
        result["match_score"] = 0

    # Normalize apply_decision
    decision = str(result.get("apply_decision", "")).upper()
    if decision not in ("YES", "NO", "MAYBE", "MANUAL"):
        decision = "MAYBE"
    result["apply_decision"] = decision

    return result


def apply_decision_from_score(
    score: int,
    profile: ProfileConfig,
    is_dream_company: bool = False,
) -> str:
    """Determine apply decision based on score and profile thresholds.

    Overrides LLM decision if needed (e.g., dream companies get MANUAL review).
    """
    if is_dream_company:
        return "MANUAL"  # Always human review for dream companies

    if score >= profile.filters.auto_apply_threshold:
        return "YES"
    elif score >= profile.filters.min_match_score:
        return "MAYBE"
    else:
        return "NO"


async def analyze_jobs_batch(
    jobs: list[dict],
    profile: ProfileConfig,
) -> list[dict]:
    """Analyze a batch of jobs with the LLM.

    Adds analysis results to each job dict. Skips jobs where analysis fails.
    Returns only successfully analyzed jobs.
    """
    analyzed = []

    for job in jobs:
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        jd = job.get("description", "")

        logger.info(f"Analyzing: {title} at {company}")

        analysis = await analyze_job(jd, profile)
        if not analysis:
            logger.warning(f"Analysis failed for: {title} at {company}")
            continue

        # Check if it's a dream company
        is_dream = any(
            dc.lower() in company.lower()
            for dc in profile.dream_companies
        )

        # Override decision if needed
        score = analysis["match_score"]
        final_decision = apply_decision_from_score(score, profile, is_dream)
        if final_decision != analysis["apply_decision"]:
            logger.info(
                f"Decision override for {company}: "
                f"{analysis['apply_decision']} → {final_decision} "
                f"(score={score}, dream={is_dream})"
            )
            analysis["apply_decision"] = final_decision

        job["analysis"] = analysis
        analyzed.append(job)

        logger.info(
            f"  → Score: {score}, Decision: {analysis['apply_decision']}, "
            f"Matching: {len(analysis.get('matching_skills', []))} skills"
        )

    logger.info(
        f"LLM analysis complete: {len(analyzed)}/{len(jobs)} jobs analyzed"
    )
    return analyzed
