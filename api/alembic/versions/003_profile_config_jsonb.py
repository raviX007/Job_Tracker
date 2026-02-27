"""Add JSONB config, user_id, and resume fields to profiles table.

Revision ID: 003
Revises: 002
"""

revision = "003"
down_revision = "002"

from alembic import op


def upgrade() -> None:
    op.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS config JSONB")
    op.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS resume_filename TEXT")
    op.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS resume_text TEXT")
    op.execute("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()")
    op.execute("ALTER TABLE profiles ALTER COLUMN config_path DROP NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON profiles(user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_profiles_user_id")
    op.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS resume_text")
    op.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS resume_filename")
    op.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS config")
    op.execute("ALTER TABLE profiles DROP COLUMN IF EXISTS user_id")
    op.execute("ALTER TABLE profiles ALTER COLUMN config_path SET NOT NULL")
