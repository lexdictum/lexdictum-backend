# LexDictum Backend

![CI](https://github.com/your-org/lexdictum-backend/actions/workflows/ci.yml/badge.svg)

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

# Background worker (document pipeline — requires ML deps)
uv sync --extra ml
uv run arq app.workers.settings.WorkerSettings
```

API docs: http://localhost:8000/docs

Health checks:

- Liveness: `GET /api/v1/health`
- Readiness: `GET /api/v1/health/ready` (Redis, Qdrant, optional Supabase)
- Metrics: `GET /metrics` (Prometheus)

## Tests

```bash
uv run pytest tests/
```

## Deployment

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_ENV` | No | `development` (default) or `production` |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Service role key (workers) |
| `SUPABASE_JWT_SECRET` | Yes | JWT secret for token validation |
| `REDIS_URL` | Yes | Redis URL for arq and rate limiting |
| `QDRANT_URL` | Yes | Qdrant vector DB URL |
| `LLM_API_KEY` | Yes* | OpenAI-compatible API key for chat/RAG |
| `LLM_MODEL` | No | Model name (default `gpt-4o-mini`) |
| `LLM_BASE_URL` | No | Custom OpenAI-compatible base URL |
| `SENTRY_DSN` | No | Sentry DSN for error tracking |
| `RATE_LIMIT_CHAT_PER_MINUTE` | No | Chat rate limit (default `20`) |

\* Required for conversation endpoints; document indexing works without it.

### Docker (production)

```bash
# Build and run API + worker + Redis + Qdrant
docker compose -f docker-compose.prod.yml up -d --build

# Worker needs ML dependencies for embeddings — rebuild with:
# docker build --build-arg INSTALL_ML=1 -t lexdictum-backend .
# Or install ml extra in a custom Dockerfile stage
```

Configure `.env` with production Supabase credentials and `LLM_API_KEY` before starting.

### Observability

- Structured JSON logs in production (`APP_ENV=production`)
- Request ID in header `X-Request-ID` and log context
- Prometheus metrics at `/metrics`
- Optional Sentry when `SENTRY_DSN` is set

## Project layout

- `app/api/` — FastAPI routers (v1)
- `app/core/` — Security, exceptions, logging, rate limiting
- `app/services/` — Business logic (Supabase, cases, documents)
- `app/workers/` — arq async tasks
- `app/vector/` — Qdrant client
- `supabase/migrations/` — Database schema + RLS

See `ROADMAP.md` for phased development plan.
