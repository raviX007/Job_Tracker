"""Pipeline orchestrators — JobPipeline and StartupScoutPipeline.

Each pipeline is a class with staged methods that can be called individually
or as a complete run. All DB operations go through the FastAPI backend.

Usage:
    # Full pipeline
    async with APIClient(base_url, api_key) as api:
        pipeline = JobPipeline(profile, profile_id, settings)
        stats = await pipeline.run(source="all", limit=20)

    # Individual stages
    jobs = await pipeline.scrape("remotive", limit=10)
    new_jobs = await pipeline.dedup(jobs)
"""

from analyzer.embedding_filter import filter_by_embedding
from analyzer.freshness_filter import apply_pre_filters
from analyzer.llm_analyzer import analyze_jobs_batch
from config.settings import AppSettings
from core.api_client import (
    advance_to_ready,
    enqueue_email,
    filter_new_jobs,
    mark_verified,
    save_analysis,
    save_job,
    save_startup_profile,
    update_cover_letter,
)
from core.constants import NON_COMPANY_DOMAINS, STARTUP_MAX_AGE_MONTHS
from core.logger import logger
from core.models import ProfileConfig
from core.utils import mask_email
from scraper.dedup import make_dedup_key
from scraper.source_router import route_job


class JobPipeline:
    """Main pipeline: scrape → dedup → pre-filter → embed → LLM analyze → save → email."""

    def __init__(
        self,
        profile: ProfileConfig,
        profile_id: int,
        settings: AppSettings,
    ):
        self.profile = profile
        self.profile_id = profile_id
        self.settings = settings

    async def scrape(self, source: str, limit: int) -> list[dict]:
        """Stage 1: Scrape jobs from specified source."""
        from scraper.registry import get_groups, get_scraper, run_all, run_group, run_scraper

        if source == "all":
            return await run_all(self.profile, limit)
        elif source in get_groups():
            return await run_group(source, self.profile, limit)
        elif get_scraper(source):
            return await run_scraper(source, self.profile, limit)
        else:
            logger.error(f"Unknown scraper source: '{source}'")
            return []

    async def dedup(self, jobs: list[dict]) -> list[dict]:
        """Stage 2: Dedup against DB via API."""
        for job in jobs:
            if "dedup_key" not in job:
                job["dedup_key"] = make_dedup_key(job)
        return await filter_new_jobs(jobs)

    def prefilter(self, jobs: list[dict]) -> tuple[list[dict], list[dict]]:
        """Stage 3: Pre-filter (freshness, title skip, keywords) + source routing."""
        passed, filtered_out = apply_pre_filters(jobs, self.profile)
        for job in passed:
            route_job(job, self.profile)
        return passed, filtered_out

    async def embed(self, jobs: list[dict]) -> tuple[list[dict], list[dict]]:
        """Stage 4: Embedding similarity filter."""
        return await filter_by_embedding(jobs, self.profile)

    async def analyze(self, jobs: list[dict]) -> list[dict]:
        """Stage 5: LLM analysis."""
        return await analyze_jobs_batch(jobs, self.profile)

    async def save(self, analyzed_jobs: list[dict]) -> int:
        """Stage 6: Save jobs + analyses to DB via API."""
        saved = 0
        for job in analyzed_jobs:
            job_id = await save_job(job)
            if job_id and job.get("analysis"):
                await save_analysis(
                    job_id, self.profile_id,
                    job["analysis"],
                    embedding_score=job.get("embedding_score"),
                    route_action=job.get("route_action"),
                )
                job["db_job_id"] = job_id
                saved += 1
        return saved

    async def generate_emails(self, analyzed_jobs: list[dict]) -> int:
        """Stage 7: Generate cover letters + cold emails, queue via API."""
        from emailer.cold_email import generate_cold_email
        from emailer.cover_letter import generate_cover_letter
        from emailer.email_finder import find_emails
        from emailer.validator import validate_generated_content
        from emailer.verifier import verify_email as verify_email_address

        queued = 0
        for job in analyzed_jobs:
            analysis = job.get("analysis", {})
            decision = analysis.get("apply_decision", "")
            route = job.get("route_action", "")
            job_id = job.get("db_job_id")

            if decision == "NO" or "cold_email" not in route or not job_id:
                continue

            company = job.get("company", "")
            title = job.get("title", "")
            score = analysis.get("match_score", 0)

            try:
                # Find recipient email
                candidates = await find_emails(
                    company_name=company,
                    job_url=job.get("job_url", ""),
                    high_value=score >= 80,
                )
                if not candidates:
                    continue

                top = candidates[0]
                verification = await verify_email_address(top.email)

                # Generate cold email
                email_content = await generate_cold_email(
                    job, analysis, self.profile,
                    recipient_name=top.name, recipient_role=top.role,
                )
                if not email_content:
                    continue

                # Validate (anti-hallucination)
                validation = validate_generated_content(email_content["body_plain"], self.profile)
                if not validation.is_valid:
                    logger.warning(f"Email for {company} failed validation: {validation.issues}")
                    continue

                # Generate cover letter
                cover_letter = await generate_cover_letter(job, analysis, self.profile)
                if cover_letter:
                    await update_cover_letter(job_id, self.profile_id, cover_letter)

                # Queue email
                entry_id = await enqueue_email(
                    job_id=job_id,
                    profile_id=self.profile_id,
                    recipient_email=top.email,
                    recipient_name=top.name,
                    recipient_role=top.role,
                    recipient_source=top.source,
                    subject=email_content["subject"],
                    body_html=email_content["body_html"],
                    body_plain=email_content["body_plain"],
                    signature=self.profile.cold_email.signature,
                    resume_path="",
                    email_verified=verification.is_valid,
                    verification_result=verification.status,
                    verification_provider=verification.provider,
                )

                if entry_id:
                    if verification.is_valid:
                        await mark_verified(entry_id, verification.status, verification.provider)
                    await advance_to_ready(entry_id)
                    queued += 1
                    logger.info(f"Queued email: {company} → {mask_email(top.email)}")

            except Exception as e:
                logger.error(f"Email pipeline failed for {company}: {e}")

        return queued

    async def run(self, source: str = "all", limit: int = 20) -> dict:
        """Run the full pipeline end-to-end. Returns stats dict."""
        stats = {
            "scraped": 0, "deduped": 0, "pre_filtered": 0,
            "embed_passed": 0, "analyzed": 0, "saved": 0,
            "emails_queued": 0, "errors": [],
        }

        # Scrape
        try:
            raw_jobs = await self.scrape(source, limit)
            stats["scraped"] = len(raw_jobs)
        except Exception as e:
            stats["errors"].append(f"Scraping failed: {e}")
            return stats

        if not raw_jobs:
            return stats

        # Dedup
        new_jobs = await self.dedup(raw_jobs)
        stats["deduped"] = len(new_jobs)
        if not new_jobs:
            return stats

        # Pre-filter
        filtered, _ = self.prefilter(new_jobs)
        stats["pre_filtered"] = len(filtered)
        if not filtered:
            return stats

        # Embed
        passed, _ = await self.embed(filtered)
        stats["embed_passed"] = len(passed)
        if not passed:
            return stats

        # Analyze
        analyzed = await self.analyze(passed)
        stats["analyzed"] = len(analyzed)

        # Save
        stats["saved"] = await self.save(analyzed)

        # Emails
        stats["emails_queued"] = await self.generate_emails(analyzed)

        logger.info(
            f"Pipeline complete: {stats['scraped']} scraped → "
            f"{stats['deduped']} new → {stats['pre_filtered']} filtered → "
            f"{stats['embed_passed']} embed → {stats['analyzed']} analyzed → "
            f"{stats['emails_queued']} emails"
        )
        return stats


