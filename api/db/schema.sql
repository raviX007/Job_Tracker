-- Job Application Agent — Full PostgreSQL Schema
-- Neon PostgreSQL (free tier, requires sslmode=require)

-- Profiles table — one row per user
CREATE TABLE IF NOT EXISTS profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    config_path TEXT,
    config JSONB,
    resume_filename TEXT,
    resume_text TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Jobs table — shared across all users
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    job_url TEXT UNIQUE,
    aggregator_url TEXT,
    source VARCHAR(50),              -- naukri, indeed, linkedin, wellfound, greenhouse, etc.
    discovered_via VARCHAR(50),      -- jooble, adzuna, remoteok, jobspy, direct_scrape
    title VARCHAR(255),
    company VARCHAR(255),
    location VARCHAR(255),
    is_remote BOOLEAN DEFAULT FALSE,
    remote_type VARCHAR(30),         -- full_remote, hybrid, onsite, remote_country, remote_global
    description TEXT,
    salary_min INTEGER CHECK (salary_min IS NULL OR salary_min >= 0),
    salary_max INTEGER CHECK (salary_max IS NULL OR salary_max >= 0),
    salary_currency VARCHAR(10),
    date_posted DATE,
    date_scraped TIMESTAMP DEFAULT NOW(),
    url_verified BOOLEAN DEFAULT TRUE,
    dedup_key TEXT UNIQUE,
    is_obsolete BOOLEAN DEFAULT FALSE,
    obsolete_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Job analysis — per-user per-job (same job scored differently for different profiles)
CREATE TABLE IF NOT EXISTS job_analyses (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    profile_id INTEGER REFERENCES profiles(id) ON DELETE CASCADE,
    match_score INTEGER CHECK (match_score IS NULL OR (match_score >= 0 AND match_score <= 100)),
    embedding_score FLOAT,
    skills_required TEXT[],
    skills_matched TEXT[],
    skills_missing TEXT[],
    ats_keywords TEXT[],
    experience_required VARCHAR(50),
    location_compatible BOOLEAN,
    remote_compatible BOOLEAN,
    company_type VARCHAR(30),        -- startup, mnc, service
    gap_tolerant BOOLEAN,
    red_flags TEXT[],
    apply_decision VARCHAR(20),      -- YES, NO, MAYBE, MANUAL
    cold_email_angle TEXT,
    gap_framing_for_this_role TEXT,
    route_action VARCHAR(40),        -- auto_apply_and_cold_email, cold_email_only, manual_alert
    cover_letter TEXT,
    analyzed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(job_id, profile_id)
);

-- Applications — tracks every action taken per user per job
CREATE TABLE IF NOT EXISTS applications (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    profile_id INTEGER REFERENCES profiles(id) ON DELETE CASCADE,
    method VARCHAR(30),              -- auto_apply, cold_email, manual_apply, telegram_alert
    platform VARCHAR(50),
    applied_at TIMESTAMP DEFAULT NOW(),
    cold_email_sent BOOLEAN DEFAULT FALSE,
    cold_email_to VARCHAR(255),
    cold_email_subject TEXT,
    response_received BOOLEAN DEFAULT FALSE,
    response_type VARCHAR(30),       -- interview, rejection, ghosted, followup_needed, offer, assignment
    response_date TIMESTAMP,
    followup_sent BOOLEAN DEFAULT FALSE,
    followup_at TIMESTAMP,
    notes TEXT,
    UNIQUE(job_id, profile_id, method)
);

