"""Alembic environment — raw SQL migrations (no ORM models).

Reads DATABASE_URL from .env and runs migrations against Neon PostgreSQL.
"""

import os
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Load .env from api/ root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

config = context.config

# Override sqlalchemy.url from DATABASE_URL env var
db_url = os.getenv("DATABASE_URL", "")
if db_url:
    # Neon requires sslmode=require
    if "sslmode" not in db_url:
        separator = "&" if "?" in db_url else "?"
        db_url += f"{separator}sslmode=require"
    config.set_main_option("sqlalchemy.url", db_url)

# No ORM metadata — all migrations are raw SQL via op.execute()
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL script)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
