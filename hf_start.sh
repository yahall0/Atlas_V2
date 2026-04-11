#!/bin/bash
set -e

echo "ATLAS Platform Starting on HF Spaces..."
echo "Waiting for services to initialize..."
sleep 10

# Run Alembic migrations (Supervisord will start Postgres first)
echo "Running Alembic migrations..."
cd /app/backend
/usr/local/bin/alembic upgrade head || echo "Migration skipped or already completed"

echo "Services initialized. Starting Supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf