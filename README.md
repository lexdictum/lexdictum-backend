# LexDictum Backend

Spanish legal case management API for lawyers.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker (for Redis, Qdrant, optional local Postgres)
- Supabase project (Auth, Postgres, Storage)

## Setup

```bash
# Install dependencies
uv sync --extra dev

# Copy environment template
cp .env.example .env
# Edit .env with your Supabase credentials

# Start local infrastructure
docker compose up -d

# Apply Supabase schema (from project root)
supabase db push
# Or run supabase/migrations/001_initial_schema.sql in the SQL editor

# Create storage bucket named "documents" in Supabase (private)
```

## Run

```bash
# API server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Background worker (document pipeline)
uv run arq app.workers.settings.WorkerSettings
```

API docs: http://localhost:8000/docs

Health check: `GET /api/v1/health`

## Tests

```bash
uv run pytest tests/
```

## Project layout

- `app/api/` — FastAPI routers (v1)
- `app/core/` — Security, exceptions
- `app/services/` — Business logic (Supabase, cases, documents)
- `app/workers/` — arq async tasks
- `app/vector/` — Qdrant client
- `supabase/migrations/` — Database schema + RLS

See `ROADMAP.md` for phased development plan.
