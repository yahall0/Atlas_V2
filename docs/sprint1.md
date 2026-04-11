# ATLAS Sprint 1 GÇö Engineering Task Prompts

**Sprint:** 1 of 8 | **Duration:** 14 calendar days | **Sprint Goal:** All infrastructure operational, architecture decided, security designed, data audited, API contracts defined.  
**Team:** Prishiv (Backend/ML/DevOps) -+ Aditya (Frontend/Data/NLP) -+ Amit (Lead)  
**Date:** Sprint start = today  
**Velocity Assumption:** 40 SP total capacity (20 SP per developer)  
**Sprint 1 Committed:** 37 SP (T1GÇôT14) + 4 governance + 1 documentation = buffer-safe

---

## SPRINT 1 TASK MAP

```
DAY  1    2    3    4    5    6    7    8    9   10   11   12   13   14
     Gö£GöÇT1GöÇGöñ         Aditya: Repo + CI/CD (3SP)
     Gö£GöÇT2GöÇGöñ         Prishiv: Docker Compose (2SP)
     Gö£GöÇGöÇT11GöÇGöÇGöñ       Both: Architecture ADR (3SP)
     Gö£GöÇGöÇT7GöÇGöÇGöÇGöñ       Both: Data Inventory (3SP)
          Gö£GöÇT3GöÇGöÇGöñ    Aditya: FastAPI scaffold (3SP)
          Gö£GöÇT4GöÇGöÇGöñ    Prishiv: Next.js scaffold (3SP)
          Gö£GöÇGöÇT8GöÇGöÇGöñ   Both: Schema design (3SP)
            Gö£T5Göñ     Aditya: Databases + migrations (2SP)
            Gö£T12Göñ    Prishiv: RBAC matrix (2SP)
            Gö£GöÇT6GöÇGöñ   Prishiv: Logging + monitoring (2SP)
              Gö£GöÇT13GöÇGöñ Aditya: OpenAPI spec (3SP)
              Gö£GöÇGöÇT9GöÇGöÇGöñ Aditya: Ingestion pipeline (3SP)
              Gö£GöÇT10GöÇGöÇGöñ Prishiv: PII redaction (3SP)
                  Gö£T14Göñ Both: Security arch doc (2SP)
GOV1 Gûá                                          GOV2 Gûá              GOV3 Gûá GOV4 Gûá DOC1 Gûá
```

---
---

# T1-PROMPT GÇö GitHub Repository + Branching Strategy + CI/CD Pipeline

**Assignee:** Aditya | **Story Points:** 3 | **Days:** 1GÇô2 | **Jira:** ATLAS-T1

---

### ROLE + EST TIME

Aditya (Frontend/Data/NLP) GÇö 6 hours across Days 1GÇô2

### ENVIRONMENT

Claude Code terminal (`claude`) for repo scaffolding and CI/CD authoring. GitHub web UI for org/repo settings.

### EXACT TOOLS

GitHub CLI (`gh`), Git, GitHub Actions, pre-commit, gitleaks, Node.js (for commitlint)

### OBJECTIVE

Create the `atlas-platform` monorepo with trunk-based branching, branch protection, CI/CD pipeline (lint GåÆ test GåÆ build GåÆ security scan), pre-commit hooks for secrets detection, and initialise the Jira Sprint 1 board with all task tickets.

### INPUTS

- GitHub org `atlas-gujarat-police` created (Amit provides org admin access)
- Aditya's GitHub account added as org member with admin role
- Prishiv's GitHub account added as org member with write role
- Jira project `ATLAS` created (Amit provides project admin access)

### STEPS

**Step 1: Create the monorepo**

```bash
# CLAUDE CODE INVOCATION:
# Paste into `claude` terminal:

claude "Create a GitHub monorepo called 'atlas-platform' under the org 'atlas-gujarat-police' with the following structure. This is a modular monolith (per ADR-D01) with a FastAPI backend and Next.js frontend.

Directory structure:
atlas-platform/
Gö£GöÇGöÇ .github/
Göé   Gö£GöÇGöÇ workflows/
Göé   Göé   Gö£GöÇGöÇ ci.yml              # Main CI pipeline
Göé   Göé   Gö£GöÇGöÇ security-scan.yml   # Nightly security scan
Göé   Göé   GööGöÇGöÇ deploy-staging.yml  # Deploy to staging (manual trigger)
Göé   Gö£GöÇGöÇ PULL_REQUEST_TEMPLATE.md
Göé   GööGöÇGöÇ CODEOWNERS
Gö£GöÇGöÇ backend/
Göé   Gö£GöÇGöÇ app/
Göé   Göé   Gö£GöÇGöÇ __init__.py
Göé   Göé   Gö£GöÇGöÇ main.py             # FastAPI app entry
Göé   Göé   Gö£GöÇGöÇ config.py           # Pydantic Settings
Göé   Göé   Gö£GöÇGöÇ api/                # Route handlers
Göé   Göé   Göé   GööGöÇGöÇ v1/
Göé   Göé   Göé       Gö£GöÇGöÇ __init__.py
Göé   Göé   Göé       GööGöÇGöÇ health.py   # Health check endpoint
Göé   Göé   Gö£GöÇGöÇ core/               # Auth, RBAC, middleware
Göé   Göé   Göé   GööGöÇGöÇ __init__.py
Göé   Göé   Gö£GöÇGöÇ models/             # SQLAlchemy + Pydantic models
Göé   Göé   Göé   GööGöÇGöÇ __init__.py
Göé   Göé   Gö£GöÇGöÇ services/           # Business logic
Göé   Göé   Göé   GööGöÇGöÇ __init__.py
Göé   Göé   GööGöÇGöÇ nlp/                # NLP pipeline module
Göé   Göé       GööGöÇGöÇ __init__.py
Göé   Gö£GöÇGöÇ alembic/                # Database migrations
Göé   Göé   GööGöÇGöÇ versions/
Göé   Gö£GöÇGöÇ alembic.ini
Göé   Gö£GöÇGöÇ tests/
Göé   Göé   Gö£GöÇGöÇ conftest.py
Göé   Göé   GööGöÇGöÇ test_health.py
Göé   Gö£GöÇGöÇ requirements.txt
Göé   Gö£GöÇGöÇ requirements-dev.txt
Göé   Gö£GöÇGöÇ Dockerfile
Göé   GööGöÇGöÇ pyproject.toml
Gö£GöÇGöÇ frontend/
Göé   GööGöÇGöÇ .gitkeep               # T4 will scaffold this
Gö£GöÇGöÇ infrastructure/
Göé   Gö£GöÇGöÇ docker/
Göé   Göé   GööGöÇGöÇ docker-compose.yml
Göé   Gö£GöÇGöÇ terraform/
Göé   Göé   GööGöÇGöÇ .gitkeep
Göé   GööGöÇGöÇ ansible/
Göé       GööGöÇGöÇ .gitkeep
Gö£GöÇGöÇ docs/
Göé   Gö£GöÇGöÇ decisions/              # ADR storage
Göé   Göé   GööGöÇGöÇ .gitkeep
Göé   Gö£GöÇGöÇ validation/             # Validation gate evidence
Göé   Göé   GööGöÇGöÇ .gitkeep
Göé   GööGöÇGöÇ research/
Göé       GööGöÇGöÇ .gitkeep
Gö£GöÇGöÇ data/
Göé   Gö£GöÇGöÇ reference/              # Static reference data (BNS sections, NCRB codes)
Göé   Göé   GööGöÇGöÇ .gitkeep
Göé   Gö£GöÇGöÇ test/                   # Test fixtures
Göé   Göé   GööGöÇGöÇ .gitkeep
Göé   GööGöÇGöÇ .gitkeep
Gö£GöÇGöÇ scripts/
Göé   GööGöÇGöÇ setup-dev.sh            # Developer onboarding script
Gö£GöÇGöÇ .pre-commit-config.yaml
Gö£GöÇGöÇ .gitignore
Gö£GöÇGöÇ .env.example
Gö£GöÇGöÇ README.md
Gö£GöÇGöÇ LICENSE
GööGöÇGöÇ Makefile

For the README.md, include: project name 'ATLAS GÇö Advanced Technology for Law-enforcement Analytics & Surveillance', team (BITS Pilani x Gujarat Police), quick start with Docker Compose, architecture overview placeholder, and link to docs/.

For .gitignore, include Python, Node.js, Docker, IDE, .env, __pycache__, node_modules, .next, dist, *.pyc, .coverage, .pytest_cache, venv.

For .env.example, include all environment variables the project will need with placeholder values:
DATABASE_URL, MONGODB_URI, REDIS_URL, JWT_SECRET_KEY, JWT_ALGORITHM=HS256, JWT_EXPIRY_MINUTES=60, API_PREFIX=/api/v1, DEBUG=false, LOG_LEVEL=INFO, CORS_ORIGINS, SENTRY_DSN.

For the Makefile, include targets: dev (docker-compose up), test (pytest), lint (ruff + mypy), format (ruff format), migrate (alembic upgrade head), seed (python -m scripts.seed), clean, help.

For the health check endpoint (backend/app/api/v1/health.py), create a simple GET /health that returns {status: 'healthy', version: '0.1.0', timestamp: datetime.utcnow()}.

For tests/test_health.py, create a pytest test using httpx AsyncClient that calls GET /health and asserts 200 with expected fields.

For pyproject.toml, configure ruff (line-length=100, target python 3.11), mypy (strict=true for app/), and pytest.

For requirements.txt: fastapi==0.110.0, uvicorn[standard]==0.27.1, pydantic==2.6.1, pydantic-settings==2.1.0, sqlalchemy==2.0.27, alembic==1.13.1, asyncpg==0.29.0, motor==3.3.2, redis==5.0.1, python-jose[cryptography]==3.3.0, passlib[bcrypt]==1.7.4, httpx==0.27.0.

For requirements-dev.txt: -r requirements.txt, pytest==8.0.2, pytest-asyncio==0.23.5, pytest-cov==4.1.0, ruff==0.3.0, mypy==1.8.0, pre-commit==3.6.2.

Initialize as a proper Python package. Do NOT include any actual secrets."
```

**Step 2: Create the CI/CD pipeline**

```bash
claude "Create the GitHub Actions CI pipeline at .github/workflows/ci.yml for the atlas-platform repo. The pipeline should:

Trigger on: push to develop and main, pull_request to develop and main.

Jobs:
1. 'lint' (runs on ubuntu-latest):
   - Checkout code
   - Setup Python 3.11
   - Install requirements-dev.txt
   - Run: ruff check backend/
   - Run: ruff format --check backend/
   - Run: mypy backend/app/ --ignore-missing-imports

2. 'test' (runs on ubuntu-latest, needs: lint):
   - Checkout code
   - Setup Python 3.11
   - Start services: postgres:16, mongo:7.0, redis:7.2 (use service containers)
   - Install requirements-dev.txt
   - Set env vars: DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/atlas_test, MONGODB_URI=mongodb://localhost:27017/atlas_test, REDIS_URL=redis://localhost:6379/0, JWT_SECRET_KEY=test-secret-key-not-for-production
   - Run: pytest backend/tests/ -v --cov=backend/app --cov-report=xml --cov-report=term-missing
   - Upload coverage report as artifact

3. 'security-scan' (runs on ubuntu-latest, needs: lint):
   - Checkout code
   - Run gitleaks detect --source . --report-format json --report-path gitleaks-report.json
   - Run pip-audit on requirements.txt
   - Upload scan reports as artifacts

4. 'build' (runs on ubuntu-latest, needs: [test, security-scan]):
   - Checkout code
   - Build Docker image: docker build -t atlas-backend:ci-\${{ github.sha }} backend/
   - Verify image runs: docker run --rm atlas-backend:ci-\${{ github.sha }} python -c 'import app; print(app.__name__)'

Use caching for pip dependencies. Add status badges to README."
```

**Step 3: Set up pre-commit hooks**

```bash
claude "Create .pre-commit-config.yaml for the atlas-platform repo with these hooks:

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks (rev: v4.5.0)
    hooks: trailing-whitespace, end-of-file-fixer, check-yaml, check-json, check-merge-conflict, detect-private-key

  - repo: https://github.com/gitleaks/gitleaks (rev: v8.18.2)
    hooks: gitleaks

  - repo: https://github.com/astral-sh/ruff-pre-commit (rev: v0.3.0)
    hooks: ruff (args: [--fix]), ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy (rev: v1.8.0)
    hooks: mypy (additional_dependencies: [pydantic])

Also create a conventional commits hook using commitlint format:
  type(scope): description
  Types: feat, fix, docs, style, refactor, test, chore, ci
  Scopes: backend, frontend, infra, data, docs, security"
```

**Step 4: Configure branch protection**

```bash
# Run manually via GitHub CLI:
gh repo create atlas-gujarat-police/atlas-platform --private --clone
cd atlas-platform
git add -A && git commit -m "chore: initial project scaffold"
git push -u origin main
git checkout -b develop
git push -u origin develop

# Branch protection via GitHub CLI:
gh api repos/atlas-gujarat-police/atlas-platform/branches/main/protection \
  --method PUT \
  --field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field required_status_checks='{"strict":true,"contexts":["lint","test","security-scan","build"]}' \
  --field enforce_admins=true \
  --field restrictions=null

gh api repos/atlas-gujarat-police/atlas-platform/branches/develop/protection \
  --method PUT \
  --field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field required_status_checks='{"strict":true,"contexts":["lint","test"]}' \
  --field enforce_admins=false
```

**Step 5: Initialise Jira Sprint 1** (Sprint ceremony GÇö embedded per requirement)

```
Manual steps in Jira:
1. Create Sprint 1 in ATLAS project board (14-day duration, start today)
2. Create epic: "ATLAS-SPRINT1 GÇö Infrastructure & Architecture"
3. Create 14 task tickets (ATLAS-T1 through ATLAS-T14) with:
   - Summary, description, story points, assignee, sprint, labels per task map above
4. Create 4 governance tickets (ATLAS-GOV1 through ATLAS-GOV4)
5. Create 1 documentation ticket (ATLAS-DOC1)
6. Add all 19 tickets to Sprint 1
7. Start sprint GåÆ Jira burndown chart initialises automatically
8. Verify burndown chart shows 37 SP committed (T1-T14)
9. Screenshot burndown chart baseline GåÆ commit to docs/sprints/sprint1-burndown-baseline.png
```

### VALIDATION COMMAND

```bash
# Verify repo structure:
find . -type f | head -40

# Verify CI pipeline:
gh workflow list
gh run list --workflow=ci.yml

# Verify pre-commit:
pre-commit run --all-files

# Verify branch protection:
gh api repos/atlas-gujarat-police/atlas-platform/branches/main/protection | jq '.required_status_checks'

# Verify health endpoint:
cd backend && pip install -r requirements-dev.txt && pytest tests/test_health.py -v
```

### DONE WHEN

- [ ] Repo exists at `github.com/atlas-gujarat-police/atlas-platform` with full directory structure
- [ ] CI pipeline runs on push (all 4 jobs: lint, test, security-scan, build)
- [ ] Pre-commit hooks installed and passing
- [ ] Branch protection on `main` (1 reviewer + all CI checks required) and `develop` (1 reviewer + lint+test)
- [ ] Jira Sprint 1 board active with all 19 tickets and burndown chart initialised
- [ ] Initial commit on `main`, `develop` branch created
- [ ] PR merged: `feature/T1-repo-setup` GåÆ `develop` with CI green
- [ ] Jira ATLAS-T1 moved to Done

### STORE AT

- Repo: `github.com/atlas-gujarat-police/atlas-platform`
- Jira: ATLAS-T1
- Wiki: `docs/infrastructure/repo-setup.md`

### DORA METRIC

**Deployment Frequency (DF)** GÇö CI/CD pipeline is the foundation for all future deployments. **Lead Time (LT)** GÇö automated lint+test+build reduces time from commit to deployable artifact.

---
---

# T2-PROMPT GÇö Docker Compose Dev + Staging Environment

**Assignee:** Prishiv | **Story Points:** 2 | **Days:** 1GÇô2 | **Jira:** ATLAS-T2

