# ---- stage 1: build the React frontend -------------------------------------
FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- stage 2: Python API serving the built frontend -------------------------
FROM python:3.12-slim
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache \
    PYTHONUNBUFFERED=1

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Pre-bake the embedding, sparse, and reranker models into the image so free-tier
# hosts don't spend their cold start (or ephemeral disk) downloading ~250 MB.
RUN python -c "\
from fastembed import TextEmbedding, SparseTextEmbedding; \
from fastembed.rerank.cross_encoder import TextCrossEncoder; \
TextEmbedding('BAAI/bge-small-en-v1.5'); \
SparseTextEmbedding('Qdrant/bm25'); \
TextCrossEncoder('Xenova/ms-marco-MiniLM-L-6-v2')"

COPY backend/app ./app
COPY --from=frontend /build/dist ./static

# Render/Fly set PORT; Hugging Face Spaces expects 7860 (set PORT=7860 there).
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
