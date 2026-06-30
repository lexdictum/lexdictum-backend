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

## Phase 5: Case Conversations + RAG Agent (current)

- Conversation and message CRUD endpoints
- RAG retrieval: query Qdrant by case_id, re-rank chunks
- LLM integration for legal Q&A per case (streaming responses)
- Citation metadata in assistant messages (source document, page)
- Conversation history management and context window strategy

## Phase 6: Production Hardening

- Structured logging, OpenTelemetry, health checks for all deps
- Rate limiting, request validation hardening
- Comprehensive test suite (unit, integration, e2e)
- CI/CD pipeline, staging environment
- Secrets management, security audit
- Monitoring and alerting (Sentry, Prometheus)

## Notes for Agents

- Use service layer; keep routers thin
- All user data access must respect RLS — prefer user JWT client where possible
- Document pipeline is CPU/GPU heavy — keep in arq workers, not API process
- API error messages may be in Spanish for legal domain UX