---

### ROLE + EST TIME

Prishiv (Backend/ML/DevOps) GÇö 4 hours across Days 1GÇô2

### ENVIRONMENT

Claude Code terminal. Requires Docker Desktop or Docker Engine + Docker Compose v2.24+.

### EXACT TOOLS

Docker, Docker Compose, Docker BuildKit, envsubst

### OBJECTIVE

Create multi-service Docker Compose configuration for local development (hot-reload, debug ports) and staging (production-like, no debug) environments.

### INPUTS

- T1 repo scaffold completed (directory structure exists)
- Docker Desktop installed on both developer machines
- Port allocations agreed: Backend 8000, Frontend 3000, PostgreSQL 5432, MongoDB 27017, Redis 6379, Prometheus 9090, Grafana 3001, Kibana 5601, Elasticsearch 9200

### STEPS

```bash
claude "Create Docker Compose configuration for the ATLAS platform at infrastructure/docker/docker-compose.yml (development) and infrastructure/docker/docker-compose.staging.yml (staging).

DEVELOPMENT docker-compose.yml should include these services:

1. 'backend' (FastAPI):
   - Build from ../../backend/Dockerfile
   - Volumes: mount ../../backend/app to /app/app (hot-reload)
   - Command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   - Ports: 8000:8000
   - Env file: ../../.env
   - Depends on: postgres, mongodb, redis
   - Healthcheck: curl -f http://localhost:8000/health || exit 1 (interval 30s, timeout 10s, retries 3)

2. 'frontend' (Next.js GÇö placeholder until T4):
   - Image: node:20-alpine
   - Working dir: /app
   - Volumes: mount ../../frontend to /app
   - Command: 'echo Frontend placeholder GÇö run T4 first'
   - Ports: 3000:3000

3. 'postgres' (PostgreSQL 16):
   - Image: postgres:16-alpine
   - Volumes: atlas_pgdata:/var/lib/postgresql/data
   - Environment: POSTGRES_DB=atlas_dev, POSTGRES_USER=atlas, POSTGRES_PASSWORD=atlas_dev_password
   - Ports: 5432:5432
   - Healthcheck: pg_isready -U atlas -d atlas_dev

4. 'mongodb' (MongoDB 7.0):
   - Image: mongo:7.0
   - Volumes: atlas_mongodata:/data/db
   - Environment: MONGO_INITDB_ROOT_USERNAME=atlas, MONGO_INITDB_ROOT_PASSWORD=atlas_dev_password, MONGO_INITDB_DATABASE=atlas_dev
   - Ports: 27017:27017
   - Healthcheck: mongosh --eval 'db.runCommand({ping:1})' --quiet

5. 'redis' (Redis 7.2):
   - Image: redis:7.2-alpine
   - Command: redis-server --requirepass atlas_dev_password
   - Ports: 6379:6379
   - Healthcheck: redis-cli -a atlas_dev_password ping

6. 'elasticsearch' (for ELK GÇö T6 will configure):
   - Image: docker.elastic.co/elasticsearch/elasticsearch:8.12.2
   - Environment: discovery.type=single-node, xpack.security.enabled=false, ES_JAVA_OPTS='-Xms512m -Xmx512m'
   - Volumes: atlas_esdata:/usr/share/elasticsearch/data
   - Ports: 9200:9200

7. 'prometheus' (T6 placeholder):
   - Image: prom/prometheus:v2.50.1
   - Volumes: ../../infrastructure/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
   - Ports: 9090:9090

8. 'grafana' (T6 placeholder):
   - Image: grafana/grafana:10.3.3
   - Volumes: atlas_grafanadata:/var/lib/grafana
   - Ports: 3001:3000
   - Environment: GF_SECURITY_ADMIN_PASSWORD=atlas_dev_password

Named volumes: atlas_pgdata, atlas_mongodata, atlas_esdata, atlas_grafanadata

Networks: atlas-network (bridge)

Also create the backend Dockerfile at backend/Dockerfile:
- FROM python:3.11-slim
- WORKDIR /app
- COPY requirements.txt .
- RUN pip install --no-cache-dir -r requirements.txt
- COPY . .
- EXPOSE 8000
- CMD ['uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000']
- Add a .dockerignore: __pycache__, .pytest_cache, .git, .env, *.pyc, venv

STAGING docker-compose.staging.yml should override:
- No volume mounts for source code (image-only)
- No debug ports exposed for databases
- Backend command without --reload
- Resource limits: backend 1GB RAM, postgres 2GB, mongodb 2GB
- Restart policy: unless-stopped for all services

Also create infrastructure/prometheus/prometheus.yml with a basic scrape config targeting backend:8000/metrics.

Create scripts/setup-dev.sh that:
1. Checks Docker and Docker Compose versions
2. Copies .env.example to .env if .env doesn't exist
3. Runs docker compose -f infrastructure/docker/docker-compose.yml up -d --build
4. Waits for all healthchecks to pass (30s timeout)
5. Runs alembic upgrade head (once backend is healthy)
6. Prints status table showing all service ports
Make it executable with chmod +x."
```

### VALIDATION COMMAND

```bash
# Start all services:
cd infrastructure/docker && docker compose up -d --build

# Wait and check health:
docker compose ps  # All services should show "healthy"

# Verify backend:
curl -s http://localhost:8000/health | jq .

# Verify databases:
docker compose exec postgres pg_isready -U atlas -d atlas_dev
docker compose exec mongodb mongosh --eval "db.runCommand({ping:1})" --quiet
docker compose exec redis redis-cli -a atlas_dev_password ping

# Verify monitoring stack:
curl -s http://localhost:9200/_cluster/health | jq .status  # Elasticsearch
curl -s http://localhost:9090/-/healthy                       # Prometheus
curl -s http://localhost:3001/api/health                      # Grafana

# Teardown:
docker compose down -v  # Remove volumes for clean state
```

### DONE WHEN

- [ ] `docker compose up -d` starts all 7 services successfully
- [ ] All healthchecks pass within 60 seconds
- [ ] Backend responds to `curl localhost:8000/health`
- [ ] PostgreSQL, MongoDB, Redis accept connections
- [ ] Staging compose file works independently
- [ ] `scripts/setup-dev.sh` runs end-to-end for a fresh clone
- [ ] PR merged: `feature/T2-docker-compose` GåÆ `develop`, CI green
- [ ] Jira ATLAS-T2 moved to Done

### STORE AT

- Repo: `infrastructure/docker/docker-compose.yml`, `infrastructure/docker/docker-compose.staging.yml`
- Jira: ATLAS-T2

### DORA METRIC

**Lead Time (LT)** GÇö reproducible dev environments eliminate "works on my machine" delays. **Deployment Frequency (DF)** GÇö staging compose enables consistent pre-production validation.

---
---

# T3-PROMPT GÇö FastAPI Scaffold + JWT Auth + RBAC Middleware

**Assignee:** Aditya | **Story Points:** 3 | **Days:** 2GÇô4 | **Jira:** ATLAS-T3

---

### ROLE + EST TIME

Aditya GÇö 8 hours across Days 2GÇô4

### ENVIRONMENT

Claude Code terminal. Depends on T1 (repo) and T2 (Docker Compose with PostgreSQL + Redis).

### EXACT TOOLS

FastAPI 0.110+, Pydantic v2, python-jose, passlib, SQLAlchemy 2.0 async, Redis (session/blacklist)

### OBJECTIVE

Build the FastAPI application skeleton with JWT authentication, role-based access control middleware for 6 roles (IO, SHO, DySP, SP, Admin, ReadOnly), automatic OpenAPI docs at /docs, CORS, request ID middleware, and structured logging.

### INPUTS

- T1 repo structure exists with `backend/app/` skeleton
- T2 Docker Compose running PostgreSQL and Redis
- ADR-D03 RBAC matrix (from deliberation prompts GÇö use the 6-role model)
- `.env` file with JWT_SECRET_KEY, DATABASE_URL, REDIS_URL

### STEPS

```bash
claude "Build the FastAPI application core in backend/app/ for the ATLAS platform. This is the authentication and authorization foundation. Follow this specification exactly:

1. backend/app/main.py GÇö FastAPI application factory:
   - Create app with title='ATLAS API', version='0.1.0', description='Gujarat Police AI/ML Platform'
   - Include CORS middleware: allow origins from CORS_ORIGINS env var (comma-separated), allow credentials, allow all methods and headers
   - Include RequestID middleware: generate UUID4 for each request, add to response headers as X-Request-ID, make available in request.state
   - Include structured logging middleware: log method, path, status_code, duration_ms, request_id for every request
   - Mount API router with prefix /api/v1
   - Health endpoint at /health (already exists from T1)
   - OpenAPI docs at /docs (Swagger UI) and /redoc

2. backend/app/config.py GÇö Pydantic Settings:
   - class Settings(BaseSettings):
     - DATABASE_URL: str
     - MONGODB_URI: str  
     - REDIS_URL: str
     - JWT_SECRET_KEY: str
     - JWT_ALGORITHM: str = 'HS256'
     - JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
     - JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
     - API_PREFIX: str = '/api/v1'
     - DEBUG: bool = False
     - LOG_LEVEL: str = 'INFO'
     - CORS_ORIGINS: str = 'http://localhost:3000'
     - PROJECT_NAME: str = 'ATLAS'
   - model_config = SettingsConfigDict(env_file='.env')
   - Singleton pattern: get_settings() with lru_cache

3. backend/app/core/security.py GÇö JWT token management:
   - create_access_token(subject: str, role: str, extra_claims: dict = None) -> str
   - create_refresh_token(subject: str) -> str
   - decode_token(token: str) -> dict (raises HTTPException 401 on invalid/expired)
   - hash_password(password: str) -> str (using passlib bcrypt)
   - verify_password(plain: str, hashed: str) -> bool
   - Token payload must include: sub (user_id), role, exp, iat, jti (unique token ID for blacklisting)

4. backend/app/core/roles.py GÇö Role enumeration and permissions:
   - class Role(str, Enum): IO, SHO, DYSP, SP, ADMIN, READ_ONLY
   - class Permission(str, Enum):
     - VIEW_OWN_STATION_FIRS, VIEW_CROSS_STATION_FIRS, VIEW_DISTRICT_FIRS, VIEW_STATE_FIRS
     - VIEW_NLP_RESULTS, OVERRIDE_NLP_CLASSIFICATION
     - VIEW_VICTIM_IDENTITY_RESTRICTED, EXPORT_DATA
     - MANAGE_USERS, VIEW_AUDIT_LOG, CONFIGURE_SYSTEM, VIEW_BIAS_REPORTS
   - ROLE_PERMISSIONS: dict[Role, set[Permission]] mapping each role to its allowed permissions
     - IO: VIEW_OWN_STATION_FIRS, VIEW_NLP_RESULTS
     - SHO: IO permissions + VIEW_CROSS_STATION_FIRS (own district), OVERRIDE_NLP_CLASSIFICATION, EXPORT_DATA, VIEW_VICTIM_IDENTITY_RESTRICTED
     - DYSP: SHO permissions + VIEW_DISTRICT_FIRS, VIEW_BIAS_REPORTS
     - SP: DYSP permissions + VIEW_STATE_FIRS, VIEW_AUDIT_LOG
     - ADMIN: MANAGE_USERS, VIEW_AUDIT_LOG, CONFIGURE_SYSTEM (no case-level access)
     - READ_ONLY: VIEW_STATE_FIRS, VIEW_NLP_RESULTS, VIEW_BIAS_REPORTS

5. backend/app/core/auth.py GÇö Authentication dependencies:
   - get_current_user(token: str = Depends(oauth2_scheme)) -> UserTokenPayload
     - Extracts and validates JWT from Authorization: Bearer header
     - Checks token not blacklisted in Redis (key: blacklist:{jti})
     - Returns UserTokenPayload(user_id, role, permissions)
   - require_permission(permission: Permission) -> dependency factory
     - Returns a FastAPI Depends that checks current user has the required permission
     - Raises HTTPException 403 if permission denied
   - require_role(min_role: Role) -> dependency factory
     - Hierarchical: SP > DYSP > SHO > IO (ADMIN and READ_ONLY are lateral)
     - Raises HTTPException 403 if role insufficient

6. backend/app/api/v1/auth.py GÇö Auth endpoints:
   - POST /auth/login GÇö accepts username + password, returns {access_token, refresh_token, token_type, role}
   - POST /auth/refresh GÇö accepts refresh_token, returns new access_token
   - POST /auth/logout GÇö blacklists current token's jti in Redis with TTL = remaining token lifetime
   - GET /auth/me GÇö returns current user profile (requires any valid token)

7. backend/app/models/user.py GÇö SQLAlchemy User model:
   - id: UUID (primary key, default uuid4)
   - username: str (unique, indexed)
   - hashed_password: str
   - full_name: str
   - role: Role (enum)
   - police_station_code: str (nullable GÇö for IO/SHO)
   - district_code: str (nullable GÇö for DySP/SP)
   - is_active: bool (default True)
   - created_at: datetime (server default now)
   - updated_at: datetime (onupdate now)

8. backend/app/core/database.py GÇö Database session management:
   - Async SQLAlchemy engine + sessionmaker
   - get_db() async generator for dependency injection
   - get_redis() async function for Redis connection

9. backend/app/core/middleware.py GÇö Custom middleware:
   - RequestIDMiddleware: adds X-Request-ID header
   - AuditLogMiddleware: logs all write operations (POST/PUT/DELETE) with user_id, endpoint, timestamp, request_id to a separate audit log (print to structured JSON for now GÇö T6 will route to ELK)

10. Tests in backend/tests/:
    - test_auth.py: test login success, login failure (wrong password), token refresh, logout + re-use blocked, expired token rejected
    - test_rbac.py: test IO cannot access MANAGE_USERS, SHO can OVERRIDE_NLP, ADMIN cannot view FIRs, permission hierarchy works
    - conftest.py: fixtures for test database, test client, test users (one per role)

All imports must be correct. All type hints must be present. Use async/await throughout. Use Pydantic v2 model_validator where needed."
```

### VALIDATION COMMAND

```bash
# With Docker Compose running (T2):
cd backend

# Run tests:
pytest tests/ -v --cov=app --cov-report=term-missing

# Manual smoke test:
uvicorn app.main:app --reload &

# Test login:
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test_io","password":"testpassword"}'

# Test protected endpoint:
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test_io","password":"testpassword"}' | jq -r .access_token)

curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/auth/me

# Test RBAC (IO should get 403 on admin endpoints):
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/admin/users
# Expected: 403 Forbidden

# Verify OpenAPI docs accessible:
curl -s http://localhost:8000/docs | head -5   # Should return HTML
curl -s http://localhost:8000/openapi.json | jq .info
```

### DONE WHEN

- [ ] All auth endpoints functional (login, refresh, logout, me)
- [ ] JWT tokens issued with role and permissions
- [ ] RBAC middleware blocks unauthorized access (tested for all 6 roles)
- [ ] Token blacklisting on logout works (Redis)
- [ ] OpenAPI docs render at /docs
- [ ] All tests pass: `pytest tests/ -v` with GëÑ 80% coverage on `core/`
- [ ] PR merged: `feature/T3-fastapi-auth` GåÆ `develop`, CI green
- [ ] Jira ATLAS-T3 moved to Done

### STORE AT

- Repo: `backend/app/core/`, `backend/app/api/v1/auth.py`, `backend/app/models/user.py`
- Jira: ATLAS-T3

### DORA METRIC

**Change Failure Rate (CFR)** GÇö auth/RBAC bugs are security-critical change failures. Comprehensive test coverage reduces CFR.

---
---

# T4-PROMPT GÇö Next.js 14 + Tailwind + shadcn/ui Project Scaffold

**Assignee:** Prishiv | **Story Points:** 3 | **Days:** 2GÇô4 | **Jira:** ATLAS-T4

---

### ROLE + EST TIME

Prishiv GÇö 6 hours across Days 2GÇô4

### ENVIRONMENT

Claude Code terminal. Node.js 20 LTS required.

### EXACT TOOLS

