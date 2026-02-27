"""Pydantic models for API request/response bodies."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ─── Valid pipeline source values ───────────────────
PIPELINE_SOURCES = Literal[
    "all",
    "remote_boards", "aggregators", "api_boards", "ats_direct",
    "remotive", "jobicy", "himalayas", "arbeitnow",
    "jooble", "adzuna", "remoteok", "hiringcafe",
    "jsearch", "careerjet", "themuse", "findwork",
    "greenhouse", "lever",
    "startup_scout", "hn_hiring", "yc_directory", "producthunt",
]


# ─── Dashboard Request Models ────────────────────────

class CreateApplicationRequest(BaseModel):
    job_id: int = Field(..., gt=0)
    profile_id: int = Field(..., gt=0)
    method: str = Field(..., min_length=1, max_length=30)
    platform: str = Field(..., max_length=50)


class UpsertApplicationRequest(BaseModel):
    job_id: int = Field(..., gt=0)
    profile_id: int = Field(..., gt=0)
    method: str = Field(..., min_length=1, max_length=30)
    platform: str = Field(default="", max_length=50)
    response_type: str | None = None
    notes: str | None = None
    app_id: int | None = None


class UpdateOutcomeRequest(BaseModel):
    response_type: str = Field(..., min_length=1, max_length=30)
    response_date: str | None = None
    notes: str = ""


class UpdateEmailRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=500)
    body_plain: str = Field(..., min_length=1)


class PipelineRunRequest(BaseModel):
    source: PIPELINE_SOURCES = "all"
    limit: int = Field(default=10, ge=1, le=100)


class PipelineCallbackPayload(BaseModel):
    status: str | None = None
    output: str | None = None
    duration_seconds: float | None = None
    return_code: int | None = None
    error: str | None = None
    started_at: bool | None = None  # if True, sets started_at = NOW()


# ─── Pipeline Request Models ─────────────────────────

class EnsureProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., max_length=255)
    config_path: str = Field(..., min_length=1)


class SaveJobRequest(BaseModel):
    job_url: str | None = None
    source: str | None = Field(default=None, max_length=50)
    discovered_via: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    is_remote: bool = False
    description: str | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, max_length=10)
    date_posted: str | None = None
    dedup_key: str | None = None

    @field_validator("salary_max")
    @classmethod
    def salary_max_gte_min(cls, v, info):
        salary_min = info.data.get("salary_min")
        if v is not None and salary_min is not None and v < salary_min:
            raise ValueError("salary_max must be >= salary_min")
        return v


class SaveAnalysisRequest(BaseModel):
    job_id: int = Field(..., gt=0)
    profile_id: int = Field(..., gt=0)
    match_score: int | None = Field(default=None, ge=0, le=100)
    embedding_score: float | None = None
    skills_required: list[str] = []
    skills_matched: list[str] = []
    skills_missing: list[str] = []
    ats_keywords: list[str] = []
    experience_required: str | None = None
    location_compatible: bool | None = None
    remote_compatible: bool | None = None
    company_type: str | None = Field(default=None, max_length=30)
    gap_tolerant: bool | None = None
    red_flags: list[str] = []
    apply_decision: str | None = Field(default=None, max_length=20)
    cold_email_angle: str | None = None
    gap_framing_for_this_role: str | None = None
    route_action: str | None = Field(default=None, max_length=40)


class UpdateCoverLetterRequest(BaseModel):
    job_id: int = Field(..., gt=0)
    profile_id: int = Field(..., gt=0)
    cover_letter: str


class EnqueueEmailRequest(BaseModel):
    job_id: int = Field(..., gt=0)
    profile_id: int = Field(..., gt=0)
    recipient_email: str = Field(..., min_length=1, max_length=255)
    recipient_name: str = Field(default="", max_length=255)
    recipient_role: str = Field(default="", max_length=255)
    recipient_source: str = Field(default="", max_length=50)
    subject: str = Field(..., min_length=1)
    body_html: str
    body_plain: str
    signature: str = ""
    resume_path: str = ""
    email_verified: bool = False
    email_verification_result: str = "unverified"
    email_verification_provider: str = ""


class VerifyEmailRequest(BaseModel):
    verification_result: str
    verification_provider: str


class DedupCheckRequest(BaseModel):
    urls: list[str] = Field(default=[], max_length=1000)
    dedup_keys: list[str] = Field(default=[], max_length=1000)


class SaveStartupProfileRequest(BaseModel):
    job_id: int
    startup_name: str | None = None
    website_url: str | None = None
    yc_url: str | None = None
    ph_url: str | None = None
    founding_date: str | None = None
    founding_date_source: str | None = None
    age_months: int | None = None
    founder_names: list[str] = []
    founder_emails: list[str] = []
    founder_roles: list[str] = []
    employee_count: int | None = None
    employee_count_source: str | None = None
    one_liner: str | None = None
    product_description: str | None = None
    tech_stack: list[str] = []
    topics: list[str] = []
    has_customers: bool | None = None
    has_customers_evidence: str | None = None
    funding_amount: str | None = None
    funding_round: str | None = None
    funding_date: str | None = None
    funding_source: str | None = None
    source: str | None = None
    yc_batch: str | None = None
    ph_launch_date: str | None = None
    ph_votes_count: int | None = None
    ph_maker_info: str | None = None
    hn_thread_date: str | None = None
    llm_extracted: bool = False
    llm_extraction_raw: dict | None = None
    data_completeness: int | None = None
