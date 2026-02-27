"""Embedding-based fast filter — local similarity scoring.

Uses all-MiniLM-L6-v2 (80MB, runs locally, no API cost).
First-run downloads the model from HuggingFace (~30 seconds).

This is the Stage 1 filter: cheap and fast. Jobs scoring below
the threshold are skipped without burning an LLM API call.
"""

import asyncio

from analyzer.jd_preprocessor import preprocess_for_embedding
from core.logger import logger
from core.models import ProfileConfig

# Lazy-loaded model singleton
_model = None


def _load_model():
    """Load the sentence-transformers model (lazy, first call only)."""
    global _model
    if _model is None:
        logger.info("Loading embedding model: all-MiniLM-L6-v2 (first run may download ~80MB)...")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model loaded.")
    return _model


def build_resume_text(profile: ProfileConfig) -> str:
    """Build a text representation of the candidate profile for embedding.

    Focuses on skills, experience, and project descriptions — the parts
    that should match against JD requirements.
    """
    parts = []

    # Role/identity
    parts.append(f"{profile.candidate.name}, {profile.experience.degree}")
    parts.append(f"Location: {profile.candidate.location}")

    # Skills
    parts.append(f"Primary skills: {', '.join(profile.skills.primary)}")
    if profile.skills.secondary:
        parts.append(f"Secondary skills: {', '.join(profile.skills.secondary)}")
    if profile.skills.frameworks:
        parts.append(f"Frameworks: {', '.join(profile.skills.frameworks)}")

    # Work history
    for job in profile.experience.work_history:
        line = f"{job.role} at {job.company} ({job.duration})"
        if job.tech:
            line += f" — {', '.join(job.tech)}"
        if job.description:
            line += f". {job.description}"
        parts.append(line)
        for proj in job.projects:
            proj_line = f"  - {proj.name}"
            if proj.description:
                proj_line += f": {proj.description}"
            parts.append(proj_line)

    # Gap projects
    for project in profile.experience.gap_projects:
        line = f"Project: {project.name}"
        if project.tech:
            line += f" — {', '.join(project.tech)}"
        if project.description:
            line += f". {project.description}"
        parts.append(line)

    # Gap explanation
    if profile.experience.gap_explanation:
        parts.append(f"Background: {profile.experience.gap_explanation}")

    return "\n".join(parts)


def compute_similarity(text_a: str, text_b: str) -> float:
    """Compute cosine similarity between two texts using embeddings.

    Returns a float between 0.0 and 1.0.
    """
    model = _load_model()
    embeddings = model.encode([text_a, text_b], normalize_embeddings=True)
    # Cosine similarity of normalized vectors = dot product
    similarity = float(embeddings[0] @ embeddings[1])
    return max(0.0, min(1.0, similarity))


def fast_similarity_score(resume_text: str, jd_text: str) -> float:
    """Stage 1 filter: compute embedding similarity between resume and JD.

    Preprocesses JD to extract key sections and stay within model limits.
    """
    processed_jd = preprocess_for_embedding(jd_text)
    if not processed_jd:
        return 0.0

    score = compute_similarity(resume_text, processed_jd)
    return round(score, 4)


async def filter_by_embedding(
    jobs: list[dict],
    profile: ProfileConfig,
    threshold: float | None = None,
) -> tuple[list[dict], list[dict]]:
    """Filter jobs using embedding similarity.

    Runs the CPU-heavy embedding in a thread pool to keep the event loop free.

    Returns: (passed_jobs, filtered_out_jobs)
    - passed_jobs: embedding_score >= threshold → proceed to LLM analysis
    - filtered_out_jobs: below threshold → skip
    """
    if threshold is None:
        threshold = profile.matching.fast_filter_threshold

    resume_text = build_resume_text(profile)
    loop = asyncio.get_event_loop()

    passed = []
    filtered_out = []

    for job in jobs:
        jd = job.get("description", "")
        score = await loop.run_in_executor(
            None, fast_similarity_score, resume_text, jd
        )
        job["embedding_score"] = score

        if score >= threshold:
            passed.append(job)
        else:
            filtered_out.append(job)

    logger.info(
        f"Embedding filter: {len(passed)} passed (>= {threshold}), "
        f"{len(filtered_out)} filtered out"
    )
    return passed, filtered_out