Next.js 14 (App Router), TypeScript, Tailwind CSS 3.4, shadcn/ui, next-auth (or custom JWT client), Axios/fetch

### OBJECTIVE

Scaffold the ATLAS frontend dashboard with Next.js 14 App Router, TypeScript, Tailwind CSS, shadcn/ui component library, authentication flow (JWT from backend), role-aware layout, and a placeholder dashboard page.

### INPUTS

- T1 repo exists with `frontend/` directory (currently `.gitkeep`)
- T3 auth API endpoints defined (POST /auth/login, GET /auth/me)
- ADR-D03 RBAC roles (6 roles with different dashboard views)

### STEPS

```bash
claude "Create a Next.js 14 frontend application in the frontend/ directory of the atlas-platform repo. Use the App Router (app/ directory), TypeScript strict mode, and Tailwind CSS.

1. Initialize with: npx create-next-app@14 frontend --typescript --tailwind --eslint --app --src-dir --import-alias '@/*'

2. Install and configure shadcn/ui:
   - npx shadcn-ui@latest init (style: default, base color: slate, CSS variables: yes)
   - Add components: button, card, input, label, table, badge, dropdown-menu, avatar, sheet, alert, dialog, tabs, toast, separator

3. Create the following directory structure inside frontend/src/:
   app/
   Gö£GöÇGöÇ layout.tsx            # Root layout with font, metadata
   Gö£GöÇGöÇ page.tsx              # Landing/redirect to /dashboard or /login
   Gö£GöÇGöÇ globals.css           # Tailwind base + shadcn theme
   Gö£GöÇGöÇ (auth)/
   Göé   Gö£GöÇGöÇ login/
   Göé   Göé   GööGöÇGöÇ page.tsx      # Login page
   Göé   GööGöÇGöÇ layout.tsx        # Auth layout (centered, no sidebar)
   Gö£GöÇGöÇ (dashboard)/
   Göé   Gö£GöÇGöÇ layout.tsx        # Dashboard layout (sidebar + header + main)
   Göé   Gö£GöÇGöÇ dashboard/
   Göé   Göé   GööGöÇGöÇ page.tsx      # Main dashboard (role-aware content)
   Göé   Gö£GöÇGöÇ firs/
   Göé   Göé   GööGöÇGöÇ page.tsx      # FIR list/search (placeholder)
   Göé   GööGöÇGöÇ analytics/
   Göé       GööGöÇGöÇ page.tsx      # Analytics dashboard (placeholder)
   lib/
   Gö£GöÇGöÇ api.ts                # Axios/fetch wrapper configured with base URL and JWT interceptor
   Gö£GöÇGöÇ auth.ts               # JWT token storage (httpOnly cookie or secure localStorage), login/logout functions, getCurrentUser
   Gö£GöÇGöÇ types.ts              # TypeScript interfaces: User, FIR, Role, Permission, APIResponse
   GööGöÇGöÇ utils.ts              # cn() helper for Tailwind class merging
   components/
   Gö£GöÇGöÇ layout/
   Göé   Gö£GöÇGöÇ sidebar.tsx       # Role-aware sidebar navigation
   Göé   Gö£GöÇGöÇ header.tsx        # Top bar with user avatar, role badge, logout
   Göé   GööGöÇGöÇ role-gate.tsx     # Component that shows/hides children based on user role
   Gö£GöÇGöÇ auth/
   Göé   GööGöÇGöÇ login-form.tsx    # Login form component
   GööGöÇGöÇ ui/                   # shadcn/ui components (auto-generated)
   middleware.ts              # Next.js middleware: redirect unauthenticated users to /login

4. Login page (app/(auth)/login/page.tsx):
   - Centered card with ATLAS logo placeholder, username + password inputs, login button
   - On submit: POST to backend /api/v1/auth/login, store tokens, redirect to /dashboard
   - Error handling: show toast on invalid credentials
   - Styled with Tailwind: dark police-blue theme (#1a365d primary, #2d3748 secondary)

5. Dashboard layout (app/(dashboard)/layout.tsx):
   - Left sidebar (collapsible on mobile): navigation items based on user role
     - IO: Dashboard, My FIRs
     - SHO: Dashboard, Station FIRs, Analytics, Override Classification
     - DySP: Dashboard, District FIRs, Analytics, Bias Reports
     - SP: Dashboard, State Overview, Analytics, Audit Log, Bias Reports
     - Admin: User Management, System Config, Audit Log
     - ReadOnly: Dashboard, Analytics, Bias Reports
   - Top header: ATLAS logo, user name, role badge (using shadcn Badge), logout button
   - Main content area: renders child pages

6. Dashboard page (app/(dashboard)/dashboard/page.tsx):
   - Show greeting: 'Welcome, {user.full_name}' with role badge
   - 4 stat cards (shadcn Card): Total FIRs (placeholder), Pending Review, Classified Today, Accuracy Rate
   - Placeholder chart area: 'Crime trend chart coming in Sprint 3'
   - All data is placeholder/mock GÇö real API integration in Sprint 2-3

7. Middleware (middleware.ts):
   - Check for auth token in cookies/headers
   - If no token and path is not /login: redirect to /login
   - If token exists and path is /login: redirect to /dashboard

8. API client (lib/api.ts):
   - Create axios instance with baseURL from NEXT_PUBLIC_API_URL env var (default http://localhost:8000/api/v1)
   - Request interceptor: attach Bearer token from storage
   - Response interceptor: on 401, clear token and redirect to /login
   - Generic request function with TypeScript generics

9. Types (lib/types.ts):
   - enum Role { IO = 'IO', SHO = 'SHO', DYSP = 'DYSP', SP = 'SP', ADMIN = 'ADMIN', READ_ONLY = 'READ_ONLY' }
   - interface User { id: string; username: string; full_name: string; role: Role; police_station_code?: string; district_code?: string }
   - interface LoginResponse { access_token: string; refresh_token: string; token_type: string; role: Role }
   - interface FIR { fir_id: string; fir_number: string; district: string; ... } (placeholder)

10. Create Dockerfile for frontend:
    - FROM node:20-alpine
    - WORKDIR /app, COPY package*.json, RUN npm ci, COPY ., RUN npm run build
    - EXPOSE 3000, CMD ['npm', 'start']

11. Update docker-compose.yml frontend service to build from this Dockerfile with volume mount for dev.

Use 'use client' directive where needed. Use server components by default. Ensure all TypeScript types are strict GÇö no 'any'."
```

### VALIDATION COMMAND

```bash
cd frontend
npm install
npm run build          # Should compile without errors
npm run lint           # ESLint should pass
npm run dev &          # Start dev server

# Verify pages render:
curl -s http://localhost:3000/login | grep -i "atlas"
curl -s http://localhost:3000/ | head -5  # Should redirect to /login

# Run with Docker:
cd ../infrastructure/docker
docker compose up -d frontend
curl -s http://localhost:3000/login | head -5
```

### DONE WHEN

- [ ] `npm run build` compiles without TypeScript errors
- [ ] Login page renders with styled form
- [ ] Dashboard layout with role-aware sidebar renders
- [ ] Middleware redirects unauthenticated users to /login
- [ ] API client configured with JWT interceptor
- [ ] Docker build succeeds
- [ ] PR merged: `feature/T4-frontend-scaffold` GåÆ `develop`, CI green
- [ ] Jira ATLAS-T4 moved to Done

### STORE AT

- Repo: `frontend/`
- Jira: ATLAS-T4

### DORA METRIC

**Lead Time (LT)** GÇö component library (shadcn/ui) reduces future UI development time.

---
---

# T5-PROMPT GÇö PostgreSQL + MongoDB + Alembic Migrations + Seed Data

**Assignee:** Aditya | **Story Points:** 2 | **Days:** 3GÇô4 | **Jira:** ATLAS-T5

---

### ROLE + EST TIME

Aditya GÇö 4 hours across Days 3GÇô4

### ENVIRONMENT

Claude Code terminal. T2 Docker Compose must be running (PostgreSQL 16, MongoDB 7.0).

### EXACT TOOLS

SQLAlchemy 2.0, Alembic, asyncpg, Motor (async MongoDB driver), PostgreSQL 16, MongoDB 7.0

### OBJECTIVE

Configure Alembic for PostgreSQL migrations, create initial migration (users table + audit_log table), set up MongoDB collections with validation schemas (for FIR documents, NLP results), and create seed data script for development (1 user per role + 10 sample FIR stubs).

### STEPS

```bash
claude "Set up database infrastructure for the ATLAS platform.

1. backend/alembic.ini GÇö configure:
   - sqlalchemy.url = driver://... (read from env via env.py)
   - file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(rev)s_%%(slug)s

2. backend/alembic/env.py GÇö async migration environment:
   - Import settings from app.config
   - Use async engine with asyncpg
   - Set target_metadata from app.models.base (Base.metadata)
   - Support both online and offline migration modes

3. backend/app/models/base.py GÇö SQLAlchemy base:
   - Base = declarative_base() with async support
   - TimestampMixin: created_at (server_default=func.now()), updated_at (onupdate=func.now())
   - UUIDMixin: id = Column(UUID, primary_key=True, default=uuid.uuid4)

4. Initial migration (alembic revision --autogenerate -m 'initial_schema'):
   Tables:
   - users (from T3 User model)
   - audit_logs: id (UUID), user_id (FK->users), action (VARCHAR), resource_type (VARCHAR), resource_id (VARCHAR), details (JSONB), ip_address (INET), request_id (UUID), created_at (TIMESTAMP WITH TZ)
   - Index on audit_logs: (user_id, created_at), (resource_type, resource_id)

5. backend/app/core/mongodb.py GÇö MongoDB setup:
   - Async Motor client from MONGODB_URI
   - get_mongodb() dependency
   - Database name from URI
   - Create collections with JSON Schema validation:
     a. 'firs' collection GÇö validation schema:
        {fir_id: string (required), fir_number: string, district: string, police_station: string,
         fir_date: date, occurrence_date: date, acts_sections: [{act: string, section: string}],
         crime_head_major: string, crime_head_minor: string, complainant: {name: string, ...},
         accused: [{name: string, known: boolean, ...}], narrative: string (required),
         raw_text: string, source: string, ingested_at: datetime, is_synthetic: boolean (default false)}
     b. 'nlp_results' collection GÇö validation schema:
        {fir_id: string (required, indexed), model_version: string,
         classification: {predicted_category: string, confidence: float, all_scores: object},
         entities: [{text: string, label: string, start: int, end: int}],
         sections_extracted: [{section: string, act: string}],
         language_detected: string, processed_at: datetime}
     c. 'audit_trail_nlp' collection:
        {fir_id: string, action: string, user_id: string, previous_value: object,
         new_value: object, reason: string, timestamp: datetime}
   - Create indexes: firs.fir_id (unique), firs.district, firs.fir_date, nlp_results.fir_id

6. backend/scripts/seed.py GÇö Development seed data:
   - Create 6 users (one per role) with known passwords:
     - test_io / testpass123 (Role.IO, station: 'PS001', district: 'Ahmedabad_City')
     - test_sho / testpass123 (Role.SHO, station: 'PS001', district: 'Ahmedabad_City')
     - test_dysp / testpass123 (Role.DYSP, district: 'Ahmedabad_City')
     - test_sp / testpass123 (Role.SP, district: 'Ahmedabad_City')
     - test_admin / testpass123 (Role.ADMIN)
     - test_readonly / testpass123 (Role.READ_ONLY)
   - Insert 10 sample FIR documents into MongoDB 'firs' collection:
     - Mix of categories: 3 property crime, 2 violent crime, 2 crimes against women, 1 cyber, 1 traffic, 1 missing persons
     - Mix of languages: 5 English, 3 Gujarati-placeholder, 2 code-mixed placeholder
     - FIR numbers: GJ/AHD/2024/001 through GJ/AHD/2024/010
     - Narratives: realistic but fully fictional (no real names, addresses, or identifiable information)
     - Mark all as is_synthetic: true
   - Script is idempotent: drops and recreates seed data on each run

7. Add Makefile targets:
   - make migrate: cd backend && alembic upgrade head
   - make seed: cd backend && python -m scripts.seed
   - make db-reset: alembic downgrade base && alembic upgrade head && python -m scripts.seed

All async. All type-hinted. Include docstrings."
```

### VALIDATION COMMAND

```bash
# Run migration:
cd backend
alembic upgrade head
# Should output: 'Running upgrade -> initial_schema'

# Verify PostgreSQL tables:
docker compose exec postgres psql -U atlas -d atlas_dev -c "\dt"
# Should show: users, audit_logs, alembic_version

# Run seed:
python -m scripts.seed
# Should output: '6 users created', '10 FIR documents inserted'

# Verify MongoDB:
docker compose exec mongodb mongosh --eval "db.firs.countDocuments()" atlas_dev
# Should output: 10

docker compose exec mongodb mongosh --eval "db.firs.findOne({fir_number:'GJ/AHD/2024/001'})" atlas_dev
# Should output: FIR document

# Verify login with seed user:
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test_io","password":"testpass123"}'
# Should return: access_token, role: IO
```

### DONE WHEN

- [ ] Alembic migration runs cleanly (upgrade + downgrade)
- [ ] PostgreSQL has `users` and `audit_logs` tables with correct schema
- [ ] MongoDB has `firs`, `nlp_results`, `audit_trail_nlp` collections with validation schemas
- [ ] Seed script creates 6 users and 10 FIRs
- [ ] Login works with seed users
- [ ] `make db-reset` works end-to-end
- [ ] PR merged: `feature/T5-databases` GåÆ `develop`, CI green
- [ ] Jira ATLAS-T5 moved to Done

### STORE AT

- Repo: `backend/alembic/`, `backend/app/core/mongodb.py`, `backend/app/models/base.py`, `backend/scripts/seed.py`
- Jira: ATLAS-T5

### DORA METRIC

**Lead Time (LT)** GÇö migration automation reduces deployment lead time. **MTTR** GÇö `make db-reset` enables rapid recovery from data corruption.

---
---

# T6-PROMPT GÇö Logging (ELK) + Prometheus Metrics + Grafana Dashboards

**Assignee:** Prishiv | **Story Points:** 2 | **Days:** 4GÇô5 | **Jira:** ATLAS-T6

---

### ROLE + EST TIME
Prishiv GÇö 5 hours across Days 4GÇô5

### ENVIRONMENT
Claude Code terminal. T2 Docker Compose running (Elasticsearch, Prometheus, Grafana).

### EXACT TOOLS
Python `logging` + `python-json-logger`, Prometheus `prometheus-client`, Grafana, Elasticsearch, Logstash/Filebeat, Kibana

### OBJECTIVE
Implement structured JSON logging routed to ELK stack, a Prometheus /metrics endpoint in FastAPI with custom counters (requests per role, NLP inference latency, FIR ingestion rate), and a Grafana dashboard with 4 alert rules.

### STEPS

