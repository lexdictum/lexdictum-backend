# Deploy LexDictum Backend on Fly.io

This guide covers deploying the **API** and **arq worker** as separate Fly.io apps, with Redis and Qdrant as external managed services.

## Architecture

```
                    ┌─────────────────┐
                    │  lexdictum-api  │  HTTP :8000, auto start/stop
                    │  (fly.toml)     │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
  ┌─────────────┐    ┌─────────────┐    ┌──────────────┐
  │ Upstash /   │    │ Qdrant      │    │ Supabase     │
  │ Fly Redis   │    │ Cloud       │    │ (Auth, DB,   │
  │ (REDIS_URL) │    │ (QDRANT_URL)│    │  Storage)    │
  └──────▲──────┘    └──────▲──────┘    └──────────────┘
         │                   │
         └─────────┬─────────┘
                   ▼
         ┌─────────────────┐
         │ lexdictum-worker│  arq, no HTTP
         │ (fly.worker.toml)│
         └─────────────────┘
```

Do **not** run Redis or Qdrant in the same container as the API. Use managed or dedicated Fly apps for those data stores.

## Prerequisites

1. [Install flyctl](https://fly.io/docs/flyctl/install/)
2. Log in: `fly auth login`
3. Supabase production project with migrations applied (`001`–`003`)
4. OpenAI-compatible LLM API key

## 1. Create Fly apps

Pick names per environment. Examples:

| Environment | API app | Worker app |
|-------------|---------|------------|
| Production | `lexdictum-api` | `lexdictum-worker` |
| Staging | `lexdictum-api-staging` | `lexdictum-worker-staging` |

```bash
# Production (adjust names if needed)
fly apps create lexdictum-api
fly apps create lexdictum-worker

# Staging
fly apps create lexdictum-api-staging
fly apps create lexdictum-worker-staging
```

If you use different app names, either edit `app = '...'` in `fly.toml` / `fly.worker.toml`, or pass `--app <name>` on every deploy.

## 2. External services

### Redis (required)

**Recommended: [Upstash Redis](https://upstash.com/)** (Fly partnership — low latency, TLS, free tier).

1. Create a Redis database in a region close to `mad` (Madrid) if available, or `eu-west-1`.
2. Copy the **TLS** URL (`rediss://...`).

**Alternative: [Fly Redis (Upstash)](https://fly.io/docs/reference/redis/)**

```bash
fly redis create
# Attach to API app when prompted, or copy REDIS_URL manually
```

Both API and worker must use the **same** `REDIS_URL` (arq queue + rate limiting).

### Qdrant (required)

**Recommended: [Qdrant Cloud](https://cloud.qdrant.io/)**

1. Create a cluster in EU.
2. Copy the HTTPS URL and API key (if enabled).
3. Set `QDRANT_URL=https://....cloud.qdrant.io:6333` (or the URL shown in the dashboard).

**Alternative: self-hosted on Fly**

Run Qdrant as a **separate Fly app** with a [volume](https://fly.io/docs/reference/volumes/) for persistence — not in the API or worker container. See [Qdrant Docker docs](https://qdrant.tech/documentation/guides/installation/). This adds operational overhead; Qdrant Cloud is simpler for production.

### Supabase

Already external. Use production URL and keys from the Supabase dashboard (Settings → API).

## 3. Set secrets

Secrets are never committed. Set them on **both** API and worker apps (worker needs Supabase service role + Qdrant + Redis; API needs all runtime secrets).

```bash
# API — replace values; repeat with --app lexdictum-api-staging for staging
fly secrets set --app lexdictum-api \
  SUPABASE_URL='https://xxxx.supabase.co' \
  SUPABASE_ANON_KEY='eyJ...' \
  SUPABASE_SERVICE_ROLE_KEY='eyJ...' \
  SUPABASE_JWT_SECRET='your-jwt-secret' \
  REDIS_URL='rediss://default:xxx@xxx.upstash.io:6379' \
  QDRANT_URL='https://xxx.cloud.qdrant.io:6333' \
  LLM_API_KEY='sk-...'

# Optional
fly secrets set --app lexdictum-api \
  SENTRY_DSN='https://...@sentry.io/...' \
  OTEL_EXPORTER_ENDPOINT='https://your-collector/v1/traces'

# Worker — same core secrets (worker uses service role, Redis, Qdrant, LLM for pipeline)
fly secrets set --app lexdictum-worker \
  SUPABASE_URL='https://xxxx.supabase.co' \
  SUPABASE_ANON_KEY='eyJ...' \
  SUPABASE_SERVICE_ROLE_KEY='eyJ...' \
  SUPABASE_JWT_SECRET='your-jwt-secret' \
  REDIS_URL='rediss://default:xxx@xxx.upstash.io:6379' \
  QDRANT_URL='https://xxx.cloud.qdrant.io:6333' \
  LLM_API_KEY='sk-...'
```

### Non-secret env (in fly.toml)

These defaults are in `[env]` sections: `APP_ENV=production`, `DEBUG=false`, `RATE_LIMIT_ENABLED=true`, etc.

Set additional non-secrets per app:

```bash
# Production CORS — API only
fly secrets set --app lexdictum-api CORS_ORIGINS='["https://lexdictum.es","https://www.lexdictum.es"]'
# Or use fly.toml [env] after converting to a string Fly accepts

# Hybrid search (after FTS backfill)
fly config env --app lexdictum-api  # then edit or:
fly secrets set --app lexdictum-api RAG_USE_HYBRID_SEARCH=true
```

For `CORS_ORIGINS`, prefer setting via `fly.toml` `[env]` or `fly secrets set` depending on whether you treat origins as sensitive.

### Optional worker build args (OCR)

Rebuild worker with OCR when needed:

```bash
fly deploy -c fly.worker.toml --build-arg INSTALL_OCR=1
fly secrets set --app lexdictum-worker OCR_ENABLED=true
```

### HTTP embedder (optional)

To avoid loading the ML model on workers, run a third Fly app or external service with `EMBEDDING_PROVIDER=http` and `EMBEDDING_SERVICE_URL` set on API and worker.

## 4. Deploy

From the repository root:

```bash
# API (uses fly.toml)
fly deploy --app lexdictum-api

# Worker (uses fly.worker.toml + Dockerfile.worker with INSTALL_ML=1)
fly deploy -c fly.worker.toml --app lexdictum-worker
```

Staging:

```bash
fly deploy --app lexdictum-api-staging
fly deploy -c fly.worker.toml --app lexdictum-worker-staging
```

### Verify

```bash
fly status --app lexdictum-api
fly logs --app lexdictum-api

curl https://lexdictum-api.fly.dev/api/v1/health
curl https://lexdictum-api.fly.dev/api/v1/health/ready

fly logs --app lexdictum-worker
```

Readiness (`/api/v1/health/ready`) checks Redis and Qdrant; it returns 503 in production if either is unreachable.

## 5. Scaling

### API (`lexdictum-api`)

| Setting | Location | Notes |
|---------|----------|-------|
| `min_machines_running` | `fly.toml` `[http_service]` | `0` = scale to zero when idle (cost savings, cold start). `1` = always warm (better latency). |
| `auto_stop_machines` / `auto_start_machines` | `fly.toml` | Enabled by default in this config. |
| Horizontal scale | `fly scale count` | Multiple API machines behind Fly proxy. |

```bash
# Always-on production API
# Edit fly.toml: min_machines_running = 1, then:
fly deploy --app lexdictum-api

# Or scale without redeploy:
fly scale count 2 --app lexdictum-api
```

### Worker (`lexdictum-worker`)

Workers have **no HTTP service** — Fly does not health-check them. Scale based on queue depth and processing time.

```bash
# One worker VM (default after deploy)
fly scale count 1 --app lexdictum-worker

# Heavy document load — add workers (each loads embedding model ~2GB RAM)
fly scale count 2 --app lexdictum-worker
```

Worker VM size is `shared-cpu-2x` / `2048mb` in `fly.worker.toml` for local `sentence-transformers` embeddings. Reduce memory only if using `EMBEDDING_PROVIDER=http`.

**Rule of thumb:** scale API for request concurrency; scale workers for document indexing backlog.

## 6. Custom domain

Suggest API subdomain: **`api.lexdictum.es`**

```bash
fly certs add api.lexdictum.es --app lexdictum-api
```

Add the ACME DNS records Fly prints (`A` / `AAAA` or `CNAME`). TLS is terminated by Fly (`force_https = true`).

Point frontend `CORS_ORIGINS` at `https://lexdictum.es` (and `www` if used).

## 7. Health checks

Configured in `fly.toml`:

| Check | Path | Purpose |
|-------|------|---------|
| Liveness | `/api/v1/health` | Process up; always 200 |
| Readiness | `/api/v1/health/ready` | Redis + Qdrant reachable before routing traffic |

Worker apps cannot use HTTP checks; monitor logs, Sentry, and Redis queue length.

## 8. CI/CD

GitHub Actions workflow: `.github/workflows/deploy-fly.yml`

1. Add repository secret `FLY_API_TOKEN` from `fly tokens create deploy -x 999999h`
2. Push to `main` deploys **staging** apps by default
3. Use **workflow_dispatch** to promote to production (manual approval)

Protect production with GitHub Environment rules requiring reviewers.

## 9. Environment variables reference

See `.env.example` and `README.md` for the full list. Required in production:

| Variable | API | Worker | Secret |
|----------|-----|--------|--------|
| `SUPABASE_URL` | ✓ | ✓ | ✓ |
| `SUPABASE_ANON_KEY` | ✓ | ✓ | ✓ |
| `SUPABASE_SERVICE_ROLE_KEY` | ✓ | ✓ | ✓ |
| `SUPABASE_JWT_SECRET` | ✓ | ✓ | ✓ |
| `REDIS_URL` | ✓ | ✓ | ✓ |
| `QDRANT_URL` | ✓ | ✓ | ✓ |
| `LLM_API_KEY` | ✓ | ✓ | ✓ |
| `SENTRY_DSN` | optional | optional | ✓ |
| `OTEL_EXPORTER_ENDPOINT` | optional | optional | ✓ |

## 10. Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Readiness 503 | Wrong `REDIS_URL` / `QDRANT_URL`, or Upstash/Qdrant firewall |
| Worker idle, jobs stuck | Worker not deployed, wrong `REDIS_URL`, or worker OOM (increase memory) |
| Cold start latency | `min_machines_running = 0`; set to `1` for production |
| CORS errors | Set `CORS_ORIGINS` to production frontend URL |

```bash
fly logs --app lexdictum-api
fly ssh console --app lexdictum-worker
fly secrets list --app lexdictum-api
```

## Related

- `PRODUCTION.md` — launch checklist
- `docker-compose.prod.yml` — local production-like stack
- `Dockerfile` / `Dockerfile.worker` — container images
