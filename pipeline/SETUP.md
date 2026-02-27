# Job Tracker — Full System Setup

Three standalone projects that work together:

```
UI ──triggers──→ API ──dispatches──→ Pipeline Service
                  ↑                       │
                  └── callback (status) ──┘
                  │
               PostgreSQL
                (Neon)
```

| Project | Port | Role |
|---------|------|------|
| [api/](../api/) | `8000` | FastAPI backend, PostgreSQL connection |
| [pipeline/](../pipeline/) | `8002` | Pipeline microservice (scraping, analysis, email generation) |
| [ui-next/](../ui-next/) | `3000` | Next.js dashboard |

---

## Prerequisites

| Requirement | Version | Notes |
|------------|---------|-------|
| Python | 3.12+ | All 3 projects |
| PostgreSQL | Any | [Neon free tier](https://neon.tech/) recommended |
| OpenAI API key | GPT-4o-mini | ~$0.001 per job analysis |

---

## 1. Database (Neon)

Create a free PostgreSQL database at [neon.tech](https://neon.tech/). Copy the connection string — you'll need it for the API.

```
postgresql://neondb_owner:<password>@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
```

---

## 2. Generate a Shared API Key

The API key is shared across all 3 projects. Generate one:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Save this value — it goes into every `.env` file.

---

## 3. Start the API (first)

```bash
cd api

pip install -r requirements.txt

cp .env.example .env
# Edit .env:
#   DATABASE_URL=postgresql://neondb_owner:<password>@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
#   API_SECRET_KEY=<your-generated-key>
#   ALLOWED_ORIGINS=http://localhost:8501
```

Initialize database tables:

```bash
python -c "
import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()

async def setup():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    with open('db/schema.sql') as f:
        await conn.execute(f.read())
    await conn.close()
    print('Tables created.')

asyncio.run(setup())
"
```

Start the server:

```bash
uvicorn api.server:app --reload --port 8000
```

Verify: [http://localhost:8000/api/health](http://localhost:8000/api/health) should return `{"status": "ok"}`

---

## 4. Configure and Start the Pipeline Service

```bash
cd pipeline

pip install -r requirements.txt

# Embedding model (downloads ~90MB first time)
pip install torch --index-url https://download.pytorch.org/whl/cpu

cp .env.example .env
# Edit .env:
#   API_BASE_URL=http://localhost:8000
#   API_SECRET_KEY=<same-key-as-api>
#   OPENAI_API_KEY=sk-...
```

Start the pipeline microservice (required for UI-triggered runs):

```bash
uvicorn server:app --reload --port 8002
```

Verify: [http://localhost:8002/health](http://localhost:8002/health) should return `{"status": "ok"}`

Test with a standalone dry run (API must be running):

```bash
python scripts/dry_run.py --source sample --limit 5
```

---

## 5. Start the Dashboard

```bash
cd ui-next

npm install

cp .env.example .env.local
# Edit .env.local:
#   NEXT_PUBLIC_API_URL=http://localhost:8000
#   NEXT_PUBLIC_API_KEY=<same-key-as-api>

npm run dev
```

Open: [http://localhost:3000](http://localhost:3000)

---

## Shared Config Across Projects

One key connects everything. The `API_SECRET_KEY` must be identical across `.env` files:

| Variable | API | Pipeline | UI |
|----------|-----|----------|-----|
| `DATABASE_URL` | **Yes** | — | — |
| `API_SECRET_KEY` | **Yes** | **Yes** | **Yes** |
| `API_BASE_URL` | — | **Yes** | **Yes** |
| `PIPELINE_SERVICE_URL` | **Yes** | — | — |
| `ALLOWED_ORIGINS` | **Yes** | — | — |
| `OPENAI_API_KEY` | — | **Yes** | — |
| `LANGFUSE_*` keys | — | **Yes** | — |
| `SENTRY_DSN` | Optional | Optional | — |
| `LOG_FORMAT` | Optional | Optional | — |

Only the API talks to PostgreSQL. Pipeline and UI talk to the API. The API dispatches pipeline runs to the pipeline service via `PIPELINE_SERVICE_URL`.

Set `LOG_FORMAT=json` on production (Render) for structured JSON logs. Default is `console` (colored text).

---

## Startup Order

```
1. API              →  cd api && uvicorn api.server:app --reload --port 8000
2. Pipeline Service →  cd pipeline && uvicorn server:app --reload --port 8002
3. Dashboard        →  cd ui-next && npm run dev
```

The API must be running before the pipeline service or dashboard can work. The pipeline service must be running for UI-triggered pipeline runs. For standalone CLI runs (`python scripts/dry_run.py`), only the API needs to be running.

---

## Production Deployment

| Project | Platform | Config |
|---------|----------|--------|
| **API** | [Render](https://render.com) | `render.yaml` included — auto-detected on connect |
| **Pipeline CI** | [GitHub Actions](https://github.com/features/actions) | `.github/workflows/pipeline-ci.yml` — lint + test on push/PR |
| **Pipeline Run** | [GitHub Actions](https://github.com/features/actions) | `.github/workflows/pipeline.yml` — runs daily at 3:00 AM UTC |
| **Dashboard** | [Vercel](https://vercel.com) | Next.js auto-deploy from GitHub |

Production env vars:

```
# Render (API)
DATABASE_URL=<neon-connection-string>
API_SECRET_KEY=<shared-key>
ALLOWED_ORIGINS=https://your-app.vercel.app
LOG_FORMAT=json

# GitHub Secrets (Pipeline)
API_BASE_URL=https://your-api.onrender.com
API_SECRET_KEY=<shared-key>
OPENAI_API_KEY=sk-...

# Vercel (Dashboard)
NEXT_PUBLIC_API_URL=https://your-api.onrender.com
NEXT_PUBLIC_API_KEY=<shared-key>
```

---

## Quick Reference

| What | Command |
|------|---------|
| Start API | `cd api && uvicorn api.server:app --reload --port 8000` |
| Start Pipeline Service | `cd pipeline && uvicorn server:app --reload --port 8002` |
| Start Dashboard | `cd ui-next && npm run dev` |
| API docs | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Pipeline health | [http://localhost:8002/health](http://localhost:8002/health) |
| Dry run (sample) | `cd pipeline && python scripts/dry_run.py --source sample --limit 5` |
| Dry run (live) | `cd pipeline && python scripts/dry_run.py --source remotive --limit 10` |
| Push pipeline prompts | `cd pipeline && python scripts/push_prompts.py` |
| Run migrations | `cd api && alembic upgrade head` |
| Install pre-commit | `pip install pre-commit && pre-commit install` |
| Run linters | `pre-commit run --all-files` |
| Init DB tables | See step 3 above |
