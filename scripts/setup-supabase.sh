#!/usr/bin/env bash
# Bootstrap Supabase local: start stack, apply migrations, print credentials.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v supabase >/dev/null 2>&1; then
  echo "Supabase CLI not found. Install: https://supabase.com/docs/guides/cli"
  exit 1
fi

if [[ ! -f supabase/config.toml ]]; then
  echo "Initializing Supabase project in $ROOT/supabase ..."
  supabase init
fi

echo "Starting Supabase local stack ..."
supabase start

echo "Applying database migrations ..."
supabase db push

echo ""
echo "Supabase local is ready. Add these to your .env (from supabase status):"
echo ""
supabase status -o env | grep -E '^(API_URL|ANON_KEY|SERVICE_ROLE_KEY|JWT_SECRET)=' || true
echo ""
echo "Map to LexDictum env vars:"
echo "  SUPABASE_URL=<API_URL>"
echo "  SUPABASE_ANON_KEY=<ANON_KEY>"
echo "  SUPABASE_SERVICE_ROLE_KEY=<SERVICE_ROLE_KEY>"
echo "  SUPABASE_JWT_SECRET=<JWT_SECRET>"
echo ""
echo "Run integration tests:"
echo "  SUPABASE_LOCAL=1 uv run pytest tests/test_rls.py --run-integration -k TestRLSIsolation"
