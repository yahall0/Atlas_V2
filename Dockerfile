FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1
ENV NEXT_PUBLIC_API_URL=""

# Install prerequisites
RUN apt-get update && apt-get install -y \
    curl gnupg software-properties-common wget \
    supervisor nginx \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-guj \
    libglib2.0-0 poppler-utils \
    postgresql-14 postgresql-contrib redis-server \
    && rm -rf /var/lib/apt/lists/*

# Install Python 3.11
RUN add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update && \
    apt-get install -y python3.11 python3.11-venv python3.11-dev build-essential && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# Install MongoDB
RUN curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | \
    gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor && \
    echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list && \
    apt-get update && apt-get install -y mongodb-org && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /data/db /var/log/mongodb && \
    chown -R mongodb:mongodb /data/db /var/log/mongodb

# Setup Postgres Database
USER postgres
RUN /etc/init.d/postgresql start && \
    psql -c "CREATE USER atlas WITH SUPERUSER PASSWORD 'atlaspass';" && \
    createdb -O atlas atlas_db && \
    /etc/init.d/postgresql stop
USER root
# Allow local connections
RUN echo "host all all 127.0.0.1/32 trust" >> /etc/postgresql/14/main/pg_hba.conf && \
    echo "listen_addresses='*'" >> /etc/postgresql/14/main/postgresql.conf

WORKDIR /app

# 1. Setup Backend
COPY backend/ /app/backend/
WORKDIR /app/backend
RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# Force CPU-only PyTorch wheel to save container space and build time
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# 2. Setup Frontend
WORKDIR /app/frontend
COPY frontend/ /app/frontend/
RUN npm ci && npm run build

# 3. Setup Configurations
WORKDIR /app
COPY hf_nginx.conf /etc/nginx/sites-available/default
COPY hf_supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY hf_start.sh /app/hf_start.sh
RUN chmod +x /app/hf_start.sh

# Expose the single port that Hugging Face expects
EXPOSE 7860

CMD ["/app/hf_start.sh"]