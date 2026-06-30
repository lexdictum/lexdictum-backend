# Production launch checklist

Concise checklist before going live. Staging validation (`docker-compose.staging.yml`) should pass first.

## Secrets and configuration

- [ ] Supabase production project: URL, anon key, service role key, JWT secret in a secret manager (not in git)
- [ ] `LLM_API_KEY` and optional `SENTRY_DSN` stored as secrets
- [ ] `APP_ENV=production`, `DEBUG=false`, CORS limited to production frontend origin(s)
- [ ] `RATE_LIMIT_ENABLED=true` with appropriate `RATE_LIMIT_CHAT_PER_MINUTE`

## Infrastructure

- [ ] Redis and Qdrant reachable from API and worker (managed or self-hosted)
- [ ] Supabase migrations applied (`001`–`003` including FTS `document_chunks`)
- [ ] Storage bucket `documents` with RLS policies
- [ ] Worker image built with ML extras: `docker build --build-arg INSTALL_ML=1`
- [ ] OCR (if needed): `INSTALL_OCR=1` worker image + `OCR_ENABLED=true` + Tesseract in image

## Search and documents

- [ ] Existing documents reprocessed or backfilled after FTS migration:
  `uv run python scripts/backfill_document_chunks.py`
- [ ] Hybrid search (`RAG_USE_HYBRID_SEARCH=true`) only after backfill/reprocess verified
- [ ] HTTP embedder (`EMBEDDING_PROVIDER=http`) if workers should not load the ML model

## Observability

- [ ] Prometheus scraping `GET /metrics` on API instances
- [ ] OpenTelemetry: `OTEL_ENABLED=true`, `OTEL_EXPORTER_ENDPOINT` pointing to OTLP collector
- [ ] API image includes observability extra if tracing enabled: `uv sync --extra observability`
- [ ] Grafana dashboards and alerting wired (request rate, latency, 5xx, worker queue depth)
- [ ] Sentry DSN configured for API and worker

## Staging validation

- [ ] `cp .env.staging.example .env.staging` and fill staging Supabase credentials
- [ ] `docker compose -f docker-compose.staging.yml up -d --build`
- [ ] Optional observability: `docker compose -f docker-compose.staging.yml --profile observability up -d`
- [ ] Readiness: `GET /api/v1/health/ready` returns 200
- [ ] Upload PDF → worker processes → document status `ready`
- [ ] Chat with citations on a case with indexed documents
- [ ] Load smoke test: `uv run python scripts/load_test_chat.py --base-url http://localhost:8000`

## Security

- [ ] Run `uv run pytest tests/test_security.py` in CI
- [ ] RLS integration tests against staging Supabase: `SUPABASE_LOCAL=1 pytest tests/test_rls.py --run-integration`
- [ ] TLS termination at load balancer / ingress
- [ ] Service role key never exposed to clients or frontend

## Operations

- [ ] On-call runbook for worker failures, Qdrant/Redis outages, LLM rate limits
- [ ] Backup strategy for Supabase Postgres and Qdrant volumes
- [ ] Document pipeline retry policy (`ARQ_MAX_TRIES`) reviewed

## Fly.io deployment

- [ ] API and worker Fly apps created (`lexdictum-api`, `lexdictum-worker`)
- [ ] Upstash Redis or Fly Redis — `REDIS_URL` on both apps
- [ ] Qdrant Cloud (or dedicated Fly volume app) — `QDRANT_URL` on both apps
- [ ] Secrets set via `fly secrets set` (never in git)
- [ ] `GET /api/v1/health/ready` returns 200 after deploy
- [ ] Custom domain (e.g. `api.lexdictum.es`) and CORS for production frontend
- [ ] See **`docs/DEPLOY-FLY.md`** for full steps

## Not in scope (later)

- Other managed platforms (Cloud Run, ECS, Kubernetes)
- Frontend integration and end-user UAT in production
