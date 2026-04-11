FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

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
    motor>=3.3

EXPOSE 7860

# Run FastAPI directly
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]