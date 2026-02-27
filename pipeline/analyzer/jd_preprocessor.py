"""JD Preprocessor — extract key sections and trim for embedding model.

The all-MiniLM-L6-v2 model truncates at 256 tokens (~200 words).
We need to extract the most relevant parts of a job description
to stay within that limit for accurate similarity scoring.
"""

import re

# Common boilerplate patterns to strip
_BOILERPLATE_PATTERNS = [
    r"(?i)equal\s+opportunity\s+employer.*",
    r"(?i)we\s+are\s+an?\s+equal.*",
    r"(?i)about\s+(the\s+)?company\s*[:\-]?\s*\n.*?(?=\n\n|\Z)",
    r"(?i)benefits?\s*[:\-]?\s*\n.*?(?=\n\n|\Z)",
    r"(?i)perks?\s*(and|&)\s*benefits?.*?(?=\n\n|\Z)",
    r"(?i)what\s+we\s+offer.*?(?=\n\n|\Z)",
    r"(?i)how\s+to\s+apply.*",
    r"(?i)apply\s+now.*",
    r"(?i)disclaimer\s*[:\-].*",
]

# Section headers that indicate important content
_KEY_SECTION_HEADERS = [
    r"(?i)(requirements?|qualifications?|what\s+we.re\s+looking\s+for|must\s+have|skills?\s+required)",
    r"(?i)(responsibilities?|what\s+you.ll\s+do|role\s+description|job\s+description)",
    r"(?i)(nice\s+to\s+have|preferred|good\s+to\s+have|bonus)",
    r"(?i)(tech\s*stack|technologies?|tools?\s+we\s+use)",
    r"(?i)(experience|eligibility)",
]


def strip_boilerplate(text: str) -> str:
    """Remove common boilerplate sections from job descriptions."""
    cleaned = text
    for pattern in _BOILERPLATE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL)
    # Collapse multiple newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_key_sections(text: str) -> str:
    """Extract requirements, skills, and responsibilities sections.

    Returns the most relevant text for similarity matching.
    """
    sections = []
    lines = text.split("\n")

    in_key_section = False
    current_section = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_section and in_key_section:
                sections.append("\n".join(current_section))
                current_section = []
                in_key_section = False
            continue

        # Check if this line is a key section header
        is_header = any(re.search(p, stripped) for p in _KEY_SECTION_HEADERS)
        if is_header:
            if current_section and in_key_section:
                sections.append("\n".join(current_section))
            current_section = [stripped]
            in_key_section = True
        elif in_key_section:
            current_section.append(stripped)

    # Don't forget the last section
    if current_section and in_key_section:
        sections.append("\n".join(current_section))

    if sections:
        return "\n\n".join(sections)

    # If no sections found, return the cleaned full text
    return text


def preprocess_for_embedding(jd_text: str, max_words: int = 200) -> str:
    """Full preprocessing pipeline for the embedding model.

    1. Strip boilerplate
    2. Extract key sections
    3. Truncate to ~200 words (stays under 256 token limit for MiniLM)

    Returns clean text ready for embedding.
    """
    if not jd_text or len(jd_text.strip()) < 50:
        return jd_text or ""

    # Step 1: Strip boilerplate
    cleaned = strip_boilerplate(jd_text)

    # Step 2: Extract key sections
    extracted = extract_key_sections(cleaned)

    # Step 3: Truncate to max_words
    words = extracted.split()
    if len(words) > max_words:
        extracted = " ".join(words[:max_words])

    return extracted.strip()


def extract_title_and_skills(jd_text: str) -> dict:
    """Quick extraction of structured info from JD text.

    Returns dict with: skills_mentioned, experience_required, location_mentioned
    Used for fast pre-filtering before LLM analysis.
    """
    text_lower = jd_text.lower()

    # Common tech skills to look for
    skill_patterns = [
        "python", "django", "fastapi", "flask", "react", "angular", "vue",
        "node.js", "nodejs", "typescript", "javascript", "java", "go", "golang",
        "rust", "c++", "ruby", "rails", "php", "laravel",
        "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "docker", "kubernetes", "aws", "gcp", "azure",
        "langchain", "langgraph", "llm", "rag", "openai", "gpt",
        "machine learning", "deep learning", "nlp", "computer vision",
        "rest api", "graphql", "microservices", "ci/cd",
        "git", "linux", "agile", "scrum",
    ]

    found_skills = [s for s in skill_patterns if s in text_lower]

    # Experience extraction
    exp_match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*years?", text_lower)
    if not exp_match:
        exp_match = re.search(r"(\d+)\+?\s*years?", text_lower)

    experience = exp_match.group(0) if exp_match else None

    return {
        "skills_mentioned": found_skills,
        "experience_required": experience,
    }
