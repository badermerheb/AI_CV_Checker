# AI CV Checker

A production-grade RAG app for recruiters: upload CVs/resumes, then chat with them —
"Who best fits this job description?", "Tell me about candidate X", or general questions
across all CVs. Answers come with inline citations back to the source CVs.

> Work in progress — see [PLAN.md](PLAN.md) for the full build plan and progress.

## Stack

React + Vite (frontend) · FastAPI + LlamaIndex (backend) · Qdrant (hybrid vector + keyword search)
· BGE embeddings + bge-reranker (local) · Gemini (LLM) · RAGAS (evaluation) · Langfuse (tracing)

## Run locally (dev)

```bash
# 1. Qdrant (Podman or Docker)
podman run -d --name qdrant -p 6333:6333 -p 6334:6334 \
  -v qdrant_storage:/qdrant/storage qdrant/qdrant

# 2. Backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env                              # then fill in your keys
uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd frontend
npm install
npm run dev                                       # http://localhost:5173
```

## Sample data

`data/generate_sample_cvs.py` generates 16 synthetic candidate CVs (PDF) plus
`data/ground_truth.json` — the fixed test set used by the evaluation harness.

```bash
backend/.venv/Scripts/python data/generate_sample_cvs.py
```

<!-- Architecture diagram + metrics table land here in later phases -->
