# ATLAS Platform — Progress Log

**Date:** 2026-04-07
**Branch:** main

---

## T1: CI/CD Pipeline
- Added `lint` job (flake8, max-line-length=120) and `secrets-scan` job (gitleaks) to GitHub Actions
- Created `.pre-commit-config.yaml` with gitleaks, flake8, trailing-whitespace, end-of-file-fixer, check-yaml
- Scaffolded folder structure: `src/ml/`, `src/integrations/`, `docs/decisions/`, `docs/architecture/`, `docs/security/`, `docs/research/phase1/`, `docs/training/`

## T2: Docker Compose Hardening
- Added health checks to backend (HTTP), db (pg_isready), redis (redis-cli ping)
- Added `restart: unless-stopped` to all services
- Backend `depends_on` now uses `condition: service_healthy`
- Created `.env.example` with all required env vars

## T3: JWT Auth + RBAC
- `backend/app/core/security.py` — JWT create/verify (HS256, python-jose), bcrypt password hashing
- `backend/app/core/rbac.py` — Role enum (IO, SHO, DYSP, SP, ADMIN, READONLY), permission map, `get_current_user` and `require_role` dependencies
- `backend/app/api/v1/auth.py` — `/login`, `/refresh`, `/me` endpoints; 3 hardcoded pilot users
- Stub routers: `/chargesheet/health`, `/sop/health`, `/dashboard/health`, `/dashboard/stats`
- CORS middleware (localhost:3000, 3001)
- Prometheus metrics via `prometheus-fastapi-instrumentator`
- 10 passing tests in `test_auth.py`

## T4: Next.js 14 Frontend
- Bootstrapped with `create-next-app@14` (TypeScript, Tailwind, App Router)
- shadcn/ui components: Button, Card, Input, Label, Badge, Separator (v1-compatible with Tailwind v3)
- Pages: `/login` (auth form), `/dashboard` (stats cards), `/dashboard/fir` (PDF drag-drop upload), `/dashboard/chargesheet` (placeholder), `/dashboard/sop` (placeholder)
- Dashboard layout: sidebar nav + header with user info/role badge + logout
- `src/lib/api.ts` — fetch wrapper with Bearer token injection and 401 redirect
- `frontend/Dockerfile` (multi-stage node:20-alpine) + added to `docker-compose.yml`

## T5: Database Schema Expansion
- Appended to both `infrastructure/docker/init/init_schema.sql` and `backend/app/db/init_schema.sql`:
  - `users` table (UUID PK, username, password_hash, role, district, police_station)
  - `audit_log` table (BIGSERIAL PK, append-only, JSONB details, ip_address)
  - `ocr_jobs` table (UUID PK, status, filename, FK to firs, result_summary JSONB)

## T11/T14: Architecture & Security Docs
- `docs/decisions/ADR-D01-architecture.md` — modular monolith decision, 3 AI model tiers, on-premise deployment
- `docs/security/security-architecture.md` — JWT, AES-256, RBAC, PII detection, audit log, DPDP Act compliance

## T9: OCR Test Harness
- `backend/tests/conftest.py` — shared fixtures: `sample_ocr_text` (Gujarati FIR excerpt), `mock_db_connection`
- `backend/tests/test_ingest.py` — 9 tests total:
  - 2 endpoint tests (upload PDF, reject non-PDF) — auto-skip until `/ingest` route exists
  - 5 parser tests (district, FIR number, sections, complainant, stolen property) — auto-skip until `fir_parser.py` exists
  - 2 Gujarati numeral conversion tests — pass now

---

**Test results:** 25 passed, 7 skipped | **Frontend build:** clean
