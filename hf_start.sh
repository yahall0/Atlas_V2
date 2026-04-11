#!/bin/bash
set -e

# Temporarily start Postgres for Alembic migrations
echo "Starting PostgreSQL for migrations..."
su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /var/lib/postgresql/14/main start"
sleep 5

echo "Running Alembic migrations..."
cd /app/backend
export DATABASE_URL="postgresql://atlas:atlaspass@127.0.0.1:5432/atlas_db"
/opt/venv/bin/alembic upgrade head

echo "Stopping PostgreSQL..."
su - postgres -c "/usr/lib/postgresql/14/bin/pg_ctl -D /var/lib/postgresql/14/main stop"
sleep 2

# Hand over process control to Supervisord
echo "Starting Supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf