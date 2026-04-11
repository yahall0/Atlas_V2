# Atlas Platform - Complete Docker Image
# Combines Frontend (Next.js) + Backend (FastAPI) + Services (nginx, supervisord)

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production
ENV NEXT_PUBLIC_API_URL=
ENV DATABASE_URL=postgresql://user@127.0.0.1:5432/atlas_db
ENV REDIS_URL=redis://127.0.0.1:6379
ENV MONGO_URL=mongodb://127.0.0.1:27017
ENV HOME=/home/user
ENV PATH=/home/user/.local/bin:$PATH

# Install system dependencies, including a local PostgreSQL server.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget supervisor nodejs npm git \
    postgresql postgresql-contrib postgresql-client \
    tesseract-ocr libglib2.0-0 poppler-utils \
    build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies before dropping privileges.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --prefer-binary \
    fastapi uvicorn pydantic python-multipart python-dotenv \
    bcrypt python-jose pdfplumber PyMuPDF pytesseract pdf2image Pillow \
    psycopg2-binary redis sqlalchemy alembic motor structlog transformers \
    fasttext-wheel sentencepiece scikit-learn rapidfuzz

RUN useradd -m -u 1000 user && \
    mkdir -p /home/user/app /home/user/postgres /home/user/logs && \
    chown -R user:user /home/user

WORKDIR /home/user/app

# Copy application code owned by the runtime user.
COPY --chown=user:user backend/ /home/user/app/backend/
COPY --chown=user:user frontend/ /home/user/app/frontend/
COPY --chown=user:user scripts/ /home/user/app/scripts/
COPY --chown=user:user infrastructure/docker/init/ /home/user/app/infrastructure/docker/init/
COPY --chown=user:user hf_start.sh /home/user/app/hf_start.sh
COPY --chown=user:user hf_supervisord.conf /home/user/app/hf_supervisord.conf
COPY --chown=user:user result.json /home/user/app/result.json
RUN chmod +x /home/user/app/hf_start.sh

# Build frontend as the non-root runtime user.
USER user
WORKDIR /home/user/app/frontend
RUN npm ci --include=dev && \
    npm run build && \
    npm prune --omit=dev

# Expose the frontend entry point used by Spaces.
EXPOSE 7860 8000

CMD ["/home/user/app/hf_start.sh"]