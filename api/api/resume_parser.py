"""Resume extraction — PDF (vision-based) + LaTeX (text-based).

Uses OpenAI structured outputs with Pydantic models for guaranteed schema compliance.
PDF pages are rendered as images and sent via the vision API for better accuracy.
LaTeX files are sent as text (GPT-4o-mini reads LaTeX natively).

Langfuse: if configured, all OpenAI calls are auto-traced via the langfuse.openai
wrapper. The extraction prompt can be managed in Langfuse (name: "resume-extraction").
"""

import base64
import logging
import os

from pydantic import BaseModel

# Use Langfuse-wrapped OpenAI for automatic tracing (falls back to regular if not installed)
try:
    from langfuse.openai import AsyncOpenAI
except ImportError:
    from openai import AsyncOpenAI

logger = logging.getLogger("jobbot.resume-parser")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ─── Structured Output Models ─────────────────────────


class ExtractedWorkProject(BaseModel):
    name: str
    description: str


class ExtractedWorkHistory(BaseModel):
    company: str
    role: str
    duration: str
    type: str  # full_time, internship, freelance, contract
    tech: list[str]
    description: str
    projects: list[ExtractedWorkProject]


class ExtractedGapProject(BaseModel):
    name: str
    description: str
    tech: list[str]


class ExtractedCandidate(BaseModel):
    name: str
    email: str
    phone: str
    github: str
    linkedin: str
    portfolio: str
    location: str
    timezone: str


class ExtractedSkills(BaseModel):
    primary: list[str]
    secondary: list[str]
    frameworks: list[str]


class ExtractedExperience(BaseModel):
    years: int
    graduation_year: int
    degree: str
    gap_explanation: str
    work_history: list[ExtractedWorkHistory]
    gap_projects: list[ExtractedGapProject]


class ExtractedResume(BaseModel):
    candidate: ExtractedCandidate
    skills: ExtractedSkills
    experience: ExtractedExperience


# ─── Extraction Prompt (fetched from Langfuse) ───────


def _get_extraction_prompt() -> str:
    """Fetch the resume-extraction prompt from Langfuse. Raises on failure."""
    from langfuse import Langfuse

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
    if not public_key or not secret_key:
        raise ValueError(
            "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set — "
            "resume extraction prompt is managed in Langfuse"
        )

    client = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
    prompt = client.get_prompt("resume-extraction", type="text", cache_ttl_seconds=300)
    compiled = prompt.compile()
    logger.info("Using Langfuse prompt 'resume-extraction' v%s", prompt.version)
    return compiled


# ─── Text Extractors ──────────────────────────────────


async def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from a PDF file using PyPDF2 (for DB storage)."""
    from PyPDF2 import PdfReader
    import io

    reader = PdfReader(io.BytesIO(file_content))
    text_parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            text_parts.append(text)

    return "\n".join(text_parts)


async def extract_text_from_tex(file_content: bytes) -> str:
    """Read LaTeX file as UTF-8 text."""
    try:
        return file_content.decode("utf-8")
    except UnicodeDecodeError:
        return file_content.decode("latin-1")


# ─── PDF → Image Conversion ───────────────────────────


async def pdf_pages_to_base64_images(file_content: bytes, dpi: int = 150) -> list[str]:
    """Convert each PDF page to a base64-encoded PNG image using PyMuPDF."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=file_content, filetype="pdf")
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=dpi)
        png_bytes = pix.tobytes("png")
        images.append(base64.b64encode(png_bytes).decode("utf-8"))
    doc.close()
    return images


# ─── LLM Extraction ───────────────────────────────────


async def extract_profile_from_pdf(file_content: bytes) -> dict:
    """Extract structured profile from PDF using vision-based approach."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set — cannot parse resume")

    prompt = _get_extraction_prompt()
    images = await pdf_pages_to_base64_images(file_content)

    # Build multimodal message: text prompt + page images
    content: list[dict] = [{"type": "text", "text": prompt}]
    for b64_img in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64_img}", "detail": "high"},
        })

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    completion = await client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": content}],
        response_format=ExtractedResume,
        temperature=0.1,
        max_tokens=3000,
        name="resume-extraction-pdf",
    )

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("OpenAI returned no parsed result")
    return parsed.model_dump()


async def extract_profile_from_tex(resume_text: str) -> dict:
    """Extract structured profile from LaTeX text."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set — cannot parse resume")

    prompt = _get_extraction_prompt()
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    completion = await client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Resume (LaTeX source):\n\n{resume_text[:12000]}"},
        ],
        response_format=ExtractedResume,
        temperature=0.1,
        max_tokens=3000,
        name="resume-extraction-tex",
    )

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("OpenAI returned no parsed result")
    return parsed.model_dump()


# ─── Legacy compatibility ──────────────────────────────


async def extract_profile_from_resume(resume_text: str) -> dict:
    """Legacy text-based extraction (redirects to structured output)."""
    return await extract_profile_from_tex(resume_text)
