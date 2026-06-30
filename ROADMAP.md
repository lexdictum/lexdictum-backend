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

## Future work

- Full end-to-end test suite against Supabase local + real services
- Hybrid search (BM25 + vector) for legal document retrieval
- OCR pipeline for scanned PDFs and image documents
- OpenTelemetry distributed tracing
- Staging environment and secrets management (Vault / cloud secret manager)
- Security audit and penetration testing
- Alerting dashboards (Grafana) wired to Prometheus metrics

## Notes for Agents

- Use service layer; keep routers thin
- All user data access must respect RLS — prefer user JWT client where possible
- Document pipeline is CPU/GPU heavy — keep in arq workers, not API process
- API error messages may be in Spanish for legal domain UX