-- Email queue — all composed emails saved here, sent only when EMAIL_SENDING_ENABLED=true
CREATE TABLE IF NOT EXISTS email_queue (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    profile_id INTEGER REFERENCES profiles(id) ON DELETE CASCADE,

    -- Recipient
    recipient_email VARCHAR(255) NOT NULL,
    recipient_name VARCHAR(255),
    recipient_role VARCHAR(255),
    recipient_source VARCHAR(50),    -- apollo, snov, hunter, pattern_guess

    -- Email content (fully generated, ready to send)
    subject TEXT NOT NULL,
    body_html TEXT NOT NULL,
    body_plain TEXT NOT NULL,
    signature TEXT,
    resume_path TEXT,                     -- Path to tailored PDF (empty = use default static resume)
    resume_attached BOOLEAN DEFAULT TRUE,

    -- Verification
    email_verified BOOLEAN DEFAULT FALSE,
    email_verification_result VARCHAR(30),   -- valid, invalid, risky, catch_all, unknown, unverified
    email_verification_provider VARCHAR(30), -- hunter, apollo, smtp_check, regex_only
    verified_at TIMESTAMP,

    -- Status lifecycle
    -- draft → verified → ready → queued → sent → delivered/bounced/failed
    -- If EMAIL_SENDING_ENABLED=false, status stays at "ready"
    status VARCHAR(30) DEFAULT 'draft'
        CHECK (status IN ('draft', 'verified', 'ready', 'queued', 'sent', 'delivered', 'bounced', 'failed')),

    -- Sending metadata
    queued_at TIMESTAMP,
    sent_at TIMESTAMP,
    send_attempt_count INTEGER DEFAULT 0,
    last_error TEXT,

    -- Tracking
    follow_up_eligible BOOLEAN DEFAULT TRUE,
    follow_up_sent BOOLEAN DEFAULT FALSE,
    follow_up_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Startup profiles — enriched data for startups discovered by the startup scout pipeline.
-- One row per startup (linked to jobs.id). All fields nullable since not all sources provide all data.
CREATE TABLE IF NOT EXISTS startup_profiles (
    id SERIAL PRIMARY KEY,
    job_id INTEGER UNIQUE NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,

    -- Identity
    startup_name VARCHAR(255),
    website_url TEXT,
    yc_url TEXT,
    ph_url TEXT,

    -- Founding
    founding_date DATE,
    founding_date_source VARCHAR(30),
    age_months INTEGER,

    -- People
    founder_names TEXT[],
    founder_emails TEXT[],
    founder_roles TEXT[],
    employee_count INTEGER,
    employee_count_source VARCHAR(30),

    -- Product
    one_liner TEXT,
    product_description TEXT,
    tech_stack TEXT[],
    topics TEXT[],
    has_customers BOOLEAN,
    has_customers_evidence TEXT,

    -- Funding
    funding_amount VARCHAR(100),
    funding_round VARCHAR(30),
    funding_date DATE,
    funding_source VARCHAR(30),

    -- Source metadata
    source VARCHAR(30),
    yc_batch VARCHAR(10),
    ph_launch_date DATE,
    ph_votes_count INTEGER,
    ph_maker_info TEXT,
    hn_thread_date DATE,

    -- Enrichment
    llm_extracted BOOLEAN DEFAULT FALSE,
    llm_extraction_raw JSONB,
    data_completeness INTEGER,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- System flags — runtime state (kill switch, platform pauses)
CREATE TABLE IF NOT EXISTS system_flags (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Pipeline runs — tracks async pipeline executions triggered from the UI
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    run_id UUID NOT NULL UNIQUE,
    pipeline VARCHAR(30) NOT NULL CHECK (pipeline IN ('main', 'startup_scout')),
    source VARCHAR(50) NOT NULL,
    job_limit INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    pid INTEGER,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    duration_seconds FLOAT,
    return_code INTEGER,
    output TEXT DEFAULT '',
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_jobs_company_title ON jobs(company, title);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_jobs_discovered_via ON jobs(discovered_via);
CREATE INDEX IF NOT EXISTS idx_jobs_dedup_key ON jobs(dedup_key);
CREATE INDEX IF NOT EXISTS idx_jobs_date_scraped ON jobs(date_scraped);

CREATE INDEX IF NOT EXISTS idx_analyses_profile ON job_analyses(profile_id);
CREATE INDEX IF NOT EXISTS idx_analyses_score ON job_analyses(match_score);
CREATE INDEX IF NOT EXISTS idx_analyses_job_profile ON job_analyses(job_id, profile_id);

CREATE INDEX IF NOT EXISTS idx_applications_profile ON applications(profile_id);
CREATE INDEX IF NOT EXISTS idx_applications_method ON applications(method);
CREATE INDEX IF NOT EXISTS idx_applications_applied_at ON applications(applied_at);

CREATE INDEX IF NOT EXISTS idx_email_queue_status ON email_queue(status);
CREATE INDEX IF NOT EXISTS idx_email_queue_profile ON email_queue(profile_id);
CREATE INDEX IF NOT EXISTS idx_email_queue_job ON email_queue(job_id);

CREATE INDEX IF NOT EXISTS idx_startup_profiles_job_id ON startup_profiles(job_id);
CREATE INDEX IF NOT EXISTS idx_startup_profiles_source ON startup_profiles(source);
CREATE INDEX IF NOT EXISTS idx_startup_profiles_founding_date ON startup_profiles(founding_date);
CREATE INDEX IF NOT EXISTS idx_startup_profiles_funding_round ON startup_profiles(funding_round);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_email_queue_profile_created ON email_queue(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analyses_profile_decision ON job_analyses(profile_id, apply_decision);
CREATE INDEX IF NOT EXISTS idx_applications_profile_applied ON applications(profile_id, applied_at DESC);

CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON profiles(user_id);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_run_id ON pipeline_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created ON pipeline_runs(created_at DESC);

-- Users table — authentication credentials
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Insert default system flags
INSERT INTO system_flags (key, value) VALUES
    ('active', 'true'),
    ('naukri', 'true'),
    ('indeed', 'true'),
    ('foundit', 'true'),
    ('cold_email', 'true'),
    ('scraping', 'true')
ON CONFLICT (key) DO NOTHING;
