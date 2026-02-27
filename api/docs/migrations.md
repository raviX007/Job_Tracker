# Database Migrations (Alembic)

The project uses **Alembic** for versioned database migrations in **raw SQL mode** — no SQLAlchemy ORM, just `op.execute()` with plain SQL.

---

## Quick Reference

```bash
cd api

alembic upgrade head              # Apply all pending migrations
alembic current                   # Show current revision
alembic revision -m "add_x"      # Create new migration
alembic downgrade -1              # Roll back one step
alembic history                   # List all migrations
```

---

## Setup

### Existing database (already has tables)

If your database already has the schema from `db/schema.sql`, stamp it with the baseline:

```bash
cd api
alembic stamp 001_baseline
```

This tells Alembic "the database is at revision 001" without running anything.

### New database (fresh setup)

```bash
cd api

# 1. Create tables from schema.sql
python -c "
import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()

async def setup():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'), ssl='require')
    with open('db/schema.sql') as f:
        await conn.execute(f.read())
    await conn.close()
    print('Tables created.')

asyncio.run(setup())
"

# 2. Mark as fully migrated
alembic stamp head
```

---

## Creating a Migration

```bash
cd api
alembic revision -m "add_status_to_jobs"
```

This creates `alembic/versions/<hash>_add_status_to_jobs.py`. Edit it:

```python
def upgrade() -> None:
    op.execute("ALTER TABLE jobs ADD COLUMN status VARCHAR(20) DEFAULT 'active'")
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_jobs_status")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS status")
```

Then apply:

```bash
alembic upgrade head
```

### Important: update schema.sql too

After creating a migration, also update `db/schema.sql` to include the change. This keeps `schema.sql` as the complete schema reference for new deployments.

---

## Common Migration Patterns

### Add a column

```python
def upgrade() -> None:
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS remote_type VARCHAR(30)")

def downgrade() -> None:
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS remote_type")
```

### Add an index

```python
def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_remote ON jobs(remote_type)")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_jobs_remote")
```

### Add a table

```python
def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            profile_id INTEGER REFERENCES profiles(id) ON DELETE CASCADE,
            message TEXT NOT NULL,
            read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS notifications")
```

### Add seed data

```python
def upgrade() -> None:
    op.execute("""
        INSERT INTO system_flags (key, value)
        VALUES ('new_flag', 'true')
        ON CONFLICT (key) DO NOTHING
    """)

def downgrade() -> None:
    op.execute("DELETE FROM system_flags WHERE key = 'new_flag'")
```

---

## Configuration

Alembic reads `DATABASE_URL` from `api/.env`:

```
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
```

The `env.py` automatically appends `sslmode=require` if missing (required by Neon).

---

## Production Deployment (Render)

On Render, run migrations as part of the build/deploy:

```bash
# In Render build command or pre-deploy script
cd api && alembic upgrade head
```

For the first deploy after adding Alembic, stamp the existing database:

```bash
cd api && alembic stamp 001_baseline
```

---

## Migration History

| Revision | Description | Date |
|----------|-------------|------|
| `001_baseline` | Baseline — marks existing schema (7 tables, 19 indexes) | 2026-02-23 |

---

## Connecting to the Database

### Neon (production)

```bash
psql "postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require"
```

### Useful diagnostic queries

```sql
-- Check Alembic version
SELECT * FROM alembic_version;

-- List all tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' ORDER BY table_name;

-- Check table columns
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'jobs'
ORDER BY ordinal_position;

-- Check row counts
SELECT 'jobs' as t, count(*) FROM jobs
UNION ALL SELECT 'analyses', count(*) FROM job_analyses
UNION ALL SELECT 'emails', count(*) FROM email_queue
UNION ALL SELECT 'apps', count(*) FROM applications
UNION ALL SELECT 'startups', count(*) FROM startup_profiles;

-- Check indexes
SELECT indexname, indexdef FROM pg_indexes
WHERE schemaname = 'public' ORDER BY tablename;
```
