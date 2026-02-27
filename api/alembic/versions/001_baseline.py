"""Baseline — marks current schema state.

Existing databases: run `alembic stamp 001_baseline` to mark as current.
New databases: run `db/schema.sql` first, then `alembic stamp head`.

Revision ID: 001_baseline
Revises: None
Create Date: 2026-02-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline migration — no-op.
    # The current schema is defined in db/schema.sql (7 tables, 19 indexes).
    pass


def downgrade() -> None:
    # Cannot downgrade past baseline.
    pass
