"""Add users table for username+password authentication.

Revision ID: 002_add_users
Revises: 001_baseline
Create Date: 2026-02-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002_add_users"
down_revision: Union[str, None] = "001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users;")
