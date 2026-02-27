"""Centralized constants for the job-tracker pipeline.

All hardcoded thresholds, limits, timeouts, and domain lists live here.
Import from this module instead of scattering magic numbers across files.
"""

# ─── Timeouts (seconds) ────────────────────────────────────

API_TIMEOUT = 60
EMAIL_FINDER_TIMEOUT = 15
HUNTER_VERIFY_TIMEOUT = 10

# ─── Retry Configuration ───────────────────────────────────

RETRY_MAX_ATTEMPTS = 3
RETRY_MIN_WAIT = 2  # seconds
RETRY_MAX_WAIT = 10  # seconds
LLM_RETRY_ATTEMPTS = 2
LLM_RETRY_MIN_WAIT = 1
LLM_RETRY_MAX_WAIT = 5
# ─── Pipeline Thresholds ───────────────────────────────────

JD_TRUNCATE_LENGTH = 3000
STARTUP_DESC_TRUNCATE = 2000
STARTUP_MAX_AGE_MONTHS = 18
EMBEDDING_DEFAULT_THRESHOLD = 0.35

# ─── Email Generation ──────────────────────────────────────

EMAIL_MAX_BODY_WORDS = 200
COVER_LETTER_MAX_WORDS = 150
COVER_LETTER_TRUNCATE_WORDS = 130  # truncate to this if over max
STARTUP_EMAIL_MAX_WORDS = 150
PATTERN_GUESS_CONFIDENCE = "low"
GENERIC_EMAIL_PREFIXES = [
    "hr", "careers", "hiring", "jobs", "recruitment", "talent",
]

# ─── Source Display Names ───────────────────────────────────

SOURCE_DISPLAY_NAMES = {
    "hn_hiring": "Hacker News Who's Hiring",
    "yc_directory": "Y Combinator directory",
    "producthunt": "ProductHunt",
}

# ─── Domains ───────────────────────────────────────────────

NON_COMPANY_DOMAINS = [
    "ycombinator.com",
    "news.ycombinator.com",
    "producthunt.com",
    "algolia.com",
]

DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "10minutemail.com", "yopmail.com", "trashmail.com", "sharklasers.com",
    "guerrillamailblock.com", "grr.la", "dispostable.com", "maildrop.cc",
    "fakeinbox.com", "mailnesia.com", "tempr.email", "discard.email",
    "getnada.com", "emailondeck.com", "tempail.com", "burnermail.io",
    "temp-mail.org", "mohmal.com", "minuteinbox.com",
}

# ─── Team Page Scraping ────────────────────────────────────

TEAM_PAGE_PATHS = ["/about", "/team", "/about-us", "/our-team"]
HR_ROLE_PATTERNS = [
    r"(?:head|vp|director|manager|lead)\s+(?:of\s+)?(?:people|hr|human|talent|recruiting)",
    r"(?:recruiter|recruiting|talent\s+acquisition|hr\s+manager|people\s+ops)",
]

# ─── Email Verification ───────────────────────────────────

MAX_EMAIL_LOCAL_PART = 64
APOLLO_RESULTS_PER_PAGE = 5

# ─── Email Warmup Schedule ────────────────────────────────

# Week number → max emails per day (ramp up over 4 weeks)
WARMUP_SCHEDULE = {
    1: 5,   # Week 1: 5/day
    2: 8,   # Week 2: 8/day
    3: 12,  # Week 3: 12/day
    4: 15,  # Week 4+: full speed (capped by config)
}

# ─── Scraper Relevance Filtering ──────────────────────────

GENERIC_JOB_TERMS = {
    "developer", "engineer", "fullstack", "full-stack",
    "backend", "frontend", "software",
}

# ─── LLM Model Defaults ────────────────────────────────────

DEFAULT_LLM_MODEL = "gpt-4o-mini"
