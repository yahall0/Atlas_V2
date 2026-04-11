---
title: ATLAS Legal AI Platform
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# ATLAS Legal AI Platform - Demo API

**Lightweight API-only deployment of ATLAS on Hugging Face Spaces**

An advanced legal case analysis system powered by AI. This deployment showcases the core FastAPI backend for document analysis and extraction.

## Features

- **PDF Document Analysis**: Extract text, metadata, and structured information from legal PDFs
- **Document Classification**: Categorize documents (FIRs, chargesheets, etc.)
- **Text Extraction**: Advanced PDF text extraction with table detection
- **PII Detection**: Identifies personally identifiable information
- **RESTful API**: Full OpenAPI documentation at `/docs`

## What's Included

✅ **FastAPI Backend** - Lightweight, production-ready REST API  
✅ **PDF Processing** - Document extraction and analysis  
✅ **OpenAPI Docs** - Interactive API documentation  
✅ **Docker Container** - Deploy anywhere with consistent environment  

❌ **Full Stack** - This is API-only. For full stack with UI, run locally with `docker-compose`  
❌ **Databases** - Stripped for lightweight deployment (can be added)  
❌ **ML Models** - Optional. Basic features work without large models  

## Quick Start

Once deployed, access the API at: `https://huggingface.co/spaces/Prishiv/atlas_demo`

### API Examples

**Health Check**
```bash
curl https://[space-url]/api/v1/health
```

**Upload and Analyze Document**
```bash
curl -X POST https://[space-url]/api/v1/firs/ingest \
  -F "file=@document.pdf"
```

**Predict/Classify**
```bash
curl -X POST https://[space-url]/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "Your legal text here"}'
```

**Validate Legal Document**
```bash
curl -X POST https://[space-url]/api/v1/validate \
  -H "Content-Type: application/json" \
  -d '{"content": "FIR content", "type": "FIR"}'
```

### Interactive API Documentation
- **Swagger UI**: `https://[space-url]/docs`
- **ReDoc**: `https://[space-url]/redoc`

## API Endpoints

### Core Endpoints
- `GET /api/v1/health` - Service health
- `POST /api/v1/firs/ingest` - Upload and ingest FIR
- `GET /api/v1/firs` - List ingested FIRs
- `POST /api/v1/chargesheet/ingest` - Upload chargesheet
- `POST /api/v1/predict` - Run ML prediction
- `POST /api/v1/validate` - Validate legal document
- `POST /api/v1/evidence` - Evidence gap analysis

## Tech Stack

- **Framework**: FastAPI (Python 3.11)
- **Server**: Uvicorn
- **Document Processing**: PDFPlumber, PyMuPDF, python-pdf2image
- **OCR**: Tesseract
- **Serialization**: Pydantic
- **Deployment**: Docker on Hugging Face Spaces

## For Full Stack Deployment

To run the complete system locally with database, UI, and all services:

```bash
cd infrastructure/docker
docker compose up --build
```

Access at:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

## Performance

- **Build Time**: ~3-5 minutes on HF
- **Container Size**: ~450MB (lightweight)
- **Cold Start**: ~10-15 seconds
- **API Response Time**: <1 second per request

## Limitations

This is a **minimal demo deployment**:
- No database persistence (stateless API)
- No frontend UI
- Basic ML features only (heavy models optional)
- No authentication/authorization
- Limited to HF Spaces resource constraints

## Adding Features

To extend this deployment:

1. **Add Database**: Uncomment PostgreSQL in docker-compose.yml
2. **Add ML Models**: Uncomment dependencies in requirements.txt
3. **Add Frontend**: Deploy Next.js separately or use HF Spaces interface builder
4. **Add Authentication**: See backend/app/api/v1/auth

## Production Deployment

For production, deploy the full stack with:
- Kubernetes/Docker Swarm orchestration
- PostgreSQL + Redis + MongoDB
- Nginx reverse proxy
- Full authentication/RBAC
- See local `docker-compose.yml` for reference

## License

Proprietary - ATLAS Platform

## Support

For issues or feature requests, refer to project documentation or contact the development team.

---

**Deployment**: Hugging Face Spaces (Lightweight API)  
**Backend**: FastAPI  
**Full Stack Branch**: `demo`  
**Last Updated**: April 11, 2026