```bash
claude "Set up the observability stack for ATLAS.

1. backend/app/core/logging_config.py GÇö Structured logging:
   - Configure Python logging with python-json-logger (or structlog)
   - Format: JSON with fields: timestamp, level, message, request_id, user_id, module, function, duration_ms
   - Log levels: INFO for requests, WARNING for 4xx, ERROR for 5xx, DEBUG for development
   - Create get_logger(name: str) factory that returns configured logger
   - All log output goes to stdout (Docker captures it)

2. backend/app/core/metrics.py GÇö Prometheus metrics:
   - Use prometheus_client library
   - Counters:
     - atlas_http_requests_total (labels: method, endpoint, status_code, role)
     - atlas_auth_attempts_total (labels: result=[success, failure])
     - atlas_fir_ingested_total (labels: district, source)
     - atlas_nlp_predictions_total (labels: category, model_version)
   - Histograms:
     - atlas_http_request_duration_seconds (labels: method, endpoint)
     - atlas_nlp_inference_duration_seconds (labels: model_name)
   - Gauges:
     - atlas_active_users (current logged-in users)
     - atlas_fir_total_count (total FIRs in database)
   - Create FastAPI middleware that auto-increments request counters and histograms

3. backend/app/api/v1/metrics.py GÇö Metrics endpoint:
   - GET /metrics GÇö returns Prometheus exposition format
   - No authentication required (Prometheus scrapes this)

4. infrastructure/prometheus/prometheus.yml GÇö Prometheus config:
   - Global scrape interval: 15s
   - Scrape targets:
     - job: atlas-backend, target: backend:8000, metrics_path: /api/v1/metrics
     - job: postgres, target: postgres-exporter:9187 (optional, add if time permits)
   - Alerting rules file: /etc/prometheus/alerts.yml

5. infrastructure/prometheus/alerts.yml GÇö Alert rules:
   - atlas_high_error_rate: rate of 5xx responses > 5% over 5 minutes (severity: critical)
   - atlas_slow_responses: p95 latency > 3s over 5 minutes (severity: warning)
   - atlas_nlp_slow_inference: p95 NLP inference > 5s over 5 minutes (severity: warning)
   - atlas_service_down: up == 0 for > 1 minute (severity: critical)

6. infrastructure/grafana/dashboards/atlas-overview.json GÇö Grafana dashboard:
   - Provisioned via Grafana config (auto-loaded on startup)
   - Panels:
     a. Request Rate (graph): rate(atlas_http_requests_total[5m]) by status_code
     b. Response Time p95 (graph): histogram_quantile(0.95, atlas_http_request_duration_seconds)
     c. NLP Inference Time (graph): histogram_quantile(0.95, atlas_nlp_inference_duration_seconds)
     d. Error Rate (stat): rate of 5xx / total requests
     e. FIRs Ingested (counter): atlas_fir_ingested_total
     f. Auth Attempts (graph): rate(atlas_auth_attempts_total[5m]) by result
     g. Active Users (gauge): atlas_active_users
   - Datasource: Prometheus at http://prometheus:9090

7. infrastructure/grafana/provisioning/ GÇö Auto-provisioning:
   - datasources.yml: Prometheus datasource
   - dashboards.yml: dashboard provider pointing to /var/lib/grafana/dashboards/

8. Update docker-compose.yml:
   - Add Kibana service (docker.elastic.co/kibana/kibana:8.12.2, port 5601)
   - Mount Grafana provisioning files
   - Mount Grafana dashboard JSON
   - Mount Prometheus config and alerts

9. Add requirements.txt: prometheus-client==0.20.0, python-json-logger==2.0.7

All logging async-safe. Include docstrings. Add type hints."
```

### VALIDATION COMMAND

```bash
# Restart stack with new config:
docker compose up -d --build

# Check Prometheus is scraping:
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Check metrics endpoint:
curl -s http://localhost:8000/api/v1/metrics | head -20

# Generate some traffic then check:
for i in $(seq 1 10); do curl -s http://localhost:8000/health > /dev/null; done
curl -s http://localhost:9090/api/v1/query?query=atlas_http_requests_total | jq .

# Check Grafana dashboard:
curl -s http://localhost:3001/api/dashboards/db/atlas-overview | jq .meta.slug
# Open browser: http://localhost:3001 (admin/atlas_dev_password) GåÆ Atlas Overview dashboard

# Check Kibana:
curl -s http://localhost:5601/api/status | jq .status.overall.state
```

### DONE WHEN
- [ ] Structured JSON logs appear in stdout (visible via `docker compose logs backend`)
- [ ] Prometheus scrapes /metrics successfully (target status: UP)
- [ ] All 7 custom metrics registered and incrementing
- [ ] 4 alert rules loaded in Prometheus
- [ ] Grafana dashboard auto-loads with 7 panels rendering data
- [ ] Kibana accessible at :5601
- [ ] PR merged: `feature/T6-observability` GåÆ `develop`, CI green
- [ ] Jira ATLAS-T6 Done

### STORE AT
Repo: `backend/app/core/logging_config.py`, `backend/app/core/metrics.py`, `infrastructure/prometheus/`, `infrastructure/grafana/` | Jira: ATLAS-T6

### DORA METRIC
**Mean Time to Recovery (MTTR)** GÇö alerting enables rapid failure detection. **Change Failure Rate (CFR)** GÇö monitoring catches degraded deployments.

---
---

# T7-PROMPT GÇö FIR/Charge-Sheet Data Inventory + Quality Audit

**Assignee:** Both (Aditya leads, Prishiv supports) | **Story Points:** 3 | **Days:** 1GÇô3 | **Jira:** ATLAS-T7

---

### ROLE + EST TIME
Aditya (lead, 5 hours) + Prishiv (support, 3 hours) GÇö Days 1GÇô3

### ENVIRONMENT
Claude.ai for research synthesis + Google Sheets/Excel for audit spreadsheet + Claude Code for any automated data profiling.

### EXACT TOOLS
R01-fir-legal-standards.md (from Phase 1 research), Google Sheets or Excel, pandas (for data profiling if sample data available)

### OBJECTIVE
Produce a complete data inventory of all FIR and charge-sheet fields available from eGujCop and NCRB sources, assess data quality per field (completeness, consistency, format), and create the quality audit spreadsheet that becomes the ground-truth validation schema for the ingestion pipeline (T9).

### INPUTS
- R01-fir-legal-standards.md (47-field matrix from Phase 1)
- Any sample FIR data received from Gujarat Police (CSV/PDF)
- NCRB IIF-I form specification
- eGujCop Citizen Portal field observations

### STEPS

```bash
claude "Create a comprehensive data inventory and quality audit document for the ATLAS project.

Using the field-level matrix from R01-fir-legal-standards.md (47 fields across 8 functional groups), create two deliverables:

DELIVERABLE 1: docs/data/data-inventory.md

A markdown document with:

Section 1: Data Source Inventory
List every data source ATLAS will consume:
| Source | Owner | Format | Volume | Access Status | Priority |
|--------|-------|--------|--------|--------------|----------|
| eGujCop FIR database | Gujarat Police IT Cell | PostgreSQL/API TBD | ~2-3 lakh FIRs/year | Pending IT Cell confirmation | P1 - Critical |
| NCRB Crime Code Master | NCRB | CSV/JSON | ~500 codes | Publicly available | P1 |
| BNS Section Master | Legislative Dept | PDF/JSON | 358 sections | Publicly available (create ourselves) | P1 |
| IPC-to-BNS Mapping | MHA | PDF | ~400 mappings | Available from R01 Appendix A | P1 |
| eGujCop Charge-Sheet data | Gujarat Police IT Cell | TBD | Linked to FIRs | Pending | P2 |
| Court Disposition data | ICJS/NIC | TBD | Linked to FIRs | Pending MoU | P3 |
| Geographic coordinates | Google Maps API / manual | Geocoded addresses | Per FIR | ATLAS generates | P2 |
| MO Code Master | NCRB | CSV | ~200 codes | Available from NCRB publications | P1 |

Section 2: Field-Level Inventory (from R01)
Reproduce the 47-field matrix from R01 Section 5.1 with additional columns:
| Field # | Field Name | Source System | Source Field Name (if known) | Data Type | Expected Completeness % | Known Quality Issues |

Section 3: Data Gap Analysis
Identify fields required by ATLAS but not available from any confirmed source:
- Geo-coordinates (ATLAS-critical, not in FIR form)
- Digital evidence metadata (not in standard FIR proforma)
- Historical conviction outcome data (per ADR-D08 SPIKE)
- Modus Operandi narrative (MO code often blank in practice)

Section 4: Data Quality Risk Register
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| IPC/BNS section confusion during transition | High | High (misclassification) | Bidirectional mapping in ingestion pipeline |
| Gujarati/English text mixing | High | Medium (NLP accuracy) | Multilingual pipeline per ADR-D06 |
| Incomplete FIR narratives (<50 words) | Medium | High (NLP fails on short text) | Minimum length check; fallback to structured fields |
| Missing geo-coordinates | High | High (spatial analytics disabled) | Geocoding from address text; GPS capture advocacy |
| MO code blank/generic | High | Medium (pattern analysis degraded) | NLP-based MO suggestion from narrative |

DELIVERABLE 2: docs/data/quality-audit-spreadsheet.csv (or .xlsx)

A spreadsheet with columns:
Field_Number, Field_Name, Source, Data_Type, Mandatory_Status, Expected_Completeness_Percent, Actual_Completeness_Percent (TBD GÇö fill when real data arrives), Format_Validation_Rule, Known_Issues, AI_ML_Relevance_Score, Pipeline_Stage (ingestion/preprocessing/feature_engineering), Remediation_Action

Pre-populate with all 47 fields from R01. The Actual_Completeness_Percent column should be marked 'PENDING GÇö awaiting eGujCop data sample' for now.

This spreadsheet becomes the acceptance criteria for T9 (ingestion pipeline) GÇö every field must pass its format validation rule."
```

### VALIDATION COMMAND

```bash
# Verify documents exist and have content:
wc -l docs/data/data-inventory.md        # Should be 200+ lines
wc -l docs/data/quality-audit-spreadsheet.csv  # Should have 47+ data rows

# Verify CSV is valid:
python -c "import csv; r=csv.reader(open('docs/data/quality-audit-spreadsheet.csv')); rows=list(r); print(f'{len(rows)} rows, {len(rows[0])} columns')"
```

### DONE WHEN
- [ ] Data inventory document covers all 8 data sources with access status
- [ ] 47 fields inventoried with source field mapping (where known)
- [ ] Data gap analysis identifies all missing-but-needed fields
- [ ] Quality risk register has GëÑ 5 risks with mitigations
- [ ] Audit spreadsheet has all 47 fields with validation rules
- [ ] Both team members have reviewed and agreed on the inventory
- [ ] PR merged: `feature/T7-data-inventory` GåÆ `develop`
- [ ] Jira ATLAS-T7 Done

### STORE AT
Repo: `docs/data/data-inventory.md`, `docs/data/quality-audit-spreadsheet.csv` | Jira: ATLAS-T7

### DORA METRIC
**Change Failure Rate (CFR)** GÇö data quality issues caught in audit prevent downstream pipeline failures.

---
---

# T8-PROMPT GÇö MongoDB + PostgreSQL Schema Design (ERD + JSON Schema)

**Assignee:** Both (Prishiv leads DB design, Aditya leads JSON schema) | **Story Points:** 3 | **Days:** 3GÇô5 | **Jira:** ATLAS-T8

---

### ROLE + EST TIME
Prishiv (PostgreSQL ERD, 4 hours) + Aditya (MongoDB JSON schemas, 4 hours) GÇö Days 3GÇô5

### ENVIRONMENT
Claude Code terminal for schema generation. Draw.io / Mermaid for ERD.

### OBJECTIVE
Design the complete database schema: PostgreSQL for relational data (users, audit logs, roles, reference tables) and MongoDB for document data (FIRs, NLP results, case timelines). Produce ERD diagram, JSON schema validation documents, and index strategy.

### STEPS

```bash
claude "Design the complete database schema for ATLAS. This is a polyglot persistence architecture: PostgreSQL for structured/relational data, MongoDB for semi-structured document data.

DELIVERABLE 1: docs/architecture/erd-postgresql.mermaid GÇö Mermaid ERD

Include these PostgreSQL tables:
- users (from T5 GÇö already exists)
- audit_logs (from T5 GÇö already exists)
- reference_acts (id, act_code, act_name, is_active, effective_date) GÇö BNS, IPC, POCSO, IT Act etc.
- reference_sections (id, act_id FK, section_number, description, chapter, punishment_description, cognizable boolean, bailable boolean, ipc_equivalent_section nullable)
- reference_crime_heads (id, major_head_code, major_head_description, minor_head_code, minor_head_description)
- reference_mo_codes (id, mo_code, description, category)
- reference_districts (id, district_code, district_name, state, is_pilot boolean)
- reference_police_stations (id, ps_code, ps_name, district_id FK, latitude, longitude)
- user_sessions (id, user_id FK, token_jti, created_at, expires_at, revoked_at nullable, ip_address, user_agent)
- system_config (key, value, updated_by FK, updated_at) GÇö for runtime configuration
- nlp_model_registry (id, model_name, model_version, model_type, file_path, is_active, deployed_at, metrics_json, deployed_by FK)

Show all relationships, primary keys, foreign keys, and indexes.

DELIVERABLE 2: docs/architecture/schema-mongodb.json GÇö MongoDB collection schemas

For each MongoDB collection (firs, nlp_results, audit_trail_nlp from T5), create a detailed JSON Schema document that includes:
- All fields with types, required flags, descriptions
- Nested object schemas (complainant, accused, property)
- Array schemas (acts_sections, witnesses, accused list)
- Enum constraints (crime categories, language codes)
- Index definitions with rationale
- Example documents

Add these additional collections:
- 'case_timeline': {fir_id, events: [{event_type: enum(fir_registered, investigation_started, chargesheet_filed, court_hearing, verdict), date, details, source_system}]}
- 'ingestion_log': {batch_id, source, started_at, completed_at, records_total, records_success, records_failed, errors: [{record_id, error_type, error_message}]}

DELIVERABLE 3: docs/architecture/index-strategy.md

Document the indexing strategy:
- PostgreSQL: list all indexes with rationale (lookup pattern they serve)
- MongoDB: list all indexes with expected query patterns
- Compound indexes for common filter combinations (district + date range, crime_head + district)
- Text index on FIR narrative for text search (MongoDB)
- TTL index on ingestion_log (auto-delete after 90 days)

DELIVERABLE 4: docs/architecture/data-flow-diagram.mermaid

Mermaid diagram showing data flow:
eGujCop GåÆ Ingestion Pipeline GåÆ MongoDB (firs) GåÆ NLP Pipeline GåÆ MongoDB (nlp_results) GåÆ API GåÆ Frontend
                                    Gåò
                              PostgreSQL (reference data, users, audit)
"
```

### VALIDATION COMMAND

```bash
# Verify Mermaid renders:
npx -y @mermaid-js/mermaid-cli mmdc -i docs/architecture/erd-postgresql.mermaid -o docs/architecture/erd-postgresql.png

# Verify JSON schemas are valid:
python -c "
import json
with open('docs/architecture/schema-mongodb.json') as f:
    schemas = json.load(f)
    for name, schema in schemas.items():
        assert 'properties' in schema or 'items' in schema, f'{name} missing properties'
        print(f'G£ô {name}: {len(schema.get(\"properties\", {}))} fields')
"

# Verify index strategy document:
grep -c "INDEX" docs/architecture/index-strategy.md  # Should find multiple
```

### DONE WHEN
- [ ] PostgreSQL ERD with 11 tables, all relationships, all indexes
- [ ] MongoDB JSON schemas for 5 collections with validation rules
- [ ] Index strategy document covering both databases
- [ ] Data flow diagram created
- [ ] Both team members have reviewed and approved the schema
- [ ] PR merged: `feature/T8-schema-design` GåÆ `develop`
- [ ] Jira ATLAS-T8 Done

### STORE AT
Repo: `docs/architecture/` | Jira: ATLAS-T8

### DORA METRIC
**Lead Time (LT)** GÇö well-designed schemas reduce future migration overhead.

---
---

# T9-PROMPT GÇö Data Ingestion Pipeline (PDF/Text/Structured GåÆ MongoDB)

**Assignee:** Aditya | **Story Points:** 3 | **Days:** 5GÇô7 | **Jira:** ATLAS-T9

---

### ROLE + EST TIME
Aditya GÇö 8 hours across Days 5GÇô7

### ENVIRONMENT
Claude Code terminal. T2 Docker (MongoDB), T5 seed data, T8 schema.

### EXACT TOOLS
Python, PyMuPDF/pdfplumber (PDF parsing), pandas, Motor (async MongoDB), Pydantic v2 (validation)

### OBJECTIVE
Build a modular ingestion pipeline that can consume FIR data from 3 formats (structured CSV/JSON, plain text files, scanned/digital PDFs), validate against the quality audit schema (T7), transform to the MongoDB FIR document schema (T8), and load into MongoDB with comprehensive error handling and logging.

### STEPS

