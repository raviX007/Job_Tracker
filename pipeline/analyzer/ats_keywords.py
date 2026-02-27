"""ATS keyword matching — match JD keywords against candidate skills.

Identifies which keywords from the JD align with the candidate's profile.
Used for cover letter optimization and ATS scoring.
"""

from core.models import ProfileConfig


def get_candidate_keywords(profile: ProfileConfig) -> set[str]:
    """Build the full set of candidate keywords from profile."""
    keywords = set()

    # Skills (all lowercase for matching)
    for skill in profile.skills.primary:
        keywords.add(skill.lower())
    for skill in profile.skills.secondary:
        keywords.add(skill.lower())
    for framework in profile.skills.frameworks:
        keywords.add(framework.lower())

    # Tech from work history
    for wh in profile.experience.work_history:
        for tech in wh.tech:
            keywords.add(tech.lower())

    # Tech from gap projects
    for proj in profile.experience.gap_projects:
        for tech in proj.tech:
            keywords.add(tech.lower())

    return keywords


def match_ats_keywords(
    ats_keywords: list[str],
    profile: ProfileConfig,
) -> dict:
    """Match ATS keywords from LLM analysis against candidate profile.

    Returns dict with:
    - matched: keywords the candidate has
    - missing: keywords the candidate doesn't have
    - match_ratio: percentage of keywords matched
    """
    candidate_keywords = get_candidate_keywords(profile)

    matched = []
    missing = []

    for kw in ats_keywords:
        kw_lower = kw.lower()
        # Check if any candidate keyword contains this ATS keyword or vice versa
        found = any(
            kw_lower in ck or ck in kw_lower
            for ck in candidate_keywords
        )
        if found:
            matched.append(kw)
        else:
            missing.append(kw)

    match_ratio = len(matched) / len(ats_keywords) if ats_keywords else 0.0

    return {
        "matched": matched,
        "missing": missing,
        "match_ratio": round(match_ratio, 2),
    }


def suggest_keywords_for_cover_letter(
    analysis: dict,
    profile: ProfileConfig,
    max_keywords: int = 8,
) -> list[str]:
    """Suggest the best keywords to include in a cover letter.

    Prioritizes: matched ATS keywords > primary skills that appear in JD > secondary skills.
    """
    ats_keywords = analysis.get("ats_keywords", [])
    matching_skills = analysis.get("matching_skills", [])

    # Start with ATS keywords that the candidate actually has
    ats_match = match_ats_keywords(ats_keywords, profile)
    suggestions = list(ats_match["matched"])

    # Add matching skills not already in suggestions
    for skill in matching_skills:
        if skill.lower() not in {s.lower() for s in suggestions}:
            suggestions.append(skill)

    # Deduplicate and limit
    seen = set()
    unique = []
    for s in suggestions:
        if s.lower() not in seen:
            seen.add(s.lower())
            unique.append(s)

    return unique[:max_keywords]
