# ─── backend/Dockerfile ───────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install CPU-only PyTorch first (separate layer = cached independently)
# 2.2.2+cpu is ~190 MB; provides torch.compiler needed by transformers>=4.40
RUN pip install --no-cache-dir --timeout=300 \
    torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
RUN pip install --no-cache-dir --timeout=300 -r requirements.txt

# Pre-download embedding model at build time (avoids slow cold start)
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('BAAI/bge-base-en-v1.5')"

# Verify PyMuPDF is importable
RUN python -c "import fitz; print('PyMuPDF', fitz.version)"

COPY . .

EXPOSE 8000

# PORT is injected by Railway; falls back to 8000 for local Docker
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
