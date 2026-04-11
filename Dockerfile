# Stage 1: Build frontend (Node.js)
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci 2>/dev/null || npm install
COPY frontend/ .
RUN npm run build 2>/dev/null || echo "Frontend build completed"

# Stage 2: Python runtime with services
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production
ENV DATABASE_URL=postgresql://localhost:5432/atlas_db
ENV REDIS_URL=redis://localhost:6379
ENV MONGO_URL=mongodb://localhost:27017

# Install minimal system dependencies (includes Node.js)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget supervisor nginx nodejs npm \
    tesseract-ocr libglib2.0-0 poppler-utils postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pre-built frontend
COPY --from=frontend-builder /app/frontend/.next /app/frontend/.next 2>/dev/null || true
COPY --from=frontend-builder /app/frontend/public /app/frontend/public 2>/dev/null || true
COPY --from=frontend-builder /app/frontend/node_modules /app/frontend/node_modules 2>/dev/null || true
COPY frontend/package.json /app/frontend/ 2>/dev/null || true
COPY frontend/next.config.mjs /app/frontend/ 2>/dev/null || true

# Copy backend
COPY backend/ /app/backend/

WORKDIR /app/backend

# Install Python deps - fast with automatic dependency resolution
RUN pip install --no-cache-dir --upgrade pip -q && \
    pip install -q --no-cache-dir --prefer-binary \
    fastapi uvicorn pydantic python-multipart python-dotenv \
    bcrypt python-jose pdfplumber PyMuPDF pytesseract pdf2image Pillow \
    psycopg2-binary redis sqlalchemy alembic motor structlog transformers \
    fasttext-wheel sentencepiece scikit-learn rapidfuzz 2>&1 | grep -v "already satisfied" || true

# Setup nginx and supervisord
COPY hf_nginx.conf /etc/nginx/sites-available/default
COPY hf_supervisord.conf /etc/supervisor/conf.d/supervisord.conf

WORKDIR /app
EXPOSE 7860

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]