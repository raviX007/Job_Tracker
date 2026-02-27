"""Email queue and sending endpoints."""

import logging
import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Literal

import aiosmtplib
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from api.deps import require_editor
from api.helpers import _ParamBuilder, _rows
from api.models import UpdateEmailRequest

router = APIRouter(tags=["Emails"])
request_logger = logging.getLogger("jobbot.requests")

# ─── Email / SMTP Config ───────────────────────────
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
EMAIL_SENDING_ENABLED = os.getenv("EMAIL_SENDING_ENABLED", "false").lower() == "true"
RESUME_PATH = os.getenv("RESUME_PATH", "./resumes/ravi_raj.pdf")
TEST_RECIPIENT_OVERRIDE = os.getenv("TEST_RECIPIENT_OVERRIDE", "")

_EMAIL_STATUSES = Literal[
    "All", "draft", "verified", "ready", "queued", "sent", "delivered", "bounced", "failed",
]


@router.get("/api/emails/queue")
async def email_queue(
    request: Request,
    profile_id: int = Query(..., gt=0),
    status: _EMAIL_STATUSES = Query("All"),
    source: str = Query("All"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List queued emails with optional status and source filters."""
    pool = request.app.state.pool
    p = _ParamBuilder()
    p.conditions.append(f"eq.profile_id = {p.add(profile_id)}")

    if status != "All":
        p.conditions.append(f"eq.status = {p.add(status)}")
    if source != "All":
        p.conditions.append(f"j.source = {p.add(source)}")

    count_sql = f"""
        SELECT COUNT(*)
        FROM email_queue eq
        JOIN jobs j ON j.id = eq.job_id
        WHERE {p.where_sql}
    """
    count_params = list(p.params)  # snapshot before LIMIT/OFFSET

    sql = f"""
        SELECT eq.id, eq.recipient_email, eq.recipient_name, eq.recipient_role,
               eq.recipient_source, eq.subject, eq.body_plain,
               eq.email_verified, eq.email_verification_result,
               eq.status, eq.sent_at, eq.created_at,
               j.title as job_title, j.company as job_company, j.job_url, j.source as job_source,
               ja.match_score, ja.route_action
        FROM email_queue eq
        JOIN jobs j ON j.id = eq.job_id
        LEFT JOIN job_analyses ja ON ja.job_id = eq.job_id AND ja.profile_id = eq.profile_id
        WHERE {p.where_sql}
        ORDER BY eq.created_at DESC
        LIMIT {p.add(limit)} OFFSET {p.add(offset)}
    """
    async with pool.acquire() as conn:
        total = await conn.fetchval(count_sql, *count_params)
        rows = await conn.fetch(sql, *p.params)
    return JSONResponse(
        content=_rows(rows),
        headers={"X-Total-Count": str(total)},
    )


@router.get("/api/emails/statuses")
async def email_statuses(request: Request, profile_id: int = Query(..., gt=0)):
    """Get email counts grouped by status."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT status, COUNT(*) as count FROM email_queue WHERE profile_id = $1 GROUP BY status",
            profile_id,
        )
    if not rows:
        return {}
    return {row["status"]: row["count"] for row in rows}


@router.get("/api/emails/sources")
async def email_sources(request: Request, profile_id: int = Query(..., gt=0)):
    """Get distinct job sources that have emails in the queue."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT DISTINCT j.source FROM email_queue eq
               JOIN jobs j ON j.id = eq.job_id
               WHERE eq.profile_id = $1 ORDER BY j.source""",
            profile_id,
        )
    return [row["source"] for row in rows if row["source"]]


@router.get("/api/emails/{email_id}")
async def get_email_by_id(request: Request, email_id: int):
    """Get a single email by ID."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM email_queue WHERE id = $1", email_id)
    if not row:
        raise HTTPException(status_code=404, detail="Email not found")
    return _rows([row])[0]


@router.put("/api/emails/{email_id}/content", dependencies=[Depends(require_editor)])
async def update_email_content(request: Request, email_id: int, body: UpdateEmailRequest):
    """Update the subject and body of a queued email."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE email_queue SET subject = $1, body_plain = $2 WHERE id = $3",
            body.subject, body.body_plain, email_id,
        )
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="Email not found")
    return {"status": "ok"}


