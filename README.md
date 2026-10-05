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

# On a new machine, install git-crypt and unlock once.
# The working tree stays plaintext. The committed blob is ciphertext.
# The key file is never committed.
git-crypt unlock ~/Desktop/crypt/lexdictum-backend/lexdictum-backend.key
# Until a root .env is in git, copy the template and fill it in.
cp .env.example .env

# Start local infrastructure
docker compose up -d

# Apply Supabase schema (from project root)
./scripts/setup-supabase.sh
# Or manually: supabase db push
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

Integration tests (optional, require Supabase local):

```bash
./scripts/setup-supabase.sh
SUPABASE_LOCAL=1 uv run pytest tests/ --run-integration
```

Hybrid search is opt-in. After applying migration `003_document_chunks_fts.sql` and
reprocessing documents, enable with `RAG_USE_HYBRID_SEARCH=true`.

Optional Qdrant integration (requires `--extra ml` for embeddings):

```bash
docker compose up -d qdrant
QDRANT_INTEGRATION=1 uv run pytest tests/test_chat_e2e.py --run-integration -k Qdrant
```

### HTTP embedding server (optional)

Run a standalone embedder when workers should not load the ML model locally:

```bash
uv sync --extra ml
uv run uvicorn app.embedding_server.main:app --host 0.0.0.0 --port 8081
```

Point the API/worker at it:

```bash
EMBEDDING_PROVIDER=http
EMBEDDING_SERVICE_URL=http://localhost:8081
```

### OCR (optional)

```bash
uv sync --extra ocr
# Debian/Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-spa
OCR_ENABLED=true
```

When enabled, JPEG/PNG/WebP uploads are accepted and scanned PDFs use OCR as fallback.

### Hybrid search backfill

If documents were indexed before FTS migration `003_document_chunks_fts.sql`:

```bash
uv run python scripts/backfill_document_chunks.py --dry-run
uv run python scripts/backfill_document_chunks.py
```

### Integration CI

The optional workflow `.github/workflows/integration.yml` runs on manual dispatch and does not block main CI. It attempts Supabase-local integration tests when the CLI is available.

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
| `RAG_USE_HYBRID_SEARCH` | No | Enable dense+FTS RRF retrieval (default `false`) |
| `RAG_RRF_K` | No | RRF constant k (default `60`) |
| `EMBEDDING_PROVIDER` | No | `local` (default) or `http` |
| `EMBEDDING_SERVICE_URL` | No* | Base URL for HTTP embedder (`POST /embed`) |
| `OCR_ENABLED` | No | Enable OCR for scanned PDFs/images (default `false`) |
| `TESSERACT_LANG` | No | Tesseract language pack (default `spa`) |
| `OTEL_ENABLED` | No | Enable OpenTelemetry tracing (default `false`) |
| `OTEL_EXPORTER_ENDPOINT` | No | OTLP HTTP endpoint (e.g. `http://localhost:4318/v1/traces`) |
| `SENTRY_DSN` | No | Sentry DSN for error tracking |
| `RATE_LIMIT_CHAT_PER_MINUTE` | No | Chat rate limit (default `20`) |

\* Required for conversation endpoints; document indexing works without it.

### Docker (production)

```bash
# Build and run API + worker + Redis + Qdrant
docker compose -f docker-compose.prod.yml up -d --build

# Worker image variants (Dockerfile build args):
docker build --build-arg INSTALL_ML=1 -t lexdictum-backend .
docker build --build-arg INSTALL_ML=1 --build-arg INSTALL_OCR=1 -t lexdictum-worker-full .
# OCR also requires OCR_ENABLED=true and Tesseract (installed when INSTALL_OCR=1)
```

Configure `.env` with production Supabase credentials and `LLM_API_KEY` before starting.

See `PRODUCTION.md` for the full launch checklist.

### Fly.io

Deploy API and arq worker as separate Fly apps with external Redis (Upstash) and Qdrant Cloud:

```bash
fly apps create lexdictum-api
fly apps create lexdictum-worker
# Set secrets — see docs/DEPLOY-FLY.md
fly deploy --app lexdictum-api
fly deploy -c fly.worker.toml --app lexdictum-worker
```

Full guide: **`docs/DEPLOY-FLY.md`** (secrets, scaling, custom domain `api.lexdictum.es`, CI/CD).

### Staging

Local staging stack (API + worker + Redis + Qdrant, optional observability):

```bash
cp .env.staging.example .env.staging
# Edit .env.staging with staging Supabase credentials

docker compose -f docker-compose.staging.yml up -d --build

# Optional Prometheus, Grafana, OTEL collector:
docker compose -f docker-compose.staging.yml --profile observability up -d
```

- API: http://localhost:8000
- Grafana (observability profile): http://localhost:3001 (admin / password from `GRAFANA_ADMIN_PASSWORD`)
- Prometheus: http://localhost:9090

Worker image in staging defaults to `INSTALL_ML=1`. Set `WORKER_INSTALL_OCR=1` and `OCR_ENABLED=true` for OCR.

### Load testing

Requires a running API:

```bash
# Health only
uv run python scripts/load_test_chat.py --base-url http://localhost:8000 --workers 5 --requests 50

# Health + chat (needs JWT and conversation UUID)
uv run python scripts/load_test_chat.py \
  --base-url http://localhost:8000 \
  --token "$JWT" \
  --conversation-id "$CONVERSATION_UUID" \
  --workers 10 \
  --requests 30
```

### Observability

- Structured JSON logs in production (`APP_ENV=production`)
- Request ID in header `X-Request-ID` and log context
- Prometheus metrics at `/metrics`
- Optional Sentry when `SENTRY_DSN` is set
- Optional OpenTelemetry (`OTEL_ENABLED`, `uv sync --extra observability`)
- Staging stack: `docker-compose.staging.yml` with optional `--profile observability`
- Production checklist: `PRODUCTION.md`

## Project layout

- `app/api/` — FastAPI routers (v1)
- `app/core/` — Security, exceptions, logging, rate limiting
- `app/services/` — Business logic (Supabase, cases, documents)
- `app/workers/` — arq async tasks
- `app/vector/` — Qdrant client
- `supabase/migrations/` — Database schema + RLS

See `ROADMAP.md` for phased development plan.