```bash
claude "Build the ATLAS data ingestion pipeline in backend/app/services/ingestion/.

Directory structure:
backend/app/services/ingestion/
Gö£GöÇGöÇ __init__.py
Gö£GöÇGöÇ pipeline.py          # Main pipeline orchestrator
Gö£GöÇGöÇ parsers/
Göé   Gö£GöÇGöÇ __init__.py
Göé   Gö£GöÇGöÇ csv_parser.py    # Parse structured CSV/TSV
Göé   Gö£GöÇGöÇ json_parser.py   # Parse structured JSON/JSONL
Göé   Gö£GöÇGöÇ pdf_parser.py    # Parse PDF FIR documents
Göé   GööGöÇGöÇ text_parser.py   # Parse plain text FIR narratives
Gö£GöÇGöÇ validators/
Göé   Gö£GöÇGöÇ __init__.py
Göé   GööGöÇGöÇ fir_validator.py # Pydantic models for FIR validation
Gö£GöÇGöÇ transformers/
Göé   Gö£GöÇGöÇ __init__.py
Göé   Gö£GöÇGöÇ section_normalizer.py  # IPCGåÆBNS section mapping
Göé   GööGöÇGöÇ field_mapper.py        # Map source fields to ATLAS schema
GööGöÇGöÇ loaders/
    Gö£GöÇGöÇ __init__.py
    GööGöÇGöÇ mongodb_loader.py      # Async batch insert to MongoDB

Specification:

1. pipeline.py GÇö IngestionPipeline class:
   - async def ingest(source_path: str, source_format: str, source_name: str) -> IngestionResult
   - Orchestrates: parse GåÆ validate GåÆ transform GåÆ load
   - Creates ingestion_log entry in MongoDB at start
   - Updates ingestion_log with results at end
   - Returns IngestionResult(batch_id, total, success, failed, errors, duration_seconds)
   - All errors are caught and logged, never crash the pipeline GÇö skip bad records

2. csv_parser.py GÇö CSVParser:
   - Parse CSV/TSV with configurable delimiter, encoding (utf-8, utf-8-sig, latin-1)
   - Map column headers to ATLAS field names (configurable header mapping dict)
   - Handle Gujarati Unicode in CSV cells
   - Return list of dict records

3. json_parser.py GÇö JSONParser:
   - Parse JSON array or JSONL (one JSON object per line)
   - Support nested structures (complainant.name, accused[0].name)
   - Return list of dict records

4. pdf_parser.py GÇö PDFParser:
   - Use pdfplumber to extract text from each page
   - Attempt to identify FIR form fields using regex patterns:
     - 'FIR No[.:]?\s*(\d+)' for FIR number
     - 'District[.:]?\s*(.+)' for district
     - 'Police Station[.:]?\s*(.+)' for PS
     - 'Date[.:]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})' for dates
     - 'Act.*Section[.:]?\s*(.+)' for acts and sections
     - 'Gist of Information[.:]?\s*(.+)' for narrative (capture everything after this header until next section header)
   - For each successfully extracted field, populate the record dict
   - Store full raw text in 'raw_text' field regardless of extraction success
   - Return list of dict records (typically 1 per PDF, but handle multi-FIR PDFs)

5. text_parser.py GÇö TextParser:
   - Read plain text file as a single FIR narrative
   - Minimal structure extraction (date, FIR number if present in text)
   - Store full text as 'narrative' and 'raw_text'

6. fir_validator.py GÇö Pydantic validation:
   - class FIRDocument(BaseModel): with all fields from T8 MongoDB schema
   - Required fields: fir_id (auto-generate UUID if not present), narrative
   - Optional fields: all others (graceful handling of missing data)
   - Validators:
     - fir_date must be a valid date (parse multiple formats: DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY)
     - acts_sections: each must have valid act name
     - crime_head_major: must be in reference list (warn if not, don't reject)
   - model_config: validate_assignment=True, str_strip_whitespace=True

7. section_normalizer.py GÇö IPCGåöBNS mapping:
   - Load the mapping table from data/reference/ipc_bns_mapping.json
   - def normalize_section(act: str, section: str) -> tuple[str, str]:
     - If act is 'IPC' and section has a BNS equivalent: return ('BNS', bns_section)
     - If act is already 'BNS': return as-is
     - If unknown: return as-is with a warning log
   - Apply to all acts_sections in the FIR during transformation

8. field_mapper.py GÇö Source-to-ATLAS field mapping:
   - Configurable mapping dict: {source_field_name: atlas_field_name}
   - Default mappings for common eGujCop-like field names
   - Handle nested field creation (flat source GåÆ nested ATLAS: e.g., 'complainant_name' GåÆ complainant.name)

9. mongodb_loader.py GÇö Async batch loader:
   - async def load_batch(documents: list[dict], collection: str = 'firs') -> LoadResult
   - Use Motor insert_many with ordered=False (continue on individual insert errors)
   - Handle duplicate key errors (upsert or skip based on config)
   - Return LoadResult(inserted, duplicates_skipped, errors)

10. Create API endpoint: POST /api/v1/ingest
    - Accept multipart file upload (CSV, JSON, JSONL, PDF, TXT)
    - Accept query params: source_format (auto-detect if not provided), source_name
    - Requires ADMIN role
    - Returns IngestionResult
    - Also create: GET /api/v1/ingest/logs GÇö returns recent ingestion_log entries

11. Tests:
    - test_csv_parser.py: parse sample CSV with 5 FIRs, verify field mapping
    - test_json_parser.py: parse sample JSONL with 5 FIRs
    - test_pdf_parser.py: parse a sample FIR PDF (create a test fixture)
    - test_validator.py: test valid FIR passes, invalid FIR fails with specific errors
    - test_section_normalizer.py: IPC 302 GåÆ BNS 103, IPC 376 GåÆ BNS 63
    - test_pipeline.py: end-to-end pipeline test with CSV input GåÆ MongoDB output

12. Create data/reference/ipc_bns_mapping.json with the mapping from R01 Appendix A (at least 30 key sections).

13. Add requirements.txt: pdfplumber==0.11.0

All async. Comprehensive error handling. Type hints. Docstrings."
```

### VALIDATION COMMAND

```bash
cd backend
# Run ingestion tests:
pytest tests/test_ingestion/ -v

# Manual test with seed data CSV:
python -c "
import asyncio
from app.services.ingestion.pipeline import IngestionPipeline
pipeline = IngestionPipeline()
result = asyncio.run(pipeline.ingest('data/test/sample_firs.csv', 'csv', 'test_batch'))
print(result)
"

# Test API endpoint:
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"test_admin","password":"testpass123"}' | jq -r .access_token)

curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@data/test/sample_firs.csv" \
  -F "source_format=csv" \
  -F "source_name=test_upload"

# Check ingestion log:
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/ingest/logs | jq .
```

### DONE WHEN
- [ ] Pipeline parses CSV, JSON, PDF, and TXT formats
- [ ] Pydantic validation catches invalid records without crashing
- [ ] IPCGåÆBNS section normalisation working (tested with GëÑ 30 mappings)
- [ ] Ingestion API endpoint functional (ADMIN-only)
- [ ] Ingestion log tracks every batch with success/failure counts
- [ ] All tests pass
- [ ] PR merged: `feature/T9-ingestion-pipeline` GåÆ `develop`, CI green
- [ ] Jira ATLAS-T9 Done

### STORE AT
Repo: `backend/app/services/ingestion/`, `data/reference/ipc_bns_mapping.json` | Jira: ATLAS-T9

### DORA METRIC
**Deployment Frequency (DF)** GÇö automated ingestion enables continuous data updates. **CFR** GÇö validation prevents corrupt data from entering the system.

---
---

# T10-PROMPT GÇö PII Detection + Redaction Pipeline (NER + Regex)

**Assignee:** Prishiv | **Story Points:** 3 | **Days:** 5GÇô7 | **Jira:** ATLAS-T10

---

### ROLE + EST TIME
Prishiv GÇö 8 hours across Days 5GÇô7

### ENVIRONMENT
Claude Code terminal. T5 (MongoDB with seed FIRs), T9 (ingestion pipeline).

### EXACT TOOLS
spaCy (en_core_web_sm + Gujarati model if available), regex, Presidio (Microsoft PII detection library), custom NER patterns

### OBJECTIVE
Build a PII detection and redaction pipeline that identifies personal information (names, Aadhaar numbers, phone numbers, addresses, bank accounts) in FIR text and can either mask or redact them for different access levels, complying with DPDP Act 2023 data minimisation principles.

### STEPS

```bash
claude "Build the PII detection and redaction pipeline for ATLAS in backend/app/services/pii/.

Directory structure:
backend/app/services/pii/
Gö£GöÇGöÇ __init__.py
Gö£GöÇGöÇ detector.py          # PII detection engine
Gö£GöÇGöÇ redactor.py          # Redaction/masking engine
Gö£GöÇGöÇ patterns.py          # Regex patterns for Indian PII
GööGöÇGöÇ config.py            # PII categories and sensitivity levels

Specification:

1. config.py GÇö PII categories and sensitivity levels:
   - enum PIICategory: PERSON_NAME, AADHAAR_NUMBER, PHONE_NUMBER, EMAIL, ADDRESS, BANK_ACCOUNT, VEHICLE_NUMBER, PASSPORT_NUMBER, VOTER_ID, CASTE, RELIGION
   - enum SensitivityLevel: HIGH (Aadhaar, bank), MEDIUM (phone, email, address), LOW (vehicle number, voter ID)
   - enum RedactionMode: FULL (replace with [REDACTED]), PARTIAL (show last 4 digits), MASK (replace chars with *), NONE (no redaction)
   - Mapping: which role sees which redaction mode for each PII category
     - IO: FULL redaction on accused's Aadhaar/bank; NONE on complainant details (they need them)
     - SHO: PARTIAL on Aadhaar (show last 4); NONE on most fields
     - READ_ONLY: FULL redaction on all HIGH sensitivity PII
     - ADMIN: FULL redaction on all PII (admin shouldn't see case data)

2. patterns.py GÇö Indian PII regex patterns:
   - AADHAAR: r'\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b' (12 digits, not starting with 0 or 1)
   - PHONE_INDIA: r'\b(?:\+91[\s-]?)?[6-9]\d{9}\b'
   - EMAIL: standard email regex
   - PAN: r'\b[A-Z]{5}\d{4}[A-Z]\b'
   - VEHICLE_GJ: r'\bGJ[\s-]?\d{1,2}[\s-]?[A-Z]{1,2}[\s-]?\d{4}\b' (Gujarat vehicle)
   - BANK_ACCOUNT: r'\b\d{9,18}\b' (context-dependent GÇö only flag if near keywords like 'account', 'A/C', 'añûañ+aññañ+')
   - PASSPORT: r'\b[A-Z]\d{7}\b'
   - PINCODE: r'\b\d{6}\b' (context: near 'pin', 'pincode', or after address text)
   - All patterns should be compiled (re.compile) for performance

3. detector.py GÇö PIIDetector class:
   - def detect(text: str) -> list[PIIDetection]:
     - PIIDetection: category, text_match, start_pos, end_pos, confidence (0-1), detection_method (regex/ner)
   - Two detection methods:
     a. Regex-based: apply all patterns from patterns.py
     b. NER-based: use spaCy model for PERSON, GPE (location), ORG detection
   - Merge detections: if regex and NER detect the same span, prefer higher confidence
   - Deduplicate overlapping detections (keep longest span)
   - Return sorted list by position

4. redactor.py GÇö PIIRedactor class:
   - def redact(text: str, detections: list[PIIDetection], user_role: Role) -> RedactedText:
     - RedactedText: redacted_text (str), redaction_log (list of what was redacted and why)
   - Apply redaction mode based on user_role and PII category mapping from config
   - Preserve text structure GÇö only replace PII spans, keep everything else
   - For PARTIAL mode: show last 4 characters (e.g., 'XXXX XXXX 1234' for Aadhaar)
   - For MASK mode: replace each character with * except spaces
   - For FULL mode: replace with '[REDACTED-{category}]'
   - Return both the redacted text and a log of all redactions performed

5. Integration with ingestion pipeline (T9):
   - Add a post-ingestion step: after FIR is loaded to MongoDB, run PII detection
   - Store detection results in a separate field: fir.pii_detections = [{category, start, end, confidence}]
   - Do NOT redact the stored text GÇö store original, redact at API response time
   - This way, higher-privileged roles can see unredacted text while lower roles see redacted

6. API middleware integration:
   - Create a response middleware or serializer that applies role-based redaction to FIR text fields before sending to client
   - Add to FIR API endpoints (to be built in Sprint 2) as a dependency

7. Tests:
   - test_patterns.py: test each regex against positive and negative examples
     - Aadhaar: '1234 5678 9012' should NOT match (starts with 1), '2345 6789 0123' SHOULD match
     - Phone: '+91 9876543210' should match, '1234567890' should NOT (starts with 1)
     - Vehicle: 'GJ 01 AB 1234' should match
   - test_detector.py: test detection on sample FIR text with known PII
   - test_redactor.py: test redaction for IO role (high redaction) vs SHO role (partial) vs SP role (minimal)
   - test_integration.py: detect PII in seed FIR data, verify all Aadhaar-like numbers are detected

8. Requirements: spacy==3.7.4, install en_core_web_sm model

Include comprehensive docstrings. Type hints throughout. Log all detections at DEBUG level."
```

### VALIDATION COMMAND

```bash
cd backend
# Download spaCy model:
python -m spacy download en_core_web_sm

# Run PII tests:
pytest tests/test_pii/ -v

# Test on seed data:
python -c "
from app.services.pii.detector import PIIDetector
detector = PIIDetector()
sample = 'Complainant Ramesh Patel, Aadhaar 2345 6789 0123, phone +91 9876543210, residing at 12 MG Road, Ahmedabad 380001, Gujarat. FIR registered against accused with vehicle GJ 01 AB 1234.'
detections = detector.detect(sample)
for d in detections:
    print(f'  {d.category}: \"{d.text_match}\" (confidence: {d.confidence})')
"
# Expected: PERSON_NAME, AADHAAR_NUMBER, PHONE_NUMBER, ADDRESS/PINCODE, VEHICLE_NUMBER detected
```

### DONE WHEN
- [ ] PII detection finds Aadhaar, phone, email, vehicle, PAN, names in test text
- [ ] Role-based redaction produces different outputs for different roles
- [ ] Regex patterns validated with positive and negative test cases
- [ ] Integration point with ingestion pipeline documented
- [ ] All tests pass with GëÑ 85% coverage on pii/ module
- [ ] PR merged: `feature/T10-pii-pipeline` GåÆ `develop`, CI green
- [ ] Jira ATLAS-T10 Done

### STORE AT
Repo: `backend/app/services/pii/` | Jira: ATLAS-T10

### DORA METRIC
**Change Failure Rate (CFR)** GÇö PII leakage is a critical change failure with legal consequences under DPDP Act.

---
---

# T11-PROMPT GÇö Architecture ADR (Modular Monolith Decision + C4 Diagrams)

**Assignee:** Both (Amit facilitates; Prishiv + Aditya are decision-makers) | **Story Points:** 3 | **Days:** 1GÇô3 | **Jira:** ATLAS-T11

---

### ROLE + EST TIME
Amit (facilitator, 1.5 hours) + Prishiv (2 hours) + Aditya (2 hours) GÇö Days 1GÇô3

### ENVIRONMENT
In-person or video call for deliberation (use D01-PROMPT from deliberation document). Claude.ai for C4 diagram generation. Claude Code for Mermaid rendering.

### EXACT TOOLS
D01-PROMPT (deliberation session guide), Mermaid.js (for C4 diagrams), MkDocs/wiki

### OBJECTIVE
Execute the D01 deliberation session, produce signed ADR-D01, and create C4 model diagrams (Context, Container, Component levels) documenting the chosen architecture.

### STEPS

**Step 1: Run the D01 Deliberation Session** (75 minutes)
- Follow D01-PROMPT exactly from the deliberation document
- Amit facilitates; Prishiv and Aditya are decision-makers
- Score the three options (Modular Monolith, Microservices, Hybrid) against weighted criteria
- Reach consensus or Amit casts deciding vote

**Step 2: Draft the ADR** (during session)
- Fill in the ADR template from D01-PROMPT with the session's decisions
- All three team members sign off

