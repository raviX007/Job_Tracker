"""Email verifier — 4-layer verification pipeline.

Layer 1: Regex syntax check (is it a valid email format?)
Layer 2: MX record check (does the domain have a mail server?)
Layer 3: Disposable email check (is it a throwaway domain?)
Layer 4: API verification (does the specific inbox exist?) — uses credits

Each layer is independent. Layers 1-3 are free and always run.
Layer 4 only runs for pattern-guessed emails or high-value targets.
"""

import re
from dataclasses import dataclass

import dns.exception
import dns.resolver

from core.constants import MAX_EMAIL_LOCAL_PART
from core.logger import logger


@dataclass
class VerificationResult:
    """Result of email verification."""
    email: str
    is_valid: bool
    status: str  # valid, invalid, risky, catch_all, unknown, unverified
    provider: str  # regex, mx_check, disposable_check, apollo, hunter, smtp_check
    confidence: str  # high, medium, low
    details: str = ""


# ─── Layer 1: Regex ────────────────────────────────────

_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)


def check_syntax(email: str) -> VerificationResult:
    """Layer 1: Basic regex syntax check."""
    email = email.strip().lower()

    if not _EMAIL_REGEX.match(email):
        return VerificationResult(
            email=email,
            is_valid=False,
            status="invalid",
            provider="regex",
            confidence="high",
            details="Invalid email format",
        )

    # Additional checks
    local_part, domain = email.rsplit("@", 1)

    if len(local_part) > MAX_EMAIL_LOCAL_PART:
        return VerificationResult(
            email=email, is_valid=False, status="invalid",
            provider="regex", confidence="high",
            details="Local part exceeds 64 characters",
        )

    if ".." in email:
        return VerificationResult(
            email=email, is_valid=False, status="invalid",
            provider="regex", confidence="high",
            details="Contains consecutive dots",
        )

    return VerificationResult(
        email=email,
        is_valid=True,
        status="valid",
        provider="regex",
        confidence="low",  # Syntax valid, but inbox may not exist
        details="Syntax valid",
    )


# ─── Layer 2: MX Record Check ─────────────────────────

def check_mx_record(email: str) -> VerificationResult:
    """Layer 2: Check if the domain has MX records (a mail server exists)."""
    domain = email.rsplit("@", 1)[-1]

    try:
        mx_records = dns.resolver.resolve(domain, "MX")
        if mx_records:
            mx_hosts = [str(r.exchange).rstrip(".") for r in mx_records]
            return VerificationResult(
                email=email,
                is_valid=True,
                status="valid",
                provider="mx_check",
                confidence="medium",
                details=f"MX: {', '.join(mx_hosts[:2])}",
            )
    except dns.resolver.NoAnswer:
        return VerificationResult(
            email=email, is_valid=False, status="invalid",
            provider="mx_check", confidence="high",
            details="Domain has no MX records",
        )
    except dns.resolver.NXDOMAIN:
        return VerificationResult(
            email=email, is_valid=False, status="invalid",
            provider="mx_check", confidence="high",
            details="Domain does not exist",
        )
    except dns.exception.DNSException as e:
        return VerificationResult(
            email=email, is_valid=False, status="unknown",
            provider="mx_check", confidence="low",
            details=f"MX check failed: {e}",
        )

    return VerificationResult(
        email=email, is_valid=False, status="invalid",
        provider="mx_check", confidence="medium",
        details="No MX records found",
    )


# ─── Layer 3: Disposable Email Check ──────────────────

from core.constants import DISPOSABLE_DOMAINS as _DISPOSABLE_DOMAINS


def check_disposable(email: str) -> VerificationResult:
    """Layer 3: Check if the email is from a disposable/throwaway domain."""
    domain = email.rsplit("@", 1)[-1].lower()

    if domain in _DISPOSABLE_DOMAINS:
        return VerificationResult(
            email=email,
            is_valid=False,
            status="invalid",
            provider="disposable_check",
            confidence="high",
            details="Disposable email domain",
        )

    return VerificationResult(
        email=email,
        is_valid=True,
        status="valid",
        provider="disposable_check",
        confidence="low",
        details="Not a known disposable domain",
    )


# ─── Layer 4: API Verification ─────────────────────────

async def check_via_api(email: str) -> VerificationResult:
    """Layer 4: Verify via Hunter.io or Apollo API.

    Uses API credits — only call for pattern-guessed or high-value emails.
    """
    import os

    import httpx

    # Try Hunter first (has email verification endpoint)
    hunter_key = os.getenv("HUNTER_API_KEY", "")
    if hunter_key:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.hunter.io/v2/email-verifier",
                    params={"email": email, "api_key": hunter_key},
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    status = data.get("status", "unknown")
                    score = data.get("score", 0)

                    return VerificationResult(
                        email=email,
                        is_valid=status in ("valid", "accept_all"),
                        status="valid" if status == "valid" else
                               "catch_all" if status == "accept_all" else
                               "risky" if score > 50 else "invalid",
                        provider="hunter",
                        confidence="high" if status == "valid" else "medium",
                        details=f"Hunter: {status} (score={score})",
                    )
        except httpx.HTTPError as e:
            logger.debug(f"Hunter verification failed for {email}: {e}")

    return VerificationResult(
        email=email, is_valid=True, status="unverified",
        provider="none", confidence="low",
        details="No API verification available",
    )


# ─── Full Verification Pipeline ────────────────────────

async def verify_email(
    email: str,
    use_api: bool = False,
) -> VerificationResult:
    """Run the full verification pipeline on an email address.

    Layers 1-3 always run (free). Layer 4 only if use_api=True.
    Returns the most informative result.
    """
    email = email.strip().lower()

    # Layer 1: Syntax
    result = check_syntax(email)
    if not result.is_valid:
        return result

    # Layer 2: MX record
    result = check_mx_record(email)
    if not result.is_valid:
        return result

    # Layer 3: Disposable check
    result = check_disposable(email)
    if not result.is_valid:
        return result

    # Layer 4: API (optional)
    if use_api:
        result = await check_via_api(email)
        return result

    # Passed layers 1-3 without API
    return VerificationResult(
        email=email,
        is_valid=True,
        status="valid",
        provider="mx_check",
        confidence="medium",
        details="Passed syntax + MX + disposable checks",
    )


async def verify_emails_batch(
    emails: list[str],
    sources: list[str] | None = None,
    use_api_for_guessed: bool = True,
) -> list[VerificationResult]:
    """Verify a batch of emails. Uses API only for pattern-guessed ones.

    Args:
        emails: List of email addresses to verify.
        sources: Per-email source metadata (e.g. "pattern_guess", "apollo").
                 Must match length of emails if provided.
        use_api_for_guessed: Whether to use API verification for pattern-guessed emails.
    """
    results = []
    for i, email in enumerate(emails):
        source = sources[i] if sources else "unknown"
        use_api = use_api_for_guessed and source == "pattern_guess"
        result = await verify_email(email, use_api=use_api)
        results.append(result)

    valid_count = sum(1 for r in results if r.is_valid)
    logger.info(f"Email verification: {valid_count}/{len(results)} valid")
    return results
