#!/bin/sh
set -eu

echo "[ATLAS] Running database migrations..."
alembic upgrade head

echo "[ATLAS] Starting backend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
