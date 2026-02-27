# Job Tracker

Automated job search system — scrapes 20+ sources, scores with embeddings + LLM, generates cold emails, and tracks everything in a dashboard.

```
Pipeline ──writes──→ API ←──reads── Dashboard
                      │
                   PostgreSQL
                    (Neon)
```

| Directory | What | Tech | Docs |
|-----------|------|------|------|
| [`api/`](api/) | REST API backend | FastAPI, asyncpg, PostgreSQL | [api/docs/](api/docs/) |
| [`ui-next/`](ui-next/) | Dashboard | Next.js 15, React Query, Tailwind v4 | [ui-next/docs/](ui-next/docs/) |
| [`pipeline/`](pipeline/) | Scraping + analysis + emails | asyncio, GPT-4o-mini, MiniLM | [pipeline/docs/](pipeline/docs/) |

Each project has its own README, dependencies, tests, and deployment config. See the individual READMEs for setup instructions.
