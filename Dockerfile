FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=postgresql://localhost:5432/atlas_db
ENV REDIS_URL=redis://localhost:6379
ENV MONGO_URL=mongodb://localhost:27017

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget \
    tesseract-ocr tesseract-ocr-eng \
    libglib2.0-0 poppler-utils \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend code
COPY backend/ /app/backend/

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
    rapidfuzz>=3.6.0

EXPOSE 7860

# Create startup wrapper to handle missing services gracefully
RUN echo '#!/bin/bash\necho "Starting ATLAS API on HF Spaces..."\necho "Note: Database connections may fail - this is expected without active services"\necho "Health check at: http://localhost:7860/api/v1/health"\nexec uvicorn app.main:app --host 0.0.0.0 --port 7860 --log-level info' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]