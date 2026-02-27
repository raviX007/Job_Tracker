"""Email sender — Gmail SMTP with rate limits, warmup, and safety gates.

DOUBLE SAFETY:
1. DRY_RUN=true → logs but doesn't send
2. EMAIL_SENDING_ENABLED=false → composes but doesn't send

Both must be explicitly disabled for emails to actually go out.
Warmup schedule gradually increases daily send limit over 4 weeks.
"""

import asyncio
import os
import random
from datetime import date, datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib

from core.constants import WARMUP_SCHEDULE
from core.logger import logger


class EmailSender:
    """Gmail SMTP sender with rate limiting and warmup."""

    def __init__(self):
        self.gmail_address = os.getenv("GMAIL_ADDRESS", "")
        self.gmail_app_password = os.getenv("GMAIL_APP_PASSWORD", "")
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        self.email_enabled = os.getenv("EMAIL_SENDING_ENABLED", "false").lower() == "true"
        self.delay_sec = int(os.getenv("COLD_EMAIL_DELAY_SECONDS", "5"))
        self.max_per_hour = int(os.getenv("COLD_EMAIL_MAX_PER_HOUR", "8"))
        self.max_per_day = int(os.getenv("COLD_EMAIL_MAX_PER_DAY", "12"))

        # Tracking
        self.sent_today = 0
        self.sent_this_hour = 0
        self.last_send_date = None
        self.last_send_hour = None
        self.warmup_start_date = None

    def _reset_counters(self):
        """Reset send counters at date/hour boundaries."""
        now = datetime.now()
        today = now.date()
        current_hour = now.hour

        if self.last_send_date != today:
            self.sent_today = 0
            self.last_send_date = today

        if self.last_send_hour != current_hour:
            self.sent_this_hour = 0
            self.last_send_hour = current_hour

    def get_warmup_limit(self) -> int:
        """Get the current daily limit based on warmup schedule."""
        if not self.warmup_start_date:
            self.warmup_start_date = date.today()

        days_active = (date.today() - self.warmup_start_date).days
        week = (days_active // 7) + 1

        for w in sorted(WARMUP_SCHEDULE.keys(), reverse=True):
            if week >= w:
                return min(WARMUP_SCHEDULE[w], self.max_per_day)

        return WARMUP_SCHEDULE[1]

    def can_send(self) -> tuple[bool, str]:
        """Check if we can send an email right now."""
        # Gate 1: DRY_RUN
        if self.dry_run:
            return False, "DRY_RUN is enabled"

        # Gate 2: EMAIL_SENDING_ENABLED
        if not self.email_enabled:
            return False, "EMAIL_SENDING_ENABLED is false"

        # Gate 3: Gmail credentials
        if not self.gmail_address or not self.gmail_app_password:
            return False, "Gmail credentials not configured"

        self._reset_counters()

        # Gate 4: Warmup limit
        warmup_limit = self.get_warmup_limit()
        if self.sent_today >= warmup_limit:
            return False, f"Warmup limit reached ({warmup_limit}/day)"

        # Gate 5: Daily limit
        if self.sent_today >= self.max_per_day:
            return False, f"Daily limit reached ({self.max_per_day}/day)"

        # Gate 6: Hourly limit
        if self.sent_this_hour >= self.max_per_hour:
            return False, f"Hourly limit reached ({self.max_per_hour}/hour)"

        return True, "OK"

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_plain: str,
        resume_path: str | None = None,
    ) -> tuple[bool, str]:
        """Send an email via Gmail SMTP.

        Returns: (success, message)
        """
        can, reason = self.can_send()
        if not can:
            logger.info(f"Email NOT sent to {to_email}: {reason}")
            return False, reason

        try:
            # Build message
            msg = MIMEMultipart("alternative")
            msg["From"] = self.gmail_address
            msg["To"] = to_email
            msg["Subject"] = subject

            # Attach plain text and HTML
            msg.attach(MIMEText(body_plain, "plain"))
            msg.attach(MIMEText(body_html, "html"))

            # Attach resume if provided
            if resume_path:
                resume_file = Path(resume_path)
                if resume_file.exists():
                    with open(resume_file, "rb") as f:
                        part = MIMEBase("application", "pdf")
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename={resume_file.name}",
                        )
                        msg.attach(part)

            # Send via SMTP
            await aiosmtplib.send(
                msg,
                hostname="smtp.gmail.com",
                port=587,
                start_tls=True,
                username=self.gmail_address,
                password=self.gmail_app_password,
            )

            self.sent_today += 1
            self.sent_this_hour += 1

            logger.info(
                f"Email sent to {to_email} "
                f"(today: {self.sent_today}/{self.get_warmup_limit()}, "
                f"hour: {self.sent_this_hour}/{self.max_per_hour})"
            )
            return True, "Sent successfully"

        except aiosmtplib.SMTPAuthenticationError:
            msg = "Gmail authentication failed — check GMAIL_APP_PASSWORD"
            logger.error(msg)
            return False, msg
        except (aiosmtplib.SMTPException, OSError) as e:
            logger.error(f"Email send failed to {to_email}: {e}")
            return False, str(e)

    async def send_with_delay(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_plain: str,
        resume_path: str | None = None,
        jitter_sec: int = 3,
    ) -> tuple[bool, str]:
        """Send email with human-like delay + jitter before sending."""
        delay = self.delay_sec + random.randint(0, jitter_sec)
        logger.debug(f"Waiting {delay}s before sending to {to_email}")
        await asyncio.sleep(delay)
        return await self.send_email(to_email, subject, body_html, body_plain, resume_path)


# Module-level singleton
_sender: EmailSender | None = None


def get_email_sender() -> EmailSender:
    """Get or create the singleton email sender."""
    global _sender
    if _sender is None:
        _sender = EmailSender()
    return _sender
