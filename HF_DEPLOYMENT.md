# HF Spaces Deployment Guide - Full Stack

## Architecture

**Port 7860** (Nginx reverse proxy)
- Routes `/api/*` → Backend (FastAPI on port 8000)
- Routes `/*` → Frontend (Next.js on port 3000)

## Services Running

1. **Nginx** (port 7860) - Reverse proxy router
2. **FastAPI Backend** (port 8000) - Handles all API requests
3. **Next.js Frontend** (port 3000) - Interactive UI

All managed by **supervisord** in one container.

## Access

- **Main URL**: https://huggingface.co/spaces/Prishiv/atlas_demo
- **Frontend**: Automatically served at `/`
- **API Docs**: Available at `/docs` (Swagger UI)
- **API Endpoints**: `/api/v1/*`

## Features Now Available

✅ **Full Stack Deployment**
- Interactive web UI (Next.js)
- REST API backend (FastAPI)
- Shared port 7860 via nginx routing
- All services auto-managed by supervisord

## Build Notes

- **Frontend**: Pre-built in Stage 1 using Node.js Alpine
- **Backend**: Python 3.11 slim with all dependencies
- **Build Time**: ~8-12 minutes (includes npm build)
- **Size**: ~1GB (frontend artifacts + Python packages)

## Testing

Once deployed:

```bash
# Check health
curl https://[space-url]/api/v1/health

# Access UI
Open https://[space-url] in browser

# API Documentation
Visit https://[space-url]/docs
```

## Notes

- Database connections will fail (no services running) - this is expected
- Frontend loads from `/` and works as SPA
- API calls are proxied through nginx to backend
- All processes managed by supervisord, auto-restart on failure
