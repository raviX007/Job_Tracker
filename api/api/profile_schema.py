"""Pydantic models for ProfileConfig — mirrored from pipeline/core/models.py.

Used by the API to validate profile config JSON before storing as JSONB.
The pipeline has its own copy and validates independently when loading.
"""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class SearchMode(str, Enum):
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"


class RemotePreferences(BaseModel):
    accept_global_remote: bool = False
    accept_country_remote: bool = True
    country: str = "India"
    timezone_range: str = "IST ± 2hrs"
    visa_sponsorship_needed: bool = False


class PlatformConfig(BaseModel):
    enabled: bool = True
    auto_apply: bool = False
    max_daily: int = Field(default=0, ge=0, le=50)
    delay_min: int = Field(default=3, ge=1)
    delay_max: int = Field(default=5, ge=2)

    @field_validator("delay_max")
    @classmethod
    def delay_max_gte_min(cls, v, info):
        if "delay_min" in info.data and v < info.data["delay_min"]:
            raise ValueError("delay_max must be >= delay_min")
        return v


class AggregatorConfig(BaseModel):
    enabled: bool = True
    api_key: str = ""
    app_id: str = ""
    app_key: str = ""


class CandidateConfig(BaseModel):
    name: str
    email: str
    phone: str = ""
    resume_path: str = ""
    github: str = ""
    linkedin: str = ""
    portfolio: str = ""
    location: str
    timezone: str = "Asia/Kolkata"


class SearchPreferences(BaseModel):
    mode: SearchMode = SearchMode.HYBRID
    locations: list[str] = []
    remote_preferences: RemotePreferences = RemotePreferences()
    relocation_willing: bool = False
    salary_min: int = Field(default=0, ge=0)
    salary_currency: str = "INR"


class SkillsConfig(BaseModel):
    primary: list[str] = []
    secondary: list[str] = []
    frameworks: list[str] = []


class WorkHistoryProject(BaseModel):
    name: str
    description: str = ""


class WorkHistoryEntry(BaseModel):
    company: str
    role: str
    duration: str = ""
    type: str = "full_time"
    tech: list[str] = []
    description: str = ""
    client: str = ""
    rating: str = ""
    client_quote: str = ""
    projects: list[WorkHistoryProject] = []


class GapProject(BaseModel):
    name: str
    description: str = ""
    tech: list[str] = []


class ExperienceConfig(BaseModel):
    years: int = Field(default=0, ge=0)
    graduation_year: int = 2023
    degree: str = ""
    gap_explanation: str = ""
    work_history: list[WorkHistoryEntry] = []
    gap_projects: list[GapProject] = []


class AntiHallucinationConfig(BaseModel):
    strict_mode: bool = True
    validate_output: bool = True
    allowed_companies: list[str] = []


class FiltersConfig(BaseModel):
    must_have_any: list[str] = []
    skip_titles: list[str] = []
    skip_companies: list[str] = []
    target_companies: list[str] = []
    min_match_score: int = Field(default=40, ge=0, le=100)
    auto_apply_threshold: int = Field(default=60, ge=0, le=100)
    maybe_range: list[int] = [40, 60]


class MatchingConfig(BaseModel):
    embedding_model: str = "all-MiniLM-L6-v2"
    fast_filter_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    max_job_age_days: int = Field(default=7, ge=1, le=30)
    prefer_gap_tolerant: bool = True
    prefer_fresher_roles: bool = True


class ScreeningAnswers(BaseModel):
    work_authorization_india: str = "Yes"
    visa_sponsorship_required: str = "No"
    willing_to_relocate: str = "Yes"
    notice_period: str = "Immediate"
    expected_ctc_range: str = "4-8 LPA"
    years_of_experience: str = "0-1"
    current_location: str = "Bengaluru"
    unknown_question_action: str = "skip_and_alert"


class LLMConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1500, ge=100, le=4000)
    json_mode: bool = True


class ColdEmailConfig(BaseModel):
    sender_email: str = ""
    sender_name: str = ""
    max_daily: int = Field(default=12, ge=0, le=50)
    max_per_hour: int = Field(default=8, ge=0, le=20)
    morning_batch_time: str = "09:00"
    signature: str = ""
    delay_between_sends_sec: int = Field(default=5, ge=1)
    delay_jitter_sec: int = Field(default=3, ge=0)
    warmup_enabled: bool = True
    include_unsubscribe: bool = True
    max_followups_per_recipient: int = Field(default=1, ge=0, le=2)
    followup_after_days: int = Field(default=7, ge=3, le=14)
    only_business_emails: bool = True


class TelegramChannels(BaseModel):
    urgent: str = ""
    digest: str = ""
    review: str = ""


class TelegramConfig(BaseModel):
    enabled: bool = True
    bot_token: str = ""
    channels: TelegramChannels = TelegramChannels()
    review_batch_interval_hours: int = Field(default=2, ge=1, le=12)
    digest_time: str = "20:00"


class NotificationsConfig(BaseModel):
    telegram: TelegramConfig = TelegramConfig()


class SystemPlatformFlags(BaseModel):
    naukri: bool = True
    indeed: bool = True
    foundit: bool = True
    cold_email: bool = True
    scraping: bool = True


class SystemConfig(BaseModel):
    active: bool = True
    platforms: SystemPlatformFlags = SystemPlatformFlags()


class SafetyConfig(BaseModel):
    max_applications_per_company_per_month: int = Field(default=2, ge=1, le=5)
    require_review_above_score: int = Field(default=85, ge=50, le=100)
    auto_submit_platforms: list[str] = ["naukri", "indeed", "foundit"]
    followup_after_days: int = Field(default=7, ge=3, le=14)
    followup_max_per_email: int = Field(default=1, ge=1, le=2)


class ProfileConfig(BaseModel):
    """Top-level config model. Validates the full profile config JSONB."""

    candidate: CandidateConfig
    search_preferences: SearchPreferences = SearchPreferences()
    skills: SkillsConfig = SkillsConfig()
    experience: ExperienceConfig = ExperienceConfig()
    anti_hallucination: AntiHallucinationConfig = AntiHallucinationConfig()
    filters: FiltersConfig = FiltersConfig()
    matching: MatchingConfig = MatchingConfig()
    screening_answers: ScreeningAnswers = ScreeningAnswers()
    llm: LLMConfig = LLMConfig()
    cold_email: ColdEmailConfig = ColdEmailConfig()
    notifications: NotificationsConfig = NotificationsConfig()
    system: SystemConfig = SystemConfig()
    safety: SafetyConfig = SafetyConfig()
    dream_companies: list[str] = []
    platforms: dict[str, PlatformConfig] = {}
    aggregators: dict[str, AggregatorConfig] = {}
