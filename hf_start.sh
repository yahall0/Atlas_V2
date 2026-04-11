#!/bin/bash
set -euo pipefail

PG_BIN_DIR="$(find /usr/lib/postgresql -mindepth 2 -maxdepth 2 -type d -name bin | sort -V | tail -n 1)"
export PATH="$PG_BIN_DIR:$PATH"
export PGDATA="${PGDATA:-$HOME/postgres/data}"
export PGLOG="${PGLOG:-$HOME/logs/postgres.log}"

echo "ATLAS Platform Starting on HF Spaces..."
mkdir -p "$PGDATA" "$(dirname "$PGLOG")"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
	echo "Initializing PostgreSQL cluster..."
	initdb -D "$PGDATA" --auth=trust --encoding=UTF8 --locale=C
fi

echo "Starting PostgreSQL..."
pg_ctl -D "$PGDATA" -l "$PGLOG" -o "-c listen_addresses=127.0.0.1 -p 5432" start

echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; do
	sleep 1
done

createdb -h 127.0.0.1 atlas_db || true

echo "Running Alembic migrations..."
cd /home/user/app/backend
/usr/local/bin/alembic upgrade head

echo "Seeding demo data..."
python /home/user/app/scripts/seed_demo_db.py

echo "Services initialized. Starting Supervisord..."
exec /usr/bin/supervisord -c /home/user/app/hf_supervisord.conf