# LexDictum Backend Roadmap

Phased plan for agent-driven development.

## Phase 1: Foundation (done)

- [x] uv project with FastAPI architecture
- [x] Settings, dependency injection, lifespan, CORS
- [x] Supabase schema (profiles, cases, documents, conversations, messages) + RLS
- [x] JWT auth dependency (Supabase tokens)
- [x] Cases CRUD stubs wired to service layer
- [x] Document upload stub with arq queue
- [x] Qdrant collection helper
- [x] docker-compose (Redis, Qdrant, optional Postgres)
- [x] Worker stub for document pipeline

## Phase 2: Supabase Auth Integration + RLS Testing (done)

- [x] Wire frontend auth flow (login, refresh, logout) — backend: JWT validation + `/auth/me`
- [x] Validate JWT claims against Supabase Auth config
- [x] Integration tests with Supabase local (`supabase start`) — scaffold in `tests/test_rls.py`
- [x] RLS policy tests: users cannot access other users' cases/documents — unit mocks + integration stub
- [x] Profile CRUD endpoints (`GET/PATCH /profiles/me`)
- [x] Service role vs user-scoped client patterns (`get_supabase_admin` / `get_supabase_user`)
- [x] Storage bucket migration (`002_storage_bucket.sql`)

## Phase 3: Document Upload to Supabase Storage + Worker Queue (done)

- [x] Create `documents` storage bucket with RLS policies
- [x] Reliable upload flow with size/type validation (PDF, DOCX, images)
- [x] Document metadata persistence and status transitions
- [x] arq worker reliability: retries, job status API
- [x] Signed URL generation for document download

## Phase 4: Document Pipeline (Chunking, Embeddings, Qdrant) (done)

- [x] Text extraction: PyMuPDF (PDF), python-docx (DOCX)
- [x] Legal-aware chunking (paragraph/section boundaries, overlap)
- [x] Embeddings with **nlpaueb/legal-bert-base-uncased** (768-dim) via `sentence-transformers`
  - Install: `uv sync --extra ml`
- [x] Qdrant indexing: payload with `case_id`, `document_id`, `chunk_index`, `text`, `page`
- [x] Re-index and delete-on-document-remove flows

## Phase 5: Case Conversations + RAG Agent (done)

- [x] Conversation and message CRUD endpoints
- [x] RAG retrieval: query Qdrant by case_id, re-rank chunks
- [x] LLM integration for legal Q&A per case (streaming responses)
- [x] Citation metadata in assistant messages (source document, page)
- [x] Conversation history management and context window strategy

## Phase 6: Production Hardening (done)

- [x] Structured JSON logging (production) + readable dev logs
- [x] Request ID middleware (`X-Request-ID`)
- [x] Liveness (`/api/v1/health`) and readiness (`/api/v1/health/ready`) checks
- [x] Redis-based chat rate limiting (configurable per minute)
- [x] Global exception handlers (no stack trace leak in prod)
- [x] Optional Sentry integration (`SENTRY_DSN`)
- [x] Prometheus metrics endpoint (`/metrics`)
- [x] CI pipeline (GitHub Actions: pytest + ruff)
- [x] Production Dockerfile and `docker-compose.prod.yml`
- [x] Qdrant client pinned to v1.12.x (aligned with Docker image v1.12.5)

## Phase 7: Integration Test Infrastructure + Upload Consistency (done)

- [x] Reject image uploads at validation (OCR deferred; PDF/DOCX only)
- [x] Supabase local auth seed helpers (`tests/helpers/supabase_seed.py`)
- [x] RLS integration tests enabled (`TestRLSIsolation` with `--run-integration`)
- [x] pytest auto-skip for `@pytest.mark.integration` unless `--run-integration`
- [x] `scripts/setup-supabase.sh` — start local stack, apply migrations, print env vars
- [x] Integration settings fixture with Supabase local defaults

Run integration tests:

```bash
./scripts/setup-supabase.sh
# Copy credentials to .env, then:
SUPABASE_LOCAL=1 uv run pytest tests/test_rls.py --run-integration -k TestRLSIsolation
```

## Phase 8: E2E Chat Flow + Search Architecture Prep (done)

