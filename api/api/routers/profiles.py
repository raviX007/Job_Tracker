"""Profile management endpoints — CRUD + resume upload + LLM extraction."""

import json
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from api.deps import ADMIN_USERNAME, require_editor
from api.profile_schema import ProfileConfig
from api.resume_parser import (
    extract_profile_from_pdf,
    extract_profile_from_tex,
    extract_text_from_pdf,
    extract_text_from_tex,
)

router = APIRouter(tags=["Profiles"])
logger = logging.getLogger("jobbot.profiles")

MAX_RESUME_SIZE = 5 * 1024 * 1024  # 5 MB


# ─── Helpers ─────────────────────────────────────────


async def _get_user_id(request: Request) -> int:
    """Extract user_id from JWT. Raises 401 if not authenticated via JWT."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="JWT authentication required")
    return int(user_id)


# ─── GET /api/profiles/me ───────────────────────────


@router.get("/api/profiles/me")
async def get_my_profile(request: Request):
    """Get the current user's profile and config."""
    user_id = await _get_user_id(request)
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM profiles WHERE user_id = $1", user_id,
        )

    if not row:
        return {"profile": None}

    config = row["config"]
    if isinstance(config, str):
        config = json.loads(config)

    # Obfuscate email/phone for non-editor users
    is_editor = getattr(request.state, "username", None) == ADMIN_USERNAME
    email = row["email"]
    if not is_editor and config:
        if config.get("candidate", {}).get("email"):
            e = config["candidate"]["email"]
            at_idx = e.find("@")
            config["candidate"]["email"] = e[0] + "***" + e[at_idx:] if at_idx > 0 else "***"
        if config.get("candidate", {}).get("phone"):
            p = config["candidate"]["phone"]
            config["candidate"]["phone"] = p[:3] + "***" + p[-3:] if len(p) > 6 else "***"
        if email:
            at_idx = email.find("@")
            email = email[0] + "***" + email[at_idx:] if at_idx > 0 else "***"

    return {
        "profile": {
            "id": row["id"],
            "user_id": row["user_id"],
            "name": row["name"],
            "email": email,
            "config": config,
            "resume_filename": row["resume_filename"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }
    }


# ─── PUT /api/profiles/me ───────────────────────────


class SaveProfileRequest(BaseModel):
    config: dict  # Validated as ProfileConfig below


@router.put("/api/profiles/me", dependencies=[Depends(require_editor)])
async def save_my_profile(request: Request, body: SaveProfileRequest):
    """Create or update the current user's profile config."""
    user_id = await _get_user_id(request)
    pool = request.app.state.pool

    # Validate config against ProfileConfig schema
    try:
        validated = ProfileConfig(**body.config)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid profile config: {e}")

    config_json = json.dumps(validated.model_dump(mode="json"))
    name = validated.candidate.name
    email = validated.candidate.email

    async with pool.acquire() as conn:
        # Check if profile exists for this user
        existing = await conn.fetchrow(
            "SELECT id FROM profiles WHERE user_id = $1", user_id,
        )

        if existing:
            await conn.execute(
                """UPDATE profiles
                   SET name = $1, email = $2, config = $3::jsonb, updated_at = NOW()
                   WHERE user_id = $4""",
                name, email, config_json, user_id,
            )
            profile_id = existing["id"]
            logger.info("Updated profile %d for user %d", profile_id, user_id)
        else:
            profile_id = await conn.fetchval(
                """INSERT INTO profiles (user_id, name, email, config, config_path)
                   VALUES ($1, $2, $3, $4::jsonb, $5)
                   RETURNING id""",
                user_id, name, email, config_json, f"db:user:{user_id}",
            )
            logger.info("Created profile %d for user %d", profile_id, user_id)

    return {"status": "ok", "profile_id": profile_id}


# ─── POST /api/profiles/me/resume ───────────────────


@router.post("/api/profiles/me/resume", dependencies=[Depends(require_editor)])
async def upload_resume(request: Request, file: UploadFile = File(...)):
    """Upload a PDF/LaTeX resume, extract structured data with LLM, auto-save to DB."""
    user_id = await _get_user_id(request)
    pool = request.app.state.pool

    # Validate file type
    filename = (file.filename or "").lower()
    is_pdf = filename.endswith(".pdf")
    is_tex = filename.endswith(".tex")
    if not filename or not (is_pdf or is_tex):
        raise HTTPException(status_code=400, detail="Only PDF and LaTeX (.tex) files are supported")

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_RESUME_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")

    # Extract text and structured data based on file type
    if is_pdf:
        # Text extraction (for DB storage)
        resume_text = await extract_text_from_pdf(content)
        if not resume_text or len(resume_text.strip()) < 50:
            raise HTTPException(
                status_code=422,
                detail="Could not extract enough text from the PDF. Is it a scanned image?",
            )
        # Vision-based structured extraction (PDF pages → images → OpenAI)
        try:
            extracted = await extract_profile_from_pdf(content)
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # LaTeX: read as text
        resume_text = await extract_text_from_tex(content)
        if not resume_text or len(resume_text.strip()) < 50:
            raise HTTPException(
                status_code=422,
                detail="Could not extract enough text from the LaTeX file.",
            )
        # Text-based structured extraction
        try:
            extracted = await extract_profile_from_tex(resume_text)
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ─── Auto-save: merge extracted data into existing config ─────
    auto_saved = False
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id, config FROM profiles WHERE user_id = $1", user_id,
        )

        # Build merged config: preserve existing sections, overlay extracted fields
        existing_config = {}
        if existing and existing["config"]:
            cfg = existing["config"]
            existing_config = json.loads(cfg) if isinstance(cfg, str) else dict(cfg)

        # Map extracted fields → ProfileConfig sections
        ext_candidate = extracted.get("candidate", {})
        ext_skills = extracted.get("skills", {})
        ext_experience = extracted.get("experience", {})

        # Merge candidate (overlay non-empty extracted fields)
        merged_candidate = existing_config.get("candidate", {})
        for key in ("name", "email", "phone", "github", "linkedin", "portfolio", "location", "timezone"):
            val = ext_candidate.get(key, "")
            if val:
                merged_candidate[key] = val

        # Merge skills (replace entirely from extraction)
        merged_skills = {
            "primary": ext_skills.get("primary", []) or existing_config.get("skills", {}).get("primary", []),
            "secondary": ext_skills.get("secondary", []) or existing_config.get("skills", {}).get("secondary", []),
            "frameworks": ext_skills.get("frameworks", []) or existing_config.get("skills", {}).get("frameworks", []),
        }

        # Merge experience (replace work_history, gap_projects, overlay scalars)
        merged_experience = existing_config.get("experience", {})
        if ext_experience.get("years"):
            merged_experience["years"] = ext_experience["years"]
        if ext_experience.get("graduation_year"):
            merged_experience["graduation_year"] = ext_experience["graduation_year"]
        if ext_experience.get("degree"):
            merged_experience["degree"] = ext_experience["degree"]
        if ext_experience.get("gap_explanation"):
            merged_experience["gap_explanation"] = ext_experience["gap_explanation"]
        if ext_experience.get("work_history"):
            merged_experience["work_history"] = ext_experience["work_history"]
        if ext_experience.get("gap_projects"):
            merged_experience["gap_projects"] = ext_experience["gap_projects"]

        # Build final config (preserves filters, cold_email, matching, etc.)
        existing_config["candidate"] = merged_candidate
        existing_config["skills"] = merged_skills
        existing_config["experience"] = merged_experience

        # Validate merged config against ProfileConfig
        try:
            validated = ProfileConfig(**existing_config)
            config_json = json.dumps(validated.model_dump(mode="json"))
            name = validated.candidate.name
            email_val = validated.candidate.email
            auto_saved = True
        except Exception as e:
            logger.warning("Auto-save validation failed, saving resume only: %s", e)
            config_json = None
            name = ext_candidate.get("name", "Unknown")
            email_val = ext_candidate.get("email", "")

        if existing:
            if auto_saved:
                await conn.execute(
                    """UPDATE profiles
                       SET name = $1, email = $2, config = $3::jsonb,
                           resume_filename = $4, resume_text = $5, updated_at = NOW()
                       WHERE user_id = $6""",
                    name, email_val, config_json,
                    file.filename, resume_text[:10000], user_id,
                )
            else:
                await conn.execute(
                    """UPDATE profiles
                       SET resume_filename = $1, resume_text = $2, updated_at = NOW()
                       WHERE user_id = $3""",
                    file.filename, resume_text[:10000], user_id,
                )
        else:
            if auto_saved:
                await conn.execute(
                    """INSERT INTO profiles (user_id, name, email, config, resume_filename, resume_text, config_path)
                       VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)""",
                    user_id, name, email_val, config_json,
                    file.filename, resume_text[:10000], f"db:user:{user_id}",
                )
            else:
                await conn.execute(
                    """INSERT INTO profiles (user_id, name, email, resume_filename, resume_text, config_path)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    user_id, name, email_val,
                    file.filename, resume_text[:10000], f"db:user:{user_id}",
                )

    logger.info("Resume uploaded for user %d: %s (%d chars, auto_saved=%s)",
                user_id, file.filename, len(resume_text), auto_saved)

    return {"extracted": extracted, "resume_text_length": len(resume_text), "auto_saved": auto_saved}


# ─── GET /api/profiles/{profile_id}/config ──────────
# Used by the pipeline service to fetch config from DB


@router.get("/api/profiles/{profile_id}/config")
async def get_profile_config(request: Request, profile_id: int):
    """Get profile config by ID. Used by the pipeline service."""
    pool = request.app.state.pool

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, config FROM profiles WHERE id = $1", profile_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")

    config = row["config"]
    if config and isinstance(config, str):
        config = json.loads(config)

    return {"profile_id": row["id"], "config": config}
