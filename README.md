---
title: ATLAS Legal AI Platform
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# ATLAS Legal AI Platform - Demo

**Full-stack deployment of ATLAS on Hugging Face Spaces with PostgreSQL, FastAPI, and Next.js**

An advanced legal case analysis system powered by AI. This Space runs the frontend UI, backend API, and a local PostgreSQL demo database inside the same container.

## Features

- **FIR Browser**: Browse seeded FIR records and open detailed case views
- **Charge-sheet Workflow**: View seeded charge-sheets and review evidence/validation tabs
- **Dashboards**: Live KPI cards driven by PostgreSQL-backed data
- **REST API**: OpenAPI documentation at `/docs`
- **Demo Login**: Seeded authentication users for the Space

## What's Included

✅ **FastAPI Backend** - Production API for FIRs, chargesheets, validation, and dashboard stats  
✅ **Next.js Frontend** - Full UI for browsing and reviewing cases  
✅ **PostgreSQL Demo DB** - Seeded at container startup with real demo records  
✅ **Docker Container** - Single-image deployment for Hugging Face Spaces  

## Quick Start

Once deployed, open the Space at: `https://huggingface.co/spaces/Prishiv/atlas_demo`

### Demo Login

Use one of the seeded accounts:

- `admin` / `atlas2025`
- `io_sanand` / `atlas2025`
- `sho_sanand` / `atlas2025`

### API Examples

**Health Check**
---
title: ATLAS Legal AI Platform
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# ATLAS Legal AI Platform - Demo

**Full-stack deployment of ATLAS on Hugging Face Spaces with PostgreSQL, FastAPI, and Next.js**

An advanced legal case analysis system powered by AI. This Space runs the frontend UI, backend API, and a local PostgreSQL demo database inside the same container.

## Features

- **FIR Browser**: Browse seeded FIR records and open detailed case views
- **Charge-sheet Workflow**: View seeded charge-sheets and review evidence / validation tabs
- **Dashboards**: Live KPI cards driven by PostgreSQL-backed data
- **REST API**: OpenAPI documentation at `/docs`
- **Demo Login**: Seeded authentication users for the Space

## What's Included

✅ **FastAPI Backend** - Production API for FIRs, chargesheets, validation, and dashboard stats  
✅ **Next.js Frontend** - Full UI for browsing and reviewing cases  
✅ **PostgreSQL Demo DB** - Seeded at container startup with real demo records  
✅ **Docker Container** - Single-image deployment for Hugging Face Spaces  

## Quick Start

Once deployed, open the Space at: `https://huggingface.co/spaces/Prishiv/atlas_demo`

### Demo Login

Use one of the seeded accounts:

- `admin` / `atlas2025`
- `io_sanand` / `atlas2025`
- `sho_sanand` / `atlas2025`

### API Examples

**Health Check**
```bash
curl https://[space-url]/api/v1/health
```

**List FIRs**
```bash
curl https://[space-url]/api/v1/firs
```

**List Chargesheets**
```bash
curl https://[space-url]/api/v1/chargesheet/
```

### Interactive API Documentation
- **Swagger UI**: `https://[space-url]/docs`
- **ReDoc**: `https://[space-url]/redoc`

## Tech Stack

- **Framework**: FastAPI (Python 3.11)
- **Frontend**: Next.js 14
- **Database**: PostgreSQL running inside the Space container
- **Document Processing**: PDFPlumber, PyMuPDF, PDF-to-image OCR
- **OCR**: Tesseract
- **Deployment**: Docker on Hugging Face Spaces

## Local Full Stack

To run the complete system locally with database, UI, and all services:

```bash
cd infrastructure/docker
docker compose up --build
```

Access at:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

The Hugging Face Space uses the same backend and frontend code, but starts a local PostgreSQL server and seeds demo records at container boot.

## Performance

- **Build Time**: several minutes on HF because the frontend and database stack are built together
- **Container Size**: large, because it includes the app, Node.js, and PostgreSQL
- **Cold Start**: depends on PostgreSQL init and demo seeding
- **API Response Time**: <1 second for normal DB-backed reads

## Limitations

This is a **demo deployment**:
- PostgreSQL runs inside the container, so data resets if the Space is rebuilt
- Some optional external services such as Redis and MongoDB are not deployed in the Space image
- Heavy ML fallbacks still degrade gracefully when large model caches are unavailable

## Production Deployment

For production, deploy the full stack with:
- Kubernetes/Docker Swarm orchestration
- Separate PostgreSQL, Redis, and MongoDB services
- Reverse proxy / ingress
- Full authentication/RBAC
- See local `docker-compose.yml` for reference

## License

Proprietary - ATLAS Platform

## Support

For issues or feature requests, refer to project documentation or contact the development team.

---

**Deployment**: Hugging Face Spaces (Full Stack Demo)  
**Backend**: FastAPI  
**Frontend**: Next.js  
**Last Updated**: April 11, 2026
