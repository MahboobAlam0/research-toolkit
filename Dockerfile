# ─── Dockerfile (root) ─────────────────────────────────────────────────────────
# Used by Railway. Build context is the repo root so all paths are prefixed
# with backend/ unlike the local backend/Dockerfile which uses context=./backend
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY backend/requirements.txt .

# CPU-only PyTorch (~190 MB vs 532 MB for CUDA build)
RUN pip install --no-cache-dir --timeout=300 \
    torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu

# Remaining dependencies
RUN pip install --no-cache-dir --timeout=300 -r requirements.txt

# Pre-bake the embedding model so cold starts are fast
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('BAAI/bge-base-en-v1.5')"

# Verify PyMuPDF
RUN python -c "import fitz; print('PyMuPDF', fitz.version)"

# Copy backend source
COPY backend/ .

EXPOSE 8000

# Railway injects $PORT automatically
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