- [x] Chat flow e2e tests with mocked LLM/RAG (`tests/test_chat_e2e.py`)
- [x] Optional Qdrant integration test (`QDRANT_INTEGRATION=1`)
- [x] `EmbeddingProvider` abstraction (`app/pipeline/embeddings.py`) for future embedder service
- [x] Hybrid search RRF stub (`app/services/search/hybrid.py`) + unit test
- [x] RAGService uses injectable embedder provider

## Phase 9: Hybrid Search + HTTP Embedder (done)

- [x] Wire hybrid search into RAGService (dense Qdrant + sparse Postgres FTS via RRF)
- [x] `document_chunks` table with Spanish tsvector FTS (`003_document_chunks_fts.sql`)
- [x] Worker persists/deletes chunks for FTS on document process/remove
- [x] Config: `RAG_USE_HYBRID_SEARCH` (default false), `RAG_RRF_K` (default 60)
- [x] `HttpEmbeddingProvider` + `EMBEDDING_PROVIDER` enum (`local` | `http`)
- [x] Unit tests: RRF fusion, hybrid RAG, HTTP embedder, chunk store

## Phase 10: OCR, Observability, Full CI (done)

- [x] OCR pipeline for scanned PDFs and image documents (PyMuPDF text first, pytesseract fallback)
- [x] Re-enable image uploads when `OCR_ENABLED=true` (JPEG/PNG/WebP)
- [x] OpenTelemetry distributed tracing (API + worker spans, `X-Request-ID` on spans)
- [x] Hybrid search backfill script (`scripts/backfill_document_chunks.py`)
- [x] HTTP embedder microservice stub (`app/embedding_server/`)
- [x] Optional GitHub Actions integration job (manual `workflow_dispatch`)
- [x] Unit tests: telemetry no-op, OCR mocked, backfill dry-run

Run OCR (optional):

```bash
uv sync --extra ocr
# System: apt install tesseract-ocr tesseract-ocr-spa
OCR_ENABLED=true uv run arq app.workers.settings.WorkerSettings
```

Run OpenTelemetry (optional):

```bash
uv sync --extra observability
OTEL_ENABLED=true OTEL_EXPORTER_ENDPOINT=http://localhost:4318/v1/traces uv run uvicorn app.main:app
```

Backfill FTS chunks from Qdrant:

```bash
uv run python scripts/backfill_document_chunks.py --dry-run
uv run python scripts/backfill_document_chunks.py
```

## Phase 11: Staging & Production Observability (done)

- [x] Staging compose (`docker-compose.staging.yml`) — API, worker, Redis, Qdrant
- [x] Optional observability profile: Prometheus, Grafana, OTEL collector
- [x] `.env.staging.example` and README staging section
- [x] Security audit tests (`tests/test_security.py`)
- [x] Load test stub (`scripts/load_test_chat.py`)
- [x] Production checklist (`PRODUCTION.md`)
- [x] Worker Docker build args for `--extra ml` / `--extra ocr`

Run staging:

```bash
cp .env.staging.example .env.staging
docker compose -f docker-compose.staging.yml up -d --build
docker compose -f docker-compose.staging.yml --profile observability up -d
```

Security tests:

```bash
uv run pytest tests/test_security.py
```

## Phase 12: Fly.io deployment (done)

- [x] `fly.toml` for API (health checks, auto start/stop, `mad` region)
- [x] `fly.worker.toml` + `Dockerfile.worker` for arq worker (separate app, `INSTALL_ML=1`)
- [x] `docs/DEPLOY-FLY.md` — Upstash Redis, Qdrant Cloud, secrets, scaling, custom domain
- [x] `.github/workflows/deploy-fly.yml` — staging on push to main, production via manual dispatch
- [x] `PRODUCTION.md` and README Fly.io sections

## Phase 13: Future

- Other managed platforms (Cloud Run, ECS, Kubernetes)
- Frontend integration and production UAT
- Managed secrets (Vault / cloud secret manager)
- Grafana alerting and on-call runbooks in production
- Penetration testing and formal security audit

## Notes for Agents

- Use service layer; keep routers thin
- All user data access must respect RLS — prefer user JWT client where possible
- Document pipeline is CPU/GPU heavy — keep in arq workers, not API process
- API error messages may be in Spanish for legal domain UX
