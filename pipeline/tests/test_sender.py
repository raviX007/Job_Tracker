"""Tests for email sender — warmup schedule, safety gates, rate limiting."""

import os
import sys
from datetime import date
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.constants import WARMUP_SCHEDULE
from emailer.sender import EmailSender

# ─── Warmup Schedule ─────────────────────────────────────

class TestWarmupSchedule:
    """Warmup schedule ramps up over 4 weeks."""

    def test_week_1_limit(self):
        sender = EmailSender()
        sender.warmup_start_date = date.today()
        limit = sender.get_warmup_limit()
        assert limit == WARMUP_SCHEDULE[1]

    def test_week_2_limit(self):
        sender = EmailSender()
        sender.warmup_start_date = date.today()
        with patch("emailer.sender.date") as mock_date:
            mock_date.today.return_value = date.fromordinal(
                sender.warmup_start_date.toordinal() + 7
            )
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            limit = sender.get_warmup_limit()
        assert limit == WARMUP_SCHEDULE[2]

    def test_warmup_capped_by_max_per_day(self):
        sender = EmailSender()
        sender.max_per_day = 3  # Lower than any warmup value
        sender.warmup_start_date = date.today()
        limit = sender.get_warmup_limit()
        assert limit == 3

    def test_constants_match(self):
        """Warmup schedule should have 4 weeks."""
        assert len(WARMUP_SCHEDULE) == 4
        assert WARMUP_SCHEDULE[1] < WARMUP_SCHEDULE[4]


# ─── Safety Gates ─────────────────────────────────────────

class TestCanSend:
    """Safety gates block sending in various conditions."""

    def test_dry_run_blocks(self):
        sender = EmailSender()
        sender.dry_run = True
        sender.email_enabled = True
        sender.gmail_address = "test@gmail.com"
        sender.gmail_app_password = "pass"
        can, reason = sender.can_send()
        assert can is False
        assert "DRY_RUN" in reason

    def test_email_disabled_blocks(self):
        sender = EmailSender()
        sender.dry_run = False
        sender.email_enabled = False
        sender.gmail_address = "test@gmail.com"
        sender.gmail_app_password = "pass"
        can, reason = sender.can_send()
        assert can is False
        assert "EMAIL_SENDING_ENABLED" in reason

    def test_missing_credentials_blocks(self):
        sender = EmailSender()
        sender.dry_run = False
        sender.email_enabled = True
        sender.gmail_address = ""
        sender.gmail_app_password = ""
        can, reason = sender.can_send()
        assert can is False
        assert "credentials" in reason

    def test_daily_limit_blocks(self):
        sender = EmailSender()
        sender.dry_run = False
        sender.email_enabled = True
        sender.gmail_address = "test@gmail.com"
        sender.gmail_app_password = "pass"
        sender.max_per_day = 5
        sender.sent_today = 5
        sender.last_send_date = date.today()
        sender.warmup_start_date = date.today()
        can, reason = sender.can_send()
        assert can is False

    def test_hourly_limit_blocks(self):
        sender = EmailSender()
        sender.dry_run = False
        sender.email_enabled = True
        sender.gmail_address = "test@gmail.com"
        sender.gmail_app_password = "pass"
        sender.max_per_hour = 2
        sender.sent_this_hour = 2
        from datetime import datetime
        sender.last_send_hour = datetime.now().hour
        sender.last_send_date = date.today()
        sender.warmup_start_date = date.today()
        can, reason = sender.can_send()
        assert can is False
        assert "Hourly" in reason

    def test_all_gates_pass(self):
        sender = EmailSender()
        sender.dry_run = False
        sender.email_enabled = True
        sender.gmail_address = "test@gmail.com"
        sender.gmail_app_password = "pass"
        sender.max_per_day = 50
        sender.max_per_hour = 20
        sender.sent_today = 0
        sender.sent_this_hour = 0
        sender.warmup_start_date = date.today()
        can, reason = sender.can_send()
        assert can is True
        assert reason == "OK"


# ─── Counter Reset ────────────────────────────────────────

class TestCounterReset:
    """Counters reset at date/hour boundaries."""

    def test_daily_counter_resets_on_new_day(self):
        sender = EmailSender()
        sender.sent_today = 10
        sender.last_send_date = date.fromordinal(date.today().toordinal() - 1)
        sender._reset_counters()
        assert sender.sent_today == 0

    def test_daily_counter_persists_same_day(self):
        sender = EmailSender()
        sender.sent_today = 5
        sender.last_send_date = date.today()
        sender._reset_counters()
        assert sender.sent_today == 5


# ─── Scraper Utils ────────────────────────────────────────

class TestScraperUtils:
    """Test shared scraper utility functions."""

    def test_build_skill_set_includes_generic_terms(self):
        from core.models import ProfileConfig
        from scraper.utils import build_skill_set

        profile = ProfileConfig(
            candidate={
                "name": "Test", "email": "t@t.com", "phone": "123",
                "resume_path": "/tmp/r.pdf", "location": "Bengaluru",
            },
            search_preferences={"locations": ["Bengaluru"]},
            skills={"primary": ["Python", "Django"]},
            experience={"graduation_year": 2023, "degree": "B.Tech"},
            filters={"must_have_any": ["python"]},
        )
        skills = build_skill_set(profile)
        assert "python" in skills
        assert "django" in skills
        assert "developer" in skills
        assert "engineer" in skills
        assert "software" in skills

    def test_strip_html(self):
        from scraper.utils import strip_html
        assert strip_html("<p>Hello <b>World</b></p>") == "Hello World"
        assert strip_html("&amp; &lt;") == "& <"

    def test_parse_date_iso(self):
        from scraper.utils import parse_date_iso
        result = parse_date_iso("2024-01-15")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1

    def test_parse_date_iso_none(self):
        from scraper.utils import parse_date_iso
        assert parse_date_iso(None) is None
        assert parse_date_iso("") is None

    def test_parse_salary_value(self):
        from scraper.utils import parse_salary_value
        assert parse_salary_value(50000) == 50000
        assert parse_salary_value("60000") == 60000
        assert parse_salary_value(None) is None
        assert parse_salary_value("not-a-number") is None

    def test_check_relevance(self):
        from scraper.utils import check_relevance
        skills = {"python", "django", "developer"}
        assert check_relevance("Python Developer", "", skills) is True
        assert check_relevance("Chef Cook", "", skills) is False
        assert check_relevance("", "We need a python developer", skills) is True

    def test_is_short_description(self):
        from scraper.utils import is_short_description
        assert is_short_description("short") is True
        assert is_short_description("x" * 100) is False
