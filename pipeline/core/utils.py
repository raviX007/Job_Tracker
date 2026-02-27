"""Shared utilities used across the pipeline.

Functions here are imported by emailer, scripts, and core modules.
Keep this module dependency-free (no imports from other pipeline modules).
"""

import html as html_module


def plain_to_html(plain_text: str) -> str:
    """Convert plain text email to simple HTML.

    Used by cold_email.py, cover_letter.py, and _startup_analyzer.py.
    """
    escaped = html_module.escape(plain_text)
    html_body = escaped.replace("\n\n", "</p><p>").replace("\n", "<br>")
    return (
        "<div style='font-family: Arial, sans-serif; font-size: 14px; "
        f"line-height: 1.6;'><p>{html_body}</p></div>"
    )


def mask_email(email: str) -> str:
    """Mask an email address for safe logging. 'alice@example.com' → 'al***@example.com'."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.rsplit("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[:2] + "***"
    return f"{masked_local}@{domain}"