**Step 3: Create C4 Diagrams** (post-session, 2 hours)

```bash
claude "Create C4 architecture diagrams for the ATLAS platform using Mermaid syntax. The architecture decision is MODULAR MONOLITH with async NLP worker (Option C from ADR-D01 GÇö adjust if team chose differently).

Create 3 diagrams:

1. docs/architecture/c4-context.mermaid GÇö C4 Context Diagram:
   External actors:
   - Gujarat Police Officers (IO, SHO, DySP, SP) GÇö use ATLAS dashboard
   - Gujarat Police Admin (IT Cell) GÇö manages system
   - eGujCop System GÇö provides FIR data
   - NCRB CCTNS GÇö receives statistical returns / provides code masters
   - ICJS GÇö future integration (court data)
   System: ATLAS Platform

2. docs/architecture/c4-container.mermaid GÇö C4 Container Diagram:
   Within ATLAS:
   - Next.js Frontend (browser-based SPA)
   - FastAPI Backend (REST API GÇö main application)
   - NLP Worker (Celery/RQ GÇö async NLP processing, can be in-process or separate)
   - PostgreSQL Database (users, audit logs, reference data)
   - MongoDB Database (FIRs, NLP results, ingestion logs)
   - Redis (JWT blacklist, session cache, Celery broker)
   - Prometheus + Grafana (monitoring)
   - ELK Stack (logging)
   Show communication protocols: HTTPS, async task queue, TCP database connections

3. docs/architecture/c4-component.mermaid GÇö C4 Component Diagram (Backend only):
   Within FastAPI Backend:
   - API Layer: Auth endpoints, FIR endpoints, Analytics endpoints, Ingestion endpoints, Admin endpoints
   - Core Layer: JWT Security, RBAC Middleware, Audit Logger, Request ID Middleware
   - Service Layer: Ingestion Service, NLP Service (interface), PII Service, Analytics Service
   - Data Layer: PostgreSQL Repository, MongoDB Repository, Redis Client
   - NLP Module: Language Detector, Text Preprocessor, Classifier, NER Extractor, Section Normalizer
   Show dependencies between components (arrows).

Also create: docs/architecture/deployment-diagram.mermaid
   Show deployment for:
   - Development: Docker Compose on developer laptop
   - Staging: Docker Compose on Gujarat State Data Centre VM
   - Production (target): Kubernetes on Gujarat State Data Centre / NIC Cloud

Use Mermaid C4 syntax (C4Context, C4Container, C4Component). Render to PNG using mmdc."
```

**Step 4: Render diagrams**

```bash
# Install mermaid CLI if needed:
npm install -g @mermaid-js/mermaid-cli

# Render all diagrams:
mmdc -i docs/architecture/c4-context.mermaid -o docs/architecture/c4-context.png
mmdc -i docs/architecture/c4-container.mermaid -o docs/architecture/c4-container.png
mmdc -i docs/architecture/c4-component.mermaid -o docs/architecture/c4-component.png
mmdc -i docs/architecture/deployment-diagram.mermaid -o docs/architecture/deployment-diagram.png
```

### VALIDATION COMMAND

```bash
# Verify ADR exists and is signed:
cat docs/decisions/ADR-D01-system-architecture.md | grep -c "Sign-off"

# Verify diagrams render:
ls -la docs/architecture/*.png  # Should show 4 PNG files

# Verify Mermaid source is valid:
mmdc -i docs/architecture/c4-context.mermaid -o /dev/null  # Should exit 0
```

### DONE WHEN
- [ ] D01 deliberation session completed (75 min)
- [ ] ADR-D01 signed by all 3 team members
- [ ] C4 Context, Container, Component, and Deployment diagrams created
- [ ] All diagrams rendered to PNG
- [ ] ADR committed to `docs/decisions/ADR-D01-system-architecture.md`
- [ ] Diagrams committed to `docs/architecture/`
- [ ] PR merged: `feature/T11-architecture-adr` GåÆ `develop`
- [ ] Jira ATLAS-T11 Done

### STORE AT
Repo: `docs/decisions/ADR-D01-system-architecture.md`, `docs/architecture/*.mermaid`, `docs/architecture/*.png` | Jira: ATLAS-T11

### DORA METRIC
**Lead Time (LT)** GÇö clear architecture reduces design-decision delays in later sprints.

---
---

# T12-PROMPT GÇö RBAC Matrix (6 Roles) + FastAPI Role Enum Implementation

**Assignee:** Prishiv | **Story Points:** 2 | **Days:** 3GÇô4 | **Jira:** ATLAS-T12

---

### ROLE + EST TIME
Prishiv GÇö 4 hours across Days 3GÇô4

### ENVIRONMENT
Claude Code terminal. T3 (FastAPI auth/RBAC code) must be complete.

### EXACT TOOLS
FastAPI, Pydantic v2, Excel/CSV (for RBAC matrix document)

### OBJECTIVE
Formalise the RBAC matrix from ADR-D03 into a machine-readable format, implement role-permission checking in FastAPI middleware, and create the human-readable RBAC matrix document for the wiki.

### STEPS

```bash
claude "Formalise the RBAC implementation for ATLAS.

1. Create docs/security/rbac-matrix.md:
   A human-readable table documenting every permission for every role.
   
   Format:
   | Feature / Action | IO | SHO | DySP | SP | Admin | Read-Only |
   |-----------------|:--:|:---:|:----:|:--:|:-----:|:---------:|
   | Login | G£ô | G£ô | G£ô | G£ô | G£ô | G£ô |
   | View own-station FIRs | G£ô | G£ô | G£ô | G£ô | GÇö | G£ô* |
   | View cross-station FIRs (same district) | GÇö | G£ô | G£ô | G£ô | GÇö | G£ô* |
   | View cross-district FIRs | GÇö | GÇö | GÇö | G£ô | GÇö | G£ô* |
   | View NLP classification results | G£ô | G£ô | G£ô | G£ô | GÇö | G£ô |
   | Override NLP classification | GÇö | G£ô | G£ô | G£ô | GÇö | GÇö |
   | View victim identity (BNS Ch.V cases) | G£ôGÇá | G£ôGÇá | G£ôGÇá | G£ôGÇá | GÇö | GÇö |
   | Export data (CSV/PDF) | GÇö | G£ô | G£ô | G£ô | GÇö | GÇö |
   | View analytics dashboard | G£ô | G£ô | G£ô | G£ô | GÇö | G£ô |
   | View bias audit reports | GÇö | GÇö | G£ô | G£ô | G£ô | G£ô |
   | Manage users | GÇö | GÇö | GÇö | GÇö | G£ô | GÇö |
   | View audit log | GÇö | GÇö | GÇö | G£ô | G£ô | GÇö |
   | Configure system | GÇö | GÇö | GÇö | GÇö | G£ô | GÇö |
   | Trigger data ingestion | GÇö | GÇö | GÇö | GÇö | G£ô | GÇö |
   | View ingestion logs | GÇö | GÇö | GÇö | G£ô | G£ô | GÇö |
   | Access API /metrics | GÇö | GÇö | GÇö | GÇö | G£ô | GÇö |
   
   G£ô* = Read-only: can view aggregated data, not individual FIR details
   G£ôGÇá = Victim identity in sexual offence cases: masked by default; requires explicit 'View Restricted' action with audit log entry. Access granted only for officers assigned to the case or supervisory chain.

   Add notes explaining the data masking rules for victim identity.

2. Create docs/security/rbac-matrix.json:
   Machine-readable version:
   {
     'roles': {
       'IO': {
         'permissions': ['VIEW_OWN_STATION_FIRS', 'VIEW_NLP_RESULTS', 'VIEW_ANALYTICS'],
         'data_scope': {'firs': 'own_station', 'analytics': 'own_station'},
         'restricted_fields': {'victim_identity_sexual_offence': 'masked_unless_case_assigned'}
       },
       ...for all 6 roles
     }
   }

3. Update backend/app/core/roles.py (from T3):
   Add the data scope concept:
   - DataScope enum: OWN_STATION, OWN_DISTRICT, ALL_DISTRICTS, NONE
   - ROLE_DATA_SCOPE: dict mapping each role to its FIR visibility scope
   - Add helper: def get_fir_query_filter(role: Role, user_station: str, user_district: str) -> dict
     - Returns a MongoDB filter dict that limits FIR queries to the role's data scope

4. Create backend/app/core/data_masking.py:
   - def mask_victim_identity(fir_doc: dict, user_role: Role, user_id: str, case_assigned_to: list[str]) -> dict:
     - If FIR category is 'crimes_against_women_children' AND user is not assigned to this case AND user is not in supervisory chain:
       - Replace victim name with '[IDENTITY PROTECTED GÇö BNS S.72]'
       - Replace victim address with '[ADDRESS PROTECTED]'
       - Log the access attempt to audit_trail_nlp
     - If user IS assigned or in supervisory chain: return unmasked but log the access

5. Write tests:
   - test_data_scope.py: IO can query only own station FIRs; SHO can query own station; SP can query all
   - test_data_masking.py: victim identity masked for non-assigned IO, unmasked for case-assigned IO, logged in both cases

All type hints. Docstrings."
```

### VALIDATION COMMAND

```bash
cd backend
pytest tests/test_rbac.py tests/test_data_scope.py tests/test_data_masking.py -v

# Verify RBAC matrix document:
cat docs/security/rbac-matrix.md | grep -c "G£ô"  # Should be 50+

# Verify JSON is valid:
python -c "import json; json.load(open('docs/security/rbac-matrix.json')); print('Valid JSON')"
```

### DONE WHEN
- [ ] RBAC matrix document (human-readable) committed to wiki
- [ ] RBAC matrix JSON (machine-readable) committed
- [ ] Data scope filtering implemented and tested
- [ ] Victim identity masking implemented and tested (BNS S.72 compliance)
- [ ] All tests pass
- [ ] PR merged: `feature/T12-rbac-implementation` GåÆ `develop`, CI green
- [ ] Jira ATLAS-T12 Done

### STORE AT
Repo: `docs/security/rbac-matrix.md`, `docs/security/rbac-matrix.json`, `backend/app/core/data_masking.py` | Jira: ATLAS-T12

### DORA METRIC
**Change Failure Rate (CFR)** GÇö RBAC bugs are security-critical failures.

---
---

# T13-PROMPT GÇö OpenAPI 3.0 Spec (All 4 Modules) + Swagger at /docs

**Assignee:** Aditya | **Story Points:** 3 | **Days:** 4GÇô6 | **Jira:** ATLAS-T13

---

### ROLE + EST TIME
Aditya GÇö 6 hours across Days 4GÇô6

### ENVIRONMENT
Claude Code terminal. T3 (FastAPI running) must be complete.

### EXACT TOOLS
FastAPI auto-generated OpenAPI, Pydantic v2 models, Swagger UI (built into FastAPI)

### OBJECTIVE
Define the complete API contract for all 4 ATLAS modules (SOP Assistant, FIR Review, Charge-Sheet, Dashboard) as OpenAPI 3.0 spec, implement route stubs with proper Pydantic request/response models, and verify Swagger UI renders at /docs.

### STEPS

```bash
claude "Define the complete ATLAS API surface as FastAPI route stubs with Pydantic models. All endpoints should return proper OpenAPI documentation. Implement route handlers as stubs that return mock data GÇö real logic comes in Sprint 2+.

Create these API modules:

1. backend/app/api/v1/firs.py GÇö FIR Review Module:
   Endpoints:
   - GET /firs GÇö List FIRs (paginated, filterable by district, date_range, category, status)
     Query params: page, per_page, district, date_from, date_to, category, search_text
     Response: {total, page, per_page, results: [FIRSummary]}
     Requires: VIEW_OWN_STATION_FIRS (data scope filter applied per role)
   
   - GET /firs/{fir_id} GÇö Get FIR details with NLP results
     Response: {fir: FIRDetail, nlp: NLPResult | null, pii_redacted: bool}
     Requires: VIEW_OWN_STATION_FIRS + data scope check
   
   - PATCH /firs/{fir_id}/classification GÇö Override NLP classification
     Request: {new_category: str, reason: str}
     Response: {status: 'updated', audit_log_id: str}
     Requires: OVERRIDE_NLP_CLASSIFICATION
   
   - GET /firs/{fir_id}/timeline GÇö Get case timeline
     Response: {events: [TimelineEvent]}
     Requires: VIEW_OWN_STATION_FIRS
   
   - POST /firs/{fir_id}/restricted-access GÇö Request access to restricted victim info
     Request: {justification: str}
     Response: {granted: bool, audit_log_id: str}
     Requires: VIEW_VICTIM_IDENTITY_RESTRICTED

2. backend/app/api/v1/analytics.py GÇö Dashboard Module:
   Endpoints:
   - GET /analytics/dashboard GÇö Dashboard summary stats
     Query params: district, date_from, date_to
     Response: {total_firs, pending_review, classified_today, accuracy_rate, category_distribution: dict}
     Requires: VIEW_ANALYTICS
   
   - GET /analytics/trends GÇö Crime trend data (time series)
     Query params: district, category, granularity=[daily|weekly|monthly], date_from, date_to
     Response: {labels: [str], datasets: [{label, data: [int]}]}
     Requires: VIEW_ANALYTICS
   
   - GET /analytics/heatmap GÇö Geographic crime distribution
     Query params: district, category, date_from, date_to
     Response: {points: [{lat, lng, intensity, category}]}
     Requires: VIEW_ANALYTICS
   
   - GET /analytics/bias-report GÇö Model bias audit summary
     Response: per ADR-D05 format
     Requires: VIEW_BIAS_REPORTS

3. backend/app/api/v1/sop.py GÇö SOP Assistant Module:
   Endpoints:
   - POST /sop/query GÇö Ask SOP question
     Request: {question: str, context: str | null}
     Response: {answer: str, sources: [SOPSource], confidence: float}
     Requires: any authenticated user
   
   - GET /sop/categories GÇö List SOP categories
     Response: {categories: [SOPCategory]}

4. backend/app/api/v1/chargesheet.py GÇö Charge-Sheet Module:
   Endpoints:
   - GET /chargesheet/{fir_id} GÇö Get charge-sheet draft for FIR
     Response: {fir_id, recommended_sections: [Section], evidence_checklist: [EvidenceItem], completeness_score: float}
     Requires: VIEW_OWN_STATION_FIRS
   
   - POST /chargesheet/{fir_id}/generate GÇö Generate charge-sheet draft
     Request: {include_sections: [str], notes: str | null}
     Response: {draft_id, status: 'generating'}
     Requires: OVERRIDE_NLP_CLASSIFICATION (SHO+ only)

5. backend/app/api/v1/admin.py GÇö Admin Module:
   Endpoints:
   - GET /admin/users GÇö List users (paginated)
   - POST /admin/users GÇö Create user
   - PATCH /admin/users/{user_id} GÇö Update user
   - DELETE /admin/users/{user_id} GÇö Deactivate user
   - GET /admin/audit-log GÇö Audit log entries (paginated, filterable)
   - GET /admin/system-config GÇö Get system configuration
   - PATCH /admin/system-config GÇö Update system configuration
   All require: MANAGE_USERS or VIEW_AUDIT_LOG or CONFIGURE_SYSTEM

6. Pydantic models in backend/app/schemas/:
   - schemas/fir.py: FIRSummary, FIRDetail, FIRFilter, NLPResult, TimelineEvent, ClassificationOverride
   - schemas/analytics.py: DashboardStats, TrendData, HeatmapPoint, BiasReport
   - schemas/sop.py: SOPQuery, SOPResponse, SOPCategory, SOPSource
   - schemas/chargesheet.py: ChargeSheetDraft, EvidenceItem, Section
   - schemas/admin.py: UserCreate, UserUpdate, UserResponse, AuditLogEntry, SystemConfig
   - schemas/common.py: PaginatedResponse[T], ErrorResponse, SuccessResponse

   All Pydantic v2 models with:
   - Field descriptions (shown in Swagger)
   - Examples (shown in Swagger)
   - Proper JSON Schema types

7. backend/app/api/v1/__init__.py GÇö Router aggregation:
   - Create APIRouter with prefix='' (prefix set at app level)
   - Include all module routers with tags: ['Authentication', 'FIRs', 'Analytics', 'SOP', 'Charge-Sheet', 'Admin']

8. Update backend/app/main.py to include all routers.

9. OpenAPI customisation:
   - Custom description with markdown
   - Server URLs: [{url: '/api/v1', description: 'ATLAS API v1'}]
   - Security scheme: Bearer JWT
   - Tags with descriptions
   - Contact info: ATLAS Team, BITS Pilani

All endpoints return stub/mock data for now (Sprint 1). Real implementation in Sprint 2GÇô5.
Include Pydantic model examples so Swagger 'Try it out' works with realistic data."
```

