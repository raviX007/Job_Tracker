"""Async database connection pool for Neon PostgreSQL.

Neon free tier:
- Auto-wakes on first query (~300ms)
- Requires ssl="require"
- 100 concurrent connections
- 0.5GB storage per project
"""

from pathlib import Path

import asyncpg

from core.logger import logger


async def check_db_connection(db_url: str) -> bool:
    """Verify database connection at startup."""
    try:
        conn = await asyncpg.connect(db_url, ssl="require")
        version = await conn.fetchval("SELECT version()")
        await conn.close()
        logger.info(f"Database connected: {version[:50]}...")
        return True
    except Exception as e:
        logger.error(f"Cannot connect to database: {e}")
        logger.error("Check DATABASE_URL in .env (get from Neon Console -> Connection Details)")
        return False


async def init_db_pool(db_url: str) -> asyncpg.Pool:
    """Create and return an asyncpg connection pool.

    Neon requires SSL — all connections use ssl='require'.
    Pool: min_size=2 (keep 2 warm connections), max_size=10.
    """
    if not db_url:
        logger.error("DATABASE_URL is not set in .env")
        raise ValueError("DATABASE_URL is required")

    pool = await asyncpg.create_pool(
        dsn=db_url,
        min_size=2,
        max_size=10,
        ssl="require",
        command_timeout=30,
        max_inactive_connection_lifetime=300,
    )
    logger.info("Database connection pool created (min=2, max=10, ssl=require, timeout=30s)")
    return pool


async def setup_schema(pool: asyncpg.Pool) -> None:
    """Execute the schema SQL to create all tables and indexes."""
    schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
    if not schema_path.exists():
        logger.error(f"Schema file not found: {schema_path}")
        return

    schema_sql = schema_path.read_text()
    async with pool.acquire() as conn:
        await conn.execute(schema_sql)
    logger.info("Database schema applied successfully")


async def verify_tables(pool: asyncpg.Pool) -> bool:
    """Verify that all required tables exist."""
    required_tables = ["profiles", "jobs", "job_analyses", "applications", "email_queue", "system_flags", "pipeline_runs", "users"]
    async with pool.acquire() as conn:
        existing = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        existing_names = {row["tablename"] for row in existing}

    missing = [t for t in required_tables if t not in existing_names]
    if missing:
        logger.warning(f"Missing tables: {missing}")
        return False

    logger.info(f"All {len(required_tables)} required tables verified")
    return True


# --- Helper functions for system flags ---

async def get_system_flag(pool: asyncpg.Pool, key: str) -> str | None:
    """Get a system flag value."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT value FROM system_flags WHERE key = $1", key
        )
        return row["value"] if row else None


async def set_system_flag(pool: asyncpg.Pool, key: str, value: str) -> None:
    """Set a system flag value (upsert)."""
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO system_flags (key, value, updated_at)
               VALUES ($1, $2, NOW())
               ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()""",
            key, value,
        )


# --- Helper to ensure a profile exists ---

async def ensure_profile(pool: asyncpg.Pool, name: str, email: str, config_path: str) -> int:
    """Ensure a profile row exists for this user. Returns profile_id."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM profiles WHERE config_path = $1", config_path
        )
        if row:
            return row["id"]

        profile_id = await conn.fetchval(
            "INSERT INTO profiles (name, email, config_path) VALUES ($1, $2, $3) RETURNING id",
            name, email, config_path,
        )
        logger.info(f"Created profile: {name} (id={profile_id})")
        return profile_id
