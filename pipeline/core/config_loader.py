"""Load and validate YAML profile configs with Pydantic."""

import sys
from pathlib import Path

import httpx
import yaml
from pydantic import ValidationError

from core.logger import logger
from core.models import ProfileConfig


async def load_profile_from_api(
    profile_id: int, api_base_url: str, api_key: str,
) -> ProfileConfig | None:
    """Load profile config from DB via the API. Returns None if not found or no config."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{api_base_url}/api/profiles/{profile_id}/config",
                headers={"X-API-Key": api_key},
            )
            if resp.status_code == 404:
                logger.warning("Profile %d not found in DB", profile_id)
                return None
            resp.raise_for_status()
            data = resp.json()
            config = data.get("config")
            if not config:
                logger.warning("Profile %d has no config in DB", profile_id)
                return None
            profile = ProfileConfig(**config)
            logger.info("Profile loaded from DB (id=%d): %s", profile_id, profile.candidate.name)
            return profile
    except ValidationError as e:
        logger.error("DB profile %d failed validation: %s", profile_id, e)
        return None
    except Exception as e:
        logger.warning("Failed to load profile %d from API: %s", profile_id, e)
        return None


def load_and_validate_profile(yaml_path: str) -> ProfileConfig:
    """Load a YAML profile and validate with Pydantic.

    If validation fails, prints the exact field and error, then exits.
    Never lets the system start with invalid config.
    """
    path = Path(yaml_path)
    if not path.exists():
        logger.error(f"Profile config not found: {yaml_path}")
        sys.exit(1)

    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(f"YAML parse error in {yaml_path}: {e}")
        sys.exit(1)

    if not raw:
        logger.error(f"Profile config is empty: {yaml_path}")
        sys.exit(1)

    try:
        profile = ProfileConfig(**raw)
        logger.info(f"Profile loaded and validated: {profile.candidate.name}")
        return profile
    except ValidationError as e:
        logger.error(f"Config validation failed for {yaml_path}:\n{e}")
        sys.exit(1)
