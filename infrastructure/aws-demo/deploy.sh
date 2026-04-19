#!/usr/bin/env bash
# Atlas_V2 — ship the repo to the EC2 box and bring the stack up.
# Assumes provision.sh has run (reads ./.state.json).
#
# Steps:
#   1. rsync repo to /opt/atlas on the box (excludes node_modules, venvs, models, .git)
#   2. Copy .env (must be filled locally at infrastructure/aws-demo/.env before this)
#   3. Install nginx site + reload nginx
#   4. docker compose build + up -d  (production override)
#   5. alembic upgrade head
#   6. Print URLs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
STATE_FILE="${SCRIPT_DIR}/.state.json"
ENV_FILE="${SCRIPT_DIR}/.env"

[[ -f "${STATE_FILE}" ]] || { echo "Missing ${STATE_FILE} — run provision.sh first." >&2; exit 1; }
[[ -f "${ENV_FILE}" ]]   || { echo "Missing ${ENV_FILE} — cp .env.prod.example .env and fill it in." >&2; exit 1; }

PY="$(command -v python || command -v python3)"
read_state() { "${PY}" -c "import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])" "${STATE_FILE}" "$1"; }
KEY_PATH="$(read_state key_path)"
PUBLIC_IP="$(read_state public_ip)"
SSH="ssh -i ${KEY_PATH} -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 ubuntu@${PUBLIC_IP}"
REMOTE=/opt/atlas

log() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }

# Wait for bootstrap to finish
log "Waiting for user-data bootstrap to complete on ${PUBLIC_IP}"
for i in $(seq 1 60); do
  if ${SSH} "test -f /var/log/atlas-bootstrap.done" 2>/dev/null; then
    echo "Bootstrap ready."
    break
  fi
  sleep 10
  [[ $i -eq 60 ]] && { echo "Bootstrap did not complete in 10 min. Check /var/log/cloud-init-output.log" >&2; exit 1; }
done

# ───────────── 1. Sync repo (tar-over-ssh — works without rsync, portable to Windows git-bash) ─────────────
log "Packaging repo and streaming to ${REMOTE}"
${SSH} "sudo mkdir -p ${REMOTE} && sudo chown ubuntu:ubuntu ${REMOTE}"

tar -czf - \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='frontend/.next' \
  --exclude='frontend/node_modules' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='backend/models/hf_cache' \
  --exclude='backend/models/*.bin' \
  --exclude='infrastructure/aws-demo/.secrets' \
  --exclude='infrastructure/aws-demo/.state.json' \
  --exclude='infrastructure/aws-demo/.env' \
  -C "${REPO_ROOT}" . \
  | ${SSH} "cd ${REMOTE} && tar -xzf -"

# ───────────── 2. Deploy .env ─────────────
log "Deploying .env"
scp -i "${KEY_PATH}" -o StrictHostKeyChecking=accept-new "${ENV_FILE}" "ubuntu@${PUBLIC_IP}:${REMOTE}/.env"
${SSH} "chmod 600 ${REMOTE}/.env"

# ───────────── 3. Install nginx site ─────────────
log "Installing nginx reverse-proxy"
${SSH} "sudo sed 's/__SERVER_NAME__/${PUBLIC_IP}/g' ${REMOTE}/infrastructure/aws-demo/nginx.conf \
  | sudo tee /etc/nginx/sites-available/atlas >/dev/null && \
  sudo ln -sf /etc/nginx/sites-available/atlas /etc/nginx/sites-enabled/atlas && \
  sudo nginx -t && sudo systemctl reload nginx"

# ───────────── 4. Build & launch stack ─────────────
log "docker compose build (this will take a while on first run)"
${SSH} "cd ${REMOTE} && docker compose -f docker-compose.yml -f infrastructure/aws-demo/docker-compose.prod.yml --env-file .env build"

log "docker compose up -d"
${SSH} "cd ${REMOTE} && docker compose -f docker-compose.yml -f infrastructure/aws-demo/docker-compose.prod.yml --env-file .env up -d"

# ───────────── 5. Migrations ─────────────
log "Running alembic upgrade head"
${SSH} "cd ${REMOTE} && docker compose -f docker-compose.yml -f infrastructure/aws-demo/docker-compose.prod.yml exec -T backend alembic upgrade head"

# ───────────── 6. Done ─────────────
cat <<EOF

✅ Deploy complete.

  App:      http://${PUBLIC_IP}/
  API:      http://${PUBLIC_IP}/api/v1/health
  Grafana:  http://${PUBLIC_IP}/grafana/  (admin / see GRAFANA_PASSWORD in .env)

Next:
  • Point DNS at ${PUBLIC_IP} then run:
      ${SSH} "sudo certbot --nginx -d YOUR.DOMAIN"
    and update PUBLIC_URL in .env to https://... then re-deploy.
  • Smoke-test:  ./infrastructure/aws-demo/smoke-test.sh
EOF
