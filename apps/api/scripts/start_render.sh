#!/usr/bin/env bash
set -euo pipefail

account_name="${GENLAYER_ACCOUNT_NAME:-replayer-runtime}"

genlayer network set studionet
if ! genlayer account use "$account_name"; then
  genlayer account create --name "$account_name" --password "$GENLAYER_ACCOUNT_PASSWORD"
  genlayer account use "$account_name"
fi

cd /app/apps/api
python3 scripts/indexer_service.py &
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
