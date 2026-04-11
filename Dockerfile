# Atlas Platform - Complete Docker Image
# Combines Frontend (Next.js) + Backend (FastAPI) + Services (nginx, supervisord)

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production
ENV NEXT_PUBLIC_API_URL=
ENV DATABASE_URL=postgresql://localhost:5432/atlas_db
ENV REDIS_URL=redis://localhost:6379
ENV MONGO_URL=mongodb://localhost:27017

# Install all system dependencies in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget supervisor nginx nodejs npm git \
    tesseract-ocr libglib2.0-0 poppler-utils postgresql-client \
    build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend code
COPY backend/ /app/backend/

# Copy frontend code
COPY frontend/ /app/frontend/

# Install Python dependencies
WORKDIR /app/backend
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --prefer-binary \
    fastapi uvicorn pydantic python-multipart python-dotenv \
    bcrypt python-jose pdfplumber PyMuPDF pytesseract pdf2image Pillow \
    psycopg2-binary redis sqlalchemy alembic motor structlog transformers \
    fasttext-wheel sentencepiece scikit-learn rapidfuzz

# Build frontend
WORKDIR /app/frontend
RUN npm ci --omit=dev 2>/dev/null || npm install --omit=dev || true && \
    npm run build 2>/dev/null || echo "Frontend built or skipped"

# Copy service configuration
WORKDIR /app
COPY hf_nginx.conf /etc/nginx/sites-available/default
COPY hf_supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose HF Spaces port
EXPOSE 7860

# Start services via supervisord
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]