@router.delete("/api/emails/{email_id}", dependencies=[Depends(require_editor)])
async def delete_email(request: Request, email_id: int):
    """Delete a single email from the queue."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM email_queue WHERE id = $1", email_id)
    if result.endswith(" 0"):
        raise HTTPException(status_code=404, detail="Email not found")
    return {"status": "ok"}


@router.delete("/api/emails", dependencies=[Depends(require_editor)])
async def delete_all_emails(request: Request, profile_id: int = Query(..., gt=0)):
    """Delete all emails for a profile."""
    pool = request.app.state.pool
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM email_queue WHERE profile_id = $1", profile_id,
        )
    try:
        count = int(result.split()[-1])
    except (ValueError, IndexError):
        count = 0
    return {"deleted": count}


@router.post("/api/emails/{email_id}/send", dependencies=[Depends(require_editor)])
async def send_email(request: Request, email_id: int):
    """Send a queued email via Gmail SMTP with resume attachment."""
    if not EMAIL_SENDING_ENABLED:
        raise HTTPException(status_code=501, detail="Email sending is disabled (EMAIL_SENDING_ENABLED=false)")
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        raise HTTPException(status_code=400, detail="Gmail credentials not configured")

    pool = request.app.state.pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT id, recipient_email, subject, body_html, body_plain, status, resume_path
               FROM email_queue WHERE id = $1""",
            email_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Email not found")
    if row["status"] in ("sent", "delivered"):
        raise HTTPException(status_code=400, detail=f"Email already {row['status']}")

    actual_recipient = row["recipient_email"]
    to_email = TEST_RECIPIENT_OVERRIDE or actual_recipient
    subject = row["subject"]
    if TEST_RECIPIENT_OVERRIDE:
        subject = f"[TEST → {actual_recipient}] {subject}"
    body_html = row["body_html"] or ""
    body_plain = row["body_plain"] or ""

    # Build MIME message
    msg = MIMEMultipart("mixed")
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject

    # Text body (plain + HTML alternative)
    text_part = MIMEMultipart("alternative")
    text_part.attach(MIMEText(body_plain, "plain"))
    if body_html:
        text_part.attach(MIMEText(body_html, "html"))
    msg.attach(text_part)

    # Attach resume PDF (with path traversal protection)
    project_root = Path(__file__).resolve().parent.parent.parent
    tailored_path = row.get("resume_path")
    if tailored_path:
        resume_file = Path(tailored_path)
        if not resume_file.is_absolute():
            resume_file = (project_root / tailored_path).resolve()
    else:
        resume_file = (project_root / RESUME_PATH).resolve()

    if not str(resume_file).startswith(str(project_root)):
        raise HTTPException(status_code=400, detail="Resume path escapes project directory")

    if resume_file.exists():
        with open(resume_file, "rb") as f:
            part = MIMEBase("application", "pdf")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={resume_file.name}")
            msg.attach(part)

    try:
        await aiosmtplib.send(
            msg,
            hostname="smtp.gmail.com",
            port=587,
            start_tls=True,
            username=GMAIL_ADDRESS,
            password=GMAIL_APP_PASSWORD,
        )
    except aiosmtplib.SMTPAuthenticationError:
        raise HTTPException(status_code=500, detail="Gmail authentication failed — check GMAIL_APP_PASSWORD") from None
    except aiosmtplib.SMTPException as e:
        request_logger.error("SMTP error sending email %d: %s", email_id, e)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE email_queue SET status = 'failed', updated_at = NOW() WHERE id = $1",
                email_id,
            )
        raise HTTPException(status_code=502, detail=f"SMTP error: {e}") from None
    except (OSError, TimeoutError, ConnectionError) as e:
        request_logger.error("Network error sending email %d: %s", email_id, e)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE email_queue SET status = 'failed', updated_at = NOW() WHERE id = $1",
                email_id,
            )
        raise HTTPException(status_code=502, detail="Network error sending email") from None

    # Mark as sent in DB
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE email_queue SET status = 'sent', sent_at = NOW(), updated_at = NOW() WHERE id = $1",
            email_id,
        )

    return {"status": "sent", "email_id": email_id, "to": to_email}
