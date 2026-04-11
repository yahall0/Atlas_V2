---
title: ATLAS Legal AI Platform
emoji: ⚖️
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# ATLAS Legal AI Platform

An advanced legal case analysis system powered by AI. Automatically extract, classify, and analyze legal documents including FIRs (First Information Reports), chargesheets, and evidence.

## Features

- **Legal Document Ingestion**: Upload and process FIRs, chargesheets, and other legal documents
- **Multi-Language Support**: Handles English, Hindi, Gujarati, Marathi, Tamil, Telugu, etc.
- **AI Classification**: Automatic categorization and prediction using state-of-the-art transformers
- **Evidence Gap Detection**: Identifies missing evidence and logical inconsistencies
- **PII Detection**: Detects and handles personally identifiable information
- **Legal Validation**: Validates documents against legal standards
- **Interactive Dashboard**: View analytics, timelines, and document reviews

## Tech Stack

- **Backend**: FastAPI (Python 3.11)
- **Frontend**: Next.js with TypeScript
- **Databases**: PostgreSQL, MongoDB, Redis
- **ML Models**: Transformers (BERT, mDeBERTa, FastText)
- **Orchestration**: Nginx, Supervisord
- **Infrastructure**: Docker

## Architecture

The platform consists of:

1. **Backend API** (`/api/v1/*`): FastAPI microservices for document processing and ML inference
2. **Frontend UI** (`/`): Next.js dashboard for user interactions
3. **Data Layer**: PostgreSQL for structured data, MongoDB for document storage
4. **Cache Layer**: Redis for session management and caching
5. **Reverse Proxy**: Nginx for routing and load balancing

## Getting Started

The application will automatically:

1. Initialize PostgreSQL database with schema migrations
2. Start Redis cache service
3. Start MongoDB document database
4. Build and deploy the FastAPI backend
5. Build and deploy the Next.js frontend
6. Configure reverse proxy on port 7860

Once deployed, access the application at the space URL.

## API Endpoints

### Health Check
- `GET /api/v1/health` - Service health status

### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/logout` - User logout

### Documents
- `GET /api/v1/firs` - List FIR documents
- `POST /api/v1/firs/ingest` - Upload new FIR
- `GET /api/v1/chargesheet` - List chargesheets

### Analysis
- `POST /api/v1/predict` - Run ML classification
- `POST /api/v1/validate` - Legal validation
- `GET /api/v1/evidence` - Evidence gap analysis

### Dashboard
- `GET /api/v1/dashboard` - Analytics and statistics

## Configuration

Environment variables (pre-configured):
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection URL
- `MONGO_URL`: MongoDB connection URL
- `TRANSFORMERS_CACHE`: Model cache directory
- `INDIC_BERT_MODEL`: Hindi/regional language model
- `ZERO_SHOT_MODEL`: Multi-language classification model

## Development

### Local Deployment
```bash
cd infrastructure/docker
docker compose up --build
```

Access at:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

## Model Information

- **Language Identification**: FastText (176 language support)
- **Regional NLP**: Google mBERT + Indic-BERT
- **Multi-label Classification**: mDeBERTa-v3 with multilingual XNLI
- **Zero-shot Threshold**: 0.20 (configurable)

## Performance

- Concurrent document processing: ~100+ documents
- Average classification latency: <2 seconds per document
- Memory usage: ~4GB (optimized for HF Spaces)

## License

Proprietary - ATLAS Platform

## Support

For issues, feature requests, or questions, please refer to project documentation or contact the development team.

---

**Current Deployment**: Hugging Face Spaces  
**Backend Branch**: demo  
**Last Updated**: April 11, 2026
