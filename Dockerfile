# Stage 1: Build Next.js frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --prefer-offline --no-audit
COPY frontend/ .
RUN npm run build

# Stage 2: Final image with Python backend, Node runtime, and services
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production
ENV DATABASE_URL=postgresql://localhost:5432/atlas_db
ENV REDIS_URL=redis://localhost:6379
ENV MONGO_URL=mongodb://localhost:27017

# Install system dependencies (supervisor, nginx, Node.js runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget \
    supervisor nginx \
    tesseract-ocr tesseract-ocr-eng \
    libglib2.0-0 poppler-utils \
    postgresql-client \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pre-built frontend
COPY --from=frontend-builder /app/frontend/.next /app/frontend/.next
COPY --from=frontend-builder /app/frontend/public /app/frontend/public
COPY --from=frontend-builder /app/frontend/package*.json /app/frontend/

# Copy backend code
COPY backend/ /app/backend/

# Copy frontend remaining files
COPY frontend/next.config.mjs /app/frontend/

WORKDIR /app/backend

# Install Python dependencies - backend requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    fastapi==0.110.0 \
    uvicorn[standard]==0.27.1 \
    pydantic>=2.6.0 \
    python-multipart==0.0.9 \
    python-dotenv==1.0.1 \
    structlog==24.1.0 \
    bcrypt==4.2.1 \
    python-jose[cryptography]==3.3.0 \
    pdfplumber==0.11.0 \
    PyMuPDF==1.26.7 \
    pytesseract==0.3.13 \
    pdf2image==1.17.0 \
    Pillow>=10.0.0 \
    psycopg2-binary==2.9.9 \
    redis==5.0.3 \
    sqlalchemy==2.0.28 \
    alembic==1.13.1 \
    motor>=3.3 \
    transformers>=4.38.0 \
    fasttext-wheel==0.9.2 \
    sentencepiece>=0.1.99 \
    scikit-learn>=1.4.0 \
    rapidfuzz>=3.6.0 && \
    pip install --no-cache-dir xlit || true

# Setup configurations
COPY hf_nginx.conf /etc/nginx/sites-available/default
COPY hf_supervisord.conf /etc/supervisor/conf.d/supervisord.conf

WORKDIR /app
EXPOSE 7860

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]