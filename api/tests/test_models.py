"""Tests for Pydantic request models — validation rules."""

import pytest
from pydantic import ValidationError

from api.models import (
    CreateApplicationRequest,
    EnqueueEmailRequest,
    PipelineRunRequest,
    SaveAnalysisRequest,
    SaveJobRequest,
    UpdateEmailRequest,
)

# ─── SaveJobRequest ──────────────────────────────────

def test_save_job_salary_validation():
    """salary_max must be >= salary_min."""
    with pytest.raises(ValidationError, match="salary_max"):
        SaveJobRequest(salary_min=100000, salary_max=50000)


def test_save_job_salary_valid():
    """Valid salary range passes."""
    job = SaveJobRequest(salary_min=50000, salary_max=100000)
    assert job.salary_min == 50000
    assert job.salary_max == 100000


def test_save_job_null_salaries():
    """Null salaries are allowed."""
    job = SaveJobRequest()
    assert job.salary_min is None
    assert job.salary_max is None


def test_save_job_negative_salary():
    """Negative salaries are rejected."""
    with pytest.raises(ValidationError):
        SaveJobRequest(salary_min=-1)


# ─── SaveAnalysisRequest ─────────────────────────────

def test_analysis_score_range():
    """match_score must be 0–100."""
    with pytest.raises(ValidationError):
        SaveAnalysisRequest(job_id=1, profile_id=1, match_score=101)

    with pytest.raises(ValidationError):
        SaveAnalysisRequest(job_id=1, profile_id=1, match_score=-5)


def test_analysis_valid_score():
    """Valid match_score passes."""
    a = SaveAnalysisRequest(job_id=1, profile_id=1, match_score=85)
    assert a.match_score == 85


def test_analysis_null_score():
    """Null match_score is allowed."""
    a = SaveAnalysisRequest(job_id=1, profile_id=1)
    assert a.match_score is None


def test_analysis_positive_ids():
    """job_id and profile_id must be > 0."""
    with pytest.raises(ValidationError):
        SaveAnalysisRequest(job_id=0, profile_id=1)

    with pytest.raises(ValidationError):
        SaveAnalysisRequest(job_id=1, profile_id=-1)


# ─── CreateApplicationRequest ─────────────────────────

def test_create_app_requires_method():
    """method cannot be empty."""
    with pytest.raises(ValidationError):
        CreateApplicationRequest(job_id=1, profile_id=1, method="", platform="test")


def test_create_app_valid():
    """Valid request passes."""
    app = CreateApplicationRequest(job_id=1, profile_id=1, method="cold_email", platform="email")
    assert app.method == "cold_email"


# ─── EnqueueEmailRequest ─────────────────────────────

def test_enqueue_email_requires_subject():
    """subject cannot be empty."""
    with pytest.raises(ValidationError):
        EnqueueEmailRequest(
            job_id=1, profile_id=1, recipient_email="a@b.com",
            subject="", body_html="<p>Hi</p>", body_plain="Hi",
        )


def test_enqueue_email_valid():
    """Valid email request passes."""
    e = EnqueueEmailRequest(
        job_id=1, profile_id=1, recipient_email="a@b.com",
        subject="Hello", body_html="<p>Hi</p>", body_plain="Hi",
    )
    assert e.recipient_email == "a@b.com"


# ─── UpdateEmailRequest ──────────────────────────────

def test_update_email_requires_content():
    """subject and body cannot be empty."""
    with pytest.raises(ValidationError):
        UpdateEmailRequest(subject="", body_plain="text")

    with pytest.raises(ValidationError):
        UpdateEmailRequest(subject="Subj", body_plain="")


# ─── PipelineRunRequest ──────────────────────────────

def test_pipeline_limit_bounds():
    """limit must be 1–100."""
    with pytest.raises(ValidationError):
        PipelineRunRequest(limit=0)

    with pytest.raises(ValidationError):
        PipelineRunRequest(limit=101)
