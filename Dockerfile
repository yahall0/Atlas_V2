# Build stage for frontend
FROM node:20-alpine as frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --prefer-offline --no-audit
COPY frontend/ .
RUN npm run build

# Final stage - optimized for HF Spaces
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production
ENV NEXT_PUBLIC_API_URL=""
ENV DATABASE_URL="postgresql://atlas:atlaspass@127.0.0.1:5432/atlas_db"
ENV REDIS_URL="redis://127.0.0.1:6379"
ENV MONGO_URL="mongodb://127.0.0.1:27017"

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget gnupg \
    supervisor nginx \
    tesseract-ocr tesseract-ocr-eng \
    libglib2.0-0 poppler-utils \
    postgresql postgresql-contrib redis-server \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Initialize PostgreSQL database
RUN /etc/init.d/postgresql start && \
    su - postgres -c "psql -c \"CREATE USER atlas WITH SUPERUSER PASSWORD 'atlaspass';\"" && \
    su - postgres -c "createdb -O atlas atlas_db" && \
    /etc/init.d/postgresql stop || true

# Install MongoDB (lightweight approach)
RUN curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | apt-key add - && \
    echo "deb [ arch=amd64 ] https://repo.mongodb.org/apt/debian bullseye/mongodb-org/7.0 main" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list && \
    apt-get update && apt-get install -y --no-install-recommends mongodb-org-server && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pre-built frontend
COPY --from=frontend-builder /app/frontend/.next /app/frontend/.next
COPY frontend/public /app/frontend/public
COPY frontend/package.json /app/frontend/
COPY frontend/next.config.mjs /app/frontend/

# Setup Python backend
COPY backend/ /app/backend/

# Install Python dependencies (skip torch for now - add only if needed)
WORKDIR /app/backend
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    fastapi==0.110.0 \
    uvicorn[standard]==0.27.1 \
    psycopg2-binary==2.9.9 \
    python-dotenv==1.0.1 \
    redis==5.0.3 \
    pydantic>=2.6.0 \
    python-jose[cryptography]==3.3.0 \
    bcrypt==4.2.1 \
    structlog==24.1.0 \
    prometheus-fastapi-instrumentator==6.1.0 \
    pdfplumber==0.11.0 \
    PyMuPDF==1.26.7 \
    pytesseract==0.3.13 \
    pdf2image==1.17.0 \
    Pillow>=10.0.0 \
    python-multipart==0.0.9 \
    alembic==1.13.1 \
    sqlalchemy==2.0.28 \
    motor>=3.3 \
    fasttext-wheel==0.9.2 \
    sentencepiece>=0.1.99 \
    mlflow>=2.10.2 \
    label-studio-sdk>=0.8.0 \
    scikit-learn>=1.4.0 \
    rapidfuzz>=3.6.0

# Optional: Install transformers separately with minimal deps
RUN pip install --no-cache-dir --no-deps transformers>=4.38.0 && \
    pip install --no-cache-dir huggingface_hub

# Setup configurations
COPY hf_nginx.conf /etc/nginx/sites-available/default
COPY hf_supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY hf_start.sh /app/hf_start.sh
RUN chmod +x /app/hf_start.sh

WORKDIR /app
EXPOSE 7860

CMD ["/app/hf_start.sh"]