### VALIDATION COMMAND

```bash
cd backend
# Start server:
uvicorn app.main:app --reload &

# Verify OpenAPI spec:
curl -s http://localhost:8000/openapi.json | python -c "
import json, sys
spec = json.load(sys.stdin)
print(f'Title: {spec[\"info\"][\"title\"]}')
print(f'Version: {spec[\"info\"][\"version\"]}')
print(f'Paths: {len(spec[\"paths\"])}')
for path in sorted(spec['paths'].keys()):
    methods = ', '.join(spec['paths'][path].keys())
    print(f'  {methods.upper()} {path}')
"
# Expected: 20+ paths across 5 modules

# Verify Swagger UI renders:
curl -s http://localhost:8000/docs | grep -i "swagger"  # Should find Swagger HTML

# Run tests:
pytest tests/ -v
```

### DONE WHEN
- [ ] All 4 modules + admin have route stubs returning mock data
- [ ] All Pydantic request/response models defined with examples
- [ ] Swagger UI at /docs renders all endpoints with "Try it out" functional
- [ ] OpenAPI spec (`/openapi.json`) has 20+ paths
- [ ] RBAC permissions enforced on all endpoints (tested)
- [ ] All tests pass
- [ ] PR merged: `feature/T13-openapi-spec` GåÆ `develop`, CI green
- [ ] Jira ATLAS-T13 Done

### STORE AT
Repo: `backend/app/api/v1/`, `backend/app/schemas/` | Jira: ATLAS-T13

### DORA METRIC
**Lead Time (LT)** GÇö API contracts defined early enable parallel frontend/backend development in Sprint 2+.

---
---

# T14-PROMPT GÇö Security Architecture Document

**Assignee:** Both (Aditya drafts, Prishiv reviews infra sections) | **Story Points:** 2 | **Days:** 6GÇô7 | **Jira:** ATLAS-T14

---

### ROLE + EST TIME
Aditya (draft, 3 hours) + Prishiv (review, 1 hour) GÇö Days 6GÇô7

### ENVIRONMENT
Claude.ai for document drafting. Claude Code for technical verification.

### OBJECTIVE
Produce the security architecture document covering encryption (at rest, in transit), audit logging design, data classification scheme, DPDP Act compliance mapping, and vulnerability management process.

### STEPS

```bash
claude "Create the ATLAS Security Architecture Document at docs/security/security-architecture.md.

Structure:

# ATLAS Security Architecture

## 1. Data Classification Scheme
Define 4 levels:
| Level | Label | Description | Examples | Controls |
|-------|-------|-------------|----------|----------|
| L1 | PUBLIC | Publicly available data | NCRB crime codes, BNS section text | No restrictions |
| L2 | INTERNAL | Internal operational data | Aggregated crime statistics, model performance metrics | Authentication required |
| L3 | CONFIDENTIAL | Case-specific data with PII | FIR text, complainant details, accused details | Authentication + RBAC + Audit logging |
| L4 | RESTRICTED | Highly sensitive data | Victim identity in sexual offences, Aadhaar numbers, undercover operations | Authentication + RBAC + PII masking + Enhanced audit + Encryption at rest |

## 2. Encryption Architecture
### 2.1 In Transit
- All client-server communication: TLS 1.3 (HTTPS enforced)
- Internal service-to-database: TLS for PostgreSQL (sslmode=require), MongoDB (tls=true)
- Redis: TLS or encrypted tunnel (stunnel) in production

### 2.2 At Rest
- PostgreSQL: Transparent Data Encryption (TDE) via pgcrypto for L4 fields (victim_name, aadhaar in FIR)
- MongoDB: WiredTiger encryption at rest (Enterprise) or application-level encryption for L4 fields
- File system: EXT4 + LUKS encryption on data volumes
- Backups: AES-256 encrypted before storage

### 2.3 Key Management
- Development: .env file with secrets (never committed to git)
- Staging: HashiCorp Vault (self-hosted)
- Production target: AWS Secrets Manager or Vault (depending on Gujarat State Data Centre capabilities)
- JWT signing key: rotated monthly; old keys retained for validation for 30 days

## 3. Authentication & Authorization
Reference: ADR-D03, T3, T12
- JWT Bearer tokens (HS256 for dev, RS256 for production)
- Token lifecycle: 60-minute access token, 7-day refresh token
- Token blacklisting: Redis-based (on logout, token jti added to blacklist with TTL)
- Brute force protection: Rate limiting on /auth/login (10 attempts per minute per IP)
- Password policy: minimum 8 characters, at least 1 uppercase, 1 digit, 1 special char
- Session management: single active session per user (configurable)

## 4. Audit Logging
### 4.1 What is logged
Every L3/L4 data access is logged:
- User ID, timestamp, IP address, request ID
- Action (read/write/delete)
- Resource type and ID (e.g., FIR GJ/AHD/2024/001)
- Whether PII was accessed (and whether it was masked or unmasked)
- Classification override events (who overrode, old value, new value, reason)
- All admin actions (user creation, config changes)

### 4.2 Storage
- PostgreSQL audit_logs table (structured, queryable)
- ELK stack (searchable, long-term retention)
- Retention: 7 years (per Gujarat Police record retention policy) GÇö production target
- Tamper protection: append-only in production (no UPDATE/DELETE on audit tables)

### 4.3 Monitoring
- Alert on: >10 failed login attempts (potential brute force), L4 data access by unusual role, mass data export, after-hours access patterns

## 5. DPDP Act 2023 Compliance Mapping
| DPDP Provision | Requirement | ATLAS Implementation | Status |
|---------------|------------|---------------------|--------|
| S.4 GÇö Lawful purpose | Process data for lawful purpose | Law enforcement purpose GÇö exempted under S.17(2) | Compliant (documented) |
| S.8(1) GÇö Safeguards | Reasonable security safeguards | Encryption, RBAC, audit logging, PII detection | Implemented (Sprint 1) |
| S.8(7) GÇö Retention | Do not retain beyond purpose | Configurable retention policy; audit log rotation | Planned (Sprint 4) |
| S.9 GÇö Accuracy | Ensure data accuracy | Validation pipeline (T9), quality audit (T7) | Implemented (Sprint 1) |
| S.12 GÇö Breach notification | Notify within 72 hours | Incident response procedure documented | Planned (Sprint 3) |
| S.17(2) GÇö State exemption | Exemption for sovereignty, public order | Applicable GÇö Gujarat Police is a state instrumentality | Documented |

## 6. Vulnerability Management
- Pre-commit: gitleaks for secrets scanning
- CI: pip-audit for Python dependency vulnerabilities
- Weekly: Snyk scan (if license available) or safety check
- Pre-release: OWASP ZAP baseline scan on staging
- Incident response: documented in docs/security/incident-response.md (to be created Sprint 3)

## 7. Network Security (Production Target)
- Application behind reverse proxy (Nginx/Traefik) with rate limiting
- Database ports not exposed externally
- VPN required for administrative access
- IP whitelisting for API access (Gujarat Police network ranges)
- DDoS protection via Gujarat State Data Centre infrastructure

## 8. Compliance Certifications Target
- [ ] STQC (Standardization Testing and Quality Certification) GÇö Indian government IT security standard
- [ ] ISO 27001 GÇö Information security management (stretch goal)
- [ ] DPDP Act compliance self-assessment completed

Include diagrams where helpful. Reference ADR-D01, ADR-D03, T3, T10, T12."
```

### VALIDATION COMMAND

```bash
# Verify document completeness:
cat docs/security/security-architecture.md | grep -c "^## "  # Should be 8 sections
cat docs/security/security-architecture.md | wc -w            # Should be 1500+ words

# Verify technical claims:
# Check HTTPS: (already verified in T6)
# Check gitleaks in pre-commit:
grep "gitleaks" .pre-commit-config.yaml
# Check audit logging:
grep -r "audit" backend/app/core/ | head -5
```

### DONE WHEN
- [ ] Security architecture document has all 8 sections
- [ ] Data classification scheme (4 levels) defined
- [ ] DPDP Act compliance mapping table complete
- [ ] Prishiv has reviewed and approved infra sections
- [ ] Document committed to `docs/security/security-architecture.md`
- [ ] PR merged: `feature/T14-security-doc` GåÆ `develop`
- [ ] Jira ATLAS-T14 Done

### STORE AT
Repo: `docs/security/security-architecture.md` | Jira: ATLAS-T14

### DORA METRIC
**Change Failure Rate (CFR)** GÇö security design documentation prevents security-related change failures.

---
---

# GOV1-PROMPT GÇö Sprint Ceremonies Setup

**Assignee:** Both + Amit | **Day:** 1 | **Jira:** ATLAS-GOV1

---

### ROLE + EST TIME
Amit (lead, 1 hour) + Prishiv + Aditya (30 min each)

### ENVIRONMENT
Jira web UI, Google Calendar, Slack/WhatsApp group

### OBJECTIVE
Establish all Sprint 1 ceremonies, communication channels, and Nodal Officer reporting cadence.

### STEPS

**Step 1: Daily Standup Setup**
```
Create recurring calendar event:
  Title: ATLAS Daily Standup
  Time: 9:30 AM IST, MonGÇôFri (or Mon/Wed/Fri if team prefers)
  Duration: 15 minutes (HARD STOP)
  Location: [Video call link] or [Lab room number]
  Attendees: Amit, Prishiv, Aditya
  
  Format (each person, 2 minutes max):
    1. What I completed since last standup
    2. What I'm working on today (reference Jira ticket)
    3. Any blockers (Amit resolves or escalates)
  
  Amit logs standup notes in: docs/sprints/sprint1-standup-log.md
```

**Step 2: Jira Board Configuration**
```
Columns: Backlog GåÆ To Do GåÆ In Progress GåÆ In Review GåÆ Done
WIP Limits: In Progress = 2 per developer (max 4 total), In Review = 3
Swimlanes: by assignee (Prishiv, Aditya, Both)
Labels: infrastructure, backend, frontend, data, security, documentation, governance
Sprint 1 committed: 37 SP (T1-T14 total)
Quick filters: "My Issues", "Blocked", "Today's Focus"
```

**Step 3: Communication Channels**
```
Create WhatsApp/Slack group: "ATLAS Sprint Chat"
  Members: Amit, Prishiv, Aditya
  Purpose: Quick questions, blocker alerts, daily async updates
  Rule: No architectural decisions in chat GÇö those go through ADR process

Create email thread with Nodal Officer:
  Subject: "ATLAS Project GÇö Sprint 1 Status Updates"
  Cadence: Weekly (every Friday)
  Format: 3 bullets GÇö Done this week, Planned next week, Blockers/Risks
  First email: send today with Sprint 1 kickoff summary
```

**Step 4: Definition of Done (Sprint-level)**
```
A Sprint 1 task is DONE when:
  G£ô Code is in a PR targeting `develop`
  G£ô CI pipeline passes (lint + test + security scan + build)
  G£ô At least 1 team member has reviewed and approved the PR
  G£ô PR is merged to `develop`
  G£ô Documentation is updated (if applicable)
  G£ô Jira ticket is moved to Done with comment summarising what was delivered
  G£ô Any new technical debt is logged as a Jira ticket with label "tech-debt"
```

### DONE WHEN
- [ ] Daily standup calendar invite sent and accepted by all
- [ ] Jira Sprint 1 board configured with correct columns, WIP limits, swimlanes
- [ ] Communication channels created
- [ ] First Nodal Officer status email sent
- [ ] Definition of Done documented in `docs/sprints/definition-of-done.md`
- [ ] Jira ATLAS-GOV1 Done

### STORE AT
Repo: `docs/sprints/sprint1-standup-log.md`, `docs/sprints/definition-of-done.md` | Jira: ATLAS-GOV1

### DORA METRIC
**Deployment Frequency (DF)** GÇö clear ceremonies and cadence enable consistent delivery rhythm.

---
---

# GOV2-PROMPT GÇö Mid-Sprint Review (Day 7 Burndown Check)

**Assignee:** Both + Amit | **Day:** 7 | **Jira:** ATLAS-GOV2

---

### ROLE + EST TIME
Amit (facilitator, 45 min) + Prishiv (15 min prep) + Aditya (15 min prep)

### ENVIRONMENT
Jira burndown chart + in-person/video call

### OBJECTIVE
Assess Sprint 1 progress at the midpoint using burndown chart diagnosis (per Lecture 9, Figure 3 patterns), identify at-risk tasks, and take corrective action.

### STEPS

**Step 1: Burndown Chart Analysis** (Amit, 10 min)

Pull the Jira burndown chart for Sprint 1. Diagnose which pattern it matches:

| Pattern (Lecture 9 Figure 3) | Shape | Diagnosis | Action |
|------------------------------|-------|-----------|--------|
| **Ideal** | Steady downward slope, on or near ideal line | On track | Continue as planned |
| **Late Start** | Flat for first 2GÇô3 days, then dropping | Slow sprint start (setup tasks took longer) | Acceptable if dropping now; watch closely |
| **Scope Creep** | Line goes UP before going down | Work was added mid-sprint | Remove added work or extend sprint |
| **Plateau** | Drops, then goes flat | Team stuck on blocking tasks | Identify and resolve blockers immediately |
| **Cliff** | Mostly flat, then drops sharply near end | Work not tracked in real-time; big batch merge at end | Insist on daily Jira updates; smaller PRs |
| **Never-ending** | Line never reaches zero | Over-committed sprint | Descope: move P2 tasks to Sprint 2 |

```
Amit's checklist:
1. Screenshot current burndown chart
2. Calculate: story points completed (Done) vs. expected (ideal line at Day 7)
   - Expected at Day 7: ~18-19 SP (37 SP ++ 14 days +ù 7 days)
   - If completed < 14 SP: AT RISK GåÆ corrective action needed
   - If completed GëÑ 14 SP: ON TRACK
3. Identify pattern from table above
4. Log analysis in docs/sprints/sprint1-midreview.md
```

**Step 2: Task-Level Status Check** (All, 20 min)

Review each Day 1GÇô7 task:

| Task | Expected Status (Day 7) | Actual Status | On Track? |
|------|:-----------------------:|:-------------:|:---------:|
| T1 (Repo/CI) | Done | ___ | Y/N |
| T2 (Docker) | Done | ___ | Y/N |
| T11 (Architecture ADR) | Done | ___ | Y/N |
| T7 (Data Inventory) | Done | ___ | Y/N |
| T3 (FastAPI Auth) | Done | ___ | Y/N |
| T4 (Next.js) | Done | ___ | Y/N |
| T8 (Schema Design) | Done | ___ | Y/N |
| T5 (Databases) | Done | ___ | Y/N |
| T12 (RBAC) | Done | ___ | Y/N |
| T6 (Monitoring) | Done or In Progress | ___ | Y/N |

**Step 3: Risk Assessment** (All, 10 min)

| Risk | Likelihood | Impact | Mitigation |
|------|:---------:|:------:|-----------|
| [Identify from current state] | H/M/L | H/M/L | [Action + Owner] |

**Step 4: Corrective Action** (Amit decides, 5 min)

If AT RISK:
- Option A: Extend working hours (Days 8GÇô10) to catch up
- Option B: Descope lowest-priority task (T14 Security Doc is most deferrable)
- Option C: Request Amit to take on documentation tasks (T7, T14)
- Option D: Accept slip and plan carryover to Sprint 2

Document decision in mid-review notes.