class StartupScoutPipeline:
    """Startup Scout pipeline: scrape → dedup → LLM relevance → email founders."""

    def __init__(
        self,
        profile: ProfileConfig,
        profile_id: int,
        settings: AppSettings,
    ):
        self.profile = profile
        self.profile_id = profile_id
        self.settings = settings

    async def scrape(self, source: str, limit: int) -> list[dict]:
        """Stage 1: Scrape startups from specified source."""
        from scraper.registry import get_scraper, run_group, run_scraper

        if source == "startup_scout":
            return await run_group("startup_scout", self.profile, limit)
        elif get_scraper(source):
            return await run_scraper(source, self.profile, limit)
        else:
            from scraper.registry import get_group
            entries = get_group("startup_scout")
            names = [e.name for e in entries]
            logger.error(f"Unknown source: '{source}'. Use: startup_scout, {', '.join(names)}")
            return []

    async def dedup(self, startups: list[dict]) -> list[dict]:
        """Stage 2: Dedup against DB via API."""
        for s in startups:
            if "dedup_key" not in s:
                s["dedup_key"] = make_dedup_key(s)
        return await filter_new_jobs(startups)

    async def analyze_and_save(self, startups: list[dict]) -> tuple[list[dict], list[dict]]:
        """Stage 3: LLM relevance analysis + save jobs/analyses/profiles.

        Returns (all_relevant, email_eligible) — email_eligible is age-filtered.
        """
        from scripts._startup_analyzer import analyze_startup_relevance

        from core.startup_utils import _build_startup_profile

        relevant = []
        email_eligible = []

        for startup in startups:
            analysis = await analyze_startup_relevance(startup, self.profile)
            if not analysis:
                continue

            startup["analysis"] = analysis
            relevant.append(startup)

            # Save to DB
            job_id = await save_job(startup)
            if not job_id:
                continue

            await save_analysis(
                job_id, self.profile_id, analysis,
                embedding_score=None, route_action="cold_email_only",
            )
            startup["db_job_id"] = job_id

            # Build and save startup profile
            llm_profile = analysis.get("startup_profile", {})
            profile_data = _build_startup_profile(startup, llm_profile, job_id)
            await save_startup_profile(profile_data)
            startup["startup_profile_data"] = profile_data

            # Age filter
            age = profile_data.get("age_months")
            if age is None or age > STARTUP_MAX_AGE_MONTHS:
                reason = "age unknown" if age is None else f"{age}mo (>{STARTUP_MAX_AGE_MONTHS})"
                logger.info(f"Skipping {startup.get('company', '?')} — {reason}")
                continue
            email_eligible.append(startup)

        return relevant, email_eligible

    async def find_and_email(self, eligible: list[dict]) -> int:
        """Stage 4: Find founder emails, generate cold emails, queue."""
        from emailer.email_finder import find_emails
        from emailer.validator import validate_generated_content
        from emailer.verifier import verify_email as verify_email_address
        from scripts._startup_analyzer import generate_startup_cold_email

        queued = 0
        for startup in eligible:
            job_id = startup.get("db_job_id")
            if not job_id:
                continue

            company = startup.get("company", "")
            analysis = startup.get("analysis", {})
            sp_data = startup.get("startup_profile_data", {})
            founder_name = analysis.get("founder_name", "")
            founder_role = analysis.get("founder_role", "")

            if not founder_name and sp_data.get("founder_names"):
                founder_name = sp_data["founder_names"][0]
                founder_role = sp_data["founder_roles"][0] if sp_data.get("founder_roles") else ""

            try:
                job_url = startup.get("job_url", "")
                if any(d in job_url for d in NON_COMPANY_DOMAINS):
                    job_url = ""

                candidates = await find_emails(
                    company_name=company, job_url=job_url,
                    recruiter_name=founder_name, high_value=True,
                )
                if not candidates:
                    logger.info(f"No email found for {company}")
                    continue

                top = candidates[0]
                verification = await verify_email_address(top.email)

                recipient_name = founder_name or top.name
                recipient_role = founder_role or top.role

                email_content = await generate_startup_cold_email(
                    startup, analysis, self.profile,
                    startup_profile=sp_data or None,
                    recipient_name=recipient_name,
                    recipient_role=recipient_role,
                )
                if not email_content:
                    continue

                validation = validate_generated_content(email_content["body_plain"], self.profile)
                if not validation.is_valid:
                    logger.warning(f"Email for {company} failed validation: {validation.issues}")
                    continue

                entry_id = await enqueue_email(
                    job_id=job_id,
                    profile_id=self.profile_id,
                    recipient_email=top.email,
                    recipient_name=recipient_name,
                    recipient_role=recipient_role,
                    recipient_source=top.source,
                    subject=email_content["subject"],
                    body_html=email_content["body_html"],
                    body_plain=email_content["body_plain"],
                    signature=self.profile.cold_email.signature,
                    email_verified=verification.is_valid,
                    verification_result=verification.status,
                    verification_provider=verification.provider,
                )

                if entry_id:
                    if verification.is_valid:
                        await mark_verified(entry_id, verification.status, verification.provider)
                    await advance_to_ready(entry_id)
                    queued += 1
                    logger.info(f"Queued: {company} → {mask_email(top.email)}")

            except Exception as e:
                logger.error(f"Email pipeline failed for {company}: {e}")

        return queued

    async def run(self, source: str = "startup_scout", limit: int = 50) -> dict:
        """Run the full startup scout pipeline. Returns stats dict."""
        stats = {
            "scraped": 0, "deduped": 0, "relevant": 0,
            "email_eligible": 0, "emails_queued": 0, "errors": [],
        }

        # Scrape
        try:
            raw = await self.scrape(source, limit)
            stats["scraped"] = len(raw)
        except Exception as e:
            stats["errors"].append(f"Scraping failed: {e}")
            return stats

        if not raw:
            return stats

        # Dedup
        new = await self.dedup(raw)
        stats["deduped"] = len(new)
        if not new:
            return stats

        # Analyze + save
        relevant, eligible = await self.analyze_and_save(new)
        stats["relevant"] = len(relevant)
        stats["email_eligible"] = len(eligible)

        # Email
        stats["emails_queued"] = await self.find_and_email(eligible)

        logger.info(
            f"Startup Scout complete: {stats['scraped']} scraped → "
            f"{stats['deduped']} new → {stats['relevant']} relevant → "
            f"{stats['email_eligible']} eligible → {stats['emails_queued']} emails"
        )
        return stats
