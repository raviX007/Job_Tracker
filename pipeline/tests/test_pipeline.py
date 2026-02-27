"""Tests for core.pipeline — JobPipeline and StartupScoutPipeline orchestrators."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import AppSettings
from core.models import ProfileConfig
from core.pipeline import JobPipeline, StartupScoutPipeline

# ─── Helpers ──────────────────────────────────────────────

def _make_profile() -> MagicMock:
    """Create a mock ProfileConfig for testing."""
    profile = MagicMock(spec=ProfileConfig)
    profile.cold_email = MagicMock()
    profile.cold_email.signature = "Best regards"
    return profile


def _make_settings() -> MagicMock:
    """Create a mock AppSettings for testing."""
    return MagicMock(spec=AppSettings)


def _make_job(**overrides) -> dict:
    """Create a sample job dict."""
    job = {
        "title": "Python Developer",
        "company": "TestCo",
        "location": "Remote",
        "job_url": "https://example.com/job/1",
        "source": "remotive",
        "description": "Build cool stuff with Python.",
    }
    job.update(overrides)
    return job


def _make_pipeline() -> JobPipeline:
    """Create a JobPipeline with mock dependencies."""
    return JobPipeline(
        profile=_make_profile(),
        profile_id=1,
        settings=_make_settings(),
    )


def _make_startup_pipeline() -> StartupScoutPipeline:
    """Create a StartupScoutPipeline with mock dependencies."""
    return StartupScoutPipeline(
        profile=_make_profile(),
        profile_id=1,
        settings=_make_settings(),
    )


# ─── JobPipeline.scrape ──────────────────────────────────

class TestJobPipelineScrape:
    """Tests for JobPipeline.scrape — source routing to registry functions."""

    @pytest.mark.asyncio
    @patch("core.pipeline.logger")
    async def test_scrape_all_calls_run_all(self, _mock_logger):
        """source='all' should call run_all and return its result."""
        pipe = _make_pipeline()
        mock_jobs = [_make_job(title="Job A"), _make_job(title="Job B")]

        with patch("scraper.registry.run_all", new_callable=AsyncMock, return_value=mock_jobs) as mock_run_all, \
             patch("scraper.registry.get_groups", return_value=["remote_boards"]), \
             patch("scraper.registry.get_scraper", return_value=None):
            result = await pipe.scrape("all", limit=10)

        assert result == mock_jobs
        mock_run_all.assert_awaited_once_with(pipe.profile, 10)

    @pytest.mark.asyncio
    @patch("core.pipeline.logger")
    async def test_scrape_group_calls_run_group(self, _mock_logger):
        """source matching a group name should call run_group."""
        pipe = _make_pipeline()
        mock_jobs = [_make_job(title="Group Job")]

        with patch("scraper.registry.get_groups", return_value=["remote_boards", "ats_direct"]), \
             patch("scraper.registry.run_group", new_callable=AsyncMock, return_value=mock_jobs) as mock_run_group, \
             patch("scraper.registry.get_scraper", return_value=None):
            result = await pipe.scrape("remote_boards", limit=15)

        assert result == mock_jobs
        mock_run_group.assert_awaited_once_with("remote_boards", pipe.profile, 15)

    @pytest.mark.asyncio
    @patch("core.pipeline.logger")
    async def test_scrape_individual_calls_run_scraper(self, _mock_logger):
        """source matching a single scraper name should call run_scraper."""
        pipe = _make_pipeline()
        mock_jobs = [_make_job(title="Remotive Job")]
        mock_entry = MagicMock()

        with patch("scraper.registry.get_groups", return_value=["remote_boards"]), \
             patch("scraper.registry.get_scraper", return_value=mock_entry), \
             patch("scraper.registry.run_scraper", new_callable=AsyncMock, return_value=mock_jobs) as mock_run:
            result = await pipe.scrape("remotive", limit=5)

        assert result == mock_jobs
        mock_run.assert_awaited_once_with("remotive", pipe.profile, 5)

    @pytest.mark.asyncio
    @patch("core.pipeline.logger")
    async def test_scrape_unknown_source_returns_empty(self, mock_logger):
        """Unknown source should log error and return []."""
        pipe = _make_pipeline()

        with patch("scraper.registry.get_groups", return_value=["remote_boards"]), \
             patch("scraper.registry.get_scraper", return_value=None):
            result = await pipe.scrape("nonexistent_source", limit=10)

        assert result == []
        mock_logger.error.assert_called_once()


# ─── JobPipeline.dedup ───────────────────────────────────

class TestJobPipelineDedup:
    """Tests for JobPipeline.dedup — dedup_key generation and filter_new_jobs delegation."""

    @pytest.mark.asyncio
    @patch("core.pipeline.filter_new_jobs", new_callable=AsyncMock)
    @patch("core.pipeline.make_dedup_key", return_value="generated_key_123")
    async def test_dedup_adds_missing_dedup_key(self, mock_make_key, mock_filter):
        """Jobs without dedup_key should get one via make_dedup_key."""
        pipe = _make_pipeline()
        job_no_key = _make_job(title="No Key Job")
        assert "dedup_key" not in job_no_key

        mock_filter.return_value = [job_no_key]
        result = await pipe.dedup([job_no_key])

        mock_make_key.assert_called_once_with(job_no_key)
        assert job_no_key["dedup_key"] == "generated_key_123"
        assert result == [job_no_key]

    @pytest.mark.asyncio
    @patch("core.pipeline.filter_new_jobs", new_callable=AsyncMock)
    @patch("core.pipeline.make_dedup_key")
    async def test_dedup_preserves_existing_dedup_key(self, mock_make_key, mock_filter):
        """Jobs with an existing dedup_key should not be overwritten."""
        pipe = _make_pipeline()
        job_with_key = _make_job(dedup_key="existing_key_456")

        mock_filter.return_value = [job_with_key]
        result = await pipe.dedup([job_with_key])

        mock_make_key.assert_not_called()
        assert job_with_key["dedup_key"] == "existing_key_456"
        assert result == [job_with_key]

    @pytest.mark.asyncio
    @patch("core.pipeline.filter_new_jobs", new_callable=AsyncMock)
    @patch("core.pipeline.make_dedup_key", return_value="key")
    async def test_dedup_delegates_to_filter_new_jobs(self, _mock_key, mock_filter):
        """dedup should call filter_new_jobs with the jobs list."""
        pipe = _make_pipeline()
        jobs = [_make_job(title="A"), _make_job(title="B")]
        mock_filter.return_value = [jobs[0]]

        result = await pipe.dedup(jobs)

        mock_filter.assert_awaited_once_with(jobs)
        assert len(result) == 1


# ─── JobPipeline.prefilter ───────────────────────────────

class TestJobPipelinePrefilter:
    """Tests for JobPipeline.prefilter — pre-filter + source routing."""

    @patch("core.pipeline.route_job")
    @patch("core.pipeline.apply_pre_filters")
    def test_prefilter_calls_apply_pre_filters(self, mock_apply, mock_route):
        """prefilter should call apply_pre_filters with jobs and profile."""
        pipe = _make_pipeline()
        jobs = [_make_job(title="A"), _make_job(title="B")]
        passed_jobs = [jobs[0]]
        filtered_out = [jobs[1]]
        mock_apply.return_value = (passed_jobs, filtered_out)

        result_passed, result_filtered = pipe.prefilter(jobs)

        mock_apply.assert_called_once_with(jobs, pipe.profile)
        assert result_passed == passed_jobs
        assert result_filtered == filtered_out

    @patch("core.pipeline.route_job")
    @patch("core.pipeline.apply_pre_filters")
    def test_prefilter_routes_each_passed_job(self, mock_apply, mock_route):
        """prefilter should call route_job on every passed job."""
        pipe = _make_pipeline()
        jobs = [_make_job(title="A"), _make_job(title="B"), _make_job(title="C")]
        passed = [jobs[0], jobs[2]]
        mock_apply.return_value = (passed, [jobs[1]])

        pipe.prefilter(jobs)

        assert mock_route.call_count == 2
        mock_route.assert_any_call(jobs[0], pipe.profile)
        mock_route.assert_any_call(jobs[2], pipe.profile)

    @patch("core.pipeline.route_job")
    @patch("core.pipeline.apply_pre_filters")
    def test_prefilter_no_passed_jobs_skips_routing(self, mock_apply, mock_route):
        """If no jobs pass pre-filter, route_job should not be called."""
        pipe = _make_pipeline()
        jobs = [_make_job()]
        mock_apply.return_value = ([], jobs)

        passed, filtered = pipe.prefilter(jobs)

        assert passed == []
        mock_route.assert_not_called()


# ─── JobPipeline.save ────────────────────────────────────

class TestJobPipelineSave:
    """Tests for JobPipeline.save — saving jobs and analyses to DB."""

    @pytest.mark.asyncio
    @patch("core.pipeline.save_analysis", new_callable=AsyncMock)
    @patch("core.pipeline.save_job", new_callable=AsyncMock)
    async def test_save_saves_job_and_analysis(self, mock_save_job, mock_save_analysis):
        """save should call save_job and save_analysis for each job with analysis."""
        pipe = _make_pipeline()
        job = _make_job(
            analysis={"match_score": 85, "apply_decision": "YES"},
            embedding_score=0.9,
            route_action="apply_and_cold_email",
        )
        mock_save_job.return_value = 42

        saved = await pipe.save([job])

        assert saved == 1
        mock_save_job.assert_awaited_once_with(job)
        mock_save_analysis.assert_awaited_once_with(
            42, 1,
            job["analysis"],
            embedding_score=0.9,
            route_action="apply_and_cold_email",
        )
        assert job["db_job_id"] == 42

    @pytest.mark.asyncio
    @patch("core.pipeline.save_analysis", new_callable=AsyncMock)
    @patch("core.pipeline.save_job", new_callable=AsyncMock)
    async def test_save_skips_when_save_job_returns_none(self, mock_save_job, mock_save_analysis):
        """save should skip save_analysis if save_job returns None."""
        pipe = _make_pipeline()
        job = _make_job(analysis={"match_score": 50})
        mock_save_job.return_value = None

        saved = await pipe.save([job])

        assert saved == 0
        mock_save_job.assert_awaited_once()
        mock_save_analysis.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("core.pipeline.save_analysis", new_callable=AsyncMock)
    @patch("core.pipeline.save_job", new_callable=AsyncMock)
    async def test_save_skips_when_no_analysis(self, mock_save_job, mock_save_analysis):
        """save should skip save_analysis if job has no analysis dict."""
        pipe = _make_pipeline()
        job = _make_job()  # no "analysis" key
        mock_save_job.return_value = 99

        saved = await pipe.save([job])

        assert saved == 0
        mock_save_job.assert_awaited_once()
        mock_save_analysis.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("core.pipeline.save_analysis", new_callable=AsyncMock)
    @patch("core.pipeline.save_job", new_callable=AsyncMock)
    async def test_save_counts_multiple_successes(self, mock_save_job, mock_save_analysis):
        """save should count all successfully saved jobs."""
        pipe = _make_pipeline()
        jobs = [
            _make_job(title="A", analysis={"score": 90}),
            _make_job(title="B", analysis={"score": 70}),
            _make_job(title="C"),  # no analysis
        ]
        mock_save_job.side_effect = [10, 20, 30]

        saved = await pipe.save(jobs)

        assert saved == 2
        assert mock_save_job.await_count == 3
        assert mock_save_analysis.await_count == 2


# ─── JobPipeline.run ─────────────────────────────────────

class TestJobPipelineRun:
    """Tests for JobPipeline.run — full pipeline orchestration and stats."""

    @pytest.mark.asyncio
    async def test_run_full_pipeline_populates_stats(self):
        """run() should call all stages in order and return correct stats."""
        pipe = _make_pipeline()

        raw = [_make_job(title="A"), _make_job(title="B"), _make_job(title="C")]
        new = [_make_job(title="A"), _make_job(title="B")]
        filtered = [_make_job(title="A")]
        embedded = [_make_job(title="A")]
        analyzed = [_make_job(title="A", analysis={"score": 90})]

        with patch.object(pipe, "scrape", new_callable=AsyncMock, return_value=raw), \
             patch.object(pipe, "dedup", new_callable=AsyncMock, return_value=new), \
             patch.object(pipe, "prefilter", return_value=(filtered, [])), \
             patch.object(pipe, "embed", new_callable=AsyncMock, return_value=(embedded, [])), \
             patch.object(pipe, "analyze", new_callable=AsyncMock, return_value=analyzed), \
             patch.object(pipe, "save", new_callable=AsyncMock, return_value=1), \
             patch.object(pipe, "generate_emails", new_callable=AsyncMock, return_value=1), \
             patch("core.pipeline.logger"):

            stats = await pipe.run(source="all", limit=20)

        assert stats["scraped"] == 3
        assert stats["deduped"] == 2
        assert stats["pre_filtered"] == 1
        assert stats["embed_passed"] == 1
        assert stats["analyzed"] == 1
        assert stats["saved"] == 1
        assert stats["emails_queued"] == 1
        assert stats["errors"] == []

    @pytest.mark.asyncio
    async def test_run_early_exit_on_empty_scrape(self):
        """run() should return early if scrape returns []."""
        pipe = _make_pipeline()

        with patch.object(pipe, "scrape", new_callable=AsyncMock, return_value=[]), \
             patch.object(pipe, "dedup", new_callable=AsyncMock) as mock_dedup, \
             patch("core.pipeline.logger"):

            stats = await pipe.run(source="all", limit=10)

        assert stats["scraped"] == 0
        mock_dedup.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_early_exit_on_empty_dedup(self):
        """run() should return early if dedup returns []."""
        pipe = _make_pipeline()

        with patch.object(pipe, "scrape", new_callable=AsyncMock, return_value=[_make_job()]), \
             patch.object(pipe, "dedup", new_callable=AsyncMock, return_value=[]), \
             patch.object(pipe, "prefilter") as mock_prefilter, \
             patch("core.pipeline.logger"):

            stats = await pipe.run(source="all", limit=10)

        assert stats["scraped"] == 1
        assert stats["deduped"] == 0
        mock_prefilter.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_early_exit_on_empty_prefilter(self):
        """run() should return early if prefilter returns no passed jobs."""
        pipe = _make_pipeline()

        with patch.object(pipe, "scrape", new_callable=AsyncMock, return_value=[_make_job()]), \
             patch.object(pipe, "dedup", new_callable=AsyncMock, return_value=[_make_job()]), \
             patch.object(pipe, "prefilter", return_value=([], [_make_job()])), \
             patch.object(pipe, "embed", new_callable=AsyncMock) as mock_embed, \
             patch("core.pipeline.logger"):

            stats = await pipe.run(source="all", limit=10)

        assert stats["pre_filtered"] == 0
        mock_embed.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_early_exit_on_empty_embed(self):
        """run() should return early if embed returns no passed jobs."""
        pipe = _make_pipeline()

        with patch.object(pipe, "scrape", new_callable=AsyncMock, return_value=[_make_job()]), \
             patch.object(pipe, "dedup", new_callable=AsyncMock, return_value=[_make_job()]), \
             patch.object(pipe, "prefilter", return_value=([_make_job()], [])), \
             patch.object(pipe, "embed", new_callable=AsyncMock, return_value=([], [_make_job()])), \
             patch.object(pipe, "analyze", new_callable=AsyncMock) as mock_analyze, \
             patch("core.pipeline.logger"):

            stats = await pipe.run(source="all", limit=10)

        assert stats["embed_passed"] == 0
        mock_analyze.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_scrape_failure_populates_errors(self):
        """run() should catch scrape exceptions, populate errors, and return early."""
        pipe = _make_pipeline()

        with patch.object(pipe, "scrape", new_callable=AsyncMock, side_effect=RuntimeError("Network down")), \
             patch.object(pipe, "dedup", new_callable=AsyncMock) as mock_dedup, \
             patch("core.pipeline.logger"):

            stats = await pipe.run(source="all", limit=10)

        assert stats["scraped"] == 0
        assert len(stats["errors"]) == 1
        assert "Scraping failed" in stats["errors"][0]
        assert "Network down" in stats["errors"][0]
        mock_dedup.assert_not_awaited()


# ─── StartupScoutPipeline.scrape ─────────────────────────

class TestStartupScoutPipelineScrape:
    """Tests for StartupScoutPipeline.scrape — startup source routing."""

    @pytest.mark.asyncio
    @patch("core.pipeline.logger")
    async def test_scrape_startup_scout_calls_run_group(self, _mock_logger):
        """source='startup_scout' should call run_group('startup_scout', ...)."""
        pipe = _make_startup_pipeline()
        mock_startups = [_make_job(title="Startup A")]

        with patch("scraper.registry.run_group", new_callable=AsyncMock, return_value=mock_startups) as mock_run_group, \
             patch("scraper.registry.get_scraper", return_value=None):
            result = await pipe.scrape("startup_scout", limit=50)

        assert result == mock_startups
        mock_run_group.assert_awaited_once_with("startup_scout", pipe.profile, 50)

    @pytest.mark.asyncio
    @patch("core.pipeline.logger")
    async def test_scrape_individual_startup_source(self, _mock_logger):
        """A known individual scraper name should call run_scraper."""
        pipe = _make_startup_pipeline()
        mock_startups = [_make_job(title="YC Startup")]
        mock_entry = MagicMock()

        with patch("scraper.registry.get_scraper", return_value=mock_entry), \
             patch("scraper.registry.run_scraper", new_callable=AsyncMock, return_value=mock_startups) as mock_run:
            result = await pipe.scrape("yc_directory", limit=25)

        assert result == mock_startups
        mock_run.assert_awaited_once_with("yc_directory", pipe.profile, 25)

    @pytest.mark.asyncio
    @patch("core.pipeline.logger")
    async def test_scrape_unknown_source_returns_empty(self, mock_logger):
        """Unknown source should log error and return []."""
        pipe = _make_startup_pipeline()

        with patch("scraper.registry.get_scraper", return_value=None), \
             patch("scraper.registry.get_group", return_value=[]):
            result = await pipe.scrape("nonexistent_startup_source", limit=10)

        assert result == []
        mock_logger.error.assert_called_once()


# ─── StartupScoutPipeline.run ────────────────────────────

class TestStartupScoutPipelineRun:
    """Tests for StartupScoutPipeline.run — full pipeline orchestration."""

    @pytest.mark.asyncio
    async def test_run_full_pipeline_populates_stats(self):
        """run() should call all stages and return correct stats."""
        pipe = _make_startup_pipeline()

        raw = [_make_job(title="S1"), _make_job(title="S2"), _make_job(title="S3")]
        new = [_make_job(title="S1"), _make_job(title="S2")]
        relevant = [_make_job(title="S1", analysis={"score": 80})]
        eligible = [_make_job(title="S1", db_job_id=10)]

        with patch.object(pipe, "scrape", new_callable=AsyncMock, return_value=raw), \
             patch.object(pipe, "dedup", new_callable=AsyncMock, return_value=new), \
             patch.object(pipe, "analyze_and_save", new_callable=AsyncMock, return_value=(relevant, eligible)), \
             patch.object(pipe, "find_and_email", new_callable=AsyncMock, return_value=1), \
             patch("core.pipeline.logger"):

            stats = await pipe.run(source="startup_scout", limit=50)

        assert stats["scraped"] == 3
        assert stats["deduped"] == 2
        assert stats["relevant"] == 1
        assert stats["email_eligible"] == 1
        assert stats["emails_queued"] == 1
        assert stats["errors"] == []

    @pytest.mark.asyncio
    async def test_run_early_exit_on_empty_scrape(self):
        """run() should return early if scrape returns []."""
        pipe = _make_startup_pipeline()

        with patch.object(pipe, "scrape", new_callable=AsyncMock, return_value=[]), \
             patch.object(pipe, "dedup", new_callable=AsyncMock) as mock_dedup, \
             patch("core.pipeline.logger"):

            stats = await pipe.run(source="startup_scout", limit=50)

        assert stats["scraped"] == 0
        mock_dedup.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_early_exit_on_empty_dedup(self):
        """run() should return early if dedup returns []."""
        pipe = _make_startup_pipeline()

        with patch.object(pipe, "scrape", new_callable=AsyncMock, return_value=[_make_job()]), \
             patch.object(pipe, "dedup", new_callable=AsyncMock, return_value=[]), \
             patch.object(pipe, "analyze_and_save", new_callable=AsyncMock) as mock_analyze, \
             patch("core.pipeline.logger"):

            stats = await pipe.run(source="startup_scout", limit=50)

        assert stats["scraped"] == 1
        assert stats["deduped"] == 0
        mock_analyze.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_scrape_failure_populates_errors(self):
        """run() should catch scrape exceptions and populate errors."""
        pipe = _make_startup_pipeline()

        with patch.object(pipe, "scrape", new_callable=AsyncMock, side_effect=ConnectionError("API down")), \
             patch.object(pipe, "dedup", new_callable=AsyncMock) as mock_dedup, \
             patch("core.pipeline.logger"):

            stats = await pipe.run(source="startup_scout", limit=50)

        assert stats["scraped"] == 0
        assert len(stats["errors"]) == 1
        assert "Scraping failed" in stats["errors"][0]
        assert "API down" in stats["errors"][0]
        mock_dedup.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_default_parameters(self):
        """run() should use source='startup_scout' and limit=50 by default."""
        pipe = _make_startup_pipeline()

        with patch.object(pipe, "scrape", new_callable=AsyncMock, return_value=[]) as mock_scrape, \
             patch("core.pipeline.logger"):

            await pipe.run()

        mock_scrape.assert_awaited_once_with("startup_scout", 50)