### DONE WHEN
- [ ] Burndown chart screenshot saved
- [ ] Pattern diagnosed and documented
- [ ] All Day 1GÇô7 tasks status verified
- [ ] Risks identified with mitigations
- [ ] Corrective action decided (if needed)
- [ ] Mid-review notes committed to `docs/sprints/sprint1-midreview.md`
- [ ] Jira ATLAS-GOV2 Done

### STORE AT
Repo: `docs/sprints/sprint1-midreview.md`, `docs/sprints/sprint1-burndown-day7.png` | Jira: ATLAS-GOV2

### DORA METRIC
**Lead Time (LT)** GÇö mid-sprint diagnosis prevents multi-sprint delays.

---
---

# GOV3-PROMPT GÇö Sprint Review Prep (Day 13 GÇö Demo Script)

**Assignee:** Both + Amit | **Day:** 13 | **Jira:** ATLAS-GOV3

---

### ROLE + EST TIME
Amit (demo script author, 1 hour) + Prishiv (tech prep, 30 min) + Aditya (tech prep, 30 min)

### ENVIRONMENT
Staging environment (Docker Compose). Screen recording software (optional).

### OBJECTIVE
Prepare the Sprint Review demo script for the Nodal Officer, verify all demonstration steps work in staging, and prepare the Sprint 1 completion summary.

### STEPS

**Step 1: Demo Script** (Amit, 45 min)

```markdown
## Sprint 1 Demo Script GÇö For Nodal Officer Review

### Duration: 30 minutes
### Presenter: Amit (narrates), Prishiv (operates backend), Aditya (operates frontend)

### Demo Flow:

1. **Project Overview** (3 min) GÇö Amit
   - Show C4 Context diagram (T11)
   - Explain Sprint 1 goal: "All infrastructure operational"
   - Show Jira burndown chart: planned vs. actual

2. **Infrastructure** (5 min) GÇö Prishiv
   - Run `docker compose up -d` GÇö show all services starting
   - Show `docker compose ps` GÇö all services healthy
   - Open Grafana dashboard GÇö show monitoring is active
   - Open Prometheus targets GÇö show metrics being collected

3. **Authentication & RBAC** (7 min) GÇö Aditya
   - Open Swagger UI at /docs GÇö walk through API endpoints
   - Demo login as IO GåÆ show limited permissions
   - Demo login as SHO GåÆ show expanded permissions
   - Demo login as Admin GåÆ show user management access
   - Attempt unauthorized action (IO trying admin endpoint) GåÆ show 403

4. **Frontend Dashboard** (5 min) GÇö Prishiv
   - Open Next.js app at localhost:3000
   - Login flow GåÆ dashboard with role-appropriate sidebar
   - Show responsive design (resize browser)

5. **Data Pipeline** (5 min) GÇö Aditya
   - Show seed data in MongoDB (10 FIRs)
   - Demo CSV upload through ingestion API
   - Show ingestion log with success/failure counts
   - Show IPCGåÆBNS section normalisation in action

6. **Security** (3 min) GÇö Amit
   - Show PII detection on a sample FIR
   - Show victim identity masking for different roles
   - Reference security architecture document
   - Show audit log entries generated during the demo

7. **Questions** (2 min) GÇö All

### Fallback Plan:
If staging is unstable:
- Use pre-recorded video of each demo step
- Have screenshots ready for each key screen
```

**Step 2: Technical Verification** (Prishiv + Aditya, 30 min each)

```bash
# Verify staging environment:
cd infrastructure/docker
docker compose -f docker-compose.staging.yml up -d --build

# Run through every demo step:
# 1. Health check: curl localhost:8000/health
# 2. Login: curl -X POST localhost:8000/api/v1/auth/login ...
# 3. RBAC: test each role
# 4. Frontend: open localhost:3000
# 5. Ingestion: upload test CSV
# 6. PII: test detection endpoint
# 7. Grafana: open localhost:3001

# If any step fails: fix before Day 14, or prepare fallback
```

**Step 3: Sprint Completion Summary** (Amit, 15 min)

```markdown
## Sprint 1 Completion Summary

| Task | Status | SP | Deliverable |
|------|:------:|:--:|------------|
| T1 Repo/CI | G£ô/G£ù | 3 | GitHub repo + CI pipeline |
| T2 Docker | G£ô/G£ù | 2 | Docker Compose dev + staging |
| ... (all 14 tasks) ...
| Total | __/14 complete | __/37 SP delivered | |

### Key Achievements
1. [Highlight 1]
2. [Highlight 2]
3. [Highlight 3]

### Carryover to Sprint 2
- [Any incomplete tasks]

### Risks Identified
- [List]
```

### DONE WHEN
- [ ] Demo script written and distributed to Prishiv + Aditya
- [ ] Every demo step verified in staging environment
- [ ] Fallback materials prepared (screenshots/recording)
- [ ] Sprint completion summary drafted
- [ ] Jira ATLAS-GOV3 Done

### STORE AT
Repo: `docs/sprints/sprint1-demo-script.md`, `docs/sprints/sprint1-completion-summary.md` | Jira: ATLAS-GOV3

---
---

# GOV4-PROMPT GÇö Sprint Review + Retrospective + Sprint 2 Planning Prep

**Assignee:** Both + Amit | **Day:** 14 | **Jira:** ATLAS-GOV4

---

### ROLE + EST TIME
Amit (facilitator, 2.5 hours total) + Prishiv (participant) + Aditya (participant)

### ENVIRONMENT
Meeting room or video call. Jira board visible. Miro/whiteboard for retrospective.

### OBJECTIVE
Conduct Sprint 1 Review (demo to Nodal Officer), Sprint 1 Retrospective (internal team), and prepare Sprint 2 backlog.

### STEPS

**Step 1: Sprint Review** (45 min GÇö Nodal Officer + team)

- Execute demo script from GOV3
- Nodal Officer provides feedback and asks questions
- Record all feedback items as Jira tickets (label: "nodal-feedback")
- Nodal Officer confirms satisfactory progress (or raises concerns)
- Screenshot: Nodal Officer thumbs-up or email confirmation

**Step 2: Sprint 1 Retrospective** (45 min GÇö team only)

Format: **Start / Stop / Continue** (per Lecture 9, Section 3.4)

```
Facilitate using this protocol:

ROUND 1 GÇö Silent Brainstorm (10 min)
  Each person writes sticky notes (physical or digital) for:
  - START: Things we should begin doing in Sprint 2
  - STOP: Things that didn't work and we should stop
  - CONTINUE: Things that worked well and we should keep doing
  Minimum 2 items per category per person.

ROUND 2 GÇö Share and Cluster (15 min)
  Each person presents their items (1 min per item).
  Amit groups similar items into themes.

ROUND 3 GÇö Dot Voting (5 min)
  Each person gets 3 votes. Vote on the themes most important to address.

ROUND 4 GÇö Action Items (15 min)
  Top 3 voted themes become action items.
  Each action item gets:
  - Description: what changes
  - Owner: who is responsible
  - When: Sprint 2 start, mid-sprint, or ongoing
  - Success metric: how we know it worked

  Example action items:
  - "START: pair programming on integration tasks" GåÆ Owner: Both GåÆ When: Sprint 2 Day 1 GåÆ Metric: At least 2 pair sessions per sprint
  - "STOP: working past midnight" GåÆ Owner: Amit (enforces) GåÆ When: Immediate GåÆ Metric: No commits between 12 AM GÇô 6 AM
  - "CONTINUE: daily standups at 9:30 AM" GåÆ Already embedded
```

Document retrospective in: `docs/sprints/sprint1-retrospective.md`

**Step 3: Sprint 2 Planning Prep** (45 min GÇö team only)

```
Sprint 2 Focus Areas (tentative GÇö to be finalised in Sprint 2 planning):
1. NLP pipeline implementation (model loading, inference, classification)
2. FIR API endpoints GÇö real data serving (not stubs)
3. Frontend: FIR list view, search, detail view
4. eGujCop data integration (if API access granted)
5. Annotation pipeline setup (per ADR-D04)

Sprint 2 Planning Steps:
1. Review all carryover from Sprint 1
2. Review Nodal Officer feedback items
3. Pull from product backlog: prioritise by dependency + value
4. Estimate each task (story points GÇö planning poker)
5. Commit to Sprint 2 scope (Gëñ 40 SP)
6. Create Sprint 2 in Jira, add tickets, start sprint
```

### DONE WHEN
- [ ] Sprint Review demo completed for Nodal Officer
- [ ] Nodal Officer feedback recorded in Jira
- [ ] Retrospective completed with 3+ action items documented
- [ ] Sprint 1 velocity calculated: actual SP delivered / committed SP
- [ ] Sprint 2 backlog drafted (ready for Sprint 2 Day 1 planning)
- [ ] All Sprint 1 Jira tickets in final state (Done or moved to Sprint 2 backlog)
- [ ] Burndown chart screenshot saved for Sprint 1 final state
- [ ] Jira ATLAS-GOV4 Done

### STORE AT
Repo: `docs/sprints/sprint1-retrospective.md`, `docs/sprints/sprint1-burndown-final.png` | Jira: ATLAS-GOV4

### DORA METRIC
**Deployment Frequency (DF)** GÇö retrospective improvements increase future sprint velocity. **Lead Time (LT)** GÇö Sprint 2 planning prep reduces Day 1 ramp-up time.

---
---

# DOC1-PROMPT GÇö Monthly Progress Report #1 Draft (MoU Clause 7.1)

**Assignee:** Both (Amit leads, team contributes) | **Day:** 14 | **Jira:** ATLAS-DOC1

---

### ROLE + EST TIME
Amit (lead author, 2 hours) + Prishiv (technical sections, 30 min) + Aditya (NLP/data sections, 30 min)

### ENVIRONMENT
Claude.ai for drafting. Per ADR-D11 Monthly Report Format (from deliberation prompts).

### OBJECTIVE
Produce the first monthly progress report per MoU Clause 7.1, covering Sprint 1 outcomes, metrics, and Sprint 2 plan.

### STEPS

```bash
claude "Draft Monthly Progress Report #1 for Project ATLAS at docs/reports/monthly-report-001.md.

Use this template (per ADR-D11):

# ATLAS Monthly Progress Report #1
**Project:** ATLAS GÇö Gujarat Police +ù BITS Pilani
**Period:** [Sprint 1 dates]
**Submitted by:** Amit (Project Lead)
**Submitted to:** [Nodal Officer name], Gujarat Police

## Executive Summary
[3GÇô5 sentences: Sprint 1 completed. Infrastructure operational. Architecture decided. X of 14 tasks completed. Ready for Sprint 2 NLP development.]

## Progress Metrics

| Metric | Target | Actual | Status |
|--------|:------:|:------:|:------:|
| Sprint velocity (SP delivered / committed) | GëÑ 0.80 | __/37 = __ | =ƒƒó/=ƒƒí/=ƒö¦ |
| P1 feature completion | All Sprint 1 tasks | __/14 | =ƒƒó/=ƒƒí/=ƒö¦ |
| CI/CD pipeline operational | Yes | Yes/No | =ƒƒó/=ƒö¦ |
| Test coverage (backend) | GëÑ 70% | __% | =ƒƒó/=ƒƒí/=ƒö¦ |
| ADR decisions made | 1 (Architecture) | __ | =ƒƒó/=ƒƒí/=ƒö¦ |
| Security scan clean | Yes | Yes/No | =ƒƒó/=ƒö¦ |

## Technical Progress
### Infrastructure (Prishiv)
- GitHub repository with CI/CD pipeline: [status]
- Docker Compose development environment: [status]
- Monitoring stack (Prometheus + Grafana + ELK): [status]
- Database setup (PostgreSQL + MongoDB): [status]

### Application (Aditya)
- FastAPI backend with JWT authentication: [status]
- RBAC middleware for 6 police roles: [status]
- OpenAPI specification (20+ endpoints defined): [status]
- Data ingestion pipeline (CSV/JSON/PDF): [status]

### Security (Both)
- PII detection pipeline: [status]
- Security architecture document: [status]
- Pre-commit secrets scanning: [status]

### Data & Research (Both)
- FIR data inventory and quality audit: [status]
- Database schema design (ERD + JSON schemas): [status]
- Architecture ADR (modular monolith decision): [status]

## Sprint 2 Plan
| Focus Area | Key Deliverables | Assigned To |
|-----------|-----------------|-------------|
| NLP Pipeline | Model loading, inference service, classification endpoint | Prishiv |
| FIR API | Real data serving, search, filtering | Aditya |
| Frontend Views | FIR list, detail, search UI | Prishiv |
| Annotation Setup | Label Studio deployment, guideline creation | Aditya |
| eGujCop Integration | API access request, data mapping | Both |

## Risk Register
| Risk | Likelihood | Impact | Mitigation | Owner |
|------|:---------:|:------:|-----------|:-----:|
| eGujCop API access delayed | Medium | High | Fallback to CSV upload; escalate through Nodal Officer | Amit |
| Gujarati NLP model accuracy insufficient | Medium | High | Benchmark multiple models in Sprint 2; fallback to rule-based | Aditya |
| GPU unavailable for model inference | Low | Medium | Use CPU inference with smaller model; request BITS lab GPU | Prishiv |

## Blockers Requiring Stakeholder Action
1. [If any GÇö e.g., 'Awaiting eGujCop API documentation from IT Cell']
2. [If any]

## Budget Status
[If applicable GÇö hours spent, resources consumed]

## Next Report Due
[Date GÇö end of Sprint 2]

---
*Prepared by ATLAS Team, BITS Pilani. For questions, contact: [Amit's email]*"
```

### VALIDATION COMMAND

```bash
# Verify report exists and has content:
wc -w docs/reports/monthly-report-001.md  # Should be 800+ words

# Verify all sections present:
grep -c "^## " docs/reports/monthly-report-001.md  # Should be 7+ sections
```

### DONE WHEN
- [ ] Monthly report drafted with all sections filled in (actual data from Sprint 1)
- [ ] Prishiv and Aditya have reviewed and contributed their sections
- [ ] Amit has reviewed the final version
- [ ] Report committed to `docs/reports/monthly-report-001.md`
- [ ] Report sent to Nodal Officer via email
- [ ] Jira ATLAS-DOC1 Done

### STORE AT
Repo: `docs/reports/monthly-report-001.md` | Jira: ATLAS-DOC1

### DORA METRIC
**Lead Time (LT)** GÇö monthly reporting cadence maintains stakeholder confidence, preventing scope change delays.

---
---

# SPRINT 1 DAILY EXECUTION GUIDE

For quick reference GÇö which prompts to execute each day:

| Day | Prishiv | Aditya | Both/Amit |
|:---:|---------|--------|-----------|
| **1** | T2 (Docker) start | T1 (Repo/CI) start | GOV1 (ceremonies), T11 (ADR session), T7 (data audit) start |
| **2** | T2 finish, T4 (Next.js) start | T1 finish, T3 (FastAPI) start | T11 (C4 diagrams), T7 continue |
| **3** | T4 continue | T3 continue | T7 finish, T8 (schema design) start |
| **4** | T4 finish, T12 (RBAC) start, T6 (monitoring) start | T3 finish, T5 (databases) start | T8 continue |
| **5** | T12 finish, T6 finish, T10 (PII) start | T5 finish, T13 (OpenAPI) start, T9 (ingestion) start | T8 finish |
| **6** | T10 continue | T13 continue, T9 continue | T14 (security doc) start |
| **7** | T10 finish | T13 finish, T9 finish | T14 finish, **GOV2 (mid-sprint review)** |
| **8GÇô12** | Buffer / bug fixes / carryover | Buffer / bug fixes / carryover | Resolve blockers |
| **13** | Demo prep (GOV3) | Demo prep (GOV3) | **GOV3 (demo script)** |
| **14** | Sprint Review + Retro | Sprint Review + Retro | **GOV4 + DOC1** |

**Total Sprint 1 committed:** 37 SP + governance + documentation  
**Buffer days (8GÇô12):** 5 days for overruns, bug fixes, and unexpected blockers  
**This buffer is intentional** GÇö Sprint 1 has the highest uncertainty; better to under-commit and over-deliver.
