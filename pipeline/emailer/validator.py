"""Anti-hallucination validator — ensures LLM-generated content is truthful.

Checks that cover letters and cold emails don't contain:
1. Companies the candidate never worked at
2. Fabricated degrees or certifications
3. Inflated years of experience
4. Skills the candidate doesn't have

This is critical for maintaining credibility — one fabricated detail
can destroy a candidate's reputation.
"""

import re
from dataclasses import dataclass, field

from core.logger import logger
from core.models import ProfileConfig


@dataclass
class ValidationResult:
    """Result of anti-hallucination validation."""
    is_valid: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_generated_content(
    content: str,
    profile: ProfileConfig,
) -> ValidationResult:
    """Validate that generated content doesn't contain fabricated details.

    Runs all checks and returns a ValidationResult with any issues found.
    """
    if not content:
        return ValidationResult(is_valid=True)

    issues = []
    warnings = []
    content_lower = content.lower()

    # Check 1: Only allowed companies mentioned
    company_issues = _check_companies(content_lower, profile)
    issues.extend(company_issues)

    # Check 2: No fabricated degrees/certifications
    degree_issues = _check_degrees(content_lower, profile)
    issues.extend(degree_issues)

    # Check 3: No inflated experience
    exp_issues = _check_experience(content_lower, profile)
    issues.extend(exp_issues)

    # Check 4: Skills mentioned exist in profile
    skill_warnings = _check_skills(content_lower, profile)
    warnings.extend(skill_warnings)

    is_valid = len(issues) == 0

    if not is_valid:
        logger.warning(f"Anti-hallucination: {len(issues)} issues found: {issues}")
    if warnings:
        logger.debug(f"Anti-hallucination warnings: {warnings}")

    return ValidationResult(
        is_valid=is_valid,
        issues=issues,
        warnings=warnings,
    )


def _check_companies(content: str, profile: ProfileConfig) -> list[str]:
    """Check that only allowed companies are mentioned as past employers."""
    issues = []

    # Build set of allowed company references
    allowed = set()
    for company in profile.anti_hallucination.allowed_companies:
        allowed.add(company.lower())
        # Also allow shortened forms
        for word in company.lower().split():
            if len(word) > 3:
                allowed.add(word)

    # Also allow dream companies (they're targets, not fabricated employers)
    for company in profile.dream_companies:
        allowed.add(company.lower())

    # Phrases that indicate PAST work experience claims (not applying/interested)
    work_claim_patterns = [
        r"(?:worked|was\s+working)\s+(?:at|for|with)\s+([A-Z][a-zA-Z\s]+)",
        r"(?:my\s+(?:role|position|experience))\s+(?:at|with)\s+([A-Z][a-zA-Z\s]+)",
        r"(?:during\s+my\s+time|my\s+internship)\s+(?:at|with)\s+([A-Z][a-zA-Z\s]+)",
    ]

    for pattern in work_claim_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            company_name = match.strip().lower()
            if not any(allowed_word in company_name for allowed_word in allowed):
                issues.append(f"Mentions working at '{match.strip()}' — not in allowed companies")

    return issues


def _check_degrees(content: str, profile: ProfileConfig) -> list[str]:
    """Check for fabricated degrees or certifications."""
    issues = []

    # Known degree the candidate has
    actual_degree = profile.experience.degree.lower()

    # Degrees that would be fabricated
    fabricated_degree_patterns = [
        (r"(?:master|m\.?s\.?|m\.?tech)", "Master's degree"),
        (r"(?:ph\.?d|doctorate)", "PhD"),
        (r"(?:mba)", "MBA"),
    ]

    for pattern, degree_name in fabricated_degree_patterns:
        if re.search(pattern, content) and not re.search(pattern, actual_degree):
            # Check if it's mentioned as something the candidate HAS (not just a requirement)
            context_patterns = [
                rf"(?:my|i have|i hold|completed|earned|with)\s+(?:a\s+)?{pattern}",
                rf"{pattern}\s+(?:degree|in|from)",
            ]
            for ctx in context_patterns:
                if re.search(ctx, content):
                    issues.append(f"Claims to have {degree_name} — candidate has {profile.experience.degree}")
                    break

    # Check for fabricated certifications
    cert_patterns = [
        (r"(?:aws\s+certified|aws\s+certification)", "AWS Certification"),
        (r"(?:gcp\s+certified|google\s+cloud\s+certified)", "GCP Certification"),
        (r"(?:azure\s+certified)", "Azure Certification"),
        (r"(?:pmp\s+certified|pmp\s+certification)", "PMP Certification"),
    ]

    for pattern, cert_name in cert_patterns:
        if re.search(pattern, content):
            claim_patterns = [
                rf"(?:i am|i'm|i hold|certified|have)\s+.*{pattern}",
            ]
            for ctx in claim_patterns:
                if re.search(ctx, content):
                    issues.append(f"Claims {cert_name} — not in candidate profile")
                    break

    return issues


def _check_experience(content: str, profile: ProfileConfig) -> list[str]:
    """Check for inflated years of experience."""
    issues = []
    actual_years = profile.experience.years

    # Look for experience claims
    exp_patterns = [
        r"(\d+)\+?\s*years?\s+(?:of\s+)?experience",
        r"(?:over|more than)\s+(\d+)\s*years?",
        r"(\d+)\s*years?\s+(?:in|of|working)",
    ]

    for pattern in exp_patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            try:
                claimed_years = int(match)
                if claimed_years > actual_years + 1:  # Allow 1 year rounding
                    issues.append(
                        f"Claims {claimed_years} years experience — "
                        f"candidate has {actual_years} years"
                    )
            except ValueError:
                continue

    return issues


def _check_skills(content: str, profile: ProfileConfig) -> list[str]:
    """Check if mentioned skills exist in the candidate's profile.

    Returns warnings (not issues) since the LLM might mention skills
    in the context of the job requirements, not as claims.
    """
    warnings = []

    # All candidate skills
    all_skills = set()
    for skill in profile.skills.primary + profile.skills.secondary:
        all_skills.add(skill.lower())
    for framework in profile.skills.frameworks:
        all_skills.add(framework.lower())
    for wh in profile.experience.work_history:
        for tech in wh.tech:
            all_skills.add(tech.lower())
    for proj in profile.experience.gap_projects:
        for tech in proj.tech:
            all_skills.add(tech.lower())

    # Skill claim patterns (only flag when candidate claims to HAVE the skill)
    claim_patterns = [
        r"(?:proficient|experienced|skilled|expertise)\s+(?:in|with)\s+([A-Za-z/+#.\s]+?)(?:[,.]|\s+and)",
        r"(?:my|i have|i know)\s+(?:strong\s+)?([A-Za-z/+#.\s]+?)\s+(?:skills?|experience|knowledge)",
    ]

    for pattern in claim_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            claimed_skill = match.strip().lower()
            if claimed_skill and not any(s in claimed_skill or claimed_skill in s for s in all_skills) and 2 < len(claimed_skill) < 30:
                warnings.append(f"Claims skill '{match.strip()}' — verify it's in profile")

    return warnings
